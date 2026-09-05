"""Seed ORACLE's `people` table + durable identity facts with Noah's ACTUAL people,
so "who is Ashley" resolves to his wife, not a Mass Effect character.

Law XIII (people are not record types) + Law IV (preserve the hole) + Law V
(label provenance). Only verified relationships are asserted; unknown ones are
recorded AS unknown, never guessed. ORACLE previously hallucinated Ashley as a
game character and fabricated Elijah as a "brother" — both are corrected here to
the truth or to an explicit UNKNOWN.

DRY RUN by default (prints the plan). --apply writes. Running --apply is Noah's
own authorization of these facts. Run AFTER a relight so it lands live.

Usage:
  python tools/seed_people.py            # show the plan, write nothing
  python tools/seed_people.py --apply     # register the people + facts
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "Memory" / "oracle_memory.db"


def _now():
    return datetime.now(timezone.utc).isoformat()


# (name, role) — role phrasing is honest: verified relationships stated,
# unknowns marked UNKNOWN, never guessed.
PEOPLE = [
    ("Noah Alexander Hawkes Sr.", "Noah.Physical - the human operator, authorial authority, final approval"),
    ("Ashley Hawkes", "Noah's wife (SOV2 co-sovereign). NOT his mother, NOT a game character."),
    ("Elijah Hawkes", "Person Noah references as 'Eli'. Relationship to Noah UNKNOWN - do NOT assume brother."),
    ("Thomas Alvin Hawkes Jr.", "Noah's father. Died 1997 when Noah was fifteen."),
    ("Ethan", "Person Noah references (garage/bike, EcoWater context). Relationship UNKNOWN."),
]

# (fact_text, source_type, confidence)
FACTS = [
    ("Ashley Hawkes is Noah's wife (SOV2 co-sovereign). She is NOT Noah's mother and NOT a Mass Effect / video-game character; that was a model hallucination.", "noah_stated", 0.95),
    ("Elijah Hawkes is a person Noah references as 'Eli'. His relationship to Noah is UNKNOWN and must not be assumed. ORACLE previously fabricated 'brother' - that was a hallucination, not a record.", "noah_stated_hole", 0.5),
    ("Thomas Alvin Hawkes Jr. is Noah's father. He died in 1997, when Noah was fifteen.", "noah_authored_journal", 0.9),
    ("Noah's full name is Noah Alexander Hawkes Sr. He is Noah.Physical, the authorial authority and final approver.", "durable_memory_verified", 0.95),
    ("When asked 'who is <a name Noah uses>', ORACLE must retrieve from durable memory FIRST and answer from the record or say UNKNOWN - never fill the gap with a model training prior (e.g. a game character).", "oracle_law_III", 0.99),
]


def main(apply: bool) -> int:
    if not DB.exists():
        print(f"no db at {DB}"); return 1
    conn = sqlite3.connect(str(DB)) if apply else sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    existing = {r["name"] for r in conn.execute("SELECT name FROM people")}
    p_new = [p for p in PEOPLE if p[0] not in existing]

    print(("APPLY" if apply else "DRY RUN") + " - register people:")
    for name, role in PEOPLE:
        tag = "exists" if name in existing else ("WRITE" if apply else "would add")
        print(f"  [{tag}] {name}  ->  {role}")
    print(f"\n{('APPLY' if apply else 'DRY RUN')} - durable identity facts: {len(FACTS)}")
    for f in FACTS:
        print(f"  - ({f[1]}, conf {f[2]}) {f[0][:80]}...")

    if apply:
        for name, role in p_new:
            conn.execute("INSERT INTO people (name, role, created_at) VALUES (?,?,?)",
                         (name, role, _now()))
        cols = {r[1] for r in conn.execute("PRAGMA table_info(durable_facts)")}
        for text, stype, conf in FACTS:
            row = {"fact_text": text, "source_type": stype, "observed_at": _now(),
                   "confidence": conf, "canonical_status": "candidate",
                   "approval_status": "noah_seeded", "created_at": _now(),
                   "authority_rank": 90, "provenance_json": '{"seeded_by":"seed_people.py","authority":"Noah.Physical"}'}
            row = {k: v for k, v in row.items() if k in cols}
            keys = ",".join(row); qs = ",".join("?" * len(row))
            conn.execute(f"INSERT INTO durable_facts ({keys}) VALUES ({qs})", list(row.values()))
        conn.commit()
        print(f"\nWROTE {len(p_new)} people + {len(FACTS)} facts.")
    else:
        print(f"\n{len(p_new)} people would be added. Re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main(apply="--apply" in sys.argv))
