import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from cv_tools import ALLOWED_DIR

DB_PATH = ALLOWED_DIR / "jobhunt.db"
STATUSES = ("saved", "applied", "interview", "offer", "rejected", "withdrawn", "skipped")
MAX_DESCRIPTION = 20000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _conn():
    ALLOWED_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT DEFAULT '',
            url TEXT DEFAULT '',
            source TEXT DEFAULT 'pasted',
            description TEXT DEFAULT '',
            status TEXT DEFAULT 'saved',
            notes TEXT DEFAULT '',
            added_at TEXT,
            updated_at TEXT,
            applied_at TEXT
        )""")
    return conn


def save_job(title, company, location="", url="", description="", source="pasted") -> dict:
    title, company = title.strip(), company.strip()
    if not title or not company:
        raise ValueError("title and company are required")
    now = _now()
    with closing(_conn()) as conn:
        row = None
        if url:
            row = conn.execute("SELECT id FROM jobs WHERE url = ?", (url,)).fetchone()
        if row is None:
            row = conn.execute(
                "SELECT id FROM jobs WHERE lower(company) = lower(?) AND lower(title) = lower(?)",
                (company, title)).fetchone()
        if row:
            return {"saved": False, "reason": "already in tracker", "id": row["id"]}
        cur = conn.execute(
            "INSERT INTO jobs (title, company, location, url, source, description, added_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (title, company, location.strip(), url.strip(), source, description[:MAX_DESCRIPTION], now, now))
        conn.commit()
        return {"saved": True, "id": cur.lastrowid}


def list_jobs(status: str = "") -> list:
    if status and status not in STATUSES:
        raise ValueError(f"status must be one of: {', '.join(STATUSES)}")
    query = "SELECT id, title, company, location, url, status, added_at, updated_at, applied_at FROM jobs"
    params = ()
    if status:
        query += " WHERE status = ?"
        params = (status,)
    query += " ORDER BY updated_at DESC"
    with closing(_conn()) as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def get_job(job_id: int) -> dict:
    with closing(_conn()) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        raise ValueError(f"No job with id {job_id}")
    return dict(row)


def update_status(job_id: int, status: str, notes: str = "") -> dict:
    if status not in STATUSES:
        raise ValueError(f"status must be one of: {', '.join(STATUSES)}")
    now = _now()
    with closing(_conn()) as conn:
        row = conn.execute("SELECT applied_at, notes FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise ValueError(f"No job with id {job_id}")
        applied_at = row["applied_at"] or (now if status == "applied" else None)
        conn.execute(
            "UPDATE jobs SET status = ?, notes = ?, updated_at = ?, applied_at = ? WHERE id = ?",
            (status, notes or row["notes"], now, applied_at, job_id))
        conn.commit()
    return {"id": job_id, "status": status}

