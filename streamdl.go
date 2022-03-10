package main

import (
	"bytes"
	"io/ioutil"
	"log"
	"os"
	"time"

	fluentffmpeg "github.com/modfy/fluent-ffmpeg"
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

	for user, url := range urls {
		buf := &bytes.Buffer{}
		done := make(chan error, 1)
		cmd := fluentffmpeg.NewCommand("").InputPath(url).OutputFormat("mp4").OutputPath(user + ".mp4").Overwrite(true).OutputLogs(buf).Build()
		cmd.Start()

		go func() {
			done <- cmd.Wait()
		}()

		time.Sleep(time.Second * 30)
		out, _ := ioutil.ReadAll(buf) // read logs
		log.Println(string(out))
		cmd.Process.Signal(os.Interrupt)
	}
}
