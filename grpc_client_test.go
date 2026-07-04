package main

import (
	"os"
	"testing"
)

// TODO: Figure out a way to pull a definitely active Twitch stream for a 200 test

func TestGetStreamTwitch404(t *testing.T) {
	os.Setenv("STREAMDL_GRPC_ADDR", "localhost")
	defer os.Unsetenv("STREAMDL_GRPC_ADDR")

	os.Setenv("STREAMDL_GRPC_PORT", "50051")
	defer os.Unsetenv("STREAMDL_GRPC_PORT")

	result, _ := getStream("twitch.tv", "ANonExistentUser", "best")

	if result.Video != "" {
		t.Errorf("Test should have not received an URL, got %s", result.Video)
	}
}

func TestGetStreamYouTube404(t *testing.T) {
	os.Setenv("STREAMDL_GRPC_ADDR", "localhost")
	defer os.Unsetenv("STREAMDL_GRPC_ADDR")

	os.Setenv("STREAMDL_GRPC_PORT", "50051")
	defer os.Unsetenv("STREAMDL_GRPC_PORT")

	result, _ := getStream("youtube.com", "ANonExistentUser1234", "best")

	if result.Video != "" {
		t.Errorf("Test should have not received an URL, got %s", result.Video)
	}
}

func TestGetStreamKick404(t *testing.T) {
	os.Setenv("STREAMDL_GRPC_ADDR", "localhost")
	defer os.Unsetenv("STREAMDL_GRPC_ADDR")

	os.Setenv("STREAMDL_GRPC_PORT", "50051")
	defer os.Unsetenv("STREAMDL_GRPC_PORT")

	result, _ := getStream("kick.com", "ANonExistentUser", "best")

	if result.Video != "" {
		t.Errorf("Test should have not received an URL, got %s", result.Video)
	}
}

func TestStreamResolveError(t *testing.T) {
	t.Run("uses status message when present", func(t *testing.T) {
		got := streamResolveError("Requested quality '1080p' not available", "fallback")
		if got.Error() != "Requested quality '1080p' not available" {
			t.Fatalf("unexpected message: %q", got.Error())
		}
	})

	t.Run("falls back for empty message", func(t *testing.T) {
		got := streamResolveError("", "stream not found or offline")
		if got.Error() != "stream not found or offline" {
			t.Fatalf("unexpected message: %q", got.Error())
		}
	})

	t.Run("falls back for unknown error suffix", func(t *testing.T) {
		got := streamResolveError("500 - Unknown error", "failed to get stream")
		if got.Error() != "failed to get stream" {
			t.Fatalf("unexpected message: %q", got.Error())
		}
	})
}

func TestStreamResolveErrorIsUsableAsNotice(t *testing.T) {
	err := streamResolveError("Channel 'offlineuser' is offline", "stream not found or offline")
	if err.Error() != "Channel 'offlineuser' is offline" {
		t.Fatalf("expected offline message, got %q", err.Error())
	}
}
