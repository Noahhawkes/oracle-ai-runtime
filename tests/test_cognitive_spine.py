from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import cognitive_spine as spine  # noqa: E402
import state_store  # noqa: E402


def test_advance_state_creates_root_state_when_none_exists(tmp_path):
    db_path = tmp_path / "cognitive_test.db"

    state, receipt = spine.advance_state(
        session_id="s1", trigger_event="boot", current_intent="wake_up", db_path=db_path
    )

    assert state.parent_state_id is None
    assert receipt["prior_state_id"] is None
    assert receipt["new_state_id"] == state.state_id
    assert receipt["state_hash"] == state.state_hash
    assert receipt["trigger_event"] == "boot"


def test_advance_state_creates_child_with_parent_linkage(tmp_path):
    db_path = tmp_path / "cognitive_test.db"
    first, _ = spine.advance_state(session_id="s1", trigger_event="boot", db_path=db_path)

    second, receipt = spine.advance_state(
        session_id="s1", trigger_event="chat_turn", current_decision="respond", db_path=db_path
    )

    assert second.parent_state_id == first.state_id
    assert receipt["prior_state_id"] == first.state_id


def test_advance_state_carries_forward_omitted_fields(tmp_path):
    db_path = tmp_path / "cognitive_test.db"
    spine.advance_state(
        session_id="s1",
        trigger_event="boot",
        active_goals=["ship_cognitive_spine"],
        epistemic_claim_ids=["claim_1"],
        db_path=db_path,
    )

    state, _ = spine.advance_state(session_id="s1", trigger_event="chat_turn", db_path=db_path)

    assert state.active_goals == ["ship_cognitive_spine"]
    assert state.epistemic_claim_ids == ["claim_1"]


def test_integrate_chat_turn_records_observation_and_preserves_prior_state(tmp_path):
    db_path = tmp_path / "cognitive_test.db"
    spine.advance_state(
        session_id="s1", trigger_event="boot", active_goals=["build_spine"], db_path=db_path
    )

    state, receipt = spine.integrate_chat_turn(
        session_id="s1",
        user_text="What are we building?",
        reply_text="We are building the Cognitive Spine.",
        model_id="qwen2.5:7b",
        db_path=db_path,
    )

    assert state.active_goals == ["build_spine"]
    assert state.model_id == "qwen2.5:7b"
    assert state.current_decision == "respond"
    assert receipt["action_status"] == "responded"
    assert receipt["observations_used"][0].startswith("user_text_sha256:")


# ── Acceptance test 1: context removal ──────────────────────────────────────
# A verified fact is introduced in Session A and integrated into CognitiveState.
# The immediate conversation context is discarded and a new Session B begins
# with the fact NOT reinserted into the prompt. ORACLE's answer must depend on
# the persisted state, not on the fact being re-typed.
def test_context_removal_acceptance(tmp_path):
    db_path = tmp_path / "cognitive_test.db"

    # Session A: a fact is verified and integrated into state.
    spine.advance_state(
        session_id="session-A",
        trigger_event="verified_fact_integrated",
        epistemic_claim_ids=["claim_jupiter_station_2397"],
        active_goals=["track_jupiter_station_canon"],
        db_path=db_path,
    )

    # Session A's in-memory context (chat history, prompt) is discarded here --
    # nothing carries it forward except what was written to state_store.

    # Session B begins. It does NOT reinsert the fact into any prompt; it only
    # asks a semantically indirect question and consults persisted state.
    current = state_store.load_current_state(db_path=db_path)

    assert current is not None
    assert current.session_id == "session-A"  # state outlives the session that wrote it
    assert "claim_jupiter_station_2397" in current.epistemic_claim_ids
    assert "track_jupiter_station_canon" in current.active_goals

    # Session B integrates its own turn without repeating the fact, and the
    # fact must still be present afterward -- state accumulated, not reset.
    state_b, _ = spine.advance_state(
        session_id="session-B", trigger_event="chat_turn", db_path=db_path
    )
    assert "claim_jupiter_station_2397" in state_b.epistemic_claim_ids


# ── Acceptance test 2: model swap ───────────────────────────────────────────
# Continuity must not belong to the reasoning model. Swapping model_id between
# two transitions must not perturb the persisted intent/goals/claims.
def test_model_swap_acceptance(tmp_path):
    db_path = tmp_path / "cognitive_test.db"

    spine.advance_state(
        session_id="s1",
        trigger_event="verified_fact_integrated",
        model_id="qwen2.5:7b",
        epistemic_claim_ids=["claim_x"],
        active_goals=["goal_x"],
        db_path=db_path,
    )

    # Reasoning model is swapped/mocked for the next transition.
    swapped, _ = spine.advance_state(
        session_id="s1",
        trigger_event="chat_turn",
        model_id="mock-different-model-v9",
        db_path=db_path,
    )

    assert swapped.model_id == "mock-different-model-v9"
    # MODEL != CONTINUITY STATE: identity-bearing fields are unaffected by the swap.
    assert swapped.epistemic_claim_ids == ["claim_x"]
    assert swapped.active_goals == ["goal_x"]


# ── Acceptance test 3: contradiction preservation ───────────────────────────
# Two contradictory verified sources must both persist as claim ids. A store
# reload (simulated restart -- no shared Python state, fresh load calls) must
# not flatten them into a single resolved value.
def test_contradiction_preservation_acceptance(tmp_path):
    db_path = tmp_path / "cognitive_test.db"

    spine.advance_state(
        session_id="s1",
        trigger_event="contradiction_observed",
        contradiction_ids=["claim_a_says_x", "claim_b_says_not_x"],
        db_path=db_path,
    )

    # Simulate a restart: a fresh load with no in-process state carried over.
    reloaded = state_store.load_current_state(db_path=db_path)

    assert reloaded is not None
    assert set(reloaded.contradiction_ids) == {"claim_a_says_x", "claim_b_says_not_x"}
    assert len(reloaded.contradiction_ids) == 2  # neither claim was dropped or merged

    # An unrelated later turn that doesn't mention contradictions must still
    # preserve them (they are not silently resolved by inaction).
    later, _ = spine.advance_state(session_id="s1", trigger_event="chat_turn", db_path=db_path)
    assert set(later.contradiction_ids) == {"claim_a_says_x", "claim_b_says_not_x"}
