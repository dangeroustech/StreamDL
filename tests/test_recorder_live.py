import asyncio
import logging
import os
import re
import signal

import pytest
from helpers import (
    FAKE_FFMPEG,
    BlockingMove,
    ffmpeg_runs,
    streamlink_runs,
    wait_for_glob,
)

from streamdl import recorder
from streamdl.ffmpeg import build_live_args, build_pipe_args
from streamdl.recorder import record_live, run_ffmpeg
from streamdl.resolver import Offline, RateLimited, StreamURLs
from streamdl.settings import FfmpegOptions, TwitchOptions

URLS = StreamURLs("https://video.example/live.m3u8")
FRESH = StreamURLs("https://video.example/fresh.m3u8")
AD_FREE = TwitchOptions(adfree=True)


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


# --- ad-free Twitch -------------------------------------------------------------


async def test_twitch_records_through_streamlink(
    make_runtime, ffmpeg_log, streamlink_log, tmp_path
):
    rt = make_runtime(twitch=AD_FREE)
    rt.active.add("alice")

    await record_live(rt, "alice", "twitch.tv", "720p", URLS, "")

    [sl] = streamlink_runs(streamlink_log)
    assert sl["args"][-3:] == ["--no-config", "twitch.tv/alice", "720p"]
    [run] = ffmpeg_runs(ffmpeg_log)
    assert run == build_pipe_args(run[-1], rt.settings.ffmpeg, ffmpeg=FAKE_FFMPEG)[1:]
    assert URLS.video not in run
    [moved] = files(tmp_path / "out")
    assert moved.read_bytes() == b"fake mp4"
    assert "alice" not in rt.active


@pytest.mark.parametrize("site", ["www.twitch.tv", "Twitch.TV"])
async def test_twitch_host_variants_use_streamlink(make_runtime, streamlink_log, site):
    rt = make_runtime(twitch=AD_FREE)
    await record_live(rt, "alice", site, "best", URLS, "")
    [sl] = streamlink_runs(streamlink_log)
    assert "twitch.tv/alice" in sl["args"]


async def test_other_sites_record_directly(make_runtime, ffmpeg_log, streamlink_log):
    rt = make_runtime(twitch=AD_FREE)
    await record_live(rt, "alice", "kick.com", "best", URLS, "")
    assert streamlink_runs(streamlink_log) == []
    [run] = ffmpeg_runs(ffmpeg_log)
    assert URLS.video in run


async def test_twitch_records_directly_when_ad_free_is_off(
    make_runtime, ffmpeg_log, streamlink_log
):
    rt = make_runtime(twitch=TwitchOptions(adfree=False))
    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")
    assert streamlink_runs(streamlink_log) == []
    assert URLS.video in ffmpeg_runs(ffmpeg_log)[0]


async def test_token_reaches_streamlink_only_through_a_private_file(
    make_runtime, ffmpeg_log, streamlink_log, caplog
):
    caplog.set_level(logging.DEBUG, logger="streamdl")
    rt = make_runtime(twitch=TwitchOptions(adfree=True, oauth_token="sekrit"))

    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")

    [sl] = streamlink_runs(streamlink_log)
    assert sl["config"] == "twitch-api-header=Authorization=OAuth sekrit\n"
    assert (sl["config_mode"], sl["dir_mode"]) == (0o600, 0o700)
    config = sl["args"][sl["args"].index("--config") + 1]
    assert not os.path.exists(os.path.dirname(config))
    assert not any("sekrit" in a for a in sl["args"])
    assert not any("sekrit" in a for a in ffmpeg_runs(ffmpeg_log)[0])
    assert "sekrit" not in caplog.text


async def test_ffmpeg_failure_retries_the_whole_pipe(
    make_runtime, ffmpeg_log, streamlink_log, monkeypatch, tmp_path
):
    monkeypatch.setenv("FAKE_FFMPEG_EXITS", "1,0")
    rt = make_runtime(twitch=AD_FREE)
    rt.resolver.streams = [FRESH]

    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")

    assert len(streamlink_runs(streamlink_log)) == 2
    assert len(ffmpeg_runs(ffmpeg_log)) == 2
    assert rt.resolver.stream_calls == [("twitch.tv", "alice", "best")]
    assert rt.sleep.calls == [2.0]
    assert len(files(tmp_path / "out")) == 1


async def test_ffmpeg_failure_logs_the_streamlink_tail(
    make_runtime, monkeypatch, caplog
):
    caplog.set_level(logging.WARNING, logger="streamdl")
    monkeypatch.setenv("FAKE_FFMPEG_EXITS", "1")
    monkeypatch.setenv("FAKE_STREAMLINK_STDERR", "[cli][error] Read timeout")
    rt = make_runtime(twitch=AD_FREE, ffmpeg=FfmpegOptions(max_retries=0))

    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")

    assert "streamlink log tail for alice:\n[cli][error] Read timeout" in caplog.text


async def test_streamlink_failure_keeps_the_recording(
    make_runtime, streamlink_log, monkeypatch, caplog, tmp_path
):
    caplog.set_level(logging.WARNING, logger="streamdl")
    monkeypatch.setenv("FAKE_STREAMLINK_EXITS", "1")
    monkeypatch.setenv(
        "FAKE_STREAMLINK_STDERR", "[cli][error] Error when reading from stream"
    )
    rt = make_runtime(twitch=AD_FREE)

    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")

    assert len(streamlink_runs(streamlink_log)) == 1
    assert len(files(tmp_path / "out")) == 1
    assert (
        "streamlink failed for alice (exit status 1); keeping what was recorded"
        in caplog.text
    )
    assert "[cli][error] Error when reading from stream" in caplog.text


async def test_cancel_stops_streamlink_and_ffmpeg_finishes(
    make_runtime, monkeypatch, tmp_path
):
    monkeypatch.setenv("FAKE_STREAMLINK_BLOCK", "1")
    monkeypatch.setenv("FAKE_STREAMLINK_READY", str(tmp_path / "sl.ready"))
    rt = make_runtime(twitch=AD_FREE)
    rt.active.add("alice")
    task = asyncio.create_task(record_live(rt, "alice", "twitch.tv", "best", URLS, ""))
    await wait_for_glob(tmp_path, "sl.ready")

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert list((tmp_path / "dl").glob("*.mp4.stdin"))
    assert files(tmp_path / "out") == []
    assert "alice" not in rt.active


async def test_missing_streamlink_is_logged_not_raised(make_runtime, caplog, tmp_path):
    caplog.set_level(logging.ERROR, logger="streamdl")
    rt = make_runtime(
        twitch=AD_FREE, streamlink_cmd=(str(tmp_path / "missing-streamlink"),)
    )
    rt.active.add("alice")

    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")

    assert "Failed to start streamlink or FFmpeg for alice" in caplog.text
    assert "alice" not in rt.active
