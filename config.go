package main

type Config struct {
	Site      string     `yaml:"site"`
	Streamers []Streamer `yaml:"channels"`
}

type Streamer struct {
	User    string `yaml:"name"`
	Quality string `yaml:"quality"`
}
