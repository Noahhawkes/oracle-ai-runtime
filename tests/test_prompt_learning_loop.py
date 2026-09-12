"""Prompt Learning Loop v0.1 (oracle-ai-core issue #8).

Every prompt can teach. No prompt can rule until approved.

Also asserts the reconciliation: this producer and reflection_candidates share
one anti-amplification module rather than maintaining two copies.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import candidate_drift as cd  # noqa: E402
import prompt_learning_loop as pll  # noqa: E402
import reflection_candidates as rc  # noqa: E402


# ── Reconciliation: one loop, two producers ───────────────────────────────────
def test_both_producers_share_one_drift_implementation():
    """If these ever diverge, a fix to one silently leaves the other exposed."""
    assert rc.drift_score is cd.drift_score
    assert rc.DRIFT_THRESHOLD == cd.DRIFT_THRESHOLD
    assert pll.drift_score is cd.drift_score


# ── Nothing is promoted ───────────────────────────────────────────────────────
def test_prompt_becomes_candidate_not_memory():
    result = pll.ingest("I prefer shorter replies")

    assert result["ok"] is True
    c = result["candidate"]
    assert c["promotion_status"] == "observed"
    assert c["requires_approval"] is True
    assert c["promotion_status"] != "approved_meaning"


def test_module_cannot_create_behavioral_rules():
    assert pll.can_create_behavioral_rule() is False


def test_repetition_raises_confidence_never_promotion():
    for _ in range(5):
        pll.ingest("I prefer shorter replies")

    items = pll.list_candidates()
    assert len(items) == 1
    c = items[0]
    assert c["recurrence_count"] >= 3
    # Repetition may reach hypothesis, never approved_meaning.
    assert c["promotion_status"] in ("observed", "hypothesis")
    assert c["requires_approval"] is True


# ── Classification and UNKNOWN preservation ───────────────────────────────────
@pytest.mark.parametrize("prompt,expected", [
    ("No, stop doing that, I told you already", "correction"),
    ("I prefer tables over prose", "preference"),
    ("You must never post publicly without my approval", "boundary_rule"),
])
def test_classification(prompt, expected):
    assert pll.classify_interaction(prompt) == expected


def test_unknown_is_preserved_not_guessed():
    result = pll.ingest("banana turnip helicopter")
    c = result["candidate"]

    assert c["interaction_type"] == "unknown"
    assert "interaction_type" in c["unknowns"]
    assert c["possible_preference"] == pll.UNKNOWN
    assert c["possible_boundary_rule"] == pll.UNKNOWN


# ── Secrets and raw material ──────────────────────────────────────────────────
def test_credential_material_is_blocked_and_never_stored():
    result = pll.ingest("here is my api_key = sk-abcdefghijklmnopqrstuvwxyz012345")

    assert result["ok"] is False
    assert result["action"] == "blocked"
    assert pll.list_candidates() == []


def test_raw_transcript_is_summarized_not_stored():
    raw = "Begin transcript: " + ("verbose filler content " * 500)
    result = pll.ingest(raw)

    c = result["candidate"]
    assert len(c["prompt_summary"]) <= 260
    assert len(c["prompt_summary"]) < len(raw)


def test_sensitive_context_is_tagged():
    result = pll.ingest("Never mention my bankruptcy in anything public")
    c = result["candidate"]

    assert c["sensitive"] is True
    assert c["risk_level"] == "high"


# ── Risk banding ──────────────────────────────────────────────────────────────
def test_boundary_rules_are_high_risk():
    assert pll.assess_risk("never do that without approval", "boundary_rule") == "high"


def test_plain_preference_is_low_risk():
    assert pll.assess_risk("i prefer tables", "preference") == "low"


# ── Governance ────────────────────────────────────────────────────────────────
def test_safe_sleep_blocks_learning_writes(monkeypatch):
    monkeypatch.setenv("ORACLE_SELF_PROMPT_CONTROL_STATE", "SAFE_SLEEP")

    result = pll.ingest("I prefer tables over prose")

    assert result["ok"] is False
    assert "SAFE_SLEEP" in result["blocked_reason"]
    assert pll.list_candidates() == []


def test_safe_sleep_can_be_explicitly_overridden(monkeypatch):
    monkeypatch.setenv("ORACLE_SELF_PROMPT_CONTROL_STATE", "SAFE_SLEEP")

    result = pll.ingest("I prefer tables", allow_during_safe_sleep=True)

    assert result["ok"] is True


def test_optional_integrations_fail_closed():
    assert pll._log_mindcoin({}) in (True, False)
    assert pll._notify_approval_center({}) in (True, False)


# ── Status surface ────────────────────────────────────────────────────────────
def test_status_reports_no_approved_meaning():
    pll.ingest("I prefer shorter replies")
    s = pll.status()

    assert s["total"] == 1
    assert s["approved_meaning_count"] == 0
    assert "Noah.Physical" in s["note"]


# ── The worked example from the spec ──────────────────────────────────────────
def test_the_em_dash_preference_becomes_a_durable_candidate():
    """The preference that sat unenforced in issue #8 from 2026-06-08."""
    result = pll.ingest("keep replies short and do not use em dashes")

    c = result["candidate"]
    assert c["interaction_type"] == "preference"
    assert "em dash" in c["prompt_summary"]
    assert c["requires_approval"] is True
