package main

import (
	"fmt"
	"os"
	"os/exec"

	log "github.com/sirupsen/logrus"
)

// runPostScript executes a user-defined script after a successful download.
// The file path is passed as the first argument, and context is provided via
// STREAMDL_FILE, STREAMDL_USER, STREAMDL_SITE, and STREAMDL_TYPE env vars.
// Returns nil immediately if scriptPath is empty (no hook configured).
func runPostScript(scriptPath, filePath, user, site, dlType string) error {
	if scriptPath == "" {
		return nil
	}

	info, err := os.Stat(scriptPath)
	if err != nil {
		return fmt.Errorf("post_script not found: %w", err)
	}
	if info.Mode().Perm()&0111 == 0 {
		return fmt.Errorf("post_script %s is not executable", scriptPath)
	}

	log.Infof("Running post_script %s for %s (%s)", scriptPath, user, filePath)

	cmd := exec.Command(scriptPath, filePath)
	cmd.Env = append(os.Environ(),
		"STREAMDL_FILE="+filePath,
		"STREAMDL_USER="+user,
		"STREAMDL_SITE="+site,
		"STREAMDL_TYPE="+dlType,
	)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	if err := cmd.Run(); err != nil {
		return fmt.Errorf("post_script %s failed: %w", scriptPath, err)
	}

	log.Infof("post_script %s completed for %s", scriptPath, user)
	return nil
}
