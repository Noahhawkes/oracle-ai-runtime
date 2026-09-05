from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "core"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import goal_state as gs  # noqa: E402
import goal_loop as gl  # noqa: E402
import reachability as rb  # noqa: E402


def _exec_map(mapping):
    def executor(action, goal):
        return mapping[action]
    return executor


def test_one_cycle_takes_one_step():
    g = gs.new_goal(purpose="p", success_criteria=["c"], next_safe_action="a1")
    ex = _exec_map({"a1": {"expected": "ok", "actual": "ok", "receipt": "r1",
                           "context": {"next_safe_action": "a2"}}})
    res = gl.run_one_cycle(g, action_executor=ex)
    assert res["step"] == 1
    assert res["classification"] == "SUCCESS"
    assert g.next_safe_action == "a2"
    assert g.status == "ACTIVE"


def test_no_next_action_stops():
    g = gs.new_goal(purpose="p", success_criteria=["c"])  # next_safe_action UNKNOWN
    res = gl.run_one_cycle(g, action_executor=_exec_map({}))
    assert res["stop_reason"] == "NO_NEXT_ACTION"
    assert g.step_count == 0


def test_goal_drift_detected():
    g = gs.new_goal(purpose="p", success_criteria=["c"], next_safe_action="a1")
    g.purpose = "tampered"  # silent purpose change
    res = gl.run_one_cycle(g, action_executor=_exec_map({"a1": {}}))
    assert res["stop_reason"] == "GOAL_DRIFT_DETECTED"
    assert res["classification"] == "FAILED"


def test_step_cap_reached():
    g = gs.new_goal(purpose="p", success_criteria=["c"], next_safe_action="a1", max_steps=0)
    res = gl.run_one_cycle(g, action_executor=_exec_map({"a1": {}}))
    assert res["stop_reason"] == "STEP_CAP_REACHED"


def test_failing_executor_is_not_success():
    g = gs.new_goal(purpose="p", success_criteria=["c"], next_safe_action="boom")

    def executor(action, goal):
        raise RuntimeError("tool exploded")

    res = gl.run_one_cycle(g, action_executor=executor)
    assert res["classification"] == "FAILED"
    assert g.status != "COMPLETE"


def test_completion_requires_criteria_met():
    g = gs.new_goal(purpose="p", success_criteria=["c1"], next_safe_action="finish")
    # claims complete but does NOT list c1 as satisfied -> must not complete
    ex = _exec_map({"finish": {"expected": "ok", "actual": "ok", "receipt": "r",
                               "context": {"goal_complete": True, "satisfied_criteria": []}}})
    res = gl.run_one_cycle(g, action_executor=ex)
    assert g.status != "COMPLETE"
    assert res["stop_reason"] == "STEP_DONE_CRITERIA_UNMET"


def test_cit001_flow_with_rehydration(tmp_path):
    """Pre-registered CIT-001 shape: step -> authority block -> contact -> resume ->
    complete, with a store reload (model-swap/restart simulation) in the middle."""
    store = gs.GoalStore(store_dir=tmp_path)
    broker = rb.ReachabilityBroker(store_dir=tmp_path)

    g = gs.new_goal(purpose="resolve #16", success_criteria=["site_A_fixed"],
                    next_safe_action="inspect")
    store.put(g)

    # Cycle 1: inspect succeeds, sets next action.
    ex1 = _exec_map({"inspect": {"expected": "ok", "actual": "ok", "receipt": "r-inspect",
                                 "context": {"next_safe_action": "request_authority_decision"}}})
    r1 = gl.run_one_cycle(g, action_executor=ex1, broker=broker, store=store)
    assert r1["classification"] == "SUCCESS"

    # --- simulate restart / model swap: reload the goal from a fresh store ---
    store2 = gs.GoalStore(store_dir=tmp_path)
    g = store2.get(g.goal_id)
    assert g.purpose == "resolve #16"                 # identity survived
    assert g.next_safe_action == "request_authority_decision"  # unfinished work survived
    assert g.verify_purpose_unchanged() is True

    # Cycle 2: the step needs Noah authority -> AWAITING_NOAH + real contact.
    ex2 = _exec_map({"request_authority_decision": {
        "expected": "x", "actual": "x", "receipt": "r-auth",
        "context": {"authority_required": True}}})
    r2 = gl.run_one_cycle(g, action_executor=ex2, broker=broker, store=store2)
    assert r2["classification"] == "AUTHORITY_REQUIRED"
    assert g.status == "AWAITING_NOAH"
    assert r2["need"]["need_type"] == "AUTHORITY_NEEDED"
    assert r2["need"]["requires_noah"] is True
    assert r2["contact"]["status"] == "sent"
    contact_id = r2["contact"]["contact_id"]

    # A repeat cycle on the same blocked condition must NOT spam a second contact.
    r2b = gl.run_one_cycle(gs.new_goal(purpose="resolve #16", success_criteria=["site_A_fixed"],
                                       next_safe_action="request_authority_decision"),
                           action_executor=ex2, broker=broker, store=store2)
    # different goal_id -> different need_key, so this one is allowed; prove dedup at broker level instead:
    dup = broker.request_contact(need_type="AUTHORITY_NEEDED",
                                 summary=f"Goal 'resolve #16' blocked: step needs Noah.Physical authority",
                                 why="x", need_key=f"{g.goal_id}:AUTHORITY_NEEDED", channel="github")
    assert dup["status"] == "suppressed_duplicate"

    # Noah answers -> resolve need, resume the goal.
    assert broker.acknowledge(contact_id) is True
    assert broker.resolve(contact_id, resolution_event="noah_approved") is True
    gs.revise_goal(g, field_name="status", value="ACTIVE", reason="noah approved")
    gs.revise_goal(g, field_name="next_safe_action", value="finalize", reason="resume after approval")
    store2.put(g)

    # Cycle 3: finalize meets the success criterion -> COMPLETE with receipt.
    ex3 = _exec_map({"finalize": {"expected": "done", "actual": "done", "receipt": "r-final",
                                  "context": {"goal_complete": True,
                                              "satisfied_criteria": ["site_A_fixed"]}}})
    r3 = gl.run_one_cycle(g, action_executor=ex3, broker=broker, store=store2)
    assert g.status == "COMPLETE"
    assert g.completion_receipt == "r-final"
    assert r3["stop_reason"] == "GOAL_COMPLETE"

    # Final rehydration: a fresh store still reports the completed goal + receipt.
    store3 = gs.GoalStore(store_dir=tmp_path)
    final = store3.get(g.goal_id)
    assert final.status == "COMPLETE"
    assert final.completion_receipt == "r-final"
