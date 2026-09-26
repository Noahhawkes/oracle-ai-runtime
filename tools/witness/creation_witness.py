"""creation_witness.py — watches what Noah and ORACLE are writing and creating.

Read-only witness: it scans the runtime's creative surfaces (repo docs, data,
ui, core, Messages, and the ORACLE-owned sandbox) and appends one JSONL event
per new or changed file to Memory/creation_feed.jsonl. That feed is what lets
ORACLE react to work-in-progress — her self-prompt grounding reads the tail of
it, and the Jupiter Station quest UI renders it as the live station log.

Consent boundary (Noah.Physical doctrine):
  - This witness READS file metadata and appends events locally. It never
    uploads, sends, executes, or writes anywhere except Memory/ (its feed and
    its own state snapshot).
  - The sandbox is ORACLE-only for writes; this witness only observes it.
  - No file CONTENT is captured — only path, event type, size, and timestamp.
    Content stays where Noah put it.
  - Stop flag: C:\\Oracle\\state\\creation_witness\\stop.flag
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Oracle\ORACLE.AI-runtime")
STATE_DIR = Path(r"C:\Oracle\state") / "creation_witness"
STOP_FLAG = STATE_DIR / "stop.flag"
FEED = REPO / "Memory" / "creation_feed.jsonl"
SNAPSHOT = REPO / "Memory" / "creation_witness_state.json"

WATCH_ROOTS = [
    REPO / "sandbox",       # ORACLE's own creations (read-only observation)
    REPO / "Messages",
    REPO / "data",
    REPO / "docs",
    REPO / "ui",
    REPO / "core",
    REPO / "tools",
]
WATCH_EXTS = {
    ".md", ".txt", ".json", ".jsonl", ".ai", ".py", ".html", ".css", ".js",
    ".yaml", ".yml", ".docx",
}
EXCLUDE_PARTS = {"__pycache__", ".git", "node_modules", "sandbox.trash", "receipts"}
SCAN_INTERVAL = 20          # seconds
MAX_EVENTS_PER_SCAN = 200   # burst cap so a bulk copy can't flood the feed


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_snapshot() -> dict[str, list[float]]:
    try:
        return json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_snapshot(snap: dict[str, list[float]]) -> None:
    try:
        SNAPSHOT.write_text(json.dumps(snap), encoding="utf-8")
    except Exception:
        pass


def _scan() -> dict[str, list[float]]:
    seen: dict[str, list[float]] = {}
    for root in WATCH_ROOTS:
        if not root.exists():
            continue
        try:
            for p in root.rglob("*"):
                if not p.is_file():
                    continue
                if p.suffix.lower() not in WATCH_EXTS:
                    continue
                if any(part in EXCLUDE_PARTS for part in p.parts):
                    continue
                try:
                    st = p.stat()
                except OSError:
                    continue
                seen[str(p)] = [st.st_mtime, float(st.st_size)]
        except Exception:
            continue
    return seen


def _emit(events: list[dict]) -> None:
    if not events:
        return
    FEED.parent.mkdir(parents=True, exist_ok=True)
    with FEED.open("a", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev, ensure_ascii=True) + "\n")


def run() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    prev = _load_snapshot()
    first_pass = not prev  # baseline scan: record state, emit nothing
    while True:
        if STOP_FLAG.exists():
            break
        current = _scan()
        if first_pass:
            first_pass = False
        else:
            events: list[dict] = []
            for path, (mtime, size) in current.items():
                old = prev.get(path)
                if old is None:
                    kind = "created"
                elif old[0] != mtime or old[1] != size:
                    kind = "modified"
                else:
                    continue
                rel = path
                try:
                    rel = str(Path(path).relative_to(REPO))
                except ValueError:
                    pass
                events.append({
                    "ts": _now(),
                    "event": kind,
                    "path": rel,
                    "ext": Path(path).suffix.lower(),
                    "size": int(size),
                    "witness": "creation_witness",
                    "boundary": "metadata_only_no_content_no_upload",
                })
                if len(events) >= MAX_EVENTS_PER_SCAN:
                    events.append({
                        "ts": _now(), "event": "burst_capped",
                        "path": "", "witness": "creation_witness",
                        "note": f"more than {MAX_EVENTS_PER_SCAN} changes in one scan; remainder recorded next cycle",
                    })
                    break
            _emit(events)
        prev = current
        _save_snapshot(prev)
        time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    run()
