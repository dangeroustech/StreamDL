package main

// Config represents a streaming site and its list of channels to monitor.
type Config struct {
	Site      string     `yaml:"site"`
	Streamers []Streamer `yaml:"channels"`
}

// Streamer represents a single channel to monitor, with quality and VOD settings.
type Streamer struct {
	User     string `yaml:"name"`
	Quality  string `yaml:"quality"`
	VOD      bool   `yaml:"vod"`
	VODLimit int    `yaml:"vod_limit"`
}
