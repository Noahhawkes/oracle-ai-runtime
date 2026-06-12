"""
core/meaning_engine.py — ORACLE Meaning Engine v0.1

Watches for OBS recording activity and automatically compresses sessions
into meaning candidates for Noah's approval.

Two modes:
  1. watch  — poll OBS logs for new sessions, fire ingest when a new log appears
  2. ingest — one-shot: scan all OBS logs and videos now

This is the module the RENDERED_REALITY_MISSION.md describes as planned but
not yet implemented. It is now implemented.

Pipeline:
  OBS records -> log written -> watcher detects new log -> OBSSession.compressed_meaning()
  -> IdentityContinuityRecord (PENDING) -> Noah approves -> durable memory

CLI:
  python core/meaning_engine.py --watch           # live watcher (polls every 60s)
  python core/meaning_engine.py --ingest          # one-shot scan
  python core/meaning_engine.py --ingest --dry    # preview without writing
  python core/meaning_engine.py --status          # show last N candidates
"""

from __future__ import annotations

import sys
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path

# ── Root bootstrap ─────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

OBS_LOG_DIR = Path.home() / "AppData" / "Roaming" / "obs-studio" / "logs"
POLL_INTERVAL_SECONDS = 60
STATE_FILE = ROOT / "state" / "meaning_engine_state.json"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_seen_logs() -> set[str]:
    import json
    if STATE_FILE.exists():
        try:
            return set(json.loads(STATE_FILE.read_text(encoding="utf-8")).get("seen_logs", []))
        except Exception:
            pass
    return set()


def _save_seen_logs(seen: set[str]) -> None:
    import json
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps({"seen_logs": sorted(seen), "updated": datetime.now(timezone.utc).isoformat()}, indent=2),
        encoding="utf-8",
    )


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


# ── Core ingest call ──────────────────────────────────────────────────────────

def ingest_new_logs(new_paths: list[Path], dry_run: bool = False) -> list[str]:
    """Run obs_ingest on a specific set of log paths. Returns candidate IDs."""
    try:
        from obs_ingest import ingest_logs
    except ImportError:
        print("[meaning_engine] obs_ingest not available — check core/ path")
        return []

    if not new_paths:
        return []

    print(f"[{_now()}] meaning_engine: ingesting {len(new_paths)} new OBS log(s)")
    ids = ingest_logs(log_paths=new_paths, dry_run=dry_run)
    if ids:
        print(f"[{_now()}] meaning_engine: created {len(ids)} memory candidate(s) — PENDING Noah approval")
    return ids


# ── Watch mode ────────────────────────────────────────────────────────────────

def watch(poll_interval: int = POLL_INTERVAL_SECONDS) -> None:
    """
    Poll OBS log directory for new log files.
    When a new log appears (OBS started a session), ingest it immediately.
    Runs forever — call from oracle.py background thread or standalone.
    """
    seen = _load_seen_logs()
    print(f"[{_now()}] meaning_engine: watching {OBS_LOG_DIR} (poll every {poll_interval}s)")
    print(f"[{_now()}] meaning_engine: {len(seen)} previously seen log(s)")

    if not OBS_LOG_DIR.exists():
        print(f"[{_now()}] meaning_engine: OBS log dir not found — {OBS_LOG_DIR}")
        print(f"[{_now()}] meaning_engine: will retry each poll cycle")

    while True:
        try:
            _poll_once(seen)
        except Exception as e:
            print(f"[{_now()}] meaning_engine: poll error — {e}")

        try:
            time.sleep(poll_interval)
        except KeyboardInterrupt:
            print(f"\n[{_now()}] meaning_engine: stopped by user")
            _save_seen_logs(seen)
            break


def _poll_once(seen: set[str]) -> None:
    if not OBS_LOG_DIR.exists():
        return

    all_logs = sorted(OBS_LOG_DIR.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    new_logs = [p for p in all_logs if p.name not in seen]

    if new_logs:
        ids = ingest_new_logs(new_logs)
        for p in new_logs:
            seen.add(p.name)
        _save_seen_logs(seen)
        if ids:
            _notify_oracle(ids)
    else:
        pass  # quiet poll — nothing new


def _notify_oracle(candidate_ids: list[str]) -> None:
    """
    Post a notification to oracle.py that new meaning candidates are pending.
    Uses the Messages/ channel if available, otherwise prints.
    """
    try:
        msg_path = ROOT / "Messages" / "oracle_inner.md"
        if msg_path.exists():
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            entry = (
                f"\n---\n**[{ts}] MEANING ENGINE — OBS session(s) recorded**\n"
                f"New memory candidate(s) pending approval: {', '.join(c[:8] for c in candidate_ids)}\n"
                f"Run: `python core/oracle.py --pending` to review.\n"
            )
            with open(msg_path, "a", encoding="utf-8") as f:
                f.write(entry)
            print(f"[{_now()}] meaning_engine: notified oracle_inner.md")
    except Exception as e:
        print(f"[{_now()}] meaning_engine: could not notify oracle — {e}")


# ── Status mode ───────────────────────────────────────────────────────────────

def show_status() -> None:
    try:
        from remember_me import RememberMeStore, STATUS_PENDING
        store = RememberMeStore()
        candidates = [r for r in store.list_all() if r.status == STATUS_PENDING and "obs" in (r.tags or [])]
        print(f"\nOBS meaning candidates pending approval: {len(candidates)}")
        for c in candidates[-10:]:
            print(f"  [{c.id[:8]}] {c.title} — {c.compressed_meaning[:80]}...")
    except ImportError:
        print("[meaning_engine] remember_me not available")

    seen = _load_seen_logs()
    print(f"\nOBS logs tracked: {len(seen)}")
    all_logs = sorted(OBS_LOG_DIR.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True) if OBS_LOG_DIR.exists() else []
    print(f"OBS logs on disk: {len(all_logs)}")
    if all_logs:
        print(f"Most recent: {all_logs[0].name}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="ORACLE Meaning Engine — OBS session recorder")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--watch",   action="store_true", help="Live watcher mode (polls every 60s)")
    group.add_argument("--ingest",  action="store_true", help="One-shot: ingest all OBS logs now")
    group.add_argument("--status",  action="store_true", help="Show pending candidates and state")
    parser.add_argument("--dry",    action="store_true", help="Dry run — preview without writing")
    parser.add_argument("--poll",   type=int, default=POLL_INTERVAL_SECONDS, help="Poll interval in seconds")
    args = parser.parse_args()

    if args.watch:
        watch(poll_interval=args.poll)
    elif args.ingest:
        from obs_ingest import find_obs_logs
        all_logs = find_obs_logs()
        print(f"Found {len(all_logs)} OBS log(s)")
        ingest_new_logs(all_logs, dry_run=args.dry)
    elif args.status:
        show_status()


if __name__ == "__main__":
    main()
