package main

import (
	"database/sql"
	"os"
	"path/filepath"
	"time"

	log "github.com/sirupsen/logrus"
	_ "modernc.org/sqlite"
)

// VodDB tracks VOD download state in a SQLite database.
type VodDB struct {
	db *sql.DB
}

// InitVodDB opens or creates a SQLite database at the given path.
func InitVodDB(dbPath string) (*VodDB, error) {
	if err := os.MkdirAll(filepath.Dir(dbPath), 0755); err != nil {
		return nil, err
	}

	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		return nil, err
	}

	_, err = db.Exec(`CREATE TABLE IF NOT EXISTS downloaded_vods (
		vod_id TEXT PRIMARY KEY,
		user TEXT NOT NULL,
		site TEXT NOT NULL,
		title TEXT NOT NULL,
		status TEXT NOT NULL DEFAULT 'downloading',
		started_at TEXT NOT NULL,
		completed_at TEXT
	)`)
	if err != nil {
		db.Close()
		return nil, err
	}

	return &VodDB{db: db}, nil
}

// Close closes the database connection.
func (v *VodDB) Close() error {
	return v.db.Close()
}

// ClaimVOD atomically checks whether a VOD should be downloaded and marks it as
// in-progress in a single operation. Returns true if the claim was successful
// (VOD is new, failed, or stale). Returns false if the VOD is completed or
// already being downloaded by another goroutine.
func (v *VodDB) ClaimVOD(vodID, user, site, title string, staleThreshold time.Duration) (bool, error) {
	now := time.Now().UTC().Format(time.RFC3339)
	staleCutoff := time.Now().Add(-staleThreshold).UTC().Format(time.RFC3339)

	res, err := v.db.Exec(
		`INSERT INTO downloaded_vods (vod_id, user, site, title, status, started_at)
		 VALUES (?, ?, ?, ?, 'downloading', ?)
		 ON CONFLICT(vod_id) DO UPDATE SET status='downloading', started_at=?, completed_at=NULL
		 WHERE downloaded_vods.status = 'failed'
		    OR (downloaded_vods.status = 'downloading' AND downloaded_vods.started_at <= ?)`,
		vodID, user, site, title, now, now, staleCutoff,
	)
	if err != nil {
		log.Errorf("Failed to claim VOD %s: %v", vodID, err)
		return false, err
	}

	rows, err := res.RowsAffected()
	if err != nil {
		return false, err
	}
	return rows > 0, nil
}

// MarkVODCompleted marks a VOD as successfully downloaded.
func (v *VodDB) MarkVODCompleted(vodID string) error {
	now := time.Now().UTC().Format(time.RFC3339)
	_, err := v.db.Exec(
		"UPDATE downloaded_vods SET status='completed', completed_at=? WHERE vod_id=?",
		now, vodID,
	)
	if err != nil {
		log.Errorf("Failed to mark VOD %s as completed: %v", vodID, err)
	}
	return err
}

// MarkVODFailed marks a VOD download as failed so it will be retried.
func (v *VodDB) MarkVODFailed(vodID string) error {
	_, err := v.db.Exec(
		"UPDATE downloaded_vods SET status='failed' WHERE vod_id=?",
		vodID,
	)
	if err != nil {
		log.Errorf("Failed to mark VOD %s as failed: %v", vodID, err)
	}
	return err
}
