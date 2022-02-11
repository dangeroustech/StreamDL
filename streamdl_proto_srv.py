#!/usr/bin/env python3

import logging
from yt_dlp import YoutubeDL as ytdl
from yt_dlp import utils as ytdl_utils
from streamlink import Streamlink, PluginError, NoPluginError
import stream_pb2 as pb
import stream_pb2_grpc as pb_grpc
from concurrent import futures
import grpc


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
    server.add_insecure_port("[::]:50051")
    server.start()
    server.wait_for_termination()


def get_stream(r):
    session = Streamlink()
    session.set_plugin_option("twitch", "twitch-disable-ads", True)
    session.set_plugin_option("twitch", "twitch-disable-reruns", True)
    session.set_plugin_option("twitch", "twitch-disable-hosting", True)

    try:
        stream = session.streams(url=(r.site + "/" + r.user))

        if not stream:
            # logger.warning(f"No streams found for user {user}")
            return {"error": 404}
        else:
            try:
                return {"url": stream[r.quality if r.quality else "best"].url}
            except KeyError:
                # logger.critical("Stream quality not found - exiting")
                return {"error": 414}
    except NoPluginError:
        # logger.warning(f"Streamlink is unable to handle the {url}")
        return {"error": 101}
    except PluginError as err:
        # logger.warning(f"Plugin error: {err}")
        return {"error": 102}


if __name__ == "__main__":
    logging.basicConfig()
    try:
        serve()
    except KeyboardInterrupt as e:
        print("\nClosing Due To Keyboard Interrupt...")
