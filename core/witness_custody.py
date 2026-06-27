"""Witness custody primitives for ORACLE.AI.

This module implements the Witness Layer rule that classification and
authorization must happen before generation. It is intentionally small and
pure-Python so the runtime, tests, and future UI can share the same custody
logic without pulling in an LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Iterable


class ClaimType(str, Enum):
    WITNESSED = "witnessed"
    DECLARED = "declared"
    UPLOADED = "uploaded"
    INFERRED = "inferred"
    GENERATED = "generated"
    DISPUTED = "disputed"
    UNSUPPORTED = "unsupported"
    UNRESOLVED = "unresolved"


class GenerationMode(str, Enum):
    RECITE = "recite"
    INTERPRET = "interpret"
    RECONSTRUCT = "reconstruct"
    HYPOTHESIZE = "hypothesize"
    REFUSE = "refuse"


class MemoryStatus(str, Enum):
    DURABLE = "durable"
    CANDIDATE = "candidate"
    TEMPORARY = "temporary"
    DISPUTED = "disputed"
    REJECTED = "rejected"


@dataclass(frozen=True)
class SourceReceipt:
    source_id: str
    source_type: str
    source_distance: int
    location: str = ""
    timestamp: str = ""
    verification_authority: str = ""

    def has_receipt(self) -> bool:
        return bool(self.source_id and self.source_type)


@dataclass(frozen=True)
class WitnessClaim:
    claim_id: str
    claim_text: str
    claim_type: ClaimType
    source: SourceReceipt
    confidence_level: str = "unknown"
    confidence_basis: str = "unverified"
    consent_scope: str = "unspecified"
    refusal_boundary: str = "Do not claim beyond the available evidence."
    contradictions: tuple[str, ...] = field(default_factory=tuple)
    corroborating_sources: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["claim_type"] = self.claim_type.value
        return data


@dataclass(frozen=True)
class RoutedClaim:
    claim: WitnessClaim
    generation_mode: GenerationMode
    memory_status: MemoryStatus
    authorized: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["claim"] = self.claim.to_dict()
        data["generation_mode"] = self.generation_mode.value
        data["memory_status"] = self.memory_status.value
        return data


@dataclass(frozen=True)
class ContradictionRecord:
    contradiction_id: str
    claim_ids: tuple[str, ...]
    summary: str
    memory_status: MemoryStatus = MemoryStatus.DISPUTED
    retrieval_rule: str = (
        "Surface all linked claims and state that the contradiction is unresolved "
        "unless corroborating evidence resolves it."
    )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["memory_status"] = self.memory_status.value
        return data


_REFUSAL_REASON = "I do not have enough verified evidence to claim that."


def route_claim(claim: WitnessClaim) -> RoutedClaim:
    """Classify and authorize a claim before any substantive generation.

    The router is deliberately conservative. Generated, inferred, unsupported,
    unresolved, and disputed claims can still be useful, but they do not receive
    the same permissions as witnessed or declared claims with receipts.
    """
    if not claim.claim_text.strip():
        return RoutedClaim(
            claim=claim,
            generation_mode=GenerationMode.REFUSE,
            memory_status=MemoryStatus.REJECTED,
            authorized=False,
            reason="Empty claim text cannot be promoted.",
        )

    if not claim.source.has_receipt():
        return RoutedClaim(
            claim=claim,
            generation_mode=GenerationMode.REFUSE,
            memory_status=MemoryStatus.REJECTED,
            authorized=False,
            reason=_REFUSAL_REASON,
        )

    if claim.contradictions:
        return RoutedClaim(
            claim=claim,
            generation_mode=GenerationMode.INTERPRET,
            memory_status=MemoryStatus.DISPUTED,
            authorized=True,
            reason="Claim is preserved as disputed custody, not collapsed into a single fact.",
        )

    if claim.claim_type in {ClaimType.UNSUPPORTED, ClaimType.UNRESOLVED}:
        return RoutedClaim(
            claim=claim,
            generation_mode=GenerationMode.REFUSE,
            memory_status=MemoryStatus.CANDIDATE,
            authorized=False,
            reason=_REFUSAL_REASON,
        )

    if claim.claim_type == ClaimType.GENERATED:
        return RoutedClaim(
            claim=claim,
            generation_mode=GenerationMode.HYPOTHESIZE,
            memory_status=MemoryStatus.TEMPORARY,
            authorized=True,
            reason="Generated synthesis may be used only as temporary or clearly labeled hypothesis.",
        )

    if claim.claim_type == ClaimType.INFERRED:
        return RoutedClaim(
            claim=claim,
            generation_mode=GenerationMode.INTERPRET,
            memory_status=MemoryStatus.CANDIDATE,
            authorized=True,
            reason="Inference requires visible confidence basis and cannot speak as witnessed fact.",
        )

    if claim.claim_type in {ClaimType.WITNESSED, ClaimType.DECLARED, ClaimType.UPLOADED}:
        return RoutedClaim(
            claim=claim,
            generation_mode=GenerationMode.RECITE,
            memory_status=MemoryStatus.DURABLE,
            authorized=True,
            reason="Claim has source receipt and may be recited within its refusal boundary.",
        )

    return RoutedClaim(
        claim=claim,
        generation_mode=GenerationMode.REFUSE,
        memory_status=MemoryStatus.REJECTED,
        authorized=False,
        reason=_REFUSAL_REASON,
    )


def promote_contradiction(
    contradiction_id: str,
    claims: Iterable[WitnessClaim],
    summary: str | None = None,
) -> ContradictionRecord:
    """Preserve contradictions as durable dispute records.

    The gate does not pick a winner when two valid artifacts conflict. It keeps
    the conflict visible so retrieval must surface the unresolved structure.
    """
    claim_list = list(claims)
    if len(claim_list) < 2:
        raise ValueError("A contradiction record requires at least two claims.")

    claim_ids = tuple(claim.claim_id for claim in claim_list)
    if summary is None:
        summary = (
            "The record contains contradictory claims. Preserve each claim, "
            "its receipt, and its authority chain; do not resolve without new evidence."
        )

    return ContradictionRecord(
        contradiction_id=contradiction_id,
        claim_ids=claim_ids,
        summary=summary,
    )


def refusal_boundary_message(claim: WitnessClaim) -> str:
    """Return the enforceable refusal message for a claim."""
    boundary = claim.refusal_boundary.strip()
    if boundary:
        return f"{_REFUSAL_REASON} Boundary: {boundary}"
    return _REFUSAL_REASON
