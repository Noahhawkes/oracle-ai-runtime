"""Canonical Thread Registry (V1) - a thread is a durable backend object, not a
browser session.

Root problem proven in oracle_memory.db: messages are keyed by session_id (no
thread_id), there is no threads table, every boot makes a fresh session, and
thread_engine.py is unwired. So "conversations" fragment into hundreds of
ephemeral session shards.

This module makes a thread a first-class durable row and lets messages attach to
it so a conversation survives restarts. Additive and non-destructive: it only
CREATEs a threads table and adds a nullable thread_id column to messages if
missing. It never deletes conversation data and never invents history -
discovery proposes mappings from existing rows; it does not fabricate threads.

Pure stdlib (sqlite3). Not yet wired into the live /chat path (that is the next,
authorized step; it needs a relight to take effect).
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

THREAD_STATUSES = ("active", "paused", "resolved", "archived")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _has_table(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def ensure_schema(conn: sqlite3.Connection) -> dict[str, Any]:
    """Additive, idempotent. Creates the threads table and adds messages.thread_id
    if absent. Returns what it did."""
    did = {"threads_table_created": False, "thread_id_column_added": False,
           "session_id_column_added": False}
    if not _has_table(conn, "threads"):
        conn.execute(
            """CREATE TABLE threads (
                 thread_id TEXT PRIMARY KEY,
                 title TEXT NOT NULL,
                 created_at TEXT NOT NULL,
                 updated_at TEXT NOT NULL,
                 status TEXT NOT NULL DEFAULT 'active',
                 participants_json TEXT NOT NULL DEFAULT '["Noah.Physical"]',
                 active_goal TEXT,
                 turn_count INTEGER NOT NULL DEFAULT 0,
                 last_event TEXT,
                 runtime_boot_id TEXT,
                 parent_thread TEXT,
                 session_id TEXT
               )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_threads_updated ON threads(updated_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_threads_session ON threads(session_id)")
        did["threads_table_created"] = True
    elif "session_id" not in _columns(conn, "threads"):
        conn.execute("ALTER TABLE threads ADD COLUMN session_id TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_threads_session ON threads(session_id)")
        did["session_id_column_added"] = True
    if _has_table(conn, "messages") and "thread_id" not in _columns(conn, "messages"):
        # nullable, additive: existing rows keep NULL until mapped. No data touched.
        conn.execute("ALTER TABLE messages ADD COLUMN thread_id TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id)")
        did["thread_id_column_added"] = True
    conn.commit()
    return did


def create_thread(conn: sqlite3.Connection, *, title: str, status: str = "active",
                  active_goal: str | None = None, runtime_boot_id: str | None = None,
                  parent_thread: str | None = None) -> str:
    ensure_schema(conn)
    tid = f"thread_{uuid.uuid4().hex[:12]}"
    now = _now()
    conn.execute(
        """INSERT INTO threads
           (thread_id,title,created_at,updated_at,status,active_goal,turn_count,runtime_boot_id,parent_thread)
           VALUES (?,?,?,?,?,?,0,?,?)""",
        (tid, title, now, now, status, active_goal, runtime_boot_id, parent_thread))
    conn.commit()
    return tid


def attach_message(conn: sqlite3.Connection, *, thread_id: str, message_id: int,
                   last_event: str | None = None) -> bool:
    """Attach an existing message row to a thread and bump the thread's counters."""
    cur = conn.execute("UPDATE messages SET thread_id=? WHERE id=?", (thread_id, message_id))
    if cur.rowcount == 0:
        return False
    conn.execute(
        "UPDATE threads SET turn_count=turn_count+1, updated_at=?, last_event=COALESCE(?,last_event) "
        "WHERE thread_id=?", (_now(), last_event, thread_id))
    conn.commit()
    return True


def get_or_create_thread_for_session(conn: sqlite3.Connection, session_id: Any, *,
                                     title: str | None = None,
                                     runtime_boot_id: str | None = None) -> str:
    """One durable thread per session (V1). Idempotent: same session_id -> same
    thread_id across restarts. Threads can later be merged across sessions via
    parent_thread; V1 keeps the conversation from evaporating."""
    ensure_schema(conn)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT thread_id FROM threads WHERE session_id=?",
                       (str(session_id),)).fetchone()
    if row:
        return row["thread_id"]
    tid = f"thread_{uuid.uuid4().hex[:12]}"
    now = _now()
    _lines = str(title or "").strip().splitlines()
    ttl = ((_lines[0] if _lines else "") or f"session {session_id}")[:60]
    conn.execute(
        "INSERT INTO threads (thread_id,title,created_at,updated_at,status,turn_count,"
        "session_id,runtime_boot_id) VALUES (?,?,?,?, 'active', 0, ?, ?)",
        (tid, ttl, now, now, str(session_id), runtime_boot_id))
    conn.commit()
    return tid


def on_message_saved(conn: sqlite3.Connection, *, session_id: Any, message_id: int,
                     role: str, content: str) -> str:
    """Hot-path hook. Attaches a just-saved message to its session's durable thread.
    Best-effort by contract: callers wrap in try/except so chat never breaks on it."""
    tid = get_or_create_thread_for_session(
        conn, session_id, title=content if role == "user" else None)
    # give the thread a real title from the first user turn even if an assistant/
    # system message created it first
    if role == "user":
        _lines = str(content or "").strip().splitlines()
        ttl = ((_lines[0] if _lines else "") or "conversation")[:60]
        conn.execute("UPDATE threads SET title=? WHERE thread_id=? AND "
                     "(title LIKE 'session %' OR title='')", (ttl, tid))
    attach_message(conn, thread_id=tid, message_id=message_id)
    return tid


def get_thread(conn: sqlite3.Connection, thread_id: str) -> dict[str, Any] | None:
    conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT * FROM threads WHERE thread_id=?", (thread_id,)).fetchone()
    return dict(r) if r else None


def thread_messages(conn: sqlite3.Connection, thread_id: str) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(
        "SELECT id,role,content,timestamp FROM messages WHERE thread_id=? ORDER BY id", (thread_id,))]


def list_threads(conn: sqlite3.Connection, limit: int = 50) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(
        "SELECT * FROM threads ORDER BY updated_at DESC LIMIT ?", (limit,))]


def discover_threads_from_sessions(conn: sqlite3.Connection) -> dict[str, Any]:
    """Read-only. Propose recoverable threads from existing session/message rows.
    Invents nothing: sessions with zero messages are reported unrecoverable."""
    if not _has_table(conn, "messages"):
        return {"recoverable": [], "unrecoverable_sessions": 0, "note": "no messages table"}
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT session_id, COUNT(*) n, MIN(timestamp) first_ts, MAX(timestamp) last_ts,
                  (SELECT content FROM messages m2 WHERE m2.session_id=m.session_id AND m2.role='user'
                   ORDER BY id LIMIT 1) first_user
           FROM messages m GROUP BY session_id""").fetchall()
    recoverable = []
    for r in rows:
        if r["n"] and r["n"] > 0:
            _lines = str(r["first_user"] or "").strip().splitlines()
            title = (_lines[0] if _lines else f"session {r['session_id']}")[:60]
            recoverable.append({"session_id": r["session_id"], "message_count": r["n"],
                                "first_ts": r["first_ts"], "last_ts": r["last_ts"],
                                "suggested_title": title})
    total_sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] if _has_table(conn, "sessions") else 0
    return {"recoverable": recoverable, "recoverable_count": len(recoverable),
            "total_sessions": total_sessions,
            "unrecoverable_or_empty_sessions": max(0, total_sessions - len(recoverable)),
            "note": "read-only proposal; no writes; no invented history"}
