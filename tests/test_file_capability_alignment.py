"""File-access capability alignment (.AI:ORACLE_FILE_ACCESS_CAPABILITY_ALIGNMENT).

Root rule under test: read access is not ingest authority, and *mentioning* a
capability is not requesting its execution. Frontend claims must mirror backend
receipts.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import oracle_intent as oi  # noqa: E402
import oracle_server as srv  # noqa: E402


# 1. Quoted / reported "file_ingest" text must not trigger unsupported routing.
def test_quoted_file_ingest_text_does_not_trigger_unsupported_capability():
    reported = (
        "The chat router responds: "
        '"I cannot do that from this runtime yet. Missing capability: file_ingest."'
    )

    assert oi.action_capability(reported) != "file_ingest"
    assert "unsupported_capability_request" not in oi.classify_intent(reported)


def test_status_panel_mentioning_ingest_stays_out_of_mutation_lane():
    snapshot = (
        ".AI:RECURSION_ARENA_ROUND_002B\n"
        "frontend_snapshot_supplied_by_codex:\n"
        "- visible_mode: Talk / Safe / Read All\n"
        "- recall_count: 145\n"
        "- latest_visible_problem: ORACLE reported a missing local ingest capability.\n"
    )

    assert oi.action_capability(snapshot) is None
    assert "unsupported_capability_request" not in oi.classify_intent(snapshot)


# 2. A read-only file status summary stays in talk_lane.
def test_read_only_status_summary_stays_talk_lane():
    for text in (
        "summarize this ingest status",
        "compare the file capability panel",
        "what does this manifest mean",
        "the broker says local file access is available",
        "file_ingest is missing",
    ):
        intents = oi.classify_intent(text)
        assert "unsupported_capability_request" not in intents, text
        assert oi.action_capability(text) not in oi.FILE_MUTATION_CAPS, text


# 3. Explicit ingest execution routes to the staging/build lane.
def test_explicit_ingest_request_routes_to_staging_lane():
    assert oi.action_capability("ingest this folder now") == "file_ingest_stage"

    dispatch = srv._oracle_intent_dispatch("ingest this folder now")
    assert dispatch is not None
    text, route = dispatch
    assert route == "file_ingest_staging_ready"
    assert "FILE INGEST STAGING READY" in text
    assert "Missing capability: file_ingest" not in text
    # Staging is not execution.
    assert "approval" in text.lower()


# 4. Read-only search works without Builder mode.
def test_read_only_search_needs_no_builder_mode():
    for text, expected in (
        ("search my files for the Ellie note", "file_search"),
        ("search the index for continuity", "file_index_read"),
        ("manifest lookup for the source map", "file_manifest_read"),
        ("receipt lookup for the last write", "file_receipt_read"),
    ):
        cap = oi.action_capability(text)
        assert cap == expected, f"{text} -> {cap}"
        assert cap in oi.FILE_READONLY_CAPS
        meta = oi.CAPABILITY_META[cap]
        assert meta["lane"] == "read_only"
        assert meta["requires_approval"] is False


# 5. Builder mode does not bypass approval boundaries.
def test_read_only_caps_never_require_approval_and_mutation_always_does():
    reg = oi.capability_registry()
    for cap in oi.FILE_READONLY_CAPS:
        assert oi.CAPABILITY_META[cap]["requires_approval"] is False, cap
    for cap in ("file_ingest_stage", "file_delete", "file_execute"):
        assert oi.CAPABILITY_META[cap]["requires_approval"] is True, cap
    # Delete/execute are genuinely absent from this runtime.
    assert reg["file_delete"]["status"] == "missing"
    assert reg["file_execute"]["status"] == "missing"


# 6 / 7. Recursion Arena frontend + backend snapshots pass normally.
def test_recursion_arena_frontend_snapshot_is_not_a_capability_request():
    frontend = (
        ".AI:RECURSION_ARENA_ROUND_002C\n"
        "frontend_snapshot_supplied_by_codex:\n"
        "- visible_mode: Talk / Safe / Read All\n"
        "- recall_count: 145\n"
        "- writer: ON\n"
        "- session_seen_in_ui: 335\n"
        "ORACLE, answer on screen only:\n"
        "1. Summarize the visible frontend state in plain English.\n"
    )

    assert oi.action_capability(frontend) is None
    assert "unsupported_capability_request" not in oi.classify_intent(frontend)


def test_recursion_arena_backend_snapshot_is_not_a_capability_request():
    backend = (
        ".AI:RECURSION_ARENA_ROUND_003\n"
        "backend_snapshot_supplied_by_codex:\n"
        "- api_history_session_id: 335\n"
        "- server: 127.0.0.1:7781\n"
        "- server_pid: 73580\n"
        "- api_history_gap: capability/status panel text is visible in the UI but\n"
        "  is not part of /api/history dialogue.\n"
    )

    assert oi.action_capability(backend) is None
    assert "unsupported_capability_request" not in oi.classify_intent(backend)


# 8. A PID supplied without a receipt is unverified, not runtime-proven.
def test_codex_supplied_pid_is_not_treated_as_runtime_evidence():
    claim = "server_pid: 73580 supplied_by codex"

    # Nothing in a supplied snapshot may become an execution request.
    assert oi.action_capability(claim) is None
    # And the surface strips it, so it cannot be mistaken for an imperative.
    assert oi.capability_request_surface(claim).strip() == ""


# 9. Capability claims mirror broker state rather than a hardcoded denial.
def test_available_capability_is_never_reported_missing():
    reg = oi.capability_registry()
    # These read lanes are broker-available; nothing may call them missing.
    for cap in ("file_search", "file_manifest_read", "file_receipt_read"):
        assert reg[cap]["status"] == "available", cap
        assert reg[cap]["failure_message"] == "", cap
    assert "file_ingest" not in oi.CHAT_UNSUPPORTED


# 10. The request surface separates the dialogue from the room around it.
def test_request_surface_keeps_imperatives_and_drops_reports():
    mixed = (
        "the broker says local file access is available\n"
        "- visible_mode: Talk / Safe / Read All\n"
        "ingest this folder now\n"
    )

    surface = oi.capability_request_surface(mixed)
    assert "ingest this folder now" in surface
    assert "broker says" not in surface
    assert "visible_mode" not in surface


def test_mention_of_delete_in_a_prohibition_is_not_a_delete_request():
    prohibition = (
        "Read-only does not mean:\n"
        "- overwrite\n"
        "- delete\n"
        "- execute\n"
    )

    cap = oi.action_capability(prohibition)
    assert cap not in oi.FILE_MUTATION_CAPS
    assert cap != "file_delete"
