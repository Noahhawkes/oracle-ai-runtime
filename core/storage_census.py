"""ORACLE Storage Census v0.1 — governed, read-only storage discovery.

This feature does NOT define governance. It imports and obeys the existing
ORACLE governance authority (``core/governance.py``) and the ratified root
authority (``core/root_map.py``). If governance cannot be loaded, the census
fails closed.

Census == discovery (metadata only): path, filename, root, size, extension,
modified time, classification, risk flags, and an optional hash. It never reads
credential contents, never ingests/summarizes/embeds/promotes content, never
uploads, syncs, deletes, moves, renames, commits, or pushes, and never merges
candidates into the canonical SourceMap automatically.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from root_map import RATIFIED_STATE_ROOT, FORBIDDEN_RUNTIME_ROOTS
except Exception:  # pragma: no cover - direct execution fallback
    RATIFIED_STATE_ROOT = Path(r"C:\Oracle\state")
    FORBIDDEN_RUNTIME_ROOTS = ()


STATE_ROOT = Path(RATIFIED_STATE_ROOT)
STORAGE_DIR = STATE_ROOT / "storage"
SOURCES_DIR = STATE_ROOT / "sources"
RECEIPTS_DIR = STATE_ROOT / "receipts"
ROOTS_STATE_FILE = STORAGE_DIR / "storage_census_roots.json"

BLOCKED_MESSAGE = "Storage Census blocked: governance state unavailable."

# Roots.
DEFAULT_APPROVED_ROOT = Path(r"C:\Oracle")
KNOWN_CANDIDATE_ROOTS = [
    Path(r"C:\ORACLE.AI"),
    Path(r"G:\My Drive\HawkesNest LLC\ORACLE.AI"),
]

# Never scanned, regardless of approval.
EXCLUDED_DIR_NAMES = {"node_modules", ".venv", "venv", ".git", "__pycache__"}
EXCLUDED_ABS_PREFIXES = [
    Path(r"C:\Windows"),
    Path(r"C:\Program Files"),
    Path(r"C:\Program Files (x86)"),
    Path(r"C:\Users\noahh\AppData"),
    Path(r"C:\$Recycle.Bin"),
    Path(r"C:\System Volume Information"),
]

# Safety cap so a census can never run away on an over-broad root.
MAX_FILES_PER_CENSUS = 200_000
MAX_HASH_BYTES = 8 * 1024 * 1024

ORACLE_INDICATORS = (
    "oracle", "sov1", "renderedreality", "rendered reality", "miracledrive",
    "sourcemap", "source_map", "hydra", "legacy.gi", "legacygi", "noah ai",
    "noahai", "continuity", "mindcoin", "lootdrop", "flamevault", "receipt",
)
CREDENTIAL_INDICATORS = (
    "key", "token", "secret", "password", "credential", ".env", "alive",
    "id_rsa", "ssh", "pem", "p12", "pfx", "private", "\U0001f5dd",
)
CREDENTIAL_RISK_MESSAGE = "credential-risk file detected, rotation/quarantine required"

CANDIDATE_STATUS = "candidate_pending_noah_approval"

MEDIA_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".mp3", ".wav", ".flac", ".m4a"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".heic"}
DOC_EXT = {".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".odt"}
SHEET_EXT = {".xls", ".xlsx", ".csv", ".ods"}
SLIDE_EXT = {".ppt", ".pptx", ".odp"}
ARCHIVE_EXT = {".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz"}
CODE_EXT = {".py", ".js", ".ts", ".bat", ".ps1", ".html", ".css", ".json", ".jsonl", ".sh"}


# ── helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _norm(path: Path | str) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path) -> Any:
    try:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


# ── governance integration (obey, never replace) ──────────────────────────────

def load_governance() -> dict[str, Any] | None:
    """Load resolved governance posture from the existing authority.

    Returns None (fail closed) if governance cannot be imported/loaded.
    """

    try:
        import governance as gov  # core/governance.py
        gov.load()
        summary = gov.governance_summary()
        return {
            "source": getattr(gov, "__file__", "core/governance.py"),
            "summary": summary,
            "approval_required": bool(gov.is_approval_required()),
            "sensitive_block": bool(gov.is_sensitive_block_active()),
            "local_only": bool(gov.is_local_mode_default()),
            "surveillance_mode": bool(summary.get("surveillance_mode")),
            "auto_approve": bool(gov.is_auto_approve_allowed()),
            "noah_sovereignty_pct": int(summary.get("noah_sovereignty_pct") or 0),
            "max_actions_per_batch": int(summary.get("max_actions_per_batch") or 0),
            "hashing_allowed": not bool(gov.is_sensitive_block_active()),
        }
    except Exception:
        return None


def _blocked() -> dict[str, Any]:
    return {"ok": False, "blocked": True, "governance_loaded": False, "message": BLOCKED_MESSAGE}


# ── roots ─────────────────────────────────────────────────────────────────────

def detect_onedrive_roots() -> list[Path]:
    candidates: list[Path] = []
    for env_name in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial", "ONEDRIVE"):
        val = os.environ.get(env_name)
        if val:
            candidates.append(Path(val))
    candidates.append(Path(r"C:\Users\noahh\OneDrive"))
    seen: set[str] = set()
    out: list[Path] = []
    for c in candidates:
        try:
            if c.exists() and _norm(c) not in seen:
                out.append(c)
                seen.add(_norm(c))
        except Exception:
            continue
    return out


def _approvable_roots() -> dict[str, Path]:
    roots: dict[str, Path] = {_norm(DEFAULT_APPROVED_ROOT): DEFAULT_APPROVED_ROOT}
    for p in list(KNOWN_CANDIDATE_ROOTS) + detect_onedrive_roots():
        roots[_norm(p)] = p
    return roots


def _load_root_state() -> tuple[set[str], set[str]]:
    data = _read_json(ROOTS_STATE_FILE) or {}
    approved = {_norm(p) for p in (data.get("approved") or [])}
    rejected = {_norm(p) for p in (data.get("rejected") or [])}
    return approved, rejected


def _save_root_state(approved: set[str], rejected: set[str]) -> None:
    _write_json(ROOTS_STATE_FILE, {
        "approved": sorted(approved),
        "rejected": sorted(rejected),
        "updated_at": _now(),
    })


def approved_roots() -> list[Path]:
    """Roots cleared for scanning: the default approved root plus any explicitly
    approved known/OneDrive roots. Rejected roots are excluded."""

    approved, rejected = _load_root_state()
    out: list[Path] = []
    seen: set[str] = set()
    ordered = [DEFAULT_APPROVED_ROOT] + KNOWN_CANDIDATE_ROOTS + detect_onedrive_roots()
    for root in ordered:
        key = _norm(root)
        is_default = key == _norm(DEFAULT_APPROVED_ROOT)
        if key in rejected and not is_default:
            continue
        if not (is_default or key in approved):
            continue
        try:
            if root.exists() and key not in seen:
                out.append(root)
                seen.add(key)
        except Exception:
            continue
    return out


def known_roots_not_scanned() -> list[dict[str, Any]]:
    scanned = {_norm(r) for r in approved_roots()}
    approved, rejected = _load_root_state()
    out: list[dict[str, Any]] = []
    for root in KNOWN_CANDIDATE_ROOTS + detect_onedrive_roots():
        key = _norm(root)
        if key in scanned:
            continue
        try:
            exists = root.exists()
        except Exception:
            exists = False
        is_drive_mirror = str(root).upper().startswith("G:")
        is_onedrive = "onedrive" in str(root).lower()
        out.append({
            "path": str(root),
            "exists": exists,
            "status": "rejected" if key in rejected else "known_candidate",
            "kind": "drive_mirror" if is_drive_mirror else ("onedrive_candidate" if is_onedrive else "known"),
            "note": "detected only — not scanned until Noah.Physical approves the exact root",
        })
    return out


def approve_root(path: str) -> dict[str, Any]:
    if load_governance() is None:
        return _blocked()
    key = _norm(path)
    approvable = _approvable_roots()
    if key not in approvable:
        return {
            "ok": False,
            "error": "root is not an approvable census candidate",
            "approvable": [str(p) for p in approvable.values()],
        }
    approved, rejected = _load_root_state()
    approved.add(key)
    rejected.discard(key)
    _save_root_state(approved, rejected)
    return {"ok": True, "approved": str(approvable[key]), "approved_roots": [str(r) for r in approved_roots()]}


def reject_root(path: str) -> dict[str, Any]:
    if load_governance() is None:
        return _blocked()
    key = _norm(path)
    if key == _norm(DEFAULT_APPROVED_ROOT):
        return {"ok": False, "error": "the default approved root C:\\Oracle cannot be rejected"}
    approved, rejected = _load_root_state()
    rejected.add(key)
    approved.discard(key)
    _save_root_state(approved, rejected)
    return {"ok": True, "rejected": str(path), "approved_roots": [str(r) for r in approved_roots()]}


def roots_payload() -> dict[str, Any]:
    gov = load_governance()
    if gov is None:
        return _blocked()
    return {
        "ok": True,
        "governance_loaded": True,
        "governance_source": gov["source"],
        "governance_summary": gov["summary"],
        "default_approved_root": str(DEFAULT_APPROVED_ROOT),
        "approved_roots": [str(r) for r in approved_roots()],
        "known_roots_not_scanned": known_roots_not_scanned(),
        "onedrive_roots_detected": [str(p) for p in detect_onedrive_roots()],
        "forbidden_runtime_roots": [str(p) for p in FORBIDDEN_RUNTIME_ROOTS],
        "note": "Discovery is read-only metadata. Approval expands scan scope; it never ingests content.",
    }


# ── classification ────────────────────────────────────────────────────────────

def is_credential_risk(name: str, full_path: str) -> bool:
    hay = (name + " " + full_path).lower()
    if any(ind in hay for ind in CREDENTIAL_INDICATORS if ind != "\U0001f5dd"):
        return True
    return "\U0001f5dd" in (name + full_path)


def is_oracle_related(name: str, full_path: str) -> bool:
    hay = (name + " " + full_path).lower()
    return any(ind in hay for ind in ORACLE_INDICATORS)


def classify(name: str, full_path: str, ext: str) -> str:
    lower_name = name.lower()
    lower_path = full_path.lower()

    if is_credential_risk(name, full_path):
        return "credential_risk"
    if "g:\\my drive" in lower_path or lower_path.startswith("g:/my drive"):
        return "drive_mirror"
    if "onedrive" in lower_path:
        return "onedrive_candidate"
    if "governance" in lower_name:
        return "governance"
    if "mindcoin" in lower_name and ext in (".jsonl", ".json"):
        return "mindcoin_ledger"
    if "lootdrop" in lower_name:
        return "lootdrop"
    if "source_map" in lower_name or "sourcemap" in lower_name:
        return "sourcemap_manifest"
    if "active_context" in lower_name:
        return "active_context"
    if "route" in lower_name or "router" in lower_name:
        return "routing"
    if "receipt" in lower_name or "\\receipts\\" in lower_path or "/receipts/" in lower_path:
        return "receipt"
    if "\\oracle\\state\\" in lower_path or "/oracle/state/" in lower_path:
        return "state_file"
    if any(g in lower_name for g in ("screenshot", "capture", "wow", "obs")) and ext in IMAGE_EXT | MEDIA_EXT:
        return "game_capture"
    if ext in ARCHIVE_EXT:
        return "archive"
    if ext in MEDIA_EXT:
        return "media"
    if ext in IMAGE_EXT:
        return "image"
    if ext in SHEET_EXT:
        return "spreadsheet"
    if ext in SLIDE_EXT:
        return "presentation"
    if ext in DOC_EXT:
        return "document"
    if ext in CODE_EXT:
        return "runtime_code"
    return "unknown"


def _is_excluded_dir(dir_path: str) -> bool:
    norm = _norm(dir_path)
    for prefix in EXCLUDED_ABS_PREFIXES:
        if norm == _norm(prefix) or norm.startswith(_norm(prefix) + os.sep):
            return True
    return False


# ── census ────────────────────────────────────────────────────────────────────

def _scan_root(root: Path, gov: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    entries: list[dict[str, Any]] = []
    warnings: list[str] = []
    hashing_allowed = bool(gov.get("hashing_allowed"))
    count = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # Prune excluded / symlinked directories in place.
        dirnames[:] = [
            d for d in dirnames
            if d not in EXCLUDED_DIR_NAMES
            and not os.path.islink(os.path.join(dirpath, d))
            and not _is_excluded_dir(os.path.join(dirpath, d))
        ]
        if _is_excluded_dir(dirpath):
            continue
        for fname in filenames:
            if count >= MAX_FILES_PER_CENSUS:
                warnings.append(f"census truncated at {MAX_FILES_PER_CENSUS} files under {root}")
                return entries, warnings
            full = os.path.join(dirpath, fname)
            try:
                if os.path.islink(full):
                    entries.append({
                        "path": full, "filename": fname, "root": str(root),
                        "size_bytes": 0, "extension": Path(fname).suffix.lower(),
                        "modified": None, "classification": "unknown",
                        "oracle_related": False, "risk_flags": ["symlink_not_followed"],
                        "sha256": None,
                    })
                    count += 1
                    continue
                st = os.stat(full)
            except Exception:
                continue
            ext = Path(fname).suffix.lower()
            credential = is_credential_risk(fname, full)
            oracle_related = is_oracle_related(fname, full)
            classification = classify(fname, full, ext)
            risk_flags: list[str] = []
            if credential:
                risk_flags.append("credential_risk")
            if ext in ARCHIVE_EXT:
                risk_flags.append("archive")

            sha256 = None
            if hashing_allowed and not credential and st.st_size <= MAX_HASH_BYTES:
                try:
                    sha256 = hashlib.sha256(Path(full).read_bytes()).hexdigest()
                except Exception:
                    sha256 = None

            entries.append({
                "path": full,
                "filename": fname,
                "root": str(root),
                "size_bytes": int(st.st_size),
                "extension": ext,
                "modified": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
                "classification": classification,
                "oracle_related": oracle_related,
                "risk_flags": risk_flags,
                "sha256": sha256,
            })
            count += 1
    return entries, warnings


def _mark_duplicates(entries: list[dict[str, Any]]) -> int:
    groups: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for e in entries:
        if e.get("size_bytes"):
            groups[(e["filename"].lower(), int(e["size_bytes"]))].append(e)
    dup_count = 0
    for members in groups.values():
        if len(members) > 1:
            for e in members:
                if "duplicate_candidate" not in e["risk_flags"]:
                    e["risk_flags"].append("duplicate_candidate")
                dup_count += 1
    return dup_count


def run_census() -> dict[str, Any]:
    """Scan only approved roots. Discovery only — no ingestion, no mutation."""

    gov = load_governance()
    if gov is None:
        return _blocked()

    roots = approved_roots()
    all_entries: list[dict[str, Any]] = []
    warnings: list[str] = []
    for root in roots:
        ents, warns = _scan_root(root, gov)
        all_entries.extend(ents)
        warnings.extend(warns)

    dup_count = _mark_duplicates(all_entries)
    credential_count = sum(1 for e in all_entries if "credential_risk" in e["risk_flags"])
    oracle_candidates = [
        e for e in all_entries
        if e["oracle_related"] and e["classification"] != "credential_risk"
    ]
    if credential_count:
        warnings.append(CREDENTIAL_RISK_MESSAGE)

    onedrive_detected = [str(p) for p in detect_onedrive_roots()]
    drive_detected = [
        str(p) for p in KNOWN_CANDIDATE_ROOTS
        if str(p).upper().startswith("G:") and _safe_exists(p)
    ]
    not_scanned = known_roots_not_scanned()

    stamp = _stamp()
    manifest = {
        "schema_version": 1,
        "census_kind": "oracle_storage_census",
        "census_id": _id("census"),
        "created_at": _now(),
        "governance_loaded": True,
        "governance_source": gov["source"],
        "governance_summary": gov["summary"],
        "approved_roots_scanned": [str(r) for r in roots],
        "known_roots_not_scanned": not_scanned,
        "onedrive_roots_detected": onedrive_detected,
        "drive_roots_detected": drive_detected,
        "counts": {
            "files_seen": len(all_entries),
            "oracle_related_candidates": len(oracle_candidates),
            "credential_risk": credential_count,
            "duplicate_candidates": dup_count,
        },
        "entries": all_entries,
        "warnings": sorted(set(warnings)),
        "content_ingested": False,
        "cloud_upload": False,
        "sync": False,
        "drive_modified": False,
        "onedrive_modified": False,
        "git_commit": False,
        "git_push": False,
        "deleted_files": False,
        "moved_files": False,
        "renamed_files": False,
        "conversation_reset": False,
    }

    manifest_path = STORAGE_DIR / f"storage_census_{stamp}.json"
    latest_path = STORAGE_DIR / "storage_census_latest.json"
    manifest["manifest_path"] = str(manifest_path)
    manifest["latest_path"] = str(latest_path)
    _write_json(manifest_path, manifest)
    _write_json(latest_path, manifest)

    candidates_payload = {
        "schema_version": 1,
        "kind": "storage_sourcemap_candidates",
        "created_at": _now(),
        "census_id": manifest["census_id"],
        "status": CANDIDATE_STATUS,
        "auto_merged_into_canonical_sourcemap": False,
        "candidates": [
            {
                "path": e["path"],
                "filename": e["filename"],
                "classification": e["classification"],
                "size_bytes": e["size_bytes"],
                "modified": e["modified"],
                "status": CANDIDATE_STATUS,
            }
            for e in oracle_candidates
        ],
    }
    candidates_path = SOURCES_DIR / f"storage_sourcemap_candidates_{stamp}.json"
    candidates_latest = SOURCES_DIR / "storage_sourcemap_candidates_latest.json"
    _write_json(candidates_path, candidates_payload)
    _write_json(candidates_latest, candidates_payload)

    report_md = _render_report_md(manifest, all_entries)
    report_path = STORAGE_DIR / f"storage_census_report_{stamp}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_md, encoding="utf-8")

    receipt = _write_census_receipt(
        stamp=stamp,
        gov=gov,
        roots=roots,
        not_scanned=not_scanned,
        manifest=manifest,
        onedrive_detected=onedrive_detected,
        drive_detected=drive_detected,
        candidates_path=candidates_path,
        report_path=report_path,
    )

    return {
        "ok": True,
        "governance_loaded": True,
        "governance_source": gov["source"],
        "manifest_path": str(manifest_path),
        "latest_path": str(latest_path),
        "report_path": str(report_path),
        "candidates_path": str(candidates_path),
        "candidates_latest_path": str(candidates_latest),
        "receipt_path": receipt["receipt_path"],
        "counts": manifest["counts"],
        "approved_roots_scanned": manifest["approved_roots_scanned"],
        "known_roots_not_scanned": [r["path"] for r in not_scanned],
        "warnings": manifest["warnings"],
    }


def _safe_exists(p: Path) -> bool:
    try:
        return p.exists()
    except Exception:
        return False


def _write_census_receipt(*, stamp, gov, roots, not_scanned, manifest,
                          onedrive_detected, drive_detected, candidates_path, report_path) -> dict[str, Any]:
    counts = manifest["counts"]
    receipt = {
        "receipt_id": _id("storage_census_receipt"),
        "timestamp": _now(),
        "action": "storage_census",
        "governance_loaded": True,
        "governance_source": gov["source"],
        "approved_roots_scanned": [str(r) for r in roots],
        "known_roots_not_scanned": [r["path"] for r in not_scanned],
        "files_seen_count": counts["files_seen"],
        "oracle_related_candidates_count": counts["oracle_related_candidates"],
        "credential_risk_count": counts["credential_risk"],
        "duplicate_candidate_count": counts["duplicate_candidates"],
        "onedrive_roots_detected": onedrive_detected,
        "drive_roots_detected": drive_detected,
        "candidates_path": str(candidates_path),
        "report_path": str(report_path),
        "manifest_path": manifest["manifest_path"],
        "content_ingested": False,
        "cloud_upload": False,
        "sync": False,
        "drive_modified": False,
        "onedrive_modified": False,
        "git_commit": False,
        "git_push": False,
        "deleted_files": False,
        "moved_files": False,
        "renamed_files": False,
        "conversation_reset": False,
        "human_authority": "Noah.Physical",
    }
    if counts["credential_risk"]:
        receipt["credential_risk_message"] = CREDENTIAL_RISK_MESSAGE
    path = RECEIPTS_DIR / f"storage_census_receipt_{stamp}.json"
    _write_json(path, receipt)
    receipt["receipt_path"] = str(path)
    return receipt


def _render_report_md(manifest: dict[str, Any], entries: list[dict[str, Any]]) -> str:
    counts = manifest["counts"]
    folder_sizes: dict[str, int] = defaultdict(int)
    for e in entries:
        folder_sizes[str(Path(e["path"]).parent)] += int(e.get("size_bytes") or 0)
    largest = sorted(folder_sizes.items(), key=lambda kv: kv[1], reverse=True)[:10]
    dated = [e for e in entries if e.get("modified")]
    newest = sorted(dated, key=lambda e: e["modified"], reverse=True)[:10]
    oldest = sorted(dated, key=lambda e: e["modified"])[:10]

    lines = [
        "# ORACLE Storage Census Report",
        "",
        f"- Created: {manifest['created_at']}",
        f"- Governance loaded: {manifest['governance_loaded']}",
        f"- Governance source: `{manifest['governance_source']}`",
        f"- Approved roots scanned: {', '.join(manifest['approved_roots_scanned']) or 'none'}",
        f"- Known roots NOT scanned: {', '.join(r['path'] for r in manifest['known_roots_not_scanned']) or 'none'}",
        "",
        "## Counts",
        f"- Files seen: {counts['files_seen']}",
        f"- ORACLE-related candidates: {counts['oracle_related_candidates']}",
        f"- Credential-risk files: {counts['credential_risk']} (count only — contents never read)",
        f"- Duplicate candidates: {counts['duplicate_candidates']}",
        "",
        "## Largest folders",
    ]
    for folder, size in largest:
        lines.append(f"- {folder} — {size / (1024*1024):.1f} MB")
    lines += ["", "## Newest files"]
    for e in newest:
        tag = "[credential-risk]" if "credential_risk" in e["risk_flags"] else e["filename"]
        lines.append(f"- {e['modified']} — {tag} ({e['classification']})")
    lines += ["", "## Oldest files"]
    for e in oldest:
        tag = "[credential-risk]" if "credential_risk" in e["risk_flags"] else e["filename"]
        lines.append(f"- {e['modified']} — {tag} ({e['classification']})")
    lines += [
        "",
        "## Recommended next actions",
        "- Approve a known root for deeper scan (`/storage-census approve-root <path>`)",
        "- Reject a root (`/storage-census reject-root <path>`)",
        "- Link ORACLE-related candidates into SourceMap (manual, Noah.Physical approval)",
        "- Copy selected files into local intake",
        "- Quarantine credential-risk references (rotation required)",
        "- Do nothing",
        "",
        "_Discovery only. No content was ingested. No files were moved, deleted, renamed, "
        "uploaded, synced, committed, or pushed. SourceMap candidates are pending Noah.Physical approval._",
    ]
    if counts["credential_risk"]:
        lines.insert(1, "")
        lines.insert(1, f"> {CREDENTIAL_RISK_MESSAGE}")
    return "\n".join(lines) + "\n"


# ── read-only views ───────────────────────────────────────────────────────────

def read_latest_manifest() -> dict[str, Any] | None:
    data = _read_json(STORAGE_DIR / "storage_census_latest.json")
    return data if isinstance(data, dict) else None


def report_payload() -> dict[str, Any]:
    if load_governance() is None:
        return _blocked()
    manifest = read_latest_manifest()
    if not manifest:
        return {"ok": True, "has_census": False, "message": "No census yet. Run scan-approved first."}
    entries = manifest.get("entries") or []
    folder_sizes: dict[str, int] = defaultdict(int)
    for e in entries:
        folder_sizes[str(Path(e["path"]).parent)] += int(e.get("size_bytes") or 0)
    largest = sorted(folder_sizes.items(), key=lambda kv: kv[1], reverse=True)[:5]
    dated = [e for e in entries if e.get("modified")]
    newest = sorted(dated, key=lambda e: e["modified"], reverse=True)[:5]
    oldest = sorted(dated, key=lambda e: e["modified"])[:5]
    return {
        "ok": True,
        "has_census": True,
        "governance_loaded": True,
        "governance_source": manifest.get("governance_source"),
        "approved_roots_scanned": manifest.get("approved_roots_scanned"),
        "known_roots_not_scanned": manifest.get("known_roots_not_scanned"),
        "counts": manifest.get("counts"),
        "credential_risk_count": (manifest.get("counts") or {}).get("credential_risk", 0),
        "largest_folders": [{"folder": f, "bytes": b} for f, b in largest],
        "newest_files": [
            {"modified": e["modified"], "name": ("[credential-risk]" if "credential_risk" in e["risk_flags"] else e["filename"]), "classification": e["classification"]}
            for e in newest
        ],
        "oldest_files": [
            {"modified": e["modified"], "name": ("[credential-risk]" if "credential_risk" in e["risk_flags"] else e["filename"]), "classification": e["classification"]}
            for e in oldest
        ],
        "manifest_path": manifest.get("manifest_path"),
        "recommended_actions": [
            "Approve root for deeper scan", "Reject root",
            "Link candidates into SourceMap", "Copy selected files into local intake",
            "Quarantine credential-risk references", "Do nothing",
        ],
    }


def risks_payload() -> dict[str, Any]:
    """Credential-risk COUNT only. Never returns paths or contents."""

    if load_governance() is None:
        return _blocked()
    manifest = read_latest_manifest()
    if not manifest:
        return {"ok": True, "has_census": False, "credential_risk_count": 0}
    count = (manifest.get("counts") or {}).get("credential_risk", 0)
    out = {
        "ok": True,
        "has_census": True,
        "credential_risk_count": count,
        "duplicate_candidate_count": (manifest.get("counts") or {}).get("duplicate_candidates", 0),
    }
    if count:
        out["message"] = CREDENTIAL_RISK_MESSAGE
    return out


# ── chat command surface ──────────────────────────────────────────────────────

def handle_command(subcommand: str, arg: str = "") -> str:
    sub = (subcommand or "roots").strip().lower()
    if load_governance() is None:
        return BLOCKED_MESSAGE

    if sub in ("roots", ""):
        data = roots_payload()
        lines = [
            "**ORACLE Storage Census — Roots**",
            f"- Governance loaded: ✅  source: `{data['governance_source']}`",
            f"- Default approved root: `{data['default_approved_root']}`",
            f"- Approved roots: {', '.join(data['approved_roots']) or 'none'}",
            "- Known roots NOT scanned (approval required):",
        ]
        for r in data["known_roots_not_scanned"]:
            lines.append(f"  - `{r['path']}` ({r['kind']}, exists={r['exists']}, {r['status']})")
        return "\n".join(lines)

    if sub in ("scan-approved", "scan"):
        res = run_census()
        if not res.get("ok"):
            return res.get("message", "Storage Census blocked.")
        c = res["counts"]
        return (
            "**Storage Census complete (approved roots only).**\n"
            f"- Scanned: {', '.join(res['approved_roots_scanned'])}\n"
            f"- Files seen: {c['files_seen']}\n"
            f"- ORACLE-related candidates: {c['oracle_related_candidates']} (pending Noah.Physical approval)\n"
            f"- Credential-risk: {c['credential_risk']} (count only)\n"
            f"- Duplicate candidates: {c['duplicate_candidates']}\n"
            f"- Manifest: `{res['manifest_path']}`\n"
            f"- Report: `{res['report_path']}`\n"
            f"- Candidates: `{res['candidates_path']}`\n"
            f"- Receipt: `{res['receipt_path']}`\n"
            "No content ingested. No files moved/deleted/renamed/uploaded/synced/committed/pushed."
        )

    if sub == "report":
        data = report_payload()
        if not data.get("has_census"):
            return data.get("message", "No census yet.")
        c = data["counts"]
        return (
            "**Storage Census report**\n"
            f"- Governance source: `{data['governance_source']}`\n"
            f"- Approved roots scanned: {', '.join(data['approved_roots_scanned'])}\n"
            f"- Files seen: {c['files_seen']}, ORACLE-related: {c['oracle_related_candidates']}, "
            f"credential-risk: {c['credential_risk']}, duplicates: {c['duplicate_candidates']}\n"
            f"- Manifest: `{data['manifest_path']}`"
        )

    if sub == "risks":
        data = risks_payload()
        return f"Credential-risk files: {data.get('credential_risk_count', 0)} (count only). " + data.get("message", "")

    if sub == "approve-root":
        res = approve_root(arg)
        return f"Approved `{res['approved']}`." if res.get("ok") else f"Could not approve: {res.get('error')}"

    if sub == "reject-root":
        res = reject_root(arg)
        return f"Rejected `{res['rejected']}`." if res.get("ok") else f"Could not reject: {res.get('error')}"

    return (
        "Unknown storage-census command. Try: roots, scan-approved, report, risks, "
        "approve-root <path>, reject-root <path>."
    )


def status_payload() -> dict[str, Any]:
    gov = load_governance()
    if gov is None:
        return _blocked()
    manifest = read_latest_manifest()
    return {
        "ok": True,
        "governance_loaded": True,
        "governance_source": gov["source"],
        "storage_root": str(STORAGE_DIR),
        "approved_roots": [str(r) for r in approved_roots()],
        "known_roots_not_scanned": known_roots_not_scanned(),
        "has_census": bool(manifest),
        "latest_manifest_path": (manifest or {}).get("manifest_path"),
        "counts": (manifest or {}).get("counts"),
    }


if __name__ == "__main__":
    print(json.dumps(roots_payload(), indent=2, ensure_ascii=True, sort_keys=True))
