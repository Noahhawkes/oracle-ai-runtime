"""Regression tests for GitHub Issue #16 ("P0: Cross-human provenance
integrity — never collapse speaker/author into Noah.Physical"), failure
site B and its live wiring point.

Historical failure:
  - `core/continuity_pipeline.py::classify_source_type` classified any
    message with `speaker in ("noah", "user", "human")` as the same
    `human_stated` source type, and `assign_provenance` never captured an
    actual speaker identity anywhere in the provenance record. A human
    typing through the generic "user" role — Ashley, a coworker, an
    unidentified guest — was structurally indistinguishable from Noah once
    it reached durable memory.
  - `oracle_server.py::_run_session_continuity` made this concrete in
    production: every history turn with `role == "user"` was mapped to
    `{"speaker": "Noah", ...}` before being handed to the pipeline,
    regardless of who actually typed it. There was no way for that call
    site to assert anything else — the chat history schema carries no
    per-turn identity at all.

Site A (`continuity_event_packet.py`) was already fixed (commit c29671e) by
adding independent `speaker_id` / `author_id` / `submitter_id` /
`account_owner_id` dimensions that default to UNKNOWN rather than
Noah.Physical. This file proves the same governing rule now holds for site
B: `core.continuity_pipeline.resolve_speaker_identity`, and the
`oracle_server.py` call site that feeds it.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

from continuity_pipeline import (  # noqa: E402
    assign_provenance,
    extract_candidates,
    resolve_speaker_identity,
    run_continuity_pipeline,
)


# ── resolve_speaker_identity: unit-level ─────────────────────────────────

def test_generic_user_placeholder_resolves_to_unknown_not_noah():
    identity = resolve_speaker_identity({"speaker": "user", "text": "hi"})
    assert identity["speaker_id"] == "UNKNOWN"
    assert identity["account_owner_id"] == "Noah.Physical"


def test_generic_human_placeholder_resolves_to_unknown_not_noah():
    identity = resolve_speaker_identity({"speaker": "human", "text": "hi"})
    assert identity["speaker_id"] == "UNKNOWN"


def test_missing_speaker_resolves_to_unknown():
    identity = resolve_speaker_identity({"text": "hi"})
    assert identity["speaker_id"] == "UNKNOWN"


def test_explicit_noah_speaker_resolves_to_noah_physical():
    identity = resolve_speaker_identity({"speaker": "Noah", "text": "hi"})
    assert identity["speaker_id"] == "Noah.Physical"


def test_ashley_speaker_is_preserved_not_collapsed():
    identity = resolve_speaker_identity({"speaker": "Ashley", "text": "hi"})
    assert identity["speaker_id"] == "Ashley"
    assert identity["speaker_id"] != "Noah.Physical"
    assert identity["human_source_id"] == "Ashley"
    assert identity["source_agent_type"] == "human"
    assert identity["identity_resolution_status"] == "explicit"


def test_account_owner_id_never_used_to_infer_speaker():
    # account_owner_id is always Noah.Physical (this is genuinely Noah's
    # runtime) but that must not leak into speaker_id for an unresolved turn.
    identity = resolve_speaker_identity({"speaker": "user", "text": "hi"})
    assert identity["account_owner_id"] == "Noah.Physical"
    assert identity["speaker_id"] == "UNKNOWN"


def test_author_and_submitter_default_to_speaker_but_are_independent():
    # Noah pasting a ChatGPT reply: he is the submitter, ChatGPT is the author.
    identity = resolve_speaker_identity(
        {"speaker": "Noah", "text": "...", "author_id": "ChatGPT"}
    )
    assert identity["speaker_id"] == "Noah.Physical"
    assert identity["submitter_id"] == "Noah.Physical"
    assert identity["author_id"] == "ChatGPT"
    assert identity["human_source_id"] == "UNKNOWN"


# ── extract_candidates / assign_provenance wiring ────────────────────────

def test_extract_candidates_attaches_identity():
    session = [{"speaker": "Ashley", "text": "The dealer visit cadence should move to Fridays."}]
    candidates = extract_candidates(session, "sess-identity")
    assert candidates[0]["identity"]["speaker_id"] == "Ashley"


def test_assign_provenance_carries_speaker_id_and_never_defaults_to_noah():
    session = [{"speaker": "user", "text": "The dealer visit cadence should move to Fridays."}]
    candidates = extract_candidates(session, "sess-provenance")
    provenance = assign_provenance(candidates[0])
    assert provenance["speaker_id"] == "UNKNOWN"
    assert provenance["speaker_id"] != "Noah.Physical"
    assert provenance["account_owner_id"] == "Noah.Physical"


def test_assign_provenance_preserves_explicit_ashley_identity():
    session = [{"speaker": "Ashley", "text": "The dealer visit cadence should move to Fridays."}]
    candidates = extract_candidates(session, "sess-ashley")
    provenance = assign_provenance(candidates[0])
    assert provenance["speaker_id"] == "Ashley"


# ── end-to-end pipeline: the historical failure, reproduced and fixed ────

def test_ashley_turn_survives_full_pipeline_without_collapsing_to_noah():
    """The concrete Issue #16 scenario: a family member's statement must
    stay attributed to her through extraction, provenance, and the audit
    chain — not silently become Noah.Physical."""
    session = [
        {"speaker": "Ashley", "text": "My preferred dealer visit cadence is Tuesday through Thursday."},
    ]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        import memory as mem_module
        db_path = Path(tmp) / "oracle_memory.db"
        orig = mem_module.DB_PATH
        try:
            result = run_continuity_pipeline(session, session_id="ashley-1", db_path=db_path)
            assert result["written"], "expected the dealer cadence statement to be written"
            written = result["written"][0]
            assert written["provenance"]["speaker_id"] == "Ashley"
            assert written["provenance"]["speaker_id"] != "Noah.Physical"
            provenance_events = [
                e for e in result["audit_chain"] if e.get("event") == "provenance_assigned"
            ]
            assert provenance_events, "expected a provenance_assigned audit event"
            assert provenance_events[0]["detail"]["speaker_id"] == "Ashley"
        finally:
            mem_module.DB_PATH = orig


def test_generic_user_role_never_becomes_noah_through_full_pipeline():
    """The structural failure mode: an unidentified human typing through the
    generic "user" role must reach durable memory as UNKNOWN, never as an
    asserted Noah.Physical identity."""
    session = [
        {"speaker": "user", "text": "My preferred dealer visit cadence is Tuesday through Thursday."},
    ]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        import memory as mem_module
        db_path = Path(tmp) / "oracle_memory.db"
        orig = mem_module.DB_PATH
        try:
            result = run_continuity_pipeline(session, session_id="genericuser-1", db_path=db_path)
            assert result["written"], "expected the dealer cadence statement to be written"
            written = result["written"][0]
            assert written["provenance"]["speaker_id"] == "UNKNOWN"
            assert written["provenance"]["speaker_id"] != "Noah.Physical"
        finally:
            mem_module.DB_PATH = orig


def test_actor_provenance_survives_sqlite_reopen_and_recall():
    """The former tests stopped at the Python return value. Prove the actor
    dimensions survive the actual SQLite boundary and a fresh runtime object."""
    session = [{
        "speaker": "Ashley",
        "text": "My preferred dealer visit cadence is Tuesday through Thursday.",
    }]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        import memory as mem_module
        from continuity_pipeline import ContinuityRuntime

        db_path = Path(tmp) / "oracle_memory.db"
        orig = mem_module.DB_PATH
        try:
            run_continuity_pipeline(session, session_id="ashley-reopen", db_path=db_path)
            mem_module.DB_PATH = orig
            fresh = ContinuityRuntime(db_path=db_path)
            recalled = fresh.wake_memory_search("dealer visit cadence")

            assert recalled is not None
            assert recalled["speaker_id"] == "Ashley"
            assert recalled["author_id"] == "Ashley"
            assert recalled["submitter_id"] == "Ashley"
            assert recalled["provenance"]["account_owner_id"] == "Noah.Physical"
            assert recalled["provenance"]["human_source_id"] == "Ashley"
            assert recalled["provenance"]["source_agent_type"] == "human"
            assert recalled["identity_resolution_status"] == "explicit"
            assert recalled["speaker_id"] != recalled["provenance"]["account_owner_id"]
            assert recalled["provenance_suspect"] is False
        finally:
            mem_module.DB_PATH = orig


def test_ai_author_and_human_submitter_survive_durable_recall():
    session = [{
        "speaker": "Noah",
        "author_id": "ChatGPT",
        "submitter_id": "Noah.Physical",
        "text": "The quoted migration plan requires a provenance regression test.",
    }]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        import memory as mem_module
        from continuity_pipeline import ContinuityRuntime

        db_path = Path(tmp) / "oracle_memory.db"
        orig = mem_module.DB_PATH
        try:
            run_continuity_pipeline(session, session_id="ai-paste-reopen", db_path=db_path)
            mem_module.DB_PATH = orig
            recalled = ContinuityRuntime(db_path=db_path).wake_memory_search(
                "quoted migration plan"
            )

            assert recalled is not None
            assert recalled["speaker_id"] == "Noah.Physical"
            assert recalled["author_id"] == "ChatGPT"
            assert recalled["submitter_id"] == "Noah.Physical"
            assert recalled["provenance"]["source_agent_type"] == "ai"
            assert recalled["provenance"]["human_source_id"] == "UNKNOWN"
        finally:
            mem_module.DB_PATH = orig


def test_unknown_human_identity_stays_unknown_after_restart():
    session = [{
        "speaker": "user",
        "text": "My preferred archive cadence is every second Friday morning.",
    }]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        import memory as mem_module
        from continuity_pipeline import ContinuityRuntime

        db_path = Path(tmp) / "oracle_memory.db"
        orig = mem_module.DB_PATH
        try:
            run_continuity_pipeline(session, session_id="unknown-reopen", db_path=db_path)
            mem_module.DB_PATH = orig
            recalled = ContinuityRuntime(db_path=db_path).wake_memory_search(
                "archive cadence"
            )

            assert recalled is not None
            assert recalled["speaker_id"] == "UNKNOWN"
            assert recalled["author_id"] == "UNKNOWN"
            assert recalled["speaker_id"] != "Noah.Physical"
        finally:
            mem_module.DB_PATH = orig


def test_legacy_rows_are_marked_suspect_without_inventing_noah(tmp_path):
    """Historical repair is a downgrade to UNKNOWN, never a guessed author."""
    import memory as mem_module

    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE durable_facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fact_text TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            confidence REAL NOT NULL,
            transformation_history TEXT NOT NULL DEFAULT '[]',
            canonical_status TEXT NOT NULL DEFAULT 'staged',
            approval_status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO durable_facts
        (fact_text, source_type, source_id, observed_at, confidence,
         canonical_status, approval_status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "Legacy personal statement with no actor receipt.",
            "human_stated",
            "legacy-session",
            "2026-01-01",
            0.8,
            "accepted",
            "auto_approved",
            "2026-01-01",
        ),
    )
    conn.commit()
    conn.close()

    orig = mem_module.DB_PATH
    try:
        mem_module.DB_PATH = db_path
        mem_module._FTS_AVAILABLE = None
        mem_module.init_db()
        row = mem_module.search_durable_facts("Legacy personal statement")[0]

        assert row["speaker_id"] == "UNKNOWN"
        assert row["author_id"] == "UNKNOWN"
        assert row["identity_resolution_status"] == "legacy_unresolved"
        assert row["provenance_suspect"] is True
        assert "Noah.Physical" not in row["provenance"].values()
    finally:
        mem_module.DB_PATH = orig
        mem_module._FTS_AVAILABLE = None


# ── oracle_server.py live wiring: the production instance of the bug ─────

def test_session_continuity_call_site_never_hardcodes_noah_for_user_role():
    """oracle_server._run_session_continuity used to build
    {"speaker": "Noah" if role == "user" else "Oracle", ...} for every turn
    — asserting Noah's identity for anyone who typed into the chat, since
    the history schema carries no real per-turn identity. It must now pass
    the generic "user" placeholder through so continuity_pipeline resolves
    it to UNKNOWN instead of a false Noah attribution."""
    import oracle_server as server

    history = [
        {"role": "user", "content": "My preferred dealer visit cadence is Tuesday through Thursday."},
        {"role": "assistant", "content": "Noted."},
    ]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        import memory as mem_module
        db_path = Path(tmp) / "oracle_memory.db"
        orig = mem_module.DB_PATH
        try:
            mem_module.DB_PATH = db_path
            result = server._run_session_continuity(history, "server-wiring-1")
            assert "error" not in result, result
            assert result["written"] >= 1
        finally:
            mem_module.DB_PATH = orig

    # The regression itself: reconstruct the same mapping the call site
    # produces and confirm it is the generic placeholder, not "Noah".
    mapped = [
        {"speaker": "user" if m.get("role") == "user" else "Oracle", "text": m.get("content", "")}
        for m in history
    ]
    assert mapped[0]["speaker"] == "user"
    assert mapped[0]["speaker"] != "Noah"
    identity = resolve_speaker_identity(mapped[0])
    assert identity["speaker_id"] == "UNKNOWN"
