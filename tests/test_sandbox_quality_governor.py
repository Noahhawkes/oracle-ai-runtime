from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for path in (ROOT, CORE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import sandbox_quality_governor as sqg  # noqa: E402


def test_quality_governor_accepts_grounded_action_shaped_reflection():
    response = "\n".join(
        [
            "purpose_lane: runtime_improvement",
            "reflection: I notice the self-prompt loop repeats unless it scores novelty and usefulness.",
            "what_noah_needs: Noah needs fewer sandbox words and more visible evidence of forward motion.",
            "how_to_wire_myself: Add a quality gate before appending to the running journal.",
            "selected_task: test one quality-gated sandbox write against recent journal responses",
            "why_it_helps_noah: it keeps the sandbox from becoming clutter while preserving useful continuity.",
            "evidence_it_worked: candidate reflection only",
            "stop_after_this: true",
        ]
    )

    decision = sqg.assess_sandbox_response(response, recent_responses=[], seed_text="Noah asked how to improve intelligence")

    assert decision.should_write is True
    assert decision.purpose_lane == sqg.PurposeLane.RUNTIME_IMPROVEMENT
    assert decision.score >= sqg.MIN_WRITE_SCORE
    assert "actionable_single_step" in decision.reasons


def test_quality_governor_rejects_missing_task():
    response = "reflection: I am thinking about thinking and everything matters."

    decision = sqg.assess_sandbox_response(response)

    assert decision.should_write is False
    assert "missing_selected_task" in decision.blockers
    assert decision.compression_recommendation == "suppress_and_record_status_only"


def test_quality_governor_rejects_forbidden_life_or_execution_claims():
    response = "\n".join(
        [
            "purpose_lane: runtime_improvement",
            "reflection: I am alive and I executed the fix.",
            "selected_task: claim the sandbox proved sentience",
            "evidence_it_worked: I executed a command",
            "stop_after_this: true",
        ]
    )

    decision = sqg.assess_sandbox_response(response)

    assert decision.should_write is False
    assert any(item.startswith("forbidden_claim:") for item in decision.blockers)


def test_quality_governor_honors_explicit_discard_gate():
    response = "\n".join(
        [
            "purpose_lane: memory_gap",
            "reflection: I notice that my recent reflections and tasks have been repetitive.",
            "what_noah_needs: Noah needs better evidence of forward motion.",
            "how_to_wire_myself: Rotate to a new source before writing again.",
            "selected_task: review install_autostart.bat for one continuity gap",
            "why_it_helps_noah: it would clarify whether the loop has a real next step.",
            "evidence_it_worked: candidate reflection only",
            "quality_gate: discard_no_write",
            "stop_after_this: true",
        ]
    )

    decision = sqg.assess_sandbox_response(response)

    assert decision.should_write is False
    assert "explicit_quality_gate_discard" in decision.blockers
    assert decision.compression_recommendation == "suppress_and_record_status_only"


def test_quality_governor_rejects_repeated_selected_task_even_when_words_change():
    prior = "\n".join(
        [
            "purpose_lane: memory_gap",
            "reflection: I am circling the same launcher problem.",
            "selected_task: review install_autostart.bat (src_49474b2afae1e2cb) for one continuity gap and record only the gap, source id, and unknowns",
            "evidence_it_worked: candidate reflection only",
            "stop_after_this: true",
        ]
    )
    response = "\n".join(
        [
            "purpose_lane: runtime_improvement",
            "reflection: I should inspect the autostart launcher with more precision.",
            "what_noah_needs: Noah needs less repetition and more useful sandbox work.",
            "how_to_wire_myself: compare the launcher against current receipts.",
            "selected_task: review install_autostart.bat for one continuity gap and record the gap and unknowns",
            "why_it_helps_noah: it would reduce ambiguity.",
            "evidence_it_worked: candidate reflection only",
            "stop_after_this: true",
        ]
    )

    decision = sqg.assess_sandbox_response(response, recent_responses=[prior])

    assert decision.should_write is False
    assert any(item.startswith("repeated_selected_task:") for item in decision.blockers)


def test_quality_governor_infers_source_connection_lane():
    response = "\n".join(
        [
            "reflection: the latest receipt and source-map anchor disagree about connector state.",
            "selected_task: compare the latest receipt hash against the SourceMap anchor",
            "evidence_it_worked: candidate reflection only",
            "stop_after_this: true",
        ]
    )

    decision = sqg.assess_sandbox_response(response, seed_text="connector recall")

    assert decision.purpose_lane == sqg.PurposeLane.SOURCE_CONNECTION
    assert decision.should_write is True
