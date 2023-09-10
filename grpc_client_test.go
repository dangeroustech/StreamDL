package main

import (
	"os"
	"testing"
)

// TODO: Figure out a way to pull a definitely active Twitch stream for a 200 test

func TestGetStreamTwitch404(t *testing.T) {
	// would be good to actually return a status code
	// from getStream so that we can actually
	// match to the status code when testing
	os.Setenv("STREAMDL_GRPC_ADDR", "localhost")
	defer os.Unsetenv("STREAMDL_GRPC_ADDR")

	os.Setenv("STREAMDL_GRPC_PORT", "50051")
	defer os.Unsetenv("STREAMDL_GRPC_PORT")

	url, _ := getStream("twitch.tv", "ANonExistentUser", "best")

	if url != "" {
		t.Errorf("Test should have not received an URL, got %s", url)
	}
}

func TestGetStreamYouTube404(t *testing.T) {
	os.Setenv("STREAMDL_GRPC_ADDR", "localhost")
	defer os.Unsetenv("STREAMDL_GRPC_ADDR")

	os.Setenv("STREAMDL_GRPC_PORT", "50051")
	defer os.Unsetenv("STREAMDL_GRPC_PORT")

	url, _ := getStream("youtube.com", "ANonExistentUser", "best")

	if url != "" {
		t.Errorf("Test should have not received an URL, got %s", url)
	}
}

func TestGetStreamKick404(t *testing.T) {
	// Kick is not actually yet supported
	// But it follows the Twitch style
	// site/channel naming format
	os.Setenv("STREAMDL_GRPC_ADDR", "localhost")
	defer os.Unsetenv("STREAMDL_GRPC_ADDR")

	os.Setenv("STREAMDL_GRPC_PORT", "50051")
	defer os.Unsetenv("STREAMDL_GRPC_PORT")

	url, _ := getStream("kick.com", "ANonExistentUser", "best")

	if url != "" {
		t.Errorf("Test should have not received an URL, got %s", url)
	}
}
