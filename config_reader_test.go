package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestReadConfig_ValidFile(t *testing.T) {
	dir := t.TempDir()
	cfg := filepath.Join(dir, "config.yml")
	want := []byte("- site: test.example\n  channels: []\n")
	if err := os.WriteFile(cfg, want, 0644); err != nil {
		t.Fatalf("write cfg: %v", err)
	}

	got := readConfig(cfg)
	if string(got) != string(want) {
		t.Fatalf("config mismatch: got %q want %q", string(got), string(want))
	}
}

func TestReadConfig_MissingFile_Fatal(t *testing.T) {
	// Stub fatalf to avoid os.Exit; instead record message
	var called bool
	oldFatal := fatalf
	fatalf = func(format string, args ...interface{}) {
		called = true
		// Do not exit in tests
	}
	t.Cleanup(func() { fatalf = oldFatal })

	_ = readConfig("/path/does/not/exist.yml")
	if !called {
		t.Fatalf("expected fatalf to be called for missing file")
	}
}

func TestParseConfig_MalformedYAML(t *testing.T) {
	dir := t.TempDir()
	cfg := filepath.Join(dir, "bad.yml")
	// channels should be a sequence, not a scalar
	bad := []byte("- site: test.example\n  channels: true\n")
	if err := os.WriteFile(cfg, bad, 0644); err != nil {
		t.Fatalf("write bad cfg: %v", err)
	}

	// Stub fatalf to no-op so readConfig won't exit on read
	oldFatal := fatalf
	fatalf = func(format string, args ...interface{}) {}
	t.Cleanup(func() { fatalf = oldFatal })

	if _, err := parseConfig(readConfig(cfg)); err == nil {
		t.Fatalf("expected YAML unmarshal error for malformed config")
	}
}
