import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .collectors.base import Job

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    dedupe_key TEXT NOT NULL,
    source TEXT,
    company TEXT,
    title TEXT,
    location TEXT,
    url TEXT,
    posted_at TEXT,
    first_seen TEXT NOT NULL,
    status TEXT NOT NULL,              -- filtered | duplicate | pending | scored
    filter_reason TEXT,
    match_path TEXT,                   -- role | degree
    description TEXT,                  -- kept only until scored
    score INTEGER,
    eligible INTEGER,
    eligibility_note TEXT,
    reasons TEXT,
    missing_skills TEXT,
    score_attempts INTEGER NOT NULL DEFAULT 0,
    scored_at TEXT,
    alerted_at TEXT,
    digest_queued INTEGER NOT NULL DEFAULT 0,
    digested_at TEXT,
    application_status TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_dedupe ON jobs(dedupe_key);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""
MAX_SCORE_ATTEMPTS = 3


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for key in ("reasons", "missing_skills"):
        d[key] = json.loads(d[key]) if d.get(key) else []
    return d


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        columns = {r["name"] for r in self.conn.execute("PRAGMA table_info(jobs)")}
        if "match_path" not in columns:
            self.conn.execute("ALTER TABLE jobs ADD COLUMN match_path TEXT")

    def commit(self) -> None:
        self.conn.commit()

    def has_job(self, job_id: str) -> bool:
        return self.conn.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone() is not None

    def has_dedupe_key(self, key: str) -> bool:
        return self.conn.execute("SELECT 1 FROM jobs WHERE dedupe_key = ? LIMIT 1", (key,)).fetchone() is not None

    def add_job(self, job: Job, status: str, reason: str | None = None, match_path: str | None = None) -> None:
        self.conn.execute(
            """INSERT OR IGNORE INTO jobs
               (id, dedupe_key, source, company, title, location, url, posted_at, first_seen, status, filter_reason,
                match_path, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                job.id, job.dedupe_key, job.source, job.company, job.title, job.location, job.url,
                job.posted_at, now_iso(), status, reason, match_path or None,
                job.description if status == "pending" else None,
            ),
        )

    def get(self, job_id: str) -> dict:
        return _to_dict(self.conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())

    def pending(self, limit: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM jobs WHERE status = 'pending' AND score_attempts < ? ORDER BY first_seen LIMIT ?",
            (MAX_SCORE_ATTEMPTS, limit),
        )
        return [_to_dict(r) for r in rows]

    def record_score_failure(self, job_id: str) -> None:
        self.conn.execute("UPDATE jobs SET score_attempts = score_attempts + 1 WHERE id = ?", (job_id,))

    def save_score(self, job_id: str, result: dict) -> None:
        self.conn.execute(
            """UPDATE jobs SET status = 'scored', score = ?, eligible = ?, eligibility_note = ?, reasons = ?,
               missing_skills = ?, scored_at = ?, description = NULL WHERE id = ?""",
            (
                result["score"], int(result["eligible"]), result["eligibility_note"],
                json.dumps(result["reasons"]), json.dumps(result["missing_skills"]), now_iso(), job_id,
            ),
        )

    def mark_alerted(self, job_id: str) -> None:
        self.conn.execute("UPDATE jobs SET alerted_at = ? WHERE id = ?", (now_iso(), job_id))

    def queue_for_digest(self, job_ids: list[str]) -> None:
        self.conn.executemany("UPDATE jobs SET digest_queued = 1 WHERE id = ?", [(i,) for i in job_ids])

    def digest_queue(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM jobs WHERE digest_queued = 1 AND digested_at IS NULL ORDER BY score DESC, first_seen"
        )
        return [_to_dict(r) for r in rows]

    def mark_digested(self, job_ids: list[str]) -> None:
        ts = now_iso()
        self.conn.executemany("UPDATE jobs SET digested_at = ? WHERE id = ?", [(ts, i) for i in job_ids])

    def get_meta(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))

    def prune(self, days: int = 90) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
        self.conn.execute("DELETE FROM jobs WHERE first_seen < ? AND status IN ('filtered', 'duplicate')", (cutoff,))
