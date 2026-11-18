"""Record live streams and VODs with FFmpeg."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import signal
import sqlite3
from collections.abc import Coroutine
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .ffmpeg import (
    build_live_args,
    build_pipe_args,
    build_vod_args,
    sanitize_args,
    sanitize_log,
    tail_lines,
)
from .files import create_dir_with_umask, move_file, sanitize_filename
from .process import describe_exit
from .progress import DownloadKind, FfmpegLogWriter, progress_key_live, progress_key_vod
from .resolver import RateLimited, ResolverError, StreamURLs, VodInfo, is_twitch
from .twitch_pipe import (
    PipeResult,
    StreamlinkLog,
    build_streamlink_args,
    run_pipe,
    streamlink_config,
)

if TYPE_CHECKING:
    from .runtime import Runtime
    from .vod_db import VodDB

log = logging.getLogger(__name__)

RATE_LIMIT_BACKOFFS = (0, 30, 60)
LOG_TAIL_LINES = 50
_RE_UNSAFE_ID = re.compile(r"[^A-Za-z0-9_-]")


def filename_safe_id(vod_id: str) -> str:
    """A VOD id for use in a filename: anything but [A-Za-z0-9_-] becomes "_".

    Normal Twitch ("v123456") and YouTube ids are unchanged.
    """
    return _RE_UNSAFE_ID.sub("_", vod_id)[:100]


async def run_ffmpeg(args: list[str], writer: FfmpegLogWriter) -> int:
    """Run FFmpeg to completion, streaming its stderr into writer.

    If the task is cancelled (shutdown), FFmpeg gets SIGINT so it can finalize the
    MP4, and we wait for it to exit before re-raising. On any other error (or if
    that wait fails or is cancelled again) FFmpeg is killed and reaped, so it is
    never left running with nobody reading its stderr. Raises OSError if FFmpeg
    can't be started.
    """
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        return await _drain(proc, writer)
    except asyncio.CancelledError:
        if proc.returncode is None:
            await _interrupt(proc, writer)
        raise
    except BaseException:
        await _kill(proc)
        raise


async def _interrupt(proc: asyncio.subprocess.Process, writer: FfmpegLogWriter) -> None:
    """SIGINT FFmpeg and wait for it to finalize; kill it if the wait goes wrong."""
    log.debug("Sending SIGINT to FFmpeg (pid %d)", proc.pid)
    try:
        proc.send_signal(signal.SIGINT)
    except ProcessLookupError:
        pass  # exited between the check and the signal
    try:
        await _drain(proc, writer)
    except BaseException:
        await _kill(proc)
        raise


async def _kill(proc: asyncio.subprocess.Process) -> None:
    """SIGKILL FFmpeg if it is still running; reap it even if cancelled."""
    if proc.returncode is None:
        log.debug("Killing FFmpeg (pid %d)", proc.pid)
        try:
            proc.kill()
        except ProcessLookupError:
            pass
    await asyncio.shield(proc.wait())


async def _run_to_completion(coro: Coroutine[Any, Any, None]) -> None:
    """Run coro to the end even if the caller is cancelled meanwhile.

    Used for the work after FFmpeg exits on its own (move, database update, hook),
    which v3 always finished. Every cancellation (a second one included) waits for
    coro to finish, then CancelledError is re-raised.
    """
    fin = asyncio.ensure_future(coro)
    cancelled = False
    while not fin.done():
        try:
            await asyncio.shield(fin)
        except asyncio.CancelledError:
            cancelled = True
    fin.result()  # coro's own error, if it failed
    if cancelled:
        raise asyncio.CancelledError


async def _drain(proc: asyncio.subprocess.Process, writer: FfmpegLogWriter) -> int:
    if proc.stderr is not None:
        while chunk := await proc.stderr.read(4096):
            writer.write(chunk)
    return await proc.wait()


async def _prepare_dirs(
    out_dir: str, move_dir: str, user: str, subfolder: bool
) -> tuple[str, str] | None:
    """Create the download and move directories (plus per-user subfolders).

    Runs in a worker thread so a slow (e.g. NFS) mount can't stall the loop. On
    failure the error is logged like v3 and None is returned.
    """
    dirs = [("output directory", out_dir), ("move directory", move_dir)]
    if subfolder:
        out_dir, move_dir = os.path.join(out_dir, user), os.path.join(move_dir, user)
        dirs += [("output subfolder", out_dir), ("move subfolder", move_dir)]
    for label, path in dirs:
        try:
            await asyncio.to_thread(create_dir_with_umask, path)
        except OSError as e:
            log.error("Failed to create %s %s: %s", label, path, e)
            return None
    return out_dir, move_dir


async def record_live(
    rt: Runtime,
    user: str,
    site: str,
    quality: str,
    initial: StreamURLs,
    post_script: str,
) -> None:
    """Record a live stream until it ends, retrying FFmpeg failures with fresh URLs.

    The channel is always removed from rt.active when this returns, so the next
    round can pick it up again.
    """
    key = progress_key_live(user)
    rt.progress.start(key, channel=user, kind=DownloadKind.LIVE)
    writer = FfmpegLogWriter(key, rt.progress)
    try:
        await _record_live(rt, user, site, quality, initial, post_script, writer)
    finally:
        rt.active.discard(user)
        rt.notices.clear_channel(user)
        rt.progress.end(key)
        log.debug("Removed %s from active list", user)


async def _record_live(
    rt: Runtime,
    user: str,
    site: str,
    quality: str,
    initial: StreamURLs,
    post_script: str,
    writer: FfmpegLogWriter,
) -> None:
    s = rt.settings
    filename = f"{user}_{datetime.now():%Y-%m-%d_%H-%M-%S}.mp4"
    dirs = await _prepare_dirs(s.out_dir, s.move_dir, user, s.subfolder)
    if dirs is None:
        return
    out_dir, move_dir = dirs
    out_path = os.path.join(out_dir, filename)
    new_path = os.path.join(move_dir, filename)
    log.info("Starting Download for %s", user)

    urls = initial
    attempt = 0
    while True:
        if attempt > 0:
            # On the ad-free path the fresh URL itself goes unused: the lookup
            # checks the channel is still live (backing off if rate limited)
            # before streamlink resolves the stream again.
            fresh = await _resolve_retry_url(rt, site, user, quality)
            if fresh is None:
                return
            urls = fresh
        try:
            returncode, streamlink_tail = await _record_attempt(
                rt, user, site, quality, urls, out_path, writer
            )
        except OSError as e:
            what = "streamlink or FFmpeg" if _ad_free(rt, site) else "FFmpeg"
            log.error("Failed to start %s for %s: %s", what, user, e)
            return
        if returncode == 0:
            break

        reason = describe_exit(returncode)
        log.warning("FFmpeg failed for %s: %s", user, reason)
        if tail := tail_lines(writer.text(), LOG_TAIL_LINES):
            log.warning("FFmpeg log tail for %s:\n%s", user, sanitize_log(tail))
        if streamlink_tail:
            log.warning("streamlink log tail for %s:\n%s", user, streamlink_tail)
        if attempt >= s.ffmpeg.max_retries:
            log.error(
                "FFmpeg failed for %s after %d attempts: %s", user, attempt, reason
            )
            rt.notices.error(
                user, f"Recording failed after {attempt} attempts: {reason}"
            )
            return
        attempt += 1
        delay = s.ffmpeg.retry_base_delay * 2 ** (attempt - 1)
        log.warning(
            "FFmpeg exited with error for %s (attempt %d/%d). Retrying in %gs",
            user,
            attempt,
            s.ffmpeg.max_retries,
            delay,
        )
        await rt.sleep(delay)

    log.debug("Stream For %s Ended", user)
    await _run_to_completion(
        _finish_live(rt, user, site, post_script, out_path, new_path)
    )


def _ad_free(rt: Runtime, site: str) -> bool:
    return rt.settings.twitch.adfree and is_twitch(site)


async def _record_attempt(
    rt: Runtime,
    user: str,
    site: str,
    quality: str,
    urls: StreamURLs,
    out_path: str,
    writer: FfmpegLogWriter,
) -> tuple[int, str]:
    """Run one recording attempt; return FFmpeg's exit code and streamlink's log tail.

    Twitch, when ad-free recording is on, goes through streamlink, which drops ad
    segments. FFmpeg's exit code alone decides the outcome: if FFmpeg finished the
    file, it's kept even when streamlink failed.
    """
    s = rt.settings
    if not _ad_free(rt, site):
        args = build_live_args(
            urls.video, urls.audio, out_path, s.ffmpeg, ffmpeg=s.ffmpeg_path
        )
        log.debug("FFmpeg args (sanitized): %s", sanitize_args(args))
        return await run_ffmpeg(args, writer), ""

    token = s.twitch.oauth_token
    with streamlink_config(token) as config:
        streamlink_args = build_streamlink_args(
            user, quality, config, cmd=s.streamlink_cmd
        )
        ffmpeg_args = build_pipe_args(out_path, s.ffmpeg, ffmpeg=s.ffmpeg_path)
        log.debug("streamlink args: %s", " ".join(streamlink_args))
        log.debug("FFmpeg args (sanitized): %s", sanitize_args(ffmpeg_args))
        result = await run_pipe(
            streamlink_args,
            ffmpeg_args,
            writer,
            StreamlinkLog(user, rt.notices, token=token),
        )
    if result.ffmpeg_rc == 0 and result.streamlink_rc != 0:
        _log_streamlink_exit(user, result)
    return result.ffmpeg_rc, result.streamlink_tail


def _log_streamlink_exit(user: str, result: PipeResult) -> None:
    """Log a streamlink failure after FFmpeg finished the file.

    A stop we caused (FFmpeg exited first) and a read timeout (Twitch stopped
    serving segments, which is how a broadcast usually ends) are expected.
    """
    reason = describe_exit(result.streamlink_rc)
    if result.streamlink_stopped:
        log.debug("Stopped streamlink for %s after FFmpeg finished (%s)", user, reason)
    elif "read timeout" in result.streamlink_tail.lower():
        log.info(
            "streamlink stopped receiving data for %s (the stream has probably "
            "ended); keeping what was recorded",
            user,
        )
    else:
        log.warning(
            "streamlink failed for %s (%s); keeping what was recorded", user, reason
        )
        if result.streamlink_tail:
            log.warning("streamlink log tail for %s:\n%s", user, result.streamlink_tail)


async def _finish_live(
    rt: Runtime, user: str, site: str, post_script: str, out_path: str, new_path: str
) -> None:
    log.debug("Moving file to %s", os.path.dirname(new_path))
    try:
        await asyncio.to_thread(move_file, out_path, new_path)
    except OSError as e:
        log.error("Failed to move file: %s", e)
        return
    log.debug("Moved file to %s", new_path)
    rt.spawn_post_script(post_script, new_path, user, site, "live")


async def _resolve_retry_url(
    rt: Runtime, site: str, user: str, quality: str
) -> StreamURLs | None:
    """Resolve a fresh URL for a retry. The site lock is held across rate-limit backoffs."""
    async with rt.site_lock(site):
        for attempt, backoff in enumerate(RATE_LIMIT_BACKOFFS):
            if backoff:
                log.warning(
                    "Rate limited resolving URL for %s, sleeping %ds", user, backoff
                )
                await rt.sleep(backoff)
            try:
                return await rt.resolver.stream(site, user, quality)
            except RateLimited:
                if attempt == len(RATE_LIMIT_BACKOFFS) - 1:
                    rt.notices.error(
                        user,
                        "Rate limited resolving stream URL after multiple attempts",
                    )
            except ResolverError as e:
                rt.notices.warn(user, f"Failed to resolve stream URL: {e}")
                return None
    return None


async def record_vod(
    rt: Runtime,
    user: str,
    site: str,
    vod: VodInfo,
    url: str,
    post_script: str,
    db: VodDB,
) -> None:
    """Download one VOD with stream copy and record the outcome in the database.

    A download cancelled by shutdown stays 'downloading', so the stale threshold
    re-claims it in a later round.
    """
    key = progress_key_vod(user, vod.id)
    rt.progress.start(
        key,
        channel=user,
        kind=DownloadKind.VOD,
        vod_id=vod.id,
        title=vod.title,
        total_duration=float(max(vod.duration_seconds, 0)),
    )
    writer = FfmpegLogWriter(key, rt.progress)
    try:
        await _record_vod(rt, user, site, vod, url, post_script, db, writer)
    finally:
        rt.active_vods.discard(vod.id)
        rt.progress.end(key)


async def _record_vod(
    rt: Runtime,
    user: str,
    site: str,
    vod: VodInfo,
    url: str,
    post_script: str,
    db: VodDB,
    writer: FfmpegLogWriter,
) -> None:
    s = rt.settings
    title = sanitize_filename(vod.title)
    filename = (
        f"{user}_vod_{filename_safe_id(vod.id)}"
        + (f"_{title}" if title else "")
        + ".mp4"
    )
    dirs = await _prepare_dirs(s.vod_out_dir, s.vod_move_dir, user, s.subfolder)
    if dirs is None:
        mark_vod_failed(db, vod.id)
        return
    out_dir, move_dir = dirs
    out_path = os.path.join(out_dir, filename)
    new_path = os.path.join(move_dir, filename)
    log.info("Starting VOD download for %s: %s", user, vod.title)

    args = build_vod_args(url, out_path, ffmpeg=s.ffmpeg_path)
    log.debug("FFmpeg VOD args (sanitized): %s", sanitize_args(args))
    try:
        returncode = await run_ffmpeg(args, writer)
    except OSError as e:
        log.error("Failed to start FFmpeg for VOD %s: %s", vod.id, e)
        mark_vod_failed(db, vod.id)
        return
    if returncode != 0:
        reason = describe_exit(returncode)
        log.warning("FFmpeg failed for VOD %s: %s", vod.id, reason)
        if tail := tail_lines(writer.text(), LOG_TAIL_LINES):
            log.debug("FFmpeg log tail for VOD %s:\n%s", vod.id, sanitize_log(tail))
        rt.notices.warn(user, f"VOD {vod.id} recording failed: {reason}")
        mark_vod_failed(db, vod.id)
        return

    log.debug("VOD %s download complete", vod.id)
    await _run_to_completion(
        _finish_vod(rt, user, site, vod, post_script, db, out_path, new_path)
    )


async def _finish_vod(
    rt: Runtime,
    user: str,
    site: str,
    vod: VodInfo,
    post_script: str,
    db: VodDB,
    out_path: str,
    new_path: str,
) -> None:
    try:
        await asyncio.to_thread(move_file, out_path, new_path)
    except OSError as e:
        log.error("Failed to move VOD file: %s", e)
        mark_vod_failed(db, vod.id)
        return
    log.debug("Moved VOD to %s", new_path)
    try:
        db.mark_completed(vod.id)
    except (LookupError, sqlite3.Error) as e:
        log.error("Failed to mark VOD %s as completed: %s", vod.id, e)
    rt.spawn_post_script(
        post_script, new_path, user, site, "vod", label=f"VOD {vod.id}"
    )


def mark_vod_failed(db: VodDB, vod_id: str) -> None:
    """Mark a VOD failed so a later round retries it; errors are logged, not raised."""
    try:
        db.mark_failed(vod_id)
    except (LookupError, sqlite3.Error) as e:
        log.error("Failed to mark VOD %s as failed: %s", vod_id, e)
