from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import file_recall as fr  # noqa: E402
import readonly_access as ra  # noqa: E402


def test_validate_blocks_paths_outside_roots_and_secret_paths(monkeypatch):
    monkeypatch.setattr(fr, "DEFAULT_ROOTS", [ROOT])
    for bad in (
        r"C:\Users\noahh\.ssh\id_rsa",
        r"C:\Windows\System32\config\SAM",
        str(ROOT / ".." / ".." / "outside.txt"),
    ):
        with pytest.raises(fr.FileRecallError):
            fr.validate_readable_path(bad)


def test_blocked_name_patterns_catch_credential_files(tmp_path, monkeypatch):
    monkeypatch.setattr(fr, "DEFAULT_ROOTS", [tmp_path])
    secret = tmp_path / "api_key_backup.txt"
    secret.write_text("hunter2", encoding="utf-8")
    with pytest.raises(fr.FileRecallError):
        fr.validate_readable_path(str(secret))


def test_sensitive_inventory_lists_metadata_without_secret_content(tmp_path, monkeypatch):
    monkeypatch.setattr(fr, "DEFAULT_ROOTS", [tmp_path])
    monkeypatch.setattr(fr, "MEMORY_DIR", tmp_path / "Memory")
    monkeypatch.setattr(fr, "RECEIPT_FILE", tmp_path / "Memory" / "receipts.jsonl")
    secret_dir = tmp_path / ".ssh"
    secret_dir.mkdir()
    secret = secret_dir / "id_ed25519"
    secret.write_text("SUPER_SECRET_PRIVATE_KEY_VALUE", encoding="utf-8")

    result = fr.sensitive_inventory("id_ed25519", limit=5)
    rendered = fr.format_recall(result)
    receipt_text = (tmp_path / "Memory" / "receipts.jsonl").read_text(encoding="utf-8")

    assert result["ok"] is True
    assert result["operation_type"] == "file_recall_sensitive_inventory"
    assert result["result_count"] == 1
    assert result["results"][0]["content_available"] is False
    assert result["boundary"]["metadata_only"] is True
    assert "SUPER_SECRET_PRIVATE_KEY_VALUE" not in json.dumps(result)
    assert "SUPER_SECRET_PRIVATE_KEY_VALUE" not in rendered
    assert "SUPER_SECRET_PRIVATE_KEY_VALUE" not in receipt_text
    assert "metadata only" in rendered


def test_search_finds_files_and_writes_read_only_receipt(tmp_path, monkeypatch):
    monkeypatch.setattr(fr, "DEFAULT_ROOTS", [tmp_path])
    monkeypatch.setattr(fr, "MEMORY_DIR", tmp_path / "Memory")
    monkeypatch.setattr(fr, "RECEIPT_FILE", tmp_path / "Memory" / "receipts.jsonl")
    (tmp_path / "jupiter_notes.md").write_text("station log", encoding="utf-8")
    (tmp_path / ".ssh").mkdir()
    (tmp_path / ".ssh" / "jupiter_key.md").write_text("nope", encoding="utf-8")

    result = fr.search("jupiter", limit=5)

    assert result["ok"] is True
    assert result["result_count"] == 1
    assert result["results"][0]["name"] == "jupiter_notes.md"
    receipt = json.loads((tmp_path / "Memory" / "receipts.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert receipt["boundary"]["read_only"] is True
    assert receipt["boundary"]["write"] is False
    assert receipt["boundary"]["external_send"] is False


def test_search_deep_content_match(tmp_path, monkeypatch):
    monkeypatch.setattr(fr, "DEFAULT_ROOTS", [tmp_path])
    monkeypatch.setattr(fr, "MEMORY_DIR", tmp_path / "Memory")
    monkeypatch.setattr(fr, "RECEIPT_FILE", tmp_path / "Memory" / "receipts.jsonl")
    (tmp_path / "log.md").write_text("the texlatian divergence re-seated the timeline", encoding="utf-8")

    deep = fr.search("texlatian divergence", limit=5, deep=True)
    shallow = fr.search("texlatian divergence", limit=5, deep=False)

    assert deep["result_count"] == 1
    assert deep["results"][0]["kind"] == "content_match"
    assert "texlatian" in deep["results"][0]["snippet"].lower()
    assert shallow["result_count"] == 0  # filename-only pass skips content


def test_read_file_returns_preview_and_receipt(tmp_path, monkeypatch):
    monkeypatch.setattr(fr, "DEFAULT_ROOTS", [tmp_path])
    monkeypatch.setattr(fr, "MEMORY_DIR", tmp_path / "Memory")
    monkeypatch.setattr(fr, "RECEIPT_FILE", tmp_path / "Memory" / "receipts.jsonl")
    target = tmp_path / "story.md"
    target.write_text("Jupiter Station held the line.", encoding="utf-8")

    result = fr.read_file(str(target))

    assert result["ok"] is True
    assert "held the line" in result["text_preview"]
    assert result["boundary"]["read_only"] is True
    assert Path(result["receipt_path"]).exists()


def test_parse_file_request_commands_and_natural_language():
    assert fr.parse_file_request("/file-search rendered reality") == {
        "mode": "search", "value": "rendered reality",
    }
    assert fr.parse_file_request("search my files for jupiter station") == {
        "mode": "search", "value": "jupiter station",
    }
    assert fr.parse_file_request("/sensitive-inventory id_ed25519") == {
        "mode": "sensitive_inventory", "value": "id_ed25519",
    }
    assert fr.parse_file_request("read file docs/README.md") == {
        "mode": "read", "value": "docs/README.md",
    }
    assert fr.parse_file_request("just talking about nothing") is None


def test_context_block_triggers_only_on_file_talk(tmp_path, monkeypatch):
    monkeypatch.setattr(fr, "DEFAULT_ROOTS", [tmp_path])
    monkeypatch.setattr(fr, "MEMORY_DIR", tmp_path / "Memory")
    monkeypatch.setattr(fr, "RECEIPT_FILE", tmp_path / "Memory" / "receipts.jsonl")
    (tmp_path / "voyager_draft.md").write_text("draft", encoding="utf-8")

    assert fr.context_block("how are you feeling today") == ""
    block = fr.context_block("what do my documents say about the voyager draft")
    assert "voyager_draft.md" in block
    assert "read-only" in block


def test_self_check_includes_readonly_grant(tmp_path, monkeypatch):
    monkeypatch.setattr(fr, "DEFAULT_ROOTS", [tmp_path])
    monkeypatch.setattr(fr, "MEMORY_DIR", tmp_path / "Memory")
    monkeypatch.setattr(fr, "RECEIPT_FILE", tmp_path / "Memory" / "receipts.jsonl")
    monkeypatch.setattr(ra, "MEMORY_DIR", tmp_path / "Memory")
    monkeypatch.setattr(ra, "RECEIPT_FILE", tmp_path / "Memory" / "readonly.jsonl")
    monkeypatch.setattr(ra, "LATEST_RECEIPT_FILE", tmp_path / "Memory" / "latest.json")
    monkeypatch.setattr(ra, "discovered_read_roots", lambda: [tmp_path])

    check = fr.self_check()

    assert check["ok"] is True
    assert check["read_access_grant"]["access_status"] == "granted"
    assert check["read_access_grant"]["approval_required_for_read"] is False
    assert check["sensitive_inventory"] == "available; metadata only; no raw secret read or receipt storage"
