#!/usr/bin/env python3

import logging
import os
from streamlink.exceptions import PluginError, NoPluginError
from streamlink.session import Streamlink
from streamlink.options import Options
import stream_pb2 as pb
import stream_pb2_grpc as pb_grpc
from concurrent import futures
import grpc


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
        logger.warning(f"Streamlink is unable to handle the {r.url}")
        return {"error": 101}
    except PluginError as err:
        logger.warning(f"Plugin error: {err}")
        return {"error": 102}


if __name__ == "__main__":
    try:
        serve()
    except KeyboardInterrupt as e:
        print("\nClosing Due To Keyboard Interrupt...")
