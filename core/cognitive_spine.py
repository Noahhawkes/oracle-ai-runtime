"""ORACLE Cognitive Spine -- the one authoritative state-transition cycle
(Cognitive Spine v1, Phase 1: minimal transition wrapper).

advance_state() is the only function in ORACLE that is allowed to move
CognitiveState from Psi(n) to Psi(n+1). It:

  1. loads the current CognitiveState (core/state_store.py), or starts a
     fresh lineage if none exists yet,
  2. derives the next CognitiveState, carrying forward anything not
     explicitly superseded this turn (core/cognitive_state.py),
  3. persists it (core/state_store.py),
  4. writes a transition receipt (core/state_store.py),
  5. returns (new_state, receipt).

This module does NOT reimplement recall, evidence gathering, contradiction
tracking, capability probing, or authority checks. Those remain owned by
core/recall_orchestrator.py, core/epistemic_ledger.py, core/capability_broker.py,
and the SOV1/governance modules respectively -- callers pass in the
ids/results those systems already produced. cognitive_spine.py only owns
the transition itself:

    MODEL != CONTINUITY STATE
    ROUTER != CONTINUITY STATE
    MEMORY (evidence) != CONTINUITY STATE

This is that state.

Phase 1 scope: wired into exactly one /chat path -- oracle_server.py's
default companion-engine turn, via integrate_chat_turn(). That wiring is
deliberately observational (records that a turn happened; carries forward
existing intent/goals/claims/contradictions/unknowns unchanged) because
real intent/goal extraction and epistemic-claim integration are Phase 2
work. Other entry points (core/oracle_heart.py, core/daemon.py,
core/bridge.py, the CLI REPL in core/oracle.py) are intentionally NOT
wired yet -- see their module-level CONTINUITY_BEARING markers.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

from cognitive_state import CognitiveState, derive_next_state, new_root_state, sha256_text
import state_store


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_transition_id() -> str:
    return f"cogxn_{uuid.uuid4().hex}"


def _as_list(value: "Iterable[str] | None") -> "list[str] | None":
    if value is None:
        return None
    return [str(v) for v in value]


def advance_state(
    *,
    session_id: str,
    trigger_event: str,
    current_intent: str | None = None,
    active_goals: "Iterable[str] | None" = None,
    unresolved_questions: "Iterable[str] | None" = None,
    epistemic_claim_ids: "Iterable[str] | None" = None,
    contradiction_ids: "Iterable[str] | None" = None,
    unknown_ids: "Iterable[str] | None" = None,
    evidence_source_ids: "Iterable[str] | None" = None,
    current_decision: str | None = None,
    pending_action_ids: "Iterable[str] | None" = None,
    recent_receipt_ids: "Iterable[str] | None" = None,
    capability_snapshot_id: str | None = None,
    model_id: str | None = None,
    build_fingerprint: str | None = None,
    scope: str = state_store.GLOBAL_SCOPE,
    observations_used: "Iterable[str] | None" = None,
    sources_used: "Iterable[str] | None" = None,
    authority_result: str = "not_evaluated",
    action_status: str = "none",
    db_path=None,
) -> "tuple[CognitiveState, dict[str, Any]]":
    """Advance ORACLE's persistent cognitive state by exactly one transition.

    Fields left as None carry forward from the prior state unchanged --
    only pass what actually changed this turn. List fields passed as an
    explicit (possibly empty) iterable REPLACE the prior list; omit them
    (None) to carry the prior list forward untouched -- this is what keeps
    contradictions/unknowns from being silently dropped by an unrelated
    turn.
    """
    prior = state_store.load_current_state(scope=scope, db_path=db_path)

    overrides: dict[str, Any] = {
        "current_intent": current_intent,
        "active_goals": _as_list(active_goals),
        "unresolved_questions": _as_list(unresolved_questions),
        "epistemic_claim_ids": _as_list(epistemic_claim_ids),
        "contradiction_ids": _as_list(contradiction_ids),
        "unknown_ids": _as_list(unknown_ids),
        "evidence_source_ids": _as_list(evidence_source_ids),
        "current_decision": current_decision,
        "pending_action_ids": _as_list(pending_action_ids),
        "recent_receipt_ids": _as_list(recent_receipt_ids),
        "capability_snapshot_id": capability_snapshot_id,
        "model_id": model_id,
        "build_fingerprint": build_fingerprint,
    }

    if prior is None:
        new_state = new_root_state(session_id=session_id, **overrides)
    else:
        new_state = derive_next_state(prior, session_id=session_id, **overrides)

    state_store.save_state(new_state, scope=scope, db_path=db_path)

    receipt = {
        "transition_id": _new_transition_id(),
        "prior_state_id": prior.state_id if prior else None,
        "new_state_id": new_state.state_id,
        "trigger_event": trigger_event,
        "observations_used": _as_list(observations_used) or [],
        "sources_used": _as_list(sources_used) or list(new_state.evidence_source_ids),
        "contradictions_preserved": list(new_state.contradiction_ids),
        "unknowns_preserved": list(new_state.unknown_ids),
        "model_used": new_state.model_id,
        "decision": new_state.current_decision,
        "action_status": action_status,
        "receipts_created": list(new_state.recent_receipt_ids),
        "authority_result": authority_result,
        "state_hash": new_state.state_hash,
        "timestamp": _utc_now_iso(),
    }
    state_store.save_transition_receipt(receipt, db_path=db_path)
    return new_state, receipt


def integrate_chat_turn(
    *,
    session_id: str,
    user_text: str,
    reply_text: str,
    model_id: str | None = None,
    build_fingerprint: str | None = None,
    evidence_source_ids: "Iterable[str] | None" = None,
    db_path=None,
) -> "tuple[CognitiveState, dict[str, Any]]":
    """Convenience wrapper for the one Phase-1-wired /chat path.

    Records that a conversational turn happened and who/what produced it,
    without asserting new intent/goals/epistemic claims -- carries the
    prior state's intent/goals/claims/contradictions/unknowns forward
    unchanged. Real intent/goal extraction and epistemic-ledger
    integration are Phase 2 work (see module docstring).
    """
    return advance_state(
        session_id=session_id,
        trigger_event="chat_turn",
        current_decision="respond",
        evidence_source_ids=evidence_source_ids,
        model_id=model_id,
        build_fingerprint=build_fingerprint,
        observations_used=[f"user_text_sha256:{sha256_text(user_text or '')}"],
        sources_used=evidence_source_ids,
        authority_result="not_applicable_read_only_turn",
        action_status="responded",
        db_path=db_path,
    )


def current_state_summary(*, scope: str = state_store.GLOBAL_SCOPE, db_path=None) -> "dict[str, Any] | None":
    """Read-only summary of the current state, for status surfaces (e.g. a
    future /api/cognitive-state endpoint). Never used to reconstruct or
    replay state -- state_store.load_current_state() is authoritative."""
    state = state_store.load_current_state(scope=scope, db_path=db_path)
    if state is None:
        return None
    return {
        "state_id": state.state_id,
        "parent_state_id": state.parent_state_id,
        "session_id": state.session_id,
        "updated_at": state.updated_at,
        "current_intent": state.current_intent,
        "active_goals": list(state.active_goals),
        "unknown_count": len(state.unknown_ids),
        "contradiction_count": len(state.contradiction_ids),
        "evidence_count": len(state.evidence_source_ids),
        "model_used": state.model_id,
        "state_hash": state.state_hash,
    }
