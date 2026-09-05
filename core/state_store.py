"""Durable load/save for ORACLE CognitiveState (Cognitive Spine v1, Phase 1).

Extends the existing canonical memory database (Memory/oracle_memory.db,
owned by core/memory.py) with additive, idempotent tables. It does not
modify or duplicate core/memory.py's own tables (sessions/messages/facts/
durable_facts/...) -- this keeps a single physical database file rather
than adding a third live database next to Memory/oracle_memory.db and
existence.db.

This is the ONLY module that persists CognitiveState. It does not define
the schema (core/cognitive_state.py) and does not decide when a transition
happens (core/cognitive_spine.py).

Existence.db decision (Phase 1, see build receipt for full rationale):
CognitiveState persistence deliberately does NOT use existence.db. That
ledger stays exactly as-is, serving its current narrow purpose (SOV1
handoff staging/boundary receipts via core/existence_integration.py) so it
never becomes a second, competing "current ORACLE state" authority.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from cognitive_state import CognitiveState

try:
    from root import ROOT
except Exception:  # pragma: no cover
    ROOT = Path(__file__).resolve().parents[1]

DB_PATH = ROOT / "Memory" / "oracle_memory.db"
GLOBAL_SCOPE = "GLOBAL"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cognitive_states (
    state_id TEXT PRIMARY KEY,
    parent_state_id TEXT,
    session_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    state_json TEXT NOT NULL,
    state_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cognitive_states_parent
    ON cognitive_states(parent_state_id);
CREATE TABLE IF NOT EXISTS cognitive_current (
    scope TEXT PRIMARY KEY,
    state_id TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cognitive_transitions (
    transition_id TEXT PRIMARY KEY,
    prior_state_id TEXT,
    new_state_id TEXT NOT NULL,
    trigger_event TEXT,
    receipt_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cognitive_transitions_new
    ON cognitive_transitions(new_state_id);
"""


def get_conn(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_state_store(db_path: Path | None = None) -> None:
    with get_conn(db_path) as conn:
        conn.executescript(_SCHEMA)


def save_state(state: CognitiveState, *, scope: str = GLOBAL_SCOPE, db_path: Path | None = None) -> None:
    init_state_store(db_path)
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO cognitive_states "
            "(state_id, parent_state_id, session_id, created_at, updated_at, state_json, state_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                state.state_id,
                state.parent_state_id,
                str(state.session_id),
                state.created_at,
                state.updated_at,
                json.dumps(state.to_dict(), ensure_ascii=False),
                state.state_hash,
            ),
        )
        conn.execute(
            "INSERT INTO cognitive_current (scope, state_id, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(scope) DO UPDATE SET "
            "state_id = excluded.state_id, updated_at = excluded.updated_at",
            (scope, state.state_id, state.updated_at),
        )


def load_state(state_id: str, *, db_path: Path | None = None) -> CognitiveState | None:
    if not state_id:
        return None
    init_state_store(db_path)
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT state_json FROM cognitive_states WHERE state_id = ?", (state_id,)
        ).fetchone()
    if row is None:
        return None
    return CognitiveState.from_dict(json.loads(row["state_json"]))


def load_current_state(*, scope: str = GLOBAL_SCOPE, db_path: Path | None = None) -> CognitiveState | None:
    init_state_store(db_path)
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT state_id FROM cognitive_current WHERE scope = ?", (scope,)
        ).fetchone()
    if row is None:
        return None
    return load_state(row["state_id"], db_path=db_path)


def load_lineage(state_id: str, *, limit: int = 20, db_path: Path | None = None) -> list[CognitiveState]:
    """Walk parent_state_id back from state_id. Defensively bounded so a
    corrupted or cyclic chain can never hang the caller."""
    chain: list[CognitiveState] = []
    seen: set[str] = set()
    current = load_state(state_id, db_path=db_path)
    while current is not None and len(chain) < max(1, limit):
        if current.state_id in seen:
            break
        seen.add(current.state_id)
        chain.append(current)
        if not current.parent_state_id:
            break
        current = load_state(current.parent_state_id, db_path=db_path)
    return chain


def save_transition_receipt(receipt: dict[str, Any], *, db_path: Path | None = None) -> None:
    init_state_store(db_path)
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO cognitive_transitions "
            "(transition_id, prior_state_id, new_state_id, trigger_event, receipt_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                receipt.get("transition_id"),
                receipt.get("prior_state_id"),
                receipt.get("new_state_id"),
                receipt.get("trigger_event"),
                json.dumps(receipt, ensure_ascii=False),
                receipt.get("timestamp"),
            ),
        )


def load_transition(transition_id: str, *, db_path: Path | None = None) -> dict[str, Any] | None:
    init_state_store(db_path)
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT receipt_json FROM cognitive_transitions WHERE transition_id = ?",
            (transition_id,),
        ).fetchone()
    return json.loads(row["receipt_json"]) if row else None


def list_recent_transitions(*, limit: int = 20, db_path: Path | None = None) -> list[dict[str, Any]]:
    init_state_store(db_path)
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT receipt_json FROM cognitive_transitions ORDER BY created_at DESC LIMIT ?",
            (max(1, limit),),
        ).fetchall()
    return [json.loads(row["receipt_json"]) for row in rows]
