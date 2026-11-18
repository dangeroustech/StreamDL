"""Build FFmpeg command lines and redact secrets from what gets logged."""

from __future__ import annotations

import re
from collections.abc import Sequence

from .settings import FfmpegOptions

COPY_ARGS = ["-c:v", "copy", "-c:a", "copy", "-movflags", "+faststart"]
_RE_SECRET = re.compile(r"((?:token|sig|signature|lsig)=)[^&\s'\"]*", re.IGNORECASE)


def network_args(opts: FfmpegOptions) -> list[str]:
    """Input options that are safe for every stream type."""
    args = ["-rw_timeout", opts.rw_timeout_us]
    if opts.protocol_whitelist:
        args += ["-protocol_whitelist", opts.protocol_whitelist]
    if opts.user_agent:
        args += ["-user_agent", opts.user_agent]
    return args


def reconnect_args(opts: FfmpegOptions) -> list[str]:
    if not opts.reconnect:
        return []
    # fmt: off
    return [
        "-reconnect", "1",
        "-reconnect_at_eof", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", opts.reconnect_delay_max,
    ]
    # fmt: on


def _insert_before(args: list[str], target: str, items: Sequence[str]) -> None:
    index = args.index(target)
    args[index:index] = items


def build_live_args(
    video_url: str,
    audio_url: str,
    out_path: str,
    opts: FfmpegOptions,
    *,
    ffmpeg: str = "ffmpeg",
) -> list[str]:
    """Full FFmpeg argv for a live recording.

    The order matches the v3 Go client exactly; tests/fixtures/ffmpeg_args.json pins it.
    """
    args = [ffmpeg, "-i", video_url, "-f", "mp4", out_path]
    # Reconnect flags are skipped for split A/V inputs: reconnect_streamed and
    # reconnect_at_eof cause 403 loops when HLS segment tokens expire between attempts.
    _insert_before(
        args, "-i", network_args(opts) + ([] if audio_url else reconnect_args(opts))
    )
    if audio_url:
        at = args.index("-i") + 2  # after "-i <video>"
        args[at:at] = [
            *network_args(opts),
            "-i",
            audio_url,
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-c",
            "copy",
        ]
    if opts.stream_copy:
        _insert_before(args, out_path, COPY_ARGS)
    if opts.extra_input:
        _insert_before(args, "-i", opts.extra_input)
    if opts.extra_output:
        _insert_before(args, out_path, opts.extra_output)
    if "-y" not in args:
        args.insert(1, "-y")
    return args


def build_pipe_args(
    out_path: str, opts: FfmpegOptions, *, ffmpeg: str = "ffmpeg"
) -> list[str]:
    """FFmpeg argv for a live recording read from stdin (streamlink's output).

    Same layout as build_live_args, minus the input options that only make sense
    for a network input (timeouts, reconnects, user agent, protocol whitelist).
    FFMPEG_EXTRA_INPUT_OPTS is left out too: it is meant for network inputs, and
    options such as -reconnect make FFmpeg reject pipe:0.
    """
    args = [
        ffmpeg,
        "-i",
        "pipe:0",
        "-f",
        "mp4",
        *(COPY_ARGS if opts.stream_copy else []),
        *opts.extra_output,
        out_path,
    ]
    if "-y" not in args:
        args.insert(1, "-y")
    return args


def build_vod_args(url: str, out_path: str, *, ffmpeg: str = "ffmpeg") -> list[str]:
    """Full FFmpeg argv for a VOD download (always stream copy; no FFMPEG_* options)."""
    return [ffmpeg, "-y", "-i", url, "-f", "mp4", *COPY_ARGS, out_path]


def sanitize_args(args: Sequence[str]) -> str:
    """Join args for logging with input URLs and the user agent redacted."""
    out = list(args)
    for i in range(len(out) - 1):
        if out[i] in ("-i", "-user_agent"):
            out[i + 1] = "<redacted>"
    return " ".join(out)


def tail_lines(s: str, n: int) -> str:
    if n <= 0 or not s:
        return ""
    lines = s.split("\n")
    return s if len(lines) <= n else "\n".join(lines[-n:])


def sanitize_log(s: str) -> str:
    """Redact every token=, sig=, signature= and lsig= value in an FFmpeg log tail.

    A value ends at "&", whitespace or a quote, so redaction never crosses lines.
    """
    return _RE_SECRET.sub(r"\1<redacted>", s)
