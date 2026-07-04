"""Tests for _extract_urls in streamdl_proto_srv.py."""

import sys
import os

# Add project root to path so we can import the server module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from streamdl_proto_srv import _extract_urls


def test_combined_format_returns_url_with_no_audio():
    """When yt-dlp returns a single combined format (video+audio in one URL)."""
    info = {"url": "https://example.com/stream.m3u8"}
    video, audio = _extract_urls(info)
    assert video == "https://example.com/stream.m3u8"
    assert audio == ""


def test_split_formats_returns_video_and_audio():
    """When yt-dlp returns separate video and audio formats (e.g. newer extractors)."""
    info = {
        "requested_formats": [
            {
                "url": "https://cdn.example.com/chunklist_video.m3u8",
                "vcodec": "avc1.4d4020",
                "acodec": "none",
            },
            {
                "url": "https://cdn.example.com/chunklist_audio.m3u8",
                "vcodec": "none",
                "acodec": "mp4a.40.2",
            },
        ]
    }
    video, audio = _extract_urls(info)
    assert video == "https://cdn.example.com/chunklist_video.m3u8"
    assert audio == "https://cdn.example.com/chunklist_audio.m3u8"


def test_split_formats_audio_none_vcodec():
    """Audio entry may have vcodec missing entirely rather than set to 'none'."""
    info = {
        "requested_formats": [
            {
                "url": "https://cdn.example.com/video.m3u8",
                "vcodec": "avc1.4d4020",
                "acodec": "none",
            },
            {
                "url": "https://cdn.example.com/audio.m3u8",
                "acodec": "mp4a.40.2",
            },
        ]
    }
    video, audio = _extract_urls(info)
    assert video == "https://cdn.example.com/video.m3u8"
    assert audio == "https://cdn.example.com/audio.m3u8"


def test_top_level_url_takes_precedence():
    """If both top-level url and requested_formats exist, prefer top-level."""
    info = {
        "url": "https://example.com/combined.m3u8",
        "requested_formats": [
            {"url": "https://cdn.example.com/video.m3u8", "vcodec": "avc1"},
            {"url": "https://cdn.example.com/audio.m3u8", "vcodec": "none"},
        ],
    }
    video, audio = _extract_urls(info)
    assert video == "https://example.com/combined.m3u8"
    assert audio == ""


def test_empty_info_returns_empty():
    """Empty info dict returns empty strings."""
    video, audio = _extract_urls({})
    assert video == ""
    assert audio == ""


def test_single_video_only_format():
    """When only a video format exists with no audio counterpart."""
    info = {
        "requested_formats": [
            {
                "url": "https://cdn.example.com/video.m3u8",
                "vcodec": "avc1.4d4020",
                "acodec": "none",
            },
        ]
    }
    video, audio = _extract_urls(info)
    assert video == "https://cdn.example.com/video.m3u8"
    assert audio == ""
