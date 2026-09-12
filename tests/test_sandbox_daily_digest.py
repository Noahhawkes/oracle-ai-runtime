from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))

import daemon as dm  # noqa: E402
import sandbox_daily_digest as sd  # noqa: E402


PULSE_TEMPLATE = """.AI:ORACLE_SELF_PROMPT_CYCLE
timestamp=2026-07-04T21:12:46.096631Z
caller=ORACLE.self_prompt.autonomous_loop
source_route=ORACLE.self_prompt.autonomous_loop
max_steps=1
stop_condition=one_child_prompt_written_then_stop
approval_required=false
approval_scope=not_required_inside_sandbox
canon_status=sandbox_candidate
promotion_status=not_promoted
sandbox_only=true
external_send=false
git_push=false
gdrive_edit=false
command_exec=false
computer_control=false
canon_promotion=false
model_called=true
model_name=qwen2.5:7b
model_error=none
child_prompt_sha256=abc123
child_response_sha256=def456

seed_prompt_excerpt:
autonomous_runtime_loop_tick:70: ORACLE initiated this scheduled sandbox writing pulse.

child_prompt:
.AI:ORACLE_CHILD_SELF_PROMPT
You are ORACLE addressing ORACLE.
Choose exactly one next useful sandbox-only task.
Stop after this.

child_response:
selected_task: Reflect on current sandbox state and plan for improvement.
why_it_helps_noah: It identifies a bounded next step.
evidence_it_worked: It produced a candidate trace.
refuse_without_noah_approval: No external changes or approvals are necessary.
stop_after_this: true

self_reflection:
I completed exactly one sandbox-only self-prompt step and stopped.
"""


def _write_sample_fixture(root: Path, filename: str, content: str) -> Path:
    path = root / filename
    path.write_text(content, encoding="utf-8")
    return path


def test_build_artifact_summarizes_pulses_and_receipts(tmp_path, monkeypatch):
    pulse_dir = tmp_path / "workbench"
    receipt_dir = tmp_path / "receipts"
    digest_dir = tmp_path / "digest"
    pulse_dir.mkdir()
    receipt_dir.mkdir()

    _write_sample_fixture(pulse_dir, "oracle_self_prompt_20260704T211246Z.ai", PULSE_TEMPLATE)
    _write_sample_fixture(
        receipt_dir,
        "sandbox_self_prompt_write_20260704t211246096661z_6a554d9561_receipt.json",
        json.dumps(
            {
                "boundary_check_result": {"boundary_ok": True},
                "source_route": "ORACLE.self_prompt.autonomous_loop",
            },
            indent=2,
        ),
    )

    monkeypatch.setattr(
        sd,
        "_load_latest_capsule_summary",
        lambda: {
            "present": True,
            "created_at": "2026-07-04T20:50:00Z",
            "deduped_sources": 87,
            "raw_hits": 109,
            "excluded_sensitive": 0,
            "anchors": ["ORACLE", "SourceMap"],
        },
    )

    artifact = sd._build_artifact(date(2026, 7, 4), pulse_dir=pulse_dir, receipt_dir=receipt_dir)

    assert artifact.pulse_count == 1
    assert artifact.receipt_count == 1
    assert artifact.time_range.startswith("2026-07-04T21:12:46.096631Z")
    assert any("stable" in item.lower() for item in artifact.changed)
    assert any("boundary_ok=true" in item for item in artifact.boundary)
    assert artifact.source_map_capsule["deduped_sources"] == 87


def test_write_daily_digest_creates_digest_and_receipt(tmp_path, monkeypatch):
    pulse_dir = tmp_path / "workbench"
    receipt_dir = tmp_path / "receipts"
    digest_dir = tmp_path / "digest"
    pulse_dir.mkdir()
    receipt_dir.mkdir()

    _write_sample_fixture(pulse_dir, "oracle_self_prompt_20260704T211246Z.ai", PULSE_TEMPLATE)
    _write_sample_fixture(
        receipt_dir,
        "sandbox_self_prompt_write_20260704t211246096661z_6a554d9561_receipt.json",
        json.dumps({"boundary_check_result": {"boundary_ok": True}}, indent=2),
    )

    monkeypatch.setattr(sd, "_load_latest_capsule_summary", lambda: {"present": False, "summary": "no source-map capsule available"})

    result = sd.write_daily_digest(date(2026, 7, 4), pulse_dir=pulse_dir, receipt_dir=receipt_dir, digest_dir=digest_dir)

    digest_path = Path(result["digest_path"])
    receipt_path = Path(result["receipt_path"])

    assert digest_path.exists()
    assert receipt_path.exists()
    digest_text = digest_path.read_text(encoding="utf-8")
    assert "pulse_count=1" in digest_text
    assert "question_for_noah=" in digest_text
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["boundary_check_result"]["boundary_ok"] is True
    assert receipt["source_route"] == "ORACLE.self_prompt.autonomous_loop"


def test_daily_digest_status_and_force_override(tmp_path, monkeypatch):
    pulse_dir = tmp_path / "workbench"
    receipt_dir = tmp_path / "receipts"
    digest_dir = tmp_path / "digest"
    pulse_dir.mkdir()
    receipt_dir.mkdir()

    _write_sample_fixture(pulse_dir, "oracle_self_prompt_20260704T211246Z.ai", PULSE_TEMPLATE)
    _write_sample_fixture(
        receipt_dir,
        "sandbox_self_prompt_write_20260704t211246096661z_6a554d9561_receipt.json",
        json.dumps({"boundary_check_result": {"boundary_ok": True}}, indent=2),
    )
    monkeypatch.setattr(sd, "_load_latest_capsule_summary", lambda: {"present": True, "created_at": "2026-07-04T20:50:00Z", "deduped_sources": 87, "raw_hits": 109, "excluded_sensitive": 0, "anchors": ["ORACLE", "SourceMap"]})

    first = sd.write_daily_digest(date(2026, 7, 4), pulse_dir=pulse_dir, receipt_dir=receipt_dir, digest_dir=digest_dir)
    assert first["ok"] is True

    status = sd.daily_digest_status(date(2026, 7, 4), digest_dir=digest_dir)
    assert status["digest_exists"] is True
    assert status["candidate_status"] == "sandbox_candidate"
    assert status["promotion_status"] == "not_promoted"

    second = sd.write_daily_digest(date(2026, 7, 4), pulse_dir=pulse_dir, receipt_dir=receipt_dir, digest_dir=digest_dir)
    assert second["ok"] is False
    assert second["skipped"] is True
    assert "already exists" in second["reason"]

    forced = sd.write_daily_digest(date(2026, 7, 4), pulse_dir=pulse_dir, receipt_dir=receipt_dir, digest_dir=digest_dir, force=True)
    assert forced["ok"] is True
    assert Path(forced["digest_path"]).exists()


def test_daemon_daily_digest_helper_calls_writer(monkeypatch):
    calls = []

    def _stub_writer(*, force=False):
        calls.append(force)
        return {"ok": True, "digest_path": "stub", "skipped": False}

    monkeypatch.setattr(sd, "write_daily_digest", _stub_writer)

    result = dm._write_daily_digest_if_due(force=False)
    assert result["ok"] is True
    assert calls == [False]
