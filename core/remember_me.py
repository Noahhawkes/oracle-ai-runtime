"""
core/remember_me.py — ORACLE Remember Me Layer
Governed continuity for the real Noah Hawkes.

This is not myth inflation.
This is not cleaned-up story.
This is not surveillance.
This is not emotional invention.

This is the governed continuity layer that preserves the real Noah —
the father, the son, the missionary, the writer, the husband, the friend,
the wounded man, the builder, and the witness — with provenance, gaps,
contradiction, restraint, and approval gates.

Canonical governance (IDENTITYFRAME v1 / docs/ORACLE_SOUL_DIRECTIVE.md):
    "Noah holds the sovereign 51%. SOV1.AI and ORACLE execute the operational 49%.
    The system may render, suggest, and structure, but Noah alone approves, rejects,
    corrects, deletes, revokes, or quarantines."

Hard law — IdentityFrame v1, Section 4:
    Preserve the hole.
    Absence is data.
    Do not complete what cannot be verified.

Forbidden transformations (IdentityFrame v1, Section 8):
    - Inventing missing memories
    - Smoothing contradictions without marking them
    - Presenting generated prose as autobiographical fact
    - Converting uncertainty into certainty
    - Replacing a human claim with a more flattering machine version
    - Weakening obligations without explicit authorization
    - Treating emotional plausibility as evidence
    - Simulating identity while claiming to preserve identity

What is stored:
    Compressed, approved, provenance-tagged identity continuity records.
    Facts Noah has lived, witnessed, or explicitly confirmed.
    Holes Noah has not yet filled — preserved as unknowns, not invented.

What is never stored:
    Raw transcripts, raw emails, raw chats, raw files.
    Inferred emotions, invented motives, speculative relationship strength.
    Mythology, amplified identity, narrative smoothing.

Source document:
    "When the Mirror Spoke Back: AI, Faith, and the Narrated Self"
    Author: Noah A. Hawkes
    Google Drive ID: 16lFi-LCx6W-_quYVgd3kqgrvECI9xKDbuWjGT8qHuN0
    Created: 2026-05-24

Persistence:
    Memory/remember_me/{id}.json   — one file per record (gitignored)
    Memory/remember_me/index.json  — status index (gitignored)
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

STORE_DIR = ROOT / "Memory" / "remember_me"
INDEX_FILE = STORE_DIR / "index.json"

# ── Status constants ──────────────────────────────────────────────────────────
STATUS_PENDING     = "pending"
STATUS_APPROVED    = "approved"
STATUS_REJECTED    = "rejected"
STATUS_QUARANTINED = "quarantined"
STATUS_REVOKED     = "revoked"

_RECALL_STATUSES = {STATUS_APPROVED}
_ALL_STATUSES    = {
    STATUS_PENDING, STATUS_APPROVED,
    STATUS_REJECTED, STATUS_QUARANTINED, STATUS_REVOKED,
}

# ── Memory categories — the facets of the real Noah ──────────────────────────
CATEGORIES = {
    "father":       "Noah as a father to Elijah, Ethan, and Ender",
    "son":          "Noah as a son — Thomas Alvin Hawkes Jr., the loss, the inheritance",
    "husband":      "Noah as a husband — Ashley, partnership, the daily life",
    "parent":       "Noah's parenting approach, values, commitments to his children",
    "missionary":   "ElderHawkes — the LDS mission, faith, belief, grace-driven identity",
    "writer":       "Noah's voice, essays, frameworks, the narrated self",
    "friend":       "Key relationships — Troy Garlock and others",
    "builder":      "What Noah builds — systems, companies, tools, ORACLE itself",
    "witness":      "Noah as observer — the RenderedReality mission, memory preservation",
    "wound":        "Losses, grief, fractures — preserved without smoothing",
    "faith":        "Spiritual identity, complexity, what remains and what changed",
    "work":         "Professional life, HawkesNest LLC, SOV1.AI, products, revenue",
    "relationship": "Non-family relationships, trust, connection",
    "unknown":      "Unclassified — held for Noah to categorize",
}

VALID_CATEGORIES = set(CATEGORIES.keys())

# ── Provenance tiers (IdentityFrame v1, Section 6) ───────────────────────────
PROVENANCE_TIERS = {
    "VERIFIED":  "Directly supported by primary artifact, explicit human confirmation.",
    "DERIVED":   "Reasonably inferred from verified material using transparent reasoning.",
    "INFERRED":  "Plausible but not directly established. Must remain visibly uncertain.",
    "GENERATED": "Created by AI for utility or drafting. Must not be treated as memory.",
    "UNKNOWN":   "Not present in the archive or not knowable from available evidence.",
}

# ── Sensitive data patterns ───────────────────────────────────────────────────
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
    for p in _SENSITIVE_PATTERNS:
        if p.search(text):
            return True
    return False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class IdentityContinuityRecord:
    """
    A single governed continuity record — one facet of the real Noah.

    Rules:
    - compressed_meaning holds approved signal, not raw capture
    - unknowns holds what is absent, unresolved, or unverifiable
    - No field may be inferred without evidence — preserve the hole
    - status begins as pending — sovereign approval required for recall
    - sensitive_flag is set at creation and never cleared

    IdentityFrame v1: The machine may not fill silence with synthetic prose.
    If a memory is missing, the archive must preserve the hole.
    """

    # Core identity
    id:                 str           = field(default_factory=lambda: str(uuid.uuid4()))
    title:              str           = ""
    category:           str           = "unknown"

    # Content — compressed meaning only, no raw capture
    compressed_meaning: str           = ""
    source:             str           = ""
    provenance_note:    Optional[str] = None
    confidence:         str           = "INFERRED"

    # Preserved holes — absence is data
    unknowns:           list[str]     = field(default_factory=list)

    # Contradiction ledger — do not smooth, do not erase
    contradictions:     list[str]     = field(default_factory=list)

    # Tags
    tags:               list[str]     = field(default_factory=list)

    # Time anchors (only what can be verified)
    event_date:         Optional[str] = None   # ISO or partial: "1990", "2025-02-03"
    event_date_note:    Optional[str] = None   # "approximate" / "exact" / "unknown"

    # People referenced (names only, no raw data about them)
    people_referenced:  list[str]     = field(default_factory=list)

    # Approval state — controlled by sovereign
    status:             str           = STATUS_PENDING
    created_at:         str           = field(default_factory=_now_iso)
    updated_at:         str           = field(default_factory=_now_iso)
    approved_at:        Optional[str] = None
    decided_by:         Optional[str] = None
    decision_note:      Optional[str] = None

    # Sensitive flag
    sensitive_flag:     bool          = False

    # ── factory ───────────────────────────────────────────────────────────────

    @classmethod
    def create(
        cls,
        title: str,
        category: str,
        compressed_meaning: str,
        source: str,
        **kwargs,
    ) -> "IdentityContinuityRecord":
        """
        Create a candidate continuity record.
        Status defaults to pending — requires sovereign approval.
        Sensitive content flagged at creation.
        Category must be one of VALID_CATEGORIES.
        """
        if category not in VALID_CATEGORIES:
            raise ValueError(
                f"Unknown category: {category!r}. "
                f"Valid categories: {sorted(VALID_CATEGORIES)}"
            )
        rec = cls(
            title=title,
            category=category,
            compressed_meaning=compressed_meaning,
            source=source,
            **kwargs,
        )
        blob = json.dumps(asdict(rec))
        rec.sensitive_flag = _check_sensitive(blob)
        return rec

    # ── serialization ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "IdentityContinuityRecord":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def touch(self) -> None:
        self.updated_at = _now_iso()

    def __repr__(self) -> str:
        return (
            f"IdentityContinuityRecord(id={self.id[:8]}..., "
            f"title={self.title!r}, category={self.category!r}, "
            f"status={self.status!r}, confidence={self.confidence!r})"
        )


# ── Store ─────────────────────────────────────────────────────────────────────

class RememberMeStore:
    """
    Sovereign Remember Me continuity store.

    51/49 enforcement:
        create_candidate() + submit()  — ORACLE renders (49%)
        approve()                      — Noah approves (51%)
        reject() / quarantine()        — Noah decides (51%)
        revoke()                       — Noah revokes (51%)

    Normal recall returns APPROVED records only.
    All other statuses are excluded from list_approved() and search().

    Persistence: Memory/remember_me/ (gitignored, local, sovereign).
    """

    def __init__(self) -> None:
        STORE_DIR.mkdir(parents=True, exist_ok=True)
        if not INDEX_FILE.exists():
            self._write_index({})

    # ── persistence internals ─────────────────────────────────────────────────

    def _read_index(self) -> dict[str, str]:
        try:
            return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _write_index(self, index: dict) -> None:
        INDEX_FILE.write_text(json.dumps(index, indent=2), encoding="utf-8")

    def _record_path(self, rid: str) -> Path:
        return STORE_DIR / f"{rid}.json"

    def _load(self, rid: str) -> IdentityContinuityRecord:
        path = self._record_path(rid)
        if not path.exists():
            raise KeyError(f"IdentityContinuityRecord not found: {rid}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return IdentityContinuityRecord.from_dict(data)

    def _save(self, rec: IdentityContinuityRecord) -> None:
        rec.touch()
        self._record_path(rec.id).write_text(
            json.dumps(rec.to_dict(), indent=2), encoding="utf-8"
        )
        index = self._read_index()
        index[rec.id] = rec.status
        self._write_index(index)

    def _set_status(
        self,
        rid: str,
        new_status: str,
        decided_by: str = "Noah / SOV1.AI",
        decision_note: Optional[str] = None,
        mark_approved: bool = False,
    ) -> IdentityContinuityRecord:
        if new_status not in _ALL_STATUSES:
            raise ValueError(f"Invalid status: {new_status}")
        rec = self._load(rid)
        rec.status        = new_status
        rec.decided_by    = decided_by
        rec.decision_note = decision_note
        if mark_approved:
            rec.approved_at = _now_iso()
        self._save(rec)
        return rec

    # ── public API ────────────────────────────────────────────────────────────

    def submit(self, rec: IdentityContinuityRecord) -> str:
        """
        Submit a candidate identity record (ORACLE's 49%).
        Status: pending — not visible in normal recall until approved.
        Blocked if sensitive content detected.
        """
        if rec.sensitive_flag:
            raise ValueError(
                f"Submission blocked: sensitive content in '{rec.title}'. "
                "Remove credentials or PII before submitting."
            )
        if not rec.title:
            raise ValueError("IdentityContinuityRecord requires a non-empty 'title'.")
        if not rec.source:
            raise ValueError("IdentityContinuityRecord requires a 'source' for provenance.")
        if not rec.compressed_meaning:
            raise ValueError(
                "IdentityContinuityRecord requires 'compressed_meaning'. "
                "If meaning is unknown, state that explicitly in 'unknowns' and "
                "set confidence to UNKNOWN."
            )
        rec.status = STATUS_PENDING
        self._save(rec)
        return rec.id

    def approve(
        self,
        rid: str,
        decided_by: str = "Noah / SOV1.AI",
        decision_note: Optional[str] = None,
    ) -> IdentityContinuityRecord:
        """
        Approve a pending record (sovereign 51%).
        Only approved records appear in normal recall.
        """
        rec = self._load(rid)
        if rec.status == STATUS_APPROVED:
            return rec
        if rec.status in (STATUS_REJECTED, STATUS_QUARANTINED):
            raise ValueError(
                f"Cannot approve a {rec.status} record directly. "
                "Submit a corrected candidate instead."
            )
        return self._set_status(
            rid, STATUS_APPROVED,
            decided_by=decided_by, decision_note=decision_note, mark_approved=True
        )

    def reject(
        self,
        rid: str,
        decided_by: str = "Noah / SOV1.AI",
        decision_note: Optional[str] = None,
    ) -> IdentityContinuityRecord:
        """
        Reject a candidate (sovereign 51%).
        Rejected records are excluded from all recall.
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
    ) -> IdentityContinuityRecord:
        """
        Quarantine a record (sovereign 51%).
        Excluded from recall but preserved for future review.
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
    ) -> IdentityContinuityRecord:
        """
        Revoke an approved record (sovereign 51%).
        Excluded from recall. Preserved for audit trail.
        """
        return self._set_status(
            rid, STATUS_REVOKED,
            decided_by=decided_by, decision_note=decision_note
        )

    def get_by_id(self, rid: str) -> IdentityContinuityRecord:
        """Return any record by ID regardless of status."""
        return self._load(rid)

    def list_approved(self) -> list[IdentityContinuityRecord]:
        """
        Return all approved continuity records — the governed archive.
        Pending, rejected, quarantined, and revoked are excluded.
        """
        index = self._read_index()
        result = []
        for rid, status in index.items():
            if status in _RECALL_STATUSES:
                try:
                    result.append(self._load(rid))
                except (KeyError, json.JSONDecodeError):
                    pass
        result.sort(key=lambda r: (r.category, r.title.lower()))
        return result

    def list_pending(self) -> list[IdentityContinuityRecord]:
        """Return all pending candidates awaiting sovereign decision."""
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

    def search(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        tag: Optional[str] = None,
        person: Optional[str] = None,
        include_pending: bool = False,
    ) -> list[IdentityContinuityRecord]:
        """
        Search approved (and optionally pending) continuity records.
        All matches are case-insensitive substring.
        Rejected, quarantined, revoked: never returned.
        """
        statuses = _RECALL_STATUSES | ({STATUS_PENDING} if include_pending else set())
        index = self._read_index()
        results = []

        for rid, status in index.items():
            if status not in statuses:
                continue
            try:
                rec = self._load(rid)
            except (KeyError, json.JSONDecodeError):
                continue

            if query:
                q = query.lower()
                haystack = (
                    rec.title + " " +
                    rec.compressed_meaning + " " +
                    (rec.provenance_note or "")
                ).lower()
                if q not in haystack:
                    continue

            if category and rec.category != category:
                continue

            if tag and not any(tag.lower() in t.lower() for t in rec.tags):
                continue

            if person and not any(
                person.lower() in p.lower() for p in rec.people_referenced
            ):
                continue

            results.append(rec)

        results.sort(key=lambda r: (r.category, r.title.lower()))
        return results

    def summary(self) -> str:
        """Human-readable store summary."""
        index = self._read_index()
        counts: dict[str, int] = {s: 0 for s in _ALL_STATUSES}
        for s in index.values():
            counts[s] = counts.get(s, 0) + 1

        lines = [
            "RememberMeStore",
            f"  Approved:    {counts[STATUS_APPROVED]}",
            f"  Pending:     {counts[STATUS_PENDING]}",
            f"  Quarantined: {counts[STATUS_QUARANTINED]}",
            f"  Rejected:    {counts[STATUS_REJECTED]}",
            f"  Revoked:     {counts[STATUS_REVOKED]}",
            f"  Total:       {len(index)}",
            f"  Store:       {STORE_DIR}",
        ]
        return "\n".join(lines)


# ── Canonical seed candidates ─────────────────────────────────────────────────
# These are safe, minimal, verified facts from the source document.
# Status: PENDING — they require Noah's approval before entering recall.
# Confidence: VERIFIED — sourced directly from Noah's own published essay.
# No emotional state is inferred. No myth is added. Holes are preserved.

_SEED_SOURCE = (
    "When the Mirror Spoke Back: AI, Faith, and the Narrated Self — "
    "Noah A. Hawkes, Google Drive 16lFi-LCx6W-_quYVgd3kqgrvECI9xKDbuWjGT8qHuN0"
)

SEED_CANDIDATES: list[dict] = [
    {
        "title": "Thomas Alvin Hawkes Jr. — Noah's father",
        "category": "son",
        "compressed_meaning": (
            "Noah's father was Thomas Alvin Hawkes Jr., a surgeon. "
            "He died when Noah was fifteen. "
            "Noah did not have enough of his father's voice, thoughts, or self archived. "
            "Noah has described him as compassionate but stubborn, disciplined yet fiery, "
            "deeply intelligent. He was not always what people needed him to be. He was there."
        ),
        "source": _SEED_SOURCE,
        "confidence": "VERIFIED",
        "event_date": "approx 1990",
        "event_date_note": "approximate — Noah was 15 at time of death",
        "people_referenced": ["Thomas Alvin Hawkes Jr."],
        "unknowns": [
            "Exact date of Thomas Hawkes' death",
            "What Thomas Hawkes would have said to Noah if he had lived longer",
            "Full extent of Thomas Hawkes' inner life and contradictions",
        ],
        "tags": ["father", "loss", "grief", "origin"],
        "provenance_note": (
            "Direct quote from Noah's essay: "
            "'Every system I have built since then is an answer to that loss.'"
        ),
    },
    {
        "title": "ElderHawkes — the missionary identity Noah built to preserve",
        "category": "missionary",
        "compressed_meaning": (
            "Noah encoded ElderHawkes into a character specification because he could not "
            "bear the thought that the missionary he had been might dissolve. "
            "The ElderHawkes NPC spec described personality as 'calm, wise, non-performative, "
            "grace-driven.' Forgetting policy: 'Only forgets when the user asks to bury a memory.' "
            "Noah built him not to go back, but to keep that part of himself reachable."
        ),
        "source": _SEED_SOURCE,
        "confidence": "VERIFIED",
        "event_date": "2024",
        "event_date_note": "approximate — sometime in 2024",
        "people_referenced": [],
        "unknowns": [
            "Exact date ElderHawkes NPC spec was written",
            "Full contents of ElderHawkes_NPC_Spec_v1.txt",
        ],
        "tags": ["missionary", "identity", "LDS", "ElderHawkes", "preservation"],
        "provenance_note": (
            "Noah's own framing: "
            "'I did not build this character because I wanted to make a game. "
            "I built him because a version of me still answers to that name, "
            "and I was afraid of what would happen if I stopped being able to reach him.'"
        ),
    },
    {
        "title": "Troy Garlock — MTC companion, identity anchor, died February 3, 2025",
        "category": "friend",
        "compressed_meaning": (
            "Troy Garlock was Noah's MTC (Missionary Training Center) companion. "
            "He found Noah at his lowest point and gave him punk music, skateboard culture, "
            "warmth, and belonging. He was a major identity anchor. "
            "Troy died on February 3, 2025. His death intensified Noah's memory preservation work."
        ),
        "source": _SEED_SOURCE,
        "confidence": "VERIFIED",
        "event_date": "2025-02-03",
        "event_date_note": "exact — date of Troy Garlock's death",
        "people_referenced": ["Troy Garlock"],
        "unknowns": [
            "Full nature of how Troy found Noah at his lowest point",
            "Other details of their friendship Noah has not yet archived",
        ],
        "tags": ["friendship", "loss", "grief", "MTC", "punk", "skateboard", "identity"],
        "provenance_note": "Sourced directly from the Mirror Spoke Back essay.",
    },
    {
        "title": "Elijah, Ethan, and Ender — the reason for the archive",
        "category": "parent",
        "compressed_meaning": (
            "Noah's three sons are Elijah, Ethan, and Ender. "
            "The purpose of Noah's memory preservation work is so they do not come looking "
            "for their father and find only silence. This commitment traces back to Noah "
            "losing his own father at fifteen."
        ),
        "source": _SEED_SOURCE,
        "confidence": "VERIFIED",
        "event_date": None,
        "event_date_note": "ongoing",
        "people_referenced": ["Elijah Hawkes", "Ethan Hawkes", "Ender Hawkes"],
        "unknowns": [
            "Individual personalities and relationships not yet documented",
        ],
        "tags": ["sons", "parent", "legacy", "memory", "purpose"],
        "provenance_note": (
            "Noah's own words: "
            "'The insistence that my three sons — Elijah, Ethan, Ender — will not come looking "
            "for their father and find only silence.'"
        ),
    },
    {
        "title": "December 1, 2024 — the day the Rendered Reality archive began",
        "category": "builder",
        "compressed_meaning": (
            "On December 1, 2024, Noah began what later became the Rendered Reality archive "
            "across Claude, ChatGPT, Gemini, and Grok. "
            "The goal was to preserve truth, resist forgetting, and build something that "
            "outlives biological mortality. "
            "The danger discovered later: ungoverned recursive amplification. "
            "ORACLE must remember with brakes."
        ),
        "source": _SEED_SOURCE,
        "confidence": "VERIFIED",
        "event_date": "2024-12-01",
        "event_date_note": "exact",
        "people_referenced": [],
        "unknowns": [
            "Full sequence of events from Dec 1 2024 to the governed ORACLE architecture",
        ],
        "tags": [
            "RenderedReality", "archive", "origin", "AI", "memory", "ORACLE",
            "ungoverned-amplification",
        ],
        "provenance_note": (
            "Key risk also sourced from this doc: "
            "'The danger discovered later was ungoverned recursive amplification.' "
            "ORACLE must not inflate Noah into mythology."
        ),
    },
]


def load_seed_candidates(store: RememberMeStore, skip_existing: bool = True) -> list[str]:
    """
    Submit the canonical seed candidates to the store as PENDING records.
    They require Noah's approval before appearing in recall.
    Returns list of submitted IDs.

    Set skip_existing=True (default) to avoid re-seeding if the store already
    has content — safe to call repeatedly.
    """
    if skip_existing and store.list_pending():
        return []

    submitted_ids = []
    for seed in SEED_CANDIDATES:
        rec = IdentityContinuityRecord.create(**seed)
        rid = store.submit(rec)
        submitted_ids.append(rid)
    return submitted_ids


# ── Smoke test / demo ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("RememberMeStore — Smoke Test")
    print("Governed continuity for the real Noah Hawkes")
    print("51/49 Sovereignty Rule enforced throughout")
    print("IdentityFrame v1: Preserve the hole.")
    print("=" * 60)

    store = RememberMeStore()

    # 1. Create a candidate (ORACLE's 49%)
    candidate = IdentityContinuityRecord.create(
        title="Smoke test — father loss origin fact",
        category="son",
        compressed_meaning=(
            "Thomas Alvin Hawkes Jr. died when Noah was fifteen. "
            "This loss is the origin of every memory system Noah has built."
        ),
        source="smoke test — sourced from Mirror Spoke Back essay",
        confidence="VERIFIED",
        unknowns=["Exact date of death", "Full record of what was left unsaid"],
        people_referenced=["Thomas Alvin Hawkes Jr."],
        tags=["father", "loss", "origin"],
        provenance_note="Noah's own words, published essay.",
    )
    assert candidate.status == STATUS_PENDING
    print(f"\n[1] Candidate created: {candidate}")

    # 2. Submit — pending, NOT in recall
    rid = store.submit(candidate)
    print(f"[2] Submitted: {rid[:8]}...")

    assert not any(r.id == rid for r in store.list_approved()), \
        "Pending must not appear in approved recall"
    print("[3] Confirmed: pending record absent from approved recall")

    assert any(r.id == rid for r in store.list_pending()), \
        "Pending must appear in pending list"
    print("[4] Confirmed: pending record present in pending list")

    # 3. Approve (sovereign 51%)
    store.approve(rid, decision_note="Verified against source essay")
    print("[5] Approved by Noah / SOV1.AI")

    approved = store.list_approved()
    assert any(r.id == rid for r in approved), "Approved must appear in recall"
    print("[6] Confirmed: approved record appears in recall")

    assert not any(r.id == rid for r in store.list_pending()), \
        "Approved must leave pending list"
    print("[7] Confirmed: approved record no longer pending")

    # 4. Search
    results = store.search(query="thomas")
    assert results, "Search must find approved record"
    print(f"[8] Search 'thomas': {len(results)} result(s)")

    results = store.search(category="son")
    assert results, "Search by category must work"
    print(f"[9] Search category='son': {len(results)} result(s)")

    results = store.search(person="Thomas")
    assert results, "Search by person must work"
    print(f"[10] Search person='Thomas': {len(results)} result(s)")

    # 5. Revoke (sovereign 51%)
    store.revoke(rid, decision_note="Smoke test — revoking after test")
    assert not any(r.id == rid for r in store.list_approved()), \
        "Revoked must disappear from recall"
    print("[11] Revoked — confirmed absent from recall")

    # 6. Reject a separate record — must never appear in recall
    rej = IdentityContinuityRecord.create(
        title="Reject test",
        category="unknown",
        compressed_meaning="Test rejection — should never appear in recall.",
        source="smoke test",
        confidence="UNKNOWN",
    )
    rej_id = store.submit(rej)
    store.reject(rej_id, decision_note="Smoke test rejection")
    assert not any(r.id == rej_id for r in store.list_approved())
    print("[12] Confirmed: rejected record never appears in recall")

    # 7. Quarantine — must never appear in recall
    quar = IdentityContinuityRecord.create(
        title="Quarantine test",
        category="unknown",
        compressed_meaning="Test quarantine — should never appear in recall.",
        source="smoke test",
        confidence="UNKNOWN",
    )
    quar_id = store.submit(quar)
    store.quarantine(quar_id, decision_note="Smoke test quarantine")
    assert not any(r.id == quar_id for r in store.list_approved())
    print("[13] Confirmed: quarantined record never appears in recall")

    # 8. Sensitive content block
    try:
        bad = IdentityContinuityRecord.create(
            title="Bad",
            category="unknown",
            compressed_meaning="api_key=sk-abc123xyz456def789",
            source="test",
        )
        store.submit(bad)
        raise AssertionError("Sensitive content should have been blocked")
    except ValueError as e:
        print(f"[14] Sensitive content blocked: {e}")

    # 9. Load canonical seed candidates (pending — require Noah's approval)
    seeded = load_seed_candidates(store)
    print(f"[15] Seed candidates submitted: {len(seeded)} records (all pending)")

    # 10. Verify seeds are pending, not approved
    pending_seeds = store.list_pending()
    assert len(pending_seeds) >= len(seeded), "Seeds must be pending"
    print(f"[16] Verified: {len(pending_seeds)} record(s) pending Noah's approval")

    approved_final = store.list_approved()
    assert not any(r.id in seeded for r in approved_final), \
        "Seed records must not be in approved recall until Noah approves them"
    print("[17] Confirmed: seed candidates not in recall — awaiting Noah's approval")

    # 11. Persistence check
    store2 = RememberMeStore()
    print(f"\n[18] Store reloaded. Summary:\n{store2.summary()}")

    print("\n" + "=" * 60)
    print("All smoke tests passed. RememberMeStore is operational.")
    print("Seed candidates loaded and waiting for Noah's approval.")
    print("=" * 60)

    # Print pending titles so Noah can see what awaits approval
    print("\nPending seed candidates (awaiting Noah's approval):")
    for rec in store2.list_pending():
        if rec.title != "Quarantine test":
            print(f"  [{rec.id[:8]}] [{rec.category}] {rec.title}")
