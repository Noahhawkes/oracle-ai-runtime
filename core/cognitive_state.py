"""ORACLE Cognitive State -- the single canonical schema for ORACLE's current
persistent cognitive state (Cognitive Spine v1, Phase 1).

This module owns the CognitiveState schema ONLY: construction, canonical
serialization, deterministic hashing, and parent-state lineage derivation.

It does not persist anything -- see core/state_store.py.
It does not decide when a transition happens -- see core/cognitive_spine.py.

CognitiveState stores REFERENCES (ids) into systems that remain the
authority for their own domain. It never duplicates their content:

  - epistemic_claim_ids / contradiction_ids / unknown_ids
        -> core/epistemic_ledger.py (claims, disputes, UNKNOWN status)
  - evidence_source_ids
        -> core/recall_orchestrator.py, core/memory.py (durable_facts)
  - capability_snapshot_id
        -> core/capability_broker.py (verified/degraded/blocked)
  - pending_action_ids
        -> core/action_candidates.py, core/pending_actions.py
  - recent_receipt_ids
        -> core/execution_receipt.py, core/sandbox_files.py, and friends

MODEL != CONTINUITY STATE: model_id records which reasoning model produced
the turn that led to this state, purely as a receipt field. It is never
read back to reconstruct behavior -- the state fields are.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from root import ROOT
except Exception:  # pragma: no cover
    ROOT = Path(__file__).resolve().parents[1]

SCHEMA_VERSION = "cognitive_state.v1"

# List-valued fields carry forward from the parent state unless the caller
# explicitly supplies a replacement value for that field.
_LIST_FIELDS = (
    "active_goals",
    "unresolved_questions",
    "epistemic_claim_ids",
    "contradiction_ids",
    "unknown_ids",
    "evidence_source_ids",
    "pending_action_ids",
    "recent_receipt_ids",
)

# Scalar fields that also carry forward from the parent unless overridden.
_CARRY_FORWARD_SCALAR_FIELDS = (
    "current_intent",
    "current_decision",
    "capability_snapshot_id",
    "model_id",
    "build_fingerprint",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_state_id() -> str:
    return f"cogstate_{uuid.uuid4().hex}"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def default_build_fingerprint() -> str:
    """Best-effort build identity. Read-only; never fails the caller."""
    try:
        from git_state_reader import read_git_snapshot

        snap = read_git_snapshot(ROOT) or {}
        head = snap.get("head") if isinstance(snap.get("head"), dict) else {}
        commit = (head.get("commit") if head else None) or snap.get("commit")
        if commit and commit != "UNKNOWN":
            return f"git:{commit}"
    except Exception:
        pass
    return "unknown_build"


@dataclass
class CognitiveState:
    state_id: str
    parent_state_id: str | None
    session_id: str
    created_at: str
    updated_at: str
    current_intent: str | None = None
    active_goals: list[str] = field(default_factory=list)
    unresolved_questions: list[str] = field(default_factory=list)
    epistemic_claim_ids: list[str] = field(default_factory=list)
    contradiction_ids: list[str] = field(default_factory=list)
    unknown_ids: list[str] = field(default_factory=list)
    evidence_source_ids: list[str] = field(default_factory=list)
    current_decision: str | None = None
    pending_action_ids: list[str] = field(default_factory=list)
    recent_receipt_ids: list[str] = field(default_factory=list)
    capability_snapshot_id: str | None = None
    model_id: str | None = None
    build_fingerprint: str | None = None
    schema_version: str = SCHEMA_VERSION
    state_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def compute_state_hash(self) -> str:
        payload = self.to_dict()
        payload.pop("state_hash", None)
        return sha256_text(canonical_json(payload))

    def verify_hash(self) -> bool:
        return bool(self.state_hash) and self.state_hash == self.compute_state_hash()

    def finalize(self) -> "CognitiveState":
        """Stamp the deterministic content hash. Call once, after all fields
        are set -- CognitiveState instances are immutable once finalized;
        a change is a new state_id (see derive_next_state), not a mutation."""
        self.state_hash = self.compute_state_hash()
        return self

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CognitiveState":
        known = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in dict(data or {}).items() if k in known}
        for list_field in _LIST_FIELDS:
            if list_field in filtered and filtered[list_field] is None:
                filtered[list_field] = []
        return cls(**filtered)


def new_root_state(*, session_id: str, **overrides: Any) -> CognitiveState:
    """Start a fresh lineage (no prior state exists yet, e.g. first-ever boot)."""
    now = utc_now_iso()
    fields: dict[str, Any] = {
        "state_id": new_state_id(),
        "parent_state_id": None,
        "session_id": str(session_id),
        "created_at": now,
        "updated_at": now,
    }
    fields.update({k: v for k, v in overrides.items() if v is not None})
    state = CognitiveState(**fields)
    return state.finalize()


def derive_next_state(prior: CognitiveState, *, session_id: str, **overrides: Any) -> CognitiveState:
    """Derive Psi(n+1) from Psi(n). Any field not present in overrides (or
    passed as None) carries forward from prior unchanged -- this is what
    lets ORACLE's state accumulate across turns/sessions/model-swaps
    instead of resetting each time. List fields passed explicitly REPLACE
    the prior list (callers own de-dup/merge decisions); omit them to carry
    the prior list forward untouched."""
    now = utc_now_iso()
    fields: dict[str, Any] = {
        "state_id": new_state_id(),
        "parent_state_id": prior.state_id,
        "session_id": str(session_id),
        "created_at": now,
        "updated_at": now,
    }
    for name in _LIST_FIELDS:
        if name in overrides and overrides[name] is not None:
            fields[name] = list(overrides[name])
        else:
            fields[name] = list(getattr(prior, name))
    for name in _CARRY_FORWARD_SCALAR_FIELDS:
        if name in overrides and overrides[name] is not None:
            fields[name] = overrides[name]
        else:
            fields[name] = getattr(prior, name)
    state = CognitiveState(**fields)
    return state.finalize()
