"""Joins with the real FFmpeg and ffprobe from the dev container; skipped without them."""

import json
import shutil
import subprocess  # nosec B404 - test helper running FFmpeg

import pytest

from streamdl.join import join_parts, probe
from streamdl.progress import FfmpegLogWriter, ProgressStore

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
pytestmark = pytest.mark.skipif(
    not (FFMPEG and FFPROBE), reason="needs real ffmpeg and ffprobe on PATH"
)


def make_clip(path, size="320x240", seconds=2):
    source = f"testsrc=size={size}:rate=25:duration={seconds}"
    tone = f"sine=frequency=440:duration={seconds}"
    subprocess.run(  # nosec B603 - fixed argv, no shell
        [FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", source]
        + ["-f", "lavfi", "-i", tone, "-c:v", "mpeg4", "-c:a", "aac"]
        + ["-shortest", "-f", "mp4", str(path)],
        check=True,
    )
    return str(path)


def duration(path):
    out = subprocess.run(  # nosec B603 - fixed argv, no shell
        [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "json"]
        + [path],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return float(json.loads(out)["format"]["duration"])


async def join(parts, out):
    writer = FfmpegLogWriter("join", ProgressStore())
    return await join_parts(parts, out, writer, ffmpeg=FFMPEG, ffprobe=FFPROBE)


async def test_matching_parts_join_into_one_file(tmp_path):
    parts = [make_clip(tmp_path / f"p{n}.mp4") for n in (1, 2, 3)]
    out = str(tmp_path / "joined.mp4")
    result = await join(parts, out)
    assert result.ok, result
    assert duration(out) == pytest.approx(6.0, abs=0.3)
    assert len(await probe(out, ffprobe=FFPROBE)) == 2


async def test_a_resolution_change_keeps_the_parts(tmp_path):
    parts = [make_clip(tmp_path / "a.mp4"), make_clip(tmp_path / "b.mp4", "160x120")]
    result = await join(parts, str(tmp_path / "j.mp4"))
    assert not result.ok
    assert result.reason == "stream 0 width is 160 in part 2, 320 in part 1"


async def test_an_unreadable_part_keeps_the_parts(tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not a video")
    result = await join(
        [make_clip(tmp_path / "a.mp4"), str(bad)], str(tmp_path / "j.mp4")
    )
    assert not result.ok
    assert result.reason.startswith("part 2 can't be read (")


async def test_quotes_and_spaces_in_paths(tmp_path):
    folder = tmp_path / "it's a dir"
    folder.mkdir()
    parts = [
        make_clip(folder / "it's part 1.mp4"),
        make_clip(folder / "it's part 2.mp4"),
    ]
    out = str(folder / "joined.mp4")
    result = await join(parts, out)
    assert result.ok, result
    assert duration(out) == pytest.approx(4.0, abs=0.3)
