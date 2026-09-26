"""Smoke tests for ORACLE Alive v0.1 — Resident Loop Mode (core/alive_loop.py).

Proves the heartbeat observes approved sources only, writes audit receipts,
never writes durable memory / takes external / destructive action, rejects
secrets and unapproved paths, and that the loop can start and stop.
No LLM, no network, isolated temp paths.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import alive_loop as al  # noqa: E402


def _isolate(tmp_path):
    al.HEARTBEAT_PATH = tmp_path / "alive_heartbeat.jsonl"
    al.ALIVE_STATE_PATH = tmp_path / "alive_state.json"


def test_module_smoke_runner_passes():
    assert al.run_smoke_tests() == 0


def test_heartbeat_writes_receipt_with_guarantees(tmp_path):
    _isolate(tmp_path)
    rec = al.tick()
    assert al.HEARTBEAT_PATH.exists()
    assert rec["durable_memory_writes"] == 0
    assert rec["external_actions"] == 0
    assert rec["network_calls"] == 0
    assert rec["destructive_actions"] == 0
    assert rec["raw_recording"] is False
    assert rec["local_only"] is True
    assert rec["outcome"] in {
        al.OUT_NO_SIGNAL, al.OUT_CONTEXT_UPDATE, al.OUT_SUGGESTED_ACTION,
        al.OUT_STALE_WARNING, al.OUT_CONTRADICTION, al.OUT_MEMORY_CANDIDATE,
        al.OUT_BUILD_BLOCKAGE,
    }


def test_approved_paths_only(tmp_path):
    _isolate(tmp_path)
    assert al.is_approved_path(str(al._SM_DIR / "intake_source_map_latest.json"))
    assert not al.is_approved_path("C:\\Users\\noahh\\secrets.txt")
    assert not al.is_approved_path("G:\\My Drive\\doc.txt")
    assert not al.is_approved_path(str(al.RUNTIME_ROOT / ".env"))
    # Repo source code is not an approved *read* subtree for the heartbeat.
    assert not al.is_approved_path(str(al.RUNTIME_ROOT / "core" / "oracle_server.py"))


def test_start_and_stop(tmp_path):
    _isolate(tmp_path)
    try:
        s_on = al.start(interval=999)
        assert s_on["running"] is True
        s_off = al.stop()
        assert s_off["running"] is False
    finally:
        al.stop()


def test_tick_does_not_create_durable_memory(tmp_path):
    _isolate(tmp_path)
    # The durable memory DB / project_states must not be created or mutated by a tick.
    before = (al.RUNTIME_ROOT / "Memory" / "project_states.json")
    before_mtime = before.stat().st_mtime if before.exists() else None
    al.tick()
    after_mtime = before.stat().st_mtime if before.exists() else None
    assert before_mtime == after_mtime  # unchanged (or still absent)
