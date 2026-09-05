from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "core"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import context_rehydrator as cr  # noqa: E402
import subagent_dispatcher as sd  # noqa: E402


# ── context rehydrator ───────────────────────────────────────────────────────

def test_capsule_built_from_event_and_goal():
    cap = cr.build_capsule(
        latest_event_fn=lambda: {"event_id": "evt_42", "session_id": "s1"},
        active_goal_fn=lambda: {"purpose": "wire DeepCut into recall", "status": "ACTIVE",
                                "next_safe_action": "add tests", "last_progress": "gate built",
                                "blocked_by": "UNKNOWN"})
    assert cap["has_state"] is True
    assert cap["goal"] == "wire DeepCut into recall"
    assert cap["next_step"] == "add tests"
    assert cap["last_event"] == "evt_42"
    assert cap["provenance"]


def test_render_capsule_is_bounded_block():
    cap = cr.build_capsule(latest_event_fn=lambda: {"event_id": "e"},
                           active_goal_fn=lambda: {"purpose": "P", "next_safe_action": "N"})
    block = cr.render_capsule(cap)
    assert "<return_to_work_state>" in block and "</return_to_work_state>" in block
    assert "P" in block and "N" in block
    assert len(block) <= cr.MAX_CAPSULE_CHARS


def test_no_state_renders_empty():
    cap = cr.build_capsule(latest_event_fn=lambda: None, active_goal_fn=lambda: None)
    assert cap["has_state"] is False
    assert cr.render_capsule(cap) == ""
    # convenience path fails closed too
    assert cr.return_to_work_block(latest_event_fn=lambda: None, active_goal_fn=lambda: None) == ""


# ── subagent dispatcher ──────────────────────────────────────────────────────

def test_formulate_directive_is_a_real_ai_build_block():
    d = sd.formulate_directive(title="fix Ashley recall",
                               mission="Route personal-entity questions through the DeepCut gate.",
                               failure="Who is Ashley -> no record",
                               files_to_inspect=["core/recall_orchestrator.py"],
                               tests_to_run=["pytest tests/test_deepcut_recall_gate.py -q"])
    assert d.startswith(".AI:CLAUDE_CODE_BUILD/")
    assert ".AI:END_CLAUDE_CODE_BUILD" in d
    assert "Who is Ashley" in d
    assert "core/recall_orchestrator.py" in d
    assert "MISSION" in d


def test_dispatch_appends_to_one_ledger(tmp_path):
    ledger = tmp_path / "build_directives.jsonl"
    r1 = sd.dispatch(title="a", mission="do a", ledger=ledger)
    r2 = sd.dispatch(title="b", mission="do b", ledger=ledger)
    assert r1["ok"] and r2["ok"]
    assert r1["dispatch_id"] != r2["dispatch_id"]
    lines = ledger.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2  # one rolling ledger, not one file per directive
    assert json.loads(lines[0])["status"] == "PENDING_AGENT"
    assert r1["directive_sha256"]


def test_from_goal_block(tmp_path):
    import goal_state as gs
    g = gs.new_goal(purpose="unblock recall", success_criteria=["ashley_returns"],
                    next_safe_action="inspect")
    gs.revise_goal(g, field_name="blocked_by", value="needs authority", reason="test")
    res = sd.from_goal_block(g, ledger=tmp_path / "d.jsonl")
    assert res["ok"]
    assert "unblock recall" in res["directive"]
    assert "needs authority" in res["directive"]
