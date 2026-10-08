"""Proof harness: build real RelationshipState records from Noah's own corpus.

Runs the Affective Provenance harvest live over Noah's authored sources, then
assembles relationship structures for the sealed family. Demonstrates that a
name becomes accumulated, receipted history. Read-only. Writes nothing durable.

Usage:  python tools/prove_relationship_state.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

# Windows consoles default to cp1252 and choke on emoji found in the corpus.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _safe(s: str) -> str:
    return s.encode("ascii", "replace").decode("ascii")
import affective_provenance as ap        # noqa: E402
import relationship_state as rs          # noqa: E402

SOURCE_DIRS = [
    ROOT / "data" / "domains" / "documents" / "extracted" / "journals_repo",
    ROOT / "data" / "domains" / "documents" / "extracted" / "renderedreality",
    ROOT / "docs",
]

# sealed family (role from the people table / Noah's authority)
PEOPLE = [
    ("Ashley", "WIFE (SOV2)", ["my wife"]),
    ("Ender", "SON", ["my son"]),
    ("Ellie", "ORACLE voice / heroine", ["Ellie.AI"]),
    ("Grimthul", "archetype: Holy Paladin (protector/healer)", ["Grim"]),
]


def _harvest():
    events = []
    for d in SOURCE_DIRS:
        if not d.exists():
            continue
        for f in d.rglob("*"):
            if f.suffix.lower() in (".txt", ".md") and f.is_file():
                try:
                    text = f.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                noah = None if "docs" in f.parts else True
                events.extend(ap.extract_affective_events(
                    text, source_id=str(f.relative_to(ROOT)), noah_authored=noah))
    return events


def main() -> int:
    events = _harvest()
    print(f"harvested {len(events)} affective events across the corpus\n")
    for identity, role, aliases in PEOPLE:
        r = rs.build_relationship(identity, events, role=role, aliases=aliases)
        print(f"=== {identity}  [{role}]  ({r.attachment} attachment, "
              f"{r.shared_event_count} events) ===")
        print(f"  current_state : {r.current_state}")
        for label, bucket in (("sacrifice", r.sacrifices), ("commitment", r.commitments),
                              ("forgiveness", r.forgiveness), ("joy", r.joys),
                              ("loss", r.losses), ("conflict", r.unresolved_conflicts)):
            if bucket:
                print(f"  {label:11}: \"{_safe(bucket[0][:120])}\"")
        if r.attachment_receipts:
            print(f"  attach recpt: \"{_safe(r.attachment_receipts[0][:120])}\"")
        print(f"  holes        : {r.holes}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
