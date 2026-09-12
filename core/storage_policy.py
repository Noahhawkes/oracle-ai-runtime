"""ORACLE storage compaction policy (Noah.Physical, 2026-08-24).

Grow like a database, not a teenager's Downloads folder. Millions of memories are
fine; millions of tiny files are not.

RULE: write dense, append when safe, index in databases, and do NOT create a new
file when an existing durable container can hold the record.

Preferred storage order:
  1. SQLite for structured durable state (Memory/oracle_memory.db)
  2. Append-only JSONL for event/receipt streams (data/ledger/*.jsonl)
  3. One rolling Markdown/JSON per major domain when humans must read it
     (journals/YYYY.md, thread_passes/YYYY-MM.jsonl)
  4. Periodic compressed archives for cold history (events_YYYY_MM.jsonl.zst)
  5. Individual files ONLY when the artifact has independent human value

This module operationalizes that rule: canonical container paths, a file-creation
gate, append-only helpers (create-on-write), sha-256 dedup, source pointers,
retention classes, and metrics. Pure stdlib. It never deletes or compacts the
runtime's existing files (the sandbox is ORACLE-only-write); it governs NEW writes.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

# ── canonical containers ─────────────────────────────────────────────────────
DB = ROOT / "Memory" / "oracle_memory.db"
EVENTS = ROOT / "data" / "ledger" / "events.jsonl"
RECEIPTS = ROOT / "data" / "ledger" / "receipts.jsonl"
MINDCOIN = ROOT / "data" / "ledger" / "mindcoin.jsonl"
ATTENTION = ROOT / "data" / "ledger" / "attention.jsonl"
THREAD_STATE = ROOT / "data" / "thread_state.jsonl"


def journal_file(year: int | None = None) -> Path:
    year = year or datetime.now(timezone.utc).year
    return ROOT / "journals" / f"{year}.md"


def thread_pass_file(year: int | None = None, month: int | None = None) -> Path:
    now = datetime.now(timezone.utc)
    return ROOT / "thread_passes" / f"{year or now.year}-{month or now.month:02d}.jsonl"


STORAGE_ORDER = ("sqlite_db", "append_jsonl", "rolling_domain_doc",
                 "compressed_archive", "independent_file")
AVOID = ("one_json_per_event", "one_markdown_per_turn", "duplicate_thread_passes",
         "duplicate_drive_mirrors", "repeated_full_transcripts", "duplicate_source_copies",
         "identical_receipts_multi_format", "one_file_per_lootdrop",
         "regenerated_summaries_repeating_source")


def sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def source_pointer(source_id: str, path: str, sha: str,
                   offset: int | None = None, length: int | None = None) -> dict[str, Any]:
    """A reference to an original source, not a copy of it. One source can back
    thousands of continuity records this way."""
    ptr: dict[str, Any] = {"source_id": source_id, "path": path, "sha256": sha}
    if offset is not None:
        ptr["offset"] = offset
    if length is not None:
        ptr["length"] = length
    return ptr


# ── file-creation gate ───────────────────────────────────────────────────────

def should_create_file(*, human_opens_independently: bool = False,
                       materially_unique: bool = False,
                       fits_ledger: bool = False,
                       storable_as_db_row: bool = False,
                       representable_as_pointer: bool = False) -> dict[str, Any]:
    """Ask before creating a file. Create only when a human must open the artifact
    independently, or it is materially unique AND no denser container fits."""
    if fits_ledger:
        route = "append_jsonl"
    elif storable_as_db_row:
        route = "sqlite_db"
    elif representable_as_pointer:
        route = "source_pointer"
    elif materially_unique:
        route = "independent_file"
    else:
        route = "append_jsonl"

    create = human_opens_independently or (
        materially_unique and not (fits_ledger or storable_as_db_row or representable_as_pointer))
    reason = ("human must open it independently" if human_opens_independently else
              "materially unique with no denser container" if create else
              f"denser container fits: {route}")
    return {"create": create, "recommended_route": route, "reason": reason}


# ── append-only helpers (create-on-first-write; no empty files) ──────────────

def append_jsonl(path: str | Path, record: dict[str, Any]) -> int:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
    with p.open("a", encoding="utf-8") as fh:
        fh.write(line)
    return len(line.encode("utf-8"))


def append_journal(entry_markdown: str, *, year: int | None = None,
                   heading: str | None = None) -> Path:
    """Append a human-readable journal entry into the rolling journals/YYYY.md
    instead of one file per entry."""
    p = journal_file(year)
    p.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    block = f"\n\n---\n\n## {heading or ts}\n\n{entry_markdown.strip()}\n"
    with p.open("a", encoding="utf-8") as fh:
        fh.write(block)
    return p


# ── dedup by content hash ────────────────────────────────────────────────────

class SeenIndex:
    """Track content hashes so identical content is referenced, not re-copied."""

    def __init__(self, initial: set[str] | None = None):
        self._seen: set[str] = set(initial or ())

    def is_new(self, sha: str) -> bool:
        return sha not in self._seen

    def dedupe(self, content: str) -> dict[str, Any]:
        h = sha256(content)
        if h in self._seen:
            return {"action": "referenced", "sha256": h, "bytes_avoided": len(content.encode("utf-8"))}
        self._seen.add(h)
        return {"action": "stored", "sha256": h, "bytes_avoided": 0}


# ── retention classes ────────────────────────────────────────────────────────

def retention_class(age_days: float, *, resolved: bool = False,
                    is_raw_source: bool = False) -> str:
    if is_raw_source:
        return "ARCHIVAL"
    if age_days <= 7 and not resolved:
        return "HOT"
    if age_days <= 92:
        return "WARM"
    return "COLD"


# ── metrics ──────────────────────────────────────────────────────────────────

@dataclass
class StorageMetrics:
    files_created: int = 0
    records_appended: int = 0
    bytes_written: int = 0
    duplicate_bytes_avoided: int = 0
    pointers: int = 0
    copies: int = 0

    def record_create(self) -> None:
        self.files_created += 1

    def record_append(self, nbytes: int) -> None:
        self.records_appended += 1
        self.bytes_written += nbytes

    def record_dedupe(self, result: dict[str, Any]) -> None:
        if result.get("action") == "referenced":
            self.duplicate_bytes_avoided += int(result.get("bytes_avoided", 0))
            self.pointers += 1
        else:
            self.copies += 1

    def snapshot(self) -> dict[str, Any]:
        total = self.files_created + self.records_appended
        return {
            "TOTAL_FILES_CREATED": self.files_created,
            "RECORDS_APPENDED": self.records_appended,
            "BYTES_WRITTEN": self.bytes_written,
            "DUPLICATE_BYTES_AVOIDED": self.duplicate_bytes_avoided,
            "AVG_RECORDS_PER_FILE": round(self.records_appended / max(1, self.files_created), 2),
            "POINTERS_VS_COPIES": f"{self.pointers}:{self.copies}",
            # health goal: growth is mostly records, not files
            "GROWTH_IS_RECORDS_NOT_FILES": (self.records_appended >= self.files_created) if total else True,
        }
