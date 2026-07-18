package main

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"sync"

	log "github.com/sirupsen/logrus"
	prefixed "github.com/x-cray/logrus-prefixed-formatter"
)

// LogDest controls where primary application logs are written.
type LogDest string

const (
	LogDestFile   LogDest = "file"
	LogDestStdout LogDest = "stdout"
	LogDestBoth   LogDest = "both"
)

// LoggingConfig holds the active logging sinks for cleanup and console summary.
type LoggingConfig struct {
	Dest     LogDest
	FilePath string
	file     *os.File
}

var (
	consoleSummaryMu sync.Mutex
	// consoleSummary, when non-nil, receives tick Active Downloads lines on
	// stdout while primary logs go only to a file (dest=file).
	consoleSummary io.Writer
)

func parseLogDest(s string) (LogDest, error) {
	switch strings.ToLower(strings.TrimSpace(s)) {
	case "", "file":
		return LogDestFile, nil
	case "stdout", "console", "container":
		return LogDestStdout, nil
	case "both", "all":
		return LogDestBoth, nil
	default:
		return "", fmt.Errorf("invalid log destination %q (want file, stdout, or both)", s)
	}
}

func envOr(name, fallback string) string {
	if v := strings.TrimSpace(os.Getenv(name)); v != "" {
		return v
	}
	return fallback
}

// setupLogging configures logrus output and the optional stdout tick summary sink.
//
// Destinations:
//   - file:   full logs → log file; container stdout gets Active Downloads each tick
//   - stdout: full logs → stdout (legacy / docker-compose logs as primary)
//   - both:   full logs → log file and stdout
//
// When dest is file or both and filePath is empty, it defaults to
// <dataDir>/streamdl.log.
func setupLogging(levelStr, destStr, filePath, dataDir string) (*LoggingConfig, error) {
	dest, err := parseLogDest(destStr)
	if err != nil {
		return nil, err
	}

	ll, err := log.ParseLevel(levelStr)
	if err != nil {
		ll = log.InfoLevel
	}

	filePath = strings.TrimSpace(filePath)
	needsFile := dest == LogDestFile || dest == LogDestBoth
	if needsFile && filePath == "" {
		if strings.TrimSpace(dataDir) == "" {
			dataDir = "/app/data"
		}
		filePath = filepath.Join(dataDir, "streamdl.log")
	}

	log.SetFormatter(&prefixed.TextFormatter{FullTimestamp: true})
	log.SetLevel(ll)

	cfg := &LoggingConfig{Dest: dest, FilePath: filePath}
	consoleSummary = nil

	var writers []io.Writer
	switch dest {
	case LogDestStdout:
		writers = append(writers, os.Stdout)
	case LogDestFile, LogDestBoth:
		if err := os.MkdirAll(filepath.Dir(filePath), 0o755); err != nil {
			return nil, fmt.Errorf("create log directory: %w", err)
		}
		f, err := os.OpenFile(filePath, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
		if err != nil {
			return nil, fmt.Errorf("open log file %s: %w", filePath, err)
		}
		cfg.file = f
		writers = append(writers, f)
		if dest == LogDestBoth {
			writers = append(writers, os.Stdout)
		} else {
			// Primary logs are file-only; expose a dedicated stdout summary sink.
			consoleSummary = os.Stdout
		}
	}

	switch len(writers) {
	case 0:
		log.SetOutput(os.Stdout)
	case 1:
		log.SetOutput(writers[0])
	default:
		log.SetOutput(io.MultiWriter(writers...))
	}

	return cfg, nil
}

// Close releases the log file handle, if any.
func (c *LoggingConfig) Close() {
	if c == nil || c.file == nil {
		return
	}
	_ = c.file.Close()
	c.file = nil
}

// writeConsoleDownloadSummary writes the Active Downloads block to stdout when
// primary logs are file-only. No-op for stdout/both (logrus already covers it).
func writeConsoleDownloadSummary(store *progressStore) {
	if consoleSummary == nil {
		return
	}
	snap := store.Snapshot()
	var b strings.Builder
	b.WriteString("Active Downloads:\n")
	if len(snap) == 0 {
		b.WriteString("  (none)\n")
	} else {
		for _, p := range snap {
			fmt.Fprintf(&b, "  %s\n", formatDownloadProgress(p))
		}
	}
	consoleSummaryMu.Lock()
	defer consoleSummaryMu.Unlock()
	_, _ = io.WriteString(consoleSummary, b.String())
}
