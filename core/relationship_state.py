"""Relationship State (V1) — a person is accumulated relational structure, not a name.

Brick 1 of the Affective Core. Builds persistent, receipted relational records for
the people who matter, from the Affective Provenance harvest (core/affective_provenance)
plus the people table. "Ashley" stops meaning a string and starts meaning shared
history: attachment, conflict, forgiveness, sacrifice, loss, joy, and a current
state — each backed by receipts, holes preserved, nothing fabricated.

Constraints (from the Emotional Core Transmission):
- Value-to-action, never sentiment floats. Evidence is counted and tiered, never scored.
- Provenance + holes preserved. No invented relationship facts.
- ORACLE models the shape; she never claims to feel it. SOV1 stays above affect.
- Candidate-only. Nothing here is canon until Noah promotes it.

This is the substrate the appraisal/love layers need next: love cannot be a one-turn
classification; it requires history. This module is that history, structured.
Pure stdlib.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Any

# Which affective signals feed which relational bucket (evidence, not scores).
_FORGIVE = re.compile(r"forgiv", re.I)
_LOSS = re.compile(r"\b(lost|loss|died|death|grief|gone|passed)\b", re.I)
_JOY = re.compile(r"\b(joy|happy|laugh|proud|love|cherish|grateful|blessed)\b", re.I)
_COMMIT = re.compile(r"\b(always|forever|never leave|promise|committed|stay|vow|marry|married)\b", re.I)


def _tier(n: int) -> str:
    """Evidence tier — NOT a sentiment magnitude. Just how much receipted material exists."""
    if n >= 12:
        return "deep"
    if n >= 4:
        return "established"
    if n >= 1:
        return "present"
    return "none"


@dataclass
class RelationshipState:
    identity: str
    role: str = "UNKNOWN"                       # from the people table if known
    aliases: list[str] = field(default_factory=list)
    shared_event_count: int = 0
    attachment: str = "none"                    # evidence tier (overall)
    lived_attachment: str = "none"              # tier from LIVED sources (journals/docs)
    fiction_attachment: str = "none"            # tier from FICTION sources (never conflate)
    attachment_receipts: list[str] = field(default_factory=list)
    unresolved_conflicts: list[str] = field(default_factory=list)
    forgiveness: list[str] = field(default_factory=list)
    sacrifices: list[str] = field(default_factory=list)   # love/charity WITH cost
    losses: list[str] = field(default_factory=list)
    joys: list[str] = field(default_factory=list)
    commitments: list[str] = field(default_factory=list)
    current_state: str = "UNKNOWN"
    holes: list[str] = field(default_factory=list)
    canonical_status: str = "candidate"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_relationship(identity: str, events: list, *, role: str = "UNKNOWN",
                       aliases: list[str] | None = None, max_receipts: int = 6) -> RelationshipState:
    """Assemble a relationship from affective events whose target matches `identity`
    or one of its aliases. Each bucket keeps raw receipts; nothing is invented."""
    aliases = aliases or []
    names = [identity.lower()] + [a.lower() for a in aliases]

    def _matches(ev) -> bool:
        # Locality discipline: an event belongs to a person only when the harvest's
        # sentence-scoped `target` names them. We do NOT scan the padded window for
        # the name (that pulls unrelated text into "structure" — false attachment).
        t = (getattr(ev, "target", "") or "").lower()
        if t in ("", "unknown"):
            return False
        return any(re.search(rf"\b{re.escape(n)}\b", t) for n in names)

    mine = [e for e in events if _matches(e)]
    rs = RelationshipState(identity=identity, role=role, aliases=aliases)
    rs.shared_event_count = len(mine)

    attach = 0
    attach_lived = 0
    attach_fiction = 0
    for e in mine:
        receipt = (getattr(e, "exact_text", "") or "")[:180]   # padded window: shown to a human
        # keyword buckets read the TIGHT sentence only, so a stray word 200 chars
        # away is never attributed to this person (fall back to receipt if no sentence)
        scope = (getattr(e, "sentence", "") or getattr(e, "exact_text", "") or "")
        fam = getattr(e, "virtue_family", "")
        if fam in ("LOVE", "CHARITY_SELFLESS_LOVE", "BENEVOLENCE"):
            attach += 1
            kind = getattr(e, "source_kind", "UNKNOWN")
            if kind == "FICTION":
                attach_fiction += 1
            elif kind == "LIVED":
                attach_lived += 1
            if len(rs.attachment_receipts) < max_receipts:
                rs.attachment_receipts.append(receipt)
        if getattr(e, "has_conflict", False) and len(rs.unresolved_conflicts) < max_receipts:
            rs.unresolved_conflicts.append(receipt)
        if _FORGIVE.search(scope) and len(rs.forgiveness) < max_receipts:
            rs.forgiveness.append(receipt)
        if getattr(e, "has_cost", False) and fam in ("LOVE", "CHARITY_SELFLESS_LOVE") \
                and len(rs.sacrifices) < max_receipts:
            rs.sacrifices.append(receipt)
        if _LOSS.search(scope) and len(rs.losses) < max_receipts:
            rs.losses.append(receipt)
        if _JOY.search(scope) and len(rs.joys) < max_receipts:
            rs.joys.append(receipt)
        if _COMMIT.search(scope) and len(rs.commitments) < max_receipts:
            rs.commitments.append(receipt)

    rs.attachment = _tier(attach)
    rs.lived_attachment = _tier(attach_lived)
    rs.fiction_attachment = _tier(attach_fiction)

    # current_state: a qualitative summary from what the evidence supports (no scores).
    # Lived attachment is the real bond; fiction attachment is authored, kept separate.
    parts = []
    if rs.lived_attachment != "none":
        parts.append(f"{rs.lived_attachment} lived attachment")
    if rs.fiction_attachment != "none":
        parts.append(f"{rs.fiction_attachment} attachment in Noah's fiction")
    if rs.lived_attachment == "none" and rs.fiction_attachment == "none" and rs.attachment != "none":
        parts.append(f"{rs.attachment} attachment (source kind unresolved)")
    if rs.forgiveness:
        parts.append("forgiveness on record")
    if rs.unresolved_conflicts:
        parts.append("conflict present but not erased")
    if rs.sacrifices:
        parts.append("valued at personal cost")
    rs.current_state = "; ".join(parts) if parts else "insufficient evidence"

    # preserve holes honestly
    if role == "UNKNOWN":
        rs.holes.append("relationship role not confirmed from the people table")
    if rs.shared_event_count == 0:
        rs.holes.append("no affective events reference this identity in the harvest")
    rs.holes.append("relational history is candidate; not canon until Noah confirms")
    return rs
