import sqlite3
import json
from datetime import datetime
from pathlib import Path
from root import ROOT

DB_PATH = ROOT / "Memory" / "oracle_memory.db"


def get_conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                summary TEXT
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(category, key)
            );
            CREATE TABLE IF NOT EXISTS projects (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL UNIQUE,
                status      TEXT NOT NULL DEFAULT 'active',
                created_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS project_notes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id  INTEGER NOT NULL,
                note        TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );
            CREATE TABLE IF NOT EXISTS people (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL UNIQUE,
                role        TEXT,
                created_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS person_notes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id   INTEGER NOT NULL,
                note        TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                FOREIGN KEY (person_id) REFERENCES people(id)
            );
        """)


def new_session():
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (started_at) VALUES (?)",
            (datetime.now().isoformat(),)
        )
        return cur.lastrowid


def save_message(session_id, role, content):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, datetime.now().isoformat())
        )


def get_recent_messages(session_id, limit=20):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit)
        ).fetchall()
        return list(reversed([{"role": r["role"], "content": r["content"]} for r in rows]))


def upsert_fact(category, key, value):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO facts (category, key, value, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(category, key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (category, key, str(value), datetime.now().isoformat())
        )


def get_facts(category=None):
    with get_conn() as conn:
        if category:
            rows = conn.execute("SELECT category, key, value FROM facts WHERE category = ?", (category,)).fetchall()
        else:
            rows = conn.execute("SELECT category, key, value FROM facts").fetchall()
        return [{"category": r["category"], "key": r["key"], "value": r["value"]} for r in rows]


# --- Projects ---

def add_project(name):
    with get_conn() as conn:
        try:
            conn.execute(
                "INSERT INTO projects (name, created_at) VALUES (?, ?)",
                (name.strip(), datetime.now().isoformat())
            )
            return True
        except Exception:
            return False  # already exists


def add_project_note(name, note):
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM projects WHERE name = ?", (name.strip(),)).fetchone()
        if not row:
            return False
        conn.execute(
            "INSERT INTO project_notes (project_id, note, created_at) VALUES (?, ?, ?)",
            (row["id"], note.strip(), datetime.now().isoformat())
        )
        return True


def recall_project(name):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, status, created_at FROM projects WHERE name = ?",
            (name.strip(),)
        ).fetchone()
        if not row:
            return None
        notes = conn.execute(
            "SELECT note, created_at FROM project_notes WHERE project_id = ? ORDER BY id DESC",
            (row["id"],)
        ).fetchall()
    return {
        "name": row["name"],
        "status": row["status"],
        "notes": [{"note": n["note"], "date": n["created_at"][:10]} for n in notes]
    }


def list_projects():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT name, status FROM projects ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


# --- People ---

def add_person(name, role=None):
    with get_conn() as conn:
        try:
            conn.execute(
                "INSERT INTO people (name, role, created_at) VALUES (?, ?, ?)",
                (name.strip(), role, datetime.now().isoformat())
            )
            return True
        except Exception:
            return False  # already exists


def add_person_note(name, note):
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM people WHERE name = ?", (name.strip(),)).fetchone()
        if not row:
            return False
        conn.execute(
            "INSERT INTO person_notes (person_id, note, created_at) VALUES (?, ?, ?)",
            (row["id"], note.strip(), datetime.now().isoformat())
        )
        return True


def recall_person(name):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, role FROM people WHERE name = ?", (name.strip(),)
        ).fetchone()
        if not row:
            return None
        notes = conn.execute(
            "SELECT note, created_at FROM person_notes WHERE person_id = ? ORDER BY id DESC",
            (row["id"],)
        ).fetchall()
    return {
        "name": row["name"],
        "role": row["role"],
        "notes": [{"note": n["note"], "date": n["created_at"][:10]} for n in notes]
    }
