from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import cognitive_state as cs  # noqa: E402
import state_store  # noqa: E402


def test_save_and_load_state_round_trip(tmp_path):
    db_path = tmp_path / "cognitive_test.db"
    state = cs.new_root_state(session_id="s1", current_intent="hello")

    state_store.save_state(state, db_path=db_path)
    loaded = state_store.load_state(state.state_id, db_path=db_path)

    assert loaded == state
    assert loaded.verify_hash() is True


def test_load_state_missing_returns_none(tmp_path):
    db_path = tmp_path / "cognitive_test.db"

    assert state_store.load_state("cogstate_does_not_exist", db_path=db_path) is None
    assert state_store.load_current_state(db_path=db_path) is None


def test_load_current_state_returns_latest(tmp_path):
    db_path = tmp_path / "cognitive_test.db"
    root = cs.new_root_state(session_id="s1")
    state_store.save_state(root, db_path=db_path)
    child = cs.derive_next_state(root, session_id="s1", current_intent="second_turn")
    state_store.save_state(child, db_path=db_path)

    current = state_store.load_current_state(db_path=db_path)

    assert current.state_id == child.state_id
    assert current.parent_state_id == root.state_id


def test_load_lineage_walks_parent_chain(tmp_path):
    db_path = tmp_path / "cognitive_test.db"
    root = cs.new_root_state(session_id="s1")
    state_store.save_state(root, db_path=db_path)
    mid = cs.derive_next_state(root, session_id="s1", current_intent="mid")
    state_store.save_state(mid, db_path=db_path)
    tip = cs.derive_next_state(mid, session_id="s1", current_intent="tip")
    state_store.save_state(tip, db_path=db_path)

    lineage = state_store.load_lineage(tip.state_id, db_path=db_path)

    assert [s.state_id for s in lineage] == [tip.state_id, mid.state_id, root.state_id]


def test_save_and_load_transition_receipt(tmp_path):
    db_path = tmp_path / "cognitive_test.db"
    receipt = {
        "transition_id": "cogxn_abc",
        "prior_state_id": None,
        "new_state_id": "cogstate_abc",
        "trigger_event": "chat_turn",
        "timestamp": "2026-08-08T00:00:00+00:00",
    }

    state_store.save_transition_receipt(receipt, db_path=db_path)
    loaded = state_store.load_transition("cogxn_abc", db_path=db_path)

    assert loaded == receipt


def test_list_recent_transitions_orders_newest_first(tmp_path):
    db_path = tmp_path / "cognitive_test.db"
    for i in range(3):
        state_store.save_transition_receipt(
            {
                "transition_id": f"cogxn_{i}",
                "prior_state_id": None,
                "new_state_id": f"cogstate_{i}",
                "trigger_event": "chat_turn",
                "timestamp": f"2026-08-08T00:00:0{i}+00:00",
            },
            db_path=db_path,
        )

    recent = state_store.list_recent_transitions(limit=2, db_path=db_path)

    assert len(recent) == 2
    assert recent[0]["transition_id"] == "cogxn_2"
