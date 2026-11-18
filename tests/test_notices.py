import logging

import pytest

from streamdl.notices import Notice, NoticeBuffer

QUALITY = "Requested quality 1080p60 unavailable"


@pytest.fixture
def records(caplog):
    caplog.set_level(logging.DEBUG, logger="streamdl")
    return caplog


def messages(caplog):
    return [r.getMessage() for r in caplog.records]


def test_flush_order_and_dedup(records):
    nb = NoticeBuffer()
    nb.warn("day9tv", QUALITY)
    nb.warn("day9tv", QUALITY)
    nb.flush(60)

    msgs = messages(records)
    assert msgs[0] == "Waiting 60s until next check..."
    assert msgs[1] == "--- notices ---"
    assert msgs.count(f"[day9tv] {QUALITY}") == 1

    records.clear()
    nb.warn("day9tv", QUALITY)
    nb.flush(60)
    assert not any("[day9tv]" in m for m in messages(records))

    nb.clear_channel("day9tv")
    records.clear()
    nb.warn("day9tv", QUALITY)
    nb.flush(60)
    assert f"[day9tv] {QUALITY}" in messages(records)


def test_error_level(records):
    nb = NoticeBuffer()
    nb.error("kickuser", "Channel is offline")
    nb.flush(5)
    notice = [
        r for r in records.records if r.getMessage() == "[kickuser] Channel is offline"
    ]
    assert notice and notice[0].levelno == logging.ERROR


def test_warning_level(records):
    nb = NoticeBuffer()
    nb.warn("alice", "something")
    nb.flush(5)
    notice = [r for r in records.records if r.getMessage() == "[alice] something"]
    assert notice[0].levelno == logging.WARNING


def test_empty_input_ignored(records):
    nb = NoticeBuffer()
    nb.warn("", "message")
    nb.warn("channel", "")
    nb.warn("  ", "  ")
    nb.flush(1)
    assert "--- notices ---" not in messages(records)


def test_clear_channel_only_affects_that_channel(records):
    nb = NoticeBuffer()
    nb.warn("day9", "x")
    nb.warn("day9tv", "x")
    nb.flush(1)
    nb.clear_channel("day9")
    nb.warn("day9", "x")
    nb.warn("day9tv", "x")
    assert nb.pending() == [Notice(logging.WARNING, "day9", "x")]


def test_pending_lists_unflushed_notices():
    nb = NoticeBuffer()
    nb.warn("a", "b")
    assert nb.pending() == [Notice(logging.WARNING, "a", "b")]
    nb.flush(1)
    assert nb.pending() == []


def test_info_level(records):
    nb = NoticeBuffer()
    nb.info("alice", "Skipping pre-roll ads")
    nb.flush(5)
    notice = [
        r for r in records.records if r.getMessage() == "[alice] Skipping pre-roll ads"
    ]
    assert notice[0].levelno == logging.INFO
