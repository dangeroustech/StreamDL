"""The main loop: check every configured channel each round and start recordings."""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
from collections.abc import Coroutine
from datetime import datetime
from typing import Any

from .config import Channel, ConfigLoader, Site
from .progress import log_active_download_summary
from .recorder import RATE_LIMIT_BACKOFFS, mark_vod_failed, record_live, record_vod
from .resolver import RateLimited, ResolverError, StreamURLs
from .runtime import Runtime
from .vod_db import VodDB

log = logging.getLogger(__name__)

BANNER = "-" * 41
MIN_STALE_SECONDS = 600


def vod_stream_user(vod_id: str) -> str:
    """Lookup path for a VOD: yt-dlp lists Twitch IDs as 'v123'; streamlink wants videos/123."""
    return "videos/" + vod_id.removeprefix("v")


class Scheduler:
    def __init__(self, rt: Runtime, config: ConfigLoader) -> None:
        self.rt = rt
        self.config = config
        self._recordings: set[asyncio.Task[None]] = set()
        self._vod_db: VodDB | None = None

    @property
    def recordings(self) -> set[asyncio.Task[None]]:
        return set(self._recordings)

    async def run(self, stop: asyncio.Event) -> None:
        """Run rounds until stop is set, then shut recordings down cleanly.

        This is a plain loop (never recursion), so it can run indefinitely. Each round
        starts one tick after the previous one started, or at once if it overran.
        """
        loop = asyncio.get_running_loop()
        try:
            while not stop.is_set():
                started = loop.time()
                if not await self._run_round_until(stop):
                    break
                delay = max(0.0, started + self.rt.settings.tick_seconds - loop.time())
                try:
                    await asyncio.wait_for(stop.wait(), delay)
                except TimeoutError:
                    pass
        finally:
            await self.shutdown()

    async def _run_round_until(self, stop: asyncio.Event) -> bool:
        """Run one round; return False if stop was set before it finished."""
        round_task = asyncio.create_task(self.run_round())
        stop_task = asyncio.create_task(stop.wait())
        try:
            await asyncio.wait(
                {round_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
            )
        finally:
            # Also reached if run() itself is cancelled: never leave either running.
            round_task.cancel()
            stop_task.cancel()
            await asyncio.gather(round_task, stop_task, return_exceptions=True)
        if round_task.cancelled():
            return False
        if (exc := round_task.exception()) is not None:
            log.error("Round failed: %s", exc, exc_info=exc)
        return True

    async def shutdown(self) -> None:
        """Stop recordings (FFmpeg gets SIGINT), wait for post-scripts, then close
        the resolver and the VOD database."""
        recordings = list(self._recordings)
        if recordings:
            log.info("Stopping %d active recording(s)...", len(recordings))
        for task in recordings:
            task.cancel()
        try:
            await asyncio.gather(*recordings, return_exceptions=True)
            if pending := self.rt.running_post_scripts:
                # docker stop's default 10s grace period may cut this short.
                log.info("Waiting for %d post-script(s) to finish...", pending)
            await self.rt.wait_for_post_scripts()
        finally:
            self.rt.resolver.close()
            if self._vod_db is not None:
                if all(task.done() for task in recordings):
                    self._vod_db.close()
                    self._vod_db = None
                else:
                    # Shutdown was itself cancelled: recordings may still update it.
                    log.debug("Recordings still running; VOD database left open")

    async def run_round(self) -> None:
        """Check every channel once, then log live users, progress and notices."""
        rt = self.rt
        log.info(BANNER)
        log.info("Running StreamDL at %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        log.info(BANNER)
        for site in self.config.reload():
            for channel in site.channels:
                log.debug(
                    "Checking user=%s on site=%s quality=%s vod=%s",
                    channel.name,
                    site.site,
                    channel.quality,
                    str(channel.vod).lower(),
                )
                if channel.vod:
                    await self._check_vods(site, channel)
                elif channel.name in rt.active:
                    log.debug("%s is already being recorded", channel.name)
                else:
                    await self._check_live(site, channel)
        log.info("Currently Live Users: %s", ", ".join(sorted(rt.active)))
        log_active_download_summary(rt.progress)
        rt.notices.flush(rt.settings.tick_seconds)

    async def _check_live(self, site: Site, channel: Channel) -> None:
        rt = self.rt
        for attempt, backoff in enumerate(RATE_LIMIT_BACKOFFS):
            if backoff:
                log.error("Rate Limited, Sleeping for %ds", backoff)
                await rt.sleep(backoff)
            urls: StreamURLs | None = None
            error: ResolverError | None = None
            try:
                async with rt.site_lock(site.site):
                    urls = await rt.resolver.stream(
                        site.site, channel.name, channel.quality
                    )
            except ResolverError as e:
                error = e
            if attempt == 0:
                await rt.sleep(rt.settings.batch_seconds)

            if urls is not None:
                rt.active.add(channel.name)
                log.debug("Discovered live stream for user=%s", channel.name)
                if urls.warning:
                    rt.notices.warn(channel.name, urls.warning)
                self._spawn(
                    record_live(
                        rt,
                        channel.name,
                        site.site,
                        channel.quality,
                        urls,
                        site.post_script,
                    ),
                    name=f"record:{channel.name}",
                )
                return
            if not isinstance(error, RateLimited):
                rt.notices.warn(channel.name, str(error))
                return
            if attempt == len(RATE_LIMIT_BACKOFFS) - 1:
                rt.notices.error(
                    channel.name, "Rate limited three times, skipping this tick"
                )

    async def _check_vods(self, site: Site, channel: Channel) -> None:
        rt = self.rt
        db = self._vod_database()
        if db is None:
            return
        vods = []
        error: ResolverError | None = None
        try:
            vods = await rt.resolver.vods(
                site.site, channel.name, channel.effective_vod_limit
            )
        except ResolverError as e:
            error = e
        await rt.sleep(rt.settings.batch_seconds)
        if isinstance(error, RateLimited):
            rt.notices.error(
                channel.name, "Rate limited checking VODs, skipping this tick"
            )
            return
        if error is not None:
            rt.notices.warn(channel.name, f"GetVods failed: {error}")
            return

        stale = max(2 * rt.settings.tick_seconds, MIN_STALE_SECONDS)
        for vod in vods:
            if vod.id in rt.active_vods:
                # Still downloading in this process: never start a second FFmpeg on
                # it, however long it runs (v3 re-claimed it after the stale cutoff).
                # The stale re-claim below is for downloads lost to a crash.
                log.debug("VOD %s is already being downloaded, skipping", vod.id)
                continue
            try:
                claimed = db.claim(vod.id, channel.name, site.site, vod.title, stale)
            except sqlite3.Error as e:
                log.error("Error claiming VOD %s: %s", vod.id, e)
                continue
            if not claimed:
                log.debug("VOD %s already completed or in progress, skipping", vod.id)
                continue
            log.info("VOD to download for %s: %s (%s)", channel.name, vod.title, vod.id)
            # If the round is cancelled during this lookup (shutdown), the claim stays
            # 'downloading' until the stale cutoff lets a later run retry it, as in v3.
            try:
                async with rt.site_lock(site.site):
                    urls = await rt.resolver.stream(
                        site.site, vod_stream_user(vod.id), channel.quality
                    )
            except ResolverError as e:
                await rt.sleep(rt.settings.batch_seconds)
                rt.notices.warn(channel.name, f"Failed to resolve VOD {vod.id}: {e}")
                mark_vod_failed(db, vod.id)
                continue
            await rt.sleep(rt.settings.batch_seconds)
            rt.active_vods.add(vod.id)
            self._spawn(
                record_vod(
                    rt, channel.name, site.site, vod, urls.video, site.post_script, db
                ),
                name=f"vod:{vod.id}",
            )

    def _vod_database(self) -> VodDB | None:
        """Open the VOD database the first time a VOD channel is checked."""
        if self._vod_db is None:
            path = os.path.join(self.rt.settings.data_dir, "streamdl.db")
            try:
                self._vod_db = VodDB(path)
            except (OSError, sqlite3.Error) as e:
                log.error("Failed to initialize VOD database: %s", e)
                return None
            log.info("VOD tracking database initialized at %s", path)
        return self._vod_db

    def _spawn(self, coro: Coroutine[Any, Any, None], *, name: str) -> None:
        task = asyncio.create_task(coro, name=name)
        self._recordings.add(task)
        task.add_done_callback(self._recording_done)

    def _recording_done(self, task: asyncio.Task[None]) -> None:
        self._recordings.discard(task)
        if not task.cancelled() and (exc := task.exception()) is not None:
            log.error(
                "Recording task %s failed: %s", task.get_name(), exc, exc_info=exc
            )
