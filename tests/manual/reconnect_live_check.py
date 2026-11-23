"""Manual check: a live Twitch recording that drops is joined into one file.

Runs inside the StreamDL image against a live channel:

    python reconnect_live_check.py <twitch channel> <work dir>

It records three parts of about 10 seconds each. Each part is ended by
SIGTERMing streamlink, which is a real clean drop: FFmpeg sees the end of its
input and exits 0. The first two reconnect checks use the real resolver; after
that the channel is reported offline, so the session ends and the parts are
joined. Exits non-zero if the result isn't one joined file of about 30s that was
moved and handed to the hook.
"""

import asyncio
import json
import os
import signal
import subprocess  # nosec B404 - manual check running ffprobe
import sys

from streamdl.recorder import record_live
from streamdl.resolver import LibraryResolver, Offline
from streamdl.runtime import Runtime
from streamdl.settings import ReconnectOptions, Settings

PART_SECONDS = 10
PARTS = 3


class LiveForTwoLookups:
    """The real resolver for the first two lookups, then Offline."""

    def __init__(self, real):
        self.real = real
        self.calls = 0

    async def stream(self, site, user, quality):
        self.calls += 1
        if self.calls > PARTS - 1:
            raise Offline(f"Channel '{user}' is offline (simulated)")
        return await self.real.stream(site, user, quality)

    async def vods(self, site, user, limit):
        raise NotImplementedError

    def close(self):
        self.real.close()


def streamlink_pids():
    pids = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/cmdline", "rb") as f:
                argv = f.read().split(b"\0")
        except OSError:
            continue
        if b"streamlink" in argv and b"--stdout" in argv:
            pids.append(int(entry))
    return pids


async def drop_streamlink(times):
    for _ in range(times):
        await asyncio.sleep(PART_SECONDS)
        for pid in streamlink_pids():
            print(f"dropping streamlink (pid {pid})", flush=True)
            os.kill(pid, signal.SIGTERM)


def duration(path):
    out = subprocess.run(  # nosec B603 B607
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json"]
        + [path],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return float(json.loads(out)["format"]["duration"])


async def main(channel, work):
    dl, out = os.path.join(work, "dl"), os.path.join(work, "out")
    marker = os.path.join(work, "hook.txt")
    hook = os.path.join(work, "hook.sh")
    with open(hook, "w") as f:
        f.write(f'#!/bin/sh\necho "$1" >> {marker}\n')
    os.chmod(hook, 0o755)  # nosec B103 - the test hook must be executable

    real = LibraryResolver()
    settings = Settings(
        out_dir=dl,
        move_dir=out,
        data_dir=os.path.join(work, "data"),
        reconnect=ReconnectOptions(window=6, interval=2),
    )
    rt = Runtime(settings=settings, resolver=LiveForTwoLookups(real))
    initial = await real.stream("twitch.tv", channel, "best")
    rt.active.add(channel)
    dropper = asyncio.create_task(drop_streamlink(PARTS))
    try:
        await asyncio.wait_for(
            record_live(rt, channel, "twitch.tv", "best", initial, hook), 120
        )
    finally:
        dropper.cancel()
        rt.resolver.close()
    await rt.wait_for_post_scripts()

    moved = sorted(os.listdir(out)) if os.path.isdir(out) else []
    left = sorted(os.listdir(dl)) if os.path.isdir(dl) else []
    hooks = open(marker).read().splitlines() if os.path.exists(marker) else []
    result = {"moved": moved, "left_in_dl": left, "hook_calls": hooks}
    ok = len(moved) == 1 and not [n for n in left if n.endswith(".mp4")]
    if ok:
        result["duration"] = duration(os.path.join(out, moved[0]))
        ok = 20 <= result["duration"] <= 45 and len(hooks) == 1
    result["ok"] = ok
    print(json.dumps(result, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1], sys.argv[2])))
