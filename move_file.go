package main

import (
	"bytes"
	"os"
	"path/filepath"
	"syscall"
	"time"

	log "github.com/sirupsen/logrus"
)

func moveFile(oldPath string, newPath string) error {
	// Open original file
	originalFile, err := os.Open(oldPath)
	if err != nil {
		log.Errorf("Failed to open original file: %v", err)
		return err
	}
	defer originalFile.Close()

	// Create new file
	newFile, err := os.Create(newPath)
	if err != nil {
		log.Errorf("Failed to create new file: %v", err)
		return err
	}
	defer newFile.Close()

	// Copy the bytes to destination from source
	_, err = io.Copy(newFile, originalFile)
	if err != nil {
		log.Errorf("Failed to copy file: %v", err)
		return err
	}

	// Commit the file contents
	err = newFile.Sync()
	if err != nil {
		log.Errorf("Failed to sync file: %v", err)
		return err
	}

	// Remove original file
	err = os.Remove(oldPath)
	if err != nil {
		log.Errorf("Failed to remove original file: %v", err)
		return err
	}

	log.Infof("Moved file from %v to %v", oldPath, newPath)

	return nil
}
