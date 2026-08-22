from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "core"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import self_state as ss  # noqa: E402


def test_state_from_evidence_unknown_stays_unknown():
    state = ss.build_self_state({})
    assert state["schema_version"] == "self_state.v1"
    assert state["runtime_status"] == ss.UNKNOWN
    assert state["model_name"] == ss.UNKNOWN
    assert state["build"]["build_match_status"] == "CAPABILITY_UNKNOWN"
    assert state["classification"] == "NORMAL"
    assert state["state_hash"]


def test_duplicate_observation_no_meaningful_change():
    ev = {"runtime_status": "online", "model_name": "qwen2.5:7b"}
    s1 = ss.build_self_state(ev)
    s2 = ss.build_self_state(ev)
    assert s1["state_hash"] == s2["state_hash"]
    assert ss.has_meaningful_change(s1, s2) is False


def test_meaningful_change_produces_new_hash():
    s1 = ss.build_self_state({"runtime_status": "online"})
    s2 = ss.build_self_state({"runtime_status": "degraded"})
    assert s1["state_hash"] != s2["state_hash"]
    assert ss.has_meaningful_change(s1, s2) is True
    assert ss.has_meaningful_change(None, s1) is True


def test_previous_state_linkage():
    s1 = ss.build_self_state({"runtime_status": "online"})
    s2 = ss.build_self_state({"runtime_status": "degraded"}, previous=s1)
    assert s2["previous_state_id"] == s1["self_state_id"]


def test_state_hash_deterministic():
    ev = {"active_goal": "resolve #16", "open_loops": ["a", "b"]}
    assert ss.build_self_state(ev)["state_hash"] == ss.build_self_state(ev)["state_hash"]


def test_classification_noah_required_on_pending_approval():
    state = ss.build_self_state({"pending_approvals": ["promote canon X"]})
    assert state["classification"] == "NOAH_REQUIRED"


def test_trivial_event_does_not_alert():
    state = ss.build_self_state({"runtime_status": "online"})
    need = ss.evaluate_need(state, {})
    assert need.need_type == "NO_NEED"
    assert need.score == 0
    assert need.tier == "CONTINUE_SILENTLY"
    assert need.requires_noah is False


def test_authority_requirement_needs_noah():
    state = ss.build_self_state({"pending_approvals": ["canon promotion"]})
    need = ss.evaluate_need(state, {"authority_required": True})
    assert need.need_type == "AUTHORITY_NEEDED"
    assert need.requires_noah is True
    assert need.score >= 70
    assert need.tier in ("NOTIFY", "URGENT_NOTIFY")


def test_source_conflict_triggers_review():
    state = ss.build_self_state({"known_conflicts": [{"a": "1982-02-02", "b": "1982-03-01"}]})
    need = ss.evaluate_need(state, {})
    assert need.need_type == "CONFLICT_NEEDS_RESOLUTION"
    assert need.requires_noah is True


def test_continuity_risk_triggers_contact():
    state = ss.build_self_state({})
    need = ss.evaluate_need(state, {"uncommitted_work": True, "severity": 85})
    assert need.need_type == "CONTINUITY_AT_RISK"
    assert need.requires_noah is True
    assert need.score >= 70


def test_model_cannot_arbitrarily_force_urgency_to_100():
    state = ss.build_self_state({})
    need = ss.evaluate_need(state, {
        "human_review_recommended": True,
        "urgency": 999, "severity": 999,   # injected garbage
    })
    assert need.need_type == "HUMAN_REVIEW_RECOMMENDED"
    assert need.dimensions["urgency"] == 100      # clamped
    assert need.dimensions["severity"] == 100     # clamped
    assert need.score < 70                         # low base type cannot be forced urgent
    assert need.requires_noah is False
