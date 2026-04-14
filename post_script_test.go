package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestRunPostScript_Success(t *testing.T) {
	dir := t.TempDir()
	marker := filepath.Join(dir, "marker.txt")

	// Create a script that writes env vars to a marker file
	script := filepath.Join(dir, "hook.sh")
	scriptContent := "#!/bin/sh\necho \"$STREAMDL_FILE|$STREAMDL_USER|$STREAMDL_SITE|$STREAMDL_TYPE\" > " + marker + "\n"
	if err := os.WriteFile(script, []byte(scriptContent), 0755); err != nil {
		t.Fatalf("write script: %v", err)
	}

	err := runPostScript(script, "/data/complete/user_2026.mp4", "testuser", "twitch.tv", "live")
	if err != nil {
		t.Fatalf("runPostScript error: %v", err)
	}

	got, err := os.ReadFile(marker)
	if err != nil {
		t.Fatalf("read marker: %v", err)
	}

	expected := "/data/complete/user_2026.mp4|testuser|twitch.tv|live\n"
	if string(got) != expected {
		t.Errorf("marker content = %q, want %q", string(got), expected)
	}
}

func TestRunPostScript_EmptyPath_Noop(t *testing.T) {
	err := runPostScript("", "/data/file.mp4", "user", "twitch.tv", "live")
	if err != nil {
		t.Fatalf("expected nil for empty script path, got: %v", err)
	}
}

func TestRunPostScript_MissingScript(t *testing.T) {
	err := runPostScript("/nonexistent/script.sh", "/data/file.mp4", "user", "twitch.tv", "live")
	if err == nil {
		t.Fatal("expected error for missing script")
	}
}

func TestRunPostScript_ScriptFails(t *testing.T) {
	dir := t.TempDir()
	script := filepath.Join(dir, "fail.sh")
	if err := os.WriteFile(script, []byte("#!/bin/sh\nexit 1\n"), 0755); err != nil {
		t.Fatalf("write script: %v", err)
	}

	err := runPostScript(script, "/data/file.mp4", "user", "twitch.tv", "vod")
	if err == nil {
		t.Fatal("expected error for failing script")
	}
}

func TestRunPostScript_FilePathAsFirstArg(t *testing.T) {
	dir := t.TempDir()
	marker := filepath.Join(dir, "arg.txt")

	script := filepath.Join(dir, "checkarg.sh")
	scriptContent := "#!/bin/sh\necho \"$1\" > " + marker + "\n"
	if err := os.WriteFile(script, []byte(scriptContent), 0755); err != nil {
		t.Fatalf("write script: %v", err)
	}

	err := runPostScript(script, "/data/complete/test.mp4", "user", "twitch.tv", "live")
	if err != nil {
		t.Fatalf("runPostScript error: %v", err)
	}

	got, err := os.ReadFile(marker)
	if err != nil {
		t.Fatalf("read marker: %v", err)
	}

	if string(got) != "/data/complete/test.mp4\n" {
		t.Errorf("arg content = %q, want %q", string(got), "/data/complete/test.mp4\n")
	}
}
