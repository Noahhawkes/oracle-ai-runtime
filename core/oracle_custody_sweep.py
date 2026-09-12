"""Metadata-only ORACLE custody sweep.

Observe.Copy.Store first pass:
- Observe: discover ORACLE-adjacent files and hash them.
- Copy: intentionally not performed without Noah.Physical approval.
- Store: write a JSONL manifest and a sweep receipt.

No raw content is duplicated into custody by this module.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "oracle_custody"
MANIFEST_PATH = OUTPUT_DIR / "oracle_artifact_manifest.jsonl"
LATEST_RECEIPT_PATH = OUTPUT_DIR / "oracle_custody_sweep_receipt_latest.json"

SEARCH_MARKERS: dict[str, tuple[str, ...]] = {
    "ORACLE": ("oracle",),
    "OracleAI": ("oracleai", "oracle ai"),
    "ORACLE.AI": ("oracle.ai", "oracle1.ai", "oracle ai"),
    "oracle-ai-runtime": ("oracle-ai-runtime", "oracle.ai-runtime", "oracle ai runtime"),
    "SOV1": ("sov1", "sov1.ai"),
    "UserPath": ("userpath", "user.ai", "noah.ai", "identity node"),
    "Rendered Reality": ("rendered reality", "renderedreality", "rendered_reality"),
    "Legacy.GI": ("legacy.gi", "legacygi", "legacy gi"),
}

TEXT_EXTENSIONS = {
    ".ai",
    ".bat",
    ".cfg",
    ".cmd",
    ".conf",
    ".css",
    ".csv",
    ".html",
    ".ini",
    ".ipynb",
    ".js",
    ".json",
    ".jsonl",
    ".log",
    ".md",
    ".ps1",
    ".py",
    ".rs",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}

SKIP_DIR_NAMES = {
    "$recycle.bin",
    ".cache",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "appdata",
    "cache",
    "caches",
    "env",
    "node_modules",
    "site-packages",
    "temp",
    "tmp",
    "venv",
}

SENSITIVE_PATH_TERMS = (
    "family",
    "financial",
    "finance",
    "medical",
    "health",
    "tax",
    "taxes",
    "legal",
    "client",
    "personal",
    "private",
    "password",
    "secret",
    "credential",
    "identity",
    "onedrive",
    "users/noahh",
    "users\\noahh",
)

REQUIRED_FIELDS = (
    "source_path",
    "source_system",
    "filename",
    "extension",
    "size_bytes",
    "created_at",
    "modified_at",
    "sha256",
    "matched_terms",
    "custody_status",
    "copy_status",
    "store_status",
    "canon_status",
    "promotion_status",
    "sensitivity",
    "notes",
)


@dataclass(frozen=True)
class SearchRoot:
    label: str
    path: Path


def utc_iso(timestamp: float | None) -> str | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def normalize_path(path: Path) -> str:
    return str(path.resolve(strict=False)).replace("\\", "/")


def text_matches_markers(text: str) -> list[str]:
    low = text.lower()
    matches: list[str] = []
    for marker, aliases in SEARCH_MARKERS.items():
        if any(alias in low for alias in aliases):
            matches.append(marker)
    return matches


def should_scan_content(path: Path, size_bytes: int, max_content_bytes: int) -> bool:
    return (
        path.suffix.lower() in TEXT_EXTENSIONS
        and size_bytes <= max_content_bytes
        and size_bytes >= 0
    )


def hash_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def read_content_sample(path: Path, max_bytes: int) -> str:
    raw = path.read_bytes()[:max_bytes]
    return raw.decode("utf-8", errors="ignore")


def discover_default_roots() -> list[SearchRoot]:
    candidates: list[SearchRoot] = [
        SearchRoot("C:/Oracle", Path("C:/Oracle")),
        SearchRoot("C:/ORACLE.AI", Path("C:/ORACLE.AI")),
        SearchRoot("C:/Users/noahh", Path("C:/Users/noahh")),
        SearchRoot("G:/My Drive", Path("G:/My Drive")),
    ]
    home = Path.home()
    try:
        for one_drive in sorted(home.glob("OneDrive*")):
            if one_drive.is_dir():
                candidates.append(SearchRoot(str(one_drive).replace("\\", "/"), one_drive))
    except Exception:
        pass
    if ROOT not in [root.path for root in candidates]:
        candidates.append(SearchRoot("local repo: Noahhawkes/oracle-ai-runtime", ROOT))
    seen: set[str] = set()
    roots: list[SearchRoot] = []
    for root in candidates:
        key = normalize_path(root.path).lower()
        if key not in seen and root.path.exists():
            seen.add(key)
            roots.append(root)
    return roots


def source_system_for(path: Path) -> str:
    norm = normalize_path(path).lower()
    if normalize_path(ROOT).lower() in norm:
        return "local_git_repo"
    if norm.startswith("c:/oracle/"):
        return "local_oracle_root"
    if norm.startswith("c:/oracle.ai/"):
        return "local_oracle_ai_root"
    if norm.startswith("g:/my drive/"):
        return "google_drive_mounted"
    if "/onedrive" in norm or "\\onedrive" in str(path).lower():
        return "onedrive_mounted"
    if "/.codex/" in norm:
        return "codex_attachment_cache"
    if norm.startswith("c:/users/noahh/"):
        return "user_home"
    return "local_filesystem"


def sensitivity_for(path: Path) -> str:
    norm = normalize_path(path).lower()
    if any(term in norm for term in SENSITIVE_PATH_TERMS):
        return "high"
    if path.suffix.lower() in {".env", ".key", ".pem", ".pfx", ".sqlite", ".db"}:
        return "high"
    return "standard"


def root_label_for(path: Path, roots: Iterable[SearchRoot]) -> str:
    norm = normalize_path(path).lower()
    best = ""
    best_label = "unknown"
    for root in roots:
        root_norm = normalize_path(root.path).lower()
        if norm.startswith(root_norm) and len(root_norm) > len(best):
            best = root_norm
            best_label = root.label
    return best_label


def match_surface_for(path: Path, roots: Iterable[SearchRoot]) -> str:
    """Return path text used for marker matching.

    The configured root itself is not treated as a match. This prevents a scan
    root such as C:/Oracle or a pytest folder named test_oracle_* from making
    every child file look ORACLE-adjacent.
    """
    best_root = None
    best_len = -1
    norm = normalize_path(path).lower()
    for root in roots:
        root_norm = normalize_path(root.path).lower()
        if norm.startswith(root_norm) and len(root_norm) > best_len:
            best_root = root.path
            best_len = len(root_norm)
    if best_root is not None:
        try:
            return str(path.relative_to(best_root)).replace("\\", "/")
        except ValueError:
            pass
    return path.name


def should_skip_dir(path: Path) -> bool:
    return path.name.lower() in SKIP_DIR_NAMES


def iter_files(
    roots: list[SearchRoot],
    *,
    max_files_scanned: int | None = None,
    max_seconds: float | None = None,
) -> tuple[list[Path], list[dict], dict]:
    files: list[Path] = []
    inaccessible: list[dict] = []
    seen: set[str] = set()
    started = time.monotonic()
    scanned = 0
    status = {
        "completed": True,
        "files_seen": 0,
        "limit_reason": None,
    }
    for root in roots:
        stack = [root.path]
        while stack:
            if max_seconds is not None and (time.monotonic() - started) >= max_seconds:
                status.update({
                    "completed": False,
                    "files_seen": scanned,
                    "limit_reason": f"max_seconds_reached:{max_seconds}",
                })
                inaccessible.append({"path": str(stack[-1]), "root": root.label, "reason": status["limit_reason"]})
                return files, inaccessible, status
            current = stack.pop()
            try:
                with os.scandir(current) as entries:
                    for entry in entries:
                        try:
                            p = Path(entry.path)
                            if entry.is_dir(follow_symlinks=False):
                                if should_skip_dir(p):
                                    continue
                                stack.append(p)
                            elif entry.is_file(follow_symlinks=False):
                                scanned += 1
                                if max_files_scanned is not None and scanned > max_files_scanned:
                                    status.update({
                                        "completed": False,
                                        "files_seen": scanned,
                                        "limit_reason": f"max_files_scanned_reached:{max_files_scanned}",
                                    })
                                    inaccessible.append({"path": entry.path, "root": root.label, "reason": status["limit_reason"]})
                                    return files, inaccessible, status
                                key = normalize_path(p).lower()
                                if key not in seen:
                                    seen.add(key)
                                    files.append(p)
                        except OSError as exc:
                            inaccessible.append({
                                "path": entry.path,
                                "root": root.label,
                                "reason": f"{type(exc).__name__}: {exc}",
                            })
            except OSError as exc:
                inaccessible.append({
                    "path": str(current),
                    "root": root.label,
                    "reason": f"{type(exc).__name__}: {exc}",
                })
    status["files_seen"] = scanned
    return files, inaccessible, status


def artifact_record(
    path: Path,
    roots: list[SearchRoot],
    *,
    max_content_bytes: int,
    max_hash_bytes: int,
) -> tuple[dict | None, dict | None]:
    try:
        stat = path.stat()
    except OSError as exc:
        return None, {"path": str(path), "reason": f"stat_failed: {type(exc).__name__}: {exc}"}

    path_text = normalize_path(path)
    terms = set(text_matches_markers(match_surface_for(path, roots) + " " + path.name))
    try:
        if should_scan_content(path, int(stat.st_size), max_content_bytes):
            terms.update(text_matches_markers(read_content_sample(path, max_content_bytes)))
    except OSError as exc:
        return None, {"path": path_text, "reason": f"content_scan_failed: {type(exc).__name__}: {exc}"}

    if not terms:
        return None, None

    if stat.st_size > max_hash_bytes:
        return None, {
            "path": path_text,
            "reason": f"matched_but_too_large_to_hash_first_pass: {stat.st_size} > {max_hash_bytes}",
        }

    try:
        sha = hash_file(path)
    except OSError as exc:
        return None, {"path": path_text, "reason": f"hash_failed: {type(exc).__name__}: {exc}"}

    record = {
        "source_path": path_text,
        "source_root": root_label_for(path, roots),
        "source_system": source_system_for(path),
        "filename": path.name,
        "extension": path.suffix.lower(),
        "size_bytes": int(stat.st_size),
        "created_at": utc_iso(getattr(stat, "st_ctime", None)),
        "modified_at": utc_iso(getattr(stat, "st_mtime", None)),
        "sha256": sha,
        "matched_terms": sorted(terms),
        "custody_status": "observed",
        "copy_status": "not_copied",
        "store_status": "indexed",
        "canon_status": "candidate",
        "promotion_status": "not_promoted",
        "sensitivity": sensitivity_for(path),
        "notes": "Metadata-only custody candidate. No copy/upload/content duplication performed.",
    }
    return record, None


def annotate_duplicates(records: list[dict]) -> list[dict]:
    counts = Counter(record["sha256"] for record in records)
    for record in records:
        count = counts[record["sha256"]]
        record["duplicate_count"] = count
        record["duplicate_group_id"] = f"sha256:{record['sha256']}" if count > 1 else None
    return records


def next_copy_candidates(records: list[dict], limit: int = 12) -> list[dict]:
    def score(record: dict) -> tuple:
        extension_bonus = 2 if record.get("extension") in {".md", ".json", ".jsonl", ".txt", ".py"} else 0
        sensitivity_penalty = -2 if record.get("sensitivity") == "high" else 0
        duplicate_penalty = -1 if int(record.get("duplicate_count") or 1) > 1 else 0
        return (
            len(record.get("matched_terms") or []),
            extension_bonus + sensitivity_penalty + duplicate_penalty,
            -int(record.get("size_bytes") or 0),
            str(record.get("source_path") or ""),
        )

    ranked = sorted(records, key=score, reverse=True)
    return [
        {
            "source_path": record["source_path"],
            "sha256": record["sha256"],
            "matched_terms": record["matched_terms"],
            "sensitivity": record["sensitivity"],
            "reason": "High marker density and small metadata/custody value; copy still requires Noah.Physical approval.",
        }
        for record in ranked[:limit]
    ]


def summarize(records: list[dict], inaccessible: list[dict], roots: list[SearchRoot], scan_status: dict | None = None) -> dict:
    by_root = Counter(record["source_root"] for record in records)
    by_source_system = Counter(record["source_system"] for record in records)
    term_counts = Counter(term for record in records for term in record["matched_terms"])
    duplicates = [
        {
            "sha256": sha,
            "count": len(group),
            "paths": [item["source_path"] for item in group[:8]],
        }
        for sha, group in _group_by_sha(records).items()
        if len(group) > 1
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest_path": str(MANIFEST_PATH.resolve()),
        "search_roots": [{"label": root.label, "path": normalize_path(root.path)} for root in roots],
        "artifact_count": len(records),
        "counts_by_root": dict(sorted(by_root.items())),
        "counts_by_source_system": dict(sorted(by_source_system.items())),
        "matched_terms": dict(sorted(term_counts.items())),
        "duplicate_group_count": len(duplicates),
        "duplicate_file_count": sum(item["count"] for item in duplicates),
        "duplicates": duplicates[:50],
        "inaccessible_count": len(inaccessible),
        "inaccessible_files": inaccessible[:200],
        "scan_status": scan_status or {"completed": True},
        "next_recommended_copy_candidates": next_copy_candidates(records),
        "rules": {
            "observe": "discover and hash ORACLE-adjacent artifacts",
            "copy": "not performed without explicit Noah.Physical approval",
            "store": "manifest and receipt written; no raw content duplication",
            "canon_status": "candidate",
            "promotion_status": "not_promoted",
            "cloud_upload": False,
            "git_push": False,
            "execution": False,
        },
    }


def _group_by_sha(records: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        groups[record["sha256"]].append(record)
    return groups


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")


def run_sweep(
    roots: list[Path | str] | None = None,
    *,
    output_dir: Path | str | None = None,
    max_content_bytes: int = 2 * 1024 * 1024,
    max_hash_bytes: int = 256 * 1024 * 1024,
    max_files_scanned: int | None = None,
    max_seconds: float | None = None,
) -> dict:
    search_roots = (
        [SearchRoot(str(Path(root)).replace("\\", "/"), Path(root)) for root in roots]
        if roots is not None
        else discover_default_roots()
    )
    search_roots = [root for root in search_roots if root.path.exists()]
    files, inaccessible, scan_status = iter_files(
        search_roots,
        max_files_scanned=max_files_scanned,
        max_seconds=max_seconds,
    )
    records: list[dict] = []
    for path in files:
        record, error = artifact_record(
            path,
            search_roots,
            max_content_bytes=max_content_bytes,
            max_hash_bytes=max_hash_bytes,
        )
        if error:
            inaccessible.append(error)
        if record:
            records.append(record)
    records = annotate_duplicates(sorted(records, key=lambda item: item["source_path"].lower()))

    out_dir = Path(output_dir) if output_dir is not None else OUTPUT_DIR
    manifest_path = out_dir / "oracle_artifact_manifest.jsonl"
    receipt_latest = out_dir / "oracle_custody_sweep_receipt_latest.json"
    write_jsonl(manifest_path, records)
    receipt = summarize(records, inaccessible, search_roots, scan_status)
    receipt["manifest_path"] = str(manifest_path.resolve())
    receipt["receipt_path"] = str(receipt_latest.resolve())
    receipt["required_fields"] = list(REQUIRED_FIELDS)
    write_json(receipt_latest, receipt)
    stamped = out_dir / f"oracle_custody_sweep_receipt_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    write_json(stamped, receipt)
    receipt["timestamped_receipt_path"] = str(stamped.resolve())
    write_json(receipt_latest, receipt)
    return receipt


def _main() -> int:
    parser = argparse.ArgumentParser(description="Observe/hash/index ORACLE-adjacent artifacts.")
    parser.add_argument("--root", action="append", default=None, help="Root to scan. Repeatable.")
    parser.add_argument("--output-dir", default=None, help="Manifest output directory.")
    parser.add_argument("--max-content-bytes", type=int, default=2 * 1024 * 1024)
    parser.add_argument("--max-hash-bytes", type=int, default=256 * 1024 * 1024)
    parser.add_argument("--max-files-scanned", type=int, default=None)
    parser.add_argument("--max-seconds", type=float, default=None)
    args = parser.parse_args()
    receipt = run_sweep(
        roots=args.root,
        output_dir=args.output_dir,
        max_content_bytes=args.max_content_bytes,
        max_hash_bytes=args.max_hash_bytes,
        max_files_scanned=args.max_files_scanned,
        max_seconds=args.max_seconds,
    )
    print(json.dumps({
        "manifest_path": receipt["manifest_path"],
        "receipt_path": receipt["receipt_path"],
        "artifact_count": receipt["artifact_count"],
        "counts_by_root": receipt["counts_by_root"],
        "counts_by_source_system": receipt["counts_by_source_system"],
        "duplicate_group_count": receipt["duplicate_group_count"],
        "inaccessible_count": receipt["inaccessible_count"],
        "scan_status": receipt["scan_status"],
    }, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
