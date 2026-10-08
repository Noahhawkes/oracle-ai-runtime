"""Deterministically summarize native ORACLE sessions without an LLM call."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memory import DB_PATH, get_conn

RECEIPT_PATH = DB_PATH.parent / "session_summary_backfill.json"
TASK_RE = re.compile(
    r"\b(need|needs|want|wants|please|todo|task|fix|build|implement|create|"
    r"review|connect|wire|clean|remove|stop|start|proceed)\b",
    re.IGNORECASE,
)
CORRECTION_RE = re.compile(
    r"\b(no|not|don't|do not|doesn't|should|shouldn't|instead|wrong|correct|"
    r"actually|must|never)\b",
    re.IGNORECASE,
)
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"(?i)\b(api[_ -]?key|token|password|secret)\s*[:=]\s*\S+"),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean(text: Any, limit: int = 260) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    for pattern in SECRET_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value[:limit]


def _select_signals(messages: list[dict[str, Any]], pattern: re.Pattern[str], limit: int = 3) -> list[str]:
    selected: list[str] = []
    seen: set[str] = set()
    for message in reversed(messages):
        if str(message.get("role") or "").lower() not in {"user", "human"}:
            continue
        text = _clean(message.get("content"))
        key = text.lower()
        if text and pattern.search(text) and key not in seen:
            seen.add(key)
            selected.append(text)
            if len(selected) >= limit:
                break
    return list(reversed(selected))


def summarize_messages(session_id: int, messages: list[dict[str, Any]]) -> str:
    user_messages = [
        _clean(message.get("content"))
        for message in messages
        if str(message.get("role") or "").lower() in {"user", "human"}
        and _clean(message.get("content"))
    ]
    assistant_messages = [
        _clean(message.get("content"))
        for message in messages
        if str(message.get("role") or "").lower() in {"assistant", "oracle"}
        and _clean(message.get("content"))
    ]
    payload = {
        "kind": "derived_session_summary",
        "session_id": session_id,
        "message_count": len(messages),
        "opening_user_context": user_messages[0] if user_messages else None,
        "latest_user_context": user_messages[-1] if user_messages else None,
        "latest_assistant_context": assistant_messages[-1] if assistant_messages else None,
        "task_signals": _select_signals(messages, TASK_RE),
        "correction_signals": _select_signals(messages, CORRECTION_RE),
        "authority": "derived_index_not_canon",
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def empty_summary_count() -> int:
    with get_conn() as conn:
        return int(conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE trim(coalesce(summary,''))=''"
        ).fetchone()[0])


def backfill_summaries(*, dry_run: bool = False, limit: int | None = None) -> dict[str, Any]:
    with get_conn() as conn:
        sessions = conn.execute(
            "SELECT id FROM sessions WHERE trim(coalesce(summary,''))='' ORDER BY id"
        ).fetchall()
        if limit is not None:
            sessions = sessions[:limit]
        updates: list[tuple[str, int]] = []
        skipped_empty = 0
        for session in sessions:
            rows = conn.execute(
                "SELECT role, content FROM messages WHERE session_id=? ORDER BY id",
                (session["id"],),
            ).fetchall()
            messages = [dict(row) for row in rows]
            if not messages:
                skipped_empty += 1
                continue
            updates.append((summarize_messages(int(session["id"]), messages), int(session["id"])))
        if not dry_run and updates:
            conn.executemany("UPDATE sessions SET summary=? WHERE id=?", updates)

    receipt = {
        "operation": "session_summary_backfill",
        "generated_at": _utc_now(),
        "memory_db": str(DB_PATH),
        "dry_run": dry_run,
        "candidate_sessions": len(sessions),
        "summaries_written": 0 if dry_run else len(updates),
        "summaries_previewed": len(updates) if dry_run else 0,
        "empty_sessions_skipped": skipped_empty,
        "summary_authority": "derived_index_not_canon",
    }
    if not dry_run:
        RECEIPT_PATH.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt

