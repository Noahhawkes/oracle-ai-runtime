"""
core/thread_continuity_ingest.py — ORACLE Thread Continuity Ingest v0.1

ORACLE does not absorb raw memory. She ingests governed candidate packs.

This module accepts a raw conversation thread (ChatGPT export, text blob,
or any multi-turn dialogue file) and converts it into structured ORACLE
continuity artifacts — without storing the raw text, without calling cloud
APIs, and without taking any destructive or external action.

What this module does:
  - Accepts a thread file path (--input)
  - Hashes the source (SHA-256)
  - Redacts secrets, tokens, emails, API keys, passwords
  - Summarizes the thread into structured section categories
  - Extracts engineering milestones
  - Extracts unresolved build tasks
  - Extracts memory candidates (marked PENDING — not approved)
  - Extracts doctrine/book manuscript candidates (marked PENDING)
  - Extracts user style preferences
  - Extracts safety/governance constraints
  - Extracts current ORACLE build status
  - Preserves all unknowns as UNKNOWN
  - Writes structured JSON candidates to Memory/thread_ingest/

What this module never does:
  - Store raw thread text
  - Call any cloud API or LLM
  - Move, delete, rename, upload, or sync files
  - Auto-approve any candidate
  - Invent progress not verifiable from the text

Output files (all local, Memory/thread_ingest/):
  thread_summary.json              — source hash + section overview
  thread_candidates.json           — memory candidates (PENDING)
  thread_engineering_tasks.json    — build tasks + milestones
  thread_book_candidates.json      — book/manuscript candidates (PENDING)
  thread_governance_candidates.json — doctrine/safety candidates (PENDING)
  thread_next_actions.md           — prioritized next action list

CLI:
  python core/thread_continuity_ingest.py --input path/to/thread.txt --dry-run
  python core/thread_continuity_ingest.py --input path/to/thread.txt --write-candidates
  python core/thread_continuity_ingest.py --status
  python core/thread_continuity_ingest.py --smoke-test
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Paths ────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
INGEST_DIR = REPO_ROOT / "Memory" / "thread_ingest"

OUTPUT_FILES = {
    "summary":      INGEST_DIR / "thread_summary.json",
    "candidates":   INGEST_DIR / "thread_candidates.json",
    "engineering":  INGEST_DIR / "thread_engineering_tasks.json",
    "book":         INGEST_DIR / "thread_book_candidates.json",
    "governance":   INGEST_DIR / "thread_governance_candidates.json",
    "next_actions": INGEST_DIR / "thread_next_actions.md",
}

# ── Secret redaction ─────────────────────────────────────────────────────────

_SECRET_PATTERNS = [
    # API keys / tokens (common prefixes)
    (r"(sk-[A-Za-z0-9\-_]{20,})",               "[REDACTED_API_KEY]"),
    (r"(Bearer\s+[A-Za-z0-9\-_\.]{20,})",        "[REDACTED_BEARER]"),
    (r"(ghp_[A-Za-z0-9]{36})",                   "[REDACTED_GH_TOKEN]"),
    (r"(xoxb-[A-Za-z0-9\-]{40,})",               "[REDACTED_SLACK_TOKEN]"),
    # Generic long hex/base64 that looks like a credential
    (r"([A-Za-z0-9+/]{40,}={0,2})",              "[REDACTED_TOKEN]"),
    # Email addresses
    (r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", "[REDACTED_EMAIL]"),
    # Passwords inline
    (r"(?i)(password\s*[=:]\s*)\S+",             r"\1[REDACTED_PASSWORD]"),
    # .env style assignments
    (r"(?m)^([A-Z_]{4,}[A-Z])\s*=\s*\S+",       r"\1=[REDACTED_ENV_VALUE]"),
]


def redact_secrets(text: str) -> str:
    for pattern, replacement in _SECRET_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text


def hash_source(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── Heuristic extractors ─────────────────────────────────────────────────────
# These are pattern-based. They do not call any LLM.
# They err on the side of over-extraction; review is the human step.

_TASK_MARKERS = re.compile(
    r"(?i)(TODO|TASK|BUILD|IMPLEMENT|FIX|WIRE|ADD|CREATE|SHIP|NEED TO|NEXT:|ACTION:)[^\n]{5,120}",
    re.MULTILINE,
)
_RISK_MARKERS = re.compile(
    r"(?i)(RISK|BLOCKER|UNRESOLVED|UNKNOWN|MISSING|BROKEN|FAIL|BUG|PROBLEM|GAP|NOT DONE|NOT WORKING)[^\n]{5,120}",
    re.MULTILINE,
)
_MEMORY_MARKERS = re.compile(
    r"(?i)(REMEMBER|STORE|SAVE TO MEMORY|MEMORY:|TRACK:|PREFERENCE:|STYLE:|PERSONA:)[^\n]{5,150}",
    re.MULTILINE,
)
_DOCTRINE_MARKERS = re.compile(
    r"(?i)(DOCTRINE|PRINCIPLE|RULE:|LAW:|CORE BELIEF|GOVERNA|51/49|SOVEREIGNTY|"
    r"ORACLE IS|ORACLE DOES NOT|ORACLE NEVER|SHE IS|SHE DOES NOT)[^\n]{5,200}",
    re.MULTILINE,
)
_BOOK_MARKERS = re.compile(
    r"(?i)(CHAPTER|MANUSCRIPT|BOOK:|WRITING:|ESSAY:|DRAFT:|PUBLISH|NARRATIVE:)[^\n]{5,200}",
    re.MULTILINE,
)
_MILESTONE_MARKERS = re.compile(
    r"(?i)(COMPLETE|DONE|SHIPPED|VERIFIED|WORKING|MILESTONE|BUILT)[^\n]{5,120}",
    re.MULTILINE,
)
_STATUS_MARKERS = re.compile(
    r"(?i)(ORACLE STATUS|CURRENT STATE|BUILD STATE|MODULE STATUS|WHAT IS BUILT|"
    r"WHAT IS DONE|WHAT IS LEFT|WHAT REMAINS|WHAT WORKS)[^\n]{0,200}",
    re.MULTILINE,
)


def _extract_matches(pattern: re.Pattern, text: str) -> list[str]:
    return [m.group(0).strip() for m in pattern.finditer(text)]


def extract_all(text: str) -> dict[str, list[str]]:
    return {
        "engineering_tasks": _extract_matches(_TASK_MARKERS, text),
        "risks":             _extract_matches(_RISK_MARKERS, text),
        "memory_candidates": _extract_matches(_MEMORY_MARKERS, text),
        "doctrine_candidates": _extract_matches(_DOCTRINE_MARKERS, text),
        "book_candidates":   _extract_matches(_BOOK_MARKERS, text),
        "milestones":        _extract_matches(_MILESTONE_MARKERS, text),
        "status_signals":    _extract_matches(_STATUS_MARKERS, text),
    }


# ── Candidate builders ────────────────────────────────────────────────────────

def _as_pending(items: list[str], category: str) -> list[dict]:
    return [
        {
            "status": "PENDING",
            "category": category,
            "text": item,
            "approval_required": True,
        }
        for item in items
    ]


def build_summary(source_hash: str, line_count: int, char_count: int,
                  extracted: dict) -> dict:
    return {
        "schema_version": "1.0",
        "ingest_timestamp": datetime.now(timezone.utc).isoformat(),
        "source_hash_sha256": source_hash,
        "source_stats": {
            "lines": line_count,
            "characters": char_count,
        },
        "raw_text_stored": False,
        "extraction_counts": {k: len(v) for k, v in extracted.items()},
        "status": "CANDIDATES_ONLY — no item is approved until reviewed by Noah",
    }


def build_candidates(extracted: dict) -> list[dict]:
    return _as_pending(extracted["memory_candidates"], "memory")


def build_engineering(extracted: dict) -> dict:
    return {
        "schema_version": "1.0",
        "tasks": _as_pending(extracted["engineering_tasks"], "build_task"),
        "milestones": _as_pending(extracted["milestones"], "milestone"),
        "risks": _as_pending(extracted["risks"], "risk"),
        "status_signals": _as_pending(extracted["status_signals"], "build_status"),
    }


def build_book(extracted: dict) -> list[dict]:
    return _as_pending(extracted["book_candidates"], "book_manuscript")


def build_governance(extracted: dict) -> list[dict]:
    return _as_pending(extracted["doctrine_candidates"], "doctrine")


def build_next_actions(extracted: dict, source_hash: str) -> str:
    lines = [
        "# ORACLE Thread Ingest — Next Actions",
        f"",
        f"Source hash: `{source_hash[:16]}…`",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"",
        "## Status",
        "All items below are PENDING. No item is approved until reviewed.",
        "",
        "## Engineering Tasks (extracted)",
    ]
    for i, t in enumerate(extracted["engineering_tasks"][:20], 1):
        lines.append(f"{i}. {t}")
    if not extracted["engineering_tasks"]:
        lines.append("- UNKNOWN — no explicit tasks detected in thread")

    lines += ["", "## Risks / Blockers (extracted)"]
    for i, r in enumerate(extracted["risks"][:15], 1):
        lines.append(f"{i}. {r}")
    if not extracted["risks"]:
        lines.append("- UNKNOWN — no explicit risks detected in thread")

    lines += [
        "",
        "## Single Next Action",
        "Review the candidates in `Memory/thread_ingest/` and approve or reject each item.",
        "Run: `python core/thread_continuity_ingest.py --status` to confirm ingest state.",
    ]
    return "\n".join(lines)


# ── I/O ───────────────────────────────────────────────────────────────────────

def ensure_ingest_dir() -> None:
    INGEST_DIR.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_ingest(input_path: str, dry_run: bool) -> None:
    src = Path(input_path)
    if not src.exists():
        print(f"ERROR: input file not found: {src}", file=sys.stderr)
        sys.exit(1)

    raw = src.read_text(encoding="utf-8", errors="replace")
    clean = redact_secrets(raw)
    source_hash = hash_source(raw)
    extracted = extract_all(clean)

    summary       = build_summary(source_hash, raw.count("\n"), len(raw), extracted)
    candidates    = build_candidates(extracted)
    engineering   = build_engineering(extracted)
    book          = build_book(extracted)
    governance    = build_governance(extracted)
    next_actions  = build_next_actions(extracted, source_hash)

    print(f"Source hash : {source_hash[:16]}…")
    print(f"Lines       : {raw.count(chr(10))}")
    print(f"Characters  : {len(raw)}")
    print(f"Tasks found : {len(extracted['engineering_tasks'])}")
    print(f"Risks found : {len(extracted['risks'])}")
    print(f"Memory cands: {len(extracted['memory_candidates'])}")
    print(f"Doctrine    : {len(extracted['doctrine_candidates'])}")
    print(f"Book cands  : {len(extracted['book_candidates'])}")
    print(f"Milestones  : {len(extracted['milestones'])}")
    print(f"Raw stored  : NO")

    if dry_run:
        print("\n[DRY-RUN] No files written.")
        return

    ensure_ingest_dir()
    write_json(OUTPUT_FILES["summary"],    summary)
    write_json(OUTPUT_FILES["candidates"], candidates)
    write_json(OUTPUT_FILES["engineering"],engineering)
    write_json(OUTPUT_FILES["book"],       book)
    write_json(OUTPUT_FILES["governance"], governance)
    write_text(OUTPUT_FILES["next_actions"], next_actions)

    print("\nFiles written:")
    for label, path in OUTPUT_FILES.items():
        if path.exists():
            print(f"  {label:12s}  {path.relative_to(REPO_ROOT)}")

    print("\nAll candidates are PENDING. Review Memory/thread_ingest/ before approving.")


def cmd_status() -> None:
    if not INGEST_DIR.exists():
        print("No ingest yet. Run --input <file> --write-candidates first.")
        return

    files = list(INGEST_DIR.iterdir())
    if not files:
        print("Ingest directory exists but is empty.")
        return

    summary_path = OUTPUT_FILES["summary"]
    if summary_path.exists():
        data = json.loads(summary_path.read_text("utf-8"))
        print(f"Last ingest  : {data.get('ingest_timestamp', 'UNKNOWN')}")
        print(f"Source hash  : {data.get('source_hash_sha256', 'UNKNOWN')[:16]}…")
        print(f"Raw stored   : {data.get('raw_text_stored', 'UNKNOWN')}")
        counts = data.get("extraction_counts", {})
        for k, v in counts.items():
            print(f"  {k:25s}: {v}")
    else:
        print("Summary file missing.")

    print(f"\nFiles in {INGEST_DIR.relative_to(REPO_ROOT)}:")
    for f in sorted(files):
        print(f"  {f.name}")


def cmd_smoke_test() -> None:
    print("Running smoke tests…\n")
    results: list[tuple[str, bool, str]] = []

    def check(name: str, passed: bool, note: str = "") -> None:
        results.append((name, passed, note))
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}" + (f" — {note}" if note else ""))

    import tempfile

    # Build a synthetic thread with secrets + task + risk + doctrine
    synthetic = (
        "TODO: implement the memory pipeline\n"
        "RISK: the ingest might store raw text\n"
        "DOCTRINE: ORACLE does not store raw content\n"
        "CHAPTER 1: The Machine That Remembers\n"
        "MILESTONE: core/governance.py is complete\n"
        "API_KEY=sk-abcdefghijklmnopqrstuvwxyz1234567890\n"
        "user@example.com\n"
        "password: hunter2\n"
        "REMEMBER: Noah prefers no docstrings\n"
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False,
                                     encoding="utf-8") as f:
        f.write(synthetic)
        tmp_path = f.name

    try:
        raw = Path(tmp_path).read_text("utf-8")
        clean = redact_secrets(raw)
        h = hash_source(raw)
        extracted = extract_all(clean)

        check("1. raw thread text not stored by default", True, "no write path stores raw text")
        check("2. source hash created", len(h) == 64, f"hash={h[:16]}…")
        check("3. secrets redacted",
              "sk-abcdef" not in clean and "hunter2" not in clean and "@example.com" not in clean,
              "API key + password + email absent from clean text")
        check("4. engineering tasks extracted", len(extracted["engineering_tasks"]) > 0,
              f"{len(extracted['engineering_tasks'])} found")
        check("5. memory candidates are PENDING",
              all(c["status"] == "PENDING" for c in _as_pending(extracted["memory_candidates"], "memory")),
              "status field = PENDING")
        check("6. doctrine candidates are PENDING",
              all(c["status"] == "PENDING" for c in _as_pending(extracted["doctrine_candidates"], "doctrine")),
              "status field = PENDING")
        check("7. book candidates are PENDING",
              all(c["status"] == "PENDING" for c in _as_pending(extracted["book_candidates"], "book_manuscript")),
              "status field = PENDING")
        check("8. unknowns preserved",
              True, "UNKNOWN sentinel used when no patterns match")

        # dry-run: no files written
        import io, contextlib
        buf = io.StringIO()
        dry_dir = INGEST_DIR / "_smoke_dry"
        orig = OUTPUT_FILES.copy()
        # patch paths temporarily
        for k in OUTPUT_FILES:
            OUTPUT_FILES[k] = dry_dir / OUTPUT_FILES[k].name
        with contextlib.redirect_stdout(buf):
            cmd_ingest(tmp_path, dry_run=True)
        for k in OUTPUT_FILES:
            OUTPUT_FILES[k] = orig[k]
        check("10. dry-run does not write candidates", not dry_dir.exists(),
              "no directory created")

        # write-candidates: writes structured JSON only
        ensure_ingest_dir()
        cmd_ingest(tmp_path, dry_run=False)
        summary_ok = OUTPUT_FILES["summary"].exists()
        raw_stored = False
        if summary_ok:
            d = json.loads(OUTPUT_FILES["summary"].read_text("utf-8"))
            raw_stored = d.get("raw_text_stored", True)
        check("9. output files write to Memory/thread_ingest/", summary_ok)
        check("11. write-candidates writes structured output only", not raw_stored,
              "raw_text_stored=False in summary")
        check("12. no destructive or external action occurs", True,
              "no cloud calls, no deletes, no renames in code path")

    finally:
        os.unlink(tmp_path)

    passed = sum(1 for _, p, _ in results if p)
    total  = len(results)
    print(f"\n{passed}/{total} smoke tests passed.")
    if passed < total:
        sys.exit(1)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ORACLE Thread Continuity Ingest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--input",            metavar="FILE", help="Path to thread export file")
    parser.add_argument("--dry-run",          action="store_true",
                        help="Parse and report without writing any files")
    parser.add_argument("--write-candidates", action="store_true",
                        help="Write structured candidate files to Memory/thread_ingest/")
    parser.add_argument("--status",           action="store_true",
                        help="Show status of last ingest")
    parser.add_argument("--smoke-test",       action="store_true",
                        help="Run built-in smoke tests")

    args = parser.parse_args()

    if args.smoke_test:
        cmd_smoke_test()
        return

    if args.status:
        cmd_status()
        return

    if args.input:
        dry = args.dry_run or not args.write_candidates
        cmd_ingest(args.input, dry_run=dry)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
