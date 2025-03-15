package main

import (
	"context"
	"errors"
	"os"
	"time"

	pb "dangerous.tech/streamdl/protos"
	log "github.com/sirupsen/logrus"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
)

func getStream(site string, user string, quality string) (string, error) {
	conn, err := grpc.Dial(os.Getenv("STREAMDL_GRPC_ADDR")+":"+os.Getenv("STREAMDL_GRPC_PORT"), grpc.WithTransportCredentials(insecure.NewCredentials()), grpc.WithBlock())
	if err != nil {
		log.Fatalf("gRPC Failed to Connect: %v", err)
	}
	defer conn.Close()
	c := pb.NewStreamClient(conn)

	ctx, cancel := context.WithTimeout(context.Background(), time.Second*10)
	defer cancel()
	msg, err := c.GetStream(ctx, &pb.StreamInfo{Site: site, User: user, Quality: quality})
	if err != nil {
		if e, ok := status.FromError(err); ok {
			statusCode := e.Code()
			statusMessage := e.Message()
			log.Errorf("Failed to Get Stream for %v: %v", user, statusMessage)

			switch statusCode {
			case codes.NotFound:
				return "", errors.New("stream not found or offline")
			case codes.DeadlineExceeded:
				return "", errors.New("request timed out")
			case codes.Unavailable:
				return "", errors.New("service unavailable")
			case codes.ResourceExhausted:
				return "", errors.New("rate limited")
			default:
				return "", errors.New("failed to get stream: " + statusCode.String())
			}
		}
		return "", err
	} else {
		if msg.GetError() != 0 {
			log.Debugf("Server returned error code: %d", msg.GetError())
			return "", errors.New("server error")
		}
		log.Tracef("Stream for %v Fetched: %v", user, msg.Url)
	}
	return msg.Url, nil
}
