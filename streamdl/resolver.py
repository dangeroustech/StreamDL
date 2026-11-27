"""Resolve channels to stream URLs and VOD lists.

streamlink is tried first; sites it has no plugin for fall back to yt-dlp. Failures
are raised as ResolverError subclasses whose message is the text users see in notices.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import re
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

import urllib3.util.url
import yt_dlp
from streamlink.exceptions import NoPluginError, PluginError
from streamlink.options import Options
from streamlink.session import Streamlink
from yt_dlp.networking.exceptions import network_exceptions
from yt_dlp.utils import (
    DownloadError,
    ExtractorError,
    GeoRestrictedError,
    UnavailableVideoError,
    UserNotLive,
)

from .ffmpeg import sanitize_log

log = logging.getLogger(__name__)
T = TypeVar("T")

# streamlink and yt-dlp both monkey-patch urllib3's _PERCENT_RE. yt-dlp wraps
# streamlink's override and forwards attributes via __getattribute__, which skips
# streamlink's __getattr__ passthrough, so urllib3>=2.8's `_PERCENT_RE.sub` calls
# raise AttributeError. Point yt-dlp's wrapper straight at the real regex instead.
_percent_re_override = urllib3.util.url._PERCENT_RE
_original_percent_re = getattr(
    getattr(_percent_re_override, "re", None), "_re_percent_encoding", None
)
if isinstance(_original_percent_re, re.Pattern):
    _percent_re_override.re = _original_percent_re

HTTP_TIMEOUT = 20.0  # per-request network timeout for streamlink and yt-dlp
RESOLVE_TIMEOUT = 30.0  # overall limit per lookup, matching v3's gRPC deadline

_BEST_FORMAT = "bestvideo*+bestaudio/best"
# Streamlink-style names mapped to yt-dlp selectors. Bare "best"/"worst" broke for
# extractors that split video and audio (e.g. Chaturbate).
_YTDLP_FORMATS = {"best": _BEST_FORMAT, "worst": "worstvideo*+worstaudio/worst"}


class _YtdlpLogger:
    """Sends yt-dlp's output to our debug log.

    With logger=None, yt-dlp still prints "ERROR: ..." lines to stderr even when
    quiet=True. The errors themselves are raised and reported by the callers.
    """

    def _log(self, msg: str) -> None:
        log.debug("yt-dlp: %s", sanitize_log(str(msg)))

    debug = info = warning = error = _log


_YTDLP_PARAMS: dict[str, Any] = {
    "quiet": True,
    "no_warnings": True,
    "verbose": False,
    "logger": _YtdlpLogger(),
    "socket_timeout": HTTP_TIMEOUT,
}
_NOT_FOUND_VODS = "user not found or no VODs available"
TOKEN_REJECTED = "Twitch rejected TWITCH_OAUTH_TOKEN"  # nosec B105 - a message
_TWITCH_HOSTS = frozenset({"twitch.tv", "www.twitch.tv"})


def is_twitch(site: str) -> bool:
    return site.strip().lower() in _TWITCH_HOSTS


# Process-global: every yt-dlp request in this process sends this User-Agent.
yt_dlp.utils.networking.std_headers["User-Agent"] = "streamdl"
# Drop the "please report this issue on ... yt-dlp -U" suffix from error messages.
# ExtractorError looks the function up in yt_dlp.utils._utils, so patch it there.
yt_dlp.utils._utils.bug_reports_message = lambda *args, **kwargs: ""
yt_dlp.utils.bug_reports_message = yt_dlp.utils._utils.bug_reports_message

# Third-party loggers silenced the way v3's server effectively did.
_SILENCED_LOGGERS = (
    "streamlink",
    "yt_dlp",
    "urllib3",
    "requests",
    "charset_normalizer",
    "websocket",
    "socks",
    "trio",
)


def _silence_third_party_loggers() -> None:
    for name in _SILENCED_LOGGERS:
        logger = logging.getLogger(name)
        logger.setLevel(logging.CRITICAL)
        logger.propagate = False
        if not any(type(h) is logging.NullHandler for h in logger.handlers):
            logger.addHandler(logging.NullHandler())


_silence_third_party_loggers()


def _text(error: BaseException) -> str:
    """An exception's text with signed-URL secrets redacted, for log lines."""
    return sanitize_log(str(error))


_RE_CAUSED_BY = re.compile(r" \(caused by .*\)\Z", re.DOTALL)
_RE_SEE_DOCS = re.compile(r" See https?://\S+ (?:first )?for more details\.")


def _short_error(text: str) -> str:
    """A yt-dlp error without its "ERROR: " prefix, doc links or "(caused by ...)" tail.

    Those repeat the message and make notices hard to read; the full text is
    still logged.
    """
    text = _RE_CAUSED_BY.sub("", text.removeprefix("ERROR: "))
    return _RE_SEE_DOCS.sub("", text).strip()


class ResolverError(Exception):
    """A lookup failed. str(error) is the user-facing message, with secrets redacted.

    Messages often embed library errors, which can carry signed URLs
    (e.g. a Twitch usher URL with sig= and token= parameters).
    """

    def __init__(self, message: str) -> None:
        super().__init__(sanitize_log(message))


class RateLimited(ResolverError):
    def __init__(self, message: str = "rate limited") -> None:
        super().__init__(message)


class Offline(ResolverError):
    pass


class NotFound(ResolverError):
    pass


class QualityUnavailable(ResolverError):
    pass


class FormatUnavailable(ResolverError):
    pass


class GeoRestricted(ResolverError):
    pass


@dataclass(frozen=True)
class StreamURLs:
    video: str
    audio: str = ""
    warning: str = ""  # non-fatal notice, e.g. a format fallback


@dataclass(frozen=True)
class VodInfo:
    id: str
    title: str = ""
    published_at: str = ""
    duration_seconds: int = 0


def ytdlp_format(quality: str | None) -> str:
    if not quality:
        return _BEST_FORMAT
    return _YTDLP_FORMATS.get(quality, quality)


def extract_urls(info: dict[str, Any]) -> tuple[str, str]:
    """Return (video_url, audio_url) from a yt-dlp info dict.

    audio_url is empty when the video URL already carries both tracks. When yt-dlp
    picks separate formats, FFmpeg gets them as two inputs.
    """
    if url := info.get("url"):
        return url, ""
    requested = info.get("requested_formats")
    if not requested:
        return "", ""
    video = audio = ""
    for fmt in requested:
        vcodec = fmt.get("vcodec", "none")
        if vcodec and vcodec != "none" and not video:
            video = fmt.get("url", "")
        elif (not vcodec or vcodec == "none") and not audio:
            audio = fmt.get("url", "")
    return video or requested[0].get("url", ""), audio


def parse_vod_entries(entries: Iterable[dict[str, Any] | None]) -> list[VodInfo]:
    vods = []
    for entry in entries:
        if entry is None:
            continue
        vod = VodInfo(
            id=str(entry.get("id", "")),
            title=entry.get("title") or "",  # v3 sent None as "" over protobuf
            published_at=entry.get("upload_date") or "",
            duration_seconds=int(entry.get("duration", 0) or 0),
        )
        if vod.id:
            vods.append(vod)
    return vods


def get_vods(site: str, user: str, limit: int = 10) -> list[VodInfo]:
    """List a channel's most recent VODs with yt-dlp."""
    url = f"https://{site}/{user}/videos"
    log.debug("Fetching VODs from %s (limit=%d)", url, limit)
    params = {**_YTDLP_PARAMS, "extract_flat": "in_playlist", "playlistend": limit}
    try:
        with yt_dlp.YoutubeDL(params) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info or "entries" not in info:
                log.warning("No VODs found for user %s", user)
                raise NotFound(_NOT_FOUND_VODS)
            vods = parse_vod_entries(info["entries"])
    except ResolverError:
        raise
    except DownloadError as e:
        text = str(e)
        if "HTTP Error 429" in text:
            log.error("Rate limited fetching VODs for %s", user)
            raise RateLimited() from e
        if "HTTP Error 404" in text or "does not exist" in text:
            log.warning("User %s not found on %s", user, site)
            raise NotFound(_NOT_FOUND_VODS) from e
        log.error("DownloadError fetching VODs for %s: %s", user, _text(e))
        raise ResolverError(f"Download error: {_short_error(text)}") from e
    except Exception as e:
        log.error("Error fetching VODs for %s: %s", user, _text(e))
        raise ResolverError(f"Unexpected error: {e}") from e
    log.debug("Found %d VODs for user %s", len(vods), user)
    return vods


def get_stream(
    site: str, user: str, quality: str, *, twitch_token: str = ""
) -> StreamURLs:
    """Resolve a live stream (or `videos/<id>` VOD) URL, falling back to yt-dlp.

    twitch_token, when set, is sent to Twitch as the viewer's login.
    """
    log.debug(
        "Resolving stream via Streamlink site=%s user=%s quality=%s",
        site,
        user,
        quality,
    )
    session = Streamlink(options={"http-timeout": HTTP_TIMEOUT})
    try:
        return _get_stream_streamlink(session, site, user, quality, twitch_token)
    except NoPluginError:
        log.debug("Streamlink has no plugin for %s; falling back to yt-dlp", site)
    finally:
        session.http.close()
    return _get_stream_ytdlp(site, user, quality)


def _get_stream_streamlink(
    session: Streamlink, site: str, user: str, quality: str, twitch_token: str
) -> StreamURLs:
    options = Options()
    send_token = bool(twitch_token) and is_twitch(site)
    if send_token:
        options.set("api-header", [("Authorization", f"OAuth {twitch_token}")])
    resolve_url = f"{site}/{user}"
    try:
        streams = session.streams(url=resolve_url, options=options)
    except NoPluginError:
        raise
    except PluginError as e:
        log.error("Plugin error: %s", _text(e))
        if send_token and "unauthorized" in str(e).lower():
            raise ResolverError(f"{TOKEN_REJECTED}: {e}") from e
        raise ResolverError(f"Plugin error: {e}") from e

    if not streams:
        log.debug("No streams found for user %s", user)
        raise Offline(f"No live streams found for '{user}' on {site}")
    selected = quality or "best"
    log.debug("Selecting quality=%s from available keys=%s", selected, list(streams))
    try:
        return StreamURLs(video=streams[selected].url)
    except KeyError:
        available = ", ".join(sorted(streams))
        message = (
            f"Requested quality '{selected}' not available. Available: {available}"
        )
        log.warning(message)
        raise QualityUnavailable(message) from None


def _lookup_error(
    error: DownloadError | ExtractorError, message: str, context: str
) -> ResolverError:
    """Log a failed yt-dlp lookup at a level that fits it; return the error to raise.

    Sorted by the error's class and flags, never by a site's text. A UserNotLive,
    or any other ExtractorError marked expected (a site saying the room is offline
    or in a private show), means the channel isn't live: DEBUG and Offline. yt-dlp
    marks network failures expected too, so those are picked out first: WARNING.
    Anything else is an ERROR. message is the ResolverError's text.
    """
    # extract_info raises the DownloadError while handling the extractor's error, so
    # that's its __context__. exc_info names it too, except when it was raised while
    # handling another error (a network error, say): then exc_info names that one,
    # hiding a UserNotLive raised after a failed request.
    if isinstance(error, DownloadError):
        inner = error.__context__
        if not isinstance(inner, ExtractorError):
            inner = error.exc_info[1] if error.exc_info else None
    else:
        inner = error
    network = isinstance(inner, network_exceptions) or (
        isinstance(inner, ExtractorError)
        and any(
            isinstance(e, network_exceptions) for e in (inner.cause, inner.exc_info[1])
        )
    )
    if isinstance(inner, UserNotLive) or (
        isinstance(inner, ExtractorError)
        and inner.expected
        and not network
        and not isinstance(inner, GeoRestrictedError)
    ):
        log.debug("%s: %s", context, _text(error))
        return Offline(f"Not live: {_short_error(inner.orig_msg)}")
    level = logging.WARNING if network else logging.ERROR
    log.log(level, "%s: %s", context, _text(error))
    return ResolverError(message)


def _get_stream_ytdlp(site: str, user: str, quality: str) -> StreamURLs:
    fmt = ytdlp_format(quality)
    url = f"{site}/{user}"
    try:
        with yt_dlp.YoutubeDL({**_YTDLP_PARAMS, "format": fmt}) as ydl:
            log.debug("yt_dlp.extract_info(url=%s)", url)
            info = ydl.extract_info(url, download=False)
    except GeoRestrictedError as e:
        log.error("GeoRestrictedError: %s", _text(e))
        raise GeoRestricted(f"Geo-restricted: {e}") from e
    except UnavailableVideoError as e:
        log.error("UnavailableVideoError: %s", _text(e))
        raise NotFound(f"Stream unavailable: {e}") from e
    except ExtractorError as e:
        message = f"Extractor error: {_short_error(str(e))}"
        raise _lookup_error(e, message, "ExtractorError") from e
    except DownloadError as e:
        text = str(e)
        # yt-dlp's own messages, checked first: both can wrap an expected error.
        if "Requested format is not available" in text:
            log.error("DownloadError: %s", _text(e))
            return _retry_with_default_format(url, user, fmt)
        if "HTTP Error 429: Too Many Requests " in text:
            log.error("DownloadError: %s", _text(e))
            raise RateLimited() from e
        message = f"Download error: {_short_error(text)}"
        raise _lookup_error(e, message, "DownloadError") from e
    except Exception as e:
        log.error("Generic Error: %s", _text(e))
        raise ResolverError(f"Unexpected error: {e}") from e

    video, audio = extract_urls(info or {})
    if not video:
        log.error("No video URL resolved for %s", user)
        raise ResolverError(f"Unable to resolve stream URL for '{user}'")
    return StreamURLs(video, audio)


def _retry_with_default_format(url: str, user: str, fmt: str) -> StreamURLs:
    log.warning(
        "Format %s not available for %s, retrying with default selection", fmt, user
    )
    try:
        with yt_dlp.YoutubeDL(dict(_YTDLP_PARAMS)) as ydl:
            log.debug("yt_dlp.extract_info (fallback) url=%s", url)
            info = ydl.extract_info(url, download=False)
    except DownloadError as e:
        message = f"Unable to resolve stream URL for '{user}'"
        context = f"Fallback yt-dlp extraction failed for {user}"
        raise _lookup_error(e, message, context) from e
    except ExtractorError as e:
        message = f"Extractor error: {_short_error(str(e))}"
        context = f"Fallback yt-dlp extractor error for {user}"
        raise _lookup_error(e, message, context) from e
    except Exception as e:
        log.error("Unexpected fallback yt-dlp error for %s: %s", user, _text(e))
        raise ResolverError(f"Unexpected error: {e}") from e

    video, audio = extract_urls(info or {})
    if not video:
        log.error("Fallback format selection returned no URL for %s", user)
        raise FormatUnavailable(f"Requested format '{fmt}' not available for '{user}'")
    log.info("Fallback format selection succeeded for %s", user)
    warning = f"Requested format '{fmt}' unavailable; using default selection"
    return StreamURLs(video, audio, warning)


class Resolver(Protocol):
    async def stream(self, site: str, user: str, quality: str) -> StreamURLs: ...

    async def vods(self, site: str, user: str, limit: int) -> list[VodInfo]: ...

    def close(self) -> None: ...


class LibraryResolver:
    """Runs the blocking streamlink/yt-dlp calls in worker threads with a time limit.

    Lookups get their own thread pool so they never queue behind other blocking work
    (such as file moves) on the default executor. The limit includes time spent
    waiting for a free worker.

    A thread can't be cancelled: a call that outlives the limit raises "request
    timed out" for the caller but keeps running, and keeps its worker busy, until
    the library gives up on its own (HTTP_TIMEOUT bounds each request). A caller
    that then releases a per-site lock lets the next lookup for that site overlap
    the abandoned one, as v3 did after a gRPC deadline.
    """

    def __init__(
        self, timeout: float = RESOLVE_TIMEOUT, *, twitch_token: str = ""
    ) -> None:
        self.timeout = timeout
        self._twitch_token = twitch_token
        self._pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="resolver")

    async def stream(self, site: str, user: str, quality: str) -> StreamURLs:
        return await self._call(
            get_stream, site, user, quality, twitch_token=self._twitch_token
        )

    async def vods(self, site: str, user: str, limit: int) -> list[VodInfo]:
        return await self._call(get_vods, site, user, limit)

    def close(self) -> None:
        """Stop accepting lookups and drop queued ones; running ones finish alone."""
        self._pool.shutdown(wait=False, cancel_futures=True)

    async def _call(
        self, fn: Callable[..., T], site: str, user: str, *args: Any, **kwargs: Any
    ) -> T:
        loop = asyncio.get_running_loop()
        call = functools.partial(fn, site, user, *args, **kwargs)
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(self._pool, call), self.timeout
            )
        except TimeoutError:
            raise ResolverError("request timed out") from None
        except ResolverError:
            raise
        except Exception as e:
            # v3's gRPC server turned these into an UNKNOWN status, which the client
            # reported as a per-channel failure; keep them from aborting a round.
            log.error(
                "Unexpected resolver error in %s site=%s user=%s: %s",
                getattr(fn, "__name__", fn),
                site,
                user,
                _text(e),
            )
            raise ResolverError(f"Unexpected error: {e}") from e
