import io
import logging
import sys
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
import urllib3.util.url
import yt_dlp
from streamlink.exceptions import NoPluginError, PluginError
from streamlink.options import Options
from streamlink.session import Streamlink
from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.networking import Response
from yt_dlp.networking.exceptions import HTTPError, TransportError
from yt_dlp.utils import (
    DownloadError,
    ExtractorError,
    GeoRestrictedError,
    UnavailableVideoError,
    UserNotLive,
)

from streamdl import resolver
from streamdl.resolver import (
    FormatUnavailable,
    GeoRestricted,
    LibraryResolver,
    NotFound,
    Offline,
    QualityUnavailable,
    RateLimited,
    ResolverError,
    StreamURLs,
    VodInfo,
    extract_urls,
    get_stream,
    get_vods,
    is_twitch,
    parse_vod_entries,
    ytdlp_format,
)

FORMAT_UNAVAILABLE = "ERROR: Requested format is not available"


def wrapped(error, message=None):
    """A DownloadError carrying `error` the way YoutubeDL.extract_info raises it.

    yt-dlp passes on the error's own exc_info when it was raised while handling
    another exception (a network error, say), so exc_info[1] is that exception. It
    raises the DownloadError while handling `error`, which becomes its __context__.
    """
    try:
        try:
            raise error
        except Exception:
            exc_info = sys.exc_info()
            if getattr(error, "exc_info", None) and error.exc_info[0]:
                exc_info = error.exc_info
            raise DownloadError(message or f"ERROR: {error}", exc_info)
    except DownloadError as e:
        return e


def not_live(message):
    return ExtractorError(message, expected=True, ie="Chaturbate", video_id="bob")


def network_error():
    """An ExtractorError raised while handling a network error, as extractors do."""
    try:
        raise TransportError("Could not resolve host: chaturbate.com")
    except TransportError as e:
        return ExtractorError(
            "Unable to download webpage", cause=e, ie="Chaturbate", video_id="bob"
        )


# --- extract_urls ---------------------------------------------------------------


def test_combined_format_has_no_audio_url():
    assert extract_urls({"url": "https://example.com/stream.m3u8"}) == (
        "https://example.com/stream.m3u8",
        "",
    )


def test_split_formats_return_video_and_audio():
    info = {
        "requested_formats": [
            {
                "url": "https://cdn/video.m3u8",
                "vcodec": "avc1.4d4020",
                "acodec": "none",
            },
            {"url": "https://cdn/audio.m3u8", "vcodec": "none", "acodec": "mp4a.40.2"},
        ]
    }
    assert extract_urls(info) == ("https://cdn/video.m3u8", "https://cdn/audio.m3u8")


def test_audio_entry_may_omit_vcodec():
    info = {
        "requested_formats": [
            {
                "url": "https://cdn/video.m3u8",
                "vcodec": "avc1.4d4020",
                "acodec": "none",
            },
            {"url": "https://cdn/audio.m3u8", "acodec": "mp4a.40.2"},
        ]
    }
    assert extract_urls(info) == ("https://cdn/video.m3u8", "https://cdn/audio.m3u8")


def test_top_level_url_takes_precedence():
    info = {
        "url": "https://example.com/combined.m3u8",
        "requested_formats": [
            {"url": "https://cdn/video.m3u8", "vcodec": "avc1"},
            {"url": "https://cdn/audio.m3u8", "vcodec": "none"},
        ],
    }
    assert extract_urls(info) == ("https://example.com/combined.m3u8", "")


def test_empty_info():
    assert extract_urls({}) == ("", "")


def test_video_only_format():
    info = {
        "requested_formats": [
            {"url": "https://cdn/video.m3u8", "vcodec": "avc1", "acodec": "none"}
        ]
    }
    assert extract_urls(info) == ("https://cdn/video.m3u8", "")


# --- ytdlp_format ---------------------------------------------------------------


@pytest.mark.parametrize(
    "quality,expected",
    [
        ("best", "bestvideo*+bestaudio/best"),
        ("worst", "worstvideo*+worstaudio/worst"),
        ("", "bestvideo*+bestaudio/best"),
        (None, "bestvideo*+bestaudio/best"),
        ("720p", "720p"),
        ("6", "6"),
        ("bestvideo[height<=480]+bestaudio", "bestvideo[height<=480]+bestaudio"),
    ],
)
def test_ytdlp_format(quality, expected):
    assert ytdlp_format(quality) == expected


# --- parse_vod_entries ----------------------------------------------------------


def test_vod_entries():
    vods = parse_vod_entries(
        [
            {
                "id": "12345",
                "title": "Stream VOD",
                "upload_date": "20260414",
                "duration": 3600,
            },
            {
                "id": "12346",
                "title": "Another VOD",
                "upload_date": "20260413",
                "duration": 7200,
            },
        ]
    )
    assert vods[0] == VodInfo("12345", "Stream VOD", "20260414", 3600)
    assert len(vods) == 2


def test_vod_none_entries_skipped():
    assert [
        v.id for v in parse_vod_entries([None, {"id": "12345", "title": "Valid"}, None])
    ] == ["12345"]


def test_vod_empty_ids_skipped():
    assert (
        parse_vod_entries([{"id": "", "title": "No ID"}, {"title": "Missing ID key"}])
        == []
    )


def test_vod_numeric_id_becomes_string():
    assert parse_vod_entries([{"id": 99999}])[0].id == "99999"


def test_vod_missing_duration_is_zero():
    assert parse_vod_entries([{"id": "1"}])[0].duration_seconds == 0


def test_vod_none_duration_is_zero():
    assert parse_vod_entries([{"id": "1", "duration": None}])[0].duration_seconds == 0


def test_vod_float_duration_truncated():
    assert (
        parse_vod_entries([{"id": "1", "duration": 3661.5}])[0].duration_seconds == 3661
    )


def test_vod_missing_optional_fields():
    vod = parse_vod_entries([{"id": "1"}])[0]
    assert (vod.title, vod.published_at) == ("", "")


def test_vod_none_optional_fields_are_empty():
    vod = parse_vod_entries([{"id": "1", "title": None, "upload_date": None}])[0]
    assert (vod.title, vod.published_at) == ("", "")


# --- get_stream via streamlink --------------------------------------------------


@pytest.fixture
def session():
    with patch("streamdl.resolver.Streamlink") as cls:
        yield cls.return_value


@pytest.fixture
def ydl(session):
    session.streams.side_effect = NoPluginError("no plugin")
    with patch("streamdl.resolver.yt_dlp.YoutubeDL") as cls:
        yield cls.return_value.__enter__.return_value


def test_streamlink_selected_quality(session):
    session.streams.return_value = {"best": MagicMock(url="http://example/best")}
    assert get_stream("twitch.tv", "alice", "best") == StreamURLs("http://example/best")


def test_empty_quality_means_best(session):
    session.streams.return_value = {"best": MagicMock(url="http://example/best")}
    assert get_stream("twitch.tv", "alice", "").video == "http://example/best"


def test_streamlink_quality_mismatch_lists_available(session):
    session.streams.return_value = {"720p": MagicMock(url="http://example/720p")}
    with pytest.raises(QualityUnavailable) as err:
        get_stream("twitch.tv", "testuser", "1080p60")
    assert "1080p60" in str(err.value)
    assert "720p" in str(err.value)


def test_streamlink_offline(session):
    session.streams.return_value = None
    with pytest.raises(Offline) as err:
        get_stream("twitch.tv", "testuser", "best")
    assert "testuser" in str(err.value)
    assert "No live streams" in str(err.value)


def test_streamlink_plugin_error(session):
    session.streams.side_effect = PluginError("Unable to open URL")
    with pytest.raises(ResolverError, match="Plugin error: Unable to open URL"):
        get_stream("twitch.tv", "alice", "best")


def test_streamlink_gets_an_http_timeout():
    with patch("streamdl.resolver.Streamlink") as cls:
        cls.return_value.streams.return_value = {"best": MagicMock(url="u")}
        get_stream("twitch.tv", "alice", "best")
    cls.assert_called_once_with(options={"http-timeout": resolver.HTTP_TIMEOUT})


def test_streamlink_plugin_error_redacts_secrets(session, caplog):
    caplog.set_level(logging.DEBUG, logger="streamdl")
    session.streams.side_effect = PluginError(
        "Unable to open URL: https://usher.ttvnw.net/a.m3u8?sig=x&token=y (404)"
    )
    with pytest.raises(ResolverError) as err:
        get_stream("twitch.tv", "alice", "best")
    for text in (str(err.value), caplog.text):
        assert "sig=<redacted>&token=<redacted>" in text
        assert "sig=x" not in text and "token=y" not in text


@pytest.mark.parametrize(
    "outcome",
    [
        {"return_value": {"best": MagicMock(url="u")}},
        {"return_value": None},
        {"side_effect": PluginError("boom")},
    ],
)
def test_streamlink_session_is_closed(session, outcome):
    session.streams.configure_mock(**outcome)
    try:
        get_stream("twitch.tv", "alice", "best")
    except ResolverError:
        pass
    session.http.close.assert_called_once_with()


def test_streamlink_session_is_closed_before_ytdlp_fallback(ydl, session):
    ydl.extract_info.side_effect = lambda *a, **k: (
        session.http.close.assert_called_once_with() or {"url": "v"}
    )
    assert get_stream("kick.com", "u", "best") == StreamURLs("v")


@pytest.mark.parametrize(
    "site,expected",
    [
        ("twitch.tv", True),
        ("www.twitch.tv", True),
        ("Twitch.TV", True),
        (" twitch.tv ", True),
        ("kick.com", False),
        ("nottwitch.tv", False),
        ("twitch.tv.example", False),
    ],
)
def test_is_twitch(site, expected):
    assert is_twitch(site) is expected


def _options(session):
    return session.streams.call_args.kwargs["options"]


def test_streamlink_options_are_empty_without_a_token(session):
    session.streams.return_value = {"best": MagicMock(url="u")}
    get_stream("twitch.tv", "alice", "best")
    options = _options(session)
    assert options.get("api-header") is None
    assert options.get("twitch") is None  # v3's no-op "twitch-disable-reruns" is gone


def test_streamlink_sends_the_token_to_twitch(session):
    session.streams.return_value = {"best": MagicMock(url="u")}
    get_stream("twitch.tv", "alice", "best", twitch_token="abc")
    assert _options(session).get("api-header") == [("Authorization", "OAuth abc")]


def test_streamlink_token_is_only_sent_to_twitch(session):
    session.streams.return_value = {"best": MagicMock(url="u")}
    get_stream("kick.com", "alice", "best", twitch_token="abc")
    assert _options(session).get("api-header") is None


def test_rejected_token_is_reported(session):
    session.streams.side_effect = PluginError(
        'Unauthorized: The "Authorization" token is invalid.'
    )
    with pytest.raises(ResolverError) as err:
        get_stream("twitch.tv", "alice", "best", twitch_token="abc")
    assert str(err.value) == (
        "Twitch rejected TWITCH_OAUTH_TOKEN: "
        'Unauthorized: The "Authorization" token is invalid.'
    )


def test_unauthorized_without_a_token_is_a_plugin_error(session):
    session.streams.side_effect = PluginError("Unauthorized: nope")
    with pytest.raises(ResolverError, match="^Plugin error: Unauthorized: nope$"):
        get_stream("twitch.tv", "alice", "best")


def test_twitch_plugin_sends_the_api_header():
    # The tests above mock session.streams; this pins the real plugin's contract.
    # Building the plugin makes no network requests.
    session = Streamlink(options={"no-plugin-cache": True})
    try:
        _, pluginclass, resolved = session.resolve_url("twitch.tv/alice")
        options = Options()
        options.set("api-header", [("Authorization", "OAuth abc")])
        plugin = pluginclass(session, resolved, options)
        assert plugin.api.headers["Authorization"] == "OAuth abc"
        plain = pluginclass(session, resolved, Options())
        assert "Authorization" not in plain.api.headers
    finally:
        session.http.close()


# --- get_stream via yt-dlp ------------------------------------------------------


def test_ytdlp_combined_url(ydl):
    ydl.extract_info.return_value = {"url": "http://example/video"}
    assert get_stream("kick.com", "u", "best") == StreamURLs("http://example/video")


def test_ytdlp_split_formats(ydl):
    ydl.extract_info.return_value = {
        "requested_formats": [
            {"url": "http://v", "vcodec": "avc1", "acodec": "none"},
            {"url": "http://a", "vcodec": "none", "acodec": "mp4a"},
        ]
    }
    assert get_stream("kick.com", "u", "best") == StreamURLs("http://v", "http://a")


@pytest.mark.parametrize(
    "message", ["Room is currently offline", "Room is resting, back soon"]
)
def test_ytdlp_expected_errors_are_offline(ydl, message):
    ydl.extract_info.side_effect = wrapped(not_live(message))
    with pytest.raises(Offline) as err:
        get_stream("chaturbate.com", "bob", "best")
    assert str(err.value) == f"Not live: {message}"


def test_ytdlp_offline_text_alone_is_not_offline(ydl, caplog):
    caplog.set_level(logging.DEBUG, logger="streamdl")
    ydl.extract_info.side_effect = DownloadError(
        "ERROR: The channel is currently offline"
    )
    with pytest.raises(ResolverError, match="Download error") as err:
        get_stream("kick.com", "offlineuser", "best")
    assert not isinstance(err.value, Offline)
    assert any(r.levelno == logging.ERROR for r in caplog.records)


def test_ytdlp_rate_limited(ydl):
    ydl.extract_info.side_effect = DownloadError(
        "ERROR: [x] user: HTTP Error 429: Too Many Requests (caused by <HTTPError 429>)"
    )
    with pytest.raises(RateLimited):
        get_stream("kick.com", "u", "best")


def test_ytdlp_429_match_needs_the_trailing_space(ydl):
    ydl.extract_info.side_effect = DownloadError("HTTP Error 429: Too Many Requests")
    with pytest.raises(ResolverError) as err:
        get_stream("kick.com", "u", "best")
    assert not isinstance(err.value, RateLimited)


def test_ytdlp_other_download_error(ydl):
    ydl.extract_info.side_effect = DownloadError("ERROR: something unexpected")
    with pytest.raises(ResolverError, match="Download error"):
        get_stream("kick.com", "u", "best")


def test_ytdlp_geo_restricted(ydl):
    ydl.extract_info.side_effect = GeoRestrictedError("blocked here")
    with pytest.raises(GeoRestricted, match="Geo-restricted"):
        get_stream("kick.com", "u", "best")


def test_ytdlp_unavailable(ydl):
    ydl.extract_info.side_effect = UnavailableVideoError("gone")
    with pytest.raises(NotFound, match="Stream unavailable"):
        get_stream("kick.com", "u", "best")


def test_ytdlp_empty_video_url(ydl):
    ydl.extract_info.return_value = {}
    with pytest.raises(ResolverError, match="testuser"):
        get_stream("kick.com", "testuser", "best")


def test_ytdlp_format_fallback_sets_warning(ydl):
    ydl.extract_info.side_effect = [
        DownloadError(FORMAT_UNAVAILABLE),
        {"url": "http://example/video", "requested_formats": None},
    ]
    urls = get_stream("kick.com", "testuser", "worst")
    assert urls.video == "http://example/video"
    assert "worst" in urls.warning
    assert "default selection" in urls.warning


def test_ytdlp_format_fallback_second_failure(ydl):
    ydl.extract_info.side_effect = [
        DownloadError(FORMAT_UNAVAILABLE),
        DownloadError("ERROR: fallback failed"),
    ]
    with pytest.raises(ResolverError, match="testuser"):
        get_stream("kick.com", "testuser", "worst")


def test_ytdlp_format_fallback_unexpected_error(ydl):
    ydl.extract_info.side_effect = [
        DownloadError(FORMAT_UNAVAILABLE),
        RuntimeError("unexpected fallback failure"),
    ]
    with pytest.raises(ResolverError, match="unexpected fallback failure"):
        get_stream("kick.com", "testuser", "worst")


def test_ytdlp_format_fallback_without_url(ydl):
    ydl.extract_info.side_effect = [DownloadError(FORMAT_UNAVAILABLE), {}]
    with pytest.raises(FormatUnavailable):
        get_stream("kick.com", "testuser", "worst")


def test_ytdlp_gets_a_socket_timeout_and_format(session):
    session.streams.side_effect = NoPluginError("no plugin")
    with patch("streamdl.resolver.yt_dlp.YoutubeDL") as cls:
        cls.return_value.__enter__.return_value.extract_info.return_value = {"url": "u"}
        get_stream("kick.com", "u", "best")
    params = cls.call_args.args[0]
    assert params["socket_timeout"] == resolver.HTTP_TIMEOUT
    assert params["format"] == "bestvideo*+bestaudio/best"


# --- get_vods -------------------------------------------------------------------


def test_get_vods_parses_entries():
    with patch("streamdl.resolver.yt_dlp.YoutubeDL") as cls:
        ydl = cls.return_value.__enter__.return_value
        ydl.extract_info.return_value = {
            "entries": [
                {"id": "v1", "title": "A", "upload_date": "20260414", "duration": 3600},
                None,
            ]
        }
        assert get_vods("twitch.tv", "alice", 5) == [
            VodInfo("v1", "A", "20260414", 3600)
        ]
    params = cls.call_args.args[0]
    assert params["playlistend"] == 5
    assert params["extract_flat"] == "in_playlist"
    ydl.extract_info.assert_called_once_with(
        "https://twitch.tv/alice/videos", download=False
    )


def test_get_vods_without_entries():
    with patch("streamdl.resolver.yt_dlp.YoutubeDL") as cls:
        cls.return_value.__enter__.return_value.extract_info.return_value = {}
        with pytest.raises(NotFound):
            get_vods("twitch.tv", "alice", 5)


@pytest.mark.parametrize(
    "message,error",
    [
        ("HTTP Error 429: Too Many Requests", RateLimited),
        ("HTTP Error 404: Not Found", NotFound),
        ("The channel does not exist", NotFound),
        ("something else", ResolverError),
    ],
)
def test_get_vods_errors(message, error):
    with patch("streamdl.resolver.yt_dlp.YoutubeDL") as cls:
        cls.return_value.__enter__.return_value.extract_info.side_effect = (
            DownloadError(message)
        )
        with pytest.raises(ResolverError) as err:
            get_vods("twitch.tv", "alice", 5)
    assert type(err.value) is error


def test_get_vods_unexpected_error():
    with patch("streamdl.resolver.yt_dlp.YoutubeDL") as cls:
        cls.return_value.__enter__.return_value.extract_info.side_effect = RuntimeError(
            "boom"
        )
        with pytest.raises(ResolverError, match="boom"):
            get_vods("twitch.tv", "alice", 5)


# --- LibraryResolver ------------------------------------------------------------


async def test_library_resolver_stream(monkeypatch):
    monkeypatch.setattr(
        resolver,
        "get_stream",
        lambda site, user, quality, **kwargs: StreamURLs(f"{site}/{user}/{quality}"),
    )
    assert await LibraryResolver().stream("twitch.tv", "alice", "best") == StreamURLs(
        "twitch.tv/alice/best"
    )


async def test_library_resolver_vods(monkeypatch):
    monkeypatch.setattr(
        resolver, "get_vods", lambda site, user, limit: [VodInfo(f"{user}-{limit}")]
    )
    assert await LibraryResolver().vods("twitch.tv", "alice", 3) == [VodInfo("alice-3")]


async def test_library_resolver_times_out(monkeypatch):
    monkeypatch.setattr(resolver, "get_stream", lambda *args, **kwargs: time.sleep(0.5))
    with pytest.raises(ResolverError, match="request timed out"):
        await LibraryResolver(timeout=0.05).stream("s", "u", "q")


async def test_library_resolver_passes_errors_through(monkeypatch):
    def offline(*args, **kwargs):
        raise Offline("Channel 'u' is offline")

    monkeypatch.setattr(resolver, "get_stream", offline)
    with pytest.raises(Offline):
        await LibraryResolver().stream("s", "u", "q")


async def test_library_resolver_wraps_unexpected_errors(monkeypatch):
    def broken(*args, **kwargs):
        raise AttributeError("'DASHStream' object has no attribute 'url'")

    monkeypatch.setattr(resolver, "get_stream", broken)
    with pytest.raises(ResolverError, match="Unexpected error: 'DASHStream'"):
        await LibraryResolver().stream("s", "u", "q")


async def test_library_resolver_logs_unexpected_errors_with_context(
    monkeypatch, caplog
):
    caplog.set_level(logging.ERROR, logger="streamdl")

    def get_stream(*args, **kwargs):
        raise RuntimeError("bad https://x/?token=secret")

    monkeypatch.setattr(resolver, "get_stream", get_stream)
    with pytest.raises(ResolverError) as err:
        await LibraryResolver().stream("twitch.tv", "alice", "best")
    assert "token=<redacted>" in str(err.value)
    assert "in get_stream site=twitch.tv user=alice" in caplog.text
    assert "secret" not in caplog.text


async def test_library_resolver_uses_its_own_pool(monkeypatch):
    monkeypatch.setattr(
        resolver, "get_stream", lambda *args, **kwargs: threading.current_thread().name
    )
    lookup = LibraryResolver()
    try:
        assert (await lookup.stream("s", "u", "q")).startswith("resolver")
    finally:
        lookup.close()


async def test_library_resolver_close_rejects_new_lookups(monkeypatch):
    monkeypatch.setattr(resolver, "get_stream", lambda *args, **kwargs: StreamURLs("v"))
    lookup = LibraryResolver()
    lookup.close()
    with pytest.raises(ResolverError):
        await lookup.stream("s", "u", "q")


async def test_library_resolver_passes_the_token(monkeypatch):
    seen = {}

    def fake(site, user, quality, **kwargs):
        seen.update(kwargs)
        return StreamURLs("v")

    monkeypatch.setattr(resolver, "get_stream", fake)
    lookup = LibraryResolver(twitch_token="abc")
    try:
        await lookup.stream("twitch.tv", "alice", "best")
    finally:
        lookup.close()
    assert seen == {"twitch_token": "abc"}


# --- library patches ------------------------------------------------------------


def test_resolver_error_messages_are_redacted():
    assert str(ResolverError("a?sig=x&token=y")) == "a?sig=<redacted>&token=<redacted>"
    assert str(Offline("b?token=z")) == "b?token=<redacted>"


def test_ytdlp_errors_have_no_bug_report_suffix():
    assert str(ExtractorError("boom")) == "boom"


def test_ytdlp_output_goes_to_the_debug_log(caplog):
    caplog.set_level(logging.DEBUG, logger="streamdl")
    resolver._YTDLP_PARAMS["logger"].error("ERROR: failed https://x/?sig=abc")
    record = caplog.records[-1]
    assert record.name == "streamdl.resolver"
    assert record.levelno == logging.DEBUG
    assert "yt-dlp: ERROR: failed https://x/?sig=<redacted>" in record.getMessage()


def test_third_party_loggers_are_silenced_once():
    resolver._silence_third_party_loggers()
    resolver._silence_third_party_loggers()
    for name in resolver._SILENCED_LOGGERS:
        logger = logging.getLogger(name)
        assert logger.level == logging.CRITICAL
        assert logger.propagate is False
        nulls = [h for h in logger.handlers if type(h) is logging.NullHandler]
        assert len(nulls) == 1
    assert not logging.getLogger("streamdl").disabled


# --- urllib3 compatibility shim -------------------------------------------------


def test_urllib3_percent_encoding_still_works():
    # urllib3>=2.8 calls _PERCENT_RE.sub; the streamlink + yt-dlp patches broke that
    assert "%20" in urllib3.util.url.parse_url("https://example.com/a b%2f").path


CURL_DNS = (
    "ERROR: [Chaturbate] busbuddies: Unable to download webpage: Failed to perform,"
    " curl: (6) Could not resolve host: chaturbate.com. See"
    " https://curl.se/libcurl/c/libcurl-errors.html first for more details."
    " (caused by TransportError('Failed to perform, curl: (6) Could not resolve"
    " host: chaturbate.com. See https://curl.se/libcurl/c/libcurl-errors.html first"
    " for more details.'))"
)
CURL_DNS_SHORT = (
    "[Chaturbate] busbuddies: Unable to download webpage: Failed to perform,"
    " curl: (6) Could not resolve host: chaturbate.com."
)


@pytest.mark.parametrize(
    "message", ["Room is currently offline", "Room is currently in a private show"]
)
def test_ytdlp_not_live_is_logged_at_debug(ydl, caplog, message):
    caplog.set_level(logging.DEBUG, logger="streamdl")
    ydl.extract_info.side_effect = wrapped(not_live(message))
    with pytest.raises(Offline) as err:
        get_stream("chaturbate.com", "bob", "best")
    assert str(err.value) == f"Not live: {message}"
    assert f"[Chaturbate] bob: {message}" in caplog.text
    assert all(r.levelno < logging.WARNING for r in caplog.records)


@pytest.mark.parametrize(
    "error",
    [UserNotLive(), wrapped(UserNotLive()), wrapped(UserNotLive("Gone fishing"))],
)
def test_ytdlp_user_not_live_is_offline(ydl, caplog, error):
    caplog.set_level(logging.DEBUG, logger="streamdl")
    ydl.extract_info.side_effect = error
    with pytest.raises(Offline, match="^Not live: "):
        get_stream("kick.com", "u", "best")
    assert all(r.levelno < logging.WARNING for r in caplog.records)


def test_ytdlp_user_not_live_after_a_network_error_is_offline(ydl, caplog):
    caplog.set_level(logging.DEBUG, logger="streamdl")
    try:
        raise network_error()
    except ExtractorError:
        # Some extractors turn a failed request (HTTP 400/404) into UserNotLive.
        error = wrapped(UserNotLive(video_id="u"))
    assert isinstance(error.exc_info[1], TransportError)
    ydl.extract_info.side_effect = error
    with pytest.raises(Offline, match="^Not live: "):
        get_stream("kick.com", "u", "best")
    assert all(r.levelno < logging.WARNING for r in caplog.records)


def test_ytdlp_download_error_without_context_uses_exc_info(ydl):
    inner = not_live("Room is currently offline")
    ydl.extract_info.side_effect = DownloadError(
        "ERROR: offline", (type(inner), inner, None)
    )
    with pytest.raises(Offline, match="^Not live: Room is currently offline$"):
        get_stream("chaturbate.com", "bob", "best")


def failed_request(status):
    """Raise the way InfoExtractor._request_webpage does when a request fails."""
    response = Response(io.BytesIO(b""), "https://fake.test/api", {}, status=status)
    try:
        raise HTTPError(response)
    except HTTPError as e:
        raise ExtractorError("Unable to download JSON", cause=e)


def private_show():
    raise not_live("Room is currently in a private show")


def gone_after_404():
    try:
        failed_request(404)
    except ExtractorError:
        raise UserNotLive(video_id="gone")


FAKE_SCENARIOS = {
    "private": private_show,
    "gone": gone_after_404,
    "down": lambda: failed_request(503),
}


class FakeIE(InfoExtractor):
    _VALID_URL = r"(?:https?://)?fake\.test/(?P<id>\w+)"

    def _real_extract(self, url):
        FAKE_SCENARIOS[self._match_id(url)]()


class FakeYoutubeDL(yt_dlp.YoutubeDL):
    """A real YoutubeDL that only knows FakeIE, so extract_info wraps its errors."""

    def __init__(self, params):
        super().__init__(params, auto_init=False)
        self.add_info_extractor(FakeIE())


@pytest.mark.parametrize(
    ("user", "kind", "level", "expected"),
    [
        (
            "private",
            Offline,
            logging.DEBUG,
            "Not live: Room is currently in a private show",
        ),
        ("gone", Offline, logging.DEBUG, "Not live: The channel is not currently live"),
        (
            "down",
            ResolverError,
            logging.WARNING,
            "Download error: [Fake] down: Unable to download JSON",
        ),
    ],
)
def test_ytdlp_errors_are_sorted_through_extract_info(
    session, caplog, user, kind, level, expected
):
    caplog.set_level(logging.DEBUG, logger="streamdl")
    session.streams.side_effect = NoPluginError("no plugin")
    with (
        patch("streamdl.resolver.yt_dlp.YoutubeDL", FakeYoutubeDL),
        pytest.raises(kind) as err,
    ):
        get_stream("fake.test", user, "best")
    assert type(err.value) is kind
    assert str(err.value) == expected
    assert max(r.levelno for r in caplog.records) == level


def test_ytdlp_raw_extractor_error_is_offline(ydl):
    ydl.extract_info.side_effect = not_live("Room is currently in a private show")
    with pytest.raises(Offline) as err:
        get_stream("chaturbate.com", "bob", "best")
    assert str(err.value) == "Not live: Room is currently in a private show"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            wrapped(network_error()),
            "Download error: [Chaturbate] bob: Unable to download webpage",
        ),
        (
            network_error(),
            "Extractor error: [Chaturbate] bob: Unable to download webpage",
        ),
        (
            ExtractorError(
                "Unable to download webpage",
                cause=TransportError("timed out"),
                expected=True,
            ),
            "Extractor error: Unable to download webpage",
        ),
    ],
)
def test_ytdlp_network_errors_are_warnings(ydl, caplog, error, expected):
    caplog.set_level(logging.DEBUG, logger="streamdl")
    ydl.extract_info.side_effect = error
    with pytest.raises(ResolverError) as err:
        get_stream("chaturbate.com", "bob", "best")
    assert not isinstance(err.value, Offline)
    assert str(err.value) == expected
    [record] = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert record.levelno == logging.WARNING


@pytest.mark.parametrize(
    "error",
    [
        wrapped(ExtractorError("Unable to extract room data", ie="Kick")),
        wrapped(GeoRestrictedError("Not available from your location")),
        wrapped(ValueError("bad json")),
    ],
)
def test_ytdlp_unexpected_errors_are_errors(ydl, caplog, error):
    caplog.set_level(logging.DEBUG, logger="streamdl")
    ydl.extract_info.side_effect = error
    with pytest.raises(ResolverError, match="^Download error: ") as err:
        get_stream("kick.com", "u", "best")
    assert not isinstance(err.value, Offline)
    [record] = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert record.levelno == logging.ERROR


def test_ytdlp_format_check_comes_before_expected(ydl):
    ydl.extract_info.side_effect = [
        wrapped(ExtractorError("Requested format is not available", expected=True)),
        {"url": "http://example/video"},
    ]
    urls = get_stream("kick.com", "u", "worst")
    assert urls.video == "http://example/video"
    assert "default selection" in urls.warning


def test_ytdlp_429_check_comes_before_expected_and_network(ydl):
    try:
        raise TransportError("HTTP Error 429: Too Many Requests")
    except TransportError as e:
        inner = ExtractorError(
            "HTTP Error 429: Too Many Requests", cause=e, ie="x", video_id="u"
        )
    assert inner.expected
    ydl.extract_info.side_effect = wrapped(inner)
    with pytest.raises(RateLimited):
        get_stream("kick.com", "u", "best")


@pytest.mark.parametrize(
    ("error", "kind", "level"),
    [
        (wrapped(not_live("Room is currently offline")), Offline, logging.DEBUG),
        (not_live("Room is currently offline"), Offline, logging.DEBUG),
        (wrapped(network_error()), ResolverError, logging.WARNING),
        (network_error(), ResolverError, logging.WARNING),
        (DownloadError("ERROR: fallback failed"), ResolverError, logging.ERROR),
    ],
)
def test_ytdlp_fallback_errors_are_sorted(ydl, caplog, error, kind, level):
    caplog.set_level(logging.DEBUG, logger="streamdl")
    ydl.extract_info.side_effect = [DownloadError(FORMAT_UNAVAILABLE), error]
    with pytest.raises(kind) as err:
        get_stream("chaturbate.com", "bob", "worst")
    assert isinstance(err.value, Offline) == (kind is Offline)
    fallback = [r for r in caplog.records if "allback yt-dlp" in r.getMessage()]
    assert [r.levelno for r in fallback] == [level]


def test_streamlink_no_streams_is_logged_at_debug(session, caplog):
    caplog.set_level(logging.DEBUG, logger="streamdl")
    session.streams.return_value = None
    with pytest.raises(Offline):
        get_stream("twitch.tv", "testuser", "best")
    assert "No streams found for user testuser" in caplog.text
    assert all(r.levelno < logging.WARNING for r in caplog.records)


def test_ytdlp_other_download_errors_are_still_errors(ydl, caplog):
    caplog.set_level(logging.DEBUG, logger="streamdl")
    ydl.extract_info.side_effect = DownloadError(CURL_DNS)
    with pytest.raises(ResolverError) as err:
        get_stream("chaturbate.com", "busbuddies", "best")
    assert str(err.value) == f"Download error: {CURL_DNS_SHORT}"
    [record] = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert "caused by TransportError" in record.getMessage()


def test_extractor_errors_are_shortened(ydl):
    ydl.extract_info.side_effect = ExtractorError(
        "boom", cause=ValueError("x"), ie="Kick", video_id="u"
    )
    with pytest.raises(ResolverError) as err:
        get_stream("kick.com", "u", "best")
    assert str(err.value) == "Extractor error: [Kick] u: boom"


def test_fallback_extractor_errors_are_shortened(ydl):
    ydl.extract_info.side_effect = [
        DownloadError(FORMAT_UNAVAILABLE),
        ExtractorError("boom", cause=ValueError("x"), ie="Kick", video_id="u"),
    ]
    with pytest.raises(ResolverError) as err:
        get_stream("kick.com", "u", "worst")
    assert str(err.value) == "Extractor error: [Kick] u: boom"


def test_vod_download_errors_are_shortened(ydl):
    ydl.extract_info.side_effect = DownloadError(CURL_DNS)
    with pytest.raises(ResolverError) as err:
        get_vods("twitch.tv", "busbuddies")
    assert str(err.value) == f"Download error: {CURL_DNS_SHORT}"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ERROR: plain", "plain"),
        ("no prefix", "no prefix"),
        ("a. See https://x.example/y for more details.", "a."),
        ("a (caused by Foo('b (c)'))", "a"),
        (CURL_DNS, CURL_DNS_SHORT),
    ],
)
def test_short_error(text, expected):
    assert resolver._short_error(text) == expected
