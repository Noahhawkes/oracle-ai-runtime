"""Forensic Affective Provenance pass over Noah's corpus.

Harvests candidate affective events (the SHAPE of faith/hope/charity/benevolence/
love as value-to-action, per docs/EMOTIONAL_CORE_TRANSMISSION) from Noah's authored
writing, with raw receipts + provenance + preserved holes. NO sentiment scores.

DRY RUN by default: writes a JSON report of what it found, stores nothing durable.
--apply writes the candidate events to Memory/affective_events/ (candidate-only;
ORACLE promotes nothing to canon without Noah).

Usage:
  python tools/extract_affective_layer.py            # preview + report
  python tools/extract_affective_layer.py --apply     # persist candidates
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))
import affective_provenance as ap  # noqa: E402

# Noah-authored source families first (his own voice = highest-value emotional data)
SOURCE_DIRS = [
    ROOT / "data" / "domains" / "documents" / "extracted" / "journals_repo",
    ROOT / "data" / "domains" / "documents" / "extracted" / "renderedreality",
    ROOT / "docs",  # includes the Emotional Core Transmission + reader's reports
]


def _iter_texts():
    for d in SOURCE_DIRS:
        if not d.exists():
            continue
        for f in d.rglob("*"):
            if f.suffix.lower() in (".txt", ".md") and f.is_file():
                try:
                    yield f, f.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue


def main(apply: bool) -> int:
    all_events = []
    per_file = []
    for f, text in _iter_texts():
        # journals/renderedreality are Noah's own voice; docs are mixed
        noah = None if "docs" in f.parts else True
        evs = ap.extract_affective_events(text, source_id=str(f.relative_to(ROOT)),
                                          noah_authored=noah)
        # keep the load-bearing ones (strong/partial) to avoid keyword noise
        evs = [e for e in evs if e.evidence_strength in ("strong", "partial")]
        if evs:
            per_file.append((f.name, len(evs)))
            all_events.extend(evs)

    summary = ap.summarize(all_events)
    strong = [e for e in all_events if e.evidence_strength == "strong"]
    print(("APPLY" if apply else "DRY RUN") + " — Affective Provenance harvest")
    print(f"  files with events : {len(per_file)}")
    print(f"  total candidates  : {summary['total']}")
    print(f"  by virtue family  : {summary['by_virtue_family']}")
    print(f"  by evidence       : {summary['by_evidence_strength']}")
    print(f"\n  sample STRONG events (receipt + shape), first 6:")
    for e in strong[:6]:
        print(f"   [{e.virtue_family} -> {e.target}] "
              f"action={e.has_action} cost={e.has_cost} conflict={e.has_conflict}")
        print(f"      \"{e.exact_text[:150]}\"")

    if apply:
        outdir = ROOT / "Memory" / "affective_events"
        outdir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        payload = {"schema": "affective_event.v1", "generated_utc": stamp,
                   "canonical_status": "candidate",
                   "note": "shape-of-emotion candidates; NOT sentiment; Noah promotes to canon",
                   "summary": summary,
                   "events": [e.to_dict() for e in all_events]}
        out = outdir / f"affective_harvest_{stamp}.json"
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
        print(f"\n  WROTE {len(all_events)} candidate events -> {out.relative_to(ROOT)}")
    else:
        print(f"\n  {summary['total']} candidates found. Re-run with --apply to persist them.")
    return 0


if __name__ == "__main__":
    sys.exit(main(apply="--apply" in sys.argv))
