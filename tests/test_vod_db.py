import sqlite3

import pytest

from streamdl.vod_db import VodDB

STALE = 600.0


@pytest.fixture
def db(tmp_path):
    database = VodDB(str(tmp_path / "test.db"))
    yield database
    database.close()


def test_init_creates_file_and_parents(tmp_path):
    path = tmp_path / "sub" / "test.db"
    VodDB(str(path)).close()
    assert path.exists()


def test_full_lifecycle(db):
    assert db.claim("12345", "testuser", "twitch.tv", "Title", STALE)
    assert not db.claim("12345", "testuser", "twitch.tv", "Title", STALE)
    db.mark_completed("12345")
    assert not db.claim("12345", "testuser", "twitch.tv", "Title", STALE)


def test_failed_vod_is_retried(db):
    assert db.claim("12345", "u", "twitch.tv", "Title", STALE)
    db.mark_failed("12345")
    assert db.claim("12345", "u", "twitch.tv", "Title", STALE)


def test_stale_download_is_retried(db):
    assert db.claim("12345", "u", "twitch.tv", "Title", STALE)
    assert db.claim("12345", "u", "twitch.tv", "Title", 0)


def test_different_vods_are_independent(db):
    for vod_id in ("111", "222"):
        assert db.claim(vod_id, "u", "twitch.tv", "T", STALE)
        db.mark_completed(vod_id)
    assert not db.claim("111", "u", "twitch.tv", "T", STALE)
    assert not db.claim("222", "u", "twitch.tv", "T", STALE)
    assert db.claim("333", "u", "twitch.tv", "T", STALE)


def test_marking_an_unknown_vod_raises(db):
    with pytest.raises(LookupError):
        db.mark_completed("nope")
    with pytest.raises(LookupError):
        db.mark_failed("nope")


def test_status(db):
    assert db.status("1") is None
    db.claim("1", "u", "twitch.tv", "T", STALE)
    assert db.status("1") == "downloading"
    db.mark_completed("1")
    assert db.status("1") == "completed"


def test_opens_a_v3_database(tmp_path):
    path = tmp_path / "streamdl.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE downloaded_vods (vod_id TEXT PRIMARY KEY, user TEXT NOT NULL, "
        "site TEXT NOT NULL, title TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'downloading', "
        "started_at TEXT NOT NULL, completed_at TEXT)"
    )
    conn.execute(
        "INSERT INTO downloaded_vods VALUES ('v9', 'u', 'twitch.tv', 'Old', 'completed', "
        "'2026-01-01T00:00:00Z', '2026-01-01T01:00:00Z')"
    )
    conn.commit()
    conn.close()
    db = VodDB(str(path))
    assert not db.claim("v9", "u", "twitch.tv", "Old", STALE)
    db.close()
