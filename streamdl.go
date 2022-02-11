package main

import (
	"fmt"
	"log"

	"gopkg.in/yaml.v2"
)

func main() {
	var config []Config
	urls := make(map[string]string)
	confErr := yaml.Unmarshal(readConfig(), &config)
	if confErr != nil {
		log.Fatalf("Config Error: %v", confErr)
	}
	for _, site := range config {
		for _, streamer := range site.Streamers {
			url, err := getStream(site.Site, streamer.User, streamer.Quality)
			if err == nil {
				urls[streamer.User] = url
			}
		}
	}
	fmt.Println(urls)
}
