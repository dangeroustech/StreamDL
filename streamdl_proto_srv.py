#!/usr/bin/env python3

import logging
import os
from concurrent import futures

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

# Configure root logger first to capture all logs
logging.basicConfig(
    level=os.environ.get("SERVER_LOG_LEVEL", "CRITICAL").lower(),
    format="%(asctime)s: |%(levelname)s| %(message)s",
)

# Create a null handler to completely silence loggers
null_handler = logging.NullHandler()

# Set up our application logger first
logger = logging.getLogger("StreamDL")
# Make sure our logger's level matches the environment setting
logger.setLevel(os.environ.get("SERVER_LOG_LEVEL", "CRITICAL").lower())
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

logger.debug("StreamDL Server Starting...")
logger.debug("Log level: %s", os.environ.get("SERVER_LOG_LEVEL", "CRITICAL"))
logger.debug("YT-DLP version: %s", yt_dlp.version.__version__)
logger.debug("Streamlink version: %s", streamlink.__version__)

# Configure yt-dlp logging to match our log level
yt_dlp.utils.std_headers["User-Agent"] = "streamdl"
yt_dlp.utils.bug_reports_message = lambda: ""
# Always set these to True to prevent direct console output
yt_dlp_quiet = True
yt_dlp_no_warnings = True

class StreamServicer(pb_grpc.Stream):
    def GetStream(self, request, context):
        res = get_stream(request)
        if not res.get("error"):
            context.set_code(grpc.StatusCode.OK)
            return pb.StreamResponse(url=res["url"])
        else:
            error_code = res["error"]
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
                    context.set_code(grpc.StatusCode.CANCELLED)
                    context.set_details(f"{res['error']} - Cancelled")
                case _:
                    context.set_code(grpc.StatusCode.UNKNOWN)
                    context.set_details(f"{res['error']} - Unknown error")
            return pb.StreamResponse(error=error_code)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb_grpc.add_StreamServicer_to_server(StreamServicer(), server)
    server.add_insecure_port(f"[::]:{os.environ.get('STREAMDL_GRPC_PORT')}")
    server.start()
    server.wait_for_termination()


def get_stream(r):
    session = Streamlink()
    options = Options()
    options.set("twitch", "twitch-disable-ads")
    options.set("twitch", "twitch-disable-reruns")

    try:
        stream = session.streams(url=(r.site + "/" + r.user), options=options)

        if not stream:
            logger.warning(f"No streams found for user {r.user}")
            return {"error": 404}
        else:
            try:
                return {"url": stream[r.quality if r.quality else "best"].url}
            except KeyError:
                logger.critical("Stream quality not found - exiting")
                return {"error": 414}
    except NoPluginError:
        logger.warning(f"Streamlink is unable to find a plugin for {r.site}")
        logger.warning("Falling back to yt_dlp")
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
                info_dict = ydl.extract_info(r.site + "/" + r.user, download=False)
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
                    info_dict = ydl_temp.extract_info(
                        r.site + "/" + r.user, download=False
                    )
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
