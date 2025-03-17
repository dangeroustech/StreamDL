//TODO: Allow users to specify naming format for downloaded files

package main

import (
	"bytes"
	"os"
	"path/filepath"
	"strconv"
	"syscall"
	"time"

	fluentffmpeg "github.com/modfy/fluent-ffmpeg"
	log "github.com/sirupsen/logrus"
)

func getUmask() int {
	// Get UMASK from environment, default to 022 if not set
	umaskStr := os.Getenv("UMASK")
	if umaskStr == "" {
		umaskStr = "022"
	}

	// Parse UMASK value (in octal)
	umask, err := strconv.ParseInt(umaskStr, 8, 32)
	if err != nil {
		log.Warnf("Invalid UMASK value %s, using default 022", umaskStr)
		umask = 022
	}

	return int(umask)
}

func createDirWithUmask(path string) error {
	// Get current umask
	oldUmask := syscall.Umask(0)
	// Restore umask after this function
	defer syscall.Umask(oldUmask)

	// Calculate directory permissions based on umask
	// Start with full permissions (0777) and apply umask
	dirPerms := os.FileMode(0777 &^ os.FileMode(getUmask()))
	return os.MkdirAll(path, dirPerms)
}

func downloadStream(user string, url string, outLoc string, moveLoc string, subfolder bool, control <-chan bool, response chan<- bool) {
	naturalFinish := make(chan error, 1)
	sigint := make(chan bool)
	t := time.Now().Format("2006-01-02_15-04-05")
	if subfolder {
		outLoc = filepath.Join(outLoc, user)
		createDirWithUmask(outLoc)
		moveLoc = filepath.Join(moveLoc, user)
		createDirWithUmask(moveLoc)
	}
	log.Tracef("out: %s", outLoc)
	log.Tracef("move: %s", moveLoc)
	log.Tracef("full: %s", filepath.Join(outLoc, user+"_"+t+".mp4"))
	log.Infof("Starting Download for %v", user)
	buf := &bytes.Buffer{}
	cmd := fluentffmpeg.
		NewCommand("").
		InputPath(url).
		OutputFormat("mp4").
		OutputPath(filepath.Join(outLoc, user+"_"+t+".mp4")).
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
		oldPath := filepath.Join(outLoc, user+"_"+t+".mp4")
		newPath := filepath.Join(moveLoc, user+"_"+t+".mp4")
		err := moveFile(oldPath, newPath)
		if err != nil {
			log.Errorf("Failed to move file: %v", err)
		} else {
			log.Debugf("Moved file to %v", newPath)
		}
		delete(urls, user)
	}
}
