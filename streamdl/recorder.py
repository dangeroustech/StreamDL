"""Record live streams and VODs with FFmpeg."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from datetime import datetime
from typing import TYPE_CHECKING

from .ffmpeg import build_live_args, sanitize_args, sanitize_log, tail_lines
from .files import create_dir_with_umask, move_file
from .process import describe_exit
from .progress import DownloadKind, FfmpegLogWriter, progress_key_live
from .resolver import RateLimited, ResolverError, StreamURLs

if TYPE_CHECKING:
    from .runtime import Runtime

log = logging.getLogger(__name__)

RATE_LIMIT_BACKOFFS = (0, 30, 60)
LOG_TAIL_LINES = 50


async def run_ffmpeg(args: list[str], writer: FfmpegLogWriter) -> int:
    """Run FFmpeg to completion, streaming its stderr into writer.

    If the task is cancelled (shutdown), FFmpeg gets SIGINT so it can finalize the
    MP4, and we wait for it to exit before re-raising. Raises OSError if FFmpeg
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
            log.debug("Sending SIGINT to FFmpeg (pid %d)", proc.pid)
            try:
                proc.send_signal(signal.SIGINT)
            except ProcessLookupError:
                pass  # exited between the check and the signal
            await _drain(proc, writer)
        raise


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
            fresh = await _resolve_retry_url(rt, site, user, quality)
            if fresh is None:
                return
            urls = fresh
        args = build_live_args(
            urls.video, urls.audio, out_path, s.ffmpeg, ffmpeg=s.ffmpeg_path
        )
        log.debug("FFmpeg args (sanitized): %s", sanitize_args(args))
        try:
            returncode = await run_ffmpeg(args, writer)
        except OSError as e:
            log.error("Failed to start FFmpeg for %s: %s", user, e)
            return
        if returncode == 0:
            break

        reason = describe_exit(returncode)
        log.warning("FFmpeg failed for %s: %s", user, reason)
        if tail := tail_lines(writer.text(), LOG_TAIL_LINES):
            log.warning("FFmpeg log tail for %s:\n%s", user, sanitize_log(tail))
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
    log.debug("Moving file to %s", move_dir)
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
