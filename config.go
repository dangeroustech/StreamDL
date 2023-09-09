package main

// Config defines the root type
type Config struct {
	Site      string     `yaml:"site"`
	Streamers []Streamer `yaml:"channels"`
}

// Streamer definition
type Streamer struct {
	User    string `yaml:"name"`
	Quality string `yaml:"quality"`
}
