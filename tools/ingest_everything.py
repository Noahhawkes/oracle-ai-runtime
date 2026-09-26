"""INGEST EVERYTHING (guarded) — feed Noah's local corpus into ORACLE's recall so
she can actually work from his life, not from a blank slate.

Runs through her OWN pipeline (core/corpus_ingest -> Light Compression Law), which
is DRY RUN by default and automatically GATES sensitive files (financial, medical,
private) out of recall. It never promotes canon and never stores a gated file.

Provenance note: this ingester treats each DOCUMENT as one candidate. AI CHAT
exports (ChatGPT/Grok logs) and screen-OCR memories need the chat-aware / OCR
importers so each turn is labeled NOAH SAID vs AI GENERATED (Law V). Those are
staged separately; this runner is for the document corpus.

Usage:
  python tools/ingest_everything.py            # DRY RUN — preview + guardrail counts
  python tools/ingest_everything.py --apply     # store the clean candidates in recall

Run --apply AFTER a relight so it lands in the live runtime. Nothing sensitive is
stored; only 'candidate' files are committed, 'gated_sensitive' are always blocked.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))
import corpus_ingest as ci  # noqa: E402

# Local document sources. (Drive G:\ exports + Perfect Memory OCR are handled by
# ORACLE's runtime, which can reach G:\, and by the chat-aware importer.)
SOURCE_ROOTS = [
    ROOT / "data" / "domains" / "documents" / "extracted",
]


def main(apply: bool) -> int:
    grand = {"seen": 0, "candidate": 0, "gated_sensitive": 0,
             "discard_noise": 0, "unknown": 0, "committed": 0}
    for root in SOURCE_ROOTS:
        if not root.exists():
            print(f"  (skip, not found) {root}")
            continue
        m = ci.ingest_corpus(str(root), commit=apply, write_receipt=apply, max_files=100000)
        if "error" in m:
            print(f"  ERROR {root}: {m['error']}")
            continue
        c = m["counts"]
        for k in grand:
            grand[k] += c.get(k, 0)
        print(f"  {root.name}: seen={c['seen']} candidates={c.get('candidate',0)} "
              f"GATED_sensitive={c.get('gated_sensitive',0)} committed={c.get('committed',0)}")
        if apply and m.get("receipt_path"):
            print(f"    receipt: {m['receipt_path']}")

    print("=" * 56)
    mode = "APPLIED (stored in recall)" if apply else "DRY RUN (nothing stored)"
    print(f"INGEST EVERYTHING — {mode}")
    print(f"  files seen            : {grand['seen']}")
    print(f"  clean -> recall        : {grand['candidate']}")
    print(f"  GATED sensitive (safe) : {grand['gated_sensitive']}   [never enters recall]")
    print(f"  noise / unreadable     : {grand['discard_noise'] + grand['unknown']}")
    print(f"  actually stored        : {grand['committed']}")
    if not apply and grand["candidate"]:
        print(f"\n{grand['candidate']} clean candidates ready. Re-run with --apply to store them.")
    return 0


if __name__ == "__main__":
    sys.exit(main(apply="--apply" in sys.argv))
