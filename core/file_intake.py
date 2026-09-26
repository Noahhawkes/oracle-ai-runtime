"""ORACLE Local File Intake v0.1.

Local-only file and folder intake for ORACLE. Uploaded bytes are copied only
into the ratified private state inbox under C:\\Oracle\\state. This module never
uploads to cloud, never syncs Drive, never commits or pushes, never deletes,
moves, or renames existing user files, and never resets the conversation.

Doctrine: files are not automatically memory. Every intake lands in a bounded
intake state (received) first. Promotion into memory is a separate, explicit,
Noah.Physical-approved step. Dangerous executables and credential-risk files are
quarantined (not stored) by default and their contents are never read for
display, logged, summarized, or exposed.

This module is intentionally HTTP-agnostic so it can be tested without a running
server or any multipart dependency. The web layer decodes uploads and hands this
module already-decoded (filename, bytes, relative_path) items.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from root_map import RATIFIED_STATE_ROOT
except Exception:  # pragma: no cover - direct execution fallback
    RATIFIED_STATE_ROOT = Path(r"C:\Oracle\state")


STATE_ROOT = Path(RATIFIED_STATE_ROOT)
INBOX_DIR = STATE_ROOT / "inbox"
UPLOADS_DIR = INBOX_DIR / "uploads"
FOLDER_UPLOADS_DIR = INBOX_DIR / "folder_uploads"
MANIFESTS_DIR = INBOX_DIR / "manifests"
RECEIPTS_DIR = STATE_ROOT / "receipts"
SOURCES_DIR = STATE_ROOT / "sources"

# Default safety limits.
MAX_INDIVIDUAL_BYTES = 50 * 1024 * 1024      # 50 MB
MAX_BATCH_BYTES = 500 * 1024 * 1024          # 500 MB
MAX_FILE_COUNT = 500

# Executable / scriptable extensions are quarantined by default and never stored.
DANGEROUS_EXTENSIONS = {
    ".exe", ".dll", ".bat", ".cmd", ".ps1", ".vbs", ".js",
    ".msi", ".scr", ".reg", ".pif", ".com",
}

# Archives are never auto-expanded; stored as-is and flagged for manual review.
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz"}

# Lowercased substrings that suggest a file may carry secrets.
SENSITIVE_FILENAME_SUBSTRINGS = (
    "key", "token", "secret", "password", "credential", ".env", "alive",
)
# The literal key glyph used by Noah's known credential-risk file name.
SENSITIVE_GLYPHS = ("\U0001f5dd",)  # 🗝

CREDENTIAL_RISK_MESSAGE = "credential-risk file detected, rotation/quarantine required"

# Intake statuses.
STATUS_RECEIVED = "received"
STATUS_QUARANTINED = "quarantined"
STATUS_REJECTED = "rejected"
STATUS_PROMOTED = "promoted"


@dataclass
class FileInput:
    """A single decoded upload handed to intake by the web layer."""

    filename: str
    data: bytes
    relative_path: str | None = None


@dataclass
class _Prepared:
    entry: dict[str, Any]
    data: bytes | None  # bytes to store, or None when storage is blocked
    target_path: Path | None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _extension(filename: str) -> str:
    suffix = PurePosixPath(filename.replace("\\", "/")).suffix
    return suffix.lower()


def _safe_basename(filename: str) -> str:
    name = PurePosixPath((filename or "").replace("\\", "/")).name
    name = name.strip().strip(".") or "unnamed"
    # Strip characters that are illegal in Windows file names.
    for bad in '<>:"/\\|?*':
        name = name.replace(bad, "_")
    return name or "unnamed"


def sanitize_relative_path(relative_path: str | None) -> tuple[str | None, bool]:
    """Return (clean_posix_relpath, traversal_detected).

    Rejects absolute paths, drive letters, and any '..' traversal. On traversal
    the cleaned path falls back to the bare basename and the flag is True.
    """

    if not relative_path:
        return None, False
    raw = relative_path.replace("\\", "/").strip()
    if not raw:
        return None, False
    pure = PurePosixPath(raw)
    traversal = False
    if pure.is_absolute() or (len(raw) >= 2 and raw[1] == ":"):
        traversal = True
    parts: list[str] = []
    for part in pure.parts:
        if part in ("", "/", "."):
            continue
        if part == "..":
            traversal = True
            continue
        if ":" in part:
            traversal = True
            continue
        parts.append(part)
    if not parts:
        return None, traversal
    if traversal:
        # Collapse to a safe basename; never honor the traversal layout.
        return parts[-1], True
    return "/".join(parts), False


def detect_risk(filename: str) -> dict[str, Any]:
    """Classify a filename without reading its contents.

    Returns risk_flags, recommended_action, whether storage is blocked, and
    whether a credential risk was detected. Never inspects or returns content.
    """

    ext = _extension(filename)
    lower = (filename or "").lower()
    risk_flags: list[str] = []
    blocked = False
    credential_risk = False

    if ext in DANGEROUS_EXTENSIONS:
        risk_flags.append("dangerous_extension")
        blocked = True

    if any(sub in lower for sub in SENSITIVE_FILENAME_SUBSTRINGS) or any(
        glyph in (filename or "") for glyph in SENSITIVE_GLYPHS
    ):
        risk_flags.append("credential_risk")
        credential_risk = True
        blocked = True

    if ext in ARCHIVE_EXTENSIONS:
        risk_flags.append("archive_not_expanded")

    if ext in {".html", ".htm", ".svg"}:
        risk_flags.append("untrusted_markup")

    if ext in {".lnk", ".url"}:
        risk_flags.append("shortcut_not_followed")
        blocked = True

    if credential_risk:
        recommended_action = "quarantine_rotate_credential"
    elif "dangerous_extension" in risk_flags or "shortcut_not_followed" in risk_flags:
        recommended_action = "reject_or_quarantine"
    elif "archive_not_expanded" in risk_flags:
        recommended_action = "manual_review_no_autoexpand"
    else:
        recommended_action = "review_before_promotion"

    return {
        "risk_flags": risk_flags,
        "recommended_action": recommended_action,
        "blocked_store": blocked,
        "credential_risk": credential_risk,
    }


def _prepare_entry(item: FileInput, *, batch_id: str, is_folder: bool) -> _Prepared:
    original = item.filename or "unnamed"
    size = len(item.data or b"")
    ext = _extension(original)
    mime = mimetypes.guess_type(original)[0]
    sha256 = hashlib.sha256(item.data or b"").hexdigest()
    clean_rel, traversal = sanitize_relative_path(item.relative_path)

    risk = detect_risk(original)
    risk_flags = list(risk["risk_flags"])
    recommended_action = risk["recommended_action"]
    blocked = bool(risk["blocked_store"])
    status = STATUS_QUARANTINED if blocked else STATUS_RECEIVED

    if traversal:
        risk_flags.append("path_traversal")
        blocked = True
        status = STATUS_QUARANTINED
        recommended_action = "reject_path_traversal"

    if size > MAX_INDIVIDUAL_BYTES:
        risk_flags.append("oversize_file")
        blocked = True
        status = STATUS_REJECTED
        recommended_action = "reject_oversize"

    safe_name = _safe_basename(original)
    target_path: Path | None = None
    data_to_store: bytes | None = None
    if not blocked:
        if is_folder and clean_rel:
            target_path = FOLDER_UPLOADS_DIR / batch_id / clean_rel
        else:
            target_path = UPLOADS_DIR / batch_id / safe_name
        data_to_store = item.data or b""

    entry = {
        "intake_id": _id("intake"),
        "original_filename": original,
        "relative_path": clean_rel,
        "stored_path": str(target_path) if target_path is not None else None,
        "size_bytes": size,
        "extension": ext,
        "mime_guess": mime,
        "sha256": sha256,
        "received_at": _now(),
        "source_surface": "local_ui_upload",
        "source_authority": "Noah.Physical",
        "status": status,
        "risk_flags": risk_flags,
        "recommended_action": recommended_action,
    }
    return _Prepared(entry=entry, data=data_to_store, target_path=target_path)


def _batch_reject_reason(items: list[FileInput]) -> str:
    count = len(items)
    total = sum(len(it.data or b"") for it in items)
    if count > MAX_FILE_COUNT:
        return f"batch file count {count} exceeds max {MAX_FILE_COUNT}"
    if total > MAX_BATCH_BYTES:
        return f"batch size {total} bytes exceeds max {MAX_BATCH_BYTES} bytes"
    return ""


def _folder_count(items: list[FileInput]) -> int:
    tops: set[str] = set()
    for it in items:
        clean_rel, _ = sanitize_relative_path(it.relative_path)
        if clean_rel and "/" in clean_rel:
            tops.add(clean_rel.split("/", 1)[0])
        elif clean_rel:
            tops.add(clean_rel)
    return len(tops)


def run_intake(
    items: list[FileInput],
    *,
    is_folder: bool = False,
) -> dict[str, Any]:
    """Receive a batch of decoded uploads into local intake state.

    Writes a timestamped manifest, a latest manifest, and an intake receipt.
    Never uploads, syncs, commits, pushes, deletes, moves, or renames.
    """

    batch_id = _id("batch")
    created_at = _now()
    stamp = _stamp()

    reject_reason = _batch_reject_reason(items)
    batch_rejected = bool(reject_reason)

    entries: list[dict[str, Any]] = []
    warnings: list[str] = []
    credential_risk_detected = False
    total_bytes = 0
    quarantined_count = 0
    rejected_count = 0
    stored_count = 0

    if batch_rejected:
        warnings.append(reject_reason)
        for item in items:
            size = len(item.data or b"")
            total_bytes += size
            clean_rel, _ = sanitize_relative_path(item.relative_path)
            risk = detect_risk(item.filename or "unnamed")
            flags = list(risk["risk_flags"]) + ["batch_rejected"]
            if risk["credential_risk"]:
                credential_risk_detected = True
            entries.append({
                "intake_id": _id("intake"),
                "original_filename": item.filename or "unnamed",
                "relative_path": clean_rel,
                "stored_path": None,
                "size_bytes": size,
                "extension": _extension(item.filename or ""),
                "mime_guess": mimetypes.guess_type(item.filename or "")[0],
                "sha256": hashlib.sha256(item.data or b"").hexdigest(),
                "received_at": _now(),
                "source_surface": "local_ui_upload",
                "source_authority": "Noah.Physical",
                "status": STATUS_REJECTED,
                "risk_flags": flags,
                "recommended_action": "reject_batch_limit",
            })
            rejected_count += 1
    else:
        for item in items:
            prepared = _prepare_entry(item, batch_id=batch_id, is_folder=is_folder)
            entry = prepared.entry
            total_bytes += int(entry["size_bytes"])
            if "credential_risk" in entry["risk_flags"]:
                credential_risk_detected = True
            if prepared.data is not None and prepared.target_path is not None:
                try:
                    prepared.target_path.parent.mkdir(parents=True, exist_ok=True)
                    tmp = prepared.target_path.with_name(prepared.target_path.name + ".part")
                    tmp.write_bytes(prepared.data)
                    tmp.replace(prepared.target_path)
                    stored_count += 1
                except Exception as exc:
                    entry["status"] = STATUS_REJECTED
                    entry["stored_path"] = None
                    entry["risk_flags"] = list(entry["risk_flags"]) + ["store_failed"]
                    entry["recommended_action"] = "retry_or_reject"
                    warnings.append(
                        f"store failed for {entry['original_filename']}: {type(exc).__name__}"
                    )
            if entry["status"] == STATUS_QUARANTINED:
                quarantined_count += 1
            elif entry["status"] == STATUS_REJECTED:
                rejected_count += 1
            entries.append(entry)

    if credential_risk_detected:
        warnings.append(CREDENTIAL_RISK_MESSAGE)

    folders_received_count = _folder_count(items) if is_folder else 0
    target_root = str(FOLDER_UPLOADS_DIR if is_folder else UPLOADS_DIR)

    manifest = {
        "schema_version": 1,
        "manifest_kind": "oracle_local_intake",
        "intake_batch_id": batch_id,
        "created_at": created_at,
        "source_surface": "local_ui_upload",
        "source_authority": "Noah.Physical",
        "is_folder_upload": bool(is_folder),
        "target_intake_roots": {
            "uploads": str(UPLOADS_DIR),
            "folder_uploads": str(FOLDER_UPLOADS_DIR),
        },
        "limits": {
            "max_individual_bytes": MAX_INDIVIDUAL_BYTES,
            "max_batch_bytes": MAX_BATCH_BYTES,
            "max_file_count": MAX_FILE_COUNT,
        },
        "counts": {
            "total_files": len(entries),
            "received": stored_count,
            "quarantined": quarantined_count,
            "rejected": rejected_count,
            "folders": folders_received_count,
        },
        "total_bytes": total_bytes,
        "batch_rejected": batch_rejected,
        "batch_reject_reason": reject_reason,
        "credential_risk_detected": credential_risk_detected,
        "entries": entries,
        "warnings": sorted(set(warnings)),
        "conversation_reset": False,
        "cloud_upload": False,
        "drive_modified": False,
        "git_commit": False,
        "git_push": False,
        "deleted_files": False,
        "moved_existing_files": False,
        "renamed_existing_files": False,
    }

    manifest_path = MANIFESTS_DIR / f"intake_manifest_{stamp}.json"
    latest_path = MANIFESTS_DIR / "intake_manifest_latest.json"
    manifest["manifest_path"] = str(manifest_path)
    manifest["latest_path"] = str(latest_path)
    _write_json(manifest_path, manifest)
    _write_json(latest_path, manifest)

    receipt = _write_intake_receipt(
        stamp=stamp,
        manifest_path=manifest_path,
        target_root=target_root,
        files_received_count=stored_count,
        folders_received_count=folders_received_count,
        total_bytes=total_bytes,
        quarantined_count=quarantined_count,
        rejected_count=rejected_count,
        credential_risk_detected=credential_risk_detected,
        batch_rejected=batch_rejected,
        warnings=manifest["warnings"],
    )

    return {
        "ok": not batch_rejected,
        "manifest": manifest,
        "manifest_path": str(manifest_path),
        "latest_path": str(latest_path),
        "receipt": receipt,
        "receipt_path": receipt["receipt_path"],
        "oracle_response": oracle_response_line(manifest),
    }


def _write_intake_receipt(
    *,
    stamp: str,
    manifest_path: Path,
    target_root: str,
    files_received_count: int,
    folders_received_count: int,
    total_bytes: int,
    quarantined_count: int,
    rejected_count: int,
    credential_risk_detected: bool,
    batch_rejected: bool,
    warnings: list[str],
) -> dict[str, Any]:
    receipt = {
        "receipt_id": _id("file_intake_receipt"),
        "timestamp": _now(),
        "action": "local_file_intake",
        "files_received_count": files_received_count,
        "folders_received_count": folders_received_count,
        "total_bytes": total_bytes,
        "target_intake_root": target_root,
        "manifest_path": str(manifest_path),
        "quarantined_count": quarantined_count,
        "rejected_count": rejected_count,
        "batch_rejected": batch_rejected,
        "credential_risk_detected": credential_risk_detected,
        "conversation_reset": False,
        "cloud_upload": False,
        "drive_modified": False,
        "git_commit": False,
        "git_push": False,
        "deleted_files": False,
        "moved_existing_files": False,
        "renamed_existing_files": False,
        "human_authority": "Noah.Physical",
        "warnings": list(warnings),
    }
    if credential_risk_detected:
        receipt["credential_risk_message"] = CREDENTIAL_RISK_MESSAGE
    path = RECEIPTS_DIR / f"file_intake_receipt_{stamp}.json"
    _write_json(path, receipt)
    receipt["receipt_path"] = str(path)
    return receipt


def read_latest_manifest() -> dict[str, Any] | None:
    return _read_json(MANIFESTS_DIR / "intake_manifest_latest.json")


def review_intake() -> dict[str, Any]:
    """Return the latest intake manifest with a review summary. Read-only."""

    manifest = read_latest_manifest()
    if not manifest:
        return {
            "ok": True,
            "has_intake": False,
            "message": "No intake manifest exists yet. Add files or a folder first.",
            "entries": [],
        }
    entries = manifest.get("entries") or []
    by_status: dict[str, int] = {}
    flagged: list[dict[str, Any]] = []
    for entry in entries:
        status = str(entry.get("status") or "unknown")
        by_status[status] = by_status.get(status, 0) + 1
        if entry.get("risk_flags"):
            flagged.append({
                "intake_id": entry.get("intake_id"),
                "original_filename": entry.get("original_filename"),
                "status": status,
                "risk_flags": entry.get("risk_flags"),
                "recommended_action": entry.get("recommended_action"),
            })
    return {
        "ok": True,
        "has_intake": True,
        "manifest_path": manifest.get("manifest_path"),
        "latest_path": manifest.get("latest_path"),
        "counts": manifest.get("counts"),
        "by_status": by_status,
        "flagged": flagged,
        "credential_risk_detected": bool(manifest.get("credential_risk_detected")),
        "promotion_requires_approval": True,
        "entries": entries,
    }


def _update_latest_entry(intake_id: str, new_status: str) -> dict[str, Any] | None:
    latest_path = MANIFESTS_DIR / "intake_manifest_latest.json"
    manifest = _read_json(latest_path)
    if not manifest:
        return None
    target: dict[str, Any] | None = None
    for entry in manifest.get("entries") or []:
        if entry.get("intake_id") == intake_id:
            entry["status"] = new_status
            history = entry.setdefault("status_history", [])
            history.append({"status": new_status, "at": _now()})
            target = entry
            break
    if target is None:
        return None
    _write_json(latest_path, manifest)
    if manifest.get("manifest_path"):
        try:
            _write_json(Path(manifest["manifest_path"]), manifest)
        except Exception:
            pass
    return target


def _write_action_receipt(action: str, entry: dict[str, Any]) -> dict[str, Any]:
    stamp = _stamp()
    receipt = {
        "receipt_id": _id(f"{action}_receipt"),
        "timestamp": _now(),
        "action": action,
        "intake_id": entry.get("intake_id"),
        "original_filename": entry.get("original_filename"),
        "new_status": entry.get("status"),
        "stored_path": entry.get("stored_path"),
        "risk_flags": entry.get("risk_flags"),
        "human_authority": "Noah.Physical",
        "content_loaded_into_memory": False,
        "conversation_reset": False,
        "cloud_upload": False,
        "drive_modified": False,
        "git_commit": False,
        "git_push": False,
        "deleted_files": False,
        "moved_existing_files": False,
        "renamed_existing_files": False,
    }
    path = RECEIPTS_DIR / f"{action}_{stamp}.json"
    _write_json(path, receipt)
    receipt["receipt_path"] = str(path)
    return receipt


def promote_intake(intake_id: str, *, override_quarantine: bool = False) -> dict[str, Any]:
    """Mark an intake entry as promoted (Noah.Physical approval).

    Promotion only changes intake status and writes a receipt. It does NOT load
    file contents into active memory; that remains a separate explicit step.
    Quarantined/rejected entries are refused unless explicitly overridden.
    """

    manifest = read_latest_manifest()
    if not manifest:
        return {"ok": False, "error": "No intake manifest exists yet."}
    current = None
    for entry in manifest.get("entries") or []:
        if entry.get("intake_id") == intake_id:
            current = entry
            break
    if current is None:
        return {"ok": False, "error": f"intake_id not found: {intake_id}"}
    if current.get("status") in (STATUS_QUARANTINED, STATUS_REJECTED) and not override_quarantine:
        return {
            "ok": False,
            "error": "refusing to promote a quarantined/rejected file without explicit override",
            "status": current.get("status"),
            "risk_flags": current.get("risk_flags"),
        }
    updated = _update_latest_entry(intake_id, STATUS_PROMOTED)
    if updated is None:
        return {"ok": False, "error": f"intake_id not found: {intake_id}"}
    receipt = _write_action_receipt("local_file_promote", updated)
    return {
        "ok": True,
        "intake_id": intake_id,
        "status": STATUS_PROMOTED,
        "content_loaded_into_memory": False,
        "receipt": receipt,
        "receipt_path": receipt["receipt_path"],
    }


def quarantine_intake(intake_id: str) -> dict[str, Any]:
    """Mark an intake entry as quarantined and write a receipt."""

    updated = _update_latest_entry(intake_id, STATUS_QUARANTINED)
    if updated is None:
        return {"ok": False, "error": f"intake_id not found: {intake_id}"}
    receipt = _write_action_receipt("local_file_quarantine", updated)
    return {
        "ok": True,
        "intake_id": intake_id,
        "status": STATUS_QUARANTINED,
        "receipt": receipt,
        "receipt_path": receipt["receipt_path"],
    }


def oracle_response_line(manifest: dict[str, Any]) -> str:
    counts = manifest.get("counts") or {}
    received = int(counts.get("received") or 0)
    if manifest.get("batch_rejected"):
        return (
            "Local intake rejected: "
            f"{manifest.get('batch_reject_reason') or 'batch limit exceeded'}. "
            "I wrote a manifest and receipt and stored nothing. I did not upload, "
            "sync, commit, push, delete, move, rename, or promote contents into memory."
        )
    line = (
        f"Local intake complete. I received {received} files into {INBOX_DIR}. "
        "I created an intake manifest and receipt. I did not upload, sync, commit, "
        "push, delete, move, rename, or promote contents into memory."
    )
    if manifest.get("credential_risk_detected"):
        line += f" Note: {CREDENTIAL_RISK_MESSAGE}."
    line += " Review intake before promotion?"
    return line


def status_payload() -> dict[str, Any]:
    manifest = read_latest_manifest()
    counts = (manifest or {}).get("counts") or {}
    return {
        "ok": True,
        "inbox_root": str(INBOX_DIR),
        "uploads_root": str(UPLOADS_DIR),
        "folder_uploads_root": str(FOLDER_UPLOADS_DIR),
        "manifests_root": str(MANIFESTS_DIR),
        "receipts_root": str(RECEIPTS_DIR),
        "has_intake": bool(manifest),
        "latest_manifest_path": (manifest or {}).get("manifest_path"),
        "counts": counts,
        "credential_risk_detected": bool((manifest or {}).get("credential_risk_detected")),
        "limits": {
            "max_individual_bytes": MAX_INDIVIDUAL_BYTES,
            "max_batch_bytes": MAX_BATCH_BYTES,
            "max_file_count": MAX_FILE_COUNT,
        },
        "doctrine": "Files are not automatically memory. Promotion requires Noah.Physical approval.",
    }


if __name__ == "__main__":
    print(json.dumps(status_payload(), indent=2, ensure_ascii=True, sort_keys=True))
