import asyncio
import os
import signal
import time

import pytest

from streamdl import runtime
from streamdl.post_script import PostScriptError, run_post_script


def write_script(path, body, mode=0o755):
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(mode)
    return str(path)


async def test_success_passes_context(tmp_path):
    marker = tmp_path / "marker.txt"
    script = write_script(
        tmp_path / "hook.sh",
        f'echo "$STREAMDL_FILE|$STREAMDL_USER|$STREAMDL_SITE|$STREAMDL_TYPE" > {marker}\n',
    )
    await run_post_script(
        script,
        "/data/complete/user_2026.mp4",
        "testuser",
        "twitch.tv",
        "live",
        timeout=10,
    )
    assert (
        marker.read_text() == "/data/complete/user_2026.mp4|testuser|twitch.tv|live\n"
    )


async def test_file_path_is_the_first_argument(tmp_path):
    marker = tmp_path / "arg.txt"
    script = write_script(tmp_path / "checkarg.sh", f'echo "$1" > {marker}\n')
    await run_post_script(
        script, "/data/complete/test.mp4", "u", "twitch.tv", "vod", timeout=10
    )
    assert marker.read_text() == "/data/complete/test.mp4\n"


async def test_empty_path_is_a_noop():
    await run_post_script("", "/data/file.mp4", "u", "twitch.tv", "live", timeout=10)


async def test_missing_script():
    with pytest.raises(PostScriptError, match="not found"):
        await run_post_script(
            "/nonexistent/script.sh", "/f.mp4", "u", "twitch.tv", "live", timeout=10
        )


async def test_failing_script(tmp_path):
    script = write_script(tmp_path / "fail.sh", "exit 1\n")
    with pytest.raises(PostScriptError, match="exit status 1"):
        await run_post_script(script, "/f.mp4", "u", "twitch.tv", "vod", timeout=10)


async def test_not_executable(tmp_path):
    script = write_script(tmp_path / "noexec.sh", "echo hi\n", mode=0o644)
    with pytest.raises(PostScriptError, match="not executable"):
        await run_post_script(script, "/f.mp4", "u", "twitch.tv", "live", timeout=10)


async def _gone(pid, wait=3.0):
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        await asyncio.sleep(0.05)
    return False


async def test_timeout_kills_the_whole_process_group(tmp_path):
    pidfile = tmp_path / "child.pid"
    script = write_script(
        tmp_path / "slow.sh", f"sleep 30 &\necho $! > {pidfile}\nwait\n"
    )
    started = time.monotonic()
    with pytest.raises(PostScriptError, match="timed out"):
        await run_post_script(script, "/f.mp4", "u", "twitch.tv", "live", timeout=2)
    assert time.monotonic() - started < 6
    assert await _gone(int(pidfile.read_text()))


async def test_cancel_kills_the_whole_process_group(tmp_path):
    pidfile = tmp_path / "pids"
    script = write_script(
        tmp_path / "slow.sh",
        f'sleep 30 &\necho "$$ $!" > {pidfile}.tmp\nmv {pidfile}.tmp {pidfile}\nwait\n',
    )
    task = asyncio.create_task(
        run_post_script(script, "/f.mp4", "u", "twitch.tv", "live", timeout=60)
    )
    deadline = time.monotonic() + 5
    while not pidfile.exists() and time.monotonic() < deadline:
        await asyncio.sleep(0.05)
    leader, child = map(int, pidfile.read_text().split())
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await _gone(child)
    assert await _gone(leader)


async def _instant_hook(*args, **kwargs):
    pass


def _spawn_a_finished_hook(make_runtime, monkeypatch):
    """Spawn a hook that finishes in its first step. After the sleep(0) it is done,
    but its clean-up callback is still queued behind the caller."""
    monkeypatch.setattr(runtime, "run_post_script", _instant_hook)
    rt = make_runtime()
    rt.spawn_post_script("/hook.sh", "/data/f.mp4", "bob", "twitch.tv", "vod")
    return rt


async def test_waiting_just_after_a_hook_finishes_returns(make_runtime, monkeypatch):
    rt = _spawn_a_finished_hook(make_runtime, monkeypatch)
    await asyncio.sleep(0)

    # A spin that never yields can't be stopped by wait_for, so SIGALRM ends it.
    def spun(signum, frame):
        raise AssertionError("wait_for_post_scripts spun without yielding")

    old_handler = signal.signal(signal.SIGALRM, spun)
    signal.setitimer(signal.ITIMER_REAL, 5)
    try:
        await asyncio.wait_for(rt.wait_for_post_scripts(), 5)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)


async def test_a_finished_hook_is_not_counted_as_running(make_runtime, monkeypatch):
    rt = _spawn_a_finished_hook(make_runtime, monkeypatch)
    assert rt.running_post_scripts == 1
    await asyncio.sleep(0)
    assert rt.running_post_scripts == 0
