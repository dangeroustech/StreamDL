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

// ShouldDownloadVOD returns true if the VOD should be (re)downloaded:
// not in DB, status is 'failed', or status is 'downloading' with started_at
// older than staleThreshold (crash recovery).
func (v *VodDB) ShouldDownloadVOD(vodID string, staleThreshold time.Duration) (bool, error) {
	var status string
	var startedAt string
	err := v.db.QueryRow(
		"SELECT status, started_at FROM downloaded_vods WHERE vod_id = ?", vodID,
	).Scan(&status, &startedAt)
	if err == sql.ErrNoRows {
		return true, nil
	}
	if err != nil {
		return false, err
	}

	switch status {
	case "completed":
		return false, nil
	case "failed":
		return true, nil
	case "downloading":
		started, err := time.Parse(time.RFC3339, startedAt)
		if err != nil {
			log.Warnf("Could not parse started_at for VOD %s: %v", vodID, err)
			return true, nil
		}
		return time.Since(started) > staleThreshold, nil
	default:
		return true, nil
	}
}

// MarkVODStarted records a VOD as in-progress. Resets status if retrying.
func (v *VodDB) MarkVODStarted(vodID, user, site, title string) error {
	now := time.Now().UTC().Format(time.RFC3339)
	_, err := v.db.Exec(
		`INSERT INTO downloaded_vods (vod_id, user, site, title, status, started_at)
		 VALUES (?, ?, ?, ?, 'downloading', ?)
		 ON CONFLICT(vod_id) DO UPDATE SET status='downloading', started_at=?, completed_at=NULL`,
		vodID, user, site, title, now, now,
	)
	if err != nil {
		log.Errorf("Failed to mark VOD %s as started: %v", vodID, err)
	}
	return err
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
