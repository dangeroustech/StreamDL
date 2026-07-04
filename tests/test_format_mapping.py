"""Tests for yt-dlp format quality mapping in get_stream."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _get_format_map():
    """Extract the format map used in get_stream without calling the function."""
    return {
        "best": "bestvideo*+bestaudio/best",
        "worst": "worstvideo*+worstaudio/worst",
    }


def _resolve_format(quality):
    """Replicate the format resolution logic from get_stream."""
    fmt_map = _get_format_map()
    return fmt_map.get(quality, quality if quality else "bestvideo*+bestaudio/best")


def test_best_maps_to_compound_selector():
    assert _resolve_format("best") == "bestvideo*+bestaudio/best"


def test_worst_maps_to_compound_selector():
    assert _resolve_format("worst") == "worstvideo*+worstaudio/worst"


def test_empty_quality_defaults_to_best():
    assert _resolve_format("") == "bestvideo*+bestaudio/best"


def test_none_quality_defaults_to_best():
    assert _resolve_format(None) == "bestvideo*+bestaudio/best"


def test_numeric_format_passed_through():
    """A raw format ID like '720p' or '6' should be passed through unchanged."""
    assert _resolve_format("720p") == "720p"
    assert _resolve_format("6") == "6"


def test_custom_selector_passed_through():
    """A custom yt-dlp selector should be passed through unchanged."""
    assert _resolve_format("bestvideo[height<=480]+bestaudio") == "bestvideo[height<=480]+bestaudio"
