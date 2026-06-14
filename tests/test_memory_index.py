"""
Tests for L2 indexed memory (FTS5) and the bounded continuity-pipeline wiring.

All tests use an isolated temp DB (the live oracle_memory.db is never touched).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import memory  # noqa: E402


@pytest.fixture
def tmpdb(tmp_path, monkeypatch):
    db = tmp_path / "test_mem.db"
    monkeypatch.setattr(memory, "DB_PATH", db)
    memory._FTS_AVAILABLE = None  # reset cached probe for the fresh DB
    memory.init_db()
    return db


def _ins(text, *, source_type="human_stated", approval="approved", conf=0.9):
    prov = {
        "source_type": source_type, "source_id": "test", "observed_at": "2026-06-14",
        "confidence": conf, "transformation_history": [],
        "canonical_status": "test", "approval_status": approval,
    }
    return memory.insert_durable_fact(text, prov)


def test_fts5_available():
    import sqlite3
    c = sqlite3.connect(":memory:")
    c.execute("CREATE VIRTUAL TABLE t USING fts5(x)")  # must not raise


def test_insert_auto_indexes_and_search(tmpdb):
    _ins("The recall fabric uses FTS5 indexing for fast retrieval.")
    hits = memory.search_memory_index("recall fabric")
    assert any("recall fabric" in h["fact_text"].lower() for h in hits)


def test_human_stated_outranks_generated(tmpdb):
    _ins("Continuity intelligence preserves identity across restarts.",
         source_type="generated", approval="unverified", conf=0.4)
    _ins("Continuity intelligence is the core of what Noah is building.",
         source_type="human_stated", approval="approved", conf=0.9)
    hits = memory.search_memory_index("continuity intelligence", limit=5)
    assert hits
    assert hits[0]["source_type"] == "human_stated", "authoritative fact should rank first"


def test_superseded_excluded_then_included(tmpdb):
    a = _ins("ORACLE runs on commit aaaaaaa.")
    b = _ins("ORACLE runs on commit bbbbbbb.")
    memory.mark_superseded(a, b)
    ids_default = {h["id"] for h in memory.search_memory_index("oracle runs commit", limit=10)}
    assert a not in ids_default and b in ids_default
    ids_all = {h["id"] for h in memory.search_memory_index("oracle runs commit", limit=10,
                                                            exclude_superseded=False)}
    assert a in ids_all


def test_get_memory_by_id(tmpdb):
    rid = _ins("A uniquely findable fact about the vault layer.")
    rec = memory.get_memory_by_id(rid)
    assert rec and rec["id"] == rid and "vault layer" in rec["fact_text"]


def test_find_contradictions_surfaces_negation(tmpdb):
    _ins("ORACLE memory is stored locally on the node.")
    _ins("ORACLE memory is not stored locally on the node.")
    conflicts = memory.find_contradictions("oracle memory stored locally")
    assert any(c["type"] == "negation_polarity" for c in conflicts)


def test_order_recent_vs_relevance(tmpdb):
    _ins("alpha topic mention one")
    last = _ins("alpha topic mention two")
    recent = memory.search_memory_index("alpha topic", order="recent", limit=5)
    assert recent and recent[0]["id"] == last


def test_migrate_is_idempotent(tmpdb):
    _ins("idempotency check fact")
    r1 = memory.migrate_memory_index()
    r2 = memory.migrate_memory_index()
    import sqlite3
    c = sqlite3.connect(tmpdb)
    facts = c.execute("SELECT COUNT(*) FROM durable_facts").fetchone()[0]
    idx = c.execute("SELECT COUNT(*) FROM durable_fts").fetchone()[0]
    assert facts == idx == 1
    assert r1["fts5"] and r2["fts5"]


def test_recall_persists_across_reconnect(tmpdb):
    _ins("persistent fact survives a fresh connection.")
    # search_memory_index opens a fresh get_conn() each call → proves persistence
    assert memory.search_memory_index("persistent fact survives")


# ── pipeline wiring: dormant continuity pipeline now reachable in production ────
def test_session_continuity_wiring_writes(tmpdb, monkeypatch):
    import oracle_server as srv
    history = [
        {"role": "user", "content": "I want ORACLE to maintain resident awareness of the build and "
                                    "reconcile git, runtime, and vision into a verified current state."},
        {"role": "assistant", "content": "Understood, staying local and grounded."},
    ]
    res = srv._run_session_continuity(history, "sess-test")
    assert "error" not in res, res
    assert isinstance(res.get("written"), int)
    assert res.get("written", 0) + res.get("staged", 0) + res.get("discarded", 0) >= 1
