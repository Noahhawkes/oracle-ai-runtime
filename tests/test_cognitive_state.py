from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import cognitive_state as cs  # noqa: E402


def test_new_root_state_has_no_parent_and_valid_hash():
    state = cs.new_root_state(session_id="s1", current_intent="say_hello")

    assert state.parent_state_id is None
    assert state.session_id == "s1"
    assert state.current_intent == "say_hello"
    assert state.state_hash
    assert state.verify_hash() is True


def test_derive_next_state_links_parent_and_carries_forward_untouched_fields():
    root = cs.new_root_state(
        session_id="s1",
        active_goals=["ship_cognitive_spine"],
        epistemic_claim_ids=["claim_1"],
    )

    child = cs.derive_next_state(root, session_id="s1", current_intent="continue_build")

    assert child.parent_state_id == root.state_id
    assert child.state_id != root.state_id
    # untouched list/scalar fields carry forward unchanged
    assert child.active_goals == ["ship_cognitive_spine"]
    assert child.epistemic_claim_ids == ["claim_1"]
    # explicitly-passed field is applied
    assert child.current_intent == "continue_build"


def test_derive_next_state_overrides_only_specified_fields():
    root = cs.new_root_state(
        session_id="s1",
        unresolved_questions=["is_x_true"],
        contradiction_ids=["claim_a", "claim_b"],
    )

    child = cs.derive_next_state(root, session_id="s1", unresolved_questions=[])

    # explicit empty list replaces the prior list
    assert child.unresolved_questions == []
    # omitted list field still carries forward
    assert child.contradiction_ids == ["claim_a", "claim_b"]


def test_hash_changes_when_content_changes():
    root = cs.new_root_state(session_id="s1", current_intent="a")
    other = cs.new_root_state(session_id="s1", current_intent="b")

    assert root.state_hash != other.state_hash


def test_from_dict_round_trip():
    root = cs.new_root_state(session_id="s1", active_goals=["g1"], model_id="qwen2.5:7b")

    restored = cs.CognitiveState.from_dict(root.to_dict())

    assert restored == root
    assert restored.verify_hash() is True


def test_verify_hash_detects_tamper():
    root = cs.new_root_state(session_id="s1", current_intent="a")

    tampered = cs.CognitiveState.from_dict(root.to_dict())
    tampered.current_intent = "tampered"

    assert tampered.verify_hash() is False
