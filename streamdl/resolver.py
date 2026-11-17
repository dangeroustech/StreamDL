"""Resolve channels to stream URLs and VOD lists.

streamlink is tried first; sites it has no plugin for fall back to yt-dlp. Failures
are raised as ResolverError subclasses whose message is the text users see in notices.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

import urllib3.util.url
import yt_dlp
from streamlink.exceptions import NoPluginError, PluginError
from streamlink.options import Options
from streamlink.session import Streamlink
from yt_dlp.utils import (
    DownloadError,
    ExtractorError,
    GeoRestrictedError,
    UnavailableVideoError,
)

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
_YTDLP_PARAMS: dict[str, Any] = {
    "quiet": True,
    "no_warnings": True,
    "verbose": False,
    "logger": None,
    "socket_timeout": HTTP_TIMEOUT,
}
_NOT_FOUND_VODS = "user not found or no VODs available"

yt_dlp.utils.networking.std_headers["User-Agent"] = "streamdl"
yt_dlp.utils.bug_reports_message = lambda *args, **kwargs: ""


def _silence_third_party_loggers() -> None:
    null = logging.NullHandler()
    for name in ["streamlink", "yt_dlp", *list(logging.root.manager.loggerDict)]:
        if name.split(".")[0] in ("streamdl", "uvicorn", "asyncio", "fastapi"):
            continue
        logger = logging.getLogger(name)
        logger.setLevel(logging.CRITICAL)
        logger.addHandler(null)
        logger.propagate = False


_silence_third_party_loggers()


class ResolverError(Exception):
    """A lookup failed. str(error) is the user-facing message."""


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
        log.error("DownloadError fetching VODs for %s: %s", user, e)
        raise ResolverError(f"Download error: {e}") from e
    except Exception as e:
        log.error("Error fetching VODs for %s: %s", user, e)
        raise ResolverError(f"Unexpected error: {e}") from e
    log.debug("Found %d VODs for user %s", len(vods), user)
    return vods


def get_stream(site: str, user: str, quality: str) -> StreamURLs:
    """Resolve a live stream (or `videos/<id>` VOD) URL, falling back to yt-dlp."""
    log.debug(
        "Resolving stream via Streamlink site=%s user=%s quality=%s",
        site,
        user,
        quality,
    )
    session = Streamlink(options={"http-timeout": HTTP_TIMEOUT})
    options = Options()
    options.set("twitch", "twitch-disable-reruns")  # carried over from v3 unchanged
    resolve_url = f"{site}/{user}"
    try:
        streams = session.streams(url=resolve_url, options=options)
    except NoPluginError:
        log.debug("Streamlink has no plugin for %s; falling back to yt-dlp", site)
        return _get_stream_ytdlp(site, user, quality)
    except PluginError as e:
        log.error("Plugin error: %s", e)
        raise ResolverError(f"Plugin error: {e}") from e

    if not streams:
        log.warning("No streams found for user %s", user)
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


def _get_stream_ytdlp(site: str, user: str, quality: str) -> StreamURLs:
    fmt = ytdlp_format(quality)
    url = f"{site}/{user}"
    try:
        with yt_dlp.YoutubeDL({**_YTDLP_PARAMS, "format": fmt}) as ydl:
            log.debug("yt_dlp.extract_info(url=%s)", url)
            info = ydl.extract_info(url, download=False)
    except GeoRestrictedError as e:
        log.error("GeoRestrictedError: %s", e)
        raise GeoRestricted(f"Geo-restricted: {e}") from e
    except UnavailableVideoError as e:
        log.error("UnavailableVideoError: %s", e)
        raise NotFound(f"Stream unavailable: {e}") from e
    except ExtractorError as e:
        log.error("ExtractorError: %s", e)
        raise ResolverError(f"Extractor error: {e}") from e
    except DownloadError as e:
        log.error("DownloadError: %s", e)
        text = str(e)
        if "Requested format is not available" in text:
            return _retry_with_default_format(url, user, fmt)
        if "HTTP Error 429: Too Many Requests " in text:
            raise RateLimited() from e
        if "currently offline" in text:
            raise Offline(f"Channel '{user}' is offline") from e
        raise ResolverError(f"Download error: {e}") from e
    except Exception as e:
        log.error("Generic Error: %s", e)
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
        log.error("Fallback yt-dlp extraction failed for %s: %s", user, e)
        raise ResolverError(f"Unable to resolve stream URL for '{user}'") from e
    except ExtractorError as e:
        log.error("Fallback yt-dlp extractor error for %s: %s", user, e)
        raise ResolverError(f"Extractor error: {e}") from e
    except Exception as e:
        log.error("Unexpected fallback yt-dlp error for %s: %s", user, e)
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


class LibraryResolver:
    """Runs the blocking streamlink/yt-dlp calls in worker threads with a time limit.

    A call that outlives the limit keeps running in its thread, but the caller moves
    on (and releases any site lock) with a "request timed out" error.
    """

    def __init__(self, timeout: float = RESOLVE_TIMEOUT) -> None:
        self.timeout = timeout

    async def stream(self, site: str, user: str, quality: str) -> StreamURLs:
        return await self._call(get_stream, site, user, quality)

    async def vods(self, site: str, user: str, limit: int) -> list[VodInfo]:
        return await self._call(get_vods, site, user, limit)

    async def _call(self, fn: Callable[..., T], *args: Any) -> T:
        try:
            return await asyncio.wait_for(asyncio.to_thread(fn, *args), self.timeout)
        except TimeoutError:
            raise ResolverError("request timed out") from None
        except ResolverError:
            raise
        except Exception as e:
            # v3's gRPC server turned these into an UNKNOWN status, which the client
            # reported as a per-channel failure; keep them from aborting a round.
            log.error("Unexpected resolver error: %s", e)
            raise ResolverError(f"Unexpected error: {e}") from e
