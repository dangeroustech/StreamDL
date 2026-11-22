"""Runtime settings from command-line flags and environment variables."""

from __future__ import annotations

import argparse
import logging
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

_RE_ATOI = re.compile(r"[+-]?[0-9]+")
_INT64_MIN, _INT64_MAX = -(2**63), 2**63 - 1


def atoi(value: str) -> int | None:
    """Parse a base-10 int64 like Go's strconv.Atoi; None if it isn't one.

    Unlike int(), this rejects surrounding whitespace, '_' separators and
    non-ASCII digits.
    """
    if not _RE_ATOI.fullmatch(value):
        return None
    try:
        n = int(value)
    except ValueError:  # more digits than int() will parse
        return None
    return n if _INT64_MIN <= n <= _INT64_MAX else None


def env_int(env: Mapping[str, str], name: str, default: int) -> int:
    """Read an integer env var; blank means default, invalid warns and means default."""
    value = env.get(name, "").strip()
    if not value:
        return default
    n = atoi(value)
    if n is None:
        log.warning("Invalid %s value %r, using default %d", name, value, default)
        return default
    return n


def split_args(s: str) -> list[str]:
    """Split a flag string on spaces, keeping quoted segments (same rules as v3)."""
    out: list[str] = []
    cur: list[str] = []
    in_quote = ""
    for ch in s:
        if ch in "\"'":
            if not in_quote:
                in_quote = ch
            elif in_quote == ch:
                in_quote = ""
            else:
                cur.append(ch)
        elif ch == " ":
            if in_quote:
                cur.append(ch)
            elif cur:
                out.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        out.append("".join(cur))
    return out


@dataclass(frozen=True)
class FfmpegOptions:
    """FFMPEG_* environment settings."""

    rw_timeout_us: str = "15000000"
    protocol_whitelist: str = ""
    user_agent: str = ""
    reconnect: bool = True
    reconnect_delay_max: str = "15"
    stream_copy: bool = False
    extra_input: tuple[str, ...] = ()
    extra_output: tuple[str, ...] = ()
    max_retries: int = 3
    retry_base_delay: float = 2.0

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> FfmpegOptions:
        return cls(
            rw_timeout_us=env.get("FFMPEG_RW_TIMEOUT_US") or "15000000",
            protocol_whitelist=env.get("FFMPEG_PROTOCOL_WHITELIST", "").strip(),
            user_agent=env.get("FFMPEG_USER_AGENT", ""),
            reconnect=env.get("FFMPEG_RECONNECT", "").lower() not in ("0", "false"),
            reconnect_delay_max=env.get("FFMPEG_RECONNECT_DELAY_MAX") or "15",
            stream_copy=env.get("FFMPEG_STREAM_COPY", "").strip().lower()
            in ("1", "true"),
            extra_input=tuple(
                split_args(env.get("FFMPEG_EXTRA_INPUT_OPTS", "").strip())
            ),
            extra_output=tuple(
                split_args(env.get("FFMPEG_EXTRA_OUTPUT_OPTS", "").strip())
            ),
            max_retries=env_int(env, "FFMPEG_MAX_RETRIES", 3),
            retry_base_delay=float(env_int(env, "FFMPEG_RETRY_BASE_DELAY_SECONDS", 2)),
        )


@dataclass(frozen=True)
class TwitchOptions:
    """TWITCH_* environment settings."""

    adfree: bool = True
    oauth_token: str = field(default="", repr=False)

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> TwitchOptions:
        token = env.get("TWITCH_OAUTH_TOKEN", "").strip()
        # Compose's list form (- TWITCH_OAUTH_TOKEN="abc") keeps the quotes.
        if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
            token = token[1:-1]
        if token[:6].lower() == "oauth ":
            token = token[6:].lstrip()
        if not (
            token.isascii()
            and token.isprintable()
            and not any(ch.isspace() for ch in token)
        ):
            # It goes into a streamlink config file, where a line break would
            # start a new option, and into an HTTP header, which http.client
            # encodes as latin-1.
            log.warning(
                "Ignoring TWITCH_OAUTH_TOKEN: it contains spaces, control or"
                " non-ASCII characters"
            )
            token = ""  # nosec B105 - clearing a rejected token
        return cls(
            adfree=env.get("TWITCH_ADFREE", "").strip().lower() not in ("0", "false"),
            oauth_token=token,
        )


@dataclass(frozen=True)
class ReconnectOptions:
    """RECONNECT_* environment settings: how long to wait for a dropped stream."""

    window: int = 30
    interval: int = 5

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> ReconnectOptions:
        return cls(
            window=max(0, env_int(env, "RECONNECT_WINDOW", 30)),
            interval=max(1, env_int(env, "RECONNECT_INTERVAL", 5)),
        )


@dataclass(frozen=True)
class Settings:
    config_path: Path = Path("config.yml")
    out_dir: str = ""
    move_dir: str = ""
    vod_out_dir: str = ""
    vod_move_dir: str = ""
    data_dir: str = "/app/data"
    tick_seconds: int = 60
    batch_seconds: int = 5
    subfolder: bool = False
    post_script_timeout: float = 1800
    ffmpeg: FfmpegOptions = field(default_factory=FfmpegOptions)
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    twitch: TwitchOptions = field(default_factory=TwitchOptions)
    reconnect: ReconnectOptions = field(default_factory=ReconnectOptions)
    # How to run streamlink; the default is the copy installed alongside StreamDL.
    streamlink_cmd: tuple[str, ...] = (sys.executable, "-m", "streamlink")

    @classmethod
    def from_args(cls, args: argparse.Namespace, env: Mapping[str, str]) -> Settings:
        return cls(
            config_path=Path(args.config),
            out_dir=args.out,
            move_dir=args.move,
            vod_out_dir=args.vod_out or args.out,
            vod_move_dir=args.vod_move or args.move,
            data_dir=args.data,
            tick_seconds=args.time,
            batch_seconds=args.batch,
            subfolder=args.subfolder,
            post_script_timeout=env_int(env, "STREAMDL_POST_SCRIPT_TIMEOUT", 1800),
            ffmpeg=FfmpegOptions.from_env(env),
            twitch=TwitchOptions.from_env(env),
            reconnect=ReconnectOptions.from_env(env),
        )
