"""Smoke tests for the Witness Artifact Lane (core/witness_artifacts.py).

Proves screenshots are stored as candidate artifacts with raw bytes preserved,
idempotent by SHA-256, secrets blocked, witness notes preserved verbatim as
candidate-only, and nothing is promoted to durable memory or moved/deleted.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import witness_artifacts as wa  # noqa: E402


def _isolate(tmp_path):
    wa.DROP_DIR = tmp_path / "screenshot_drops"
    wa.RECEIPTS_PATH = wa.DROP_DIR / "witness_receipts.jsonl"


def test_module_smoke_runner_passes():
    assert wa.run_smoke_tests() == 0


def test_screenshot_stored_raw_preserved(tmp_path):
    _isolate(tmp_path)
    shot = tmp_path / "frame.png"
    shot.write_bytes(b"\x89PNG\r\n\x1a\n" + b"pixels")
    sha = wa._sha256(shot)
    rec = wa.drop_screenshot(str(shot), note="heart in the build")
    assert rec["ingest_status"] == "stored"
    assert rec["classification"] == "candidate"
    assert rec["durable"] is False
    assert rec["sha256"] == sha
    assert Path(rec["stored_path"]).exists()
    assert wa._sha256(Path(rec["stored_path"])) == sha  # byte-for-byte
    assert shot.exists()  # original untouched


def test_idempotent_no_double_store(tmp_path):
    _isolate(tmp_path)
    shot = tmp_path / "frame.png"
    shot.write_bytes(b"same-bytes")
    wa.drop_screenshot(str(shot))
    r2 = wa.drop_screenshot(str(shot))
    assert r2["ingest_status"] == "duplicate"
    assert wa.count_drops() == 1


def test_env_blocked_secret_not_stored(tmp_path):
    _isolate(tmp_path)
    env = tmp_path / ".env"
    env.write_text("API_KEY=sk-secret", encoding="utf-8")
    rec = wa.drop_screenshot(str(env))
    assert rec["classification"] == "secret_risk"
    assert rec["ingest_status"] == "blocked"
    assert rec["stored_path"] == ""
    assert "sk-secret" not in wa.RECEIPTS_PATH.read_text(encoding="utf-8")


def test_witness_note_candidate_only_verbatim(tmp_path):
    _isolate(tmp_path)
    text = "I feel my dad in this moment. This is why witness matters."
    rec = wa.drop_witness_note(text)
    assert rec["kind"] == "witness_note"
    assert rec["classification"] == "candidate"
    assert rec["durable"] is False
    assert rec["text"] == text          # preserved verbatim
    assert rec["interpretation"] is None  # never over-expanded


def test_no_durable_memory_touched(tmp_path):
    _isolate(tmp_path)
    ps = ROOT / "Memory" / "project_states.json"
    before = ps.stat().st_mtime if ps.exists() else None
    shot = tmp_path / "x.png"
    shot.write_bytes(b"abc")
    wa.drop_screenshot(str(shot))
    wa.drop_witness_note("note")
    after = ps.stat().st_mtime if ps.exists() else None
    assert before == after
