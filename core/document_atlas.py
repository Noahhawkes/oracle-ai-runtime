"""Read-only document atlas for ORACLE.

Discovers document-bearing files across approved local drives, classifies them
as candidate continuity material, and writes a metadata index plus a receipt.
It never moves, deletes, uploads, promotes canon, or stores raw document text.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from root import ROOT
except Exception:  # pragma: no cover
    ROOT = Path(__file__).resolve().parents[1]


DEFAULT_CUTOFF = "2024-07-17T00:00:00Z"
DEFAULT_ROOTS = (Path("C:/"), Path("G:/"))
OUTPUT_DIR = ROOT / "Memory" / "document_atlas"

DOCUMENT_EXTENSIONS = {".doc", ".docx", ".gdoc", ".odt", ".rtf", ".txt"}
TEXT_SAMPLE_BYTES = 96_000
MAX_SAMPLE_CHARS = 16_000

# Operating-system, dependency, cache, credential, and duplicate-mirror noise.
# These exclusions are recorded in every receipt; they are never presented as
# scanned content.
SKIP_DIR_NAMES = {
    "$recycle.bin", "system volume information", "recovery", "windows",
    "program files", "program files (x86)", "programdata", "perflogs",
    "config.msi", "documents and settings", "onedrivetemp", "python313",
    "xboxgames", "$sysreset", "appdata", "n360_backup", ".git", "node_modules", "__pycache__", ".pytest_cache",
    ".venv", "venv", "dist", "build", "site-packages", ".encrypted",
    ".shortcut-targets-by-id", "sandbox.trash", "credentials", "secrets",
    ".ssh", ".aws", ".gnupg", ".azure", ".kube", ".docker",
}
BLOCKED_NAME_PATTERN = re.compile(
    r"(credential|secret|password|passwd|api[_-]?key|token|oauth|\.env$|\.pem$|\.key$)",
    re.IGNORECASE,
)

CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("thread_and_conversation", ("thread injection", "threadmerge", "chatgpt thread", "transcript", "conversation", "session")),
    ("oracle_runtime_and_doctrine", ("oracle", "continuity engine", "continuity intelligence", "cognitive world projection", "miracledrive")),
    ("ecowater_and_professional", ("ecowater", "bdm", "dealer", "water treatment", "work proposal", "sales")),
    ("rendered_reality_and_worldbuilding", ("rendered reality", "jupiter station", "avalon", "world bible", "elderhawkes", "npc")),
    ("identity_and_legacy", ("legacy.gi", "legacygi", "compression is identity", "identity", "memory is morality", "sovereignty is structure")),
    ("sov1_governance_and_compliance", ("sov1", "governance", "compliance", "approval gate", "provenance", "audit")),
    ("patent_invention_and_research", ("patent", "invention", "claims", "dissertation", "research", "specification", "spec")),
    ("personal_and_relationship", ("ashley", "family", "journal", "personal", "dad", "father", "ender", "eli")),
    ("creative_writing", ("chapter", "manuscript", "story", "novel", "screenplay", "book")),
    ("administrative_and_legal", ("contract", "invoice", "tax", "legal", "agreement", "policy", "resume")),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_cutoff(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _sample_text(path: Path) -> tuple[str, int, str | None]:
    """Return an in-memory sample, sampled character count, and optional URL.

    The caller uses the sample for deterministic classification. The sample is
    intentionally not persisted in the atlas.
    """
    ext = path.suffix.lower()
    try:
        if ext == ".docx":
            with zipfile.ZipFile(path) as archive:
                xml = archive.read("word/document.xml").decode("utf-8", errors="replace")
            text = re.sub(r"</w:p>", "\n", xml)
            text = _clean(re.sub(r"<[^>]+>", " ", text))[:MAX_SAMPLE_CHARS]
            return text, len(text), None
        if ext == ".odt":
            with zipfile.ZipFile(path) as archive:
                xml = archive.read("content.xml").decode("utf-8", errors="replace")
            text = _clean(re.sub(r"<[^>]+>", " ", xml))[:MAX_SAMPLE_CHARS]
            return text, len(text), None
        raw = path.read_bytes()[:TEXT_SAMPLE_BYTES]
        text = _clean(raw.decode("utf-8", errors="replace"))[:MAX_SAMPLE_CHARS]
        if ext == ".gdoc":
            try:
                payload = json.loads(text)
                url = payload.get("url") or payload.get("doc_id")
            except Exception:
                match = re.search(r"https://docs\.google\.com/[^\s\"']+", text)
                url = match.group(0) if match else None
            return text, len(text), url
        return text, len(text), None
    except Exception:
        return "", 0, None


def classify_candidate(path: Path, sample: str = "") -> tuple[str, list[str]]:
    haystack = _clean(f"{path.name} {path.parent} {sample[:6000]}").lower()
    scored: list[tuple[int, int, str, list[str]]] = []
    for order, (category, terms) in enumerate(CATEGORY_RULES):
        matches = sorted({term for term in terms if term in haystack})
        if matches:
            scored.append((len(matches), -order, category, matches[:8]))
    if not scored:
        return "general_document_candidate", []
    _, _, category, signals = max(scored)
    return category, signals


def _fingerprint(path: Path, size: int) -> str:
    """Bounded content fingerprint; not a claim of a full-file hash."""
    digest = hashlib.sha256()
    digest.update(str(size).encode("ascii"))
    try:
        with path.open("rb") as handle:
            digest.update(handle.read(64_000))
            if size > 64_000:
                handle.seek(max(0, size - 64_000))
                digest.update(handle.read(64_000))
    except Exception:
        digest.update(str(path).encode("utf-8", errors="replace"))
    return digest.hexdigest()


def _metadata_fingerprint(path: Path, size: int, modified_ns: int) -> str:
    """Fingerprint without opening a cloud-backed file."""
    payload = f"{path.resolve(strict=False)}|{size}|{modified_ns}"
    return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()


def _is_cloud_backed_path(path: Path) -> bool:
    value = str(path).lower().replace("/", "\\")
    return (
        value.startswith("g:\\")
        or "\\onedrive\\" in value
        or "\\iclouddrive\\" in value
        or "\\google drive\\" in value
    )


def _walk(root: Path, stats: dict[str, Any]) -> Iterable[Path]:
    def onerror(exc: OSError) -> None:
        stats["walk_errors"] += 1
        if len(stats["error_samples"]) < 25:
            stats["error_samples"].append(str(exc))

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, onerror=onerror):
        kept = []
        for name in dirnames:
            lower = name.lower()
            if lower in SKIP_DIR_NAMES or lower.endswith(".worktrees"):
                stats["directories_skipped"] += 1
            else:
                kept.append(name)
        dirnames[:] = kept
        for filename in filenames:
            if BLOCKED_NAME_PATTERN.search(filename):
                stats["sensitive_names_skipped"] += 1
                continue
            path = Path(dirpath) / filename
            if path.suffix.lower() in DOCUMENT_EXTENSIONS:
                yield path


def scan_documents(
    roots: Iterable[Path] = DEFAULT_ROOTS,
    *,
    cutoff: str = DEFAULT_CUTOFF,
    sample_local_content: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cutoff_dt = _parse_cutoff(cutoff)
    stats: dict[str, Any] = {
        "walk_errors": 0,
        "error_samples": [],
        "directories_skipped": 0,
        "sensitive_names_skipped": 0,
        "stat_errors": 0,
        "older_than_cutoff": 0,
        "roots_scanned": [],
        "roots_missing": [],
    }
    records: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    for root in roots:
        root = Path(root)
        if not root.exists():
            stats["roots_missing"].append(str(root))
            continue
        stats["roots_scanned"].append(str(root.resolve(strict=False)))
        for path in _walk(root, stats):
            key = str(path.resolve(strict=False)).lower()
            if key in seen_paths:
                continue
            seen_paths.add(key)
            try:
                stat = path.stat()
            except OSError:
                stats["stat_errors"] += 1
                continue
            modified = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
            if modified < cutoff_dt:
                stats["older_than_cutoff"] += 1
                continue

            # Google Drive for Desktop is metadata-only by default so the atlas
            # never bulk-downloads cloud content. Tiny .gdoc pointers are safe.
            is_drive_stream = str(path).lower().startswith("g:\\")
            is_cloud_backed = _is_cloud_backed_path(path)
            may_sample = sample_local_content and (not is_cloud_backed or path.suffix.lower() == ".gdoc")
            sample, sampled_chars, google_url = _sample_text(path) if may_sample else ("", 0, None)
            category, signals = classify_candidate(path, sample)
            fingerprint_kind = (
                "metadata_path_size_mtime_sha256" if is_cloud_backed
                else "bounded_first_last_64k_sha256"
            )
            fingerprint = (
                _metadata_fingerprint(path, stat.st_size, stat.st_mtime_ns) if is_cloud_backed
                else _fingerprint(path, stat.st_size)
            )
            records.append({
                "record_type": "document_candidate",
                "path": str(path.resolve(strict=False)),
                "name": path.name,
                "extension": path.suffix.lower(),
                "size_bytes": stat.st_size,
                "modified_at": modified.isoformat().replace("+00:00", "Z"),
                "created_at": datetime.fromtimestamp(stat.st_ctime, timezone.utc).isoformat().replace("+00:00", "Z"),
                "source_surface": (
                    "google_drive_filesystem" if is_drive_stream
                    else "cloud_sync_filesystem" if is_cloud_backed
                    else "local_filesystem"
                ),
                "google_url": google_url,
                "candidate_category": category,
                "classification_signals": signals,
                "classification_confidence": round(min(0.95, 0.40 + 0.09 * len(signals)), 2),
                "content_sampled_chars": sampled_chars,
                "content_stored": False,
                "fingerprint_kind": fingerprint_kind,
                "fingerprint": fingerprint,
                "canon_status": "candidate",
            })

    records.sort(key=lambda item: (item["modified_at"], item["path"]), reverse=True)
    stats["record_count"] = len(records)
    stats["by_extension"] = dict(sorted(Counter(item["extension"] for item in records).items()))
    stats["by_category"] = dict(sorted(Counter(item["candidate_category"] for item in records).items()))
    stats["by_surface"] = dict(sorted(Counter(item["source_surface"] for item in records).items()))
    stats["content_sampled_count"] = sum(1 for item in records if item["content_sampled_chars"])
    return records, stats


def write_atlas(
    records: list[dict[str, Any]],
    stats: dict[str, Any],
    *,
    cutoff: str = DEFAULT_CUTOFF,
    output_dir: Path = OUTPUT_DIR,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "document_atlas_latest.jsonl"
    summary_path = output_dir / "document_atlas_latest.md"
    receipt_path = output_dir / "document_atlas_receipt_latest.json"

    with jsonl_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
    index_hash = hashlib.sha256(jsonl_path.read_bytes()).hexdigest()

    summary_lines = [
        "# ORACLE Document Atlas",
        "",
        f"Generated: {_now()}",
        f"Cutoff: {cutoff}",
        f"Candidates indexed: {len(records):,}",
        "",
        "## Boundary",
        "",
        "Read-only discovery and candidate classification. No document content is stored in the atlas. "
        "No files were moved, deleted, renamed, uploaded, externally sent, or promoted to canon.",
        "",
        "## Coverage",
        "",
        f"- Roots scanned: {', '.join(stats.get('roots_scanned') or []) or 'none'}",
        f"- Missing roots: {', '.join(stats.get('roots_missing') or []) or 'none'}",
        f"- Directories skipped by boundary/noise rules: {stats.get('directories_skipped', 0):,}",
        f"- Inaccessible walk locations: {stats.get('walk_errors', 0):,}",
        f"- Older candidates outside the two-year window: {stats.get('older_than_cutoff', 0):,}",
        "",
        "## By source surface",
        "",
    ]
    summary_lines.extend(f"- {key}: {value:,}" for key, value in stats.get("by_surface", {}).items())
    summary_lines.extend(["", "## By file type", ""])
    summary_lines.extend(f"- {key}: {value:,}" for key, value in stats.get("by_extension", {}).items())
    summary_lines.extend(["", "## Candidate categories", ""])
    summary_lines.extend(f"- {key}: {value:,}" for key, value in stats.get("by_category", {}).items())
    summary_lines.extend([
        "", "## Classification rule", "",
        "Every record remains `candidate`. Classification uses deterministic filename, path, and bounded in-memory text signals. "
        "Local text samples are discarded after classification; Google Drive for Desktop content is metadata-only unless it is a tiny `.gdoc` pointer.",
        "", f"Index SHA-256: `{index_hash}`", "",
    ])
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")

    receipt = {
        "receipt_kind": "document_atlas_receipt",
        "schema_version": "document_atlas.v1",
        "generated_at": _now(),
        "cutoff": cutoff,
        "record_count": len(records),
        "index_path": str(jsonl_path),
        "summary_path": str(summary_path),
        "index_sha256": index_hash,
        "stats": stats,
        "boundary": {
            "read_only_discovery": True,
            "content_stored": False,
            "canon_promotion": False,
            "file_mutation": False,
            "drive_mutation": False,
            "external_send": False,
        },
    }
    receipt["receipt_sha256"] = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    return {"index": str(jsonl_path), "summary": str(summary_path), "receipt": str(receipt_path), **receipt}


def build_atlas(
    roots: Iterable[Path] = DEFAULT_ROOTS,
    *,
    cutoff: str = DEFAULT_CUTOFF,
    output_dir: Path = OUTPUT_DIR,
) -> dict[str, Any]:
    records, stats = scan_documents(roots, cutoff=cutoff)
    return write_atlas(records, stats, cutoff=cutoff, output_dir=output_dir)


def merge_connector_atlas(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    """Merge local atlas records with connector snapshots into one read index."""
    local_path = output_dir / "document_atlas_latest.jsonl"
    connector_paths = [
        output_dir / "google_drive_connector_latest.json",
        output_dir / "google_drive_connector_refinement_latest.json",
        output_dir / "google_drive_connector_refinement_v2_latest.json",
        output_dir / "google_drive_connector_refinement_v3_latest.json",
    ]
    local_records: list[dict[str, Any]] = []
    if local_path.exists():
        for line in local_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                local_records.append(json.loads(line))

    connector_records: dict[str, dict[str, Any]] = {}
    connector_meta: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for path in connector_paths:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        connector_meta.append({
            "path": str(path),
            "schema_version": payload.get("schema_version"),
            "record_count": len(payload.get("records") or []),
        })
        unresolved = payload.get("unresolved_saturated_intervals") or unresolved
        for record in payload.get("records") or []:
            key = str(record.get("id") or record.get("url") or record.get("name"))
            connector_records[key] = record

    connector_ids = set(connector_records)
    unified: list[dict[str, Any]] = list(connector_records.values())
    gdoc_duplicates = 0
    for record in local_records:
        url = str(record.get("google_url") or "")
        match = re.search(r"/d/([^/?#]+)", url)
        if match and match.group(1) in connector_ids:
            gdoc_duplicates += 1
            continue
        unified.append(record)
    unified.sort(key=lambda item: (str(item.get("modified_at") or ""), str(item.get("name") or "")), reverse=True)

    unified_path = output_dir / "unified_document_atlas_latest.jsonl"
    with unified_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in unified:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
    digest = hashlib.sha256(unified_path.read_bytes()).hexdigest()
    stats = {
        "unified_record_count": len(unified),
        "local_record_count": len(local_records),
        "connector_unique_record_count": len(connector_records),
        "gdoc_pointer_duplicates_removed": gdoc_duplicates,
        "by_surface": dict(sorted(Counter(item.get("source_surface", "unknown") for item in unified).items())),
        "by_category": dict(sorted(Counter(item.get("candidate_category", "unknown") for item in unified).items())),
        "by_extension_or_mime": dict(sorted(Counter(
            item.get("extension") or item.get("mime_type") or "unknown" for item in unified
        ).items())),
    }
    summary_path = output_dir / "unified_document_atlas_latest.md"
    lines = [
        "# ORACLE Unified Document Atlas",
        "",
        f"Generated: {_now()}",
        f"Indexed candidate records: {len(unified):,}",
        f"Local/Drive-for-Desktop records: {len(local_records):,}",
        f"Unique Google Drive connector records: {len(connector_records):,}",
        f"Duplicate `.gdoc` pointers removed: {gdoc_duplicates:,}",
        "",
        "## Boundary",
        "",
        "This is a read-only candidate atlas, not canon. It stores metadata and classification signals, not raw document content. "
        "No source files or Google Drive objects were changed.",
        "",
        "## Source surfaces",
        "",
    ]
    lines.extend(f"- {key}: {value:,}" for key, value in stats["by_surface"].items())
    lines.extend(["", "## Candidate categories", ""])
    lines.extend(f"- {key}: {value:,}" for key, value in stats["by_category"].items())
    lines.extend(["", "## Connector coverage note", ""])
    if unresolved:
        lines.append(
            f"- {len(unresolved)} sub-minute Drive import intervals still returned the connector maximum of 200 results. "
            "Drive-for-Desktop metadata is indexed separately and may cover those mirrors; connector completeness is not claimed for these intervals."
        )
    else:
        lines.append("- No connector interval remained saturated after refinement.")
    lines.extend(["", f"Unified index SHA-256: `{digest}`", ""])
    summary_path.write_text("\n".join(lines), encoding="utf-8")

    receipt = {
        "receipt_kind": "unified_document_atlas_receipt",
        "schema_version": "document_atlas.unified.v1",
        "generated_at": _now(),
        "index_path": str(unified_path),
        "summary_path": str(summary_path),
        "index_sha256": digest,
        "stats": stats,
        "connector_snapshots": connector_meta,
        "unresolved_connector_intervals": unresolved,
        "boundary": {
            "candidate_only": True,
            "raw_content_stored": False,
            "canon_promotion": False,
            "file_mutation": False,
            "drive_mutation": False,
            "external_send": False,
        },
    }
    receipt["receipt_sha256"] = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    receipt_path = output_dir / "unified_document_atlas_receipt_latest.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    return {"index": str(unified_path), "summary": str(summary_path), "receipt": str(receipt_path), **receipt}


def atlas_status(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    receipt_path = output_dir / "unified_document_atlas_receipt_latest.json"
    if not receipt_path.exists():
        return {"ok": False, "available": False, "error": "unified document atlas not built"}
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    return {
        "ok": True,
        "available": True,
        "generated_at": receipt.get("generated_at"),
        "index_path": receipt.get("index_path"),
        "summary_path": receipt.get("summary_path"),
        "index_sha256": receipt.get("index_sha256"),
        "stats": receipt.get("stats") or {},
        "records": (receipt.get("stats") or {}).get("unified_record_count", 0),
        "unresolved_connector_intervals": receipt.get("unresolved_connector_intervals") or [],
        "boundary": receipt.get("boundary") or {},
    }


def search_atlas(query: str, limit: int = 20, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    terms = [term.lower() for term in _clean(query).split() if term]
    if not terms:
        raise ValueError("query is required")
    bounded_limit = max(1, min(int(limit), 100))
    index_path = output_dir / "unified_document_atlas_latest.jsonl"
    if not index_path.exists():
        return {"ok": False, "query": query, "results": [], "error": "unified document atlas not built"}
    results: list[dict[str, Any]] = []
    with index_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            searchable = " ".join(str(record.get(key) or "") for key in (
                "name", "path", "candidate_category", "classification_signals", "source_surface"
            )).lower()
            if all(term in searchable for term in terms):
                results.append(record)
                if len(results) >= bounded_limit:
                    break
    return {
        "ok": True,
        "query": query,
        "result_count": len(results),
        "results": results,
        "index_path": str(index_path),
        "boundary": {
            "read_only": True, "candidate_only": True, "raw_content_stored": False,
            "file_mutation": False, "drive_mutation": False, "canon_promotion": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ORACLE's read-only document atlas")
    parser.add_argument("--root", action="append", default=[], help="Filesystem root to scan (repeatable)")
    parser.add_argument("--cutoff", default=DEFAULT_CUTOFF)
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--merge-connectors", action="store_true")
    args = parser.parse_args()
    if args.merge_connectors:
        print(json.dumps(merge_connector_atlas(Path(args.output_dir)), indent=2, sort_keys=True))
        return 0
    roots = [Path(value) for value in args.root] or list(DEFAULT_ROOTS)
    result = build_atlas(roots, cutoff=args.cutoff, output_dir=Path(args.output_dir))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
