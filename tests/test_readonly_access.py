from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import readonly_access as ra  # noqa: E402


def test_readonly_access_receipt_grants_reads_but_gates_actions(tmp_path, monkeypatch):
    monkeypatch.setattr(ra, "MEMORY_DIR", tmp_path / "Memory")
    monkeypatch.setattr(ra, "RECEIPT_FILE", tmp_path / "Memory" / "readonly.jsonl")
    monkeypatch.setattr(ra, "LATEST_RECEIPT_FILE", tmp_path / "Memory" / "latest.json")
    monkeypatch.setattr(ra, "discovered_read_roots", lambda: [tmp_path])

    payload = ra.ensure_receipt()

    assert payload["access_status"] == "granted"
    assert payload["access_mode"] == "full_pc_readonly"
    assert payload["approval_required_for_read"] is False
    assert payload["approval_required_for_local_search"] is False
    assert payload["owner_privacy_controls"]["controller"] == "Noah.Physical"
    assert payload["owner_privacy_controls"]["topic_speech_restrictions"] is False
    assert payload["owner_privacy_controls"]["sensitive_file_metadata_inventory"] is True
    assert payload["owner_privacy_controls"]["sensitive_raw_secret_auto_ingest"] is False
    assert "delete_file" in payload["approval_required_for_actions"]
    assert "execute_command" in payload["blocked_without_explicit_approval"]
    latest = json.loads((tmp_path / "Memory" / "latest.json").read_text(encoding="utf-8"))
    assert latest["grant_id"] == ra.GRANT_ID


def test_prompt_context_block_names_read_boundary(tmp_path, monkeypatch):
    monkeypatch.setattr(ra, "MEMORY_DIR", tmp_path / "Memory")
    monkeypatch.setattr(ra, "RECEIPT_FILE", tmp_path / "Memory" / "readonly.jsonl")
    monkeypatch.setattr(ra, "LATEST_RECEIPT_FILE", tmp_path / "Memory" / "latest.json")
    monkeypatch.setattr(ra, "discovered_read_roots", lambda: [tmp_path])

    block = ra.prompt_context_block()

    assert "full-PC READ-ONLY access" in block
    assert "do not require another approval" in block
    assert "topic speech is not approval-gated" in block
    assert "inventoried by metadata" in block
    assert "NOT authority to write" in block
