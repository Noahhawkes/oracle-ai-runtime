from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

import human_state  # noqa: E402
import memory  # noqa: E402
import project_state  # noqa: E402


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(memory, "DB_PATH", tmp_path / "Memory" / "oracle_memory.db")
    monkeypatch.setattr(project_state, "STATES_FILE", tmp_path / "Memory" / "project_states.json")
    human_state.ensure_schema()


def test_explicit_transition_statements_are_classified():
    assert human_state.classify_transition("I'm going on a walk with Ashley")["new_mode"] == "FAMILY"
    assert human_state.classify_transition("I'm in bed now")["new_mode"] == "SLEEP"
    assert human_state.classify_transition("We're going to Costco to inspect the EcoWater dealership")["new_mode"] == "WORK_ECOWATER"
    assert human_state.classify_transition("Back at the workstation")["new_mode"] == "WORK_ORACLE"


def test_ambiguous_statement_remains_unknown_and_unrecorded(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    result = human_state.record_transition("that sounds good")

    assert result["ok"] is True
    assert result["recorded"] is False
    assert result["classification"]["new_mode"] == "UNKNOWN"
    assert human_state.current_state()["current_mode"] == "UNKNOWN"


def test_transition_is_receipted_deduped_and_durable(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    first = human_state.record_transition(
        "I'm going on a walk with Ashley",
        source_system="test",
        open_loops=["finish self-prompt journal"],
    )
    second = human_state.record_transition(
        "I'm going on a walk with Ashley",
        source_system="test",
        open_loops=["finish self-prompt journal"],
    )
    state = human_state.current_state()

    assert first["recorded"] is True
    assert first["event"]["new_mode"] == "FAMILY"
    assert first["receipt"]["external_systems_touched"] is False
    assert first["receipt"]["mood_inference"] is False
    assert second["duplicate"] is True
    assert state["current_mode"] == "FAMILY"
    assert state["last_transition"]["open_loops"] == ["finish self-prompt journal"]


def test_reentry_brief_uses_project_state_without_triggering_work(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    state = project_state.get_or_create("ORACLE")
    state.last_completed_step = "self-prompt journal tests passed"
    state.next_recommended_step = "implement human state API tests"
    state.open_questions = ["Should UI expose quick transition buttons?"]
    project_state.save_state(state)

    human_state.record_transition("Back at the workstation", source_system="test")
    brief = human_state.reentry_brief()

    assert brief["last_known_mode"] == "WORK_ORACLE"
    assert brief["project_noah_was_working_on"] == "ORACLE"
    assert brief["last_completed_action"] == "self-prompt journal tests passed"
    assert brief["recommended_next_action"] == "implement human state API tests"
    assert "Should UI expose quick transition buttons?" in brief["open_loops"]
    assert brief["boundary"] == "read-only brief; no build action triggered"
