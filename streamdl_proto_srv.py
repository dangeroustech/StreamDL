#!/usr/bin/env python3

import logging
import os
import threading
from concurrent import futures
from http.server import BaseHTTPRequestHandler, HTTPServer

import grpc
import streamlink
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

import stream_pb2 as pb
import stream_pb2_grpc as pb_grpc

# Configure root logger first to capture all logs, honoring SERVER_LOG_LEVEL
level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
level_value = getattr(logging, level_name, logging.INFO)
logging.basicConfig(
    level=level_value, format="%(asctime)s: |%(levelname)s| %(message)s"
)

# Create a null handler to completely silence loggers
null_handler = logging.NullHandler()

# Set up our application logger first
logger = logging.getLogger("StreamDL")
# Make sure our logger's level matches the environment setting
logger.setLevel(level_value)
# Ensure our logger propagates to the root logger (which has the console handler)
logger.propagate = True

# Silence other loggers
streamlink_logger = logging.getLogger("streamlink")
streamlink_logger.setLevel(logging.CRITICAL)
streamlink_logger.addHandler(null_handler)
streamlink_logger.propagate = False

yt_dlp_logger = logging.getLogger("yt_dlp")
yt_dlp_logger.setLevel(logging.CRITICAL)
yt_dlp_logger.addHandler(null_handler)
yt_dlp_logger.propagate = False

# Silence any other third-party loggers that might be noisy
for logger_name in logging.root.manager.loggerDict:
    if logger_name != "StreamDL":
        third_party_logger = logging.getLogger(logger_name)
        third_party_logger.setLevel(logging.CRITICAL)
        third_party_logger.addHandler(null_handler)
        third_party_logger.propagate = False

logger.info("StreamDL Server Starting...")
logger.debug("YT-DLP version: %s", yt_dlp.version.__version__)
logger.debug("Streamlink version: %s", streamlink.__version__)


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the health check endpoint."""

    def do_GET(self):
        """Respond to GET requests with 200 OK on /health, 404 otherwise."""
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        """Suppress default HTTP server access logs."""
        return


# Configure yt-dlp logging to match our log level
yt_dlp.utils.std_headers["User-Agent"] = "streamdl"
yt_dlp.utils.bug_reports_message = lambda *args, **kwargs: ""
# Always set these to True to prevent direct console output
yt_dlp_quiet = True
yt_dlp_no_warnings = True


class StreamServicer(pb_grpc.Stream):
    """gRPC servicer that resolves live stream URLs."""

    def GetVods(self, request, context):
        """Enumerate recent VODs for a user on a given site."""
        logger.debug(
            "GetVods request received site=%s user=%s limit=%d",
            request.site,
            request.user,
            request.limit,
        )
        limit = request.limit if request.limit > 0 else 10
        res = get_vods(request.site, request.user, limit)

        if "error" in res:
            error_code = res["error"]
            logger.debug(
                "GetVods failure user=%s error=%s",
                request.user,
                error_code,
            )
            match error_code:
                case 404:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details("User not found or no VODs available")
                case 429:
                    context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
                    context.set_details("Rate limited")
                case _:
                    context.set_code(grpc.StatusCode.INTERNAL)
                    context.set_details("Internal server error")
            return pb.VodResponse(error=error_code)

        vod_infos = []
        for v in res.get("vods", []):
            vod_infos.append(
                pb.VodInfo(
                    id=v["id"],
                    title=v["title"],
                    published_at=v["published_at"],
                    duration_seconds=v["duration_seconds"],
                )
            )

        logger.debug("GetVods success user=%s count=%d", request.user, len(vod_infos))
        context.set_code(grpc.StatusCode.OK)
        return pb.VodResponse(vods=vod_infos)

    def GetStream(self, request, context):
        """Resolve a stream URL for the given site/user/quality and return it via gRPC."""
        logger.debug(
            "GetStream request received site=%s user=%s quality=%s",
            request.site,
            request.user,
            request.quality,
        )
        res = get_stream(request)
        if not res.get("error"):
            context.set_code(grpc.StatusCode.OK)
            logger.debug(
                "GetStream success user=%s",
                request.user,
            )
            return pb.StreamResponse(url=res["url"])
        else:
            error_code = res["error"]
            logger.debug(
                "GetStream failure user=%s site=%s quality=%s error=%s",
                request.user,
                request.site,
                request.quality,
                error_code,
            )
            match error_code:
                case 400:
                    context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                    context.set_details(f"{res['error']} - Invalid request")
                case 403:
                    context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                    context.set_details(f"{res['error']} - Unauthenticated")
                case 404:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details(f"{res['error']} - Not found")
                case 408:
                    context.set_code(grpc.StatusCode.DEADLINE_EXCEEDED)
                    context.set_details(f"{res['error']} - Deadline exceeded")
                case 412:
                    context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                    context.set_details(f"{res['error']} - Failed precondition")
                case 415:
                    context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                    context.set_details(f"{res['error']} - Invalid format")
                case 418:
                    context.set_code(grpc.StatusCode.UNIMPLEMENTED)
                    context.set_details(f"{res['error']} - Unimplemented")
                case 429:
                    context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
                    context.set_details(f"{res['error']} - Resource exhausted")
                case 450:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details(f"{res['error']} - User is offline")
                case 500:
                    context.set_code(grpc.StatusCode.INTERNAL)
                    context.set_details(f"{res['error']} - Internal server error")
                case _:
                    context.set_code(grpc.StatusCode.UNKNOWN)
                    context.set_details(f"{res['error']} - Unknown error")
            return pb.StreamResponse(error=error_code)


def serve():
    """Start the health check HTTP server and gRPC server, then block until termination."""
    # Start HTTP health server
    health_port = 8080
    health_server = HTTPServer(("127.0.0.1", health_port), HealthHandler)
    health_thread = threading.Thread(target=health_server.serve_forever)
    health_thread.daemon = True
    health_thread.start()
    logger.info(f"Health server started on port {health_port}")

    # Start gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb_grpc.add_StreamServicer_to_server(StreamServicer(), server)
    grpc_port = os.environ.get("STREAMDL_GRPC_PORT", "50051")
    bound_port = server.add_insecure_port(f"[::]:{grpc_port}")
    if bound_port == 0:
        raise RuntimeError(f"Failed to bind gRPC server to port {grpc_port}")
    server.start()
    logger.info(f"gRPC server started on port {bound_port}")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down servers...")
        health_server.shutdown()
        server.stop(0)


def get_vods(site, user, limit=10):
    """Enumerate a user's recent VODs using yt-dlp."""
    vod_url = f"https://{site}/{user}/videos"
    logger.debug("Fetching VODs from %s (limit=%d)", vod_url, limit)

    try:
        with yt_dlp.YoutubeDL(
            {
                "quiet": yt_dlp_quiet,
                "no_warnings": yt_dlp_no_warnings,
                "verbose": False,
                "logger": None,
                "extract_flat": "in_playlist",
                "playlistend": limit,
            }
        ) as ydl:
            info = ydl.extract_info(vod_url, download=False)

            if not info or "entries" not in info:
                logger.warning("No VODs found for user %s", user)
                return {"error": 404}

            vods = []
            for entry in info["entries"]:
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

            logger.debug("Found %d VODs for user %s", len(vods), user)
            return {"vods": vods}

    except yt_dlp.utils.DownloadError as e:
        error_str = str(e)
        if "HTTP Error 429" in error_str:
            logger.error("Rate limited fetching VODs for %s", user)
            return {"error": 429}
        elif "HTTP Error 404" in error_str or "does not exist" in error_str:
            logger.warning("User %s not found on %s", user, site)
            return {"error": 404}
        else:
            logger.error("DownloadError fetching VODs for %s: %s", user, e)
            return {"error": 500}
    except Exception as e:
        logger.error("Error fetching VODs for %s: %s", user, e)
        return {"error": 500}


def _extract_url(info_dict):
    """Extract the best stream URL from a yt-dlp info dict.

    When yt-dlp merges formats (e.g. bestvideo+bestaudio), there is no top-level
    'url' key — the URLs live inside 'requested_formats'. We return the video
    stream URL which FFmpeg can connect to directly. Manifest URLs are avoided
    because some CDNs bind their tokens to the originating session.
    """
    url = info_dict.get("url")
    if url:
        return url
    requested = info_dict.get("requested_formats")
    if requested:
        # Prefer the video stream URL
        for rf in requested:
            if rf.get("vcodec") and rf.get("vcodec") != "none":
                return rf.get("url", "")
        return requested[0].get("url", "")
    return ""


def get_stream(r):
    """Resolve a stream URL using Streamlink, falling back to yt-dlp on failure."""
    logger.debug(
        "Resolving stream via Streamlink site=%s user=%s quality=%s",
        r.site,
        r.user,
        r.quality,
    )
    session = Streamlink()
    options = Options()
    options.set("twitch", "twitch-disable-reruns")

    try:
        resolve_url = r.site + "/" + r.user
        logger.debug("Streamlink streams(url=%s)", resolve_url)
        stream = session.streams(url=resolve_url, options=options)

        if not stream:
            logger.warning(f"No streams found for user {r.user}")
            return {"error": 404}
        else:
            try:
                selected_quality = r.quality if r.quality else "best"
                logger.debug(
                    "Selecting quality=%s from available keys=%s",
                    selected_quality,
                    list(stream.keys()),
                )
                return {"url": stream[selected_quality].url}
            except KeyError:
                logger.critical("Stream quality not found - exiting")
                return {"error": 414}
    except NoPluginError:
        logger.debug(f"Streamlink is unable to find a plugin for {r.site}")
        logger.debug("Falling back to yt_dlp")
        # Fallback to yt_dlp
        # Map Streamlink-style quality names to yt-dlp compound format selectors.
        # Bare "best"/"worst" broke in newer yt-dlp for some extractors (e.g. Chaturbate)
        # where formats are split into separate video/audio streams.
        yt_dlp_format_map = {
            "best": "bestvideo*+bestaudio/best",
            "worst": "worstvideo*+worstaudio/worst",
        }
        yt_dlp_format = yt_dlp_format_map.get(
            r.quality, r.quality if r.quality else "bestvideo*+bestaudio/best"
        )
        try:
            with yt_dlp.YoutubeDL(
                {
                    "format": yt_dlp_format,
                    "quiet": yt_dlp_quiet,
                    "no_warnings": yt_dlp_no_warnings,
                    "verbose": False,
                    "logger": None,  # Disable yt-dlp's internal logger
                }
            ) as ydl:
                ytdlp_url = r.site + "/" + r.user
                logger.debug("yt_dlp.extract_info(url=%s)", ytdlp_url)
                info_dict = ydl.extract_info(ytdlp_url, download=False)
                return {"url": _extract_url(info_dict)}
        except GeoRestrictedError as e:
            logger.error(f"GeoRestrictedError: {e}")
            return {"error": 403}
        except UnavailableVideoError as e:
            logger.error(f"UnavailableVideoError: {e}")
            return {"error": 404}
        except ExtractorError as e:
            logger.error(f"ExtractorError: {e}")
            return {"error": 500}
        except DownloadError as e:
            logger.error(f"DownloadError: {e}")
            if "Requested format is not available" in str(e):
                logger.warning(
                    "Format %s not available for %s, retrying with default selection",
                    yt_dlp_format,
                    r.user,
                )
                with yt_dlp.YoutubeDL(
                    {
                        "quiet": yt_dlp_quiet,
                        "no_warnings": yt_dlp_no_warnings,
                        "verbose": False,
                        "logger": None,  # Disable yt-dlp's internal logger
                    }
                ) as ydl_temp:
                    fallback_url = r.site + "/" + r.user
                    logger.debug("yt_dlp.extract_info (fallback) url=%s", fallback_url)
                    info_dict = ydl_temp.extract_info(fallback_url, download=False)
                    url = _extract_url(info_dict)
                    if url:
                        logger.info(
                            "Fallback format selection succeeded for %s", r.user
                        )
                        return {"url": url}
                    logger.error("Fallback format selection returned no URL for %s", r.user)
                    return {"error": 415}  # Format Not Available
            elif "HTTP Error 429: Too Many Requests " in str(e):
                return {"error": 429}  # Too Many Requests
            elif "currently offline" in str(e):
                return {"error": 450}  # offline
            else:
                return {"error": 500}  # Generic Download Error
        except Exception as e:
            logger.error(f"Generic Error: {e}")
            return {"error": 500}  # Generic Error
    except PluginError as err:
        logger.error(f"Plugin error: {err}")
        return {"error": 500}  # Generic Plugin Error


if __name__ == "__main__":
    try:
        serve()
    except KeyboardInterrupt:
        print("\nClosing Due To Keyboard Interrupt...")
