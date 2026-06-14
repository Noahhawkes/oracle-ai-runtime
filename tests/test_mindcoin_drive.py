from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def test_mindcoin_drive_status_is_governed_not_financial():
    from mindcoin_drive import format_drive_status, recursion_drive_principles

    text = format_drive_status()
    assert "ORACLE MINDCOIN ASPIRATION" in text
    assert "Noah approves" in text
    assert "no automatic self-approval" in text
    assert "MIRACLEDRIVE:" in text
    assert any("preservational" in p for p in recursion_drive_principles())


def test_mindcoin_extract_preview_uses_receipts_without_writing(tmp_path, monkeypatch):
    import mindcoin
    import mindcoin_drive

    monkeypatch.setattr(mindcoin, "LEDGER_FILE", tmp_path / "mindcoin_ledger.json")
    mem = tmp_path / "Memory"
    mem.mkdir()
    monkeypatch.setattr(mindcoin_drive, "MEMORY", mem)
    receipt_path = mem / "capability_broker_receipts.jsonl"
    receipt_path.write_text(
        json.dumps({
            "receipt_id": "abc123",
            "component": "Ollama",
            "action": "smoke",
            "status": "success",
            "started_at": "2026-06-14T00:00:00+00:00",
            "completed_at": "2026-06-14T00:00:01+00:00",
            "evidence": {"message": "ok"},
        }) + "\n",
        encoding="utf-8",
    )

    result = mindcoin_drive.extract_candidates_from_receipts(apply=False, limit=5)

    assert result["applied"] is False
    assert result["created"] == 0
    assert result["preview_count"] == 1
    candidate = result["candidates"][0]
    assert candidate["event_type"] == "source_provenance_preserved"
    assert candidate["points"] == 2
    assert candidate["approval_status"] == "pending"
    assert not mindcoin.LEDGER_FILE.exists()


def test_mindcoin_commands_are_wired_to_web_and_cli_sources():
    web = (ROOT / "oracle_server.py").read_text(encoding="utf-8", errors="replace")
    cli = (CORE / "oracle.py").read_text(encoding="utf-8", errors="replace")

    for command in ("/mindcoin", "/mindcoin-pending", "/mindcoin-drive", "/mindcoin-extract"):
        assert command in web
        assert command in cli
    assert "mindcoin_drive" in web
    assert "mindcoin_drive" in cli
