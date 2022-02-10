package main

import (
	"context"
	"flag"
	"log"
	"time"

	pb "dangerous.tech/streamdl/protos"
	"google.golang.org/grpc"
	"google.golang.org/grpc/status"
)

const (
	address = "localhost:50051"
)

func main() {
	deadlineMs := flag.Int("deadline_ms", 20*1000, "Default deadline in milliseconds.")
	conn, err := grpc.Dial(address, grpc.WithInsecure(), grpc.WithBlock())
	if err != nil {
		log.Fatalf("grpc failed to connect: %v", err)
	}
	defer conn.Close()
	c := pb.NewStreamClient(conn)

	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(*deadlineMs)*time.Millisecond)
	defer cancel()
	msg, err := c.GetStream(ctx, &pb.StreamInfo{Site: "twitch.tv", User: "teampgp", Quality: "best"})
	if err != nil {
		if e, ok := status.FromError(err); ok {
			log.Fatalf("could not request stream: %v", e.Code())
		}
	}
	// if msg.Error == nil {
	log.Printf("Stream Fetched: %v", msg.Url)
	// }
}
