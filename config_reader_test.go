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

func TestParseConfig_VODFields(t *testing.T) {
	yamlData := []byte(`
- site: twitch.tv
  channels:
  - name: testuser
    quality: best
    vod: true
    vod_limit: 5
- site: twitch.tv
  channels:
  - name: liveuser
    quality: best
`)
	config, err := parseConfig(yamlData)
	if err != nil {
		t.Fatalf("Failed to parse config: %v", err)
	}

	if len(config) != 2 {
		t.Fatalf("Expected 2 site configs, got %d", len(config))
	}

	vodStreamer := config[0].Streamers[0]
	if !vodStreamer.VOD {
		t.Error("Expected VOD to be true")
	}
	if vodStreamer.VODLimit != 5 {
		t.Errorf("Expected VODLimit 5, got %d", vodStreamer.VODLimit)
	}

	liveStreamer := config[1].Streamers[0]
	if liveStreamer.VOD {
		t.Error("Expected VOD to default to false")
	}
	if liveStreamer.VODLimit != 0 {
		t.Errorf("Expected VODLimit 0 (default), got %d", liveStreamer.VODLimit)
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
