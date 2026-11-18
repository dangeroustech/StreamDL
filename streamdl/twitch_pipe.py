"""Ad-free Twitch recording: streamlink reads the stream and pipes it into FFmpeg.

streamlink's Twitch plugin drops ad segments, so a recording skips ahead where an
ad ran instead of containing it. A Twitch login token (Turbo or a channel sub)
avoids the ads, and the gaps, altogether.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import signal
import tempfile
from collections import deque
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .ffmpeg import sanitize_log
from .resolver import HTTP_TIMEOUT, TOKEN_REJECTED

if TYPE_CHECKING:
    from .notices import NoticeBuffer
    from .progress import FfmpegLogWriter

log = logging.getLogger(__name__)

TAIL_LINES = 50  # streamlink lines kept for failure logs
MAX_LINE_CHARS = 4096  # longer lines are cut, after redaction
_MAX_PARTIAL = 64 * 1024  # bytes kept of a line that hasn't ended yet
_RE_AD_BREAK = re.compile(
    r"detected advertisement break of (\d+) seconds?", re.IGNORECASE
)
_PRE_ROLL = "waiting for pre-roll ads"
STREAMLINK_TERM_GRACE = 3.0  # seconds streamlink gets to exit after SIGTERM
# Twitch's API error for a bad token; a segment's "401 ... Unauthorized for url"
# has no colon right after the word and doesn't match.
_RE_UNAUTHORIZED = re.compile(r"unauthorized: .*", re.IGNORECASE)


def build_streamlink_args(
    user: str, quality: str, config_path: str | None, *, cmd: Sequence[str]
) -> list[str]:
    """streamlink argv that writes the channel's stream to stdout.

    The token never goes in argv, where the process list would show it; streamlink
    reads it from config_path. With a token, --config replaces streamlink's default
    config file, though a plugin-specific config.twitch would still load; without
    one, --no-config skips both. Sideloaded plugins are never loaded.
    """
    config = ["--config", config_path] if config_path else ["--no-config"]
    # Never tie streamlink's log level to LOG_LEVEL: at debug it prints the
    # --twitch-api-header value, token included, to stderr.
    # fmt: off
    return [
        *cmd,
        "--stdout",
        "--loglevel", "info",
        "--no-plugin-sideloading",
        "--http-timeout", f"{HTTP_TIMEOUT:g}",
        *config,
        f"twitch.tv/{user}",
        quality or "best",
    ]
    # fmt: on


@contextmanager
def streamlink_config(token: str) -> Iterator[str | None]:
    """A private streamlink config file holding the token, removed on exit.

    Yields None when there is no token.
    """
    if not token:
        yield None
        return
    directory = tempfile.mkdtemp(prefix="streamdl-")  # mode 0700
    try:
        path = os.path.join(directory, "streamlink.conf")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(f"twitch-api-header=Authorization=OAuth {token}\n")
        yield path
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def ad_notice(line: str) -> str | None:
    """The notice for a streamlink ad message, or None for any other line."""
    if match := _RE_AD_BREAK.search(line):
        return f"Skipping a {match[1]}s ad break"
    if _PRE_ROLL in line.lower():
        return "Skipping pre-roll ads"
    return None


class StreamlinkLog:
    """Reads streamlink's stderr for one recording.

    Every line is logged at DEBUG and kept in a short tail for failure logs, with
    signed-URL secrets and the login token redacted. Ad messages become info
    notices for the channel; a rejected token becomes an error notice.

    Not thread-safe; call from the event loop only.
    """

    def __init__(self, user: str, notices: NoticeBuffer, *, token: str = "") -> None:
        self._user = user
        self._notices = notices
        self._token = token
        self._lines: deque[str] = deque(maxlen=TAIL_LINES)
        self._partial = b""

    def write(self, data: bytes) -> None:
        *lines, self._partial = re.split(rb"[\r\n]", self._partial + data)
        if len(self._partial) > _MAX_PARTIAL:  # output with no CR/LF at all
            # Handled whole, so a cut can never split a secret before redaction.
            lines.append(self._partial)
            self._partial = b""
        for raw in lines:
            self._handle(raw)

    def close(self) -> None:
        """Handle a last line that had no line break."""
        partial, self._partial = self._partial, b""
        self._handle(partial)

    def tail(self) -> str:
        return "\n".join(self._lines)

    def _handle(self, raw: bytes) -> None:
        line = self._redact(raw.decode("utf-8", "replace").strip())[:MAX_LINE_CHARS]
        if not line:
            return
        self._lines.append(line)
        log.debug("streamlink [%s]: %s", self._user, line)
        if notice := ad_notice(line):
            self._notices.info(self._user, notice)
        elif self._token and (match := _RE_UNAUTHORIZED.search(line)):
            self._notices.error(self._user, f"{TOKEN_REJECTED}: {match[0]}")

    def _redact(self, line: str) -> str:
        line = sanitize_log(line)
        return line.replace(self._token, "<redacted>") if self._token else line


@dataclass(frozen=True)
class PipeResult:
    ffmpeg_rc: int
    streamlink_rc: int
    streamlink_tail: str  # already redacted
    # streamlink was still running when FFmpeg exited, so we stopped it.
    streamlink_stopped: bool = False


async def run_pipe(
    streamlink_args: Sequence[str],
    ffmpeg_args: Sequence[str],
    writer: FfmpegLogWriter,
    streamlink_log: StreamlinkLog,
) -> PipeResult:
    """Run streamlink piped into FFmpeg until both have exited.

    The stream goes through an OS pipe, never through Python. Whichever exits
    first, the other follows: FFmpeg finishes the file when its input ends, and
    streamlink is stopped (SIGTERM, then SIGKILL after STREAMLINK_TERM_GRACE) once
    FFmpeg is gone.

    If the task is cancelled (shutdown) while FFmpeg is running, streamlink is
    stopped the same way, so FFmpeg sees the end of its input and finalises the
    MP4; we wait for FFmpeg, then re-raise. On any other error (a stderr reader
    failing included), or if that wait is cancelled again, both are killed.
    Neither process outlives this call. Raises OSError if either can't be started.
    """
    ffmpeg, streamlink = await _spawn(streamlink_args, ffmpeg_args)
    ff_drain = asyncio.ensure_future(_drain(ffmpeg, writer.write))
    sl_drain = asyncio.ensure_future(_drain(streamlink, streamlink_log.write))
    drains = (ff_drain, sl_drain)
    stopped = False
    try:
        try:
            done, _ = await asyncio.wait(drains, return_when=asyncio.FIRST_COMPLETED)
            _raise_first_error(done)
            if ff_drain.done():
                # If streamlink had already exited too, its exit code is its own.
                stopped = not sl_drain.done()
                await _terminate(streamlink, sl_drain)
            await _wait_all(drains)
        except asyncio.CancelledError:
            # Stopping streamlink gently only protects a file FFmpeg is still
            # writing; once FFmpeg has exited, _reap just kills streamlink.
            if not ff_drain.done():
                await _terminate(streamlink, sl_drain)
                await _wait_all(drains)
            raise
    finally:
        await _reap((("FFmpeg", ffmpeg), ("streamlink", streamlink)), drains)
        streamlink_log.close()
    return PipeResult(
        ff_drain.result(), sl_drain.result(), streamlink_log.tail(), stopped
    )


async def _spawn(
    streamlink_args: Sequence[str], ffmpeg_args: Sequence[str]
) -> tuple[asyncio.subprocess.Process, asyncio.subprocess.Process]:
    """Start FFmpeg reading a new pipe, then streamlink writing to it.

    FFmpeg starts first so streamlink always has a reader. Our copies of both
    pipe ends are closed once the children have theirs, so each child sees EOF or
    a broken pipe as soon as the other exits.
    """
    read_fd, write_fd = os.pipe()
    ffmpeg = None
    try:
        ffmpeg = await asyncio.create_subprocess_exec(
            *ffmpeg_args,
            stdin=read_fd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        streamlink = await asyncio.create_subprocess_exec(
            *streamlink_args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=write_fd,
            stderr=asyncio.subprocess.PIPE,
        )
    except BaseException:
        if ffmpeg is not None:
            await _reap((("FFmpeg", ffmpeg),), ())
        raise
    finally:
        os.close(read_fd)
        os.close(write_fd)
    return ffmpeg, streamlink


async def _drain(
    proc: asyncio.subprocess.Process, sink: Callable[[bytes], None]
) -> int:
    if proc.stderr is not None:
        while chunk := await proc.stderr.read(4096):
            sink(chunk)
    return await proc.wait()


async def _terminate(
    streamlink: asyncio.subprocess.Process, drain: asyncio.Future[int]
) -> None:
    """SIGTERM streamlink; SIGKILL it if it hasn't exited after the grace period."""
    if streamlink.returncode is None:
        log.debug("Stopping streamlink (pid %d)", streamlink.pid)
        with suppress(ProcessLookupError):
            streamlink.send_signal(signal.SIGTERM)
    _, pending = await asyncio.wait({drain}, timeout=STREAMLINK_TERM_GRACE)
    if pending:
        log.debug("Killing streamlink (pid %d)", streamlink.pid)
        with suppress(ProcessLookupError):
            streamlink.kill()


async def _wait_all(drains: Sequence[asyncio.Future[int]]) -> None:
    """Wait for every drain; raise the first error as soon as one fails."""
    done, _ = await asyncio.wait(drains, return_when=asyncio.FIRST_EXCEPTION)
    _raise_first_error(done)


def _raise_first_error(done: Iterable[asyncio.Future[int]]) -> None:
    """Raise the error of the first finished drain that failed, if any."""
    for task in done:
        if not task.cancelled() and (error := task.exception()) is not None:
            raise error


async def _reap(
    procs: Sequence[tuple[str, asyncio.subprocess.Process]],
    drains: Sequence[asyncio.Future[int]],
) -> None:
    """Kill whatever is still running and wait for it to exit.

    The kills are sent before the first await, so a further cancellation can't
    leave a process running.
    """
    for name, proc in procs:
        if proc.returncode is None:
            log.debug("Killing %s (pid %d)", name, proc.pid)
            with suppress(ProcessLookupError):
                proc.kill()
    await asyncio.shield(
        asyncio.gather(
            *(proc.wait() for _, proc in procs), *drains, return_exceptions=True
        )
    )
