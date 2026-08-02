"""SQLite state management for the primary source download pipeline."""
import sqlite3
import os
import json
import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "download_state.sqlite")
DB_PATH = os.path.abspath(DB_PATH)

SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    row_id INTEGER PRIMARY KEY,
    course TEXT,
    unit TEXT,
    standard TEXT,
    asset_type TEXT,
    source_page_url TEXT,
    direct_download_url TEXT,
    target_filename_template TEXT,
    drive_subfolder TEXT,
    title TEXT,
    creator_or_institution TEXT,
    date TEXT,
    license TEXT,
    attribution TEXT,
    repository TEXT,
    link_type TEXT,
    status TEXT,
    resolved_url TEXT,
    local_path TEXT,
    citation_path TEXT,
    sha256 TEXT,
    original_extension TEXT,
    file_size_bytes INTEGER,
    image_width INTEGER,
    image_height INTEGER,
    error_message TEXT,
    attempts INTEGER DEFAULT 0,
    last_attempt_at TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS log_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    row_id INTEGER,
    ts TEXT,
    event TEXT,
    detail TEXT
);
"""

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    return conn

def now():
    return datetime.datetime.utcnow().isoformat() + "Z"

def upsert_row_from_manifest(conn, row_id, row):
    conn.execute("""
    INSERT INTO assets (
        row_id, course, unit, standard, asset_type, source_page_url,
        direct_download_url, target_filename_template, drive_subfolder,
        title, creator_or_institution, date, license, attribution,
        repository, link_type, status, created_at, updated_at
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT(row_id) DO NOTHING
    """, (
        row_id, row["course"], row["unit"], row["standard"], row["asset_type"],
        row["source_page_url"], row["direct_download_url"], row["target_filename"],
        row["drive_subfolder"], row["title"], row["creator_or_institution"],
        row["date"], row["license"], row["attribution"], row["repository"],
        row["link_type"], "PENDING", now(), now()
    ))
    conn.commit()

def update_status(conn, row_id, status, **fields):
    fields["status"] = status
    fields["updated_at"] = now()
    set_clause = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [row_id]
    conn.execute(f"UPDATE assets SET {set_clause} WHERE row_id=?", values)
    conn.commit()
    log_event(conn, row_id, f"STATUS:{status}", json.dumps({k: v for k, v in fields.items() if k not in ("updated_at",)}, default=str))

def log_event(conn, row_id, event, detail=""):
    conn.execute("INSERT INTO log_events (row_id, ts, event, detail) VALUES (?,?,?,?)",
                 (row_id, now(), event, detail))
    conn.commit()

def get_row(conn, row_id):
    cur = conn.execute("SELECT * FROM assets WHERE row_id=?", (row_id,))
    return cur.fetchone()

def get_all(conn):
    cur = conn.execute("SELECT * FROM assets ORDER BY row_id")
    return cur.fetchall()

def increment_attempts(conn, row_id):
    conn.execute("UPDATE assets SET attempts = attempts + 1, last_attempt_at=? WHERE row_id=?", (now(), row_id))
    conn.commit()
