package main

type Config struct {
	Site      string     `yaml:"site"`
	Streamers []Streamer `yaml:"streamers"`
}

type Streamer struct {
	User    string `yaml:"channel"`
	Quality string `yaml:"quality"`
}
