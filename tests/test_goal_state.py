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
import pytest  # noqa: E402


def test_new_goal_has_immutable_purpose_hash():
    g = gs.new_goal(purpose="resolve #16", success_criteria=["site_A_fixed"])
    assert g.status == "ACTIVE"
    assert g.purpose_hash
    assert g.verify_purpose_unchanged() is True


def test_purpose_is_immutable():
    g = gs.new_goal(purpose="resolve #16", success_criteria=["x"])
    with pytest.raises(ValueError):
        gs.revise_goal(g, field_name="purpose", value="something else", reason="drift")
    with pytest.raises(ValueError):
        gs.revise_goal(g, field_name="success_criteria", value=["y"], reason="drift")


def test_revise_records_history():
    g = gs.new_goal(purpose="p", success_criteria=["x"])
    gs.revise_goal(g, field_name="next_safe_action", value="inspect", reason="planning")
    assert g.next_safe_action == "inspect"
    assert g.revision_history[-1]["field"] == "next_safe_action"
    assert g.revision_history[-1]["reason"] == "planning"


def test_evaluate_result_classes():
    assert gs.evaluate_result("done", "done")["classification"] == "SUCCESS"
    assert gs.evaluate_result("done", "done partially")["classification"] == "PARTIAL"
    assert gs.evaluate_result("done", "nope")["classification"] == "FAILED"
    assert gs.evaluate_result("done", None)["classification"] == "NO_PROGRESS"
    assert gs.evaluate_result("x", "x", context={"authority_required": True})["classification"] == "AUTHORITY_REQUIRED"
    assert gs.evaluate_result("x", "x", context={"conflict": True})["classification"] == "CONFLICT"
    assert gs.evaluate_result("x", "x", context={"new_information": True})["classification"] == "NEW_INFORMATION"
    assert gs.evaluate_result("x", "x", context={"failed": True, "error": "boom"})["classification"] == "FAILED"


def test_goalstore_persists_and_reloads(tmp_path):
    store = gs.GoalStore(store_dir=tmp_path)
    g = gs.new_goal(purpose="resolve #16", success_criteria=["site_A_fixed"], next_safe_action="inspect")
    store.put(g)
    # simulate restart / model swap: brand-new store from the same dir
    store2 = gs.GoalStore(store_dir=tmp_path)
    g2 = store2.get(g.goal_id)
    assert g2 is not None
    assert g2.purpose == "resolve #16"
    assert g2.next_safe_action == "inspect"
    assert g2.verify_purpose_unchanged() is True
