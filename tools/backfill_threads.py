"""One-time backfill: turn recoverable historical sessions into durable threads.

Safe by default: prints the plan and writes NOTHING unless you pass --apply.
Idempotent, additive, invents nothing (existing threads skipped, only NULL
thread_id messages attached, no content rewritten).

Run this AFTER a relight, once tools/relight_prove.py shows receipt #1 green
(so you are backfilling on the proven new code, not the stale process).

Usage:
  python tools/backfill_threads.py           # DRY RUN - shows the plan, writes nothing
  python tools/backfill_threads.py --apply    # actually create the threads
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "Memory" / "oracle_memory.db"
sys.path.insert(0, str(ROOT / "core"))
import thread_registry as tr  # noqa: E402


def main(apply: bool) -> int:
    if not DB.exists():
        print(f"no db at {DB}")
        return 1
    # read-write only when applying; read-only for the dry run
    conn = sqlite3.connect(str(DB)) if apply else sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    res = tr.backfill_threads_from_sessions(conn, dry_run=not apply)
    print(("APPLIED" if apply else "DRY RUN") + " backfill:")
    for k, v in res.items():
        print(f"  {k}: {v}")
    if not apply and res["would_create"]:
        print(f"\n{res['would_create']} threads would be created. Re-run with --apply to write them.")
    return 0


if __name__ == "__main__":
    sys.exit(main(apply="--apply" in sys.argv))
