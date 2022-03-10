#!/usr/bin/env python3

import stream_pb2 as pb
import stream_pb2_grpc as pb_grpc
import logging
import grpc


def get_stream(stub):
    res = stub.GetStream(pb.StatusCheck(site="site", user="hottubchick"))
    res.error if res.error else print(f"Status Check for {res.user} was {res.active}")


def run():
    channel = grpc.insecure_channel("localhost:50051")
    stub = pb_grpc.StreamStub(channel)
    stream_status = get_stream(stub)


if __name__ == "__main__":
    logging.basicConfig()
    run()
