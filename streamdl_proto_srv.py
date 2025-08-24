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
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress default HTTP server logs to avoid noise
        return


# Configure yt-dlp logging to match our log level
yt_dlp.utils.std_headers["User-Agent"] = "streamdl"
yt_dlp.utils.bug_reports_message = lambda *args, **kwargs: ""
# Always set these to True to prevent direct console output
yt_dlp_quiet = True
yt_dlp_no_warnings = True


class StreamServicer(pb_grpc.Stream):
    def GetStream(self, request, context):
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
                "GetStream success user=%s url=%s",
                request.user,
                res["url"],
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
    # Start HTTP health server
    health_port = 8080
    # Bind to all interfaces for container networking (safe in isolated container environment)
    health_server = HTTPServer(("0.0.0.0", health_port), HealthHandler)  # nosec B104
    health_thread = threading.Thread(target=health_server.serve_forever)
    health_thread.daemon = True
    health_thread.start()
    logger.info(f"Health server started on port {health_port}")

    # Start gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb_grpc.add_StreamServicer_to_server(StreamServicer(), server)
    server.add_insecure_port(f"[::]:{os.environ.get('STREAMDL_GRPC_PORT')}")
    server.start()
    logger.info(f"gRPC server started on port {os.environ.get('STREAMDL_GRPC_PORT')}")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down servers...")
        health_server.shutdown()
        server.stop(0)


def get_stream(r):
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
        try:
            with yt_dlp.YoutubeDL(
                {
                    "format": r.quality if r.quality else "best",
                    "quiet": yt_dlp_quiet,
                    "no_warnings": yt_dlp_no_warnings,
                    "verbose": False,
                    "logger": None,  # Disable yt-dlp's internal logger
                }
            ) as ydl:
                ytdlp_url = r.site + "/" + r.user
                logger.debug("yt_dlp.extract_info(url=%s)", ytdlp_url)
                info_dict = ydl.extract_info(ytdlp_url, download=False)
                return {"url": info_dict.get("url", "")}
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
                    logger.critical("Requested format is not available")
                    logger.critical("Available formats:")
                    # List available formats
                    formats = info_dict.get("formats", [])
                    for f in formats:
                        logger.critical(
                            f"Format code: {f['format_id']}, resolution: {f['width']}x{f['height']}"
                        )
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
