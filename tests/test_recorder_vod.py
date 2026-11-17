import asyncio

import pytest
from helpers import ffmpeg_runs, wait_for_glob

from streamdl.ffmpeg import build_vod_args
from streamdl.recorder import record_vod
from streamdl.resolver import VodInfo
from streamdl.vod_db import VodDB

URL = "https://vod.example/v.m3u8"


@pytest.fixture
def db(tmp_path):
    database = VodDB(str(tmp_path / "data" / "streamdl.db"))
    yield database
    database.close()


def claim(db, vod):
    assert db.claim(vod.id, "bob", "twitch.tv", vod.title, 600)


async def test_success_moves_file_and_marks_completed(
    make_runtime, db, ffmpeg_log, tmp_path
):
    rt = make_runtime()
    vod = VodInfo("v123", "My Title", "20260101", 120)
    claim(db, vod)

    await record_vod(rt, "bob", "twitch.tv", vod, URL, "", db)

    assert (tmp_path / "out" / "bob_vod_v123_My Title.mp4").exists()
    assert db.status("v123") == "completed"
    [run] = ffmpeg_runs(ffmpeg_log)
    assert (
        run
        == build_vod_args(URL, str(tmp_path / "dl" / "bob_vod_v123_My Title.mp4"))[1:]
    )
    assert rt.progress.snapshot() == []


async def test_filename_without_title(make_runtime, db, tmp_path):
    rt = make_runtime()
    vod = VodInfo("v1", "")
    claim(db, vod)
    await record_vod(rt, "bob", "twitch.tv", vod, URL, "", db)
    assert (tmp_path / "out" / "bob_vod_v1.mp4").exists()


async def test_failure_marks_failed_and_adds_a_notice(make_runtime, db, monkeypatch):
    monkeypatch.setenv("FAKE_FFMPEG_EXITS", "1")
    rt = make_runtime()
    vod = VodInfo("v123", "T")
    claim(db, vod)

    await record_vod(rt, "bob", "twitch.tv", vod, URL, "", db)

    assert db.status("v123") == "failed"
    assert [n.message for n in rt.notices.pending()] == [
        "VOD v123 recording failed: exit status 1"
    ]


async def test_cancel_leaves_the_vod_downloading(
    make_runtime, db, monkeypatch, tmp_path
):
    monkeypatch.setenv("FAKE_FFMPEG_BLOCK", "1")
    rt = make_runtime()
    vod = VodInfo("v123", "T")
    claim(db, vod)
    task = asyncio.create_task(record_vod(rt, "bob", "twitch.tv", vod, URL, "", db))
    await wait_for_glob(tmp_path / "dl", "*.mp4.ready")

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert db.status("v123") == "downloading"
    assert list((tmp_path / "dl").glob("*.finalized"))


async def test_post_script_gets_vod_type(make_runtime, db, tmp_path):
    rt = make_runtime()
    marker = tmp_path / "hook.txt"
    hook = tmp_path / "hook.sh"
    hook.write_text(f'#!/bin/sh\necho "$STREAMDL_TYPE|$STREAMDL_USER" > {marker}\n')
    hook.chmod(0o755)
    vod = VodInfo("v9", "T")
    claim(db, vod)

    await record_vod(rt, "bob", "twitch.tv", vod, URL, str(hook), db)
    await rt.wait_for_post_scripts()

    assert marker.read_text() == "vod|bob\n"


async def test_progress_knows_the_total_duration(
    make_runtime, db, monkeypatch, tmp_path
):
    monkeypatch.setenv("FAKE_FFMPEG_BLOCK", "1")
    rt = make_runtime()
    vod = VodInfo("v5", "T", duration_seconds=120)
    claim(db, vod)
    task = asyncio.create_task(record_vod(rt, "bob", "twitch.tv", vod, URL, "", db))
    await wait_for_glob(tmp_path / "dl", "*.mp4.ready")
    for _ in range(100):
        p = rt.progress.get("vod:bob:v5")
        if p and p.percent is not None:
            break
        await asyncio.sleep(0.02)
    assert p.total_duration == 120
    assert p.percent == pytest.approx(2 / 120 * 100)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
