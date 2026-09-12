"""Deterministic Continuity Merge Engine (CME).

CME is a governed conversation version-control core. It turns multiple
conversation streams into normalized events, candidate claims, conflicts,
review actions, and current-state projections without promoting canon or
modifying source records.

Milestone 1 is intentionally pure: no IO, no database, no network, no model
calls, and no runtime/server wiring. Callers own storage and approval flows.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "continuity_merge_engine.v1"

NO_CANON_PROMOTION = "not_promoted"
CANON_CANDIDATE = "candidate"
NOAH_AUTHORITY = "Noah.Physical"


class EvidenceClass(str, Enum):
    HUMAN_DECLARED = "human_declared"
    MACHINE_OBSERVED = "machine_observed"
    UPLOADED_SOURCE = "uploaded_source"
    ASSISTANT_GENERATED = "assistant_generated"
    TOOL_OUTPUT = "tool_output"
    IMPORTED_SUMMARY = "imported_summary"
    INFERENCE = "inference"
    UNKNOWN = "unknown"


class ClaimType(str, Enum):
    FACT = "fact"
    PREFERENCE = "preference"
    CORRECTION = "correction"
    DECISION = "decision"
    TASK = "task"
    RELATIONSHIP = "relationship"
    PROJECT_STATE = "project_state"
    UNKNOWN = "unknown"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"
    DEFERRED = "deferred"


class DiffKind(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    CORRECTED = "corrected"
    SUPERSEDED = "superseded"
    CHANGED_AUTHORITY = "changed_authority"
    CHANGED_CANON = "changed_canon"
    CHANGED_EVIDENCE = "changed_evidence"


@dataclass(frozen=True)
class ConversationMessage:
    thread_id: str
    message_id: str
    timestamp: str
    speaker: str
    role: str
    content: str
    attachments: tuple[str, ...] = field(default_factory=tuple)
    quoted_text: str = ""
    tool_output: str = ""
    imported_summary: str = ""
    source_ref: str = ""


@dataclass(frozen=True)
class ConversationBatch:
    thread_id: str
    messages: tuple[ConversationMessage | Mapping[str, Any], ...]
    source_system: str = "unknown"
    source_ref: str = ""


@dataclass
class ContinuityEvent:
    event_id: str
    thread_id: str
    message_id: str
    timestamp: str
    ordinal: int
    speaker: str
    role: str
    content: str
    content_sha256: str
    evidence_class: EvidenceClass
    attachments: tuple[str, ...] = field(default_factory=tuple)
    quoted_text: str = ""
    tool_output: str = ""
    imported_summary: str = ""
    source_ref: str = ""
    canon_status: str = CANON_CANDIDATE
    promotion_status: str = NO_CANON_PROMOTION


@dataclass
class ContinuityClaim:
    claim_id: str
    claim_type: ClaimType
    claim_text: str
    normalized_key: str
    source_event_ids: tuple[str, ...]
    thread_ids: tuple[str, ...]
    evidence_class: EvidenceClass
    confidence: float
    provenance: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    review_status: ReviewStatus = ReviewStatus.PENDING
    canon_status: str = CANON_CANDIDATE
    promotion_status: str = NO_CANON_PROMOTION
    approved_by: str = ""
    reviewed_by: str = ""
    supersedes: tuple[str, ...] = field(default_factory=tuple)
    superseded_by: tuple[str, ...] = field(default_factory=tuple)
    contradicts: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DuplicateRecord:
    duplicate_id: str
    normalized_key: str
    primary_claim_id: str
    duplicate_claim_ids: tuple[str, ...]
    reason: str = "exact_or_key_duplicate"


@dataclass(frozen=True)
class ConflictRecord:
    conflict_id: str
    normalized_key: str
    claim_ids: tuple[str, ...]
    evidence_classes: tuple[str, ...]
    status: str = "requires_review"
    resolution: str = "unresolved"


@dataclass(frozen=True)
class DiffRecord:
    diff_id: str
    kind: DiffKind
    claim_id: str
    normalized_key: str
    detail: str


@dataclass(frozen=True)
class ReviewDecision:
    decision_id: str
    claim_id: str
    action: ReviewStatus
    reviewed_by: str
    canon_promoted: bool
    promotion_status: str
    edited_text: str = ""


@dataclass(frozen=True)
class MergeReceipt:
    schema_version: str
    operation: str
    source_thread_ids: tuple[str, ...]
    event_count: int
    claim_count: int
    duplicate_count: int
    conflict_count: int
    merged_at: str
    canon_promoted: bool
    external_action: bool
    raw_records_mutated: bool
    history_destroyed: bool
    deterministic_core: bool
    receipt_hash_sha256: str


@dataclass(frozen=True)
class MergeResult:
    schema_version: str
    events: tuple[ContinuityEvent, ...]
    claims: tuple[ContinuityClaim, ...]
    duplicates: tuple[DuplicateRecord, ...]
    conflicts: tuple[ConflictRecord, ...]
    current_state: dict[str, Any]
    diff: dict[str, tuple[DiffRecord, ...]]
    review_queue: tuple[str, ...]
    receipt: MergeReceipt

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(self)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_text(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def canonical_text(text: str) -> str:
    lowered = str(text or "").casefold()
    lowered = re.sub(r"[^a-z0-9_:\-./ ]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _stable_id(prefix: str, *parts: Any, length: int = 16) -> str:
    material = json.dumps([str(p) for p in parts], sort_keys=True, ensure_ascii=True)
    return f"{prefix}_{sha256_text(material)[:length]}"


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None or value == "":
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(str(item) for item in value)
    return (str(value),)


def _message_from_mapping(
    thread_id: str,
    raw: ConversationMessage | Mapping[str, Any],
    ordinal: int,
    source_ref: str,
) -> ConversationMessage:
    if isinstance(raw, ConversationMessage):
        return raw
    if not isinstance(raw, Mapping):
        raise TypeError(f"Conversation message {ordinal} must be a mapping or ConversationMessage")
    content = str(raw.get("content") or raw.get("message_text") or raw.get("text") or "")
    message_id = str(raw.get("message_id") or raw.get("id") or ordinal)
    return ConversationMessage(
        thread_id=str(raw.get("thread_id") or thread_id),
        message_id=message_id,
        timestamp=str(raw.get("timestamp") or raw.get("created_at") or "UNKNOWN"),
        speaker=str(raw.get("speaker") or raw.get("author") or raw.get("role") or "unknown"),
        role=str(raw.get("role") or raw.get("speaker") or "unknown"),
        content=content,
        attachments=_as_tuple(raw.get("attachments")),
        quoted_text=str(raw.get("quoted_text") or ""),
        tool_output=str(raw.get("tool_output") or ""),
        imported_summary=str(raw.get("imported_summary") or ""),
        source_ref=str(raw.get("source_ref") or source_ref),
    )


def evidence_for_message(message: ConversationMessage) -> EvidenceClass:
    role = canonical_text(message.role)
    speaker = canonical_text(message.speaker)
    if message.tool_output:
        return EvidenceClass.TOOL_OUTPUT
    if message.imported_summary:
        return EvidenceClass.IMPORTED_SUMMARY
    if message.attachments and role in {"user", "human", "noah", "noah.physical"}:
        return EvidenceClass.UPLOADED_SOURCE
    if role in {"user", "human", "noah", "noah.physical"} or speaker in {
        "noah",
        "noah.physical",
        "noah physical",
    }:
        return EvidenceClass.HUMAN_DECLARED
    if role in {"assistant", "model", "ai", "oracle"} or speaker in {
        "assistant",
        "chatgpt",
        "claude",
        "gemini",
        "grok",
        "copilot",
        "oracle",
        "meta",
        "meta ai",
    }:
        return EvidenceClass.ASSISTANT_GENERATED
    if role == "tool":
        return EvidenceClass.TOOL_OUTPUT
    return EvidenceClass.UNKNOWN


def normalize_conversation(batch: ConversationBatch | Mapping[str, Any]) -> tuple[ContinuityEvent, ...]:
    """Normalize one conversation batch into immutable event-shaped records."""
    if isinstance(batch, Mapping):
        thread_id = str(batch.get("thread_id") or batch.get("id") or "unknown_thread")
        messages = tuple(batch.get("messages") or ())
        source_ref = str(batch.get("source_ref") or "")
    else:
        thread_id = batch.thread_id
        messages = batch.messages
        source_ref = batch.source_ref

    events: list[ContinuityEvent] = []
    for ordinal, raw_message in enumerate(messages, start=1):
        message = _message_from_mapping(thread_id, raw_message, ordinal, source_ref)
        digest = sha256_text(message.content)
        event_id = _stable_id(
            "cme_evt",
            message.thread_id,
            message.message_id,
            message.timestamp,
            message.speaker,
            digest,
        )
        events.append(
            ContinuityEvent(
                event_id=event_id,
                thread_id=message.thread_id,
                message_id=message.message_id,
                timestamp=message.timestamp,
                ordinal=ordinal,
                speaker=message.speaker,
                role=message.role,
                content=message.content,
                content_sha256=digest,
                evidence_class=evidence_for_message(message),
                attachments=message.attachments,
                quoted_text=message.quoted_text,
                tool_output=message.tool_output,
                imported_summary=message.imported_summary,
                source_ref=message.source_ref,
            )
        )
    return tuple(events)


_CLAIM_RE = re.compile(
    r"^(?P<kind>FACT|PREFERENCE|CORRECTION|DECISION|TASK|RELATIONSHIP|PROJECT_STATE)"
    r"\s*(?:\[(?P<key>[^\]]+)\])?\s*:\s*(?P<value>.+)$",
    re.IGNORECASE,
)


_HEURISTIC_PREFIXES: tuple[tuple[ClaimType, str], ...] = (
    (ClaimType.PREFERENCE, "preference:"),
    (ClaimType.DECISION, "decision:"),
    (ClaimType.TASK, "task:"),
    (ClaimType.PROJECT_STATE, "status:"),
    (ClaimType.FACT, "fact:"),
)


def _claim_type(kind: str) -> ClaimType:
    normalized = canonical_text(kind).replace("-", "_")
    if normalized == "project_state":
        return ClaimType.PROJECT_STATE
    try:
        return ClaimType(normalized)
    except ValueError:
        return ClaimType.UNKNOWN


def _claim_key(claim_type: ClaimType, key: str, value: str) -> str:
    if key:
        return canonical_text(key)
    if claim_type == ClaimType.CORRECTION:
        left = value.split("->", 1)[0] if "->" in value else value
        return canonical_text(left)[:96] or "unknown_correction"
    words = canonical_text(value).split()
    return f"{claim_type.value}:{' '.join(words[:12])}"


def _claim_confidence(evidence_class: EvidenceClass) -> float:
    return {
        EvidenceClass.HUMAN_DECLARED: 0.8,
        EvidenceClass.MACHINE_OBSERVED: 0.8,
        EvidenceClass.UPLOADED_SOURCE: 0.75,
        EvidenceClass.TOOL_OUTPUT: 0.75,
        EvidenceClass.IMPORTED_SUMMARY: 0.35,
        EvidenceClass.ASSISTANT_GENERATED: 0.25,
        EvidenceClass.INFERENCE: 0.2,
        EvidenceClass.UNKNOWN: 0.1,
    }[evidence_class]


def _task_status(value: str) -> str:
    text = canonical_text(value)
    if re.search(r"\b(done|complete|completed|closed|shipped|verified)\b", text):
        return "completed"
    if re.search(r"\b(blocked|stuck|waiting)\b", text):
        return "blocked"
    return "open"


def _extract_tagged_claim(event: ContinuityEvent, line: str) -> ContinuityClaim | None:
    match = _CLAIM_RE.match(line.strip())
    if not match:
        return None
    claim_type = _claim_type(match.group("kind"))
    key = str(match.group("key") or "")
    value = match.group("value").strip()
    normalized_key = _claim_key(claim_type, key, value)
    metadata: dict[str, Any] = {"explicit_key": key}
    if claim_type == ClaimType.TASK:
        metadata["task_status"] = _task_status(value)
    if claim_type == ClaimType.CORRECTION:
        if "->" in value:
            old_value, new_value = [part.strip() for part in value.split("->", 1)]
            metadata["old_value"] = old_value
            metadata["new_value"] = new_value
        metadata["correction_statement"] = value

    claim_id = _stable_id(
        "cme_claim",
        event.event_id,
        claim_type.value,
        normalized_key,
        value,
    )
    return ContinuityClaim(
        claim_id=claim_id,
        claim_type=claim_type,
        claim_text=value,
        normalized_key=normalized_key,
        source_event_ids=(event.event_id,),
        thread_ids=(event.thread_id,),
        evidence_class=event.evidence_class,
        confidence=_claim_confidence(event.evidence_class),
        provenance={
            "thread_id": event.thread_id,
            "message_id": event.message_id,
            "timestamp": event.timestamp,
            "speaker": event.speaker,
            "source_ref": event.source_ref,
        },
        metadata=metadata,
    )


def _extract_heuristic_claim(event: ContinuityEvent, line: str) -> ContinuityClaim | None:
    stripped = line.strip()
    lower = stripped.casefold()
    for claim_type, prefix in _HEURISTIC_PREFIXES:
        if lower.startswith(prefix):
            value = stripped[len(prefix) :].strip()
            if not value:
                return None
            normalized_key = _claim_key(claim_type, "", value)
            claim_id = _stable_id("cme_claim", event.event_id, claim_type.value, normalized_key, value)
            metadata = {"heuristic": True}
            if claim_type == ClaimType.TASK:
                metadata["task_status"] = _task_status(value)
            return ContinuityClaim(
                claim_id=claim_id,
                claim_type=claim_type,
                claim_text=value,
                normalized_key=normalized_key,
                source_event_ids=(event.event_id,),
                thread_ids=(event.thread_id,),
                evidence_class=event.evidence_class,
                confidence=_claim_confidence(event.evidence_class),
                provenance={
                    "thread_id": event.thread_id,
                    "message_id": event.message_id,
                    "timestamp": event.timestamp,
                    "speaker": event.speaker,
                    "source_ref": event.source_ref,
                },
                metadata=metadata,
            )
    return None


def extract_claims(events: Sequence[ContinuityEvent]) -> tuple[ContinuityClaim, ...]:
    """Extract deterministic candidate claims from normalized events.

    The extractor favors explicit tags, for example:
    FACT[oracle_port]: ORACLE listens on 7781.
    CORRECTION[oracle_port]: 7777 -> 7781.

    Untagged model prose is not treated as high-authority evidence.
    """
    claims: list[ContinuityClaim] = []
    for event in events:
        for line in event.content.splitlines():
            if not line.strip():
                continue
            claim = _extract_tagged_claim(event, line) or _extract_heuristic_claim(event, line)
            if claim is not None:
                claims.append(claim)
    return tuple(claims)


def apply_corrections(claims: Sequence[ContinuityClaim]) -> tuple[ContinuityClaim, ...]:
    """Mark older same-key claims as superseded by correction claims."""
    ordered = list(claims)
    prior_by_key: dict[str, list[ContinuityClaim]] = {}
    for claim in ordered:
        if claim.claim_type == ClaimType.CORRECTION:
            prior = [
                item
                for item in prior_by_key.get(claim.normalized_key, [])
                if item.claim_type != ClaimType.CORRECTION and claim.claim_id not in item.superseded_by
            ]
            if prior:
                claim.supersedes = tuple(item.claim_id for item in prior)
                for old_claim in prior:
                    old_claim.superseded_by = tuple(sorted(set(old_claim.superseded_by + (claim.claim_id,))))
        prior_by_key.setdefault(claim.normalized_key, []).append(claim)
    return tuple(ordered)


def find_duplicates(claims: Sequence[ContinuityClaim]) -> tuple[DuplicateRecord, ...]:
    buckets: dict[tuple[str, str], list[ContinuityClaim]] = {}
    for claim in claims:
        exact_key = (claim.normalized_key, canonical_text(claim.claim_text))
        buckets.setdefault(exact_key, []).append(claim)
    duplicates: list[DuplicateRecord] = []
    for (normalized_key, _), items in sorted(buckets.items(), key=lambda item: item[0]):
        if len(items) < 2:
            continue
        primary = sorted(items, key=lambda claim: claim.claim_id)[0]
        duplicate_ids = tuple(sorted(claim.claim_id for claim in items if claim.claim_id != primary.claim_id))
        duplicates.append(
            DuplicateRecord(
                duplicate_id=_stable_id("cme_dup", normalized_key, primary.claim_id, *duplicate_ids),
                normalized_key=normalized_key,
                primary_claim_id=primary.claim_id,
                duplicate_claim_ids=duplicate_ids,
            )
        )
    return tuple(duplicates)


def detect_conflicts(claims: Sequence[ContinuityClaim]) -> tuple[ConflictRecord, ...]:
    active: dict[str, list[ContinuityClaim]] = {}
    for claim in claims:
        if claim.claim_type == ClaimType.CORRECTION or claim.superseded_by:
            continue
        active.setdefault(claim.normalized_key, []).append(claim)

    conflicts: list[ConflictRecord] = []
    for normalized_key, items in sorted(active.items()):
        distinct_texts = {canonical_text(item.claim_text) for item in items}
        if len(distinct_texts) < 2:
            continue
        claim_ids = tuple(sorted(item.claim_id for item in items))
        conflict_id = _stable_id("cme_conflict", normalized_key, *claim_ids)
        for item in items:
            item.contradicts = tuple(cid for cid in claim_ids if cid != item.claim_id)
        conflicts.append(
            ConflictRecord(
                conflict_id=conflict_id,
                normalized_key=normalized_key,
                claim_ids=claim_ids,
                evidence_classes=tuple(sorted({item.evidence_class.value for item in items})),
            )
        )
    return tuple(conflicts)


def _claim_summary(claim: ContinuityClaim) -> dict[str, Any]:
    return {
        "claim_id": claim.claim_id,
        "text": claim.claim_text,
        "key": claim.normalized_key,
        "evidence_class": claim.evidence_class.value,
        "confidence": claim.confidence,
        "review_status": claim.review_status.value,
        "canon_status": claim.canon_status,
        "promotion_status": claim.promotion_status,
        "source_event_ids": claim.source_event_ids,
        "superseded_by": claim.superseded_by,
    }


def generate_current_state(
    claims: Sequence[ContinuityClaim],
    conflicts: Sequence[ConflictRecord],
) -> dict[str, Any]:
    conflict_claim_ids = {claim_id for conflict in conflicts for claim_id in conflict.claim_ids}
    deprecated = [claim for claim in claims if claim.superseded_by]
    active = [
        claim
        for claim in claims
        if not claim.superseded_by
        and claim.claim_id not in conflict_claim_ids
        and claim.review_status != ReviewStatus.REJECTED
    ]

    def by_type(kind: ClaimType) -> list[dict[str, Any]]:
        return [_claim_summary(claim) for claim in active if claim.claim_type == kind]

    tasks = [claim for claim in active if claim.claim_type == ClaimType.TASK]
    completed_tasks = [
        _claim_summary(claim) for claim in tasks if claim.metadata.get("task_status") == "completed"
    ]
    open_tasks = [
        _claim_summary(claim) for claim in tasks if claim.metadata.get("task_status") != "completed"
    ]

    timeline = sorted(
        (
            {
                "timestamp": claim.provenance.get("timestamp", "UNKNOWN"),
                "claim_id": claim.claim_id,
                "claim_type": claim.claim_type.value,
                "thread_id": claim.provenance.get("thread_id", ""),
            }
            for claim in claims
        ),
        key=lambda row: (row["timestamp"], row["thread_id"], row["claim_id"]),
    )

    return {
        "current_facts": by_type(ClaimType.FACT),
        "current_projects": by_type(ClaimType.PROJECT_STATE),
        "open_tasks": open_tasks,
        "completed_tasks": completed_tasks,
        "active_decisions": by_type(ClaimType.DECISION),
        "relationship_context": by_type(ClaimType.RELATIONSHIP),
        "preferences": by_type(ClaimType.PREFERENCE),
        "deprecated_claims": [_claim_summary(claim) for claim in deprecated],
        "conflicts": [_jsonable(conflict) for conflict in conflicts],
        "timeline": timeline,
        "receipts": {
            "claim_count": len(claims),
            "conflict_count": len(conflicts),
            "canon_promoted": False,
            "promotion_status": NO_CANON_PROMOTION,
        },
    }


def conversation_diff(
    base_claims: Sequence[ContinuityClaim],
    merged_claims: Sequence[ContinuityClaim],
) -> dict[str, tuple[DiffRecord, ...]]:
    base_by_id = {claim.claim_id: claim for claim in base_claims}
    merged_by_id = {claim.claim_id: claim for claim in merged_claims}
    records: dict[DiffKind, list[DiffRecord]] = {kind: [] for kind in DiffKind}

    for claim in merged_claims:
        base = base_by_id.get(claim.claim_id)
        if base is None:
            records[DiffKind.ADDED].append(
                _diff_record(DiffKind.ADDED, claim, "claim added to merged candidate state")
            )
            if claim.claim_type == ClaimType.CORRECTION:
                records[DiffKind.CORRECTED].append(
                    _diff_record(DiffKind.CORRECTED, claim, "correction claim added")
                )
        else:
            if base.review_status != claim.review_status or base.approved_by != claim.approved_by:
                records[DiffKind.CHANGED_AUTHORITY].append(
                    _diff_record(DiffKind.CHANGED_AUTHORITY, claim, "review authority changed")
                )
            if base.canon_status != claim.canon_status or base.promotion_status != claim.promotion_status:
                records[DiffKind.CHANGED_CANON].append(
                    _diff_record(DiffKind.CHANGED_CANON, claim, "canon or promotion status changed")
                )
            if base.evidence_class != claim.evidence_class:
                records[DiffKind.CHANGED_EVIDENCE].append(
                    _diff_record(DiffKind.CHANGED_EVIDENCE, claim, "evidence class changed")
                )
        if claim.superseded_by:
            records[DiffKind.SUPERSEDED].append(
                _diff_record(DiffKind.SUPERSEDED, claim, "claim superseded by later correction")
            )

    for claim_id, claim in base_by_id.items():
        if claim_id not in merged_by_id:
            records[DiffKind.REMOVED].append(
                _diff_record(DiffKind.REMOVED, claim, "claim absent from merged comparison")
            )

    return {kind.value: tuple(items) for kind, items in records.items()}


def _diff_record(kind: DiffKind, claim: ContinuityClaim, detail: str) -> DiffRecord:
    return DiffRecord(
        diff_id=_stable_id("cme_diff", kind.value, claim.claim_id, detail),
        kind=kind,
        claim_id=claim.claim_id,
        normalized_key=claim.normalized_key,
        detail=detail,
    )


def apply_review_action(
    claims: Sequence[ContinuityClaim],
    claim_id: str,
    action: ReviewStatus | str,
    *,
    reviewed_by: str = NOAH_AUTHORITY,
    edited_text: str = "",
) -> tuple[ContinuityClaim, ...]:
    """Apply a review action without canon promotion."""
    review_status = action if isinstance(action, ReviewStatus) else ReviewStatus(str(action))
    updated: list[ContinuityClaim] = []
    found = False
    for claim in claims:
        if claim.claim_id != claim_id:
            updated.append(claim)
            continue
        found = True
        claim.review_status = review_status
        claim.reviewed_by = reviewed_by
        if review_status == ReviewStatus.APPROVED:
            claim.approved_by = reviewed_by
        if review_status == ReviewStatus.EDITED and edited_text:
            claim.claim_text = edited_text
            claim.normalized_key = _claim_key(claim.claim_type, claim.metadata.get("explicit_key", ""), edited_text)
        claim.canon_status = CANON_CANDIDATE
        claim.promotion_status = NO_CANON_PROMOTION
        updated.append(claim)
    if not found:
        raise KeyError(f"Unknown claim_id: {claim_id}")
    return tuple(updated)


def build_review_decision(
    claim_id: str,
    action: ReviewStatus | str,
    *,
    reviewed_by: str = NOAH_AUTHORITY,
    edited_text: str = "",
) -> ReviewDecision:
    review_status = action if isinstance(action, ReviewStatus) else ReviewStatus(str(action))
    return ReviewDecision(
        decision_id=_stable_id("cme_review", claim_id, review_status.value, reviewed_by, edited_text),
        claim_id=claim_id,
        action=review_status,
        reviewed_by=reviewed_by,
        canon_promoted=False,
        promotion_status=NO_CANON_PROMOTION,
        edited_text=edited_text,
    )


def merge_conversations(
    conversations: Sequence[ConversationBatch | Mapping[str, Any]],
    *,
    base_claims: Sequence[ContinuityClaim] | None = None,
    merged_at: str | None = None,
) -> MergeResult:
    events: list[ContinuityEvent] = []
    for conversation in conversations:
        events.extend(normalize_conversation(conversation))
    events.sort(key=lambda event: (event.timestamp, event.thread_id, event.ordinal, event.event_id))

    raw_claims = extract_claims(events)
    claims = apply_corrections(raw_claims)
    duplicates = find_duplicates(claims)
    conflicts = detect_conflicts(claims)
    current_state = generate_current_state(claims, conflicts)
    diff = conversation_diff(tuple(base_claims or ()), claims)
    review_queue = tuple(
        claim.claim_id
        for claim in claims
        if claim.review_status == ReviewStatus.PENDING
        and claim.review_status != ReviewStatus.REJECTED
    )
    receipt = build_merge_receipt(
        events=events,
        claims=claims,
        duplicates=duplicates,
        conflicts=conflicts,
        merged_at=merged_at or utc_now(),
    )
    return MergeResult(
        schema_version=SCHEMA_VERSION,
        events=tuple(events),
        claims=claims,
        duplicates=duplicates,
        conflicts=conflicts,
        current_state=current_state,
        diff=diff,
        review_queue=review_queue,
        receipt=receipt,
    )


def build_merge_receipt(
    *,
    events: Sequence[ContinuityEvent],
    claims: Sequence[ContinuityClaim],
    duplicates: Sequence[DuplicateRecord],
    conflicts: Sequence[ConflictRecord],
    merged_at: str,
) -> MergeReceipt:
    source_thread_ids = tuple(sorted({event.thread_id for event in events}))
    material = {
        "schema_version": SCHEMA_VERSION,
        "operation": "continuity_merge",
        "source_thread_ids": source_thread_ids,
        "event_ids": tuple(event.event_id for event in events),
        "claim_ids": tuple(claim.claim_id for claim in claims),
        "duplicate_ids": tuple(record.duplicate_id for record in duplicates),
        "conflict_ids": tuple(record.conflict_id for record in conflicts),
        "canon_promoted": False,
        "external_action": False,
        "raw_records_mutated": False,
        "history_destroyed": False,
        "deterministic_core": True,
    }
    receipt_hash = sha256_text(json.dumps(material, sort_keys=True, ensure_ascii=True))
    return MergeReceipt(
        schema_version=SCHEMA_VERSION,
        operation="continuity_merge",
        source_thread_ids=source_thread_ids,
        event_count=len(events),
        claim_count=len(claims),
        duplicate_count=len(duplicates),
        conflict_count=len(conflicts),
        merged_at=merged_at,
        canon_promoted=False,
        external_action=False,
        raw_records_mutated=False,
        history_destroyed=False,
        deterministic_core=True,
        receipt_hash_sha256=receipt_hash,
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(_jsonable(item) for item in value)
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value
