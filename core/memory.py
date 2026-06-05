import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "Memory" / "oracle_memory.db"


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
