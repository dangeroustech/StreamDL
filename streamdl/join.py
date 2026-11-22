"""Join a live recording's parts into one file with FFmpeg's concat demuxer."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, fields

from .ffmpeg import tail_lines
from .process import describe_exit
from .progress import FfmpegLogWriter

log = logging.getLogger(__name__)

JOIN_TAIL_LINES = 20


class ProbeError(Exception):
    """ffprobe couldn't read a part."""


@dataclass(frozen=True)
class StreamInfo:
    """The stream properties that must match for a stream-copy join to play cleanly."""

    codec_type: str | None = None
    codec_name: str | None = None
    width: int | None = None
    height: int | None = None
    pix_fmt: str | None = None
    sample_rate: str | None = None
    channels: int | None = None
    profile: str | None = None


_FIELDS = tuple(f.name for f in fields(StreamInfo))


@dataclass(frozen=True)
class JoinResult:
    ok: bool
    reason: str = ""  # why the parts were kept, when not ok
    log_tail: str = ""  # FFmpeg's last lines, when the join itself failed


async def probe(path: str, *, ffprobe: str) -> list[StreamInfo]:
    """The streams in path, as ffprobe reports them. Raises ProbeError if it can't."""
    args = [ffprobe, "-v", "error", "-show_entries", "stream=" + ",".join(_FIELDS)]
    args += ["-of", "json", path]
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as e:
        raise ProbeError(f"can't run ffprobe: {e}") from e
    try:
        out, err = await proc.communicate()
    except BaseException:
        await _stop(proc)
        raise
    if proc.returncode != 0:
        lines = err.decode("utf-8", "replace").strip().splitlines()
        raise ProbeError(lines[-1] if lines else describe_exit(proc.returncode))
    try:
        streams = json.loads(out)["streams"]
        infos = [StreamInfo(**{k: s.get(k) for k in _FIELDS}) for s in streams]
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        raise ProbeError("ffprobe's output couldn't be read") from e
    if not infos:
        raise ProbeError("it has no audio or video")
    return infos


def parts_match(infos: Sequence[Sequence[StreamInfo]]) -> str | None:
    """None if every part has the same streams as part 1, else the first difference."""
    first = infos[0]
    for n, streams in enumerate(infos[1:], start=2):
        if len(streams) != len(first):
            return f"part {n} has {len(streams)} streams, part 1 has {len(first)}"
        for i, (a, b) in enumerate(zip(first, streams)):
            for name in _FIELDS:
                if getattr(a, name) != getattr(b, name):
                    return (
                        f"stream {i} {name} is {getattr(b, name)} in part {n},"
                        f" {getattr(a, name)} in part 1"
                    )
    return None


def write_concat_list(paths: Sequence[str], directory: str) -> str:
    """Write the concat demuxer's list of paths into directory; return its path.

    Each path is single-quoted, with ' written as '\\'' (the demuxer's escaping).
    """
    list_path = os.path.join(directory, "parts.txt")
    with open(list_path, "w", encoding="utf-8") as f:
        for path in paths:
            quoted = os.path.abspath(path).replace("'", "'\\''")
            f.write(f"file '{quoted}'\n")
    return list_path


def build_concat_args(list_path: str, out_path: str, *, ffmpeg: str) -> list[str]:
    """FFmpeg argv joining the listed parts by stream copy (no re-encoding)."""
    return [
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        list_path,
        "-map",
        "0",
        "-c",
        "copy",
        "-f",
        "mp4",
        out_path,
    ]


async def join_parts(
    parts: Sequence[str],
    out_path: str,
    writer: FfmpegLogWriter,
    *,
    ffmpeg: str,
    ffprobe: str,
) -> JoinResult:
    """Join parts (at least two) into out_path if they match; otherwise say why not.

    Failures come back as a JoinResult; nothing but cancellation is raised. The
    caller deletes out_path when the result isn't ok. If this is cancelled, the
    join FFmpeg is killed and out_path may be left half written.
    """
    infos = []
    for n, part in enumerate(parts, start=1):
        try:
            infos.append(await probe(part, ffprobe=ffprobe))
        except ProbeError as e:
            return JoinResult(ok=False, reason=f"part {n} can't be read ({e})")
    if reason := parts_match(infos):
        return JoinResult(ok=False, reason=reason)
    try:
        with tempfile.TemporaryDirectory(
            prefix="streamdl-join-", ignore_cleanup_errors=True
        ) as tmp:
            list_path = write_concat_list(parts, tmp)
            args = build_concat_args(list_path, out_path, ffmpeg=ffmpeg)
            log.debug("FFmpeg join args: %s", args)
            try:
                returncode = await _run(args, writer)
            except (OSError, ValueError) as e:
                return JoinResult(ok=False, reason=f"FFmpeg couldn't start: {e}")
    except (OSError, ValueError) as e:
        return JoinResult(ok=False, reason=f"the join list couldn't be written: {e}")
    if returncode != 0:
        return JoinResult(
            ok=False,
            reason=f"the join failed ({describe_exit(returncode)})",
            log_tail=tail_lines(writer.text(), JOIN_TAIL_LINES),
        )
    return JoinResult(ok=True)


async def _run(args: list[str], writer: FfmpegLogWriter) -> int:
    """Run FFmpeg, feeding its stderr to writer. Unlike a recording, a join that
    is cancelled is killed, not finalised: the parts are still there."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        if proc.stderr is not None:
            while chunk := await proc.stderr.read(4096):
                writer.write(chunk)
        return await proc.wait()
    except BaseException:
        await _stop(proc)
        raise


async def _stop(proc: asyncio.subprocess.Process) -> None:
    """SIGKILL proc if it is still running and reap it, even if cancelled again."""
    if proc.returncode is None:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
    await asyncio.shield(proc.wait())
