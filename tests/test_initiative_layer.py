from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

import initiative_layer as il  # noqa: E402


def test_thread_overload_gets_bounded_prompt_back():
    suggestion = il.maybe_prompt_back(
        "My threads all blend together and are too much to carry.",
        "Captured as candidate evidence.",
        preferences_applied=["pref_no_self_intro"],
    )

    assert suggestion is not None
    assert suggestion["reason"] == "thread_burden_decision_point"
    assert suggestion["action_taken"] == "none"
    assert suggestion["writes_performed"] is False
    assert suggestion["external_action_performed"] is False
    assert suggestion["approval_required_for_state_change"] is True
    assert "classify_candidate" in suggestion["options"]

    text = il.append_prompt_back("Captured as candidate evidence.", suggestion)
    assert "Prompt-back candidate:" in text
    assert "classify" in text
    assert "action_taken: none" in text


def test_source_failure_prompts_for_current_session_or_search():
    suggestion = il.maybe_prompt_back(
        "Who is Ellie beyond the loaded sources?",
        "UNAVAILABLE [CURRENT_SESSION]: supporting text missing.",
    )

    assert suggestion is not None
    assert suggestion["reason"] == "source_validation_boundary"
    assert "use_current_session_raw_capture" in suggestion["options"]
    assert "search_indexed_custody" in suggestion["options"]


def test_explicit_bounded_initiative_request_gets_staging_question():
    suggestion = il.maybe_prompt_back(
        "Initiative Layer: Prompt-Back Rules.",
        "I can keep this as candidate evidence.",
    )

    assert suggestion is not None
    assert suggestion["reason"] == "explicit_bounded_initiative_request"
    assert "stage_prompt_back_rules" in suggestion["options"]


def test_report_only_suppresses_prompt_back():
    suggestion = il.maybe_prompt_back(
        "REPORT ONLY: thread dump landed.",
        "Captured as candidate evidence.",
        route_type="thread_ingest_file",
    )

    assert suggestion is None

