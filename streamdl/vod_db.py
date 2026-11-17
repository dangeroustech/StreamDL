"""Track VOD download state in SQLite (same file and schema as v3)."""

from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime, timedelta

_SCHEMA = """CREATE TABLE IF NOT EXISTS downloaded_vods (
    vod_id TEXT PRIMARY KEY,
    user TEXT NOT NULL,
    site TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'downloading',
    started_at TEXT NOT NULL,
    completed_at TEXT
)"""

# Claim a VOD if it's new, failed, or a download that has gone stale.
_CLAIM = """INSERT INTO downloaded_vods (vod_id, user, site, title, status, started_at)
VALUES (?, ?, ?, ?, 'downloading', ?)
ON CONFLICT(vod_id) DO UPDATE SET status='downloading', started_at=?, completed_at=NULL
WHERE downloaded_vods.status = 'failed'
   OR (downloaded_vods.status = 'downloading' AND downloaded_vods.started_at <= ?)"""


def _timestamp(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")  # RFC 3339 in UTC, as v3 stored it


class VodDB:
    def __init__(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", mode=0o755, exist_ok=True)
        self._conn = sqlite3.connect(path, isolation_level=None)
        try:
            self._conn.execute(_SCHEMA)
        except sqlite3.Error:
            self._conn.close()
            raise

    def close(self) -> None:
        self._conn.close()

    def claim(
        self, vod_id: str, user: str, site: str, title: str, stale_threshold: float
    ) -> bool:
        """Atomically mark a VOD as downloading; False if it's done or already in progress."""
        now = datetime.now(UTC)
        stamp = _timestamp(now)
        cutoff = _timestamp(now - timedelta(seconds=stale_threshold))
        cur = self._conn.execute(
            _CLAIM, (vod_id, user, site, title, stamp, stamp, cutoff)
        )
        return cur.rowcount > 0

    def mark_completed(self, vod_id: str) -> None:
        cur = self._conn.execute(
            "UPDATE downloaded_vods SET status='completed', completed_at=? WHERE vod_id=?",
            (_timestamp(datetime.now(UTC)), vod_id),
        )
        if cur.rowcount == 0:
            raise LookupError(f"VOD {vod_id} not found in database")

    def mark_failed(self, vod_id: str) -> None:
        cur = self._conn.execute(
            "UPDATE downloaded_vods SET status='failed' WHERE vod_id=?", (vod_id,)
        )
        if cur.rowcount == 0:
            raise LookupError(f"VOD {vod_id} not found in database")

    def status(self, vod_id: str) -> str | None:
        row = self._conn.execute(
            "SELECT status FROM downloaded_vods WHERE vod_id=?", (vod_id,)
        ).fetchone()
        return row[0] if row else None
