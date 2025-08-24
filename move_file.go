package main

import (
	"io"
	"os"
	"path/filepath"
	"strings"
	"syscall"

	log "github.com/sirupsen/logrus"
)

// renameFunc is used to allow testing of cross-device fallbacks by stubbing.
var renameFunc = os.Rename

func moveFile(oldPath string, newPath string) error {
	log.Infof("Moving file from %v to %v", oldPath, newPath)

	// Ensure target directory exists with correct permissions
	targetDir := filepath.Dir(newPath)
	if err := createDirWithUmask(targetDir); err != nil {
		log.Errorf("Failed to create/set permissions on target directory: %v", err)
		return err
	}

	// Fast path: try atomic rename first (same filesystem)
	if err := renameFunc(oldPath, newPath); err == nil {
		log.Infof("Atomically renamed %v to %v", oldPath, newPath)
		return nil
	} else if !isCrossDeviceLink(err) {
		// If it's not a cross-device error, return immediately
		log.Debugf("os.Rename failed with non-cross-device error: %v", err)
		return err
	}

	// Slow path: cross-device move. Copy to temp file in destination, fsync, then rename
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

	// Create a temp file in the destination directory with the same perms
	tempPath := filepath.Join(targetDir, ".tmp."+filepath.Base(newPath))
	tempFile, err := os.OpenFile(tempPath, os.O_RDWR|os.O_CREATE|os.O_TRUNC, filePerms)
	if err != nil {
		log.Errorf("Failed to create temp file: %v", err)
		return err
	}

	// Ensure we close and clean up temp file on error
	defer func() {
		tempFile.Close()
		// Best effort: remove temp file if it still exists
		_ = os.Remove(tempPath)
	}()

	if _, err := io.Copy(tempFile, originalFile); err != nil {
		log.Errorf("Failed to copy to temp file: %v", err)
		return err
	}
	if err := tempFile.Sync(); err != nil {
		log.Errorf("Failed to fsync temp file: %v", err)
		return err
	}
	if err := tempFile.Close(); err != nil {
		log.Errorf("Failed to close temp file: %v", err)
		return err
	}

	// Atomically replace target path with temp file
	if err := renameFunc(tempPath, newPath); err != nil {
		log.Errorf("Failed to rename temp file into place: %v", err)
		return err
	}

	// Remove original file only after successful rename
	if err := os.Remove(oldPath); err != nil {
		log.Errorf("Failed to remove original file after copy: %v", err)
		return err
	}

	log.Infof("Moved file from %v to %v (cross-device)", oldPath, newPath)
	return nil
}

func isCrossDeviceLink(err error) bool {
	if err == nil {
		return false
	}
	// Check syscall errno directly when possible
	if errno, ok := err.(syscall.Errno); ok {
		if errno == syscall.EXDEV {
			return true
		}
	}
	// Some platforms may wrap the error string
	msg := strings.ToLower(err.Error())
	return strings.Contains(msg, "cross-device") || strings.Contains(msg, "exdev")
}
