//TODO: Allow users to specify naming format for downloaded files

package main

import (
	"bytes"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"

	fluentffmpeg "github.com/modfy/fluent-ffmpeg"
	log "github.com/sirupsen/logrus"
)

// getUmask reads the UMASK environment variable (octal), defaulting to 022.
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

// createDirWithUmask creates a directory (recursively) with permissions derived from the configured UMASK.
func createDirWithUmask(path string) error {
	// Check if directory already exists
	if info, err := os.Stat(path); err == nil && info.IsDir() {
		// Directory already exists, no need to create or modify permissions
		return nil
	}

	// Get current umask
	oldUmask := syscall.Umask(0)
	// Restore umask after this function
	defer syscall.Umask(oldUmask)

	// Calculate directory permissions based on umask
	// Start with full permissions (0777) and apply umask
	dirPerms := os.FileMode(0777 &^ os.FileMode(getUmask()))

	// Create directory if it doesn't exist
	err := os.MkdirAll(path, dirPerms)
	if err != nil {
		return err
	}

	// Ensure correct permissions even if directory already existed
	return os.Chmod(path, dirPerms)
}

// downloadStream records a live stream via FFmpeg, retrying on transient failures.
// It removes the user from the live list on exit and moves the finished file to moveLoc.
func downloadStream(user string, url string, outLoc string, moveLoc string, subfolder bool, control <-chan bool, response chan<- bool) {
	naturalFinish := make(chan error, 1)
	sigint := make(chan bool)
	t := time.Now().Format("2006-01-02_15-04-05")

	// Always ensure the user is removed from the live list when this goroutine exits
	defer func() {
		urlsMu.Lock()
		delete(urls, user)
		urlsMu.Unlock()
		log.Debugf("Removed %s from live list", user)
	}()

	// Always ensure base directories have correct permissions first
	if err := createDirWithUmask(outLoc); err != nil {
		log.Errorf("Failed to create output directory %s: %v", outLoc, err)
		return
	}
	if err := createDirWithUmask(moveLoc); err != nil {
		log.Errorf("Failed to create move directory %s: %v", moveLoc, err)
		return
	}

	if subfolder {
		outLoc = filepath.Join(outLoc, user)
		if err := createDirWithUmask(outLoc); err != nil {
			log.Errorf("Failed to create output subfolder %s: %v", outLoc, err)
			return
		}
		moveLoc = filepath.Join(moveLoc, user)
		if err := createDirWithUmask(moveLoc); err != nil {
			log.Errorf("Failed to create move subfolder %s: %v", moveLoc, err)
			return
		}
	}
	outPath := filepath.Join(outLoc, user+"_"+t+".mp4")
	newPath := filepath.Join(moveLoc, user+"_"+t+".mp4")
	log.Tracef("out: %s", outLoc)
	log.Tracef("move: %s", moveLoc)
	log.Tracef("full: %s", outPath)
	log.Infof("Starting Download for %v", user)

	// Single control listener — forwards shutdown signal to sigint channel
	go func() {
		for {
			_, more := <-control
			if !more {
				sigint <- true
				return
			}
		}
	}()

	// Retry loop for transient FFmpeg failures
	maxRetries := parseIntEnvOrDefault("FFMPEG_MAX_RETRIES", 3)
	baseDelay := time.Duration(parseIntEnvOrDefault("FFMPEG_RETRY_BASE_DELAY_SECONDS", 2)) * time.Second

	attempt := 0
	for {
		buf := &bytes.Buffer{}
		cmd := fluentffmpeg.
			NewCommand("").
			InputPath(url).
			OutputFormat("mp4").
			OutputPath(outPath).
			OutputLogs(buf).
			Build()

		// Inject resilient network flags before the FFmpeg input ("-i") argument.
		reconnectArgs := buildReconnectArgs()
		if len(reconnectArgs) > 0 {
			idx := indexOf(cmd.Args, "-i")
			if idx == -1 {
				cmd.Args = append(reconnectArgs, cmd.Args...)
			} else {
				newArgs := make([]string, 0, len(cmd.Args)+len(reconnectArgs))
				newArgs = append(newArgs, cmd.Args[:idx]...)
				newArgs = append(newArgs, reconnectArgs...)
				newArgs = append(newArgs, cmd.Args[idx:]...)
				cmd.Args = newArgs
			}
		}
		// Optional: prefer stream copy to avoid unnecessary transcoding; disabled by default.
		if strings.EqualFold(strings.TrimSpace(os.Getenv("FFMPEG_STREAM_COPY")), "1") ||
			strings.EqualFold(strings.TrimSpace(os.Getenv("FFMPEG_STREAM_COPY")), "true") {
			outIdx := indexOf(cmd.Args, outPath)
			if outIdx == -1 {
				cmd.Args = append(cmd.Args, "-c:v", "copy", "-c:a", "copy", "-movflags", "+faststart")
			} else {
				copyArgs := []string{"-c:v", "copy", "-c:a", "copy", "-movflags", "+faststart"}
				newArgs := make([]string, 0, len(cmd.Args)+len(copyArgs))
				newArgs = append(newArgs, cmd.Args[:outIdx]...)
				newArgs = append(newArgs, copyArgs...)
				newArgs = append(newArgs, cmd.Args[outIdx:]...)
				cmd.Args = newArgs
			}
		}
		// Allow extra opts via env for quick experiments
		if extraIn := strings.TrimSpace(os.Getenv("FFMPEG_EXTRA_INPUT_OPTS")); extraIn != "" {
			parts := splitArgs(extraIn)
			idx := indexOf(cmd.Args, "-i")
			if idx == -1 {
				cmd.Args = append(parts, cmd.Args...)
			} else {
				newArgs := make([]string, 0, len(cmd.Args)+len(parts))
				newArgs = append(newArgs, cmd.Args[:idx]...)
				newArgs = append(newArgs, parts...)
				newArgs = append(newArgs, cmd.Args[idx:]...)
				cmd.Args = newArgs
			}
		}
		if extraOut := strings.TrimSpace(os.Getenv("FFMPEG_EXTRA_OUTPUT_OPTS")); extraOut != "" {
			parts := splitArgs(extraOut)
			outIdx := indexOf(cmd.Args, outPath)
			if outIdx == -1 {
				cmd.Args = append(cmd.Args, parts...)
			} else {
				newArgs := make([]string, 0, len(cmd.Args)+len(parts))
				newArgs = append(newArgs, cmd.Args[:outIdx]...)
				newArgs = append(newArgs, parts...)
				newArgs = append(newArgs, cmd.Args[outIdx:]...)
				cmd.Args = newArgs
			}
		}
		// Global non-interactive overwrite: insert after binary name
		if indexOf(cmd.Args, "-y") == -1 {
			cmd.Args = insertAfterBinary(cmd.Args, []string{"-y"})
		}
		log.Debugf("FFmpeg args (sanitized): %s", sanitizeArgs(cmd.Args))

		// Debug: Show current process user and what user ffmpeg will run as
		log.Debugf("Current Go process user: %d, %d", os.Getuid(), os.Getgid())
		log.Debugf("FFmpeg command: %s %s", cmd.Path, sanitizeArgs(cmd.Args))
		log.Debugf("FFmpeg process will inherit current user permissions")

		if err := cmd.Start(); err != nil {
			log.Errorf("Failed to start FFmpeg for %s: %v", user, err)
			return
		}

		go func() {
			naturalFinish <- cmd.Wait()
		}()

		select {
		case <-sigint:
			log.Tracef("Sending SIGINT to %v Process", user)
			if err := cmd.Process.Signal(syscall.SIGINT); err != nil {
				log.Errorf("Failed to send SIGINT to %s process: %v", user, err)
			}
			if _, err := cmd.Process.Wait(); err != nil {
				log.Errorf("Error waiting for %s process after SIGINT: %v", user, err)
			}
			log.Tracef("Waiting for %v to Exit", user)
			if err := cmd.Wait(); err != nil {
				log.Errorf("Error waiting for %s process to exit: %v", user, err)
			}
			time.Sleep(time.Second * 2)
			response <- true
			return
		case err := <-naturalFinish:
			if err != nil {
				// Emit a compact tail of FFmpeg logs to aid diagnosis
				log.Warnf("FFmpeg failed for %s: %v", user, err)
				ffLog := tailString(buf.String(), 50)
				if ffLog != "" {
					log.Warnf("FFmpeg log tail for %s:\n%s", user, sanitizeLog(ffLog))
				}
				// On failure, attempt retry with backoff unless we've been asked to stop or max retries reached
				if attempt < maxRetries {
					attempt++
					delay := baseDelay * time.Duration(1<<uint(attempt-1))
					log.Warnf("FFmpeg exited with error for %s (attempt %d/%d). Retrying in %s", user, attempt, maxRetries, delay)
					select {
					case <-time.After(delay):
						continue
					case <-sigint:
						log.Tracef("Abort received during backoff for %s", user)
						response <- true
						return
					}
				}
				log.Errorf("FFmpeg failed for %s after %d attempts: %v", user, attempt, err)
				// Ensure cleanup so the next tick can retry fresh
				return
			}
			log.Debugf("Stream For %v Ended", user)
			log.Debugf("Moving file to %v", moveLoc)
			if err := moveFile(outPath, newPath); err != nil {
				log.Errorf("Failed to move file: %v", err)
			} else {
				log.Debugf("Moved file to %v", newPath)
			}
			return
		}
	}
}

// buildReconnectArgs constructs FFmpeg network resilience flags, taking optional overrides
// from environment variables. Defaults are conservative and safe for most HLS/HTTP streams.
// Environment variables (all optional):
//
//	FFMPEG_RECONNECT=1|0
//	FFMPEG_RECONNECT_DELAY_MAX=seconds (default 5)
//	FFMPEG_RW_TIMEOUT_US=microseconds (default 15000000 → 15s)
//	FFMPEG_USER_AGENT=custom UA string
func buildReconnectArgs() []string {
	// Toggle reconnect features (enabled by default)
	reconnectEnabled := strings.ToLower(os.Getenv("FFMPEG_RECONNECT"))
	if reconnectEnabled == "0" || reconnectEnabled == "false" {
		return nil
	}

	delayMaxStr := os.Getenv("FFMPEG_RECONNECT_DELAY_MAX")
	if delayMaxStr == "" {
		delayMaxStr = "15"
	}

	// Socket I/O timeout in microseconds (many protocols honor -rw_timeout)
	rwdTimeoutStr := os.Getenv("FFMPEG_RW_TIMEOUT_US")
	if rwdTimeoutStr == "" {
		rwdTimeoutStr = "15000000" // 15s default
	}

	args := []string{
		"-reconnect", "1",
		"-reconnect_at_eof", "1",
		"-reconnect_streamed", "1",
		"-reconnect_delay_max", delayMaxStr,
		// Use -rw_timeout for broad protocol coverage (microseconds)
		"-rw_timeout", rwdTimeoutStr,
	}

	if pw := strings.TrimSpace(os.Getenv("FFMPEG_PROTOCOL_WHITELIST")); pw != "" {
		args = append(args, "-protocol_whitelist", pw)
	}

	if ua := os.Getenv("FFMPEG_USER_AGENT"); ua != "" {
		args = append(args, "-user_agent", ua)
	}

	return args
}

// indexOf returns the index of the first occurrence of target in slice, or -1.
func indexOf(slice []string, target string) int {
	for i, s := range slice {
		if s == target {
			return i
		}
	}
	return -1
}

// sanitizeArgs redacts potentially sensitive values (e.g., URLs with tokens) for logging.
func sanitizeArgs(args []string) string {
	// Very basic: redact anything immediately following "-i" (input URL), and user-agent value.
	redacted := make([]string, len(args))
	copy(redacted, args)
	for i := 0; i < len(redacted)-1; i++ {
		if redacted[i] == "-i" || redacted[i] == "-user_agent" {
			redacted[i+1] = "<redacted>"
		}
	}
	return strings.Join(redacted, " ")
}

// parseIntEnvOrDefault parses an environment variable into an int, returning defaultVal on error or if empty.
func parseIntEnvOrDefault(name string, defaultVal int) int {
	val := strings.TrimSpace(os.Getenv(name))
	if val == "" {
		return defaultVal
	}
	parsed, err := strconv.Atoi(val)
	if err != nil {
		log.Warnf("Invalid %s value %q, using default %d", name, val, defaultVal)
		return defaultVal
	}
	return parsed
}

// insertAfterBinary inserts given flags immediately after the executable name (args[0]).
func insertAfterBinary(args []string, flags []string) []string {
	if len(args) == 0 {
		return append([]string{}, flags...)
	}
	out := make([]string, 0, len(args)+len(flags))
	out = append(out, args[0])
	out = append(out, flags...)
	out = append(out, args[1:]...)
	return out
}

// splitArgs splits a shell-like string on spaces, preserving quoted segments.
// Simple implementation sufficient for common flag strings.
func splitArgs(s string) []string {
	var out []string
	var cur strings.Builder
	inQuote := rune(0)
	for _, r := range s {
		switch r {
		case '"', '\'':
			switch inQuote {
			case 0:
				inQuote = r
			case r:
				inQuote = 0
			default:
				cur.WriteRune(r)
			}
		case ' ':
			if inQuote != 0 {
				cur.WriteRune(r)
			} else if cur.Len() > 0 {
				out = append(out, cur.String())
				cur.Reset()
			}
		default:
			cur.WriteRune(r)
		}
	}
	if cur.Len() > 0 {
		out = append(out, cur.String())
	}
	return out
}

// tailString returns the last n lines of s.
func tailString(s string, n int) string {
	if n <= 0 || s == "" {
		return ""
	}
	lines := strings.Split(s, "\n")
	if len(lines) <= n {
		return s
	}
	return strings.Join(lines[len(lines)-n:], "\n")
}

// sanitizeLog removes obvious secrets from ffmpeg stderr tails.
func sanitizeLog(s string) string {
	// crude URL token redaction
	s = redactBetween(s, "token=", "&")
	s = redactBetween(s, "sig=", "&")
	return s
}

// redactBetween replaces text between start and end markers with "<redacted>".
func redactBetween(s, start, end string) string {
	idx := strings.Index(s, start)
	if idx == -1 {
		return s
	}
	j := strings.Index(s[idx:], end)
	if j == -1 {
		return s[:idx+len(start)] + "<redacted>"
	}
	j += idx
	return s[:idx+len(start)] + "<redacted>" + s[j:]
}

// sanitizeFilename removes or replaces characters that are unsafe in filenames.
func sanitizeFilename(name string) string {
	replacer := strings.NewReplacer(
		"/", "_", "\\", "_", ":", "_", "*", "_",
		"?", "_", "\"", "_", "<", "_", ">", "_",
		"|", "_", "\n", "_", "\r", "_",
	)
	sanitized := replacer.Replace(name)
	// Collapse multiple underscores
	for strings.Contains(sanitized, "__") {
		sanitized = strings.ReplaceAll(sanitized, "__", "_")
	}
	// Trim to reasonable length
	if len(sanitized) > 100 {
		sanitized = sanitized[:100]
	}
	return strings.Trim(sanitized, "_. ")
}

// downloadVOD downloads a single VOD and updates its status in the database.
// The url parameter is a resolved stream URL (from GetStream via Streamlink/yt-dlp).
func downloadVOD(user string, vod VodResult, url string, outLoc string, moveLoc string, subfolder bool, vodDB *VodDB, control <-chan bool) {
	sanitizedTitle := sanitizeFilename(vod.Title)
	fileBase := user + "_vod_" + vod.ID
	if sanitizedTitle != "" {
		fileBase += "_" + sanitizedTitle
	}

	naturalFinish := make(chan error, 1)
	sigint := make(chan bool)

	// Always ensure base directories have correct permissions first
	if err := createDirWithUmask(outLoc); err != nil {
		log.Errorf("Failed to create output directory %s: %v", outLoc, err)
		if vodDB != nil {
			vodDB.MarkVODFailed(vod.ID)
		}
		return
	}
	if err := createDirWithUmask(moveLoc); err != nil {
		log.Errorf("Failed to create move directory %s: %v", moveLoc, err)
		if vodDB != nil {
			vodDB.MarkVODFailed(vod.ID)
		}
		return
	}

	if subfolder {
		outLoc = filepath.Join(outLoc, user)
		if err := createDirWithUmask(outLoc); err != nil {
			log.Errorf("Failed to create output subfolder %s: %v", outLoc, err)
			if vodDB != nil {
				vodDB.MarkVODFailed(vod.ID)
			}
			return
		}
		moveLoc = filepath.Join(moveLoc, user)
		if err := createDirWithUmask(moveLoc); err != nil {
			log.Errorf("Failed to create move subfolder %s: %v", moveLoc, err)
			if vodDB != nil {
				vodDB.MarkVODFailed(vod.ID)
			}
			return
		}
	}

	outPath := filepath.Join(outLoc, fileBase+".mp4")
	newPath := filepath.Join(moveLoc, fileBase+".mp4")
	log.Infof("Starting VOD download for %s: %s", user, vod.Title)

	// Single control listener
	go func() {
		for {
			_, more := <-control
			if !more {
				sigint <- true
				return
			}
		}
	}()

	buf := &bytes.Buffer{}
	cmd := fluentffmpeg.
		NewCommand("").
		InputPath(url).
		OutputFormat("mp4").
		OutputPath(outPath).
		OutputLogs(buf).
		Build()

	// Prefer stream copy for VODs to avoid re-encoding
	outIdx := indexOf(cmd.Args, outPath)
	copyArgs := []string{"-c:v", "copy", "-c:a", "copy", "-movflags", "+faststart"}
	if outIdx == -1 {
		cmd.Args = append(cmd.Args, copyArgs...)
	} else {
		newArgs := make([]string, 0, len(cmd.Args)+len(copyArgs))
		newArgs = append(newArgs, cmd.Args[:outIdx]...)
		newArgs = append(newArgs, copyArgs...)
		newArgs = append(newArgs, cmd.Args[outIdx:]...)
		cmd.Args = newArgs
	}

	if indexOf(cmd.Args, "-y") == -1 {
		cmd.Args = insertAfterBinary(cmd.Args, []string{"-y"})
	}
	log.Debugf("FFmpeg VOD args (sanitized): %s", sanitizeArgs(cmd.Args))

	if err := cmd.Start(); err != nil {
		log.Errorf("Failed to start FFmpeg for VOD %s: %v", vod.ID, err)
		if vodDB != nil {
			vodDB.MarkVODFailed(vod.ID)
		}
		return
	}

	go func() {
		naturalFinish <- cmd.Wait()
	}()

	select {
	case <-sigint:
		log.Tracef("Sending SIGINT to VOD %s process", vod.ID)
		if err := cmd.Process.Signal(syscall.SIGINT); err != nil {
			log.Errorf("Failed to send SIGINT to VOD %s: %v", vod.ID, err)
		}
		// Use only cmd.Wait() which handles process reaping internally
		if err := cmd.Wait(); err != nil {
			log.Tracef("VOD %s process exited after SIGINT: %v", vod.ID, err)
		}
		// Interrupted — leave as 'downloading'; stale threshold will handle retry
		return
	case err := <-naturalFinish:
		if err != nil {
			log.Warnf("FFmpeg failed for VOD %s: %v", vod.ID, err)
			ffLog := tailString(buf.String(), 50)
			if ffLog != "" {
				log.Warnf("FFmpeg log tail for VOD %s:\n%s", vod.ID, sanitizeLog(ffLog))
			}
			if vodDB != nil {
				vodDB.MarkVODFailed(vod.ID)
			}
			return
		}

		log.Debugf("VOD %s download complete", vod.ID)
		if err := moveFile(outPath, newPath); err != nil {
			log.Errorf("Failed to move VOD file: %v", err)
			if vodDB != nil {
				vodDB.MarkVODFailed(vod.ID)
			}
		} else {
			log.Debugf("Moved VOD to %v", newPath)
			if vodDB != nil {
				if err := vodDB.MarkVODCompleted(vod.ID); err != nil {
					log.Errorf("Failed to mark VOD %s as completed: %v", vod.ID, err)
				}
			}
		}

		return
	}
}
