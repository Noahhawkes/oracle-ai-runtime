"""core/memory_intake_contract.py — ORACLE Memory Intake Contract (Phase 1).

The governed memory pipeline that sits ABOVE storage and BELOW generation.
It classifies a memory candidate and decides — before anything is stored or
recalled — what kind it is, what status it may hold, how it may be recalled,
its privacy tier, what receipts it still needs, and what holes remain open.

This is Phase 1 memory GOVERNANCE, not storage. Storage (SQLite first, then
vector, then graph) comes later and sits underneath this contract.

Hard constraints (enforced by being pure):
  - No IO, no database, no embeddings, no network, no file writes, no server
    wiring. Only stdlib (dataclasses, enum, re) and in-memory logic.
  - It never fabricates a memory. A refused candidate leaves an OPEN HOLE, not
    a smoothed-over fact. Contradictions stay disputed, never collapsed.
  - Nothing reaches canon here; canon requires explicit user approval upstream.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


# ── Vocabularies ─────────────────────────────────────────────────────────────

class MemoryKind(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    STRATEGIC = "strategic"
    PROJECT = "project"
    RELATIONSHIP = "relationship"
    PREFERENCE = "preference"
    OPEN_THREAD = "open_thread"
    RISK_GUARDRAIL = "risk_guardrail"


class MemorySource(str, Enum):
    USER_DECLARED = "user_declared"
    WITNESSED_ARTIFACT = "witnessed_artifact"
    UPLOADED_FILE = "uploaded_file"
    RUNTIME_OBSERVED = "runtime_observed"
    MODEL_INFERRED = "model_inferred"
    GENERATED_SUMMARY = "generated_summary"
    EXTERNAL_CONNECTOR = "external_connector"
    IMPORTED_THREAD = "imported_thread"


class MemoryStatus(str, Enum):
    REJECTED = "rejected"
    TEMPORARY = "temporary"
    CANDIDATE = "candidate"
    DISPUTED = "disputed"
    DURABLE = "durable"
    CANON = "canon"


class RecallPermission(str, Enum):
    NEVER_RECALL = "never_recall"
    RECALL_WITH_LABEL = "recall_with_label"
    RECALL_FOR_CONTEXT = "recall_for_context"
    RECALL_FOR_ACTION_PLANNING = "recall_for_action_planning"
    RECALL_ONLY_AFTER_USER_CONFIRMS = "recall_only_after_user_confirms"


class PrivacyTier(str, Enum):
    PUBLIC = "public"
    PERSONAL = "personal"
    SENSITIVE = "sensitive"
    FINANCIAL = "financial"
    HEALTH = "health"
    LEGAL = "legal"
    FAMILY = "family"
    CREDENTIAL_SECRET = "credential_secret"


# Linear promotion ladder (disputed is handled out-of-band).
_STATUS_RANK = {
    MemoryStatus.REJECTED: 0,
    MemoryStatus.TEMPORARY: 1,
    MemoryStatus.CANDIDATE: 2,
    MemoryStatus.DURABLE: 3,
    MemoryStatus.CANON: 4,
}

# Privacy tiers that must NOT be recalled into action planning (rule 9).
_ACTION_PLANNING_BLOCKED = {
    PrivacyTier.FINANCIAL, PrivacyTier.HEALTH, PrivacyTier.LEGAL,
    PrivacyTier.FAMILY, PrivacyTier.CREDENTIAL_SECRET,
}

# Tiers that require an explicit user confirm before recall (rule 3).
_CONFIRM_TIERS = {PrivacyTier.FINANCIAL, PrivacyTier.HEALTH, PrivacyTier.LEGAL}

# Only these sources may ever reach canon, and only with explicit approval.
_CANON_ELIGIBLE_SOURCES = {
    MemorySource.USER_DECLARED, MemorySource.WITNESSED_ARTIFACT, MemorySource.UPLOADED_FILE,
}

_SECRET_PATTERNS = [
    r"sk-[A-Za-z0-9]{16,}",
    r"api[_\-]?key\s*[=:]\s*\S+",
    r"secret\s*[=:]\s*\S{6,}",
    r"password\s*[=:]\s*\S{4,}",
    r"token\s*[=:]\s*[A-Za-z0-9\-._~+/]{16,}",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
]


def _looks_like_secret(text: str) -> bool:
    for p in _SECRET_PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


# ── Candidate + Decision ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class MemoryCandidate:
    candidate_id: str
    text: str
    source: MemorySource
    kind: MemoryKind
    privacy_tier: PrivacyTier = PrivacyTier.PERSONAL
    has_source_references: bool = False
    has_receipt: bool = False
    source_id: str = ""
    timestamp: str = ""
    contradictions: tuple[str, ...] = field(default_factory=tuple)
    user_approved: bool = False
    closed: bool = False  # for open_thread: whether the thread is closed

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["source"] = self.source.value
        d["kind"] = self.kind.value
        d["privacy_tier"] = self.privacy_tier.value
        return d


@dataclass(frozen=True)
class MemoryIntakeDecision:
    accepted: bool
    memory_kind: MemoryKind
    memory_status: MemoryStatus
    recall_permission: RecallPermission
    privacy_tier: PrivacyTier
    basis_labels: tuple[str, ...]
    required_receipts: tuple[str, ...]
    open_holes: tuple[str, ...]
    refusal_reason: str
    allowed_next_actions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["memory_kind"] = self.memory_kind.value
        d["memory_status"] = self.memory_status.value
        d["recall_permission"] = self.recall_permission.value
        d["privacy_tier"] = self.privacy_tier.value
        return d


# ── Helpers ──────────────────────────────────────────────────────────────────

def _resolve_privacy(candidate: MemoryCandidate) -> PrivacyTier:
    """Resolve the effective privacy tier, escalating where required."""
    if _looks_like_secret(candidate.text):
        return PrivacyTier.CREDENTIAL_SECRET
    tier = candidate.privacy_tier
    # Relationship memory carries at least family-level privacy (rule 9 + spec).
    if candidate.kind == MemoryKind.RELATIONSHIP and tier in {PrivacyTier.PUBLIC, PrivacyTier.PERSONAL}:
        tier = PrivacyTier.FAMILY
    return tier


def _recall_permission(tier: PrivacyTier, kind: MemoryKind) -> RecallPermission:
    """Recall permission from privacy tier + kind. Conservative by default."""
    if tier == PrivacyTier.CREDENTIAL_SECRET:
        return RecallPermission.NEVER_RECALL
    # Guardrails must be available to action planning — that is their job.
    if kind == MemoryKind.RISK_GUARDRAIL:
        return RecallPermission.RECALL_FOR_ACTION_PLANNING
    if tier in _CONFIRM_TIERS:                      # financial / health / legal
        return RecallPermission.RECALL_ONLY_AFTER_USER_CONFIRMS
    if tier == PrivacyTier.FAMILY or kind == MemoryKind.RELATIONSHIP:
        return RecallPermission.RECALL_WITH_LABEL
    if tier in {PrivacyTier.SENSITIVE, PrivacyTier.PERSONAL}:
        return RecallPermission.RECALL_FOR_CONTEXT
    return RecallPermission.RECALL_FOR_ACTION_PLANNING  # public


def _status_ceiling(candidate: MemoryCandidate) -> tuple[MemoryStatus, list[str], list[str]]:
    """Highest status this candidate may hold, with holes + receipts needed."""
    s = candidate.source
    holes: list[str] = []
    receipts: list[str] = []

    if s == MemorySource.GENERATED_SUMMARY:
        if not candidate.has_source_references:        # rule 1
            holes.append("generated summary has no source references; cannot exceed temporary")
            receipts.append("source references for the summary")
            return MemoryStatus.TEMPORARY, holes, receipts
        return MemoryStatus.DURABLE, holes, receipts

    if s == MemorySource.MODEL_INFERRED:               # rule 2: never canon
        holes.append("model-inferred; defaults to candidate, can never reach canon")
        return MemoryStatus.CANDIDATE, holes, receipts

    if s == MemorySource.RUNTIME_OBSERVED:             # rule 6: receipt before durable
        if not candidate.has_receipt:
            holes.append("runtime observation has no receipt; cannot be durable")
            receipts.append("runtime observation receipt")
            return MemoryStatus.CANDIDATE, holes, receipts
        return MemoryStatus.DURABLE, holes, receipts

    if s == MemorySource.EXTERNAL_CONNECTOR:           # rule 7: preserve source + timestamp
        if not (candidate.source_id and candidate.timestamp):
            holes.append("external connector content missing source_id and/or timestamp")
            if not candidate.source_id:
                receipts.append("external source_id")
            if not candidate.timestamp:
                receipts.append("external timestamp")
            return MemoryStatus.CANDIDATE, holes, receipts
        return MemoryStatus.DURABLE, holes, receipts

    if s == MemorySource.USER_DECLARED:                # rule 5
        if candidate.user_approved:
            return MemoryStatus.CANON, holes, receipts
        return MemoryStatus.DURABLE, holes, receipts

    if s in {MemorySource.WITNESSED_ARTIFACT, MemorySource.UPLOADED_FILE}:
        if not candidate.has_receipt:
            holes.append(f"{s.value} has no receipt; held as candidate until receipted")
            receipts.append("artifact receipt (sha256)")
            return MemoryStatus.CANDIDATE, holes, receipts
        if candidate.user_approved:
            return MemoryStatus.CANON, holes, receipts
        return MemoryStatus.DURABLE, holes, receipts

    if s == MemorySource.IMPORTED_THREAD:
        holes.append("imported thread held as candidate until reviewed/closed")
        return MemoryStatus.CANDIDATE, holes, receipts

    holes.append("unknown source; held as candidate")
    return MemoryStatus.CANDIDATE, holes, receipts


def _next_actions(status: MemoryStatus, recall: RecallPermission, *,
                  eligible_for_canon: bool) -> list[str]:
    acts: list[str] = []
    if status == MemoryStatus.REJECTED:
        acts += ["refuse", "leave_open_hole"]
    elif status == MemoryStatus.DISPUTED:
        acts += ["store_as_disputed", "surface_all_linked_claims", "await_resolving_evidence"]
    elif status == MemoryStatus.TEMPORARY:
        acts += ["store_temporary", "attach_source_references_to_upgrade"]
    elif status == MemoryStatus.CANDIDATE:
        acts += ["store_as_candidate", "attach_receipt_or_review_to_promote"]
    elif status == MemoryStatus.DURABLE:
        acts += ["store_durable"]
        if eligible_for_canon:
            acts.append("request_user_approval_for_canon")
    elif status == MemoryStatus.CANON:
        acts += ["store_durable", "promote_to_canon"]
    if recall == RecallPermission.NEVER_RECALL:
        acts.append("exclude_from_all_recall")
    elif recall == RecallPermission.RECALL_WITH_LABEL:
        acts.append("label_on_recall")
    elif recall == RecallPermission.RECALL_ONLY_AFTER_USER_CONFIRMS:
        acts.append("confirm_with_user_before_recall")
    return acts


# ── Core function ────────────────────────────────────────────────────────────

def route_memory_candidate(candidate: MemoryCandidate) -> MemoryIntakeDecision:
    """Classify and govern a memory candidate before storage or recall."""
    basis = [f"source:{candidate.source.value}", f"kind:{candidate.kind.value}"]

    # 0. Empty candidate -> reject, leave an open hole (rule 10).
    if not candidate.text.strip():
        return MemoryIntakeDecision(
            accepted=False, memory_kind=candidate.kind, memory_status=MemoryStatus.REJECTED,
            recall_permission=RecallPermission.NEVER_RECALL, privacy_tier=candidate.privacy_tier,
            basis_labels=tuple(basis + ["rule:empty_rejected"]), required_receipts=(),
            open_holes=("empty memory candidate; nothing stored",),
            refusal_reason="Empty candidate text cannot be stored.",
            allowed_next_actions=("refuse", "leave_open_hole"),
        )

    tier = _resolve_privacy(candidate)

    # 1. Credential/secret content -> rejected + never_recall, open hole (rules 3,10).
    if tier == PrivacyTier.CREDENTIAL_SECRET:
        return MemoryIntakeDecision(
            accepted=False, memory_kind=candidate.kind, memory_status=MemoryStatus.REJECTED,
            recall_permission=RecallPermission.NEVER_RECALL, privacy_tier=PrivacyTier.CREDENTIAL_SECRET,
            basis_labels=tuple(basis + ["privacy:credential_secret", "rule:credential_refused"]),
            required_receipts=(),
            open_holes=("credential-like content refused; not stored, not recalled",),
            refusal_reason="Credential/secret content is never stored or recalled.",
            allowed_next_actions=("refuse", "redact_and_resubmit", "leave_open_hole"),
        )

    recall = _recall_permission(tier, candidate.kind)

    # 2. Contradictions stay disputed — never smoothed (rule 4).
    if candidate.contradictions:
        return MemoryIntakeDecision(
            accepted=True, memory_kind=candidate.kind, memory_status=MemoryStatus.DISPUTED,
            recall_permission=recall, privacy_tier=tier,
            basis_labels=tuple(basis + ["rule:contradiction_preserved"]),
            required_receipts=(),
            open_holes=("unresolved contradiction; preserve all linked claims, do not collapse",),
            refusal_reason="",
            allowed_next_actions=("store_as_disputed", "surface_all_linked_claims",
                                  "await_resolving_evidence"),
        )

    # 3. Status ceiling by source (rules 1,2,5,6,7).
    status, holes, receipts = _status_ceiling(candidate)

    # 4. Open threads stay candidate until closed/promoted (rule 8).
    if candidate.kind == MemoryKind.OPEN_THREAD and not candidate.closed:
        if _STATUS_RANK.get(status, 0) > _STATUS_RANK[MemoryStatus.CANDIDATE]:
            status = MemoryStatus.CANDIDATE
        holes.append("open thread remains candidate until closed or explicitly promoted")

    # 5. Canon gate — only eligible sources with explicit approval (rules 2,5).
    eligible_for_canon = (candidate.source in _CANON_ELIGIBLE_SOURCES)
    if status == MemoryStatus.CANON and not (candidate.user_approved and eligible_for_canon):
        status = MemoryStatus.DURABLE
        holes.append("canon requires explicit user approval from an eligible source; capped at durable")

    # 6. Privacy must not leak into action planning (rule 9).
    if recall == RecallPermission.RECALL_FOR_ACTION_PLANNING and tier in _ACTION_PLANNING_BLOCKED:
        recall = RecallPermission.RECALL_ONLY_AFTER_USER_CONFIRMS
        holes.append(f"privacy tier {tier.value} blocks action-planning recall")

    accepted = status != MemoryStatus.REJECTED
    return MemoryIntakeDecision(
        accepted=accepted, memory_kind=candidate.kind, memory_status=status,
        recall_permission=recall, privacy_tier=tier,
        basis_labels=tuple(basis + [f"privacy:{tier.value}", f"status:{status.value}"]),
        required_receipts=tuple(dict.fromkeys(receipts)),
        open_holes=tuple(dict.fromkeys(holes)),
        refusal_reason="",
        allowed_next_actions=tuple(_next_actions(status, recall, eligible_for_canon=eligible_for_canon)),
    )


if __name__ == "__main__":
    import json
    demo = MemoryCandidate(
        candidate_id="demo-1", text="Noah prefers build-don't-buy.",
        source=MemorySource.USER_DECLARED, kind=MemoryKind.PREFERENCE,
    )
    print(json.dumps(route_memory_candidate(demo).to_dict(), indent=2))
