package main

import (
	"bytes"
	"syscall"
	"time"

	fluentffmpeg "github.com/modfy/fluent-ffmpeg"
	log "github.com/sirupsen/logrus"
)

func downloadStream(user string, url string, control <-chan bool, response chan<- bool) {
	naturalFinish := make(chan error, 1)
	sigint := make(chan bool)
	log.Tracef("Starting Download for %v", user)
	buf := &bytes.Buffer{}
	cmd := fluentffmpeg.
		NewCommand("").
		InputPath(url).
		OutputFormat("mp4").
		OutputPath(user + ".mp4").
		OutputLogs(buf).
		Build()

	cmd.Start()

	go func() {
		naturalFinish <- cmd.Wait()
	}()

	go func() {
		for {
			_, more := <-control
			if !more {
				sigint <- true
				return
			}
		}
	}()

	select {
	case <-sigint:
		log.Tracef("Sending SIGINT to %v Process", user)
		cmd.Process.Signal(syscall.SIGINT)
		cmd.Process.Wait()
		log.Tracef("Waiting for %v to Exit", user)
		cmd.Wait()
		time.Sleep(time.Second * 2)
		response <- true
	case <-naturalFinish:
		log.Debugf("Stream For %v Ended", user)
		delete(urls, user)
	}
}
