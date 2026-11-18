"""Ad-free Twitch recording: streamlink reads the stream and pipes it into FFmpeg.

streamlink's Twitch plugin drops ad segments, so a recording skips ahead where an
ad ran instead of containing it. A Twitch login token (Turbo or a channel sub)
avoids the ads, and the gaps, altogether.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
from collections import deque
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import TYPE_CHECKING

from .ffmpeg import sanitize_log
from .resolver import HTTP_TIMEOUT, TOKEN_REJECTED

if TYPE_CHECKING:
    from .notices import NoticeBuffer

log = logging.getLogger(__name__)

TAIL_LINES = 50  # streamlink lines kept for failure logs
MAX_LINE_CHARS = 4096  # longer lines are cut, after redaction
_MAX_PARTIAL = 64 * 1024  # bytes kept of a line that hasn't ended yet
_RE_AD_BREAK = re.compile(
    r"detected advertisement break of (\d+) seconds?", re.IGNORECASE
)
_PRE_ROLL = "waiting for pre-roll ads"


def build_streamlink_args(
    user: str, quality: str, config_path: str | None, *, cmd: Sequence[str]
) -> list[str]:
    """streamlink argv that writes the channel's stream to stdout.

    The token never goes in argv, where the process list would show it; streamlink
    reads it from config_path. Without a token, --no-config keeps any streamlink
    config on the host out of the picture.
    """
    config = ["--config", config_path] if config_path else ["--no-config"]
    # Never tie streamlink's log level to LOG_LEVEL: at debug it prints the
    # --twitch-api-header value, token included, to stderr.
    # fmt: off
    return [
        *cmd,
        "--stdout",
        "--loglevel", "info",
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
            self._partial = self._partial[-_MAX_PARTIAL:]
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
        elif self._token and "unauthorized" in line.lower():
            self._notices.error(self._user, f"{TOKEN_REJECTED}: {line}")

    def _redact(self, line: str) -> str:
        line = sanitize_log(line)
        return line.replace(self._token, "<redacted>") if self._token else line
