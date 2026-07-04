"""Tests for VOD entry parsing logic from get_vods."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _parse_vod_entries(entries):
    """Replicate the VOD entry parsing from get_vods lines 253-264."""
    vods = []
    for entry in entries:
        if entry is None:
            continue
        vod = {
            "id": str(entry.get("id", "")),
            "title": entry.get("title", ""),
            "published_at": entry.get("upload_date", ""),
            "duration_seconds": int(entry.get("duration", 0) or 0),
        }
        if vod["id"]:
            vods.append(vod)
    return vods


def test_normal_entries():
    entries = [
        {"id": "12345", "title": "Stream VOD", "upload_date": "20260414", "duration": 3600},
        {"id": "12346", "title": "Another VOD", "upload_date": "20260413", "duration": 7200},
    ]
    vods = _parse_vod_entries(entries)
    assert len(vods) == 2
    assert vods[0]["id"] == "12345"
    assert vods[0]["title"] == "Stream VOD"
    assert vods[0]["published_at"] == "20260414"
    assert vods[0]["duration_seconds"] == 3600


def test_none_entries_filtered():
    entries = [None, {"id": "12345", "title": "Valid"}, None]
    vods = _parse_vod_entries(entries)
    assert len(vods) == 1
    assert vods[0]["id"] == "12345"


def test_empty_id_filtered():
    entries = [{"id": "", "title": "No ID"}, {"title": "Missing ID key"}]
    vods = _parse_vod_entries(entries)
    assert len(vods) == 0


def test_numeric_id_converted_to_string():
    entries = [{"id": 99999, "title": "Numeric ID"}]
    vods = _parse_vod_entries(entries)
    assert vods[0]["id"] == "99999"


def test_missing_duration_defaults_to_zero():
    entries = [{"id": "1", "title": "No Duration"}]
    vods = _parse_vod_entries(entries)
    assert vods[0]["duration_seconds"] == 0


def test_none_duration_defaults_to_zero():
    """yt-dlp sometimes returns None for duration."""
    entries = [{"id": "1", "title": "None Duration", "duration": None}]
    vods = _parse_vod_entries(entries)
    assert vods[0]["duration_seconds"] == 0


def test_float_duration_truncated():
    entries = [{"id": "1", "title": "Float", "duration": 3661.5}]
    vods = _parse_vod_entries(entries)
    assert vods[0]["duration_seconds"] == 3661


def test_missing_optional_fields_default_empty():
    entries = [{"id": "1"}]
    vods = _parse_vod_entries(entries)
    assert vods[0]["title"] == ""
    assert vods[0]["published_at"] == ""
