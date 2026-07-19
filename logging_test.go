package main

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"

	log "github.com/sirupsen/logrus"
)

func TestParseLogDest(t *testing.T) {
	cases := map[string]LogDest{
		"":          LogDestFile,
		"file":      LogDestFile,
		"FILE":      LogDestFile,
		"stdout":    LogDestStdout,
		"console":   LogDestStdout,
		"container": LogDestStdout,
		"both":      LogDestBoth,
		"all":       LogDestBoth,
	}
	for in, want := range cases {
		got, err := parseLogDest(in)
		if err != nil {
			t.Fatalf("parseLogDest(%q): %v", in, err)
		}
		if got != want {
			t.Fatalf("parseLogDest(%q)=%q want %q", in, got, want)
		}
	}
	if _, err := parseLogDest("nope"); err == nil {
		t.Fatal("expected error for invalid dest")
	}
}

func TestSetupLogging_FileDefaultPathAndConsoleSummary(t *testing.T) {
	dir := t.TempDir()
	origOut := log.StandardLogger().Out
	origSummary := consoleSummary
	t.Cleanup(func() {
		log.SetOutput(origOut)
		consoleSummary = origSummary
	})

	cfg, err := setupLogging("info", "file", "", dir)
	if err != nil {
		t.Fatal(err)
	}
	defer cfg.Close()

	wantPath := filepath.Join(dir, "streamdl.log")
	if cfg.FilePath != wantPath {
		t.Fatalf("path=%q want %q", cfg.FilePath, wantPath)
	}
	if consoleSummary == nil {
		t.Fatal("expected console summary writer for file dest")
	}

	log.Info("hello-file-only")
	_ = cfg.file.Sync()
	body, err := os.ReadFile(wantPath)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(body), "hello-file-only") {
		t.Fatalf("log file missing entry: %s", body)
	}
}

func TestSetupLogging_StdoutNoConsoleSummary(t *testing.T) {
	origOut := log.StandardLogger().Out
	origSummary := consoleSummary
	t.Cleanup(func() {
		log.SetOutput(origOut)
		consoleSummary = origSummary
	})

	cfg, err := setupLogging("debug", "stdout", "", t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	defer cfg.Close()
	if consoleSummary != nil {
		t.Fatal("stdout dest should not set console summary sink")
	}
	if cfg.FilePath != "" {
		t.Fatalf("stdout dest should not invent a file path, got %q", cfg.FilePath)
	}
}

func TestSetupLogging_BothWritesFile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "custom.log")
	origOut := log.StandardLogger().Out
	origSummary := consoleSummary
	t.Cleanup(func() {
		log.SetOutput(origOut)
		consoleSummary = origSummary
	})

	cfg, err := setupLogging("info", "both", path, dir)
	if err != nil {
		t.Fatal(err)
	}
	defer cfg.Close()
	if consoleSummary != nil {
		t.Fatal("both dest should rely on logrus for stdout, not summary sink")
	}
	log.Info("hello-both")
	_ = cfg.file.Sync()
	body, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(body), "hello-both") {
		t.Fatalf("missing log: %s", body)
	}
}

func TestWriteConsoleDownloadSummary(t *testing.T) {
	var buf bytes.Buffer
	origSummary := consoleSummary
	consoleSummary = &buf
	t.Cleanup(func() { consoleSummary = origSummary })

	store := newProgressStore()
	writeConsoleDownloadSummary(store)
	if !strings.Contains(buf.String(), "Active Downloads:") || !strings.Contains(buf.String(), "(none)") {
		t.Fatalf("empty summary: %q", buf.String())
	}

	buf.Reset()
	key := progressKeyLive("alice")
	store.Start(key, ProgressMeta{Channel: "alice", Kind: DownloadKindLive})
	store.Update(key, ffmpegProgressSample{SizeBytes: 2048, Duration: 0, Speed: 1, Valid: true})
	writeConsoleDownloadSummary(store)
	out := buf.String()
	if !strings.Contains(out, "[alice] live") || strings.Contains(out, "(none)") {
		t.Fatalf("unexpected summary: %q", out)
	}
}
