import asyncio
import tempfile

import pytest
from helpers import FAKE_FFMPEG, FAKE_FFPROBE, ffmpeg_runs, wait_for_glob

from streamdl.join import (
    JoinResult,
    ProbeError,
    StreamInfo,
    build_concat_args,
    join_parts,
    parts_match,
    probe,
    probe_parts,
    write_concat_list,
)
from streamdl.progress import FfmpegLogWriter, ProgressStore

VIDEO = StreamInfo("video", "h264", 1920, 1080, "yuv420p", None, None, "High")
AUDIO = StreamInfo("audio", "aac", None, None, None, "48000", 2, "LC")


def writer():
    return FfmpegLogWriter("join", ProgressStore())


def make_parts(tmp_path, n):
    paths = []
    for i in range(1, n + 1):
        path = tmp_path / f"p{i}.mp4"
        path.write_bytes(f"part{i}".encode())
        paths.append(str(path))
    return paths


def streams(parts):
    """parts mapped to matching streams, as probe_parts reports them."""
    return {part: [VIDEO, AUDIO] for part in parts}


def test_parts_match():
    assert parts_match([[VIDEO, AUDIO], [VIDEO, AUDIO], [VIDEO, AUDIO]]) is None


def test_parts_with_a_different_stream_count():
    assert (
        parts_match([[VIDEO, AUDIO], [VIDEO]]) == "part 2 has 1 streams, part 1 has 2"
    )


def test_parts_with_a_different_property():
    smaller = StreamInfo("video", "h264", 1280, 720, "yuv420p", None, None, "High")
    assert (
        parts_match([[VIDEO, AUDIO], [VIDEO, AUDIO], [smaller, AUDIO]])
        == "stream 0 width is 1280 in part 3, 1920 in part 1"
    )


def test_parts_with_a_different_profile():
    main = StreamInfo("video", "h264", 1920, 1080, "yuv420p", None, None, "Main")
    assert (
        parts_match([[VIDEO, AUDIO], [main, AUDIO]])
        == "stream 0 profile is Main in part 2, High in part 1"
    )


def test_concat_list_quotes_paths(tmp_path):
    listing = write_concat_list(["/rec/it's a.mp4", "/rec/b.mp4"], str(tmp_path))
    with open(listing, encoding="utf-8") as f:
        assert f.read() == "file '/rec/it'\\''s a.mp4'\nfile '/rec/b.mp4'\n"


def test_concat_args():
    assert build_concat_args("/t/parts.txt", "/dl/x.joining.mp4", ffmpeg="ff") == [
        "ff",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        "/t/parts.txt",
        "-map",
        "0",
        "-c",
        "copy",
        "-f",
        "mp4",
        "/dl/x.joining.mp4",
    ]


async def test_probe_reads_the_streams(tmp_path):
    [part] = make_parts(tmp_path, 1)
    assert await probe(part, ffprobe=FAKE_FFPROBE) == [VIDEO, AUDIO]


async def test_probe_failure_raises(tmp_path):
    with pytest.raises(ProbeError, match="Invalid data found"):
        await probe(str(tmp_path / "missing.mp4"), ffprobe=FAKE_FFPROBE)


async def test_probe_without_ffprobe_raises(tmp_path):
    [part] = make_parts(tmp_path, 1)
    with pytest.raises(ProbeError, match="can't run ffprobe"):
        await probe(part, ffprobe=str(tmp_path / "no-ffprobe"))


async def test_join_concatenates_matching_parts(tmp_path, ffmpeg_log, monkeypatch):
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp))
    parts = make_parts(tmp_path, 3)
    out = tmp_path / "joined.mp4"

    result = await join_parts(streams(parts), str(out), writer(), ffmpeg=FAKE_FFMPEG)

    assert result == JoinResult(ok=True)
    assert out.read_bytes() == b"part1part2part3"
    [run] = ffmpeg_runs(ffmpeg_log)
    assert "concat" in run
    assert list(tmp.iterdir()) == []  # the list's temp directory is removed


async def test_join_keeps_mismatched_parts(tmp_path, ffmpeg_log):
    parts = make_parts(tmp_path, 2)
    smaller = StreamInfo("video", "h264", 1280, 720, "yuv420p", None, None, "High")

    result = await join_parts(
        {parts[0]: [VIDEO, AUDIO], parts[1]: [smaller, AUDIO]},
        str(tmp_path / "j.mp4"),
        writer(),
        ffmpeg=FAKE_FFMPEG,
    )

    assert result == JoinResult(
        ok=False, reason="stream 0 width is 1280 in part 2, 1920 in part 1"
    )
    assert ffmpeg_runs(ffmpeg_log) == []


async def test_probe_parts_reports_unreadable_parts_separately(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_FFPROBE_FAIL", "p2")
    parts = make_parts(tmp_path, 3)

    readable, unreadable = await probe_parts(parts, ffprobe=FAKE_FFPROBE)

    assert readable == {parts[0]: [VIDEO, AUDIO], parts[2]: [VIDEO, AUDIO]}
    assert unreadable == {
        parts[1]: f"{parts[1]}: Invalid data found when processing input"
    }


async def test_failed_join_reports_ffmpeg_tail(tmp_path, ffmpeg_log, monkeypatch):
    monkeypatch.setenv("FAKE_FFMPEG_CONCAT_EXIT", "1")
    parts = make_parts(tmp_path, 2)

    result = await join_parts(
        streams(parts),
        str(tmp_path / "j.mp4"),
        writer(),
        ffmpeg=FAKE_FFMPEG,
    )

    assert not result.ok
    assert result.reason == "the join failed (exit status 1)"
    assert "concat finished" in result.log_tail


async def test_join_with_missing_ffmpeg(tmp_path):
    parts = make_parts(tmp_path, 2)
    result = await join_parts(
        streams(parts),
        str(tmp_path / "j.mp4"),
        writer(),
        ffmpeg=str(tmp_path / "no-ffmpeg"),
    )
    assert not result.ok
    assert result.reason.startswith("FFmpeg couldn't start: ")


async def test_join_with_an_unwritable_temp_dir(tmp_path, ffmpeg_log, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "missing"))
    parts = make_parts(tmp_path, 2)

    result = await join_parts(
        streams(parts),
        str(tmp_path / "j.mp4"),
        writer(),
        ffmpeg=FAKE_FFMPEG,
    )

    assert not result.ok
    assert result.reason.startswith(
        "the join list couldn't be written: [Errno 2] No such file or directory"
    )
    assert ffmpeg_runs(ffmpeg_log) == []


async def test_cancelling_a_join_kills_ffmpeg(tmp_path, ffmpeg_log, monkeypatch):
    monkeypatch.setenv("FAKE_FFMPEG_CONCAT_BLOCK", "1")
    procs = []
    spawn = asyncio.create_subprocess_exec

    async def recording_spawn(*args, **kwargs):
        proc = await spawn(*args, **kwargs)
        procs.append(proc)
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", recording_spawn)
    parts = make_parts(tmp_path, 2)
    task = asyncio.create_task(
        join_parts(
            streams(parts),
            str(tmp_path / "j.mp4"),
            writer(),
            ffmpeg=FAKE_FFMPEG,
        )
    )
    await wait_for_glob(tmp_path, "j.mp4.ready")

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert procs[-1].returncode is not None  # the join FFmpeg was reaped


def test_a_mismatch_names_the_parts_own_numbers():
    smaller = StreamInfo("video", "h264", 1280, 720, "yuv420p", None, None, "High")
    assert (
        parts_match([[VIDEO, AUDIO], [smaller, AUDIO]], [1, 3])
        == "stream 0 width is 1280 in part 3, 1920 in part 1"
    )
    assert parts_match([[VIDEO, AUDIO], [VIDEO]], [2, 4]) == (
        "part 4 has 1 streams, part 2 has 2"
    )
