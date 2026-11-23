import asyncio
import logging
import os
import re
import shutil
import signal
from types import SimpleNamespace

import pytest
from helpers import (
    FAKE_FFMPEG,
    BlockingMove,
    FakeResolver,
    ffmpeg_runs,
    streamlink_runs,
    wait_for_glob,
)

from streamdl import recorder
from streamdl.ffmpeg import build_live_args, build_pipe_args
from streamdl.notices import Notice
from streamdl.progress import DownloadKind
from streamdl.recorder import record_live, run_ffmpeg
from streamdl.resolver import NotFound, Offline, RateLimited, ResolverError, StreamURLs
from streamdl.settings import FfmpegOptions, ReconnectOptions, TwitchOptions

URLS = StreamURLs("https://video.example/live.m3u8")
FRESH = StreamURLs("https://video.example/fresh.m3u8")
AD_FREE = TwitchOptions(adfree=True)
WINDOW = ReconnectOptions(window=30, interval=5)


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
    assert len(runs) == 4  # three attempts, then the join
    assert URLS.video in runs[0]
    assert FRESH.video in runs[1] and FRESH.video in runs[2]
    assert "concat" in runs[3]
    assert rt.sleep.calls == [2.0, 4.0]
    assert rt.resolver.stream_calls == [("twitch.tv", "alice", "best")] * 2
    assert rt.notices.pending() == []
    [moved] = files(tmp_path / "out")
    assert moved.read_bytes() == b"fake mp4" * 3


async def test_gives_up_after_max_retries(
    make_runtime, ffmpeg_log, monkeypatch, caplog, tmp_path
):
    caplog.set_level(logging.WARNING, logger="streamdl")
    monkeypatch.setenv("FAKE_FFMPEG_EXITS", "1")
    rt = make_runtime(ffmpeg=FfmpegOptions(max_retries=2))
    rt.resolver.streams = [URLS]
    rt.active.add("alice")

    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")

    assert len(ffmpeg_runs(ffmpeg_log)) == 4  # three attempts, then the join
    assert [n.message for n in rt.notices.pending()] == [
        "Recording failed after 3 attempts: exit status 1"
    ]
    assert [m for m in caplog.messages if m.startswith("Recording failed for")] == [
        "Recording failed for alice (attempt 1/3). Retrying in 2s",
        "Recording failed for alice (attempt 2/3). Retrying in 4s",
    ]
    assert "FFmpeg failed for alice after 3 attempts: exit status 1" in caplog.messages
    assert len(files(tmp_path / "out")) == 1  # what was recorded is kept
    assert "alice" not in rt.active


async def test_a_rate_limited_retry_lookup_finishes_the_recording(
    make_runtime, monkeypatch, tmp_path
):
    monkeypatch.setenv("FAKE_FFMPEG_EXITS", "1")
    rt = make_runtime()
    rt.resolver.streams = [RateLimited()]

    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")

    assert rt.sleep.calls == [2.0]
    assert len(rt.resolver.stream_calls) == 1
    assert rt.notices.pending() == []
    assert len(files(tmp_path / "out")) == 1


async def test_a_failure_then_offline_still_moves_the_recording(
    make_runtime, ffmpeg_log, monkeypatch, caplog, tmp_path
):
    caplog.set_level(logging.INFO, logger="streamdl")
    monkeypatch.setenv("FAKE_FFMPEG_EXITS", "1")
    rt = make_runtime()
    rt.resolver.streams = [Offline("Channel 'alice' is offline")]
    hook, marker = make_hook(tmp_path)

    await record_live(rt, "alice", "twitch.tv", "best", URLS, hook)
    await rt.wait_for_post_scripts()

    assert len(ffmpeg_runs(ffmpeg_log)) == 1
    assert rt.notices.pending() == []
    [moved] = files(tmp_path / "out")
    assert hook_calls(marker) == [str(moved)]
    assert (
        "alice is no longer live after FFmpeg failed; finishing the recording"
        in caplog.messages
    )


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
    make_runtime, ffmpeg_log, streamlink_log, monkeypatch, caplog
):
    caplog.set_level(logging.DEBUG, logger="streamdl")
    monkeypatch.setenv(
        "FAKE_STREAMLINK_STDERR", "[cli][debug] Authorization: OAuth sekrit"
    )
    rt = make_runtime(twitch=TwitchOptions(adfree=True, oauth_token="sekrit"))

    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")

    [sl] = streamlink_runs(streamlink_log)
    assert sl["config"] == "twitch-api-header=Authorization=OAuth sekrit\n"
    assert (sl["config_mode"], sl["dir_mode"]) == (0o600, 0o700)
    config = sl["args"][sl["args"].index("--config") + 1]
    assert not os.path.exists(os.path.dirname(config))
    assert not any("sekrit" in a for a in sl["args"])
    assert not any("sekrit" in a for a in ffmpeg_runs(ffmpeg_log)[0])
    assert "Authorization: OAuth <redacted>" in caplog.text
    assert "sekrit" not in caplog.text


async def test_cancel_removes_the_token_config(
    make_runtime, streamlink_log, monkeypatch, tmp_path
):
    monkeypatch.setenv("FAKE_STREAMLINK_BLOCK", "1")
    monkeypatch.setenv("FAKE_STREAMLINK_READY", str(tmp_path / "sl.ready"))
    rt = make_runtime(twitch=TwitchOptions(adfree=True, oauth_token="sekrit"))
    task = asyncio.create_task(record_live(rt, "alice", "twitch.tv", "best", URLS, ""))
    await wait_for_glob(tmp_path, "sl.ready")
    [sl] = streamlink_runs(streamlink_log)
    config = sl["args"][sl["args"].index("--config") + 1]
    assert os.path.exists(config)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert not os.path.exists(os.path.dirname(config))


async def test_ad_breaks_become_info_notices(make_runtime, monkeypatch):
    monkeypatch.setenv(
        "FAKE_STREAMLINK_STDERR",
        "[plugins.twitch][info] Detected advertisement break of 30 seconds",
    )
    rt = make_runtime(twitch=AD_FREE)

    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")

    assert Notice(logging.INFO, "alice", "Skipping a 30s ad break") in (
        rt.notices.pending()
    )


async def test_stopping_streamlink_after_ffmpeg_finishes_is_not_a_failure(
    make_runtime, streamlink_log, monkeypatch, caplog, tmp_path
):
    caplog.set_level(logging.WARNING, logger="streamdl")
    ready = tmp_path / "sl.ready"
    monkeypatch.setenv("FAKE_STREAMLINK_BLOCK", "1")
    monkeypatch.setenv("FAKE_STREAMLINK_READY", str(ready))
    monkeypatch.setenv("FAKE_STREAMLINK_STDERR", "[cli][info] Opening stream")
    monkeypatch.setenv("FAKE_FFMPEG_SKIP_STDIN", "1")
    monkeypatch.setenv("FAKE_FFMPEG_WAIT_FOR", str(ready))
    rt = make_runtime(twitch=AD_FREE)

    await asyncio.wait_for(record_live(rt, "alice", "twitch.tv", "best", URLS, ""), 10)

    assert len(streamlink_runs(streamlink_log)) == 1
    assert len(files(tmp_path / "out")) == 1
    assert "streamlink failed" not in caplog.text
    assert "streamlink log tail" not in caplog.text


async def test_streamlink_read_timeout_is_logged_as_the_stream_ending(
    make_runtime, monkeypatch, caplog, tmp_path
):
    caplog.set_level(logging.INFO, logger="streamdl")
    monkeypatch.setenv("FAKE_STREAMLINK_EXITS", "1")
    monkeypatch.setenv(
        "FAKE_STREAMLINK_STDERR",
        "[stream.hls][error] Error when reading from stream: Read timeout, exiting",
    )
    rt = make_runtime(twitch=AD_FREE)

    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")

    assert len(files(tmp_path / "out")) == 1
    assert (
        "streamlink stopped receiving data for alice (the stream has probably "
        "ended); keeping what was recorded" in caplog.messages
    )
    assert "streamlink failed" not in caplog.text
    assert "streamlink log tail" not in caplog.text


async def test_ffmpeg_failure_retries_the_whole_pipe(
    make_runtime, ffmpeg_log, streamlink_log, monkeypatch, tmp_path
):
    monkeypatch.setenv("FAKE_FFMPEG_EXITS", "1,0")
    rt = make_runtime(twitch=AD_FREE)
    rt.resolver.streams = [FRESH]

    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")

    assert len(streamlink_runs(streamlink_log)) == 2
    assert len(ffmpeg_runs(ffmpeg_log)) == 3  # two attempts, then the join
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


# --- reconnect window -----------------------------------------------------------


class SlowResolver(FakeResolver):
    """A FakeResolver whose every lookup takes `seconds` on the fake clock."""

    def __init__(self, sleep, seconds):
        super().__init__()
        self._sleep = sleep
        self._seconds = seconds

    async def stream(self, site, user, quality):
        self._sleep.now += self._seconds
        return await super().stream(site, user, quality)


async def wait(rt, **kwargs):
    return await recorder._wait_for_live(rt, "twitch.tv", "alice", "best", **kwargs)


async def test_wait_for_live_returns_as_soon_as_the_channel_is_back(make_runtime):
    rt = make_runtime(reconnect=WINDOW)
    rt.resolver.streams = [Offline("x"), Offline("x"), FRESH]
    assert await wait(rt) == FRESH
    assert len(rt.resolver.stream_calls) == 3
    assert rt.sleep.calls == [5, 5]


async def test_wait_for_live_checks_until_the_window_closes(make_runtime):
    rt = make_runtime(reconnect=WINDOW)
    rt.resolver.streams = [Offline("x")]
    assert await wait(rt) is None
    assert len(rt.resolver.stream_calls) == 6  # at 0, 5, 10, 15, 20 and 25s
    assert rt.sleep.calls == [5] * 5


async def test_slow_checks_count_towards_the_window(make_runtime):
    rt = make_runtime(reconnect=WINDOW)
    rt.resolver = SlowResolver(rt.sleep, seconds=12)
    rt.resolver.streams = [Offline("x")]
    assert await wait(rt) is None
    assert len(rt.resolver.stream_calls) == 3  # starting at 0, 12 and 24s
    assert rt.sleep.calls == []


async def test_lookup_errors_dont_end_the_window(make_runtime):
    rt = make_runtime(reconnect=WINDOW)
    rt.resolver.streams = [
        RateLimited(),
        ResolverError("Download error: Could not resolve host: chaturbate.com."),
        NotFound("not found"),
        FRESH,
    ]
    assert await wait(rt) == FRESH
    assert rt.notices.pending() == []


async def test_a_zero_window_does_not_check(make_runtime):
    rt = make_runtime()  # make_runtime's window is 0
    rt.resolver.streams = [FRESH]
    assert await wait(rt) is None
    assert rt.resolver.stream_calls == []


async def test_at_least_once_checks_with_a_zero_window(make_runtime):
    rt = make_runtime()
    rt.resolver.streams = [Offline("x")]
    assert await wait(rt, at_least_once=True) is None
    assert len(rt.resolver.stream_calls) == 1
    rt.resolver.streams = [FRESH]
    assert await wait(rt, at_least_once=True) == FRESH


async def test_wait_for_live_shows_reconnecting(make_runtime):
    rt = make_runtime(reconnect=WINDOW)
    rt.progress.start("live:alice", channel="alice", kind=DownloadKind.LIVE)
    seen = []

    class Peek(FakeResolver):
        async def stream(self, site, user, quality):
            seen.append(rt.progress.get("live:alice").status)
            return FRESH

    rt.resolver = Peek()
    await wait(rt)
    assert seen == ["reconnecting"]
    assert rt.progress.get("live:alice").status == ""


async def test_wait_for_live_holds_the_site_lock(make_runtime):
    rt = make_runtime(reconnect=WINDOW)
    locked = []

    class Peek(FakeResolver):
        async def stream(self, site, user, quality):
            locked.append(rt.site_lock(site).locked())
            return FRESH

    rt.resolver = Peek()
    await wait(rt)
    assert locked == [True]


async def test_wait_for_live_releases_the_site_lock_between_checks(make_runtime):
    rt = make_runtime(reconnect=WINDOW)
    rt.resolver.streams = [Offline("x"), FRESH]
    fake_sleep = rt.sleep
    locked = []

    async def sleep(seconds):
        locked.append(rt.site_lock("twitch.tv").locked())
        await fake_sleep(seconds)

    rt.sleep = sleep
    assert await wait(rt) == FRESH
    assert locked == [False]


async def test_cancelling_wait_for_live_releases_the_lock_and_clears_the_status(
    make_runtime,
):
    rt = make_runtime(reconnect=WINDOW)
    rt.progress.start("live:alice", channel="alice", kind=DownloadKind.LIVE)
    looking_up = asyncio.Event()

    class Hang(FakeResolver):
        async def stream(self, site, user, quality):
            looking_up.set()
            await asyncio.Event().wait()

    rt.resolver = Hang()
    task = asyncio.create_task(wait(rt))
    await looking_up.wait()
    assert rt.progress.get("live:alice").status == "reconnecting"
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not rt.site_lock("twitch.tv").locked()
    assert rt.progress.get("live:alice").status == ""


# --- parts, reconnects and joins ---------------------------------------------------


def make_hook(tmp_path):
    marker = tmp_path / "hook.txt"
    hook = tmp_path / "hook.sh"
    hook.write_text(f'#!/bin/sh\necho "$1" >> {marker}\n')
    hook.chmod(0o755)
    return str(hook), marker


def hook_calls(marker):
    return marker.read_text().splitlines() if marker.exists() else []


class BlockingResolver(FakeResolver):
    """A resolver whose lookups never return, so a test can cancel mid-window."""

    def __init__(self):
        super().__init__()
        self.called = asyncio.Event()

    async def stream(self, site, user, quality):
        self.called.set()
        await asyncio.Event().wait()


async def test_a_drop_that_comes_back_is_joined_into_one_file(
    make_runtime, ffmpeg_log, tmp_path
):
    rt = make_runtime(reconnect=WINDOW)
    rt.resolver.streams = [Offline("x"), Offline("x"), FRESH, Offline("gone")]
    hook, marker = make_hook(tmp_path)

    await record_live(rt, "alice", "twitch.tv", "best", URLS, hook)
    await rt.wait_for_post_scripts()

    runs = ffmpeg_runs(ffmpeg_log)
    assert len(runs) == 3  # two parts, then the join
    assert URLS.video in runs[0] and FRESH.video in runs[1] and "concat" in runs[2]
    assert runs[1][-1].endswith("_part2.mp4")
    [moved] = files(tmp_path / "out")
    assert re.fullmatch(r"alice_\d{4}-\d\d-\d\d_\d\d-\d\d-\d\d\.mp4", moved.name)
    assert moved.read_bytes() == b"fake mp4" * 2
    assert files(tmp_path / "dl") == []
    assert hook_calls(marker) == [str(moved)]
    assert [n.message for n in rt.notices.pending()] == [
        "Stream came back after 10s; recording part 2"
    ]
    assert rt.sleep.calls == [5] * 7  # 2 before it came back, 5 after part 2


async def test_a_drop_that_doesnt_come_back_finishes_after_the_window(
    make_runtime, ffmpeg_log, tmp_path
):
    rt = make_runtime(reconnect=WINDOW)
    rt.resolver.streams = [Offline("x")]

    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")

    assert len(ffmpeg_runs(ffmpeg_log)) == 1
    assert len(rt.resolver.stream_calls) == 6
    [moved] = files(tmp_path / "out")
    assert moved.read_bytes() == b"fake mp4"
    assert rt.notices.pending() == []


async def test_a_failure_retry_writes_a_new_part(
    make_runtime, ffmpeg_log, monkeypatch, caplog, tmp_path
):
    caplog.set_level(logging.DEBUG, logger="streamdl")
    monkeypatch.setenv("FAKE_FFMPEG_EXITS", "1,0")
    rt = make_runtime()
    rt.resolver.streams = [FRESH]

    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")

    runs = ffmpeg_runs(ffmpeg_log)
    assert runs[0][-1] != runs[1][-1]
    assert runs[1][-1].endswith("_part2.mp4")
    [moved] = files(tmp_path / "out")
    assert moved.read_bytes() == b"fake mp4" * 2
    # Each part's log tail is that part's output alone.
    tails = [
        r.getMessage()
        for r in caplog.records
        if r.getMessage().startswith("FFmpeg log tail for alice")
    ]
    assert len(tails) == 2
    assert [t.count("Input #0") for t in tails] == [1, 1]


async def test_the_failure_count_resets_after_a_clean_part(
    make_runtime, ffmpeg_log, monkeypatch, tmp_path
):
    monkeypatch.setenv("FAKE_FFMPEG_EXITS", "1,0,1,0")
    rt = make_runtime(reconnect=WINDOW, ffmpeg=FfmpegOptions(max_retries=1))
    rt.resolver.streams = [FRESH, FRESH, FRESH, Offline("gone")]

    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")

    assert len(ffmpeg_runs(ffmpeg_log)) == 5  # four parts, then the join
    assert not [n for n in rt.notices.pending() if n.level == logging.ERROR]
    [moved] = files(tmp_path / "out")
    assert moved.read_bytes() == b"fake mp4" * 4


async def test_a_fallback_format_warning_on_a_fresh_url_becomes_a_notice(
    make_runtime, tmp_path
):
    warning = "Requested format 'best' unavailable; using default selection"
    rt = make_runtime(reconnect=WINDOW)
    rt.resolver.streams = [StreamURLs(FRESH.video, warning=warning), Offline("gone")]

    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")

    assert Notice(logging.WARNING, "alice", warning) in rt.notices.pending()
    assert len(files(tmp_path / "out")) == 1


async def test_mismatched_parts_are_kept_and_each_gets_the_hook(
    make_runtime, ffmpeg_log, monkeypatch, tmp_path
):
    monkeypatch.setenv("FAKE_FFPROBE_ODD", "_part2")
    rt = make_runtime(reconnect=WINDOW)
    rt.resolver.streams = [FRESH, Offline("gone")]
    hook, marker = make_hook(tmp_path)

    await record_live(rt, "alice", "twitch.tv", "best", URLS, hook)
    await rt.wait_for_post_scripts()

    moved = files(tmp_path / "out")
    assert [p.name.endswith("_part2.mp4") for p in moved] == [False, True]
    assert sorted(hook_calls(marker)) == [str(p) for p in moved]
    assert rt.notices.pending()[-1] == Notice(
        logging.WARNING,
        "alice",
        "Kept 2 separate parts: stream 0 width is 1280 in part 2, 1920 in part 1",
    )
    assert len(ffmpeg_runs(ffmpeg_log)) == 2  # no join was attempted


async def test_a_failed_join_keeps_the_parts(make_runtime, monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_FFMPEG_CONCAT_EXIT", "1")
    rt = make_runtime(reconnect=WINDOW)
    rt.resolver.streams = [FRESH, Offline("gone")]

    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")

    assert len(files(tmp_path / "out")) == 2
    assert files(tmp_path / "dl") == []  # the half-joined file was deleted
    assert rt.notices.pending()[-1].message == (
        "Kept 2 separate parts: the join failed (exit status 1)"
    )


async def test_cancel_during_the_window_leaves_the_parts(
    make_runtime, caplog, tmp_path
):
    caplog.set_level(logging.INFO, logger="streamdl")
    rt = make_runtime(reconnect=WINDOW)
    rt.resolver = BlockingResolver()
    rt.active.add("alice")
    hook, marker = make_hook(tmp_path)
    task = asyncio.create_task(
        record_live(rt, "alice", "twitch.tv", "best", URLS, hook)
    )
    await asyncio.wait_for(rt.resolver.called.wait(), 5)
    assert rt.progress.get("live:alice").status == "reconnecting"

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert [p.suffix for p in files(tmp_path / "dl")] == [".mp4"]
    assert files(tmp_path / "out") == []
    assert hook_calls(marker) == []
    assert "Shutting down: left 1 part(s) for alice" in caplog.text
    assert "alice" not in rt.active


async def test_cancel_during_the_join_leaves_the_parts(
    make_runtime, monkeypatch, caplog, tmp_path
):
    caplog.set_level(logging.INFO, logger="streamdl")
    monkeypatch.setenv("FAKE_FFMPEG_CONCAT_BLOCK", "1")
    rt = make_runtime(reconnect=WINDOW)
    rt.resolver.streams = [FRESH, Offline("gone")]
    task = asyncio.create_task(record_live(rt, "alice", "twitch.tv", "best", URLS, ""))
    await wait_for_glob(tmp_path / "dl", "*.joining.mp4.ready")
    assert rt.progress.get("live:alice").status == "joining"

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    names = [p.name for p in files(tmp_path / "dl")]
    assert not [n for n in names if n.endswith(".joining.mp4")]
    assert len([n for n in names if n.endswith(".mp4")]) == 2
    assert files(tmp_path / "out") == []
    assert "Shutting down: left 2 part(s) for alice" in caplog.text


async def test_a_clean_exit_logs_ffmpegs_last_lines_at_debug(make_runtime, caplog):
    caplog.set_level(logging.DEBUG, logger="streamdl")
    rt = make_runtime()

    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")

    [record] = [
        r
        for r in caplog.records
        if r.getMessage().startswith("FFmpeg log tail for alice")
    ]
    assert record.levelno == logging.DEBUG
    assert "speed=1.00x" in record.getMessage()


def test_recorded_parts_drops_missing_and_empty_files(tmp_path):
    full = tmp_path / "a.mp4"
    full.write_bytes(b"x")
    empty = tmp_path / "b.mp4"
    empty.write_bytes(b"")
    missing = tmp_path / "c.mp4"
    assert recorder._recorded_parts([str(full), str(empty), str(missing)]) == [
        str(full)
    ]
    assert not empty.exists()


async def test_a_part_that_fails_to_start_still_moves_the_earlier_part(
    make_runtime, ffmpeg_log, monkeypatch, tmp_path
):
    spawn = asyncio.create_subprocess_exec
    ffmpeg_starts = []

    async def failing_spawn(*args, **kwargs):
        if args[0] == FAKE_FFMPEG:
            ffmpeg_starts.append(args)
            if len(ffmpeg_starts) == 2:
                raise OSError("no more processes")
        return await spawn(*args, **kwargs)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", failing_spawn)
    rt = make_runtime(reconnect=WINDOW)
    rt.resolver.streams = [FRESH, Offline("gone")]
    hook, marker = make_hook(tmp_path)

    await record_live(rt, "alice", "twitch.tv", "best", URLS, hook)
    await rt.wait_for_post_scripts()

    assert len(ffmpeg_runs(ffmpeg_log)) == 1  # no concat run
    [moved] = files(tmp_path / "out")
    assert moved.read_bytes() == b"fake mp4"
    assert hook_calls(marker) == [str(moved)]
    assert files(tmp_path / "dl") == []


async def test_a_clean_exit_that_recorded_nothing_is_retried(
    make_runtime, ffmpeg_log, monkeypatch, caplog, tmp_path
):
    caplog.set_level(logging.WARNING, logger="streamdl")
    monkeypatch.setenv("FAKE_FFMPEG_EMPTY_RUNS", "1")
    rt = make_runtime()
    rt.resolver.streams = [FRESH]
    hook, marker = make_hook(tmp_path)

    await record_live(rt, "alice", "twitch.tv", "best", URLS, hook)
    await rt.wait_for_post_scripts()

    runs = ffmpeg_runs(ffmpeg_log)
    assert len(runs) == 2
    assert runs[1][-1].endswith("_part2.mp4")
    assert rt.sleep.calls == [2.0]
    assert "FFmpeg for alice exited without recording anything" in caplog.messages
    # The lone surviving part gets the recording's plain name.
    [moved] = files(tmp_path / "out")
    assert re.fullmatch(r"alice_\d{4}-\d\d-\d\d_\d\d-\d\d-\d\d\.mp4", moved.name)
    assert moved.read_bytes() == b"fake mp4"
    assert hook_calls(marker) == [str(moved)]
    assert files(tmp_path / "dl") == []
    assert rt.notices.pending() == []


async def test_clean_exits_that_record_nothing_stop_after_max_retries(
    make_runtime, ffmpeg_log, monkeypatch, tmp_path
):
    monkeypatch.setenv("FAKE_FFMPEG_EMPTY_RUNS", "1,2,3")
    rt = make_runtime(reconnect=WINDOW, ffmpeg=FfmpegOptions(max_retries=2))
    rt.resolver.streams = [FRESH, FRESH, Offline("gone")]

    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")

    assert len(ffmpeg_runs(ffmpeg_log)) == 3
    assert len(rt.resolver.stream_calls) == 2
    assert rt.sleep.calls == [2.0, 4.0]
    assert [n.message for n in rt.notices.pending()] == [
        "Recording failed after 3 attempts: nothing was recorded"
    ]
    assert files(tmp_path / "out") == []
    assert files(tmp_path / "dl") == []


async def test_a_part_that_cant_be_deleted_after_the_join_is_left(
    make_runtime, monkeypatch, caplog, tmp_path
):
    caplog.set_level(logging.WARNING, logger="streamdl")
    remove = os.remove

    def failing_remove(path, *args, **kwargs):
        if str(path).endswith("_part2.mp4"):
            raise PermissionError("not allowed")
        remove(path, *args, **kwargs)

    monkeypatch.setattr(os, "remove", failing_remove)
    rt = make_runtime(reconnect=WINDOW)
    rt.resolver.streams = [FRESH, Offline("gone")]
    statuses = []
    move_file = recorder.move_file

    def peeking_move(*args, **kwargs):
        statuses.append(rt.progress.get("live:alice").status)
        return move_file(*args, **kwargs)

    monkeypatch.setattr(recorder, "move_file", peeking_move)
    hook, marker = make_hook(tmp_path)

    await record_live(rt, "alice", "twitch.tv", "best", URLS, hook)
    await rt.wait_for_post_scripts()

    [moved] = files(tmp_path / "out")
    assert moved.read_bytes() == b"fake mp4" * 2
    assert hook_calls(marker) == [str(moved)]
    assert [p.name.endswith("_part2.mp4") for p in files(tmp_path / "dl")] == [True]
    assert "Couldn't delete joined part" in caplog.text
    assert statuses == [""]  # "joining" is cleared before the move


async def test_a_joined_file_that_cant_be_renamed_keeps_the_parts(
    make_runtime, monkeypatch, tmp_path
):
    replace = os.replace

    def failing_replace(src, dst, *args, **kwargs):
        if str(src).endswith(".joining.mp4"):
            raise OSError("rename refused")
        replace(src, dst, *args, **kwargs)

    monkeypatch.setattr(os, "replace", failing_replace)
    rt = make_runtime(reconnect=WINDOW)
    rt.resolver.streams = [FRESH, Offline("gone")]
    hook, marker = make_hook(tmp_path)

    await record_live(rt, "alice", "twitch.tv", "best", URLS, hook)
    await rt.wait_for_post_scripts()

    moved = files(tmp_path / "out")
    assert [p.read_bytes() for p in moved] == [b"fake mp4"] * 2
    assert sorted(hook_calls(marker)) == [str(p) for p in moved]
    assert files(tmp_path / "dl") == []  # the joined file was deleted
    assert rt.notices.pending()[-1].message == (
        "Kept 2 separate parts: the joined file couldn't be renamed (rename refused)"
    )


async def test_parts_are_kept_when_there_isnt_room_to_join_them(
    make_runtime, ffmpeg_log, monkeypatch, tmp_path
):
    monkeypatch.setattr(shutil, "disk_usage", lambda path: SimpleNamespace(free=10))
    rt = make_runtime(reconnect=WINDOW)
    rt.resolver.streams = [FRESH, Offline("gone")]

    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")

    assert len(ffmpeg_runs(ffmpeg_log)) == 2  # no join was attempted
    assert len(files(tmp_path / "out")) == 2
    assert rt.notices.pending()[-1].message == (
        "Kept 2 separate parts: not enough free space to join (needs 16B, 10B free)"
    )


def test_the_join_needs_5_percent_headroom(monkeypatch, tmp_path):
    parts = []
    for name in ("a.mp4", "b.mp4"):
        (tmp_path / name).write_bytes(b"x" * 1000)
        parts.append(str(tmp_path / name))
    free = [2099]
    monkeypatch.setattr(
        shutil, "disk_usage", lambda path: SimpleNamespace(free=free[0])
    )

    assert recorder._join_space_shortfall(parts, str(tmp_path)) == (
        "not enough free space to join (needs 2.1KiB, 2.0KiB free)"
    )
    free[0] = 2100  # 2000 bytes of parts plus 5%
    assert recorder._join_space_shortfall(parts, str(tmp_path)) == ""


async def test_a_twitch_drop_that_comes_back_is_joined(
    make_runtime, streamlink_log, tmp_path
):
    rt = make_runtime(twitch=AD_FREE, reconnect=WINDOW)
    rt.resolver.streams = [FRESH, Offline("gone")]

    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")

    assert len(streamlink_runs(streamlink_log)) == 2
    [moved] = files(tmp_path / "out")
    assert moved.read_bytes() == b"fake mp4" * 2


async def test_only_the_first_reconnect_posts_a_notice_but_each_is_logged(
    make_runtime, ffmpeg_log, caplog, tmp_path
):
    caplog.set_level(logging.INFO, logger="streamdl")
    rt = make_runtime(reconnect=WINDOW)
    rt.resolver.streams = [FRESH, Offline("x"), FRESH, FRESH, Offline("gone")]

    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")

    assert len(ffmpeg_runs(ffmpeg_log)) == 5  # four parts, then the join
    assert [n.message for n in rt.notices.pending()] == [
        "Stream came back after 0s; recording part 2"
    ]
    assert [m for m in caplog.messages if " came back after " in m] == [
        "alice came back after 0s; recording part 2",
        "alice came back after 5s; recording part 3",
        "alice came back after 0s; recording part 4",
    ]


async def test_the_part_number_counts_only_parts_that_recorded_something(
    make_runtime, monkeypatch, tmp_path
):
    monkeypatch.setenv("FAKE_FFMPEG_EMPTY_RUNS", "1")
    rt = make_runtime(reconnect=WINDOW)
    rt.resolver.streams = [FRESH, FRESH, Offline("gone")]
    shown = []
    record_attempt = recorder._record_attempt

    async def peeking_attempt(*args, **kwargs):
        p = rt.progress.get("live:alice")
        shown.append((p.parts, p.status))
        return await record_attempt(*args, **kwargs)

    monkeypatch.setattr(recorder, "_record_attempt", peeking_attempt)
    sleep = rt.sleep
    during_sleep = []

    async def peeking_sleep(seconds):
        p = rt.progress.get("live:alice")
        during_sleep.append((p.status, p.speed))
        await sleep(seconds)

    rt.sleep = peeking_sleep

    await record_live(rt, "alice", "twitch.tv", "best", URLS, "")

    # The empty first attempt isn't a part; the retry's backoff shows "retrying".
    assert shown == [(1, ""), (1, ""), (2, "")]
    assert during_sleep[0] == ("retrying", 0.0)
    assert len(files(tmp_path / "out")) == 1


async def test_an_unreadable_part_is_left_out_of_the_join_and_kept_without_the_hook(
    make_runtime, ffmpeg_log, monkeypatch, tmp_path
):
    monkeypatch.setenv("FAKE_FFPROBE_FAIL", "_part2")
    rt = make_runtime(reconnect=WINDOW)
    rt.resolver.streams = [FRESH, FRESH, Offline("gone")]
    hook, marker = make_hook(tmp_path)

    await record_live(rt, "alice", "twitch.tv", "best", URLS, hook)
    await rt.wait_for_post_scripts()

    [join] = [run for run in ffmpeg_runs(ffmpeg_log) if "concat" in run]
    joined, bad = files(tmp_path / "out")
    assert re.fullmatch(r"alice_\d{4}-\d\d-\d\d_\d\d-\d\d-\d\d\.mp4", joined.name)
    assert joined.read_bytes() == b"fake mp4" * 2
    assert bad.name == joined.stem + "_part2.mp4"
    assert bad.read_bytes() == b"fake mp4"
    assert hook_calls(marker) == [str(joined)]
    assert files(tmp_path / "dl") == []
    assert rt.notices.pending()[-1] == Notice(
        logging.WARNING,
        "alice",
        f"A part couldn't be read and was kept separately as {bad.name}:"
        " Invalid data found when processing input",
    )


async def test_the_one_readable_part_left_takes_the_plain_name(
    make_runtime, monkeypatch, tmp_path
):
    # Part 1 recorded nothing and part 2 can't be read, so part 3 is the recording.
    monkeypatch.setenv("FAKE_FFMPEG_EMPTY_RUNS", "1")
    monkeypatch.setenv("FAKE_FFPROBE_FAIL", "_part2")
    rt = make_runtime(reconnect=WINDOW)
    rt.resolver.streams = [FRESH, FRESH, Offline("gone")]
    hook, marker = make_hook(tmp_path)

    await record_live(rt, "alice", "twitch.tv", "best", URLS, hook)
    await rt.wait_for_post_scripts()

    plain, bad = files(tmp_path / "out")
    assert re.fullmatch(r"alice_\d{4}-\d\d-\d\d_\d\d-\d\d-\d\d\.mp4", plain.name)
    assert bad.name == plain.stem + "_part2.mp4"
    assert hook_calls(marker) == [str(plain)]
    assert files(tmp_path / "dl") == []


def first_part_unreadable(monkeypatch, before=None):
    """Make part 1 unreadable once the session finishes; before(parts) runs first."""
    probe_parts = recorder.probe_parts

    async def probe(parts, **kwargs):
        monkeypatch.setenv("FAKE_FFPROBE_FAIL", os.path.basename(parts[0]))
        if before:
            before(parts)
        return await probe_parts(parts, **kwargs)

    monkeypatch.setattr(recorder, "probe_parts", probe)


@pytest.mark.parametrize("drops", [1, 2])
async def test_an_unreadable_first_part_makes_way_for_the_recording(
    make_runtime, monkeypatch, tmp_path, drops
):
    first_part_unreadable(monkeypatch)
    rt = make_runtime(reconnect=WINDOW)
    rt.resolver.streams = [FRESH] * drops + [Offline("gone")]
    hook, marker = make_hook(tmp_path)

    await record_live(rt, "alice", "twitch.tv", "best", URLS, hook)
    await rt.wait_for_post_scripts()

    # Parts 2 and 3 are joined (or part 2 is alone) under the plain name.
    recording, bad = files(tmp_path / "out")
    assert re.fullmatch(r"alice_\d{4}-\d\d-\d\d_\d\d-\d\d-\d\d\.mp4", recording.name)
    assert recording.read_bytes() == b"fake mp4" * drops
    assert bad.name == recording.stem + "_part1.mp4"
    assert bad.read_bytes() == b"fake mp4"
    assert hook_calls(marker) == [str(recording)]
    assert files(tmp_path / "dl") == []
    assert rt.notices.pending()[-1].message.startswith(
        f"A part couldn't be read and was kept separately as {bad.name}: "
    )


async def test_an_unreadable_first_part_keeps_its_name_if_part1_is_taken(
    make_runtime, monkeypatch, tmp_path
):
    def take_part1(parts):
        with open(parts[0].removesuffix(".mp4") + "_part1.mp4", "wb") as f:
            f.write(b"someone else's")

    first_part_unreadable(monkeypatch, before=take_part1)
    rt = make_runtime(reconnect=WINDOW)
    rt.resolver.streams = [FRESH, FRESH, Offline("gone")]
    hook, marker = make_hook(tmp_path)

    await record_live(rt, "alice", "twitch.tv", "best", URLS, hook)
    await rt.wait_for_post_scripts()

    # Nothing is overwritten: the joined parts 2 and 3 keep part 2's name.
    bad, joined = files(tmp_path / "out")
    assert re.fullmatch(r"alice_\d{4}-\d\d-\d\d_\d\d-\d\d-\d\d\.mp4", bad.name)
    assert bad.read_bytes() == b"fake mp4"
    assert joined.name == bad.stem + "_part2.mp4"
    assert joined.read_bytes() == b"fake mp4" * 2
    assert hook_calls(marker) == [str(joined)]
    [taken] = files(tmp_path / "dl")
    assert taken.read_bytes() == b"someone else's"


async def test_parts_that_cant_be_read_at_all_are_kept_and_each_gets_the_hook(
    make_runtime, ffmpeg_log, monkeypatch, tmp_path
):
    monkeypatch.setenv("FAKE_FFPROBE_FAIL", "alice_")
    rt = make_runtime(reconnect=WINDOW)
    rt.resolver.streams = [FRESH, Offline("gone")]
    hook, marker = make_hook(tmp_path)

    await record_live(rt, "alice", "twitch.tv", "best", URLS, hook)
    await rt.wait_for_post_scripts()

    moved = files(tmp_path / "out")
    assert len(moved) == 2
    assert sorted(hook_calls(marker)) == [str(p) for p in moved]
    assert len(ffmpeg_runs(ffmpeg_log)) == 2  # no join was attempted
    assert rt.notices.pending()[-1].message == (
        "Kept 2 separate parts: none of them can be read"
        " (Invalid data found when processing input)"
    )


async def test_cancel_during_a_join_after_part_1_was_set_aside_counts_it(
    make_runtime, monkeypatch, caplog, tmp_path
):
    caplog.set_level(logging.INFO, logger="streamdl")
    monkeypatch.setenv("FAKE_FFMPEG_CONCAT_BLOCK", "1")
    first_part_unreadable(monkeypatch)
    rt = make_runtime(reconnect=WINDOW)
    rt.resolver.streams = [FRESH, FRESH, Offline("gone")]
    task = asyncio.create_task(record_live(rt, "alice", "twitch.tv", "best", URLS, ""))
    await wait_for_glob(tmp_path / "dl", "*.joining.mp4.ready")

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    names = [p.name for p in files(tmp_path / "dl")]
    assert len([n for n in names if n.endswith("_part1.mp4")]) == 1
    assert "Shutting down: left 3 part(s) for alice" in caplog.text
    assert files(tmp_path / "out") == []


async def test_an_unreadable_part_with_mismatched_readable_parts(
    make_runtime, ffmpeg_log, monkeypatch, tmp_path
):
    monkeypatch.setenv("FAKE_FFPROBE_ODD", "_part2")
    monkeypatch.setenv("FAKE_FFPROBE_FAIL", "_part3")
    rt = make_runtime(reconnect=WINDOW)
    rt.resolver.streams = [FRESH, FRESH, Offline("gone")]
    hook, marker = make_hook(tmp_path)

    await record_live(rt, "alice", "twitch.tv", "best", URLS, hook)
    await rt.wait_for_post_scripts()

    first, second, bad = files(tmp_path / "out")
    assert second.name == first.stem + "_part2.mp4"
    assert bad.name == first.stem + "_part3.mp4"
    assert sorted(hook_calls(marker)) == [str(first), str(second)]
    assert len(ffmpeg_runs(ffmpeg_log)) == 3  # no join was attempted
    assert [n.message for n in rt.notices.pending()][-2:] == [
        f"A part couldn't be read and was kept separately as {bad.name}:"
        " Invalid data found when processing input",
        "Kept 2 separate parts: stream 0 width is 1280 in part 2, 1920 in part 1",
    ]
