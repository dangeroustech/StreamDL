#!/usr/bin/env python3

import logging
import os
import time
from concurrent import futures

import grpc
import yt_dlp
from streamlink.exceptions import NoPluginError, PluginError
from streamlink.options import Options
from streamlink.session import Streamlink

import stream_pb2 as pb
import stream_pb2_grpc as pb_grpc

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "DEBUG").lower(),
    format="%(asctime)s: |%(levelname)s| %(message)s",
)

logger = logging.getLogger("StreamDL")
logger.debug("StreamDL Starting...")


class StreamServicer(pb_grpc.Stream):
    def GetStream(self, request, context):
        res = get_stream(request)
        if not res.get("error"):
            context.set_code(grpc.StatusCode.OK)
            return pb.StreamResponse(url=res["url"])
        else:
            match res["error"]:
                case 400:
                    context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                case 403:
                    context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                case 404:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                case 408:
                    context.set_code(grpc.StatusCode.DEADLINE_EXCEEDED)
                case 412:
                    context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                case 418:
                    context.set_code(grpc.StatusCode.UNIMPLEMENTED)
                case _:
                    context.set_code(grpc.StatusCode.UNKNOWN)
            return pb.StreamResponse()


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
                {"format": r.quality if r.quality else "best"}
            ) as ydl:
                info_dict = ydl.extract_info(r.site + "/" + r.user, download=False)
                return {"url": info_dict.get("url", "")}
        except yt_dlp.utils.DownloadError as e:
            if "Requested format is not available" in str(e):
                with yt_dlp.YoutubeDL() as ydl_temp:
                    info_dict = ydl_temp.extract_info(
                        r.site + "/" + r.user, download=False
                    )
                    logger.error("Requested format is not available")
                    logger.error("Available formats:")
                    # List available formats
                    formats = info_dict.get("formats", [])
                    for f in formats:
                        logger.error(
                            f"Format code: {f['format_id']}, resolution: {f['width']}x{f['height']}"
                        )
                    return {"error": "FormatNotAvailableError"}
            elif "HTTP Error 429: Too Many Requests " in str(e):
                logger.error("Too many requests - sleeping for 30 seconds")
                time.sleep(30)
                return {"error": "TooManyRequestsError"}
            else:
                logger.error(f"Download error: {e}")
                return {"error": "DownloadError"}
        except yt_dlp.utils.ExtractorError as e:
            logger.error(f"Extractor error: {e}")
            return {"error": "ExtractorError"}
        except yt_dlp.utils.GeoRestrictedError as e:
            logger.error(f"Geo-restricted error: {e}")
            return {"error": "GeoRestrictedError"}
        except yt_dlp.utils.AgeRestrictedError as e:
            logger.error(f"Age-restricted error: {e}")
            return {"error": "AgeRestrictedError"}
        except yt_dlp.utils.UnavailableVideoError as e:
            logger.error(f"Unavailable video error: {e}")
            return {"error": "UnavailableVideoError"}
        except yt_dlp.utils.YoutubeDLError as e:
            logger.error(f"yt_dlp error: {e}")
            return {"error": "YoutubeDLError"}
        except Exception as e:
            logger.error(f"yt_dlp error: {e}")
            return {"error": "UnknownError"}
    except PluginError as err:
        logger.error(f"Plugin error: {err}")
        return {"error": 102}


if __name__ == "__main__":
    try:
        serve()
    except KeyboardInterrupt:
        print("\nClosing Due To Keyboard Interrupt...")
