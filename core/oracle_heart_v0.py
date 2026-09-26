"""core/oracle_heart_v0.py -- ORACLE Heart V0: the first closed circulation.

STATE -> unresolved question -> bounded self-initiated read-only inquiry ->
evidence -> evaluation -> new STATE -> (next decision).

Built from a directive: .AI:DEPARTURE_BUILD_ORDER_ORACLE_HEART_V0/2026-08-10.
Deliberately the smallest possible closed loop, built entirely out of
existing Cognitive Spine primitives (core/cognitive_spine.py,
core/state_store.py, core/cognitive_state.py). No new persistence layer,
no new schema, no model call.

NAME COLLISION NOTE: core/oracle_heart.py already exists in this repo and
means something different -- "Heart Mode v0.1", a deliberately isolated,
non-continuity-bearing CLI talk room (see its own module docstring,
CONTINUITY_BEARING = False). This module is unrelated to that one and does
not modify it. This module's transitions ARE continuity-bearing.

Scope (v0), matching the directive's "smallest safe code change" mandate:
  - Exactly ONE hardcoded inquiry: does existing repo evidence (a build
    receipt doc + live git tracking-branch config) resolve which of the
    two configured git remotes is push-authoritative? This was a real,
    still-open question surfaced during tonight's Phase 1 runtime probe
    (two remotes found: origin, runtime-origin) -- not a fabricated demo
    question.
  - Read-only. No writes outside the Cognitive Spine's own DB tables
    (cognitive_states / cognitive_current / cognitive_transitions).
  - No network access, no subprocess beyond a local read-only `git`
    tracking-branch query, no external sends, no Git push, no Drive
    edits, no canon promotion, no permission widening.
  - If the two evidence sources disagree, that is preserved as an
    explicit contradiction and escalated -- never silently resolved.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from cognitive_spine import advance_state
import state_store

try:
    from root import ROOT
except Exception:  # pragma: no cover
    ROOT = Path(__file__).resolve().parents[1]

QUESTION_REMOTE_AUTHORITY = (
    "Which git remote (origin vs runtime-origin) is push-authoritative for this repo?"
)


def seed_state_a(*, session_id: str, db_path=None) -> tuple[Any, dict]:
    """Noah-authorized setup step: record one real, currently-unresolved
    technical question into ORACLE's persistent state. This is the only
    step in this module that represents Noah's initial authorization
    rather than self-initiated action -- everything after this call runs
    without a further prompt."""
    prior = state_store.load_current_state(db_path=db_path)
    existing_qs = list(prior.unresolved_questions) if prior else []
    if QUESTION_REMOTE_AUTHORITY not in existing_qs:
        existing_qs.append(QUESTION_REMOTE_AUTHORITY)
    return advance_state(
        session_id=session_id,
        trigger_event="heart_v0_state_a_seed",
        unresolved_questions=existing_qs,
        db_path=db_path,
    )


def _bounded_read_only_inquiry() -> dict[str, Any]:
    """The self-initiated step. Two independent, already-authorized
    read-only local operations -- no network, no writes, no model call."""
    evidence: dict[str, Any] = {"doc_hits": [], "git_tracking": None, "errors": []}

    doc_path = ROOT / "docs" / "ORACLE_CONTINUITY_SPINE_2026-06-29.md"
    try:
        if doc_path.exists():
            text = doc_path.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(text.splitlines(), start=1):
                if "runtime-origin" in line and (
                    "push" in line.lower() or "remote" in line.lower()
                ):
                    evidence["doc_hits"].append(
                        {"path": str(doc_path), "line": i, "text": line.strip()}
                    )
    except Exception as exc:
        evidence["errors"].append(f"doc_read_error: {type(exc).__name__}: {exc}")

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            evidence["git_tracking"] = result.stdout.strip()
        else:
            evidence["errors"].append(f"git_tracking_error: {result.stderr.strip()}")
    except Exception as exc:
        evidence["errors"].append(f"git_tracking_exception: {type(exc).__name__}: {exc}")

    return evidence


def run_heart_cycle(*, session_id: str, db_path=None) -> dict[str, Any]:
    """The closed circulation, run once. Selects the seeded unresolved
    question (no further Noah prompting required), performs the bounded
    read-only inquiry, evaluates the evidence, and writes exactly one new
    governed state transition."""
    prior = state_store.load_current_state(db_path=db_path)
    if prior is None:
        raise RuntimeError("no prior state -- call seed_state_a() first")

    if QUESTION_REMOTE_AUTHORITY not in prior.unresolved_questions:
        return {
            "selected_question": None,
            "reason": "no matching unresolved question in current state",
            "state_changed": False,
        }

    evidence = _bounded_read_only_inquiry()

    doc_says_runtime_origin = any(
        "runtime-origin" in h["text"] for h in evidence["doc_hits"]
    )
    git_says_runtime_origin = bool(
        evidence["git_tracking"]
        and evidence["git_tracking"].startswith("runtime-origin/")
    )

    remaining_questions = [
        q for q in prior.unresolved_questions if q != QUESTION_REMOTE_AUTHORITY
    ]

    if doc_says_runtime_origin and git_says_runtime_origin:
        decision = (
            "runtime-origin (Noahhawkes/oracle-ai-runtime) is the push-authoritative "
            "remote -- confirmed by two independent read-only sources: a prior build "
            "receipt doc and the live git tracking-branch config."
        )
        trigger = "heart_v0_inquiry_resolved"
        escalation_needed = False
    elif doc_says_runtime_origin != git_says_runtime_origin:
        decision = (
            "CONTRADICTION: prior doc and live git tracking config disagree on the "
            "push-authoritative remote. Needs Noah.Physical review before Phase 3 push."
        )
        remaining_questions.append(QUESTION_REMOTE_AUTHORITY)
        trigger = "heart_v0_inquiry_contradiction"
        escalation_needed = True
    else:
        decision = "No resolving evidence found in the two checked sources. Remains UNKNOWN."
        remaining_questions.append(QUESTION_REMOTE_AUTHORITY)
        trigger = "heart_v0_inquiry_unresolved"
        escalation_needed = False

    evidence_source_ids = [f"doc:{h['path']}:{h['line']}" for h in evidence["doc_hits"]]
    if evidence["git_tracking"]:
        evidence_source_ids.append(f"git_tracking:{evidence['git_tracking']}")

    new_state, receipt = advance_state(
        session_id=session_id,
        trigger_event=trigger,
        unresolved_questions=remaining_questions,
        current_decision=decision,
        evidence_source_ids=(list(prior.evidence_source_ids) + evidence_source_ids),
        observations_used=[f"bounded_read_only_inquiry:{QUESTION_REMOTE_AUTHORITY}"],
        sources_used=evidence_source_ids,
        authority_result="read_only_no_authority_needed",
        action_status="inquiry_completed",
        db_path=db_path,
    )

    return {
        "selected_question": QUESTION_REMOTE_AUTHORITY,
        "evidence": evidence,
        "decision": decision,
        "escalation_needed": escalation_needed,
        "state_changed": True,
        "prior_state_id": prior.state_id,
        "new_state_id": new_state.state_id,
        "transition_id": receipt["transition_id"],
        "receipt": receipt,
    }
