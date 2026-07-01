from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

import pytest  # noqa: E402
import sandbox_files as sf  # noqa: E402


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(sf, "SANDBOX_ROOT", tmp_path / "sandbox")


def test_write_sandbox_file_creates_file_and_receipt(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    result = sf.write_sandbox_file(
        "tests",
        "oracle_first_write.ai",
        "ORACLE TRAINING WHEELS ONLINE",
        caller="test",
        action_id="sandbox_test_action",
    )

    final_path = Path(result["final_path"])
    receipt_path = Path(result["receipt_path"])
    assert final_path.exists()
    assert receipt_path.exists()
    assert final_path.read_text(encoding="utf-8") == "ORACLE TRAINING WHEELS ONLINE"
    assert final_path.parent == (tmp_path / "sandbox" / "tests").resolve()

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["requested_filename"] == "oracle_first_write.ai"
    assert receipt["final_path"] == str(final_path)
    assert receipt["caller"] == "test"
    assert receipt["action_id"] == "sandbox_test_action"
    assert receipt["sha256"] == result["sha256"]
    assert receipt["executed_written_file"] is False
    assert receipt["overwrote_existing_file"] is False
    assert receipt["git_push"] is False


def test_write_sandbox_file_never_overwrites(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    first = sf.write_sandbox_file("notes", "note.md", "one", action_id="one")
    second = sf.write_sandbox_file("notes", "note.md", "two", action_id="two")

    assert Path(first["final_path"]).name == "note.md"
    assert Path(second["final_path"]).name == "note_v2.md"
    assert Path(first["final_path"]).read_text(encoding="utf-8") == "one"
    assert Path(second["final_path"]).read_text(encoding="utf-8") == "two"


@pytest.mark.parametrize(
    ("folder", "filename"),
    [
        ("../notes", "x.md"),
        ("notes", "../x.md"),
        ("notes", "run.py"),
        ("notes", "run.ps1"),
        ("notes", "run.exe"),
        ("receipts", "manual.json"),
    ],
)
def test_write_sandbox_file_rejects_unsafe_targets(monkeypatch, tmp_path, folder, filename):
    _isolate(monkeypatch, tmp_path)

    with pytest.raises(sf.SandboxWriteError):
        sf.write_sandbox_file(folder, filename, "blocked")


def test_read_and_list_sandbox_files(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    written = sf.write_sandbox_file("handoffs", "handoff.ai", "handoff text", action_id="handoff")

    read = sf.read_sandbox_file(written["final_path"])
    listed = sf.list_sandbox_files("handoffs")

    assert read["content"] == "handoff text"
    assert read["sha256"] == written["sha256"]
    assert [item["name"] for item in listed["files"]] == ["handoff.ai"]


def test_read_sandbox_file_rejects_outside_path(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("nope", encoding="utf-8")

    with pytest.raises(sf.SandboxWriteError):
        sf.read_sandbox_file(outside)
