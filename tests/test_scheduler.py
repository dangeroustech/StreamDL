import asyncio
import logging

import pytest
from helpers import wait_for_glob

from streamdl.config import ConfigLoader, load_config
from streamdl.resolver import (
    NotFound,
    Offline,
    RateLimited,
    ResolverError,
    StreamURLs,
    VodInfo,
)
from streamdl import scheduler as scheduler_module
from streamdl.scheduler import Scheduler, vod_stream_user
from streamdl.vod_db import VodDB

LIVE_CONFIG = "- site: twitch.tv\n  channels:\n  - name: alice\n    quality: best\n"
VOD_CONFIG = "- site: twitch.tv\n  channels:\n  - name: bob\n    quality: best\n    vod: true\n    vod_limit: 2\n"
URLS = StreamURLs("https://video.example/live.m3u8")


def scheduler(rt, text):
    path = rt.settings.config_path
    path.write_text(text)
    return Scheduler(rt, ConfigLoader(path, load_config(path)))


async def finish(sched):
    await asyncio.gather(*sched.recordings)


@pytest.fixture
def logs(caplog):
    caplog.set_level(logging.DEBUG, logger="streamdl")
    return caplog


def after_wait_line(caplog):
    msgs = [r.getMessage() for r in caplog.records]
    last_wait = max(i for i, m in enumerate(msgs) if m.startswith("Waiting "))
    return msgs[last_wait + 1 :]


@pytest.mark.parametrize(
    "vod_id,expected",
    [
        ("v2807766672", "videos/2807766672"),
        ("2807766672", "videos/2807766672"),
        ("12345", "videos/12345"),
    ],
)
def test_vod_stream_user(vod_id, expected):
    assert vod_stream_user(vod_id) == expected


async def test_live_channel_starts_a_recording(make_runtime, tmp_path):
    rt = make_runtime()
    rt.resolver.streams = [URLS]
    sched = scheduler(rt, LIVE_CONFIG)

    await sched.run_round()

    assert rt.resolver.stream_calls == [("twitch.tv", "alice", "best")]
    assert rt.sleep.calls == [5]
    assert "alice" in rt.active
    await finish(sched)
    assert len(list((tmp_path / "out").iterdir())) == 1
    assert "alice" not in rt.active


async def test_channel_already_recording_is_skipped(make_runtime):
    rt = make_runtime()
    rt.active.add("alice")
    await scheduler(rt, LIVE_CONFIG).run_round()
    assert rt.resolver.stream_calls == []
    assert rt.sleep.calls == []


async def test_offline_notice_follows_the_wait_line(make_runtime, logs):
    rt = make_runtime()
    rt.resolver.streams = [Offline("No live streams found for 'alice' on twitch.tv")]
    await scheduler(rt, LIVE_CONFIG).run_round()
    assert "[alice] No live streams found for 'alice' on twitch.tv" in after_wait_line(
        logs
    )


async def test_resolver_warning_becomes_a_notice(make_runtime, logs):
    rt = make_runtime()
    rt.resolver.streams = [
        StreamURLs(
            "https://v",
            warning="Requested format 'x' unavailable; using default selection",
        )
    ]
    sched = scheduler(rt, LIVE_CONFIG)
    await sched.run_round()
    await finish(sched)
    assert (
        "[alice] Requested format 'x' unavailable; using default selection"
        in after_wait_line(logs)
    )


async def test_rate_limited_three_times(make_runtime, logs):
    rt = make_runtime()
    rt.resolver.streams = [RateLimited()]
    await scheduler(rt, LIVE_CONFIG).run_round()
    assert rt.sleep.calls == [5, 30, 60]
    assert len(rt.resolver.stream_calls) == 3
    [record] = [
        r
        for r in logs.records
        if r.getMessage() == "[alice] Rate limited three times, skipping this tick"
    ]
    assert record.levelno == logging.ERROR


async def test_rate_limited_then_live(make_runtime):
    rt = make_runtime()
    rt.resolver.streams = [RateLimited(), URLS]
    sched = scheduler(rt, LIVE_CONFIG)
    await sched.run_round()
    assert rt.sleep.calls == [5, 30]
    assert "alice" in rt.active
    await finish(sched)


async def test_vod_channel_downloads_new_vods_once(make_runtime, tmp_path):
    rt = make_runtime()
    rt.resolver.vod_lists = [[VodInfo("v1", "First"), VodInfo("v2", "Second")]]
    rt.resolver.streams = [
        StreamURLs("https://vod/1.m3u8"),
        StreamURLs("https://vod/2.m3u8"),
    ]
    sched = scheduler(rt, VOD_CONFIG)

    await sched.run_round()
    await finish(sched)

    assert rt.resolver.vod_calls == [("twitch.tv", "bob", 2)]
    assert [call[1] for call in rt.resolver.stream_calls] == ["videos/1", "videos/2"]
    assert rt.sleep.calls == [5, 5, 5]
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == [
        "bob_vod_v1_First.mp4",
        "bob_vod_v2_Second.mp4",
    ]
    assert rt.active_vods == set()

    await sched.run_round()
    assert len(rt.resolver.stream_calls) == 2  # completed VODs aren't fetched again


async def test_vod_resolve_failure_marks_failed(make_runtime, logs, tmp_path):
    rt = make_runtime()
    rt.resolver.vod_lists = [[VodInfo("v1", "A")]]
    rt.resolver.streams = [ResolverError("boom")]
    await scheduler(rt, VOD_CONFIG).run_round()
    assert "[bob] Failed to resolve VOD v1: boom" in after_wait_line(logs)
    db = VodDB(str(tmp_path / "data" / "streamdl.db"))
    assert db.status("v1") == "failed"
    db.close()


async def test_vod_listing_rate_limited(make_runtime, logs):
    rt = make_runtime()
    rt.resolver.vod_lists = [RateLimited()]
    await scheduler(rt, VOD_CONFIG).run_round()
    assert "[bob] Rate limited checking VODs, skipping this tick" in after_wait_line(
        logs
    )
    assert rt.sleep.calls == [5]


async def test_vod_listing_error(make_runtime, logs):
    rt = make_runtime()
    rt.resolver.vod_lists = [NotFound("user not found or no VODs available")]
    await scheduler(rt, VOD_CONFIG).run_round()
    assert (
        "[bob] GetVods failed: user not found or no VODs available"
        in after_wait_line(logs)
    )


async def test_round_logs_live_users(make_runtime, logs):
    rt = make_runtime()
    rt.active.update({"zed", "amy"})
    await scheduler(rt, "[]\n").run_round()
    assert "Currently Live Users: amy, zed" in [r.getMessage() for r in logs.records]


async def test_each_round_reloads_the_config(make_runtime):
    rt = make_runtime()
    rt.resolver.streams = [Offline("offline")]
    sched = scheduler(rt, LIVE_CONFIG)
    await sched.run_round()
    rt.settings.config_path.write_text(
        "- site: kick.com\n  channels:\n  - name: carol\n"
    )
    await sched.run_round()
    assert rt.resolver.stream_calls[-1] == ("kick.com", "carol", "")


async def test_running_vod_is_not_claimed_again(
    make_runtime, monkeypatch, logs, tmp_path
):
    # Even when the stale cutoff has passed, a VOD still downloading in this
    # process must not get a second FFmpeg (v3 started one every stale window).
    monkeypatch.setenv("FAKE_FFMPEG_BLOCK", "1")
    monkeypatch.setattr(scheduler_module, "MIN_STALE_SECONDS", 0)
    rt = make_runtime(tick_seconds=0)
    rt.resolver.vod_lists = [[VodInfo("v1", "First")]]
    rt.resolver.streams = [StreamURLs("https://vod/1.m3u8")]
    sched = scheduler(rt, VOD_CONFIG)

    await sched.run_round()
    await wait_for_glob(tmp_path / "dl", "*.mp4.ready")
    assert rt.active_vods == {"v1"}

    await sched.run_round()
    assert len(rt.resolver.stream_calls) == 1
    assert [t.get_name() for t in sched.recordings] == ["vod:v1"]
    assert "VOD v1 is already being downloaded, skipping" in [
        r.getMessage() for r in logs.records
    ]

    await sched.shutdown()
    assert rt.active_vods == set()


async def test_recording_task_failure_is_logged_with_its_name(
    make_runtime, monkeypatch, logs
):
    async def broken(*args):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(scheduler_module, "record_live", broken)
    rt = make_runtime()
    rt.resolver.streams = [URLS]
    sched = scheduler(rt, LIVE_CONFIG)
    await sched.run_round()
    await asyncio.gather(*sched.recordings, return_exceptions=True)
    await asyncio.sleep(0)

    [record] = [r for r in logs.records if r.getMessage().startswith("Recording task")]
    assert record.getMessage() == "Recording task record:alice failed: kaboom"
    assert record.levelno == logging.ERROR
