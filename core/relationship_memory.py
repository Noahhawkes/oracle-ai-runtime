"""
core/relationship_memory.py — USER.AI CRM Phase 1: Sovereign Relationship Memory

The 51/49 Human Sovereignty Rule governs every write in this module.

Canonical wording (IDENTITYFRAME v1 / docs/EXTERNAL_INTEGRATION_SOVEREIGNTY.md):
    "Noah holds the sovereign 51%. SOV1.AI and ORACLE execute the operational 49%.
    The system may render, suggest, and structure, but Noah alone approves, rejects,
    corrects, deletes, revokes, or quarantines."

What this module stores:
    Compressed, approved, provenance-tagged relationship context:
    identity, role, organization, commitments, follow-ups, trust level,
    communication preferences, known boundaries, last interaction summary.

What this module NEVER stores:
    Raw emails, raw chats, raw keystrokes, full transcripts, full documents,
    inferred emotions, invented motives, speculative relationship strength.

IdentityFrame v1 rules enforced here:
    - Unknown fields remain empty/null — do not infer what is not evidenced.
    - Semantic Inflation forbidden — do not expand modest facts into grander claims.
    - Narrative Smoothing forbidden — preserve contradictions and friction.
    - Emotional Overcompletion forbidden — no invented emotional context.
    - Deontic Erosion forbidden — 'must' stays 'must', 'never' stays 'never'.

Persistence:
    Memory/relationship_memory/{id}.json   — one file per relationship record
    Memory/relationship_memory/index.json  — fast lookup index (auto-maintained)
    (Memory/ is gitignored — data is local, sovereign, never committed)

Usage:
    store = RelationshipMemoryStore()

    # 1. Render a candidate (ORACLE's 49%)
    candidate = RelationshipMemory.create(
        name="Ashley",
        sov_id="SOV2.AI",
        relationship_type="partner",
        trust_tier="sovereign_partner",
        source="manual entry",
    )

    # 2. Submit — default status: pending
    rid = store.submit(candidate)

    # 3. Noah approves (sovereign 51%)
    store.approve(rid)

    # 4. Now appears in normal recall
    store.list_approved()
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Path bootstrap ────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from root import ROOT

STORE_DIR = ROOT / "Memory" / "relationship_memory"
INDEX_FILE = STORE_DIR / "index.json"

# ── Status constants ──────────────────────────────────────────────────────────
STATUS_PENDING     = "pending"
STATUS_APPROVED    = "approved"
STATUS_REJECTED    = "rejected"
STATUS_QUARANTINED = "quarantined"
STATUS_REVOKED     = "revoked"

_RECALL_STATUSES = {STATUS_APPROVED}          # only approved returns in normal recall
_ALL_STATUSES    = {                           # valid status values
    STATUS_PENDING, STATUS_APPROVED,
    STATUS_REJECTED, STATUS_QUARANTINED, STATUS_REVOKED,
}

# ── Sensitive data patterns (mirrors integration_gate.py) ────────────────────
_SENSITIVE_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ya29\.[A-Za-z0-9_\-]+"),
    re.compile(r"-----BEGIN [A-Z ]+-----"),
    re.compile(r"Bearer [A-Za-z0-9_\-\.]+"),
    re.compile(r"\b(?:\d[ -]?){13,16}\b"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"(?i)(password|passwd|secret|api_key)\s*[:=]\s*\S+"),
]


def _check_sensitive(text: str) -> bool:
    """Return True if text contains a sensitive pattern — reject immediately."""
    for p in _SENSITIVE_PATTERNS:
        if p.search(text):
            return True
    return False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class RelationshipMemory:
    """
    A single sovereign relationship memory record.

    Provenance fields are mandatory.
    All contextual fields are optional — unknown fields remain None.
    Emotional state, inferred motives, and speculative trust are not stored.

    IdentityFrame v1: Preserve the hole.
    Do not complete what cannot be verified.
    """

    # Identity
    id:                  str            = field(default_factory=lambda: str(uuid.uuid4()))
    name:                str            = ""
    sov_id:              Optional[str]  = None    # SOV2.AI, SOV3.AI, etc. if assigned
    aliases:             list[str]      = field(default_factory=list)

    # Organization / role
    organization:        Optional[str]  = None
    role:                Optional[str]  = None
    department:          Optional[str]  = None

    # Relationship classification
    relationship_type:   str            = ""      # partner, family, coworker, vendor, prospect, etc.
    trust_tier:          Optional[str]  = None    # sovereign_partner, sovereign_family, team, peer, public
    tags:                list[str]      = field(default_factory=list)

    # Communication
    preferred_channel:   Optional[str]  = None    # email, phone, text, in-person, etc.
    contact_info_note:   Optional[str]  = None    # non-PII note: "prefers morning calls"

    # Relationship context (compressed meaning only — no raw transcripts)
    last_interaction_summary: Optional[str] = None
    commitments_made_to:      list[str]     = field(default_factory=list)
    commitments_made_by:      list[str]     = field(default_factory=list)
    follow_up_needed:         Optional[str] = None
    open_loops:               list[str]     = field(default_factory=list)
    known_boundaries:         list[str]     = field(default_factory=list)
    important_facts:          list[str]     = field(default_factory=list)
    next_suggested_action:    Optional[str] = None

    # Provenance — mandatory
    source:       str  = ""         # who/what generated this record: "manual", "oracle_proposal", etc.
    confidence:   str  = "INFERRED" # VERIFIED | DERIVED | INFERRED | GENERATED | UNKNOWN
    source_note:  Optional[str] = None

    # Approval state — controlled by sovereign only
    status:       str            = STATUS_PENDING
    created_at:   str            = field(default_factory=_now_iso)
    updated_at:   str            = field(default_factory=_now_iso)
    approved_at:  Optional[str]  = None
    decided_by:   Optional[str]  = None  # who made the approval/rejection decision
    decision_note: Optional[str] = None

    # Sensitive flag — set at creation, never cleared
    sensitive_flag: bool = False

    # ── factory ───────────────────────────────────────────────────────────────

    @classmethod
    def create(
        cls,
        name: str,
        relationship_type: str,
        source: str,
        **kwargs,
    ) -> "RelationshipMemory":
        """
        Create a new RelationshipMemory candidate.
        Status defaults to 'pending' — requires sovereign approval before recall.
        Sensitive content is flagged and will be blocked at submission.
        """
        rm = cls(
            name=name,
            relationship_type=relationship_type,
            source=source,
            **kwargs,
        )
        # Sensitive scan across all string fields
        blob = json.dumps(asdict(rm))
        rm.sensitive_flag = _check_sensitive(blob)
        return rm

    # ── serialization ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "RelationshipMemory":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def touch(self) -> None:
        self.updated_at = _now_iso()

    def __repr__(self) -> str:
        return (
            f"RelationshipMemory(id={self.id[:8]}..., name={self.name!r}, "
            f"type={self.relationship_type!r}, status={self.status!r}, "
            f"confidence={self.confidence!r})"
        )


# ── Store ─────────────────────────────────────────────────────────────────────

class RelationshipMemoryStore:
    """
    Sovereign relationship memory store — USER.AI CRM Phase 1.

    51/49 enforcement:
        submit()  — ORACLE renders (49%)
        approve() — Noah approves (51%) — only path to STATUS_APPROVED
        reject()  — Noah rejects (51%)
        quarantine() — Noah quarantines (51%)
        revoke()  — Noah revokes (51%)

    Normal recall (list_approved, search) returns APPROVED records only.
    Pending, rejected, quarantined, and revoked records are excluded.

    Persistence: Memory/relationship_memory/{id}.json (gitignored)
    """

    def __init__(self) -> None:
        STORE_DIR.mkdir(parents=True, exist_ok=True)
        if not INDEX_FILE.exists():
            self._write_index({})

    # ── internal persistence ──────────────────────────────────────────────────

    def _read_index(self) -> dict[str, str]:
        """Return {id: status} index."""
        try:
            return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _write_index(self, index: dict) -> None:
        INDEX_FILE.write_text(json.dumps(index, indent=2), encoding="utf-8")

    def _record_path(self, rid: str) -> Path:
        return STORE_DIR / f"{rid}.json"

    def _load(self, rid: str) -> RelationshipMemory:
        path = self._record_path(rid)
        if not path.exists():
            raise KeyError(f"RelationshipMemory not found: {rid}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return RelationshipMemory.from_dict(data)

    def _save(self, rm: RelationshipMemory) -> None:
        rm.touch()
        self._record_path(rm.id).write_text(
            json.dumps(rm.to_dict(), indent=2), encoding="utf-8"
        )
        index = self._read_index()
        index[rm.id] = rm.status
        self._write_index(index)

    def _set_status(
        self,
        rid: str,
        new_status: str,
        decided_by: str = "Noah / SOV1.AI",
        decision_note: Optional[str] = None,
        approved: bool = False,
    ) -> RelationshipMemory:
        if new_status not in _ALL_STATUSES:
            raise ValueError(f"Invalid status: {new_status}")
        rm = self._load(rid)
        rm.status       = new_status
        rm.decided_by   = decided_by
        rm.decision_note = decision_note
        if approved:
            rm.approved_at = _now_iso()
        self._save(rm)
        return rm

    # ── public API ────────────────────────────────────────────────────────────

    def submit(self, rm: RelationshipMemory) -> str:
        """
        Submit a candidate relationship memory (ORACLE's 49%).
        Status: pending. Not yet visible in normal recall.
        Blocked if sensitive content is detected.

        Returns the record ID.
        """
        if rm.sensitive_flag:
            raise ValueError(
                f"Submission blocked: sensitive content detected in record for '{rm.name}'. "
                "Remove credentials, keys, or PII before submitting."
            )
        if not rm.name:
            raise ValueError("RelationshipMemory requires a non-empty 'name'.")
        if not rm.source:
            raise ValueError("RelationshipMemory requires a 'source' for provenance.")
        rm.status = STATUS_PENDING
        self._save(rm)
        return rm.id

    def approve(
        self,
        rid: str,
        decided_by: str = "Noah / SOV1.AI",
        decision_note: Optional[str] = None,
    ) -> RelationshipMemory:
        """
        Approve a pending candidate (sovereign 51%).
        Approved records appear in normal recall.
        """
        rm = self._load(rid)
        if rm.status == STATUS_APPROVED:
            return rm
        if rm.status in (STATUS_REJECTED, STATUS_QUARANTINED):
            raise ValueError(
                f"Cannot approve a {rm.status} record. Revoke first or submit a new candidate."
            )
        return self._set_status(
            rid, STATUS_APPROVED,
            decided_by=decided_by, decision_note=decision_note, approved=True
        )

    def reject(
        self,
        rid: str,
        decided_by: str = "Noah / SOV1.AI",
        decision_note: Optional[str] = None,
    ) -> RelationshipMemory:
        """
        Reject a candidate (sovereign 51%).
        Rejected records are excluded from all normal recall.
        """
        return self._set_status(
            rid, STATUS_REJECTED,
            decided_by=decided_by, decision_note=decision_note
        )

    def quarantine(
        self,
        rid: str,
        decided_by: str = "Noah / SOV1.AI",
        decision_note: Optional[str] = None,
    ) -> RelationshipMemory:
        """
        Quarantine a record (sovereign 51%).
        Quarantined records are excluded from recall but preserved for review.
        Use when content is uncertain or potentially incorrect — not permanently rejected.
        """
        return self._set_status(
            rid, STATUS_QUARANTINED,
            decided_by=decided_by, decision_note=decision_note
        )

    def revoke(
        self,
        rid: str,
        decided_by: str = "Noah / SOV1.AI",
        decision_note: Optional[str] = None,
    ) -> RelationshipMemory:
        """
        Revoke an approved record (sovereign 51%).
        Revoked records are excluded from recall. The record is preserved for audit.
        """
        return self._set_status(
            rid, STATUS_REVOKED,
            decided_by=decided_by, decision_note=decision_note
        )

    def get(self, rid: str) -> RelationshipMemory:
        """Return any record by ID regardless of status."""
        return self._load(rid)

    def list_approved(self) -> list[RelationshipMemory]:
        """
        Return all approved relationship memories — normal recall path.
        Pending, rejected, quarantined, and revoked records are excluded.
        """
        index = self._read_index()
        result = []
        for rid, status in index.items():
            if status in _RECALL_STATUSES:
                try:
                    result.append(self._load(rid))
                except (KeyError, json.JSONDecodeError):
                    pass
        result.sort(key=lambda r: r.name.lower())
        return result

    def list_pending(self) -> list[RelationshipMemory]:
        """Return all pending candidates awaiting Noah's decision."""
        index = self._read_index()
        result = []
        for rid, status in index.items():
            if status == STATUS_PENDING:
                try:
                    result.append(self._load(rid))
                except (KeyError, json.JSONDecodeError):
                    pass
        result.sort(key=lambda r: r.created_at)
        return result

    def list_by_status(self, status: str) -> list[RelationshipMemory]:
        """Return all records with the given status."""
        if status not in _ALL_STATUSES:
            raise ValueError(f"Unknown status: {status}")
        index = self._read_index()
        result = []
        for rid, s in index.items():
            if s == status:
                try:
                    result.append(self._load(rid))
                except (KeyError, json.JSONDecodeError):
                    pass
        return result

    def search(
        self,
        name: Optional[str] = None,
        organization: Optional[str] = None,
        relationship_type: Optional[str] = None,
        tag: Optional[str] = None,
        include_pending: bool = False,
    ) -> list[RelationshipMemory]:
        """
        Search approved (and optionally pending) relationship memories.
        All match criteria are case-insensitive substring matches.
        Rejected, quarantined, and revoked records are never returned.
        """
        statuses = _RECALL_STATUSES | ({STATUS_PENDING} if include_pending else set())
        index = self._read_index()
        results = []
        for rid, status in index.items():
            if status not in statuses:
                continue
            try:
                rm = self._load(rid)
            except (KeyError, json.JSONDecodeError):
                continue

            if name and name.lower() not in rm.name.lower():
                if not any(name.lower() in a.lower() for a in rm.aliases):
                    continue
            if organization and (
                not rm.organization or
                organization.lower() not in rm.organization.lower()
            ):
                continue
            if relationship_type and relationship_type.lower() not in rm.relationship_type.lower():
                continue
            if tag and not any(tag.lower() in t.lower() for t in rm.tags):
                continue

            results.append(rm)

        results.sort(key=lambda r: r.name.lower())
        return results

    def summary(self) -> str:
        """Return a human-readable store summary."""
        index = self._read_index()
        counts: dict[str, int] = {}
        for status in _ALL_STATUSES:
            counts[status] = 0
        for s in index.values():
            counts[s] = counts.get(s, 0) + 1

        lines = [
            "RelationshipMemoryStore",
            f"  Approved:    {counts[STATUS_APPROVED]}",
            f"  Pending:     {counts[STATUS_PENDING]}",
            f"  Quarantined: {counts[STATUS_QUARANTINED]}",
            f"  Rejected:    {counts[STATUS_REJECTED]}",
            f"  Revoked:     {counts[STATUS_REVOKED]}",
            f"  Total:       {len(index)}",
            f"  Store:       {STORE_DIR}",
        ]
        return "\n".join(lines)


# ── Smoke test / demo ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("RelationshipMemory — Smoke Test")
    print("51/49 Sovereignty Rule enforced throughout")
    print("=" * 60)

    store = RelationshipMemoryStore()

    # 1. Create a candidate (ORACLE's 49%)
    candidate = RelationshipMemory.create(
        name="Ashley",
        sov_id="SOV2.AI",
        relationship_type="partner",
        trust_tier="sovereign_partner",
        source="manual entry — Noah",
        confidence="VERIFIED",
        tags=["family", "USER.AI"],
        important_facts=["Co-founder of the USER.AI vision"],
        follow_up_needed="Onboard as SOV2.AI node when ready",
        next_suggested_action="Discuss shared channel design",
        source_note="Identity record created by SOV1 during USER.AI CRM Phase 1 build",
    )

    print(f"\n[1] Candidate created: {candidate}")
    assert candidate.status == STATUS_PENDING, "New record must be pending"

    # 2. Submit — still pending, NOT in approved recall
    rid = store.submit(candidate)
    print(f"[2] Submitted with id: {rid[:8]}...")

    approved = store.list_approved()
    assert not any(r.id == rid for r in approved), \
        "Pending record must NOT appear in approved recall"
    print("[3] Confirmed: pending record absent from approved recall")

    pending = store.list_pending()
    assert any(r.id == rid for r in pending), "Pending record must be in pending list"
    print("[4] Confirmed: pending record present in pending list")

    # 3. Approve — Noah's 51%
    store.approve(rid, decision_note="SOV2 identity confirmed")
    print("[5] Approved by Noah / SOV1.AI")

    approved = store.list_approved()
    assert any(r.id == rid for r in approved), "Approved record must appear in recall"
    print("[6] Confirmed: approved record appears in recall")

    pending = store.list_pending()
    assert not any(r.id == rid for r in pending), "Approved record must leave pending list"
    print("[7] Confirmed: approved record no longer pending")

    # 4. Search
    results = store.search(name="Ashley")
    assert results, "Search by name must return the approved record"
    print(f"[8] Search by name='Ashley': {len(results)} result(s)")

    results = store.search(tag="USER.AI")
    assert results, "Search by tag must return the approved record"
    print(f"[9] Search by tag='USER.AI': {len(results)} result(s)")

    # 5. Revoke — Noah's 51%
    store.revoke(rid, decision_note="Test run — revoking after smoke test")
    print("[10] Revoked by Noah / SOV1.AI")

    approved = store.list_approved()
    assert not any(r.id == rid for r in approved), "Revoked record must be absent from recall"
    print("[11] Confirmed: revoked record absent from approved recall")

    # 6. Reject a separate candidate — must never appear in recall
    reject_candidate = RelationshipMemory.create(
        name="Test Reject",
        relationship_type="unknown",
        source="smoke test",
        confidence="UNKNOWN",
    )
    reject_id = store.submit(reject_candidate)
    store.reject(reject_id, decision_note="Smoke test rejection")
    approved = store.list_approved()
    assert not any(r.id == reject_id for r in approved), \
        "Rejected record must NEVER appear in approved recall"
    print("[12] Confirmed: rejected record never appears in recall")

    # 7. Quarantine a separate candidate — must never appear in recall
    quar_candidate = RelationshipMemory.create(
        name="Test Quarantine",
        relationship_type="unknown",
        source="smoke test",
        confidence="UNKNOWN",
    )
    quar_id = store.submit(quar_candidate)
    store.quarantine(quar_id, decision_note="Smoke test quarantine")
    approved = store.list_approved()
    assert not any(r.id == quar_id for r in approved), \
        "Quarantined record must NEVER appear in approved recall"
    print("[13] Confirmed: quarantined record never appears in recall")

    # 8. Sensitive content block
    try:
        bad = RelationshipMemory.create(
            name="Bad Actor",
            relationship_type="unknown",
            source="test",
            important_facts=["api_key=sk-abc123xyz456def789ghijkl"],
        )
        store.submit(bad)
        raise AssertionError("Sensitive content should have been blocked")
    except ValueError as e:
        print(f"[14] Sensitive content correctly blocked: {e}")

    # 9. Persistence: reload store and confirm data is durable
    store2 = RelationshipMemoryStore()
    print(f"\n[15] Store reloaded. Summary:\n{store2.summary()}")

    print("\n" + "=" * 60)
    print("All smoke tests passed. RelationshipMemoryStore is operational.")
    print("=" * 60)
