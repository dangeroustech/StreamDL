"""Tests for user-facing GetStream error and warning messages."""

import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamdl_proto_srv as srv


def _request(site="twitch.tv", user="testuser", quality="1080p"):
    req = MagicMock()
    req.site = site
    req.user = user
    req.quality = quality
    return req


@patch("streamdl_proto_srv.Streamlink")
def test_streamlink_quality_mismatch_includes_available_keys(mock_streamlink):
    session = mock_streamlink.return_value
    session.streams.return_value = {"720p": MagicMock(url="http://example/720p")}

    res = srv.get_stream(_request(quality="1080p60"))

    assert res["error"] == 414
    assert "1080p60" in res["message"]
    assert "720p" in res["message"]


@patch("streamdl_proto_srv.Streamlink")
def test_streamlink_offline_user_message(mock_streamlink):
    session = mock_streamlink.return_value
    session.streams.return_value = None

    res = srv.get_stream(_request())

    assert res["error"] == 404
    assert "testuser" in res["message"]
    assert "No live streams" in res["message"]


@patch("streamdl_proto_srv.yt_dlp.YoutubeDL")
@patch("streamdl_proto_srv.Streamlink")
def test_ytdlp_offline_message(mock_streamlink, mock_ydl):
    session = mock_streamlink.return_value
    session.streams.side_effect = srv.NoPluginError("no plugin")
    ydl_instance = mock_ydl.return_value.__enter__.return_value
    ydl_instance.extract_info.side_effect = srv.DownloadError(
        "ERROR: The channel is currently offline"
    )

    res = srv.get_stream(_request(site="kick.com", user="offlineuser"))

    assert res["error"] == 450
    assert "offlineuser" in res["message"]
    assert "offline" in res["message"].lower()


@patch("streamdl_proto_srv.yt_dlp.YoutubeDL")
@patch("streamdl_proto_srv.Streamlink")
def test_ytdlp_format_fallback_sets_warning(mock_streamlink, mock_ydl):
    session = mock_streamlink.return_value
    session.streams.side_effect = srv.NoPluginError("no plugin")
    ydl_instance = mock_ydl.return_value.__enter__.return_value
    ydl_instance.extract_info.side_effect = [
        srv.DownloadError("ERROR: Requested format is not available"),
        {"url": "http://example/video", "requested_formats": None},
    ]

    res = srv.get_stream(_request(site="kick.com", quality="worst"))

    assert "error" not in res
    assert res["url"] == "http://example/video"
    assert "worst" in res["warning"]
    assert "default selection" in res["warning"]
