"""
corpus_ingest.py — Light Compression Law ingestion for ORACLE.

Noah's ask: "give her every file and all the metadata; process it using our
logic and rules — Light Compression Law was built for this."

This walks a BOUNDED corpus, captures full file metadata, extracts text, and
compresses each file to its authentic kernel via the Light Compression engine
(core/light_compression.py). It honors the Consequence Loop:

    signal -> witness -> classification -> ... -> memory candidate ->
    HUMAN RATIFICATION -> durable replay

By default it is a DRY RUN: it produces ratifiable candidates plus a provenance
receipt and writes NOTHING durable. Only `commit=True` (CLI --commit) promotes
candidates into ORACLE's light memory, and even then the engine still discards
noise and gates sensitive material.

Doctrine enforced here:
  - Preserve the authentic kernel, discard noise (LCL scoring).
  - Every candidate carries a provenance receipt: path, sha256, bytes, mtime.
  - Sensitive content is gated, never auto-stored.
  - Unreadable / cloud-stub / binary files yield UNKNOWN, never a guess.
    An honest UNKNOWN beats drift.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))

import light_compression as lc  # noqa: E402

RECEIPT_DIR = ROOT / "Memory" / "corpus_ingest"

# Text we can read directly.
TEXT_EXTS = {
    ".txt", ".md", ".markdown", ".rst", ".json", ".jsonl", ".csv", ".tsv",
    ".yaml", ".yml", ".ini", ".cfg", ".toml", ".log", ".py", ".js", ".ts",
    ".html", ".htm", ".css", ".sh", ".ps1", ".bat", ".sql", ".xml", ".env",
}
# Google Drive cloud-only stubs — unreadable as local files → UNKNOWN.
CLOUD_STUB_EXTS = {".gdoc", ".gsheet", ".gslides", ".gdraw", ".gform", ".gsite"}
# Known binaries we will not guess at (metadata only).
BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".ico",
    ".mp4", ".mkv", ".mov", ".avi", ".flv", ".webm", ".mp3", ".wav", ".m4a",
    ".zip", ".gz", ".7z", ".rar", ".tar", ".exe", ".dll", ".so", ".db",
    ".sqlite", ".bin", ".pyc", ".pdf", ".docx", ".pptx", ".xlsx",  # handled below if extractor present
}

DEFAULT_MAX_BYTES = 5 * 1024 * 1024   # skip text extraction above this size
DEFAULT_MAX_FILES = 0                  # 0 = no limit

# Path/name hints → memory type (best-effort classification, never asserted hard).
_TYPE_HINTS = (
    ("constraint", lc.CONSTRAINT), ("rule", lc.CONSTRAINT), ("law", lc.CONSTRAINT),
    ("doctrine", lc.CONSTRAINT), ("governance", lc.CONSTRAINT), ("policy", lc.CONSTRAINT),
    ("journal", lc.EMOTIONAL), ("feel", lc.EMOTIONAL),
    ("project", lc.PROJECT), ("build", lc.PROJECT), ("roadmap", lc.PROJECT),
    ("plan", lc.PROJECT), ("status", lc.PROJECT),
)


def _utc(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_metadata(path: Path) -> dict:
    st = path.stat()
    h = hashlib.sha256()
    try:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        sha = h.hexdigest()
    except Exception:
        sha = None
    return {
        "source_path": str(path),
        "name": path.name,
        "ext": path.suffix.lower(),
        "bytes": st.st_size,
        "mtime_utc": _utc(st.st_mtime),
        "sha256": sha,
    }


def _guess_type(path: Path, text: str) -> str:
    hay = (str(path) + " " + text[:400]).lower()
    for needle, mtype in _TYPE_HINTS:
        if needle in hay:
            return mtype
    return lc.FACT


def extract_text(path: Path, *, max_bytes: int = DEFAULT_MAX_BYTES) -> tuple[Optional[str], str]:
    """Return (text, status). status is 'ok' or an UNKNOWN reason."""
    ext = path.suffix.lower()
    if ext in CLOUD_STUB_EXTS:
        return None, "cloud_stub_unreadable"
    try:
        size = path.stat().st_size
    except Exception:
        return None, "stat_error"
    if size == 0:
        return None, "empty_file"
    if size > max_bytes and ext in TEXT_EXTS:
        return None, "too_large"

    if ext in TEXT_EXTS:
        try:
            return path.read_text(encoding="utf-8", errors="replace"), "ok"
        except Exception as exc:
            return None, f"read_error:{type(exc).__name__}"

    if ext == ".pdf":
        try:
            from pypdf import PdfReader  # type: ignore
            reader = PdfReader(str(path))
            text = "\n".join((pg.extract_text() or "") for pg in reader.pages)
            return (text, "ok") if text.strip() else (None, "pdf_no_text")
        except Exception:
            return None, "unsupported_no_pdf_extractor"

    if ext == ".docx":
        try:
            import docx  # type: ignore
            d = docx.Document(str(path))
            text = "\n".join(p.text for p in d.paragraphs)
            return (text, "ok") if text.strip() else (None, "docx_empty")
        except Exception:
            return None, "unsupported_no_docx_extractor"

    if ext in BINARY_EXTS:
        return None, "binary_no_text"
    return None, "unsupported_ext"


def compress_file(path: Path, *, max_bytes: int = DEFAULT_MAX_BYTES) -> dict:
    """Build one ratifiable candidate (metadata + LCL kernel + provenance)."""
    meta = file_metadata(path)
    text, status = extract_text(path, max_bytes=max_bytes)
    candidate = {
        "candidate_id": "cand-" + uuid.uuid4().hex[:12],
        "captured_at_utc": _now(),
        "evidence_class": "file_extracted_text",
        "source_type": "corpus_file",
        "status": status,
        "ratified": False,
        "committed": False,
        **meta,
    }
    if status != "ok" or not text or not text.strip():
        # UNKNOWN — honest, no guess.
        candidate.update({
            "memory_type": None,
            "kernel": "UNKNOWN",
            "word_count": 0,
            "score": 0.0,
            "sensitivity": 0.0,
            "noise": 0.0,
            "disposition": "unknown",
        })
        return candidate

    mtype = _guess_type(path, text)
    score, relevance, emo, proj, sensitivity, noise = lc.score_signal(text, memory_type=mtype)
    kernel = lc._auto_compress(text, mtype)
    if sensitivity > 0.5:
        disposition = "gated_sensitive"
    elif score < lc.THRESHOLD_DISCARD:
        disposition = "discard_noise"
    else:
        disposition = "candidate"
    candidate.update({
        "memory_type": mtype,
        "kernel": kernel,
        "word_count": len(text.split()),
        "score": round(score, 3),
        "relevance": round(relevance, 3),
        "emotional_weight": round(emo, 3),
        "project_value": round(proj, 3),
        "sensitivity": round(sensitivity, 3),
        "noise": round(noise, 3),
        "disposition": disposition,
    })
    return candidate


def iter_files(root: Path, *, follow_hidden: bool = False):
    skip_dirs = {".git", "__pycache__", ".claude", "node_modules", ".pytest_cache",
                 ".snapshots", ".aider.tags.cache.v4"}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        parts = set(part for part in p.parts)
        if parts & skip_dirs:
            continue
        if not follow_hidden and any(part.startswith(".") and part not in {"."} for part in p.relative_to(root).parts[:-1]):
            continue
        yield p


def ingest_corpus(
    root: str | Path,
    *,
    commit: bool = False,
    max_files: int = DEFAULT_MAX_FILES,
    max_bytes: int = DEFAULT_MAX_BYTES,
    write_receipt: bool = True,
) -> dict:
    """
    Walk `root`, compress each file via LCL, and return a manifest.
    DRY RUN by default (commit=False) — writes only a provenance receipt, no
    durable memory. commit=True promotes non-noise/non-sensitive candidates.
    """
    root = Path(root).resolve()
    if not root.exists():
        return {"error": f"root does not exist: {root}"}

    candidates: list[dict] = []
    counts = {"seen": 0, "ok": 0, "unknown": 0, "candidate": 0,
              "discard_noise": 0, "gated_sensitive": 0, "committed": 0}

    for path in iter_files(root):
        if max_files and counts["seen"] >= max_files:
            break
        counts["seen"] += 1
        cand = compress_file(path, max_bytes=max_bytes)
        disp = cand["disposition"]
        counts[disp] = counts.get(disp, 0) + 1
        if cand["status"] == "ok":
            counts["ok"] += 1
        else:
            counts["unknown"] += 1

        if commit and disp == "candidate":
            stored = lc.compress_and_store(
                raw_signal=cand["kernel"],
                memory_type=cand["memory_type"],
                compressed=cand["kernel"],
                source=f"corpus:{cand['name']}",
                tags=["corpus_ingest", cand["sha256"][:12] if cand["sha256"] else "nohash"],
            )
            if stored is not None:
                cand["committed"] = True
                cand["ratified"] = True
                cand["light_memory_id"] = stored.id
                counts["committed"] += 1
        candidates.append(cand)

    manifest = {
        "schema_version": 1,
        "manifest_id": "corpus-" + uuid.uuid4().hex[:12],
        "generated_at_utc": _now(),
        "root": str(root),
        "mode": "commit" if commit else "dry_run",
        "law": "light_compression",
        "counts": counts,
        "candidates": candidates,
    }

    if write_receipt:
        RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        receipt_path = RECEIPT_DIR / f"manifest_{stamp}_{manifest['manifest_id']}.json"
        receipt_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True), encoding="utf-8")
        manifest["receipt_path"] = str(receipt_path)

    return manifest


def _summary(manifest: dict) -> str:
    if "error" in manifest:
        return f"ERROR: {manifest['error']}"
    c = manifest["counts"]
    lines = [
        f"corpus ingest [{manifest['mode']}]  root={manifest['root']}",
        f"  seen={c['seen']}  readable={c['ok']}  unknown={c['unknown']}",
        f"  candidates={c.get('candidate',0)}  noise_discarded={c.get('discard_noise',0)}"
        f"  sensitive_gated={c.get('gated_sensitive',0)}  committed={c.get('committed',0)}",
        f"  receipt={manifest.get('receipt_path','(none)')}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="LCL corpus ingestion (dry-run by default)")
    ap.add_argument("--root", required=True, help="corpus root directory")
    ap.add_argument("--commit", action="store_true", help="promote candidates into light memory")
    ap.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    ap.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    ap.add_argument("--top", type=int, default=12, help="show top-N candidates by score")
    args = ap.parse_args()

    man = ingest_corpus(args.root, commit=args.commit,
                        max_files=args.max_files, max_bytes=args.max_bytes)
    print(_summary(man))
    if "candidates" in man:
        ranked = sorted([c for c in man["candidates"] if c["disposition"] == "candidate"],
                        key=lambda c: c["score"], reverse=True)[:args.top]
        print("\ntop candidates:")
        for c in ranked:
            print(f"  {c['score']:.2f} [{(c['memory_type'] or 'unknown').upper():11}] "
                  f"{c['name'][:42]:42} {c['kernel'][:70]}")
