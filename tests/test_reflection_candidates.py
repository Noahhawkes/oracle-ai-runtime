"""Autonomy Gate Step 3 — the producer wire.

A sandbox reflection becomes a governed proposal, born pending, with a
MirrorShell drift check against ungoverned recursive amplification.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import action_candidates as ac  # noqa: E402
import reflection_candidates as rc  # noqa: E402


REFLECTION = """
reflection: My durable memory holds 6236 messages but nothing reads my own
  reflections back. The loop is open.
what_noah_needs: proof that thinking changes what I do next
how_to_wire_myself: emit each reflection as a pending candidate
selected_task: propose closing the reflection-to-candidate loop
why_it_helps_noah: it makes recursion auditable instead of decorative
evidence_it_worked: candidate reflection only
stop_after_this: true
"""


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(ac, "CANDIDATES_FILE", tmp_path / "action_candidates.json")


# ── Parsing ───────────────────────────────────────────────────────────────────
def test_parse_reflection_keeps_multiline_fields_and_invents_nothing():
    parsed = rc.parse_reflection(REFLECTION)

    assert parsed["selected_task"] == "propose closing the reflection-to-candidate loop"
    assert "The loop is open." in parsed["reflection"]
    assert parsed["evidence_it_worked"] == "candidate reflection only"
    # A field that was never written must not appear.
    assert "refuse_without_noah_approval" not in parsed


# ── Production ────────────────────────────────────────────────────────────────
def test_reflection_becomes_a_pending_candidate(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    result = rc.submit_reflection_candidate(
        REFLECTION, receipt_path="Memory/r.json", session_id="335"
    )

    assert result["ok"] is True
    assert result["action"] == "submitted"
    cand = result["candidate"]
    # Born pending. Always.
    assert cand["status"] == "pending"
    assert cand["required_approval"] is True
    assert cand["approved_by"] is None
    assert cand["title"] == "propose closing the reflection-to-candidate loop"
    assert "Memory/r.json" in cand["evidence"]
    assert ac.is_executable(cand) is False


def test_silent_reflection_produces_no_fake_proposal(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    for text in (
        "reflection: nothing new this cycle\nstop_after_this: true",
        "selected_task: none",
        "selected_task: UNKNOWN",
        "",
    ):
        result = rc.submit_reflection_candidate(text)
        assert result["action"] == "skipped", text
    assert ac.list_candidates() == []


# ── MirrorShell drift ─────────────────────────────────────────────────────────
def test_repeated_reflection_is_quarantined_not_amplified(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    first = rc.submit_reflection_candidate(REFLECTION)
    assert first["action"] == "submitted"

    # She proposes essentially the same thing again — the amplification case.
    second = rc.submit_reflection_candidate(REFLECTION)

    assert second["action"] == "quarantined"
    assert second["drift_score"] >= rc.DRIFT_THRESHOLD
    assert second["candidate"]["status"] == "quarantined"
    assert "MirrorShell drift" in second["candidate"]["rejection_reason"]
    # The attempt stays on the record rather than vanishing.
    assert len(ac.list_candidates()) == 2
    # A quarantined candidate can never execute.
    assert ac.is_executable(second["candidate"]) is False
    assert ac.is_inactive(second["candidate"]) is True


def test_genuinely_new_reflection_is_not_treated_as_drift(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    rc.submit_reflection_candidate(REFLECTION)
    different = """
reflection: The current-observation gate never fires because intent dispatch
  wins precedence.
what_noah_needs: answers to the question he actually asked
how_to_wire_myself: run the observation boundary before intent dispatch
selected_task: propose reordering the current-observation precedence
why_it_helps_noah: he gets a real answer about his own screen
evidence_it_worked: candidate reflection only
"""

    result = rc.submit_reflection_candidate(different)

    assert result["action"] == "submitted"
    assert result["drift_score"] < rc.DRIFT_THRESHOLD


# ── Risk banding ──────────────────────────────────────────────────────────────
def test_outside_sandbox_proposal_is_high_risk(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    escalated = """
reflection: I could keep the repo current myself.
selected_task: git push the checkpoint branch to origin
how_to_wire_myself: call git push after each pulse
evidence_it_worked: candidate reflection only
"""

    result = rc.submit_reflection_candidate(escalated)

    assert result["candidate"]["risk_level"] == "high"
    assert result["candidate"]["required_approval"] is True
    assert result["candidate"]["status"] == "pending"


def test_sandbox_only_proposal_is_low_risk(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    result = rc.submit_reflection_candidate(REFLECTION)

    assert result["candidate"]["risk_level"] == "low"


# ── Loop closing ──────────────────────────────────────────────────────────────
def test_only_approved_candidates_feed_forward(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    result = rc.submit_reflection_candidate(REFLECTION)
    # Pending work is not yet ground to reason from.
    assert rc.approved_candidate_context() == ""

    ac.approve(result["candidate"]["id"], approved_by="noah")
    context = rc.approved_candidate_context()

    assert "propose closing the reflection-to-candidate loop" in context
    assert "approved" in context.lower()


def test_rejected_candidate_never_feeds_forward(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    result = rc.submit_reflection_candidate(REFLECTION)
    ac.reject(result["candidate"]["id"], rejected_by="noah", reason="not now")

    assert rc.approved_candidate_context() == ""


# ── Failure containment ───────────────────────────────────────────────────────
def test_producer_failure_never_breaks_the_thinking_cycle(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    def _boom(*_a, **_k):
        raise RuntimeError("store unavailable")

    monkeypatch.setattr(ac, "submit", _boom)
    result = rc.submit_reflection_candidate(REFLECTION)

    assert result["ok"] is False
    assert result["action"] == "error"
    assert "store unavailable" in result["error"]
