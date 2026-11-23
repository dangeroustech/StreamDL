"""Joins with the real FFmpeg and ffprobe from the dev container; skipped without them."""

import json
import shutil
import subprocess  # nosec B404 - test helper running FFmpeg

import pytest

from streamdl.join import join_parts, probe, probe_parts
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
    readable, unreadable = await probe_parts(parts, ffprobe=FFPROBE)
    assert unreadable == {}
    writer = FfmpegLogWriter("join", ProgressStore())
    return await join_parts(readable, out, writer, ffmpeg=FFMPEG)


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


async def test_a_part_cut_off_before_its_index_is_left_out(tmp_path):
    parts = [make_clip(tmp_path / f"p{n}.mp4") for n in (1, 2, 3)]
    with open(parts[1], "r+b") as f:
        f.truncate(4096)  # like FFmpeg killed before it wrote the moov atom
    readable, unreadable = await probe_parts(parts, ffprobe=FFPROBE)
    assert list(readable) == [parts[0], parts[2]]
    assert unreadable[parts[1]].endswith("Invalid data found when processing input")

    out = str(tmp_path / "joined.mp4")
    writer = FfmpegLogWriter("join", ProgressStore())
    result = await join_parts(readable, out, writer, ffmpeg=FFMPEG)
    assert result.ok, result
    assert duration(out) == pytest.approx(4.0, abs=0.3)


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
