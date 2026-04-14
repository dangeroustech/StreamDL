package main

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestVodDB_InitAndClose(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "test.db")
	db, err := InitVodDB(dbPath)
	if err != nil {
		t.Fatalf("Failed to init DB: %v", err)
	}
	defer db.Close()

	// Verify the file was created
	if _, err := os.Stat(dbPath); os.IsNotExist(err) {
		t.Error("Database file was not created")
	}
}

func TestVodDB_FullLifecycle(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "test.db")
	db, err := InitVodDB(dbPath)
	if err != nil {
		t.Fatalf("Failed to init DB: %v", err)
	}
	defer db.Close()

	staleThreshold := 10 * time.Minute

	// Should need downloading initially
	should, err := db.ShouldDownloadVOD("12345", staleThreshold)
	if err != nil {
		t.Fatalf("ShouldDownloadVOD failed: %v", err)
	}
	if !should {
		t.Error("VOD not in DB should need downloading")
	}

	// Mark as started
	err = db.MarkVODStarted("12345", "testuser", "twitch.tv", "Test Stream Title")
	if err != nil {
		t.Fatalf("MarkVODStarted failed: %v", err)
	}

	// In-progress VOD should NOT be downloaded (not stale yet)
	should, err = db.ShouldDownloadVOD("12345", staleThreshold)
	if err != nil {
		t.Fatalf("ShouldDownloadVOD failed: %v", err)
	}
	if should {
		t.Error("Recently started VOD should not need re-downloading")
	}

	// Mark as completed
	err = db.MarkVODCompleted("12345")
	if err != nil {
		t.Fatalf("MarkVODCompleted failed: %v", err)
	}

	// Completed VOD should NOT be downloaded
	should, err = db.ShouldDownloadVOD("12345", staleThreshold)
	if err != nil {
		t.Fatalf("ShouldDownloadVOD failed: %v", err)
	}
	if should {
		t.Error("Completed VOD should not need re-downloading")
	}
}

func TestVodDB_FailedVODIsRetried(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "test.db")
	db, err := InitVodDB(dbPath)
	if err != nil {
		t.Fatalf("Failed to init DB: %v", err)
	}
	defer db.Close()

	staleThreshold := 10 * time.Minute

	db.MarkVODStarted("12345", "testuser", "twitch.tv", "Title")
	db.MarkVODFailed("12345")

	should, err := db.ShouldDownloadVOD("12345", staleThreshold)
	if err != nil {
		t.Fatalf("ShouldDownloadVOD failed: %v", err)
	}
	if !should {
		t.Error("Failed VOD should be retried")
	}
}

func TestVodDB_StaleDownloadIsRetried(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "test.db")
	db, err := InitVodDB(dbPath)
	if err != nil {
		t.Fatalf("Failed to init DB: %v", err)
	}
	defer db.Close()

	db.MarkVODStarted("12345", "testuser", "twitch.tv", "Title")

	// With a zero threshold, the download is immediately considered stale
	should, err := db.ShouldDownloadVOD("12345", 0)
	if err != nil {
		t.Fatalf("ShouldDownloadVOD failed: %v", err)
	}
	if !should {
		t.Error("Stale downloading VOD should be retried")
	}
}

func TestVodDB_DifferentVODsAreIndependent(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "test.db")
	db, err := InitVodDB(dbPath)
	if err != nil {
		t.Fatalf("Failed to init DB: %v", err)
	}
	defer db.Close()

	staleThreshold := 10 * time.Minute

	db.MarkVODStarted("111", "user1", "twitch.tv", "Title A")
	db.MarkVODCompleted("111")
	db.MarkVODStarted("222", "user2", "twitch.tv", "Title B")
	db.MarkVODCompleted("222")

	d1, _ := db.ShouldDownloadVOD("111", staleThreshold)
	d2, _ := db.ShouldDownloadVOD("222", staleThreshold)
	d3, _ := db.ShouldDownloadVOD("333", staleThreshold)

	if d1 {
		t.Error("VOD 111 is completed, should not need downloading")
	}
	if d2 {
		t.Error("VOD 222 is completed, should not need downloading")
	}
	if !d3 {
		t.Error("VOD 333 is not in DB, should need downloading")
	}
}
