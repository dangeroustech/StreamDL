"""User-facing notices, collected during a round and logged after the wait line."""

from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Notice:
    level: int
    channel: str
    message: str


def _key(channel: str, message: str) -> str:
    return f"{channel}|{message}"


class NoticeBuffer:
    """Collects notices per round.

    A notice is shown once, then suppressed until clear_channel() is called for its
    channel (when a live recording ends).

    Not thread-safe; call from the event loop only.
    """

    def __init__(self) -> None:
        self._pending: list[Notice] = []
        self._surfaced: set[str] = set()

    def warn(self, channel: str, message: str) -> None:
        self._add(logging.WARNING, channel, message)

    def error(self, channel: str, message: str) -> None:
        self._add(logging.ERROR, channel, message)

    def pending(self) -> list[Notice]:
        return list(self._pending)

    def clear_channel(self, channel: str) -> None:
        prefix = f"{channel}|"
        self._surfaced = {k for k in self._surfaced if not k.startswith(prefix)}

    def flush(self, wait_seconds: int) -> None:
        """Log the wait line, then any buffered notices, and mark them as shown."""
        pending, self._pending = self._pending, []
        log.info("Waiting %ds until next check...", wait_seconds)
        if not pending:
            return
        log.info("--- notices ---")
        for notice in pending:
            level = logging.ERROR if notice.level >= logging.ERROR else logging.WARNING
            log.log(level, "[%s] %s", notice.channel, notice.message)
            self._surfaced.add(_key(notice.channel, notice.message))

    def _add(self, level: int, channel: str, message: str) -> None:
        channel, message = channel.strip(), message.strip()
        if not channel or not message:
            return
        key = _key(channel, message)
        if key in self._surfaced:
            return
        if any(_key(n.channel, n.message) == key for n in self._pending):
            return
        self._pending.append(Notice(level, channel, message))
