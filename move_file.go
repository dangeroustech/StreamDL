package main

import (
	"io"
	"os"
	"path/filepath"
	"syscall"

	log "github.com/sirupsen/logrus"
)

func moveFile(oldPath string, newPath string) error {
	log.Infof("Moving file from %v to %v", oldPath, newPath)

	// First, ensure target directory exists with correct permissions
	targetDir := filepath.Dir(newPath)
	err := createDirWithUmask(targetDir)
	if err != nil {
		log.Errorf("Failed to create/set permissions on target directory: %v", err)
		return err
	}

	// Open original file
	originalFile, err := os.Open(oldPath)
	if err != nil {
		log.Errorf("Failed to open original file: %v", err)
		return err
	}
	defer originalFile.Close()

	// Get original file info for permissions
	fileInfo, err := originalFile.Stat()
	if err != nil {
		log.Errorf("Failed to get original file info: %v", err)
		return err
	}

	// Apply UMASK to the file permissions
	oldUmask := syscall.Umask(0)
	filePerms := fileInfo.Mode() &^ os.FileMode(getUmask())
	syscall.Umask(oldUmask)

	// Create new file with UMASK-modified permissions
	newFile, err := os.OpenFile(newPath, os.O_RDWR|os.O_CREATE|os.O_TRUNC, filePerms)
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
