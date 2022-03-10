package main

import (
	"time"

	log "github.com/sirupsen/logrus"
	prefixed "github.com/x-cray/logrus-prefixed-formatter"
	"gopkg.in/yaml.v2"
)

func main() {
	var config []Config
	urls := make(map[string]string)
	confErr := yaml.Unmarshal(readConfig(), &config)

	log.SetFormatter(&prefixed.TextFormatter{FullTimestamp: true})
	log.SetLevel(log.DebugLevel)

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

	control := make(chan bool, len(urls))
	response := make(chan bool, len(urls))

	for user, url := range urls {
		go downloadStream(user, url, control, response)
	}

	log.Debugf("Sleeping...")
	time.Sleep(time.Second * 5)
	close(control)
	for i := 0; i < len(urls); i++ {
		<-response
	}
	time.Sleep(time.Second * 2)
}
