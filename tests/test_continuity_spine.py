from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

import continuity_spine as cs  # noqa: E402
import human_state  # noqa: E402
import memory  # noqa: E402
import project_state  # noqa: E402


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(memory, "DB_PATH", tmp_path / "Memory" / "oracle_memory.db")
    monkeypatch.setattr(project_state, "STATES_FILE", tmp_path / "Memory" / "project_states.json")
    monkeypatch.setattr(cs, "ROOT", tmp_path)
    human_state.ensure_schema()
    receipt_dir = tmp_path / "sandbox" / "receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    (receipt_dir / "test_receipt.json").write_text(
        json.dumps({
            "receipt_id": "receipt-test",
            "operation_type": "test_operation",
            "status": "ok",
        }),
        encoding="utf-8",
    )


def _seed_project():
    state = project_state.get_or_create("ORACLE")
    state.current_goal = "Build the continuity spine"
    state.current_phase = "operational consolidation"
    state.last_completed_step = "Human State engine installed"
    state.last_completed_evidence = "52 tests passed"
    state.next_recommended_step = "Wire operator dashboard"
    state.next_step_reason = "single return-to-work surface"
    state.current_blocker = "Need one spine owner"
    state.blocker_evidence = "architecture directive"
    state.open_questions = ["Should daily digest write a file?"]
    state.pending_candidates = ["continuity dashboard candidate"]
    state.unknowns = ["contradiction ledger not connected"]
    state.confidence = 0.8
    project_state.save_state(state)


def test_continuity_spine_composes_existing_ledgers(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    _seed_project()
    human_state.record_transition("Back at the workstation", source_system="test")

    snapshot = cs.continuity_snapshot(limit=20)
    statuses = {loop["status"] for loop in snapshot["current_open_loops"]}

    assert snapshot["ok"] is True
    assert snapshot["continuity_owner"] == "core.continuity_spine"
    assert snapshot["current_human_state"]["current_mode"] == "WORK_ORACLE"
    assert snapshot["current_project"]["project_name"] == "ORACLE"
    assert {"completed", "active", "blocked", "waiting"}.issubset(statuses)
    assert snapshot["recent_receipts"][0]["preview"]["operation"] == "test_operation"
    assert snapshot["boundary"] == "read-only continuity composition; no external systems touched"


def test_continuity_health_metrics_are_measured_counts(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    _seed_project()
    human_state.record_transition("Back at the workstation", source_system="test")

    metrics = cs.continuity_health_metrics()

    assert metrics["metric_boundary"] == "measured system counts only; no AI scoring"
    assert metrics["project_count"] == 1
    assert metrics["open_loop_pressure"]["by_status"]["blocked"] == 1
    assert metrics["open_loop_pressure"]["by_status"]["waiting"] >= 1
    assert metrics["receipt_density_24h"]["count"] >= 1
    assert metrics["unknown_count"] >= 1


def test_operator_dashboard_is_actionable_and_read_only(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    _seed_project()
    human_state.record_transition("Back at the workstation", source_system="test")

    dashboard = cs.operator_dashboard()

    assert dashboard["current_human_state"] == "WORK_ORACLE"
    assert dashboard["current_project"] == "ORACLE"
    assert len(dashboard["top_open_loops"]) <= 5
    assert "Need one spine owner" in dashboard["suggested_resume_action"]
    assert dashboard["boundary"] == "operator dashboard is read-only and actionable; nothing decorative"


def test_daily_digest_is_derived_not_invented(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    _seed_project()
    human_state.record_transition("Back at the workstation", source_system="test")

    digest = cs.daily_continuity_digest()

    assert digest["ok"] is True
    assert digest["what_completed"]
    assert digest["what_stalled"]
    assert digest["boundary"] == "derived from ledgers only; no invented work"
