package main

import (
	"context"
	"errors"
	"time"

	pb "dangerous.tech/streamdl/protos"
	log "github.com/sirupsen/logrus"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
)

const (
	address = "localhost:50051"
)

func getStream(site string, user string, quality string) (string, error) {
	conn, err := grpc.Dial(address, grpc.WithTransportCredentials(insecure.NewCredentials()), grpc.WithBlock())
	if err != nil {
		log.Fatalf("gRPC Failed to Connect: %v", err)
	}
	defer conn.Close()
	c := pb.NewStreamClient(conn)

	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(time.Second)*time.Millisecond)
	defer cancel()
	msg, err := c.GetStream(ctx, &pb.StreamInfo{Site: site, User: user, Quality: quality})
	if err != nil {
		if e, ok := status.FromError(err); ok {
			log.Debugf("Failed to Get Stream for %v: %v", user, e.Code())
			return "", errors.New("failed to get stream")
		}
	} else {
		log.Tracef("Stream for %v Fetched: %v", user, msg.Url)
	}
	return msg.Url, nil
}
