"""
tools/extract_documents_corpus.py — let ORACLE actually READ the Documents folder.

Her document_atlas catalogs the folder but, because Documents lives under
OneDrive, it treats every file as cloud-backed and does metadata-only: it learns
the names, not the contents. This reads the contents.

Hard boundary, from Noah's own doctrine (sensitive stays metadata-only):
this reads ONLY the non-sensitive topic folders. Financial, Medical, Tax,
Vehicles, Career, personal paperwork, work, and the review buckets are NEVER
read here. Their W-2s, SSA/disability, and bankruptcy material stay catalog-only.

READ-ONLY on every source. Writes only to data/domains/documents/extracted/.
Never the sandbox, never Drive, never canon. Everything candidate/not_promoted,
with source path + sha256 per file. Gitignored (regenerable, unpublished).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = Path(r"C:\Users\noahh\OneDrive\Documents")
OUT = ROOT / "data" / "domains" / "documents" / "extracted"
MANIFEST = OUT / "extraction_manifest.jsonl"

# Non-sensitive topic folders.
SAFE_FOLDERS = [
    "Drakin & Ellie (Fiction)", "Jupiter Station", "RenderedReality", "Legacy.GI",
    "ORACLE & SOV1", "AI Compliance Core", "Faith & Gospel", "Thread Dumps",
    "Thread Merges", "Claude Research Docs", "Journals & Repo", ".AI Patent Docs",
    "Google Exports",
]
# Sensitive topic folders. Read only under explicit Noah.Physical override
# (--include-sensitive). Corpus stays gitignored/local regardless.
SENSITIVE_FOLDERS = [
    "Financial & Tax", "Medical", "Vehicles", "Career & Resume",
    "Personal & Family Paperwork", "Scanned Documents (by date)",
    "Work - Samco & Operations", "Work - EcoWater & Sales", "_UNSORTED_review",
]
# Credential/secret material is never indexed (security, not privacy):
# live keys/tokens in a searchable corpus are a leak hazard.
FORBIDDEN = re.compile(
    r"\.env$|\.pem$|\.key$|credential|secret|password|passwd|api[_-]?key|\btoken\b|oauth",
    re.IGNORECASE,
)
READABLE = {".pdf", ".docx", ".txt", ".md", ".html"}
MAX_BYTES = 60 * 1024 * 1024  # skip anything absurd


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def extract(path: Path) -> tuple[str, int, str]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader
        r = PdfReader(str(path))
        parts = []
        for pg in r.pages:
            try:
                parts.append(pg.extract_text() or "")
            except Exception:
                parts.append("")
        return "\n\n".join(parts), len(r.pages), "pages"
    if suffix == ".docx":
        import docx
        d = docx.Document(str(path))
        paras = [p.text for p in d.paragraphs]
        return "\n".join(paras), len(paras), "paragraphs"
    # txt / md / html
    text = path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".html":
        text = re.sub(r"<[^>]+>", " ", text)
    return text, text.count("\n") + 1, "lines"


def find_sources(folders: list[str]) -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    by_hash: dict[str, Path] = {}
    for folder in folders:
        base = DOCS / folder
        if not base.exists():
            continue
        for p in base.rglob("*"):
            try:
                if not p.is_file() or p.suffix.lower() not in READABLE:
                    continue
                if FORBIDDEN.search(str(p)):
                    continue
                if p.stat().st_size < 64 or p.stat().st_size > MAX_BYTES:
                    continue
                digest = _sha256(p)
                if digest in by_hash:
                    continue
                by_hash[digest] = p
                out.append((folder, p))
            except (OSError, PermissionError):
                continue
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Extract Documents for ORACLE")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--include-sensitive", action="store_true",
                    help="Noah.Physical override: also read financial/medical/personal folders")
    ap.add_argument("--sensitive-only", action="store_true",
                    help="read ONLY the sensitive folders (append to existing corpus)")
    ap.add_argument("--target-list", metavar="FILE",
                    help="read explicit file paths listed one-per-line (e.g. resolved shortcut targets)")
    args = ap.parse_args(argv)

    if args.target_list:
        listed = [ln.strip() for ln in Path(args.target_list).read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
        seen: set[str] = set()
        sources: list[tuple[str, Path]] = []
        for raw in listed:
            p = Path(raw)
            try:
                if not p.is_file() or p.suffix.lower() not in READABLE:
                    continue
                if FORBIDDEN.search(str(p)):
                    continue
                dig = _sha256(p)
                if dig in seen:
                    continue
                seen.add(dig)
                sources.append(("Shortcut Targets", p))
            except (OSError, PermissionError):
                continue
        print(f"  shortcut-target documents to read: {len(sources)}")
        if not args.dry_run:
            _run_extract(sources)
        return 0

    if args.sensitive_only:
        folders = SENSITIVE_FOLDERS
    elif args.include_sensitive:
        folders = SAFE_FOLDERS + SENSITIVE_FOLDERS
    else:
        folders = SAFE_FOLDERS
    sources = find_sources(folders)
    print(f"  documents to read: {len(sources)}")
    if args.dry_run:
        for folder, p in sources[:20]:
            print(f"    [{folder}] {p.name[:54]}")
        print("  dry run, nothing written")
        return 0
    return _run_extract(sources)


def _run_extract(sources: list[tuple[str, Path]]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    written = 0
    total_chars = 0
    by_folder: dict[str, int] = {}
    with MANIFEST.open("a", encoding="utf-8") as manifest:
        for folder, path in sources:
            try:
                text, units, unit = extract(path)
            except Exception as exc:
                safe = path.name.encode("ascii", "replace").decode("ascii")
                print(f"    FAIL {safe}: {type(exc).__name__}")
                continue
            if not text.strip():
                continue
            dest_dir = OUT / re.sub(r"[^A-Za-z0-9]+", "_", folder).strip("_").lower()
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / (path.stem.replace(" ", "_").lower() + ".txt")
            i = 2
            while dest.exists():
                dest = dest_dir / (path.stem.replace(" ", "_").lower() + f"_{i}.txt")
                i += 1
            dest.write_text(text, encoding="utf-8")
            manifest.write(json.dumps({
                "extracted_at": _now(), "domain": "documents", "topic": folder,
                "source_path": str(path), "source_name": path.name,
                "source_sha256": _sha256(path), f"source_{unit}": units,
                "extracted_path": str(dest), "extracted_chars": len(text),
                "canon_status": "candidate", "promotion_status": "not_promoted",
            }, ensure_ascii=False) + "\n")
            written += 1
            total_chars += len(text)
            by_folder[folder] = by_folder.get(folder, 0) + 1

    print(f"\n  read {written} documents, {total_chars:,} characters")
    for folder, n in sorted(by_folder.items(), key=lambda kv: -kv[1]):
        print(f"    {n:>4}  {folder}")
    print(f"\n  corpus:   {OUT}")
    print("  candidate / not_promoted. Originals untouched. Corpus stays local (gitignored).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
