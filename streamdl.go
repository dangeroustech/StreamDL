package main

import (
	"os"
	"os/signal"
	"syscall"
	"time"

	log "github.com/sirupsen/logrus"
	prefixed "github.com/x-cray/logrus-prefixed-formatter"
	"gopkg.in/yaml.v3"
)

var urls = make(map[string]string)
var c = make(chan os.Signal, 2)
var ticker = time.NewTicker(time.Second * 5)

func main() {
	var config []Config
	confErr := yaml.Unmarshal(readConfig(), &config)
	control := make(chan bool, len(config[0].Streamers))
	response := make(chan bool, len(config[0].Streamers))

	signal.Notify(c, os.Interrupt, syscall.SIGTERM, syscall.SIGINT)
	log.SetFormatter(&prefixed.TextFormatter{FullTimestamp: true})
	log.SetLevel(log.TraceLevel)
	log.Infof("Starting StreamDL...")

	if confErr != nil {
		log.Fatalf("Config Error: %v", confErr)
	}
	log.Tracef("Config: %v", config)
	for {
		for _, site := range config {
			for _, streamer := range site.Streamers {
				_, exists := urls[streamer.User]
				if !exists {
					url, err := getStream(site.Site, streamer.User, streamer.Quality)
					if err == nil {
						urls[streamer.User] = url
						go downloadStream(streamer.User, url, control, response)
					}
				}
			}
		}

		var users []string
		for user := range urls {
			users = append(users, user)
		}
		log.Debugf("Currently Live Users: %v", users)
		log.Tracef("Sleeping...")

		select {
		case <-c:
			log.Trace("Catching CTRL + C")
			log.Tracef("Stopping Ticker")
			ticker.Stop()
			log.Tracef("Ticker Stopped")
			log.Tracef("Closing Control Channel")
			close(control)

			for i := 0; i < len(urls); i++ {
				<-response
			}
			time.Sleep(time.Second * 3)
			os.Exit(0)
		case t := <-ticker.C:
			// block until we tick
			log.Tracef("Ticking Like Adam Curry: %v", t)
		}
	}
}
