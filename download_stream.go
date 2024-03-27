//TODO: Allow users to specify naming format for downloaded files

package main

import (
	"bytes"
	"os"
	"path/filepath"
	"syscall"
	"time"

	fluentffmpeg "github.com/modfy/fluent-ffmpeg"
	log "github.com/sirupsen/logrus"
)

func downloadStream(user string, url string, outLoc string, moveLoc string, subfolder bool, control <-chan bool, response chan<- bool) {
	naturalFinish := make(chan error, 1)
	sigint := make(chan bool)
	t := time.Now().Format("2006_01_02-15_04_05")
	if subfolder {
		outLoc = filepath.Join(outLoc, user)
		os.MkdirAll(outLoc, os.ModePerm)
		moveLoc = filepath.Join(moveLoc, user)
		os.MkdirAll(moveLoc, os.ModePerm)
	}
	log.Tracef("out: %s", outLoc)
	log.Tracef("move: %s", moveLoc)
	log.Tracef("full: %s", filepath.Join(outLoc, user+"-"+t+".mp4"))
	log.Tracef("Starting Download for %v", user)
	buf := &bytes.Buffer{}
	cmd := fluentffmpeg.
		NewCommand("").
		InputPath(url).
		OutputFormat("mp4").
		OutputPath(filepath.Join(outLoc, user+"-"+t+".mp4")).
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
		log.Debugf("Moving file to %v", moveLoc)
		oldPath := filepath.Join(outLoc, user+"-"+t+".mp4")
		newPath := filepath.Join(moveLoc, user+"-"+t+".mp4")
		err := moveFile(oldPath, newPath)
		if err != nil {
			log.Errorf("Failed to move file: %v", err)
		} else {
			log.Debugf("Moved file to %v", newPath)
		}
		delete(urls, user)
	}
}
