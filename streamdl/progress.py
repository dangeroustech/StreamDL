"""Parse FFmpeg's status output and track progress for active downloads.

Durations are float seconds throughout.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import math
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from . import log_setup
from .settings import atoi

log = logging.getLogger(__name__)


class DownloadKind(StrEnum):
    LIVE = "live"
    VOD = "vod"


@dataclass
class ProgressSample:
    """One parsed progress update from FFmpeg output."""

    size_bytes: int = 0
    duration: float = 0.0
    speed: float = 0.0
    bitrate_kbps: float = 0.0
    valid: bool = False


@dataclass
class DownloadProgress:
    """Point-in-time snapshot of an active download."""

    key: str
    channel: str
    kind: DownloadKind
    vod_id: str = ""
    title: str = ""
    size_bytes: int = 0
    duration: float = 0.0
    total_duration: float = 0.0  # known for some VODs; 0 if unknown
    speed: float = 0.0  # realtime multiplier; 0 if unknown
    bitrate_kbps: float = 0.0
    percent: float | None = None
    eta: float | None = None
    started_at: float = 0.0
    updated_at: float = 0.0


def progress_key_live(channel: str) -> str:
    return f"live:{channel}"


def progress_key_vod(channel: str, vod_id: str) -> str:
    return f"vod:{channel}:{vod_id}"


class ProgressStore:
    """Registry of active downloads, keyed by progress_key_live/progress_key_vod.

    Not thread-safe: use it from the event loop only.
    """

    def __init__(self) -> None:
        self._items: dict[str, DownloadProgress] = {}

    def start(
        self,
        key: str,
        *,
        channel: str,
        kind: DownloadKind,
        vod_id: str = "",
        title: str = "",
        total_duration: float = 0.0,
    ) -> None:
        now = time.time()
        self._items[key] = DownloadProgress(
            key=key,
            channel=channel,
            kind=kind,
            vod_id=vod_id,
            title=title,
            total_duration=total_duration,
            started_at=now,
            updated_at=now,
        )

    def end(self, key: str) -> None:
        self._items.pop(key, None)

    def update(self, key: str, sample: ProgressSample) -> None:
        p = self._items.get(key)
        if p is None:
            return
        if sample.size_bytes > 0:
            p.size_bytes = sample.size_bytes
        if sample.duration > 0:
            p.duration = sample.duration
        if sample.speed > 0:
            p.speed = sample.speed
        if sample.bitrate_kbps > 0:
            p.bitrate_kbps = sample.bitrate_kbps
        p.updated_at = time.time()
        p.percent, p.eta = derive_percent_eta(p.duration, p.total_duration, p.speed)

    def get(self, key: str) -> DownloadProgress | None:
        p = self._items.get(key)
        return dataclasses.replace(p) if p else None

    def snapshot(self) -> list[DownloadProgress]:
        items = [dataclasses.replace(p) for p in self._items.values()]
        return sorted(items, key=lambda p: (p.channel, p.kind, p.vod_id))


def derive_percent_eta(
    elapsed: float, total: float, speed: float
) -> tuple[float | None, float | None]:
    if total <= 0 or elapsed <= 0:
        return None, None
    percent = min(max(elapsed / total * 100, 0.0), 100.0)
    eta = None
    if speed > 0 and elapsed < total:
        eta = _finite((total - elapsed) / speed)  # a tiny speed can overflow to inf
    return percent, eta


_RE_SIZE = re.compile(r"(?:^|\s)size=\s*([0-9.]+)\s*([KkMmGg]?i?[Bb])", re.ASCII)
_RE_TIME = re.compile(r"(?:^|\s)time=\s*(\d{1,2}):(\d{2}):(\d{2}(?:\.\d+)?)", re.ASCII)
_RE_SPEED = re.compile(r"(?:^|\s)speed=\s*([0-9.]+)x", re.ASCII)
_RE_BITRATE = re.compile(r"(?:^|\s)bitrate=\s*([0-9.]+)kbits/s", re.ASCII)
_RE_KV = re.compile(r"([a-zA-Z0-9_]+)=(.+)", re.ASCII)  # -progress key=value form
_SIZE_UNITS = {
    "b": 1,
    "kb": 1024,
    "kib": 1024,
    "mb": 1024**2,
    "mib": 1024**2,
    "gb": 1024**3,
    "gib": 1024**3,
}


def _to_int(value: str) -> int | None:
    return atoi(value.strip())


def _to_float(value: str) -> float | None:
    """Parse a finite float; None for junk, '_' separators, non-ASCII or inf/nan."""
    if not value.isascii() or "_" in value:
        return None
    try:
        f = float(value)
    except ValueError, OverflowError:
        return None
    return f if math.isfinite(f) else None


def _finite(value: float) -> float | None:
    return value if math.isfinite(value) else None


def parse_ffmpeg_clock(value: str) -> float | None:
    if not value or value.upper() == "N/A":
        return None
    parts = value.split(":")
    if len(parts) != 3:
        return None
    hours, minutes, secs = atoi(parts[0]), atoi(parts[1]), _to_float(parts[2])
    if hours is None or minutes is None or secs is None:
        return None
    try:
        return _finite(hours * 3600 + minutes * 60 + secs)
    except OverflowError:
        return None


def parse_ffmpeg_size(value: str, unit: str) -> int | None:
    n = _to_float(value)
    mult = _SIZE_UNITS.get(unit.lower())
    if n is None or mult is None:
        return None
    size = n * mult
    return int(size) if math.isfinite(size) else None


def parse_ffmpeg_progress_line(line: str) -> ProgressSample:
    """Parse a status line or -progress key=value line; valid=False if it isn't progress."""
    line = line.strip()
    if not line:
        return ProgressSample()

    kv = _RE_KV.fullmatch(line)
    if kv and " " not in line:
        key, value = kv.group(1), kv.group(2).strip()
        sample = ProgressSample()
        match key:
            case "total_size":
                n = _to_int(value)
                if n is not None and n > 0:
                    sample.size_bytes, sample.valid = n, True
            case "out_time_ms" | "out_time_us":
                # FFmpeg's out_time_ms is actually microseconds despite the name.
                n = _to_int(value)
                if n is not None and n > 0:
                    sample.duration, sample.valid = n / 1_000_000, True
            case "out_time":
                d = parse_ffmpeg_clock(value)
                if d is not None:
                    sample.duration, sample.valid = d, True
            case "speed":
                f = _to_float(value.removesuffix("x"))
                if f is not None and f > 0:
                    sample.speed, sample.valid = f, True
            case "bitrate":
                f = _to_float(value.removesuffix("kbits/s"))
                if f is not None and f > 0:
                    sample.bitrate_kbps, sample.valid = f, True
        return sample

    # Human status line: frame=... size=... time=... bitrate=... speed=...
    if "size=" not in line and "time=" not in line and "speed=" not in line:
        return ProgressSample()
    sample = ProgressSample()
    if m := _RE_SIZE.search(line):
        size = parse_ffmpeg_size(m[1], m[2])
        if size is not None:
            sample.size_bytes, sample.valid = size, True
    if m := _RE_TIME.search(line):
        sample.duration = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
        sample.valid = True
    if m := _RE_SPEED.search(line):
        f = _to_float(m[1])
        if f is not None:
            sample.speed, sample.valid = f, True
    if m := _RE_BITRATE.search(line):
        f = _to_float(m[1])
        if f is not None:
            sample.bitrate_kbps, sample.valid = f, True
    return sample


class FfmpegLogWriter:
    """Keeps the last 64 KiB of FFmpeg's stderr and feeds each line to the progress store."""

    MAX_BYTES = 64 * 1024

    def __init__(
        self,
        key: str,
        store: ProgressStore,
        *,
        debug_interval: float = 10.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._key = key
        self._store = store
        self._buf = bytearray()
        self._partial = b""
        self._debug_interval = debug_interval
        self._clock = clock
        self._last_debug: float | None = None

    def write(self, data: bytes) -> None:
        self._buf += data
        if len(self._buf) > self.MAX_BYTES:
            del self._buf[: len(self._buf) - self.MAX_BYTES]
        *lines, self._partial = re.split(rb"[\r\n]", self._partial + data)
        if len(self._partial) > self.MAX_BYTES:  # output with no CR/LF at all
            self._partial = self._partial[-self.MAX_BYTES :]
        for raw in lines:
            if raw:
                self._handle_line(raw.decode("utf-8", "replace"))

    def text(self) -> str:
        return self._buf.decode("utf-8", "replace")

    def _handle_line(self, line: str) -> None:
        sample = parse_ffmpeg_progress_line(line)
        if not sample.valid:
            return
        self._store.update(self._key, sample)
        if not log.isEnabledFor(logging.DEBUG):
            return
        now = self._clock()
        if (
            self._last_debug is not None
            and now - self._last_debug < self._debug_interval
        ):
            return
        self._last_debug = now
        if p := self._store.get(self._key):
            log.debug("download progress %s", format_download_progress(p))


def format_bytes(n: int) -> str:
    kib, mib, gib = 1024, 1024**2, 1024**3
    if n >= gib:
        return f"{n / gib:.2f}GiB"
    if n >= mib:
        return f"{n / mib:.1f}MiB"
    if n >= kib:
        return f"{n / kib:.1f}KiB"
    return f"{n}B"


def format_duration_short(seconds: float) -> str:
    if not math.isfinite(seconds):
        seconds = 0.0
    total = int(max(seconds, 0.0) + 0.5)  # round half up, like Go's Duration.Round
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def format_download_progress(p: DownloadProgress) -> str:
    parts = [f"[{p.channel}] {p.kind}"]
    if p.kind == DownloadKind.VOD and (label := p.title or p.vod_id):
        parts.append(json.dumps(label, ensure_ascii=False))
    if p.percent is not None:
        parts.append(f"{p.percent:.1f}%")
    if p.size_bytes > 0:
        parts.append(f"size={format_bytes(p.size_bytes)}")
    if p.duration > 0:
        parts.append(f"time={format_duration_short(p.duration)}")
    if p.speed > 0:
        parts.append(f"speed={p.speed:.2f}x")
    if p.eta is not None:
        parts.append(f"eta={format_duration_short(p.eta)}")
    return " ".join(parts)


def log_active_download_summary(store: ProgressStore) -> None:
    """Log in-flight downloads, and mirror them to stdout when logs go only to a file."""
    snap = store.snapshot()
    if not snap:
        log.debug("Active Downloads: (none)")
    else:
        log.info("Active Downloads:")
        for p in snap:
            log.info("  %s", format_download_progress(p))
    lines = [f"  {format_download_progress(p)}" for p in snap] or ["  (none)"]
    log_setup.write_console("Active Downloads:\n" + "\n".join(lines) + "\n")
