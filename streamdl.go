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
	"gopkg.in/yaml.v3"
)

var urls = make(map[string]string)
var c = make(chan os.Signal, 2)

func main() {
	confLoc := flag.String("config", "config.yml", "Location of config file (full path inc filename)")
	outLoc := flag.String("out", "", "Location of output file (folder only, trailing slash)")
	moveLoc := flag.String("move", "", "Location of move file (folder only, trailing slash)")
	tickTime := flag.Int("time", 10, "Time to tick (seconds)")
	subfolder := flag.Bool("subfolder", false, "Add streams to a subfolder with the channel name")
	flag.Parse()

	var ticker = time.NewTicker(time.Second * time.Duration(*tickTime))
	var config []Config
	confErr := yaml.Unmarshal(readConfig(*confLoc), &config)
	control := make(chan bool, len(config[0].Streamers))
	response := make(chan bool, len(config[0].Streamers))
	ll, err := log.ParseLevel(os.Getenv("LOG_LEVEL"))

	signal.Notify(c, os.Interrupt, syscall.SIGTERM, syscall.SIGINT)
	log.SetFormatter(&prefixed.TextFormatter{FullTimestamp: true})
	if err != nil {
		log.SetLevel(ll)
	} else {
		log.SetLevel(log.TraceLevel)
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
		for _, site := range config {
			for _, streamer := range site.Streamers {
				_, exists := urls[streamer.User]
				if !exists {
					url, err := getStream(site.Site, streamer.User, streamer.Quality)
					if err == nil {
						urls[streamer.User] = url
						go downloadStream(streamer.User, url, *outLoc, *moveLoc, *subfolder, control, response)
					}
				}
			}
		}

		var users []string
		for user := range urls {
			users = append(users, user)
		}
		sort.Strings(users)
		log.Debugf("Currently Live Users: %v", strings.Join(users, ", "))
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
