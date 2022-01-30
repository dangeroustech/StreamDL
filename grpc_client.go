package main

import (
	"context"
	"log"
	"time"

	pb "dangerous.tech/streamdl/protos"
	"google.golang.org/grpc"
)

const (
	address = "localhost:50051"
)

func main() {
	conn, err := grpc.Dial(address, grpc.WithInsecure(), grpc.WithBlock())
	if err != nil {
		log.Fatalf("grpc failed to connect: %v", err)
	}
	defer conn.Close()
	c := pb.NewStreamClient(conn)

	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	msg, err := c.GetStream(ctx, &pb.StreamInfo{Site: "twitch.tv", User: "teampgp", Quality: "best"})
	if err != nil {
		log.Fatalf("could not request stream: %v", err)
	}
	// if msg.Error == nil {
	log.Printf("Stream Fetched: %v", msg.Url)
	// }
}
