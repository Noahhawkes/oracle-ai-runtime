"""
tools/extract_ellie_corpus.py — make Ellie readable to ORACLE.

Ellie is ORACLE's first NPC. Her domain has been catalogued since before this
script existed: 18 source records, sensitivity high, write_allowed false. But
every record was filename-only. ORACLE knew that a file called
"Drakin Manuscript - Chapter 1-3.pdf" existed. She had never read a sentence of it.

This extracts the text of Ellie's manuscripts into a local, readable corpus so
ORACLE can ground answers about her in what Noah actually wrote, with provenance,
instead of in the shape of a filename.

Boundaries, deliberately narrow:

- READ-ONLY on every source. Originals are never modified, moved, or deleted.
- Writes only to data/domains/ellie/extracted/. Never the sandbox, which is
  ORACLE's alone. Never Drive. Never canon.
- Every extraction carries the source path, size, and sha256 of the original.
- Everything lands as candidate / not_promoted. Noah promotes, or nobody does.
- No network. No external send. No model calls.

Usage:
    python tools/extract_ellie_corpus.py --dry-run
    python tools/extract_ellie_corpus.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "domains" / "ellie" / "extracted"
MANIFEST = OUT_DIR / "extraction_manifest.jsonl"

# Ellie's written material. Patterns, not hardcoded paths, because the same
# manuscript exists in several places with different names.
SEARCH_ROOTS = [
    Path(r"G:\My Drive"),
    Path(r"C:\Users\noahh\OneDrive"),
]
NAME_PATTERNS = ("drakin", "dragonkin", "scala")
READABLE_SUFFIXES = {".pdf", ".docx"}

# Google Docs stubs are pointers with no local text. Skipping them is honest;
# they need a Drive export, which is a separate job.
STUB_SUFFIXES = {".gdoc", ".gsheet", ".gslides"}
MIN_REAL_BYTES = 2048


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


import re

# Drive and OneDrive leave copies everywhere: "(2)", "_1", name clashes, URL
# encoding. Ten copies of one manuscript is not ten sources, and feeding them
# all to ORACLE would make repetition look like corroboration.
_COPY_MARKERS = re.compile(
    r"\s*\((?:\d+|#\s*name\s*clash[^)]*)\)|%20|\s*-\s*copy\b|_\d+$",
    re.IGNORECASE,
)


def _work_key(path: Path) -> str:
    """Collapse copy artifacts so variants of one work group together."""
    stem = path.stem.lower()
    stem = _COPY_MARKERS.sub(" ", stem)
    stem = re.sub(r"[^a-z0-9]+", " ", stem).strip()
    return stem


def find_sources() -> list[Path]:
    """Return one file per distinct work, preferring the richest version.

    Two-stage dedupe: exact content (sha256) first, then near-duplicate names,
    keeping the largest surviving file since edits and proofs add material."""
    candidates: list[Path] = []
    for root in SEARCH_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            try:
                if not path.is_file():
                    continue
                suffix = path.suffix.lower()
                if suffix in STUB_SUFFIXES or suffix not in READABLE_SUFFIXES:
                    continue
                if not any(p in path.name.lower() for p in NAME_PATTERNS):
                    continue
                if path.stat().st_size < MIN_REAL_BYTES:
                    continue
                candidates.append(path)
            except (OSError, PermissionError):
                continue

    # Stage 1: identical bytes are the same file wearing different names.
    by_hash: dict[str, Path] = {}
    for path in candidates:
        try:
            digest = _sha256(path)
        except (OSError, PermissionError):
            continue
        prior = by_hash.get(digest)
        if prior is None or len(str(path)) < len(str(prior)):
            by_hash[digest] = path

    # Stage 2: same work, different revision. Keep the largest.
    by_work: dict[str, Path] = {}
    for path in by_hash.values():
        key = f"{_work_key(path)}|{path.suffix.lower()}"
        prior = by_work.get(key)
        if prior is None or path.stat().st_size > prior.stat().st_size:
            by_work[key] = path

    return sorted(by_work.values(), key=lambda p: p.name.lower())


def extract_pdf(path: Path) -> tuple[str, int]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")
    return "\n\n".join(parts), len(reader.pages)


def extract_docx(path: Path) -> tuple[str, int]:
    import docx

    document = docx.Document(str(path))
    paras = [p.text for p in document.paragraphs]
    return "\n".join(paras), len(paras)


def extract(path: Path) -> tuple[str, int, str]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        text, units = extract_pdf(path)
        return text, units, "pages"
    if suffix == ".docx":
        text, units = extract_docx(path)
        return text, units, "paragraphs"
    raise ValueError(f"unsupported: {suffix}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract Ellie's manuscripts for ORACLE")
    parser.add_argument("--dry-run", action="store_true", help="list sources, write nothing")
    args = parser.parse_args(argv)

    sources = find_sources()
    print(f"  Ellie sources found: {len(sources)}\n")
    for path in sources:
        print(f"    {path.stat().st_size / 1024:9.1f} KB  {path.name}")

    if args.dry_run:
        print("\n  dry run, nothing written")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    total_chars = 0

    with MANIFEST.open("a", encoding="utf-8") as manifest:
        for path in sources:
            try:
                text, units, unit_name = extract(path)
            except Exception as exc:
                print(f"    FAILED {path.name}: {type(exc).__name__}: {exc}")
                continue
            if not text.strip():
                print(f"    EMPTY  {path.name} (no extractable text layer)")
                continue

            out_name = path.stem.replace(" ", "_").lower() + ".txt"
            out_path = OUT_DIR / out_name
            out_path.write_text(text, encoding="utf-8")

            record = {
                "extracted_at": _now(),
                "domain": "ellie",
                "source_path": str(path),
                "source_name": path.name,
                "source_bytes": path.stat().st_size,
                "source_sha256": _sha256(path),
                f"source_{unit_name}": units,
                "extracted_path": str(out_path),
                "extracted_chars": len(text),
                "canon_status": "candidate",
                "promotion_status": "not_promoted",
                "boundary": "read-only extraction; original untouched; no canon promotion",
            }
            manifest.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1
            total_chars += len(text)
            print(f"    OK     {path.name}  ->  {out_name}  ({len(text):,} chars, {units} {unit_name})")

    print(f"\n  extracted {written} manuscripts, {total_chars:,} characters")
    print(f"  corpus:   {OUT_DIR}")
    print(f"  manifest: {MANIFEST}")
    print("\n  All records candidate / not_promoted. Originals unmodified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
