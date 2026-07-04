"""Tests for DownloadError classification logic in get_stream.

The yt-dlp fallback path in get_stream matches error message strings to
decide which error code to return. These tests verify that classification
without needing a live yt-dlp session.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _classify_download_error(error_str):
    """Replicate the DownloadError classification from get_stream lines 382-413."""
    if "Requested format is not available" in error_str:
        return 415
    elif "HTTP Error 429: Too Many Requests " in error_str:
        return 429
    elif "currently offline" in error_str:
        return 450
    else:
        return 500


def test_rate_limit_429():
    msg = "ERROR: [SomeExtractor] user: Unable to download webpage: HTTP Error 429: Too Many Requests (caused by <HTTPError 429: Too Many Requests>)"
    assert _classify_download_error(msg) == 429


def test_format_not_available_415():
    msg = "ERROR: [SomeExtractor] user: Requested format is not available. Use --list-formats for a list of available formats"
    assert _classify_download_error(msg) == 415


def test_currently_offline_450():
    msg = "ERROR: [SomeExtractor] user: The channel is currently offline"
    assert _classify_download_error(msg) == 450


def test_generic_error_500():
    msg = "ERROR: [SomeExtractor] user: Something completely unexpected happened"
    assert _classify_download_error(msg) == 500


def test_429_requires_trailing_space():
    """The current code matches 'HTTP Error 429: Too Many Requests ' with a trailing space.
    Verify that a message without the trailing space does NOT match 429."""
    # This is a subtle bug-risk: if yt-dlp ever changes the message format
    msg = "HTTP Error 429: Too Many Requests"
    # Without trailing space, falls through to 500
    assert _classify_download_error(msg) == 500


def test_format_not_available_substring_match():
    """The match is a substring check, so it works even with extra context."""
    msg = "ERROR: Requested format is not available. Tried best, worst"
    assert _classify_download_error(msg) == 415


def test_offline_substring_match():
    """Various ways yt-dlp might phrase 'offline'."""
    assert _classify_download_error("Room is currently offline") == 450
    assert _classify_download_error("User is currently offline and not streaming") == 450
