// Package main implements StreamDL, a daemon that monitors configured streaming
// sites and automatically records live streams and VODs via FFmpeg.
package main

import (
	"flag"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"syscall"
	"time"

	log "github.com/sirupsen/logrus"
	prefixed "github.com/x-cray/logrus-prefixed-formatter"
)

var (
	urls   = make(map[string]string)
	urlsMu sync.RWMutex
	vodWg  sync.WaitGroup
)
var c = make(chan os.Signal, 2)

func main() {
	confLoc := flag.String("config", "config.yml", "Location of config file (full path inc filename)")
	outLoc := flag.String("out", "", "Location of output file (folder only, trailing slash)")
	moveLoc := flag.String("move", "", "Location of move file (folder only, trailing slash)")
	tickTime := flag.Int("time", 60, "Time to tick (seconds)")
	batchTime := flag.Int("batch", 5, "Time betwen URL checks (seconds): increase for rate limiting")
	subfolder := flag.Bool("subfolder", false, "Add streams to a subfolder with the channel name")
	logLevel := flag.String("log-level", "info", "Log level (trace, debug, info, warn, error, fatal, panic)")
	dataDir := flag.String("data", "/app/data", "Directory for persistent data (VOD tracking database)")
	vodOutLoc := flag.String("vod-out", "", "Output location for VOD downloads (defaults to -out)")
	vodMoveLoc := flag.String("vod-move", "", "Move location for completed VOD downloads (defaults to -move)")
	flag.Parse()

	// Default VOD paths to the same as live stream paths if not specified
	if *vodOutLoc == "" {
		vodOutLoc = outLoc
	}
	if *vodMoveLoc == "" {
		vodMoveLoc = moveLoc
	}

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

	// VOD database is lazily initialized on first VOD tick
	var vodDB *VodDB
	defer func() {
		if vodDB != nil {
			vodDB.Close()
		}
	}()

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
			log.Warnf("Config reload failed; keeping previous config: %v", confErr)
		} else {
			config = parsed
		}

		// TODO: Probably make a nicer 429 handling to allow for counts, retry queueing, etc.
		for _, site := range config {
			for _, streamer := range site.Streamers {
				log.Debugf("Checking user=%s on site=%s quality=%s vod=%v", streamer.User, site.Site, streamer.Quality, streamer.VOD)

				if streamer.VOD {
					// Lazy init VOD database on first use
					if vodDB == nil {
						var initErr error
						vodDB, initErr = InitVodDB(filepath.Join(*dataDir, "streamdl.db"))
						if initErr != nil {
							log.Errorf("Failed to initialize VOD database: %v", initErr)
							continue
						}
						log.Infof("VOD tracking database initialized at %s", filepath.Join(*dataDir, "streamdl.db"))
					}

					// VOD mode: check for new VODs to download
					limit := streamer.VODLimit
					if limit <= 0 {
						limit = 10
					}
					vods, err := getVods(site.Site, streamer.User, limit)
					time.Sleep(time.Second * time.Duration(*batchTime))
					if err != nil {
						if err.Error() == "rate limited" {
							log.Errorf("Rate limited checking VODs for %s, skipping", streamer.User)
						} else {
							log.Warnf("GetVods failed for user=%s: %v", streamer.User, err)
						}
						continue
					}
					// Stale threshold: 2× tick interval, minimum 10 minutes
					staleThreshold := time.Duration(*tickTime) * time.Second * 2
					if staleThreshold < 10*time.Minute {
						staleThreshold = 10 * time.Minute
					}
					for _, vod := range vods {
						claimed, err := vodDB.ClaimVOD(vod.ID, streamer.User, site.Site, vod.Title, staleThreshold)
						if err != nil {
							log.Errorf("Error claiming VOD %s: %v", vod.ID, err)
							continue
						}
						if !claimed {
							log.Tracef("VOD %s already completed or in progress, skipping", vod.ID)
							continue
						}
						log.Infof("VOD to download for %s: %s (%s)", streamer.User, vod.Title, vod.ID)
						// Resolve the VOD URL through GetStream (Streamlink → yt-dlp fallback)
						resolvedURL, err := getStream(site.Site, "videos/"+vod.ID, streamer.Quality)
						time.Sleep(time.Second * time.Duration(*batchTime))
						if err != nil {
							log.Warnf("Failed to resolve VOD %s: %v", vod.ID, err)
							if markErr := vodDB.MarkVODFailed(vod.ID); markErr != nil {
								log.Errorf("Failed to mark VOD %s as failed: %v", vod.ID, markErr)
							}
							continue
						}
						vodWg.Add(1)
						go func() {
							defer vodWg.Done()
							downloadVOD(streamer.User, vod, resolvedURL, *vodOutLoc, *vodMoveLoc, *subfolder, vodDB, control)
						}()
					}
				} else {
					// Live stream mode (existing behavior)
					urlsMu.RLock()
					_, exists := urls[streamer.User]
					urlsMu.RUnlock()
					if !exists {
						log.Tracef("No active URL cached for %s; requesting new stream URL", streamer.User)
						backoffs := []time.Duration{0, 30 * time.Second, 60 * time.Second}

						for attempt := range backoffs {
							if backoffs[attempt] > 0 {
								log.Errorf("Rate Limited, Sleeping for %v", backoffs[attempt])
								time.Sleep(backoffs[attempt])
							}

							url, err := getStream(site.Site, streamer.User, streamer.Quality)
							if attempt == 0 {
								time.Sleep(time.Second * time.Duration(*batchTime))
							}

							if err == nil {
								urlsMu.Lock()
								urls[streamer.User] = url
								urlsMu.Unlock()
								log.Debugf("Discovered live stream for user=%s", streamer.User)
								go downloadStream(streamer.User, url, *outLoc, *moveLoc, *subfolder, control, response)
								break
							}

							if err.Error() != "rate limited" {
								log.Warnf("GetStream failed for user=%s: %v", streamer.User, err)
								break
							}

							if attempt == len(backoffs)-1 {
								log.Errorf("Rate Limited Thrice, Skipping %v", streamer.User)
							}
						}
					}
				}
			}
		}

		urlsMu.RLock()
		var users []string
		for user := range urls {
			users = append(users, user)
		}
		urlsMu.RUnlock()
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

			urlsMu.RLock()
			urlsLen := len(urls)
			urlsMu.RUnlock()
			for i := 0; i < urlsLen; i++ {
				<-response
			}
			vodWg.Wait()
			time.Sleep(time.Second * 3)
			return
		case t := <-ticker.C:
			// block until we tick
			log.Tracef("Ticking: %v", t)
		}
	}
}
