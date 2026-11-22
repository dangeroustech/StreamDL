"""Test doubles shared by the recorder and scheduler tests."""

import asyncio
import json
import threading
from pathlib import Path

FAKE_FFMPEG = str(Path(__file__).parent / "fakes" / "ffmpeg")
FAKE_STREAMLINK = str(Path(__file__).parent / "fakes" / "streamlink")
FAKE_FFPROBE = str(Path(__file__).parent / "fakes" / "ffprobe")


class FakeResolver:
    """Scripted resolver. Each queue holds results to return or exceptions to raise,
    consumed in order; the last entry repeats."""

    def __init__(self):
        self.streams = []
        self.vod_lists = []
        self.stream_calls = []
        self.vod_calls = []

    async def stream(self, site, user, quality):
        self.stream_calls.append((site, user, quality))
        return self._next(self.streams)

    async def vods(self, site, user, limit):
        self.vod_calls.append((site, user, limit))
        return self._next(self.vod_lists)

    def close(self):
        pass

    @staticmethod
    def _next(queue):
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, BaseException):
            raise item
        return item


class FakeSleep:
    """Records requested sleeps and returns at once (still yielding to the loop).

    It also keeps a fake clock: each sleep moves `now` forward, and `clock` reads it.
    """

    def __init__(self):
        self.calls = []
        self.now = 0.0

    async def __call__(self, seconds):
        self.calls.append(seconds)
        self.now += seconds
        await asyncio.sleep(0)

    def clock(self):
        return self.now


class BlockingMove:
    """Wraps move_file so a test can hold a move in progress until release is set."""

    def __init__(self, move):
        self.move = move
        self.started = threading.Event()
        self.release = threading.Event()

    def __call__(self, old_path, new_path):
        self.started.set()
        assert self.release.wait(5), "move was never released"
        self.move(old_path, new_path)

    async def wait_started(self):
        assert await asyncio.to_thread(self.started.wait, 5), "move never started"


def ffmpeg_runs(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines()]


def streamlink_runs(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines()]


async def wait_for_glob(directory, pattern, timeout=5.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if directory.exists():
            matches = sorted(directory.rglob(pattern))
            if matches:
                return matches[0]
        await asyncio.sleep(0.02)
    raise AssertionError(f"nothing matching {pattern} appeared in {directory}")
