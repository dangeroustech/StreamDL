// Package main implements StreamDL, a daemon that monitors configured streaming
// sites and automatically records live streams and VODs via FFmpeg.
package main

import (
	"flag"
	"fmt"
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
	activeUsers    = make(map[string]bool)
	activeUsersMu  sync.RWMutex
	downloadWg     sync.WaitGroup
	vodWg          sync.WaitGroup
	postScriptWg   sync.WaitGroup
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
							tickNotices.Error(streamer.User, "Rate limited checking VODs, skipping this tick")
						} else {
							tickNotices.Warn(streamer.User, fmt.Sprintf("GetVods failed: %v", err))
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
						resolveMu := getSiteResolveMu(site.Site)
						resolveMu.Lock()
						resolved, err := getStream(site.Site, vodStreamUser(vod.ID), streamer.Quality)
						resolveMu.Unlock()
						time.Sleep(time.Second * time.Duration(*batchTime))
						if err != nil {
							tickNotices.Warn(streamer.User, fmt.Sprintf("Failed to resolve VOD %s: %v", vod.ID, err))
							if markErr := vodDB.MarkVODFailed(vod.ID); markErr != nil {
								log.Errorf("Failed to mark VOD %s as failed: %v", vod.ID, markErr)
							}
							continue
						}
						vodWg.Add(1)
						go func() {
							defer vodWg.Done()
							downloadVOD(streamer.User, vod, resolved.Video, *vodOutLoc, *vodMoveLoc, *subfolder, site.Site, site.PostScript, vodDB, control)
						}()
					}
				} else {
					// Live stream mode: probe liveness first, only launch goroutine for live users
					activeUsersMu.RLock()
					_, exists := activeUsers[streamer.User]
					activeUsersMu.RUnlock()
					if !exists {
						log.Tracef("No active download for %s; checking if online", streamer.User)
						backoffs := []time.Duration{0, 30 * time.Second, 60 * time.Second}

						for attempt := range backoffs {
							if backoffs[attempt] > 0 {
								log.Errorf("Rate Limited, Sleeping for %v", backoffs[attempt])
								time.Sleep(backoffs[attempt])
							}

							// Probe whether the user is live and capture the URL for the
							// initial FFmpeg attempt. Retries inside downloadStream will
							// resolve a fresh URL in case the token expires.
							resolveMu := getSiteResolveMu(site.Site)
							resolveMu.Lock()
							probeResult, err := getStream(site.Site, streamer.User, streamer.Quality)
							resolveMu.Unlock()
							if attempt == 0 {
								time.Sleep(time.Second * time.Duration(*batchTime))
							}

							if err == nil {
								activeUsersMu.Lock()
								activeUsers[streamer.User] = true
								activeUsersMu.Unlock()
								log.Debugf("Discovered live stream for user=%s", streamer.User)
								if probeResult.Warning != "" {
									tickNotices.Warn(streamer.User, probeResult.Warning)
								}
								downloadWg.Add(1)
								go func() {
									defer downloadWg.Done()
									downloadStream(streamer.User, site.Site, streamer.Quality, probeResult, *outLoc, *moveLoc, *subfolder, site.PostScript, control)
								}()
								break
							}

							if err.Error() != "rate limited" {
								tickNotices.Warn(streamer.User, err.Error())
								break
							}

							if attempt == len(backoffs)-1 {
								tickNotices.Error(streamer.User, "Rate limited three times, skipping this tick")
							}
						}
					}
				}
			}
		}

		activeUsersMu.RLock()
		var users []string
		for user := range activeUsers {
			users = append(users, user)
		}
		activeUsersMu.RUnlock()
		sort.Strings(users)
		log.Infof("Currently Live Users: %v", strings.Join(users, ", "))
		logActiveDownloadSummary(downloadProgress)
		tickNotices.Flush(*tickTime)

		select {
		case <-c:
			log.Trace("Catching CTRL + C")
			log.Tracef("Stopping Ticker")
			ticker.Stop()
			log.Tracef("Ticker Stopped")
			log.Tracef("Closing Control Channel")
			close(control)
			downloadWg.Wait()
			vodWg.Wait()
			postScriptWg.Wait()
			time.Sleep(time.Second * 3)
			return
		case t := <-ticker.C:
			// block until we tick
			log.Tracef("Ticking: %v", t)
		}
	}
}

// vodStreamUser returns the GetStream user path for a VOD ID from GetVods.
// yt-dlp returns Twitch IDs with a leading "v" (e.g. v2807766672); GetStream
// expects twitch.tv/videos/<numeric_id>.
func vodStreamUser(vodID string) string {
	return "videos/" + strings.TrimPrefix(vodID, "v")
}
