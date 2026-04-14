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

	// Should claim successfully (new VOD)
	claimed, err := db.ClaimVOD("12345", "testuser", "twitch.tv", "Test Stream Title", staleThreshold)
	if err != nil {
		t.Fatalf("ClaimVOD failed: %v", err)
	}
	if !claimed {
		t.Error("VOD not in DB should be claimable")
	}

	// Second claim should fail (already in progress, not stale)
	claimed, err = db.ClaimVOD("12345", "testuser", "twitch.tv", "Test Stream Title", staleThreshold)
	if err != nil {
		t.Fatalf("ClaimVOD failed: %v", err)
	}
	if claimed {
		t.Error("Recently started VOD should not be re-claimable")
	}

	// Mark as completed
	err = db.MarkVODCompleted("12345")
	if err != nil {
		t.Fatalf("MarkVODCompleted failed: %v", err)
	}

	// Completed VOD should NOT be claimable
	claimed, err = db.ClaimVOD("12345", "testuser", "twitch.tv", "Test Stream Title", staleThreshold)
	if err != nil {
		t.Fatalf("ClaimVOD failed: %v", err)
	}
	if claimed {
		t.Error("Completed VOD should not be claimable")
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

	claimed, err := db.ClaimVOD("12345", "testuser", "twitch.tv", "Title", staleThreshold)
	if err != nil {
		t.Fatalf("ClaimVOD failed: %v", err)
	}
	if !claimed {
		t.Fatal("Initial claim should succeed")
	}

	err = db.MarkVODFailed("12345")
	if err != nil {
		t.Fatalf("MarkVODFailed failed: %v", err)
	}

	claimed, err = db.ClaimVOD("12345", "testuser", "twitch.tv", "Title", staleThreshold)
	if err != nil {
		t.Fatalf("ClaimVOD failed: %v", err)
	}
	if !claimed {
		t.Error("Failed VOD should be re-claimable")
	}
}

func TestVodDB_StaleDownloadIsRetried(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "test.db")
	db, err := InitVodDB(dbPath)
	if err != nil {
		t.Fatalf("Failed to init DB: %v", err)
	}
	defer db.Close()

	staleThreshold := 10 * time.Minute

	claimed, err := db.ClaimVOD("12345", "testuser", "twitch.tv", "Title", staleThreshold)
	if err != nil {
		t.Fatalf("ClaimVOD failed: %v", err)
	}
	if !claimed {
		t.Fatal("Initial claim should succeed")
	}

	// With a zero threshold, the download is immediately considered stale
	claimed, err = db.ClaimVOD("12345", "testuser", "twitch.tv", "Title", 0)
	if err != nil {
		t.Fatalf("ClaimVOD failed: %v", err)
	}
	if !claimed {
		t.Error("Stale downloading VOD should be re-claimable")
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

	claimed, err := db.ClaimVOD("111", "user1", "twitch.tv", "Title A", staleThreshold)
	if err != nil {
		t.Fatalf("ClaimVOD 111 failed: %v", err)
	}
	if !claimed {
		t.Fatal("Claim 111 should succeed")
	}
	if err := db.MarkVODCompleted("111"); err != nil {
		t.Fatalf("MarkVODCompleted 111 failed: %v", err)
	}

	claimed, err = db.ClaimVOD("222", "user2", "twitch.tv", "Title B", staleThreshold)
	if err != nil {
		t.Fatalf("ClaimVOD 222 failed: %v", err)
	}
	if !claimed {
		t.Fatal("Claim 222 should succeed")
	}
	if err := db.MarkVODCompleted("222"); err != nil {
		t.Fatalf("MarkVODCompleted 222 failed: %v", err)
	}

	d1, _ := db.ClaimVOD("111", "user1", "twitch.tv", "Title A", staleThreshold)
	d2, _ := db.ClaimVOD("222", "user2", "twitch.tv", "Title B", staleThreshold)
	d3, _ := db.ClaimVOD("333", "user3", "twitch.tv", "Title C", staleThreshold)

	if d1 {
		t.Error("VOD 111 is completed, should not be claimable")
	}
	if d2 {
		t.Error("VOD 222 is completed, should not be claimable")
	}
	if !d3 {
		t.Error("VOD 333 is not in DB, should be claimable")
	}
}
