from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import ai_lockbox as lb  # noqa: E402
import file_recall as fr  # noqa: E402


def _wire_tmp_lockbox(monkeypatch, tmp_path):
    lockbox = tmp_path / "Memory" / "ai_lockbox"
    monkeypatch.setattr(lb, "LOCKBOX_DIR", lockbox)
    monkeypatch.setattr(lb, "CAPSULE_DIR", lockbox / "capsules")
    monkeypatch.setattr(lb, "MANIFEST_FILE", lockbox / "manifest.jsonl")
    monkeypatch.setattr(lb, "RECEIPT_FILE", lockbox / "receipts.jsonl")
    monkeypatch.setattr(lb, "LATEST_STATUS_FILE", lockbox / "latest_status.json")
    monkeypatch.setattr(lb, "DEFAULT_ROOTS", [tmp_path])
    monkeypatch.setattr(fr, "DEFAULT_ROOTS", [tmp_path])
    monkeypatch.setattr(fr, "MEMORY_DIR", tmp_path / "Memory")
    monkeypatch.setattr(fr, "RECEIPT_FILE", tmp_path / "Memory" / "file_recall_receipts.jsonl")


def test_build_lockbox_creates_ai_capsule_without_touching_source(tmp_path, monkeypatch):
    _wire_tmp_lockbox(monkeypatch, tmp_path)
    source = tmp_path / "oracle_note.md"
    original = "ORACLE preserves continuity without lying. Rendered Reality gives continuity form."
    source.write_text(original, encoding="utf-8")
    (tmp_path / "wallet_secret.txt").write_text("DO_NOT_LEAK_WALLET_VALUE", encoding="utf-8")

    result = lb.build_lockbox("", limit=5)
    manifest = (tmp_path / "Memory" / "ai_lockbox" / "manifest.jsonl").read_text(encoding="utf-8")
    receipts = (tmp_path / "Memory" / "ai_lockbox" / "receipts.jsonl").read_text(encoding="utf-8")
    capsule_paths = [Path(row["capsule_path"]) for row in result["created"]]
    capsule_text = "\n".join(path.read_text(encoding="utf-8") for path in capsule_paths)

    assert result["ok"] is True
    assert result["operation_type"] == "ai_lockbox_ingest"
    assert result["created_count"] == 1
    assert result["sensitive_metadata_matches"] == 1
    assert source.read_text(encoding="utf-8") == original
    assert ".AI:LOCKBOX_SOURCE/" in capsule_text
    assert "@SOURCE" in capsule_text
    assert "@RECALL" in capsule_text
    assert "Rendered Reality" in capsule_text
    assert "wallet_secret.txt" not in manifest
    assert "DO_NOT_LEAK_WALLET_VALUE" not in capsule_text
    assert "DO_NOT_LEAK_WALLET_VALUE" not in receipts


def test_search_and_context_block_use_existing_ai_capsules(tmp_path, monkeypatch):
    _wire_tmp_lockbox(monkeypatch, tmp_path)
    (tmp_path / "jupiter_station.ai").write_text(
        "Jupiter Station continuity log. Rendered Reality memory graph.",
        encoding="utf-8",
    )
    lb.build_lockbox("", limit=5)

    search = lb.search_lockbox("Rendered Reality", limit=3)
    context = lb.context_block("what does rendered reality say about jupiter station")

    assert search["operation_type"] == "ai_lockbox_search"
    assert search["result_count"] == 1
    assert search["results"][0]["name"] == "jupiter_station.ai"
    assert "AI_LOCKBOX" in context
    assert "jupiter_station.ai" in context


def test_capsule_for_file_resolves_relative_runtime_paths(tmp_path, monkeypatch):
    _wire_tmp_lockbox(monkeypatch, tmp_path)
    monkeypatch.setattr(lb, "RUNTIME_ROOT", tmp_path)
    source = tmp_path / "docs" / "oracle.ai"
    source.parent.mkdir()
    source.write_text("ORACLE shorthand capsule source.", encoding="utf-8")

    row = lb.capsule_for_file("docs/oracle.ai")

    assert row["source_path"] == str(source.resolve())
    assert Path(row["capsule_path"]).exists()


def test_parse_and_format_lockbox_commands():
    assert lb.parse_lockbox_request("/ai-lockbox-status") == {"mode": "status", "value": ""}
    assert lb.parse_lockbox_request("/ai-lockbox-ingest thesis") == {"mode": "ingest", "value": "thesis"}
    assert lb.parse_lockbox_request("/ai-lockbox-search Ashley") == {"mode": "search", "value": "Ashley"}
    assert lb.parse_lockbox_request("/ai-shorthand docs/oracle.ai") == {
        "mode": "capsule",
        "value": "docs/oracle.ai",
    }
    rendered = lb.format_result({
        "operation_type": "ai_lockbox_status",
        "capsule_count": 7,
        "receipt_count": 2,
        "manifest_path": "manifest.jsonl",
        "capsule_dir": "capsules",
        "latest_receipt": {"created_count": 3},
    })
    assert "AI LOCKBOX STATUS" in rendered
    assert "capsule_count: 7" in rendered


def test_status_payload_counts_manifest_and_receipts(tmp_path, monkeypatch):
    _wire_tmp_lockbox(monkeypatch, tmp_path)
    (tmp_path / "source.md").write_text("Source material for ORACLE.", encoding="utf-8")

    lb.build_lockbox("", limit=5)
    status = lb.status_payload()

    assert status["operation_type"] == "ai_lockbox_status"
    assert status["capsule_count"] == 1
    assert status["receipt_count"] == 1
    assert json.loads((tmp_path / "Memory" / "ai_lockbox" / "latest_status.json").read_text(encoding="utf-8"))["ok"] is True
