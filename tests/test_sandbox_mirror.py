from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))


def test_sandbox_mirror_is_read_only_and_attributes_oracle_receipt(monkeypatch, tmp_path):
    import sandbox_files as sf
    import sandbox_mirror

    sandbox_root = tmp_path / "sandbox"
    workbench = sandbox_root / "workbench"
    receipts = sandbox_root / "receipts"
    workbench.mkdir(parents=True)
    receipts.mkdir(parents=True)
    monkeypatch.setattr(sf, "SANDBOX_ROOT", sandbox_root)

    note = workbench / "oracle_self_prompt_journal.ai"
    note.write_text("child_response:\nreflection: one grounded thought\n", encoding="utf-8")
    receipt = {
        "action_id": "sandbox_self_prompt_write_test",
        "operation_type": "sandbox_self_prompt_write",
        "target_path": str(note),
        "requested_path": "workbench\\oracle_self_prompt_journal.ai",
        "source_route": "ORACLE.self_prompt.autonomous_loop",
        "timestamp": "2026-07-24T00:00:00Z",
        "novelty_status": "new_response_appended",
        "content_written": True,
        "sha256": "placeholder",
    }
    (receipts / "sandbox_self_prompt_write_test_receipt.json").write_text(
        json.dumps(receipt),
        encoding="utf-8",
    )

    before = sorted(p.relative_to(sandbox_root) for p in sandbox_root.rglob("*"))
    payload = sandbox_mirror.build_sandbox_mirror(limit=10, journal_chars=1000)
    after = sorted(p.relative_to(sandbox_root) for p in sandbox_root.rglob("*"))

    assert before == after
    assert payload["ok"] is True
    assert payload["mutated_sandbox"] is False
    assert payload["total_files"] == 2
    journal_record = next(
        item for item in payload["files"]
        if item["relative_path"] == "workbench\\oracle_self_prompt_journal.ai"
    )
    assert journal_record["author_class"] == "oracle_write"
    assert journal_record["receipt_id"] == "sandbox_self_prompt_write_test"
    assert journal_record["write_suppressed"] is False
    assert "one grounded thought" in payload["journal"]["tail"]


def test_sandbox_mirror_marks_unreceipted_files_unknown(monkeypatch, tmp_path):
    import sandbox_files as sf
    import sandbox_mirror

    sandbox_root = tmp_path / "sandbox"
    notes = sandbox_root / "notes"
    notes.mkdir(parents=True)
    monkeypatch.setattr(sf, "SANDBOX_ROOT", sandbox_root)
    (notes / "unattributed.ai").write_text("unknown source", encoding="utf-8")

    payload = sandbox_mirror.build_sandbox_mirror(limit=5)

    record = payload["files"][0]
    assert record["relative_path"] == "notes\\unattributed.ai"
    assert record["author_class"] == "unknown_author"
    assert record["receipt_id"] is None


def test_sandbox_mirror_api_route_is_read_only(monkeypatch, tmp_path):
    import os
    import sandbox_files as sf

    os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")
    sandbox_root = tmp_path / "sandbox"
    workbench = sandbox_root / "workbench"
    workbench.mkdir(parents=True)
    monkeypatch.setattr(sf, "SANDBOX_ROOT", sandbox_root)
    (workbench / "note.ai").write_text("api mirror note", encoding="utf-8")

    from fastapi.testclient import TestClient
    import oracle_server as srv

    client = TestClient(srv.app)
    before = sorted(p.relative_to(sandbox_root) for p in sandbox_root.rglob("*"))
    response = client.get("/api/sandbox/mirror", params={"limit": 5, "journal_chars": 200})
    after = sorted(p.relative_to(sandbox_root) for p in sandbox_root.rglob("*"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["read_only"] is True
    assert payload["mutated_sandbox"] is False
    assert before == after
