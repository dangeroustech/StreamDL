"""Record live streams and VODs with FFmpeg."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
import shutil
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
from .join import JoinResult, StreamInfo, join_parts, probe_parts
from .process import describe_exit
from .progress import (
    DownloadKind,
    FfmpegLogWriter,
    format_bytes,
    progress_key_live,
    progress_key_vod,
)
from .resolver import ResolverError, StreamURLs, VodInfo, is_twitch
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
    stem = f"{user}_{datetime.now():%Y-%m-%d_%H-%M-%S}"
    dirs = await _prepare_dirs(s.out_dir, s.move_dir, user, s.subfolder)
    if dirs is None:
        return
    out_dir, move_dir = dirs
    log.info("Starting Download for %s", user)

    parts: list[str] = []
    try:
        await _record_parts(
            rt, user, site, quality, initial, writer, out_dir, stem, parts
        )
        log.debug("Stream For %s Ended", user)
        await _finish_session(
            rt, user, site, post_script, parts, out_dir, move_dir, stem
        )
    except asyncio.CancelledError:
        if left := [p for p in parts if os.path.exists(p)]:
            log.info(
                "Shutting down: left %d part(s) for %s in %s", len(left), user, out_dir
            )
        raise


def _part_path(out_dir: str, stem: str, n: int) -> str:
    """Part 1 has the recording's plain name; later parts get a _part<n> suffix."""
    return os.path.join(out_dir, f"{stem}.mp4" if n == 1 else f"{stem}_part{n}.mp4")


async def _record_parts(
    rt: Runtime,
    user: str,
    site: str,
    quality: str,
    initial: StreamURLs,
    writer: FfmpegLogWriter,
    out_dir: str,
    stem: str,
    parts: list[str],
) -> None:
    """Record parts until the channel stays away, appending each part's path to parts.

    A clean FFmpeg exit opens the reconnect window; a failure, or a clean exit
    that recorded nothing, is retried after the usual backoff. Every attempt
    writes a new part, so nothing recorded is overwritten.
    """
    s = rt.settings
    key = progress_key_live(user)
    urls = initial
    failures = 0
    reconnects = 0
    has_data = False  # whether the last attempt recorded anything
    while True:
        if has_data:  # the progress line counts only parts that hold data
            rt.progress.next_part(key)
        path = _part_path(out_dir, stem, len(parts) + 1)
        parts.append(path)
        writer.clear()  # so each part's log tail is its own
        try:
            returncode, streamlink_tail = await _record_attempt(
                rt, user, site, quality, urls, path, writer
            )
        except OSError as e:
            what = "streamlink or FFmpeg" if _ad_free(rt, site) else "FFmpeg"
            log.error("Failed to start %s for %s: %s", what, user, e)
            return

        # A clean exit that left nothing behind is a failure too, so an FFmpeg
        # that keeps stopping at once can't record empty parts in a tight loop.
        has_data = await asyncio.to_thread(_has_data, path)
        if returncode == 0 and has_data:
            failures = 0
            _log_clean_exit(user, writer, streamlink_tail)
            stopped_at = rt.clock()
            fresh = await _wait_for_live(rt, site, user, quality)
            if fresh is None:
                return
            gap = rt.clock() - stopped_at
            n = len(parts) + 1
            log.info("%s came back after %.0fs; recording part %d", user, gap, n)
            reconnects += 1
            # Later reconnects are only logged, so a flapping stream can't
            # flood the notices.
            if reconnects == 1:
                rt.notices.info(
                    user, f"Stream came back after {gap:.0f}s; recording part {n}"
                )
        else:
            failures += 1
            if returncode == 0:
                reason = "nothing was recorded"
                log.warning("FFmpeg for %s exited without recording anything", user)
            else:
                reason = describe_exit(returncode)
                log.warning("FFmpeg failed for %s: %s", user, reason)
            if tail := tail_lines(writer.text(), LOG_TAIL_LINES):
                log.warning("FFmpeg log tail for %s:\n%s", user, sanitize_log(tail))
            if streamlink_tail:
                log.warning("streamlink log tail for %s:\n%s", user, streamlink_tail)
            if failures > s.ffmpeg.max_retries:
                log.error(
                    "FFmpeg failed for %s after %d attempts: %s", user, failures, reason
                )
                rt.notices.error(
                    user, f"Recording failed after {failures} attempts: {reason}"
                )
                return
            delay = s.ffmpeg.retry_base_delay * 2 ** (failures - 1)
            log.warning(
                "Recording failed for %s (attempt %d/%d). Retrying in %gs",
                user,
                failures,
                s.ffmpeg.max_retries,
                delay,
            )
            # Cleared by the lookup below, before the next attempt starts.
            rt.progress.set_status(key, "retrying")
            await rt.sleep(delay)
            # On the ad-free path the fresh URL itself goes unused: the lookup
            # checks the channel is still live before streamlink resolves it again.
            fresh = await _wait_for_live(rt, site, user, quality, at_least_once=True)
            if fresh is None:
                log.info(
                    "%s is no longer live after FFmpeg failed; finishing the recording",
                    user,
                )
                return
        if fresh.warning:
            rt.notices.warn(user, fresh.warning)
        urls = fresh


def _log_clean_exit(user: str, writer: FfmpegLogWriter, streamlink_tail: str) -> None:
    """Log FFmpeg's last lines after it stopped on its own, to show why it stopped."""
    if tail := tail_lines(writer.text(), LOG_TAIL_LINES):
        log.debug("FFmpeg log tail for %s:\n%s", user, sanitize_log(tail))
    if streamlink_tail:
        log.debug("streamlink log tail for %s:\n%s", user, streamlink_tail)


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


async def _finish_session(
    rt: Runtime,
    user: str,
    site: str,
    post_script: str,
    parts: list[str],
    out_dir: str,
    move_dir: str,
    stem: str,
) -> None:
    """Join the parts if there are several, then move the result and run the hook.

    Missing and empty parts (an attempt that failed at start-up or recorded
    nothing) are dropped, and empty part files deleted. Parts that can't be
    read are left out of the join and moved without the hook. A lone later
    part that survives takes the recording's plain name if it's free. The join
    can be stopped by shutdown, which leaves the parts in place; the moves and
    hooks always finish, as before.
    """
    recorded = await asyncio.to_thread(_recorded_parts, parts)
    if not recorded:
        log.warning("Nothing was recorded for %s", user)
        return
    unreadable: list[str] = []
    if len(recorded) > 1:
        recorded, unreadable = await _join_session(rt, user, recorded, out_dir, stem)
    plain = _part_path(out_dir, stem, 1)
    if len(recorded) == 1 and recorded[0] != plain:
        recorded = [await asyncio.to_thread(_take_plain_name, recorded[0], plain)]
    await _run_to_completion(
        _finish_files(rt, user, site, post_script, recorded, unreadable, move_dir)
    )


def _recorded_parts(parts: list[str]) -> list[str]:
    """The parts that hold data. Empty part files are deleted."""
    recorded = []
    for part in parts:
        if _has_data(part):
            recorded.append(part)
        elif os.path.isfile(part):
            log.debug("Deleting empty part %s", part)
            try:
                os.remove(part)
            except OSError as e:
                log.warning("Couldn't delete empty part %s: %s", part, e)
    return recorded


def _has_data(path: str) -> bool:
    try:
        return os.path.isfile(path) and os.path.getsize(path) > 0
    except OSError:  # deleted in between
        return False


def _take_plain_name(part: str, plain: str) -> str:
    """Rename a lone surviving later part to the recording's plain name.

    Returns the path to move: plain, or part if plain is taken or the rename fails.
    """
    if os.path.exists(plain):
        return part
    try:
        os.rename(part, plain)
    except OSError as e:
        log.warning("Couldn't rename %s to %s: %s", part, plain, e)
        return part
    return plain


def _join_space_shortfall(parts: list[str], out_dir: str) -> str:
    """Why the joined file wouldn't fit in out_dir, or "" if it would (or can't tell).

    The join needs room for a copy of every part, plus 5% to spare.
    """
    try:
        total = sum(os.path.getsize(p) for p in parts)
        needed = total + total // 20
        free = shutil.disk_usage(out_dir).free
    except OSError as e:
        log.debug("Couldn't check the free space in %s: %s", out_dir, e)
        return ""
    if free >= needed:
        return ""
    return (
        f"not enough free space to join (needs {format_bytes(needed)},"
        f" {format_bytes(free)} free)"
    )


async def _join_session(
    rt: Runtime, user: str, parts: list[str], out_dir: str, stem: str
) -> tuple[list[str], list[str]]:
    """Join the parts that can be read; return the files to move with the hook
    and the unreadable parts to move without it.

    Each unreadable part gets a notice. If no part can be read, they're all
    kept as they are and moved with the hook, as are readable parts that can't
    be joined; a notice says why. A lone readable part is returned unjoined.
    """
    key = progress_key_live(user)
    rt.progress.set_status(key, "joining")
    try:
        readable, unreadable = await probe_parts(
            parts, ffprobe=rt.settings.ffprobe_path
        )
        if not readable:
            reason = f"none of them can be read ({unreadable[parts[0]]})"
            _keep_parts(rt, user, parts, JoinResult(ok=False, reason=reason))
            return parts, []
        for path, error in unreadable.items():
            name = os.path.basename(path)
            log.warning(
                "Leaving %s out of the join for %s: it can't be read (%s)",
                name,
                user,
                error,
            )
            rt.notices.warn(
                user,
                f"A part couldn't be read and was kept separately as {name}:"
                f" {error.removeprefix(f'{path}: ')}",
            )
        if len(readable) == 1:
            return list(readable), list(unreadable)
        final = _part_path(out_dir, stem, 1)
        if final in unreadable:  # the plain name stays with the unreadable part 1
            final = next(iter(readable))
        return await _join(rt, user, readable, out_dir, stem, final), list(unreadable)
    finally:
        rt.progress.set_status(key, "")


async def _join(
    rt: Runtime,
    user: str,
    parts: dict[str, list[StreamInfo]],
    out_dir: str,
    stem: str,
    final: str,
) -> list[str]:
    """Join parts (each path mapped to its streams) into final; return the files
    to move.

    That is final alone when the join worked. Otherwise the parts are kept as
    they are, and a notice says why.
    """
    s = rt.settings
    paths = list(parts)
    joining = os.path.join(out_dir, f"{stem}.joining.mp4")
    # Not a progress entry, so the join's own progress lines are ignored.
    writer = FfmpegLogWriter(f"{progress_key_live(user)}:join", rt.progress)
    joined = False
    try:
        if shortfall := await asyncio.to_thread(_join_space_shortfall, paths, out_dir):
            result = JoinResult(ok=False, reason=shortfall)
        else:
            result = await join_parts(parts, joining, writer, ffmpeg=s.ffmpeg_path)
        if result.ok:
            # From here to the return nothing is awaited, so these file operations
            # run on the event loop: shutdown can't land between the rename and
            # the deletes. final (if it's there) is replaced first, so the
            # recording always exists under one name or another.
            try:
                os.replace(joining, final)
                joined = True
            except OSError as e:
                result = JoinResult(
                    ok=False, reason=f"the joined file couldn't be renamed ({e})"
                )
    finally:
        if not joined:
            with contextlib.suppress(OSError):
                os.remove(joining)
    if not joined:
        _keep_parts(rt, user, paths, result)
        return paths

    for part in paths:
        if part != final:
            try:
                os.remove(part)
            except OSError as e:
                log.warning("Couldn't delete joined part %s: %s", part, e)
    log.info(
        "Joined %d parts for %s into %s", len(paths), user, os.path.basename(final)
    )
    return [final]


def _keep_parts(rt: Runtime, user: str, parts: list[str], result: JoinResult) -> None:
    """Say why the parts weren't joined, in the log and in a notice."""
    log.warning("Keeping %d separate parts for %s: %s", len(parts), user, result.reason)
    if result.log_tail:
        log.warning("FFmpeg join log tail for %s:\n%s", user, result.log_tail)
    rt.notices.warn(user, f"Kept {len(parts)} separate parts: {result.reason}")


async def _finish_files(
    rt: Runtime,
    user: str,
    site: str,
    post_script: str,
    paths: list[str],
    unreadable: list[str],
    move_dir: str,
) -> None:
    """Move paths and run the hook on each; move the unreadable parts without it."""
    for path in paths:
        new_path = os.path.join(move_dir, os.path.basename(path))
        await _finish_live(rt, user, site, post_script, path, new_path)
    for path in unreadable:
        new_path = os.path.join(move_dir, os.path.basename(path))
        await _finish_live(rt, user, site, "", path, new_path)  # "": no hook


async def _wait_for_live(
    rt: Runtime, site: str, user: str, quality: str, *, at_least_once: bool = False
) -> StreamURLs | None:
    """Check whether user is live again, for up to RECONNECT_WINDOW seconds.

    The first check runs at once and later ones RECONNECT_INTERVAL seconds after
    the previous one started; a check that started inside the window may finish
    after it. Lookup errors (offline, rate limited, network) only mean "check
    again": none ends the window early or adds a notice. With at_least_once, one
    check runs even when the window is 0, since a failure retry always looks the
    stream up again.
    """
    opts = rt.settings.reconnect
    if opts.window <= 0 and not at_least_once:
        return None
    key = progress_key_live(user)
    deadline = rt.clock() + opts.window
    rt.progress.set_status(key, "reconnecting")
    try:
        while True:
            started = rt.clock()
            try:
                async with rt.site_lock(site):
                    return await rt.resolver.stream(site, user, quality)
            except ResolverError as e:
                log.debug("Reconnect check for %s: %s", user, e)
            next_check = max(started + opts.interval, rt.clock())
            if next_check >= deadline:
                log.debug("%s didn't come back within %ds", user, opts.window)
                return None
            if (delay := next_check - rt.clock()) > 0:
                await rt.sleep(delay)
    finally:
        rt.progress.set_status(key, "")


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
