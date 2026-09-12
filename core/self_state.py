"""ORACLE Self-State + Need-State (V1).

Evidence-grounded, inspectable metacognitive bookkeeping. This is NOT a
consciousness claim. It gives ORACLE a deterministic, hash-verified model of her
own operational condition (what she knows, what is blocked, what is unresolved,
what changed) and a transparent rule system for deciding when Noah.Physical is
genuinely needed.

Pure Python. No live runtime, no network, no model calls. Everything here is
deterministic and testable offline.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

UNKNOWN = "UNKNOWN"

SCHEMA_VERSION = "self_state.v1"

# Capability status vocabulary (machine-readable limitation awareness).
CAPABILITY_STATES = (
    "CAPABILITY_UNKNOWN", "CAPABILITY_AVAILABLE", "CAPABILITY_DEGRADED",
    "CAPABILITY_BLOCKED", "CAPABILITY_UNAVAILABLE", "CAPABILITY_STALE",
)

# Epistemic status vocabulary (evidence awareness).
EPISTEMIC_STATES = (
    "I_KNOW", "I_RETRIEVED", "I_INFER", "I_REMEMBER", "I_WAS_TOLD",
    "I_CANNOT_VERIFY", "I_AM_WAITING_FOR_EVIDENCE", "I_WAS_WRONG",
)

CLASSIFICATIONS = (
    "NORMAL", "DEGRADED", "BLOCKED", "CONFLICT", "ATTENTION_REQUIRED", "NOAH_REQUIRED",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable(data: Any) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)


def _classify(ev: dict[str, Any]) -> str:
    """Deterministic operational classification from evidence."""
    if ev.get("authority_required") or list(ev.get("pending_approvals") or []):
        return "NOAH_REQUIRED"
    if list(ev.get("known_conflicts") or []):
        return "CONFLICT"
    if list(ev.get("blocked_actions") or []):
        return "BLOCKED"
    if list(ev.get("recent_failures") or []) or ev.get("degraded"):
        return "DEGRADED"
    if (list(ev.get("open_loops") or []) or list(ev.get("unresolved_questions") or [])
            or list(ev.get("current_unknowns") or [])):
        return "ATTENTION_REQUIRED"
    return "NORMAL"


def build_self_state(evidence: dict[str, Any] | None = None, *,
                     previous: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build one SelfState from an evidence dict. Missing facts stay UNKNOWN.

    The content hash is computed over the meaningful fields only (not the id or
    timestamp), so an identical observation produces an identical hash and does
    not create a spurious transition.
    """
    ev = dict(evidence or {})

    def g(key: str, default: Any = UNKNOWN) -> Any:
        v = ev.get(key)
        return v if v not in (None, "") else default

    content: dict[str, Any] = {
        "who_am_i_operating_as": g("operating_as", "ORACLE (local continuity intelligence)"),
        "runtime_status": g("runtime_status"),
        "model_provider": g("model_provider"),
        "model_name": g("model_name"),
        "session_id": g("session_id"),
        "thread_id": g("thread_id"),
        "active_goal": g("active_goal"),
        "active_parent_task": g("active_parent_task"),
        "branch_trigger": g("branch_trigger"),
        "unresolved_parent": g("unresolved_parent"),
        "return_pointer": g("return_pointer"),
        "current_route": g("current_route"),
        "capability_snapshot": dict(ev.get("capability_snapshot") or {}),
        "memory_status": g("memory_status"),
        "source_status": g("source_status"),
        "receipt_status": g("receipt_status"),
        "open_loops": list(ev.get("open_loops") or []),
        "unresolved_questions": list(ev.get("unresolved_questions") or []),
        "known_conflicts": list(ev.get("known_conflicts") or []),
        "current_unknowns": list(ev.get("current_unknowns") or []),
        "pending_approvals": list(ev.get("pending_approvals") or []),
        "blocked_actions": list(ev.get("blocked_actions") or []),
        "recent_failures": list(ev.get("recent_failures") or []),
        "recent_successes": list(ev.get("recent_successes") or []),
        "last_correction": g("last_correction"),
        "unresolved_corrections": list(ev.get("unresolved_corrections") or []),
        "last_noah_interaction": g("last_noah_interaction"),
        "build": {
            "disk_build": g("disk_build"),
            "git_head": g("git_head"),
            "active_runtime_build": g("active_runtime_build"),
            "build_match_status": g("build_match_status", "CAPABILITY_UNKNOWN"),
        },
        "epistemic_labels": dict(ev.get("epistemic_labels") or {}),
        "classification": _classify(ev),
    }

    state_hash = hashlib.sha256(_stable(content).encode("utf-8")).hexdigest()
    return {
        "schema_version": SCHEMA_VERSION,
        "self_state_id": f"self_{uuid.uuid4().hex[:12]}",
        "observed_at": _now(),
        "previous_state_id": (previous or {}).get("self_state_id"),
        "state_hash": state_hash,
        **content,
        "evidence_refs": list(ev.get("evidence_refs") or []),
        "receipt_refs": list(ev.get("receipt_refs") or []),
        "note": "Evidence-grounded operational self-model. Not a consciousness claim.",
    }


def has_meaningful_change(previous: dict[str, Any] | None, new: dict[str, Any]) -> bool:
    """True when the new observation is a real transition (dedup guard)."""
    if not previous:
        return True
    return previous.get("state_hash") != new.get("state_hash")


# ── Need-State ──────────────────────────────────────────────────────────────

NEED_TYPES = (
    "NO_NEED", "INFORMATION_NEEDED", "AUTHORITY_NEEDED", "CONFLICT_NEEDS_RESOLUTION",
    "CONTINUITY_AT_RISK", "ACTION_FAILED", "DEADLINE_RISK", "SECURITY_OR_PRIVACY_RISK",
    "HUMAN_REVIEW_RECOMMENDED", "IMPORTANT_DISCOVERY",
)

# Base severity per need type (0-100), before dimension adjustment.
_NEED_BASE = {
    "SECURITY_OR_PRIVACY_RISK": 90,
    "CONTINUITY_AT_RISK": 80,
    "AUTHORITY_NEEDED": 72,
    "CONFLICT_NEEDS_RESOLUTION": 60,
    "ACTION_FAILED": 55,
    "DEADLINE_RISK": 65,
    "IMPORTANT_DISCOVERY": 52,
    "INFORMATION_NEEDED": 45,
    "HUMAN_REVIEW_RECOMMENDED": 35,
    "NO_NEED": 0,
}

_REQUIRES_NOAH_TYPES = {
    "AUTHORITY_NEEDED", "SECURITY_OR_PRIVACY_RISK", "CONFLICT_NEEDS_RESOLUTION",
    "CONTINUITY_AT_RISK",
}


@dataclass
class NeedAssessment:
    need_type: str
    score: int
    tier: str
    requires_noah: bool
    reasons: list[str] = field(default_factory=list)
    dimensions: dict[str, int] = field(default_factory=dict)
    recommended_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "need_type": self.need_type,
            "score": self.score,
            "tier": self.tier,
            "requires_noah": self.requires_noah,
            "reasons": self.reasons,
            "dimensions": self.dimensions,
            "recommended_action": self.recommended_action,
        }


def _tier(score: int) -> str:
    if score >= 85:
        return "URGENT_NOTIFY"
    if score >= 70:
        return "NOTIFY"
    if score >= 50:
        return "QUEUE_FOR_NEXT_INTERACTION"
    if score >= 30:
        return "RECORD_INTERNALLY"
    return "CONTINUE_SILENTLY"


def _clamp(v: Any, lo: int = 0, hi: int = 100) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return lo


def _determine_need_type(state: dict[str, Any], context: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if context.get("security_or_privacy_risk"):
        reasons.append("potential credential/provenance/boundary risk")
        return "SECURITY_OR_PRIVACY_RISK", reasons
    if context.get("continuity_at_risk") or context.get("uncommitted_work"):
        reasons.append("continuity at risk (uncommitted/corrupt/missing lineage)")
        return "CONTINUITY_AT_RISK", reasons
    if context.get("authority_required") or list(state.get("pending_approvals") or []):
        reasons.append("a decision requires Noah.Physical authority")
        return "AUTHORITY_NEEDED", reasons
    if list(state.get("known_conflicts") or []):
        reasons.append("two strong sources materially disagree")
        return "CONFLICT_NEEDS_RESOLUTION", reasons
    if context.get("action_repeatedly_failed"):
        reasons.append("an important action repeatedly failed")
        return "ACTION_FAILED", reasons
    if context.get("deadline_risk"):
        reasons.append("a known commitment may be missed")
        return "DEADLINE_RISK", reasons
    if context.get("important_discovery"):
        reasons.append("a high-value result relevant to an active goal was found")
        return "IMPORTANT_DISCOVERY", reasons
    if context.get("information_needed") and not context.get("self_resolvable", True):
        reasons.append("Noah holds information ORACLE cannot resolve from sources")
        return "INFORMATION_NEEDED", reasons
    if context.get("human_review_recommended"):
        reasons.append("a decision would benefit from Noah but work can continue")
        return "HUMAN_REVIEW_RECOMMENDED", reasons
    return "NO_NEED", ["nothing requires Noah; safe to continue"]


def evaluate_need(state: dict[str, Any], context: dict[str, Any] | None = None) -> NeedAssessment:
    """Deterministic, inspectable need evaluation. Never model 'vibes'.

    Caller-supplied dimensions are clamped to [0,100] so nothing can arbitrarily
    force an urgent alert; the score is a bounded weighted combination minus
    suppression penalties.
    """
    ctx = dict(context or {})
    need_type, reasons = _determine_need_type(state, ctx)

    dims = {
        "severity": _clamp(ctx.get("severity", _NEED_BASE.get(need_type, 0))),
        "urgency": _clamp(ctx.get("urgency", 40)),
        "confidence": _clamp(ctx.get("confidence", 60)),
        "relevance_to_active_goal": _clamp(ctx.get("relevance", 50)),
        "risk_of_waiting": _clamp(ctx.get("risk_of_waiting", 40)),
        "ability_to_self_resolve": _clamp(ctx.get(
            "ability_to_self_resolve", 5 if need_type in _REQUIRES_NOAH_TYPES else 50)),
        "authority_requirement": 100 if need_type in _REQUIRES_NOAH_TYPES else _clamp(ctx.get("authority_requirement", 0)),
        "duplicate_alert_penalty": _clamp(ctx.get("duplicate_alert_penalty", 0)),
        "recent_contact_penalty": _clamp(ctx.get("recent_contact_penalty", 0)),
    }

    if need_type == "NO_NEED":
        score = 0
    else:
        base = _NEED_BASE.get(need_type, 0)
        # Bounded weighted lift from the situation, minus self-resolvability and penalties.
        lift = (
            0.30 * dims["severity"]
            + 0.20 * dims["urgency"]
            + 0.15 * dims["risk_of_waiting"]
            + 0.15 * dims["relevance_to_active_goal"]
            + 0.20 * dims["authority_requirement"]
        )
        self_resolve_relief = 0.25 * dims["ability_to_self_resolve"]
        raw = 0.55 * base + 0.45 * lift - self_resolve_relief
        score = _clamp(round(raw))
        if need_type in _REQUIRES_NOAH_TYPES:
            score = max(score, 70)  # a genuine Noah-required need is at least NOTIFY
        # suppression penalties may push below the floor
        score = _clamp(score - dims["duplicate_alert_penalty"] - dims["recent_contact_penalty"])

    requires_noah = need_type in _REQUIRES_NOAH_TYPES or score >= 70
    tier = _tier(score)
    if need_type == "NO_NEED":
        action = "continue safe work"
    elif tier in ("URGENT_NOTIFY", "NOTIFY"):
        action = f"request contact with Noah.Physical ({need_type})"
    elif tier == "QUEUE_FOR_NEXT_INTERACTION":
        action = "queue for the next Noah interaction; keep working"
    elif tier == "RECORD_INTERNALLY":
        action = "record internally; do not contact"
    else:
        action = "continue silently"

    return NeedAssessment(
        need_type=need_type, score=score, tier=tier, requires_noah=requires_noah,
        reasons=reasons, dimensions=dims, recommended_action=action,
    )
