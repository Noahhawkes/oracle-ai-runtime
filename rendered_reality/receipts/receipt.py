"""
rendered_reality/receipts/receipt.py — Ingestion Receipt Gate (v0.1)

The receipt is the gate. Nothing becomes canon without one, and no receipt
promotes to canon without Noah.Physical approval. Built FIRST — before vectors,
connectors, or any Latent Canon work — per the peer-review directive:
"No new features until receipts work. First prove what went in."

Core rule: Write from truth. Do not manufacture truth.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from enum import Enum


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def content_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── Canon ladder (NEW GROUND 4) ─────────────────────────────────────────────
class CanonStatus(str, Enum):
    EXTERNAL_THREAD_PASS_SIGNAL = "external_thread_pass_signal"
    CANDIDATE_IDEA = "candidate_idea"
    DRAFT_ARCHITECTURE = "draft_architecture"
    CLAIMED_BUILD = "claimed_build"
    RUNTIME_INGESTED_RECORD = "runtime_ingested_record"
    WITNESS_VERIFIED_RECORD = "witness_verified_record"
    NOAH_APPROVED_CANON = "noah_approved_canon"


CANON_LADDER: tuple[CanonStatus, ...] = (
    CanonStatus.EXTERNAL_THREAD_PASS_SIGNAL,
    CanonStatus.CANDIDATE_IDEA,
    CanonStatus.DRAFT_ARCHITECTURE,
    CanonStatus.CLAIMED_BUILD,
    CanonStatus.RUNTIME_INGESTED_RECORD,
    CanonStatus.WITNESS_VERIFIED_RECORD,
    CanonStatus.NOAH_APPROVED_CANON,
)


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# ── Authorship (NEW GROUND 3): submission proves transfer, not origin ────────
class Authorship(str, Enum):
    NOAH_AUTHORED = "noah_authored"
    AI_AUTHORED = "ai_authored"
    HUMAN_OTHER = "human_other"
    ADOPTED_BY_NOAH = "adopted_by_noah"
    UNKNOWN = "unknown"


AI_SYSTEMS = {
    "claude", "claude_code", "claude code", "chatgpt", "gpt", "openai",
    "grok", "gemini", "meta", "meta_ai", "meta ai", "llama",
}

# ── Observation status (NEW GROUND 2): Return-from-Dark ──────────────────────
OBS_MACHINE = "machine_observed"
OBS_RETURN_FROM_DARK = "Return-from-Dark"
OBS_POST_EVENT_TESTIMONY = "post_event_testimony"

# Promotion recommendation — from the Return-from-Dark Protocol doc
# (2026-06-23 memory-promotion record, ChatGPT-authored, witnessed candidate).
PROMOTION_DECAY = "decay"
PROMOTION_LEDGER = "ledger"
PROMOTION_MEMORY_CANDIDATE = "memory_candidate"
PROMOTION_CANON_REVIEW = "canon_review"

# Documented Return-from-Dark trigger phrases.
RETURN_FROM_DARK_TRIGGERS = (
    "return from dark", "post-event witness note", "i lived this offline",
    "thought tracking from ios", "bring ashley back in",
)


class ReceiptError(Exception):
    pass


def classify_authorship(original_author: str, adopted_by_noah: bool = False) -> Authorship:
    """Authorship is NEVER inferred from first-person wording. It is decided
    from who actually wrote the text, plus whether Noah explicitly adopted it."""
    name = (original_author or "").strip().lower()
    if name in ("noah", "noah.physical", "noah physical"):
        return Authorship.NOAH_AUTHORED
    if adopted_by_noah:
        return Authorship.ADOPTED_BY_NOAH
    if name in AI_SYSTEMS:
        return Authorship.AI_AUTHORED
    if name in ("", "unknown"):
        return Authorship.UNKNOWN
    return Authorship.HUMAN_OTHER


@dataclass
class Receipt:
    # provenance
    source: str
    submitting_system: str
    submitted_by: str
    original_author: str = "unknown"
    author_confidence: float = 0.0
    authorship_status: Authorship = Authorship.UNKNOWN
    adopted_by_noah: bool = False
    transport_path: str = "unknown"
    # artifact
    content: str = ""
    artifact_path: str | None = None
    content_hash: str | None = None
    file_hash: str | None = None
    # code-execution evidence
    run_command: str | None = None
    observed_output: str | None = None
    # observation honesty
    machine_observed: bool = False
    observation_status: str = OBS_POST_EVENT_TESTIMONY
    reporter: str | None = None
    testimony_source: str | None = None
    event_label: str | None = None
    # Return-from-Dark protocol fields (capture later, label honestly, do not invent)
    people: list[str] = field(default_factory=list)
    meaning_summary: str = ""
    boundaries: list[str] = field(default_factory=list)   # what must NOT be inferred
    event_time: str | None = None                          # exact/approx/unknown
    promotion_recommendation: str = ""                     # decay|ledger|memory_candidate|canon_review
    # truth controls
    holes: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    confidence_level: str = "unverified"
    # governance
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    canon_status: CanonStatus = CanonStatus.CANDIDATE_IDEA
    source_type: str = "ingested_record"
    # auto
    receipt_id: str = field(default_factory=lambda: "rcpt_" + uuid.uuid4().hex[:12])
    timestamp: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.content and not self.content_hash:
            self.content_hash = content_hash(self.content)
        self.validate()

    def validate(self) -> None:
        if self.observation_status == OBS_RETURN_FROM_DARK:
            if self.machine_observed:
                raise ReceiptError("Return-from-Dark record cannot be machine_observed")
            if not self.testimony_source:
                raise ReceiptError("Return-from-Dark requires a testimony_source")
            if not any("machine observation" in h.lower() for h in self.holes):
                self.holes.append("No machine observation")
        if self.machine_observed and self.observation_status != OBS_MACHINE:
            raise ReceiptError(
                "machine_observed=True requires observation_status=machine_observed"
            )

    # ── gate helpers ────────────────────────────────────────────────────────
    def claims_machine_observation(self) -> bool:
        return self.machine_observed or self.observation_status == OBS_MACHINE

    def is_noah_authored(self) -> bool:
        return self.authorship_status in (Authorship.NOAH_AUTHORED, Authorship.ADOPTED_BY_NOAH)

    def adopt_by_noah(self) -> None:
        """Noah explicitly takes authorship of AI/other text. Only this — never
        first-person wording — can move authored-elsewhere text toward canon."""
        self.adopted_by_noah = True
        self.authorship_status = Authorship.ADOPTED_BY_NOAH

    def can_promote_to_canon(self) -> tuple[bool, str]:
        if self.approval_status != ApprovalStatus.APPROVED:
            return False, "approval_status is not approved"
        if self.observation_status == OBS_RETURN_FROM_DARK and self.machine_observed:
            return False, "Return-from-Dark cannot claim machine observation"
        return True, "ok"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["authorship_status"] = self.authorship_status.value
        d["approval_status"] = self.approval_status.value
        d["canon_status"] = self.canon_status.value
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


def assert_machine_observed(receipt: Receipt) -> None:
    """Guard: fail loudly if anything tries to render a machine-observation
    claim for an event the machine did not observe (NEW GROUND 2)."""
    if not receipt.machine_observed:
        raise ReceiptError(
            f"Cannot claim machine observation for {receipt.receipt_id}: "
            f"machine_observed=False (observation_status={receipt.observation_status})"
        )


class ReceiptStore:
    """Append-only receipt log. The system's memory of what went in."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._items: list[Receipt] = []

    def add(self, receipt: Receipt) -> Receipt:
        self._items.append(receipt)
        if self.path:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(receipt.to_dict()) + "\n")
        return receipt

    def get(self, receipt_id: str) -> Receipt | None:
        return next((r for r in self._items if r.receipt_id == receipt_id), None)

    def __len__(self) -> int:
        return len(self._items)
