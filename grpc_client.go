package main

import (
	"context"
	"fmt"
	"log"
	"time"

	pb "dangerous.tech/streamdl/protos"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
	"gopkg.in/yaml.v2"
)

const (
	address = "localhost:50051"
)

func main() {
	var config []Config
	confErr := yaml.Unmarshal(readConfig(), &config)
	if confErr != nil {
		log.Fatalf("error: %v", confErr)
	}
	fmt.Printf("config: %v\n", config)
	for _, site := range config {
		// fmt.Printf("site: %v\n\n", site.Site)
		for _, streamer := range site.Streamers {
			fmt.Printf("streamer: %v\nquality: %v\n", streamer.User, streamer.Quality)
			getStream(site.Site, streamer.User, streamer.Quality)
		}
	}
}

func getStream(site string, user string, quality string) {
	conn, err := grpc.Dial(address, grpc.WithTransportCredentials(insecure.NewCredentials()), grpc.WithBlock())
	if err != nil {
		log.Fatalf("grpc failed to connect: %v", err)
	}
	defer conn.Close()
	c := pb.NewStreamClient(conn)

	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(time.Second)*time.Millisecond)
	defer cancel()
	msg, err := c.GetStream(ctx, &pb.StreamInfo{Site: site, User: user, Quality: quality})
	if err != nil {
		if e, ok := status.FromError(err); ok {
			log.Printf("could not request stream: %v", e.Code())
		}
	} else {
		log.Printf("Stream Fetched: %v", msg.Url)
	}
}
