import asyncio
import re
import signal

import pytest
from helpers import FAKE_FFMPEG, BlockingMove, ffmpeg_runs, wait_for_glob

from streamdl import recorder
from streamdl.ffmpeg import build_live_args
from streamdl.recorder import record_live, run_ffmpeg
from streamdl.resolver import Offline, RateLimited, StreamURLs
from streamdl.settings import FfmpegOptions

URLS = StreamURLs("https://video.example/live.m3u8")
FRESH = StreamURLs("https://video.example/fresh.m3u8")


def files(directory):
    return (
        sorted(p for p in directory.rglob("*") if p.is_file())
        if directory.exists()
        else []
    )


async def test_records_moves_and_runs_the_post_script(
    make_runtime, ffmpeg_log, tmp_path
):
    rt = make_runtime()
    marker = tmp_path / "hook.txt"
    hook = tmp_path / "hook.sh"
    hook.write_text(f'#!/bin/sh\necho "$STREAMDL_TYPE|$STREAMDL_USER|$1" > {marker}\n')
    hook.chmod(0o755)
    rt.active.add("alice")

    await record_live(rt, "alice", "twitch.tv", "best", URLS, str(hook))
    await rt.wait_for_post_scripts()

    [moved] = files(tmp_path / "out")
    assert re.fullmatch(r"alice_\d{4}-\d\d-\d\d_\d\d-\d\d-\d\d\.mp4", moved.name)
    assert moved.read_bytes() == b"fake mp4"
    assert files(tmp_path / "dl") == []
    assert marker.read_text() == f"live|alice|{moved}\n"
    assert "alice" not in rt.active
    assert rt.progress.snapshot() == []
    [run] = ffmpeg_runs(ffmpeg_log)
    assert URLS.video in run


async def test_subfolder(make_runtime, tmp_path):
    rt = make_runtime(subfolder=True)
    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")
    assert [p.parent.name for p in files(tmp_path / "out")] == ["alice"]


async def test_retries_with_fresh_urls_and_backoff(
    make_runtime, ffmpeg_log, monkeypatch, tmp_path
):
    monkeypatch.setenv("FAKE_FFMPEG_EXITS", "1,1,0")
    rt = make_runtime()
    rt.resolver.streams = [FRESH]

    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")

    runs = ffmpeg_runs(ffmpeg_log)
    assert len(runs) == 3
    assert URLS.video in runs[0]
    assert FRESH.video in runs[1] and FRESH.video in runs[2]
    assert rt.sleep.calls == [2.0, 4.0]
    assert rt.resolver.stream_calls == [("twitch.tv", "alice", "best")] * 2
    assert rt.notices.pending() == []
    assert len(files(tmp_path / "out")) == 1


async def test_gives_up_after_max_retries(
    make_runtime, ffmpeg_log, monkeypatch, tmp_path
):
    monkeypatch.setenv("FAKE_FFMPEG_EXITS", "1")
    rt = make_runtime(ffmpeg=FfmpegOptions(max_retries=2))
    rt.resolver.streams = [URLS]
    rt.active.add("alice")

    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")

    assert len(ffmpeg_runs(ffmpeg_log)) == 3
    assert [n.message for n in rt.notices.pending()] == [
        "Recording failed after 2 attempts: exit status 1"
    ]
    assert files(tmp_path / "out") == []
    assert "alice" not in rt.active


async def test_retry_rate_limited_three_times(make_runtime, monkeypatch):
    monkeypatch.setenv("FAKE_FFMPEG_EXITS", "1")
    rt = make_runtime()
    rt.resolver.streams = [RateLimited()]

    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")

    assert rt.sleep.calls == [2.0, 30, 60]
    assert [n.message for n in rt.notices.pending()] == [
        "Rate limited resolving stream URL after multiple attempts"
    ]


async def test_retry_resolve_failure_stops(make_runtime, ffmpeg_log, monkeypatch):
    monkeypatch.setenv("FAKE_FFMPEG_EXITS", "1")
    rt = make_runtime()
    rt.resolver.streams = [Offline("Channel 'alice' is offline")]

    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")

    assert len(ffmpeg_runs(ffmpeg_log)) == 1
    assert [n.message for n in rt.notices.pending()] == [
        "Failed to resolve stream URL: Channel 'alice' is offline"
    ]


async def test_cancel_sends_sigint_and_waits_for_ffmpeg(
    make_runtime, monkeypatch, tmp_path
):
    monkeypatch.setenv("FAKE_FFMPEG_BLOCK", "1")
    rt = make_runtime()
    rt.active.add("alice")
    task = asyncio.create_task(record_live(rt, "alice", "twitch.tv", "best", URLS, ""))
    await wait_for_glob(tmp_path / "dl", "*.mp4.ready")

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert list((tmp_path / "dl").glob("*.mp4.finalized"))
    assert files(tmp_path / "out") == []
    assert "alice" not in rt.active


async def test_progress_is_tracked_while_recording(make_runtime, monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_FFMPEG_BLOCK", "1")
    rt = make_runtime()
    task = asyncio.create_task(record_live(rt, "alice", "twitch.tv", "best", URLS, ""))
    await wait_for_glob(tmp_path / "dl", "*.mp4.ready")
    try:
        for _ in range(100):
            p = rt.progress.get("live:alice")
            if p and p.size_bytes == 256 * 1024:
                break
            await asyncio.sleep(0.02)
        assert p is not None
        assert p.size_bytes == 256 * 1024
        assert p.duration == pytest.approx(2.0)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_missing_ffmpeg_is_logged_not_raised(make_runtime, ffmpeg_log, tmp_path):
    rt = make_runtime(ffmpeg_path=str(tmp_path / "missing-ffmpeg"))
    rt.active.add("alice")
    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")
    assert ffmpeg_runs(ffmpeg_log) == []
    assert "alice" not in rt.active


async def test_split_audio_and_video_urls_both_reach_ffmpeg(make_runtime, ffmpeg_log):
    rt = make_runtime()
    split = StreamURLs("https://video.example/v.m3u8", "https://audio.example/a.m3u8")

    await record_live(rt, "alice", "twitch.tv", "best", split, "")

    [run] = ffmpeg_runs(ffmpeg_log)
    assert split.video in run and split.audio in run
    expected = build_live_args(
        split.video, split.audio, run[-1], rt.settings.ffmpeg, ffmpeg=FAKE_FFMPEG
    )
    assert run == expected[1:]


async def test_cancel_during_move_still_moves_and_runs_the_post_script(
    make_runtime, monkeypatch, tmp_path
):
    move = BlockingMove(recorder.move_file)
    monkeypatch.setattr(recorder, "move_file", move)
    rt = make_runtime()
    marker = tmp_path / "hook.txt"
    hook = tmp_path / "hook.sh"
    hook.write_text(f'#!/bin/sh\necho "$STREAMDL_TYPE|$1" > {marker}\n')
    hook.chmod(0o755)
    rt.active.add("alice")
    task = asyncio.create_task(
        record_live(rt, "alice", "twitch.tv", "best", URLS, str(hook))
    )
    try:
        await move.wait_started()
        task.cancel()
        await asyncio.sleep(0)
    finally:
        move.release.set()

    with pytest.raises(asyncio.CancelledError):
        await task
    await rt.wait_for_post_scripts()

    [moved] = files(tmp_path / "out")
    assert marker.read_text() == f"live|{moved}\n"
    assert "alice" not in rt.active


async def test_ffmpeg_is_killed_if_reading_its_output_fails(
    ffmpeg_log, monkeypatch, tmp_path
):
    monkeypatch.setenv("FAKE_FFMPEG_BLOCK", "1")
    procs = []
    spawn = asyncio.create_subprocess_exec

    async def recording_spawn(*args, **kwargs):
        proc = await spawn(*args, **kwargs)
        procs.append(proc)
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", recording_spawn)

    class BrokenWriter:
        def write(self, data):
            raise RuntimeError("writer bug")

    out = tmp_path / "x.mp4"
    with pytest.raises(RuntimeError, match="writer bug"):
        await asyncio.wait_for(run_ffmpeg([FAKE_FFMPEG, str(out)], BrokenWriter()), 5)

    [proc] = procs
    assert proc.returncode == -signal.SIGKILL
    assert not (tmp_path / "x.mp4.finalized").exists()
