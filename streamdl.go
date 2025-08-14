package main

import (
	"flag"
	"net/http"
	"os"
	"os/signal"
	"sort"
	"strings"
	"syscall"
	"time"

	log "github.com/sirupsen/logrus"
	prefixed "github.com/x-cray/logrus-prefixed-formatter"
)

var urls = make(map[string]string)
var c = make(chan os.Signal, 2)

func main() {
	confLoc := flag.String("config", "config.yml", "Location of config file (full path inc filename)")
	outLoc := flag.String("out", "", "Location of output file (folder only, trailing slash)")
	moveLoc := flag.String("move", "", "Location of move file (folder only, trailing slash)")
	tickTime := flag.Int("time", 60, "Time to tick (seconds)")
	batchTime := flag.Int("batch", 5, "Time betwen URL checks (seconds): increase for rate limiting")
	subfolder := flag.Bool("subfolder", false, "Add streams to a subfolder with the channel name")
	logLevel := flag.String("log-level", "info", "Log level (trace, debug, info, warn, error, fatal, panic)")
	flag.Parse()

	var ticker = time.NewTicker(time.Second * time.Duration(*tickTime))
    var config []Config
    parsed, confErr := parseConfig(readConfig(*confLoc))
    if confErr == nil {
        config = parsed
    }
	control := make(chan bool)
	response := make(chan bool)

	signal.Notify(c, os.Interrupt, syscall.SIGTERM, syscall.SIGINT)
	log.SetFormatter(&prefixed.TextFormatter{FullTimestamp: true})

	ll, err := log.ParseLevel(*logLevel)
	if err != nil {
		log.Warnf("Invalid log level '%s', defaulting to info", *logLevel)
		log.SetLevel(log.InfoLevel)
	} else {
		log.SetLevel(ll)
	}
	log.Infof("Starting StreamDL...")
	log.Tracef("Config: %v", config)

	if confErr != nil {
		log.Fatalf("Config Error: %v", confErr)
	}

	go func() {
		http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(http.StatusOK)
			_, err := w.Write([]byte("OK"))
			if err != nil {
				log.Errorf("Error writing response: %v", err)
			}
		})

		log.Fatal(http.ListenAndServe(":8080", nil))
	}()

	for {
		log.Infof("-----------------------------------------")
		log.Infof("Running StreamDL at %v", time.Now().Format("2006-01-02 15:04:05"))
		log.Infof("-----------------------------------------")
        // Update config for each tick
        parsed, confErr := parseConfig(readConfig(*confLoc))
		if confErr != nil {
			log.Fatalf("Config Error: %v", confErr)
        } else {
            config = parsed
		}

		// TODO: Probably make a nicer 429 handling to allow for counts, retry queueing, etc.
		for _, site := range config {
			for _, streamer := range site.Streamers {
				log.Debugf("Checking user=%s on site=%s quality=%s", streamer.User, site.Site, streamer.Quality)
				_, exists := urls[streamer.User]
				if !exists {
					log.Tracef("No active URL cached for %s; requesting new stream URL", streamer.User)
					url, err := getStream(site.Site, streamer.User, streamer.Quality)
					time.Sleep(time.Second * time.Duration(*batchTime))
					if err == nil {
						urls[streamer.User] = url
						log.Debugf("Discovered live stream: user=%s url=%s", streamer.User, url)
						go downloadStream(streamer.User, url, *outLoc, *moveLoc, *subfolder, control, response)
					} else if err.Error() == "rate limited" {
						log.Errorf("Rate Limited, Sleeping for 30 seconds")
						time.Sleep(time.Second * 30)
						url, err := getStream(site.Site, streamer.User, streamer.Quality)
						if err == nil {
							urls[streamer.User] = url
							go downloadStream(streamer.User, url, *outLoc, *moveLoc, *subfolder, control, response)
						} else if err.Error() == "rate limited" {
							log.Errorf("Rate Limited, Sleeping for 60 seconds")
							time.Sleep(time.Second * 60)
							url, err := getStream(site.Site, streamer.User, streamer.Quality)
							if err == nil {
								urls[streamer.User] = url
								go downloadStream(streamer.User, url, *outLoc, *moveLoc, *subfolder, control, response)
							}
						} else if err.Error() == "rate limited" {
							log.Errorf("Rate Limited Thrice, Skipping %v", streamer.User)
						} else {
							log.Warnf("GetStream failed for user=%s: %v", streamer.User, err)
						}
					}
				}
			}
		}

		var users []string
		for user := range urls {
			users = append(users, user)
		}
		sort.Strings(users)
		log.Infof("Currently Live Users: %v", strings.Join(users, ", "))
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
			log.Tracef("Ticking: %v", t)
		}
	}
}
