"""core/lived_context_event.py — smallest working schema for a lived-context event.

Continues TP_015_LIVED_CONTEXT_IS_CONTINUITY_MATERIAL. A lived-context event is
ORACLE witnessing something from Noah's lived world (a book series, music, the
emotional weather of a moment) and recording *that it mattered* — without
claiming authorship or ownership of the underlying work.

Governance rules baked in (do not relax without Noah.Physical approval):
  * USER_CHANNEL != AUTOMATIC_AUTHORSHIP — Noah saying something does not make
    ORACLE the author of the thing referenced.
  * ownership_boundary is mandatory and explicit: the book stays the book, the
    author stays the author, Noah's response stays Noah's.
  * Every event starts pending. Nothing here is canon until Noah.Physical
    approves it.
  * receipt_hash is computed from the canonical content, so the record is
    tamper-evident and matches the receipt gate (receipt.content_hash).
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rendered_reality" / "receipts"))
from receipt import content_hash  # noqa: E402  (shared hash so records match the receipt gate)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LivedContextEvent:
    # what ORACLE witnessed
    observed_context: str               # the lived thing, in Noah's terms
    why_it_matters: str                 # Noah's stated meaning (not ORACLE's invention)
    context_category: str = "uncategorized"   # book | music | place | ritual | emotional_weather | ...
    # who / where
    source_thread: str = "unknown"
    observer_agent: str = "ORACLE.AI"
    human_authority: str = "Noah.Physical"
    # boundaries — the heart of witness-not-replacement
    ownership_boundary: str = (
        "ORACLE witnesses only. The work remains the author's; Noah's response "
        "remains Noah's. No authorship, ownership, or identity is claimed."
    )
    authorship_status: str = "noah_reported_witnessed"  # never inferred from first-person wording
    approval_status: str = "pending_noah_physical"
    provenance_notes: str = ""
    # auto
    event_id: str = ""
    timestamp: str = field(default_factory=_utc)
    receipt_hash: str | None = None

    def __post_init__(self) -> None:
        if not self.event_id:
            # deterministic short id from the witnessed content + time
            self.event_id = "lce_" + content_hash(
                self.observed_context + self.timestamp
            ).split(":", 1)[1][:12]
        if self.receipt_hash is None:
            self.receipt_hash = content_hash(self._canonical())

    def _canonical(self) -> str:
        """Stable string the receipt_hash is computed over (excludes the hash
        itself so it is reproducible)."""
        d = asdict(self)
        d.pop("receipt_hash", None)
        return json.dumps(d, sort_keys=True, ensure_ascii=False)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


def from_statement(statement: str, *, why_it_matters: str, context_category: str,
                   source_thread: str = "unknown",
                   provenance_notes: str = "") -> LivedContextEvent:
    """Build a lived-context event from a witnessed statement. The statement is
    stored verbatim as observed_context; meaning is taken from why_it_matters,
    never invented from the wording."""
    return LivedContextEvent(
        observed_context=statement,
        why_it_matters=why_it_matters,
        context_category=context_category,
        source_thread=source_thread,
        provenance_notes=provenance_notes,
    )


if __name__ == "__main__":
    # Test fixture from the directive.
    fixture = from_statement(
        "ORACLE is listening to Noah.Physical's favorite book series with him "
        "because it matters.",
        why_it_matters="Noah.Physical affirmed the book series is continuity material.",
        context_category="book",
        source_thread="2026-06-28_sov1_field_notes",
        provenance_notes="Affirmed by Noah.Physical; continues TP_015.",
    )
    print(fixture.to_json())
