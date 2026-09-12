from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import build_witness as bw  # noqa: E402
import companion_bootstrap as cb  # noqa: E402


def _point_build_witness_at(tmp_path: Path, monkeypatch) -> None:
    build_dir = tmp_path / "Memory" / "build_witness"
    monkeypatch.setattr(bw, "MEMORY_DIR", tmp_path / "Memory")
    monkeypatch.setattr(bw, "BUILD_DIR", build_dir)
    monkeypatch.setattr(bw, "RECEIPTS_DIR", build_dir / "receipts")
    monkeypatch.setattr(bw, "RECEIPT_LOG", build_dir / "build_receipts.jsonl")
    monkeypatch.setattr(bw, "LATEST_RECEIPT", build_dir / "latest_build_receipt.json")
    monkeypatch.setattr(bw, "CREATION_FEED", tmp_path / "Memory" / "creation_feed.jsonl")


def _fake_git_state() -> dict:
    return {
        "available": True,
        "branch": "checkpoint",
        "head": "abc123",
        "status_count": 2,
        "changed_files": [
            {"status": "M", "path": "core/build_witness.py", "previous_path": "", "raw": " M core/build_witness.py"},
            {"status": "M", "path": "oracle_server.py", "previous_path": "", "raw": " M oracle_server.py"},
        ],
        "status_lines": [" M core/build_witness.py", " M oracle_server.py"],
        "diff_stat": ["core/build_witness.py | 20 +++++"],
        "staged_diff_stat": [],
        "errors": [],
    }


def test_git_status_parser_preserves_first_path_character():
    assert bw._parse_status_line("M Messages/oracle_inner.json")["path"] == "Messages/oracle_inner.json"
    assert bw._parse_status_line(" M core/build_witness.py")["path"] == "core/build_witness.py"
    assert bw._parse_status_line("?? tests/test_build_witness.py")["path"] == "tests/test_build_witness.py"


def test_write_build_receipt_schema_hash_and_timeline(tmp_path, monkeypatch):
    _point_build_witness_at(tmp_path, monkeypatch)
    monkeypatch.setattr(bw, "collect_git_state", _fake_git_state)
    monkeypatch.setattr(
        bw,
        "tail_creation_feed",
        lambda limit=bw.MAX_CREATION_EVENTS: [{
            "ts": "2026-07-14T00:00:00Z",
            "event": "modified",
            "path": "core/build_witness.py",
            "witness": "creation_witness",
            "boundary": "metadata_only_no_content_no_upload",
        }],
    )

    receipt = bw.write_build_receipt(
        reason="Connect ORACLE construction events to Build Witness receipts",
        task_id="build-witness",
        tests_run=["pytest tests/test_build_witness.py"],
        test_result="passed",
    )

    assert receipt["schema_version"] == bw.SCHEMA_VERSION
    assert receipt["event_type"] == "build_change"
    assert receipt["requested_by"] == "Noah.Physical"
    assert receipt["executed_by"] == "Codex"
    assert receipt["files_changed"] == ["core/build_witness.py", "oracle_server.py"]
    assert receipt["boundaries"]["captures_file_content"] is False
    assert receipt["boundaries"]["commits_or_pushes"] is False

    unhashed = dict(receipt)
    actual_hash = unhashed.pop("receipt_hash_sha256")
    assert bw.hash_payload(unhashed) == actual_hash
    assert Path(receipt["receipt_path"]).exists()
    assert json.loads(bw.LATEST_RECEIPT.read_text(encoding="utf-8"))["receipt_id"] == receipt["receipt_id"]

    timeline = bw.timeline_payload(limit=10)
    assert timeline["ok"] is True
    assert timeline["latest_receipt"]["receipt_id"] == receipt["receipt_id"]
    assert any(event["kind"] == "build_receipt" for event in timeline["events"])
    assert any(event["kind"] == "file_witness" for event in timeline["events"])


def test_companion_bootstrap_has_build_witness_section(tmp_path, monkeypatch):
    build_dir = tmp_path / "Memory" / "build_witness"
    receipts = build_dir / "receipts"
    receipts.mkdir(parents=True)
    monkeypatch.setattr(cb, "BUILD_WITNESS_DIR", build_dir)

    receipt = {
        "receipt_id": "build_change_test",
        "observed_at": "2026-07-14T00:00:00Z",
        "task_id": "build-witness",
        "approval_status": "candidate",
        "test_result": "passed",
        "files_changed": ["core/build_witness.py"],
        "reason": "Make ORACLE witness her own construction as receipts.",
        "tests_run": ["pytest"],
        "receipt_hash_sha256": "a" * 64,
    }
    (build_dir / "build_receipts.jsonl").write_text(json.dumps(receipt) + "\n", encoding="utf-8")
    (build_dir / "latest_build_receipt.json").write_text(json.dumps(receipt) + "\n", encoding="utf-8")

    lines = cb._build_witness_source_lines(limit=2)
    text = "\n".join(lines)
    assert "candidate build receipts only" in text
    assert "build_change_test reason: Make ORACLE witness" in text

    missing = cb.SourceRecord(
        path="missing",
        resolved="missing",
        exists=False,
        sha256=None,
        size_bytes=None,
        mtime_utc=None,
        load_error="file_not_found",
        content=None,
    )
    result = cb.BootstrapResult(identity=missing, latest_reflection=missing, live_context=missing)
    block = result.system_context_block()
    assert "SOURCE SECTION: BUILD_WITNESS" in block
    assert "BUILD_WITNESS records are candidate construction receipts" in block
