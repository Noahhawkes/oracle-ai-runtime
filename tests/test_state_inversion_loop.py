from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

import companion_bootstrap as cb  # noqa: E402


def _make_memory_db(path: Path) -> None:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE sessions (
            id INTEGER PRIMARY KEY,
            started_at TEXT,
            summary TEXT
        );
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY,
            session_id INTEGER,
            role TEXT,
            content TEXT,
            timestamp TEXT
        );
        CREATE TABLE facts (
            id INTEGER PRIMARY KEY,
            category TEXT,
            key TEXT,
            value TEXT,
            updated_at TEXT
        );
        CREATE TABLE audit_chain (
            id INTEGER PRIMARY KEY,
            session_id TEXT,
            event TEXT,
            detail TEXT,
            recorded_at TEXT
        );
        """
    )
    con.execute(
        "INSERT INTO sessions (id, started_at, summary) VALUES (?,?,?)",
        (10, "2026-07-20T10:00:00+00:00", "older session"),
    )
    con.execute(
        "INSERT INTO sessions (id, started_at, summary) VALUES (?,?,?)",
        (11, "2026-07-20T11:00:00+00:00", "state inversion target"),
    )
    con.execute(
        "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?,?,?,?)",
        (11, "assistant", "latest verified state", "2026-07-20T11:05:00+00:00"),
    )
    for idx in range(3):
        sha = f"{idx + 1:064x}"
        con.execute(
            "INSERT INTO facts (category, key, value, updated_at) VALUES (?,?,?,?)",
            (
                "thread_capture",
                f"receipt-{idx}",
                "\n".join(
                    [
                        f"action_id: receipt_action_{idx}",
                        f"raw_sha256: {sha}",
                        "canon_status: candidate",
                        "promotion_status: not_promoted",
                    ]
                ),
                f"2026-07-20T11:0{idx}:00+00:00",
            ),
        )
    con.commit()
    con.close()


def test_state_snapshot_fetches_session_receipts_and_dirty_state_without_git(tmp_path):
    db = tmp_path / "oracle_memory.db"
    _make_memory_db(db)

    result = cb.fetch_state_snapshot(
        current_session=[{"role": "user", "content": "rehydrate the room"}],
        db_path=db,
        root=tmp_path,
    )
    block = cb.format_state_snapshot(result)

    assert result["ok"] is True
    assert result["status"] == "CONNECTED"
    assert result["last_active_session"]["session_id"] == 11
    assert len(result["last_verified_receipts"]) == 3
    assert result["dirty_state"]["subprocess_used"] is False
    assert result["elapsed_seconds"] < cb.PREINFERENCE_BUDGET_SECONDS
    assert block.startswith(cb.STATE_SNAPSHOT_HEADER)
    assert "last_active_session_id: 11" in block
    assert "receipt_1_action_id: receipt_action_2" in block
    assert "model_call_allowed: true" in block


def test_missing_ledger_hard_stops_as_disconnected(tmp_path):
    result = cb.build_pre_inference_context(db_path=tmp_path / "missing.db", root=tmp_path)

    assert result["ok"] is False
    assert result["status"] == "LEDGER_DISCONNECTED"
    assert "model_call_allowed: false" in result["block"]
    assert "fallback_policy: HARD_STOP_LEDGER_DISCONNECTED" in result["block"]


def test_generation_process_receipt_schema(tmp_path):
    db = tmp_path / "oracle_memory.db"
    _make_memory_db(db)
    snapshot = cb.fetch_state_snapshot(
        current_session=[{"role": "user", "content": "write receipt proof"}],
        db_path=db,
        root=tmp_path,
    )

    receipt_result = cb.write_generation_process_receipt(snapshot, output_dir=tmp_path / "receipts")
    receipt = json.loads(Path(receipt_result["receipt_path"]).read_text(encoding="utf-8"))

    assert receipt["model_called"] is True
    assert receipt["context_sources"] == ["oracle_memory.db", "current_session"]
    assert receipt["token_origin"] == "local-model-hash"
    assert receipt["fallback_used"] is False
    assert isinstance(receipt["epistemic_tension"], float)
    assert receipt["last_historical_receipt_id"] == "receipt_action_2"
    assert len(receipt["receipt_hash_sha256"]) == 64


def test_oracle_server_blocks_model_calls_until_state_snapshot_is_available():
    server = (ROOT / "oracle_server.py").read_text(encoding="utf-8")

    companion_gate = server.index("_state_preflight = _bootstrap.pre_inference_context")
    companion_model_call = server.index("lambda: web_engine_response(", companion_gate)
    builder_gate = server.index("_state_preflight = _bootstrap.pre_inference_context", companion_model_call)
    builder_model_call = server.index("lambda: web_engine_response(", builder_gate)

    assert companion_gate < companion_model_call
    assert builder_gate < builder_model_call
    assert server.count("effective_route\": \"ledger_disconnected\"") >= 2
