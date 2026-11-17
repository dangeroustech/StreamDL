"""Test doubles shared by the recorder and scheduler tests."""

import asyncio
import json
from pathlib import Path

FAKE_FFMPEG = str(Path(__file__).parent / "fakes" / "ffmpeg")


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

    @staticmethod
    def _next(queue):
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, BaseException):
            raise item
        return item


class FakeSleep:
    """Records requested sleeps and returns at once (still yielding to the loop)."""

    def __init__(self):
        self.calls = []

    async def __call__(self, seconds):
        self.calls.append(seconds)
        await asyncio.sleep(0)


def ffmpeg_runs(log_path):
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
