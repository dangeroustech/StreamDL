import asyncio
import re

import pytest
from helpers import ffmpeg_runs, wait_for_glob

from streamdl.recorder import record_live
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
    for _ in range(100):
        p = rt.progress.get("live:alice")
        if p and p.size_bytes == 256 * 1024:
            break
        await asyncio.sleep(0.02)
    assert p.size_bytes == 256 * 1024
    assert p.duration == pytest.approx(2.0)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


async def test_missing_ffmpeg_is_logged_not_raised(make_runtime, ffmpeg_log, tmp_path):
    rt = make_runtime(ffmpeg_path=str(tmp_path / "missing-ffmpeg"))
    rt.active.add("alice")
    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")
    assert ffmpeg_runs(ffmpeg_log) == []
    assert "alice" not in rt.active
