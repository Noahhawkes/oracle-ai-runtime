from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for path in (str(ROOT), str(CORE)):
    if path not in sys.path:
        sys.path.insert(0, path)

import desktop_ai_bridge as bridge
import existence_integration as integration
from existence_machine import ExistenceMachine


def _configure_temp_stores(monkeypatch, tmp_path):
    monkeypatch.setattr(
        bridge,
        "STAGED_PROMPT_FILE",
        tmp_path / "desktop_ai_staged_prompt.json",
    )
    monkeypatch.setattr(
        integration,
        "EXISTENCE_DATABASE_PATH",
        tmp_path / "existence.db",
    )


def test_sov1_stage_and_handoff_are_hash_linked(monkeypatch, tmp_path):
    _configure_temp_stores(monkeypatch, tmp_path)

    staged = bridge.stage_prompt(
        "sov1",
        "inspect the current desktop status",
        source="test",
    )

    assert staged.existence_stage_event_id
    assert staged.existence_stage_event_hash

    result = bridge.send_staged(confirmed=True)
    reloaded = bridge.load_staged()

    assert result["success"] is True
    assert result["execution_completed"] is False
    assert result["existence_event_id"]
    assert reloaded is not None
    assert reloaded.existence_handoff_event_id == result["existence_event_id"]

    machine = ExistenceMachine(integration.EXISTENCE_DATABASE_PATH)
    try:
        integrity = machine.verify_integrity()
        history = machine.history(limit=10)
    finally:
        machine.close()

    assert integrity == {
        "valid": True,
        "events_checked": 2,
        "failures": [],
    }
    assert [event["event_type"] for event in history] == [
        "SOV1_HANDOFF_RELEASED",
        "SOV1_TASK_STAGED",
    ]
    assert history[0]["payload"]["authority_authentication"] == "not_implemented"
    assert history[0]["payload"]["execution_completed"] is False
    assert history[1]["payload"]["task_sha256"]
    assert "inspect the current desktop status" not in str(history)


def test_unconfirmed_sov1_handoff_does_not_append_release(monkeypatch, tmp_path):
    _configure_temp_stores(monkeypatch, tmp_path)
    bridge.stage_prompt("sov1", "inspect status", source="test")

    try:
        bridge.send_staged(confirmed=False)
    except bridge.SendError:
        pass
    else:
        raise AssertionError("unconfirmed handoff must be blocked")

    machine = ExistenceMachine(integration.EXISTENCE_DATABASE_PATH)
    try:
        history = machine.history(limit=10)
    finally:
        machine.close()

    assert [event["event_type"] for event in history] == ["SOV1_TASK_STAGED"]


def test_operational_boundary_keeps_roles_distinct():
    boundary = integration.operational_boundary()

    assert boundary["final_authority"] == "Noah.Physical"
    assert boundary["governance_layer"] == "SOV1.AI"
    assert boundary["continuity_runtime"] == "ORACLE.AI"
    assert boundary["execution_layer"] == "SOV1.HANDS"
    assert boundary["sentience_claim"] is False
    assert boundary["authority_authentication"] == "not_implemented"
