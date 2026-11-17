import asyncio
import logging
import sys
import tracemalloc

from helpers import FakeResolver, wait_for_glob

from streamdl.config import ConfigLoader, load_config
from streamdl.resolver import Offline, StreamURLs
from streamdl.scheduler import Scheduler

LIVE_CONFIG = "- site: twitch.tv\n  channels:\n  - name: alice\n    quality: best\n"
URLS = StreamURLs("https://video.example/live.m3u8")


def scheduler(rt, text):
    path = rt.settings.config_path
    path.write_text(text)
    return Scheduler(rt, ConfigLoader(path, load_config(path)))


async def test_stops_promptly_while_waiting_for_the_next_round(make_runtime):
    rt = make_runtime(tick_seconds=3600)
    stop = asyncio.Event()
    task = asyncio.create_task(scheduler(rt, "[]\n").run(stop))
    await asyncio.sleep(0.1)
    stop.set()
    await asyncio.wait_for(task, 1)


async def test_stops_a_round_in_progress(make_runtime):
    class Hanging(FakeResolver):
        async def stream(self, site, user, quality):
            await asyncio.Event().wait()

    rt = make_runtime()
    rt.resolver = Hanging()
    stop = asyncio.Event()
    task = asyncio.create_task(scheduler(rt, LIVE_CONFIG).run(stop))
    await asyncio.sleep(0.1)
    stop.set()
    await asyncio.wait_for(task, 1)


async def test_shutdown_sends_sigint_to_recordings(make_runtime, monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_FFMPEG_BLOCK", "1")
    rt = make_runtime(tick_seconds=3600)
    rt.resolver.streams = [URLS]
    sched = scheduler(rt, LIVE_CONFIG)
    stop = asyncio.Event()
    task = asyncio.create_task(sched.run(stop))
    await wait_for_glob(tmp_path / "dl", "*.mp4.ready")

    stop.set()
    await asyncio.wait_for(task, 5)

    assert list((tmp_path / "dl").glob("*.finalized"))
    assert sched.recordings == set()


class ClosingResolver(FakeResolver):
    closed = False

    def close(self):
        self.closed = True


async def test_shutdown_waits_for_post_scripts(make_runtime, tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="streamdl")
    started, done = tmp_path / "started", tmp_path / "done"
    hook = tmp_path / "hook.sh"
    hook.write_text(f"#!/bin/sh\ntouch {started}\nsleep 0.5\ntouch {done}\n")
    hook.chmod(0o755)
    rt = make_runtime(tick_seconds=3600)
    rt.resolver = ClosingResolver()
    rt.resolver.streams = [URLS]
    sched = scheduler(
        rt, LIVE_CONFIG.replace("  channels:", f"  post_script: {hook}\n  channels:")
    )
    stop = asyncio.Event()
    task = asyncio.create_task(sched.run(stop))
    await wait_for_glob(tmp_path, "started")

    stop.set()
    await asyncio.wait_for(task, 5)

    assert done.exists()
    assert "Waiting for 1 post-script(s) to finish..." in caplog.text
    assert rt.resolver.closed


async def test_a_failing_round_does_not_stop_the_loop(make_runtime, caplog):
    caplog.set_level(logging.ERROR, logger="streamdl")
    stop = asyncio.Event()

    class Flaky(FakeResolver):
        async def stream(self, site, user, quality):
            if len(self.stream_calls) == 1:
                stop.set()
            return await super().stream(site, user, quality)

    rt = make_runtime(tick_seconds=0)
    rt.resolver = Flaky()
    rt.resolver.streams = [RuntimeError("boom"), Offline("offline")]
    await asyncio.wait_for(scheduler(rt, LIVE_CONFIG).run(stop), 5)

    assert "Round failed: boom" in caplog.text
    assert len(rt.resolver.stream_calls) == 2


def _stack_depth():
    depth, frame = 0, sys._getframe()
    while frame is not None:
        depth += 1
        frame = frame.f_back
    return depth


async def test_ten_thousand_rounds_keep_the_stack_and_memory_flat(make_runtime):
    # Guards against the 2019 RecursionError: each round must be a loop iteration,
    # not a nested call, and nothing may accumulate per round.
    rounds = 10_000
    stop = asyncio.Event()
    samples = {}

    class Counting:
        calls = 0

        async def stream(self, site, user, quality):
            n = self.calls
            self.calls += 1
            if n == 1000:
                tracemalloc.start()
            if n in (100, rounds - 1):
                samples[n] = (_stack_depth(), len(asyncio.all_tasks()))
            if n == rounds - 1:
                samples["memory"] = tracemalloc.get_traced_memory()[0]
                tracemalloc.stop()
                stop.set()
            raise Offline("No live streams found for 'alice' on twitch.tv")

        async def vods(self, site, user, limit):
            raise AssertionError("no VOD channels configured")

    async def no_sleep(seconds):
        await asyncio.sleep(0)

    rt = make_runtime(tick_seconds=0, batch_seconds=0)
    rt.resolver = Counting()
    rt.sleep = no_sleep
    await asyncio.wait_for(scheduler(rt, LIVE_CONFIG).run(stop), 120)

    assert rt.resolver.calls == rounds
    assert samples[100] == samples[rounds - 1]
    assert samples["memory"] < 1_000_000
