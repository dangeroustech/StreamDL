package main

import (
	"context"
	"errors"
	"fmt"
	"os"
	"time"

	pb "dangerous.tech/streamdl/protos"
	log "github.com/sirupsen/logrus"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
)

// VodResult holds metadata for a single VOD returned by the server.
type VodResult struct {
	ID              string
	Title           string
	PublishedAt     string
	DurationSeconds int64
}

// getVods calls the gRPC server to list recent VODs for a user on the given site.
func getVods(site string, user string, limit int) ([]VodResult, error) {
	addr := os.Getenv("STREAMDL_GRPC_ADDR")
	if addr == "" {
		addr = "server"
	}
	port := os.Getenv("STREAMDL_GRPC_PORT")
	if port == "" {
		port = "50051"
	}
	log.Debugf("Dialing gRPC server %s:%s for VODs", addr, port)
	conn, err := grpc.NewClient(addr+":"+port, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return nil, fmt.Errorf("gRPC failed to connect to %s:%s: %w", addr, port, err)
	}
	defer func() {
		if err := conn.Close(); err != nil {
			log.Errorf("Error closing gRPC connection: %v", err)
		}
	}()
	c := pb.NewStreamClient(conn)

	timeout := time.Second * 30
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	log.Debugf("Calling GetVods site=%s user=%s limit=%d", site, user, limit)
	msg, err := c.GetVods(ctx, &pb.VodRequest{Site: site, User: user, Limit: int32(limit)}, grpc.WaitForReady(true))
	if err != nil {
		if e, ok := status.FromError(err); ok {
			log.Errorf("GetVods failed for %s: %s", user, e.Message())
			switch e.Code() {
			case codes.NotFound:
				return nil, errors.New("user not found or no VODs available")
			case codes.ResourceExhausted:
				return nil, errors.New("rate limited")
			default:
				return nil, fmt.Errorf("GetVods failed: %s", e.Code().String())
			}
		}
		return nil, err
	}

	if msg.GetError() != 0 {
		return nil, fmt.Errorf("server returned error code: %d", msg.GetError())
	}

	var results []VodResult
	for _, v := range msg.GetVods() {
		results = append(results, VodResult{
			ID:              v.GetId(),
			Title:           v.GetTitle(),
			PublishedAt:     v.GetPublishedAt(),
			DurationSeconds: v.GetDurationSeconds(),
		})
	}

	log.Debugf("GetVods returned %d VODs for %s", len(results), user)
	return results, nil
}

// StreamURLs holds the resolved video and optional audio stream URLs.
type StreamURLs struct {
	Video string
	Audio string
}

// getStream calls the gRPC server to resolve a stream URL for the given site, user, and quality.
func getStream(site string, user string, quality string) (StreamURLs, error) {
	addr := os.Getenv("STREAMDL_GRPC_ADDR")
	if addr == "" {
		addr = "server"
	}
	port := os.Getenv("STREAMDL_GRPC_PORT")
	if port == "" {
		port = "50051"
	}
	log.Debugf("Dialing gRPC server %s:%s", addr, port)
	conn, err := grpc.NewClient(addr+":"+port, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return StreamURLs{}, fmt.Errorf("gRPC failed to connect to %s:%s: %w", addr, port, err)
	}
	defer func() {
		if err := conn.Close(); err != nil {
			log.Errorf("Error closing gRPC connection: %v", err)
		}
	}()
	c := pb.NewStreamClient(conn)

	log.Debugf("gRPC connection established to %s:%s", addr, port)

	timeout := time.Second * 30
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	log.Debugf("Calling GetStream site=%s user=%s quality=%s timeout=%s", site, user, quality, timeout.String())
	msg, err := c.GetStream(ctx, &pb.StreamInfo{Site: site, User: user, Quality: quality}, grpc.WaitForReady(true))
	if err != nil {
		if e, ok := status.FromError(err); ok {
			statusCode := e.Code()
			statusMessage := e.Message()
			log.Errorf("Failed to Get Stream for %v: %s", user, statusMessage)

			switch statusCode {
			case codes.NotFound:
				return StreamURLs{}, errors.New("stream not found or offline")
			case codes.DeadlineExceeded:
				return StreamURLs{}, errors.New("request timed out")
			case codes.Unavailable:
				return StreamURLs{}, errors.New("service unavailable")
			case codes.ResourceExhausted:
				return StreamURLs{}, errors.New("rate limited")
			default:
				return StreamURLs{}, errors.New("failed to get stream: " + statusCode.String())
			}
		}
		log.Errorf("GetStream RPC failed (non-gRPC error) for user=%s: %v", user, err)
		return StreamURLs{}, err
	} else {
		if msg.GetError() != 0 {
			log.Debugf("Server returned error code: %d", msg.GetError())
			return StreamURLs{}, errors.New("server error")
		}
		log.Tracef("Stream for %v Fetched: %v", user, msg.Url)
	}
	return StreamURLs{Video: msg.Url, Audio: msg.GetAudioUrl()}, nil
}
