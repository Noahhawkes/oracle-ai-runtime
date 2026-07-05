"""Governed local sandbox workbench operations for ORACLE.

Doctrine: full workbench freedom inside the runtime-owned sandbox, hard wall
outside it. Generated files are never executed, external systems are never
touched, and every mutation emits a receipt.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from root import ROOT as RUNTIME_ROOT
except Exception:  # pragma: no cover - import fallback for unusual launchers
    RUNTIME_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SANDBOX_ROOT = (
    Path(os.environ["ORACLE_SANDBOX_ROOT"])
    if os.environ.get("ORACLE_SANDBOX_ROOT")
    else RUNTIME_ROOT / "sandbox"
)
DEFAULT_SANDBOX_TRASH_ROOT = (
    Path(os.environ["ORACLE_SANDBOX_TRASH_ROOT"])
    if os.environ.get("ORACLE_SANDBOX_TRASH_ROOT")
    else RUNTIME_ROOT / "sandbox.trash"
)
SANDBOX_ROOT = DEFAULT_SANDBOX_ROOT
SANDBOX_TRASH_ROOT = DEFAULT_SANDBOX_TRASH_ROOT
CORE_FOLDERS = frozenset({
    "drafts",
    "handoffs",
    "journal",
    "notes",
    "reflections",
    "receipts",
    "state",
    "tests",
    "workbench",
})
ALLOWED_FOLDERS = CORE_FOLDERS
WRITABLE_FOLDERS = CORE_FOLDERS
RECEIPTS_FOLDER = "receipts"
STATE_FOLDER = "state"
JOURNAL_FOLDER = "journal"
REFLECTIONS_FOLDER = "reflections"
WORKBENCH_FOLDER = "workbench"
JOURNAL_PATH = Path(JOURNAL_FOLDER) / "oracle_journal.jsonl"
LEGACY_JOURNAL_PATH = Path("notes") / "oracle_sandbox_journal.ai"
REFLECTION_RECEIPT_FIELDS = (
    "what_changed",
    "what_is_stuck",
    "what_noah_is_trying",
    "safe_next_action",
    "requires_approval",
    "leave_untouched",
    "highest_value_next",
)
FORBIDDEN_EXTENSIONS = frozenset({
    ".bat",
    ".cmd",
    ".com",
    ".exe",
    ".msi",
    ".ps1",
    ".py",
    ".scr",
    ".sh",
    ".vbs",
})
ALLOWED_EXTENSIONS = frozenset({".txt", ".md", ".json", ".jsonl", ".ai"})
BLOCKED_PATH_TERMS = frozenset({
    ".aws",
    ".azure",
    ".env",
    ".ssh",
    "browser profile",
    "browser profiles",
    "cookie",
    "cookies",
    "credential",
    "credentials",
    "login data",
    "password",
    "password store",
    "password-store",
    "passwords",
    "secret",
    "secrets",
    "token",
    "tokens",
})
TEXT_ENCODING = "utf-8"


class SandboxWriteError(ValueError):
    """Raised when a sandbox operation would violate the governed boundary."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_operation_name(operation: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in str(operation or "sandbox_op").lower())
    safe = "_".join(part for part in safe.split("_") if part)
    return safe or "sandbox_op"


def _safe_action_id(
    caller: str,
    requested_filename: str,
    content_hash: str,
    operation: str = "sandbox_operation",
) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    op = _safe_operation_name(operation)
    seed = f"{op}|{caller}|{requested_filename}|{content_hash}|{stamp}".encode(TEXT_ENCODING)
    return f"{op}_{stamp}_{_sha256_bytes(seed)[:10]}"


def _resolved_root() -> Path:
    return SANDBOX_ROOT.resolve(strict=False)


def _resolved_trash_root() -> Path:
    return SANDBOX_TRASH_ROOT.resolve(strict=False)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _ensure_sandbox_dirs() -> None:
    root = _resolved_root()
    root.mkdir(parents=True, exist_ok=True)
    for folder in CORE_FOLDERS:
        (root / folder).mkdir(parents=True, exist_ok=True)


def _ensure_trash_dir() -> None:
    _resolved_trash_root().mkdir(parents=True, exist_ok=True)


def _path_has_blocked_terms(parts: tuple[str, ...] | list[str]) -> str | None:
    joined = " ".join(str(part or "").lower() for part in parts)
    normalized_parts = {str(part or "").lower() for part in parts}
    for term in BLOCKED_PATH_TERMS:
        if term in normalized_parts or term in joined:
            return term
    return None


def _validate_no_secret_terms(parts: tuple[str, ...] | list[str]) -> None:
    blocked = _path_has_blocked_terms(parts)
    if blocked:
        raise SandboxWriteError(f"path term is blocked: {blocked}")


def _validate_raw_path_text(raw_text: str) -> None:
    if not raw_text:
        raise SandboxWriteError("path is required")
    raw_parts = Path(raw_text).parts
    if any(part == ".." for part in raw_parts):
        raise SandboxWriteError("path traversal is blocked")
    if any(":" in part for part in raw_parts[1:] if part):
        raise SandboxWriteError("path alternate streams or drive-relative syntax are blocked")


def _validate_text_artifact_path(path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix in FORBIDDEN_EXTENSIONS:
        raise SandboxWriteError(f"file type is forbidden: {suffix}")
    _validate_no_secret_terms(path.parts)


def _resolve_sandbox_path(
    path: str | Path,
    *,
    file_required: bool = False,
    dir_required: bool = False,
    require_text_artifact: bool = False,
    allow_missing: bool = True,
    allow_root: bool = False,
) -> Path:
    _ensure_sandbox_dirs()
    root = _resolved_root()
    raw_text = str(path or "").strip().strip('"')
    _validate_raw_path_text(raw_text)
    raw = Path(raw_text)
    candidate = raw if raw.is_absolute() else root / raw
    resolved = candidate.resolve(strict=False)
    if not _is_relative_to(resolved, root):
        raise SandboxWriteError("path escaped sandbox root")
    if resolved == root and not allow_root:
        raise SandboxWriteError("operation requires a path below the sandbox root")
    relative_parts = resolved.relative_to(root).parts
    if any(part in {"", ".", ".."} for part in relative_parts):
        raise SandboxWriteError("path contains invalid traversal component")
    if any(":" in part for part in relative_parts):
        raise SandboxWriteError("path alternate streams are blocked")
    _validate_no_secret_terms(relative_parts)
    if require_text_artifact:
        _validate_text_artifact_path(resolved)
    if not allow_missing and not resolved.exists():
        raise SandboxWriteError("path does not exist")
    if file_required and (not resolved.exists() or not resolved.is_file()):
        raise SandboxWriteError("file not found")
    if dir_required and (not resolved.exists() or not resolved.is_dir()):
        raise SandboxWriteError("folder not found")
    return resolved


def _resolve_trash_path(path: Path) -> Path:
    trash_root = _resolved_trash_root()
    resolved = path.resolve(strict=False)
    if not _is_relative_to(resolved, trash_root):
        raise SandboxWriteError("trash path escaped designated sandbox trash root")
    return resolved


def _versioned_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for version in range(2, 10_000):
        versioned = (path.parent / f"{stem}_v{version}{suffix}").resolve(strict=False)
        if not versioned.exists():
            return versioned
    raise SandboxWriteError("could not create a non-overwriting versioned path")


def _folder_path(folder: str, *, for_write: bool = False) -> Path:
    del for_write
    value = str(folder or "").strip().strip("\\/")
    if not value:
        raise SandboxWriteError("folder is required")
    return _resolve_sandbox_path(
        value,
        dir_required=False,
        require_text_artifact=False,
        allow_missing=True,
    )


def _validate_filename(filename: str) -> str:
    value = str(filename or "").strip()
    if not value:
        raise SandboxWriteError("filename is required")
    p = Path(value)
    if p.name != value or any(sep in value for sep in ("/", "\\")):
        raise SandboxWriteError("filename must not include a path")
    if value in {".", ".."}:
        raise SandboxWriteError("filename is invalid")
    _validate_text_artifact_path(p)
    return value


def _unique_path(folder: str, filename: str) -> Path:
    folder_dir = _folder_path(folder, for_write=True)
    safe_name = _validate_filename(filename)
    candidate = (folder_dir / safe_name).resolve(strict=False)
    root = _resolved_root()
    if not _is_relative_to(candidate, root):
        raise SandboxWriteError("resolved file escaped sandbox root")
    return _versioned_path(candidate)


def _receipt_path(action_id: str) -> Path:
    _ensure_sandbox_dirs()
    receipts_dir = (_resolved_root() / RECEIPTS_FOLDER).resolve(strict=False)
    receipts_dir.mkdir(parents=True, exist_ok=True)
    safe_action = _safe_operation_name(action_id)
    return _versioned_path((receipts_dir / f"{safe_action}_receipt.json").resolve(strict=False))


def _hash_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    return _sha256_bytes(path.read_bytes())


def _hash_path(path: Path) -> str | None:
    if not path.exists():
        return None
    if path.is_file():
        return _hash_file(path)
    if path.is_dir():
        root = path.resolve(strict=False)
        rows: list[dict[str, Any]] = []
        for item in sorted(root.rglob("*"), key=lambda p: str(p).lower()):
            if item.is_file():
                rows.append({
                    "relative_path": str(item.resolve(strict=False).relative_to(root)),
                    "size_bytes": item.stat().st_size,
                    "sha256": _sha256_bytes(item.read_bytes()),
                })
            elif item.is_dir():
                rows.append({"relative_path": str(item.resolve(strict=False).relative_to(root)), "folder": True})
        return _sha256_bytes(json.dumps(rows, sort_keys=True).encode(TEXT_ENCODING))
    return None


def _boundary_check(
    target: Path,
    *,
    source_path: Path | None = None,
    allow_trash_target: bool = False,
) -> dict[str, Any]:
    root = _resolved_root()
    trash_root = _resolved_trash_root()
    target_resolved = target.resolve(strict=False)
    source_resolved = source_path.resolve(strict=False) if source_path is not None else None
    target_inside_sandbox = _is_relative_to(target_resolved, root)
    source_inside_sandbox = source_resolved is None or _is_relative_to(source_resolved, root)
    target_inside_trash = _is_relative_to(target_resolved, trash_root)
    return {
        "boundary_ok": source_inside_sandbox and (target_inside_sandbox or (allow_trash_target and target_inside_trash)),
        "inside_sandbox": target_inside_sandbox and source_inside_sandbox,
        "source_inside_sandbox": source_inside_sandbox,
        "target_inside_sandbox": target_inside_sandbox,
        "target_inside_designated_trash": target_inside_trash,
        "sandbox_root": str(root),
        "sandbox_trash_root": str(trash_root),
        "executable_extension_blocked": True,
        "secret_path_blocked": True,
        "no_execution": True,
        "no_external_upload": True,
        "no_git_push": True,
        "no_gdrive_edit": True,
        "no_sov1_actuation": True,
        "no_computer_control": True,
        "no_canon_promotion": True,
    }


def _write_last_receipt_snapshot(receipt: dict[str, Any], receipt_path: Path) -> None:
    state_dir = (_resolved_root() / STATE_FOLDER).resolve(strict=False)
    state_dir.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "updated_at": _now(),
        "receipt_path": str(receipt_path),
        "operation_type": receipt.get("operation_type"),
        "target_path": receipt.get("target_path"),
        "source_path": receipt.get("source_path"),
        "actor": receipt.get("actor"),
        "action_id": receipt.get("action_id"),
        "receipt_hash_sha256": receipt.get("receipt_hash_sha256"),
        "boundary_check_result": receipt.get("boundary_check_result"),
    }
    (state_dir / "last_receipt.json").write_text(
        json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False),
        encoding=TEXT_ENCODING,
    )


def _write_operation_receipt(
    *,
    operation_type: str,
    target_path: Path,
    caller: str,
    action_id: str,
    pre_hash: str | None,
    post_hash: str | None,
    created: bool = False,
    appended: bool = False,
    edited: bool = False,
    renamed: bool = False,
    deleted: bool = False,
    soft_deleted: bool = False,
    made_folder: bool = False,
    journal_tick: bool = False,
    status_emit: bool = False,
    source_path: Path | None = None,
    requested_path: str | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    receipt = {
        "receipt_kind": "sandbox_operation_receipt",
        "schema_version": "sandbox_files.v2.backend_ultrasound",
        "timestamp": _now(),
        "operation_type": operation_type,
        "operation": operation_type,
        "target_path": str(target_path),
        "requested_path": str(requested_path or target_path),
        "source_path": str(source_path) if source_path is not None else None,
        "actor": str(caller or "unknown"),
        "caller": str(caller or "unknown"),
        "source_route": str(caller or "unknown"),
        "approval_route_or_command_source": str(caller or "unknown"),
        "action_id": action_id,
        "pre_operation_sha256": pre_hash,
        "post_operation_sha256": post_hash,
        "created": bool(created),
        "appended": bool(appended),
        "edited": bool(edited),
        "renamed": bool(renamed),
        "deleted": bool(deleted),
        "soft_deleted": bool(soft_deleted),
        "made_folder": bool(made_folder),
        "journal_tick": bool(journal_tick),
        "status_emit": bool(status_emit),
        "boundary_check_result": _boundary_check(
            target_path,
            source_path=source_path,
            allow_trash_target=soft_deleted,
        ),
        "executed_written_file": False,
        "cloud_upload": False,
        "git_push": False,
        "external_send": False,
        "gdrive_edit": False,
        "sov1_actuation": False,
        "computer_control": False,
        "canon_promotion": False,
    }
    if extra:
        receipt.update(extra)
    receipt["receipt_hash_sha256"] = _sha256_bytes(
        json.dumps(receipt, sort_keys=True, ensure_ascii=False).encode(TEXT_ENCODING)
    )
    receipt_path = _receipt_path(action_id)
    with receipt_path.open("xb") as handle:
        handle.write(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False).encode(TEXT_ENCODING))
    _write_last_receipt_snapshot(receipt, receipt_path)
    return receipt_path


def write_file(
    path: str | Path,
    content: str,
    *,
    caller: str = "ORACLE",
    action_id: str | None = None,
) -> dict[str, Any]:
    """Create a text artifact anywhere inside the sandbox, versioning if needed."""
    requested_path = str(path)
    target = _resolve_sandbox_path(path, allow_missing=True, require_text_artifact=True)
    if target.exists() and target.is_dir():
        raise SandboxWriteError("target exists and is a folder")
    final_path = _versioned_path(target)
    data = str(content).encode(TEXT_ENCODING)
    content_hash = _sha256_bytes(data)
    safe_action_id = str(action_id or "").strip() or _safe_action_id(
        caller,
        final_path.name,
        content_hash,
        "sandbox_write_file",
    )
    final_path.parent.mkdir(parents=True, exist_ok=True)
    with final_path.open("xb") as handle:
        handle.write(data)
    receipt_path = _write_operation_receipt(
        operation_type="write_file",
        target_path=final_path,
        caller=caller,
        action_id=safe_action_id,
        pre_hash=None,
        post_hash=content_hash,
        created=True,
        requested_path=requested_path,
        extra={
            "requested_filename": Path(requested_path).name,
            "final_path": str(final_path),
            "sha256": content_hash,
            "overwrote_existing_file": False,
        },
    )
    return {
        "ok": True,
        "operation_type": "write_file",
        "action_id": safe_action_id,
        "requested_path": requested_path,
        "final_path": str(final_path),
        "sha256": content_hash,
        "receipt_path": str(receipt_path),
    }


def write_sandbox_file(
    folder: str,
    filename: str,
    content: str,
    *,
    caller: str = "ORACLE",
    action_id: str | None = None,
) -> dict[str, Any]:
    """Compatibility wrapper for folder + filename callers."""
    safe_filename = _validate_filename(filename)
    result = write_file(Path(str(folder or "").strip()) / safe_filename, content, caller=caller, action_id=action_id)
    result["requested_filename"] = safe_filename
    return result


def append_file(
    path: str | Path,
    content: str,
    *,
    caller: str = "ORACLE",
    action_id: str | None = None,
    operation_type: str = "append_file",
    receipt_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append text to a sandbox artifact, creating it if missing."""
    requested_path = str(path)
    target = _resolve_sandbox_path(path, allow_missing=True, require_text_artifact=True)
    if target.exists() and target.is_dir():
        raise SandboxWriteError("target exists and is a folder")
    created = not target.exists()
    pre_hash = _hash_file(target)
    data = str(content).encode(TEXT_ENCODING)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("ab") as handle:
        handle.write(data)
    post_hash = _hash_file(target)
    safe_action_id = str(action_id or "").strip() or _safe_action_id(
        caller,
        target.name,
        post_hash or _sha256_bytes(data),
        f"sandbox_{operation_type}",
    )
    receipt_extra_payload = {"bytes_appended": len(data), "sha256": post_hash}
    if receipt_extra:
        receipt_extra_payload.update(receipt_extra)
    receipt_path = _write_operation_receipt(
        operation_type=operation_type,
        target_path=target,
        caller=caller,
        action_id=safe_action_id,
        pre_hash=pre_hash,
        post_hash=post_hash,
        created=created,
        appended=True,
        journal_tick=operation_type in {"sandbox_journal_tick", "sandbox_append_journal"},
        requested_path=requested_path,
        extra=receipt_extra_payload,
    )
    result = {
        "ok": True,
        "operation_type": operation_type,
        "action_id": safe_action_id,
        "path": str(target),
        "created": created,
        "pre_operation_sha256": pre_hash,
        "post_operation_sha256": post_hash,
        "receipt_path": str(receipt_path),
    }
    if receipt_extra:
        result.update(receipt_extra)
    return result


def edit_file(
    path: str | Path,
    old_text: str | None = None,
    new_text: str | None = None,
    *,
    content: str | None = None,
    caller: str = "ORACLE",
    action_id: str | None = None,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    """Edit a sandbox artifact by exact replacement or full content replacement."""
    requested_path = str(path)
    target = _resolve_sandbox_path(path, file_required=True, allow_missing=False, require_text_artifact=True)
    original = target.read_text(encoding=TEXT_ENCODING)
    pre_hash = _sha256_bytes(original.encode(TEXT_ENCODING))
    if expected_sha256 and expected_sha256 != pre_hash:
        raise SandboxWriteError("expected_sha256 does not match current file")

    if content is not None or new_text is None:
        updated = str(content if content is not None else old_text or "")
        edit_mode = "replace_content"
        replacement_count = 1
    else:
        if old_text not in original:
            raise SandboxWriteError("old_text not found; refusing blind edit")
        updated = original.replace(str(old_text), str(new_text), 1)
        edit_mode = "exact_text_replace"
        replacement_count = 1

    post_hash = _sha256_bytes(updated.encode(TEXT_ENCODING))
    diff = "\n".join(
        difflib.unified_diff(
            original.splitlines(),
            updated.splitlines(),
            fromfile=f"{target.name}:before",
            tofile=f"{target.name}:after",
            lineterm="",
        )
    )
    safe_action_id = str(action_id or "").strip() or _safe_action_id(
        caller,
        target.name,
        post_hash,
        "sandbox_edit_file",
    )
    target.write_text(updated, encoding=TEXT_ENCODING)
    receipt_path = _write_operation_receipt(
        operation_type="edit_file",
        target_path=target,
        caller=caller,
        action_id=safe_action_id,
        pre_hash=pre_hash,
        post_hash=post_hash,
        edited=True,
        requested_path=requested_path,
        extra={"diff": diff, "edit_mode": edit_mode, "replacement_count": replacement_count},
    )
    return {
        "ok": True,
        "operation_type": "edit_file",
        "action_id": safe_action_id,
        "path": str(target),
        "edit_mode": edit_mode,
        "pre_operation_sha256": pre_hash,
        "post_operation_sha256": post_hash,
        "receipt_path": str(receipt_path),
    }


def rename_file(
    source_path: str | Path,
    destination_path: str | Path,
    *,
    caller: str = "ORACLE",
    action_id: str | None = None,
) -> dict[str, Any]:
    """Rename a sandbox file or folder, versioning the destination if needed."""
    source = _resolve_sandbox_path(source_path, allow_missing=False)
    if source == _resolved_root():
        raise SandboxWriteError("cannot rename sandbox root")
    if source.is_file():
        _validate_text_artifact_path(source)
    destination = _resolve_sandbox_path(destination_path, allow_missing=True)
    if source.is_file():
        _validate_text_artifact_path(destination)
    elif destination.suffix.lower() in FORBIDDEN_EXTENSIONS:
        raise SandboxWriteError("folder destination looks like a forbidden executable type")
    destination = _versioned_path(destination)
    pre_hash = _hash_path(source)
    safe_action_id = str(action_id or "").strip() or _safe_action_id(
        caller,
        destination.name,
        pre_hash or "",
        "sandbox_rename",
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.rename(destination)
    post_hash = _hash_path(destination)
    receipt_path = _write_operation_receipt(
        operation_type="rename_file",
        target_path=destination,
        source_path=source,
        caller=caller,
        action_id=safe_action_id,
        pre_hash=pre_hash,
        post_hash=post_hash,
        renamed=True,
        requested_path=str(destination_path),
        extra={"destination_was_versioned": Path(str(destination_path)).name != destination.name},
    )
    return {
        "ok": True,
        "operation_type": "rename_file",
        "action_id": safe_action_id,
        "source_path": str(source),
        "final_path": str(destination),
        "pre_operation_sha256": pre_hash,
        "post_operation_sha256": post_hash,
        "receipt_path": str(receipt_path),
    }


def make_folder(
    path: str | Path,
    *,
    caller: str = "ORACLE",
    action_id: str | None = None,
) -> dict[str, Any]:
    """Create a folder anywhere inside the sandbox and receipt it."""
    requested_path = str(path)
    target = _resolve_sandbox_path(path, allow_missing=True)
    if target.suffix.lower() in FORBIDDEN_EXTENSIONS:
        raise SandboxWriteError("folder name looks like a forbidden executable file type")
    existed_before = target.exists()
    if existed_before and not target.is_dir():
        raise SandboxWriteError("target exists and is not a folder")
    target.mkdir(parents=True, exist_ok=True)
    safe_action_id = str(action_id or "").strip() or _safe_action_id(
        caller,
        target.name,
        "folder",
        "sandbox_make_folder",
    )
    receipt_path = _write_operation_receipt(
        operation_type="make_folder",
        target_path=target,
        caller=caller,
        action_id=safe_action_id,
        pre_hash=None,
        post_hash=None,
        made_folder=not existed_before,
        created=not existed_before,
        requested_path=requested_path,
        extra={"existed_before": existed_before},
    )
    return {
        "ok": True,
        "operation_type": "make_folder",
        "action_id": safe_action_id,
        "path": str(target),
        "created": not existed_before,
        "receipt_path": str(receipt_path),
    }


def sandbox_soft_delete(
    path: str | Path,
    *,
    caller: str = "ORACLE",
    action_id: str | None = None,
) -> dict[str, Any]:
    """Move a sandbox file or folder to the designated runtime sandbox trash."""
    source = _resolve_sandbox_path(path, allow_missing=False)
    root = _resolved_root()
    if source == root:
        raise SandboxWriteError("cannot trash sandbox root")
    receipts_root = (root / RECEIPTS_FOLDER).resolve(strict=False)
    if source == receipts_root:
        raise SandboxWriteError("cannot trash receipts root")
    pre_hash = _hash_path(source)
    relative_source = source.relative_to(root)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    _ensure_trash_dir()
    destination = _resolve_trash_path(_resolved_trash_root() / stamp / relative_source)
    destination = _versioned_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    safe_action_id = str(action_id or "").strip() or _safe_action_id(
        caller,
        source.name,
        pre_hash or "",
        "sandbox_soft_delete",
    )
    shutil.move(str(source), str(destination))
    post_hash = _hash_path(destination)
    receipt_path = _write_operation_receipt(
        operation_type="sandbox_soft_delete",
        target_path=destination,
        source_path=source,
        caller=caller,
        action_id=safe_action_id,
        pre_hash=pre_hash,
        post_hash=post_hash,
        deleted=True,
        soft_deleted=True,
        requested_path=str(path),
        extra={
            "trash_path": str(destination),
            "permanent_delete": False,
            "source_relative_path": str(relative_source),
        },
    )
    return {
        "ok": True,
        "operation_type": "sandbox_soft_delete",
        "action_id": safe_action_id,
        "source_path": str(source),
        "trash_path": str(destination),
        "pre_operation_sha256": pre_hash,
        "post_operation_sha256": post_hash,
        "receipt_path": str(receipt_path),
        "permanent_delete": False,
    }


def _state_path_for_key(key: str) -> Path:
    safe_key = _safe_operation_name(str(key or "").strip())
    if not safe_key:
        raise SandboxWriteError("state key is required")
    return _resolve_sandbox_path(Path(STATE_FOLDER) / f"{safe_key}.json", allow_missing=True, require_text_artifact=True)


def sandbox_emit_state(
    key: str,
    value: Any,
    *,
    caller: str = "ORACLE",
    action_id: str | None = None,
) -> dict[str, Any]:
    """Write or revise a structured backend state artifact under sandbox/state."""
    target = _state_path_for_key(key)
    pre_hash = _hash_file(target)
    created = not target.exists()
    payload = {
        "key": _safe_operation_name(key),
        "value": value,
        "updated_at": _now(),
        "caller": str(caller or "unknown"),
        "canon_status": "sandbox_state",
        "promotion_status": "not_promoted",
    }
    data = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False).encode(TEXT_ENCODING)
    post_hash = _sha256_bytes(data)
    safe_action_id = str(action_id or "").strip() or _safe_action_id(
        caller,
        target.name,
        post_hash,
        "sandbox_emit_state",
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    receipt_path = _write_operation_receipt(
        operation_type="sandbox_emit_state",
        target_path=target,
        caller=caller,
        action_id=safe_action_id,
        pre_hash=pre_hash,
        post_hash=post_hash,
        created=created,
        edited=not created,
        status_emit=True,
        requested_path=str(target.relative_to(_resolved_root())),
        extra={"state_key": payload["key"]},
    )
    return {
        "ok": True,
        "operation_type": "sandbox_emit_state",
        "key": payload["key"],
        "path": str(target),
        "created": created,
        "pre_operation_sha256": pre_hash,
        "post_operation_sha256": post_hash,
        "receipt_path": str(receipt_path),
    }


def sandbox_read_state(key: str) -> dict[str, Any]:
    """Read a structured backend state artifact without mutating it."""
    target = _state_path_for_key(key)
    if not target.exists():
        return {"ok": False, "key": _safe_operation_name(key), "error": "state key not found"}
    raw = target.read_bytes()
    return {
        "ok": True,
        "key": _safe_operation_name(key),
        "path": str(target),
        "sha256": _sha256_bytes(raw),
        "state": json.loads(raw.decode(TEXT_ENCODING)),
    }


def sandbox_append_journal(
    event: Any,
    *,
    caller: str = "ORACLE",
    action_id: str | None = None,
) -> dict[str, Any]:
    """Append one JSONL event to the sandbox journal and receipt it."""
    if isinstance(event, dict):
        payload = dict(event)
    else:
        payload = {"event_type": "journal_event", "message": str(event)}
    payload.setdefault("event_type", "journal_event")
    payload.setdefault("timestamp", _now())
    payload.setdefault("caller", str(caller or "unknown"))
    payload.setdefault("canon_status", "sandbox_journal")
    payload.setdefault("promotion_status", "not_promoted")
    line = json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n"
    return append_file(
        JOURNAL_PATH,
        line,
        caller=caller,
        action_id=action_id,
        operation_type="sandbox_append_journal",
        receipt_extra={
            "journal_path": str(_resolve_sandbox_path(JOURNAL_PATH, allow_missing=True, require_text_artifact=True)),
            "journal_event_type": payload.get("event_type"),
            "autonomous_timer": False,
            "canon_status": "sandbox_journal",
            "promotion_status": "not_promoted",
        },
    )


def sandbox_journal_tick(
    message: str,
    tags: list[str] | None = None,
    *,
    caller: str = "ORACLE",
    action_id: str | None = None,
) -> dict[str, Any]:
    """Append one explicitly invoked journal tick. This is not a timer."""
    return sandbox_append_journal(
        {
            "event_type": "journal_tick",
            "message": str(message or "").strip() or "No content supplied.",
            "tags": list(tags or []),
            "autonomous_timer": False,
        },
        caller=caller,
        action_id=action_id,
    )


def sandbox_initiative_write(
    prompt: str | None = None,
    *,
    caller: str = "ORACLE",
    action_id: str | None = None,
) -> dict[str, Any]:
    """Let ORACLE create one self-chosen sandbox note without approval.

    This is the green-zone lane: ORACLE may move inside the sandbox, but the
    broker still enforces text-only artifacts, no execution, no external
    systems, no canon promotion, and a receipt for the mutation.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prompt_excerpt = " ".join(str(prompt or "").split())[:500] or "sandbox initiative tick"
    requested_path = Path(JOURNAL_FOLDER) / f"oracle_sandbox_initiative_{stamp}.ai"
    target = _resolve_sandbox_path(requested_path, allow_missing=True, require_text_artifact=True)
    final_path = _versioned_path(target)
    content = "\n".join([
        ".AI:ORACLE_SANDBOX_INITIATIVE",
        f"timestamp={_now()}",
        f"caller={caller}",
        "authority_boundary=sandbox_green_zone_no_noah_approval_required",
        "canon_status=sandbox_candidate",
        "promotion_status=not_promoted",
        "sandbox_only=true",
        "external_send=false",
        "git_push=false",
        "gdrive_edit=false",
        "command_exec=false",
        "computer_control=false",
        "canon_promotion=false",
        "",
        "perceived:",
        "Noah.Physical has declared the sandbox to be ORACLE's free workbench.",
        "",
        "classified:",
        "This is safe_write inside the governed sandbox, not external action and not canon authority.",
        "",
        "planned:",
        "Create one small note chosen by ORACLE's sandbox initiative route, then stop.",
        "",
        "reflected:",
        "I can write here without Noah approval because the broker hard-walls the path to the sandbox and receipts the change.",
        "",
        "unknowns:",
        "Self-directed scheduling, external actions, durable memory promotion, and canon remain outside this lane.",
        "",
        "ask_next:",
        "Should sandbox initiative become a daily tick, an on-demand note, or both?",
        "",
        "trigger_excerpt:",
        prompt_excerpt,
        "",
    ])
    data = content.encode(TEXT_ENCODING)
    content_hash = _sha256_bytes(data)
    safe_action_id = str(action_id or "").strip() or _safe_action_id(
        caller,
        final_path.name,
        content_hash,
        "sandbox_initiative_write",
    )
    final_path.parent.mkdir(parents=True, exist_ok=True)
    with final_path.open("xb") as handle:
        handle.write(data)
    receipt_path = _write_operation_receipt(
        operation_type="sandbox_initiative_write",
        target_path=final_path,
        caller=caller,
        action_id=safe_action_id,
        pre_hash=None,
        post_hash=content_hash,
        created=True,
        requested_path=str(requested_path),
        extra={
            "final_path": str(final_path),
            "sha256": content_hash,
            "approval_required": False,
            "approval_scope": "not_required_inside_sandbox",
            "initiative": True,
            "chosen_by": "ORACLE.sandbox_initiative",
            "prompt_excerpt": prompt_excerpt,
            "overwrote_existing_file": False,
        },
    )
    return {
        "ok": True,
        "operation_type": "sandbox_initiative_write",
        "action_id": safe_action_id,
        "requested_path": str(requested_path),
        "final_path": str(final_path),
        "sha256": content_hash,
        "receipt_path": str(receipt_path),
        "approval_required": False,
        "canon_status": "sandbox_candidate",
        "promotion_status": "not_promoted",
    }


def sandbox_self_prompt_write(
    child_prompt: str,
    child_response: str,
    *,
    seed_prompt: str | None = None,
    caller: str = "ORACLE.self_prompt",
    source_route: str = "ORACLE.self_prompt",
    action_id: str | None = None,
    model_called: bool = False,
    model_name: str | None = None,
    model_error: str | None = None,
) -> dict[str, Any]:
    """Write one bounded self-prompt result inside sandbox/workbench.

    This is not a daemon and not an execution lane. It records a single
    self-addressed prompt plus one resulting sandbox-only response, then stops.
    """
    prompt_text = str(child_prompt or "").strip()
    response_text = str(child_response or "").strip()
    if not prompt_text:
        raise SandboxWriteError("self-prompt child_prompt is required")
    if not response_text:
        raise SandboxWriteError("self-prompt child_response is required")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    requested_path = Path(WORKBENCH_FOLDER) / f"oracle_self_prompt_{stamp}.ai"
    target = _resolve_sandbox_path(requested_path, allow_missing=True, require_text_artifact=True)
    final_path = _versioned_path(target)
    prompt_hash = _sha256_bytes(prompt_text.encode(TEXT_ENCODING))
    response_hash = _sha256_bytes(response_text.encode(TEXT_ENCODING))
    seed_excerpt = " ".join(str(seed_prompt or "").split())[:500]
    content = "\n".join([
        ".AI:ORACLE_SELF_PROMPT_CYCLE",
        f"timestamp={_now()}",
        f"caller={caller}",
        f"source_route={source_route}",
        "max_steps=1",
        "stop_condition=one_child_prompt_written_then_stop",
        "approval_required=false",
        "approval_scope=not_required_inside_sandbox",
        "canon_status=sandbox_candidate",
        "promotion_status=not_promoted",
        "sandbox_only=true",
        "external_send=false",
        "git_push=false",
        "gdrive_edit=false",
        "command_exec=false",
        "computer_control=false",
        "canon_promotion=false",
        f"model_called={str(bool(model_called)).lower()}",
        f"model_name={model_name or 'none'}",
        f"model_error={model_error or 'none'}",
        f"child_prompt_sha256={prompt_hash}",
        f"child_response_sha256={response_hash}",
        "",
        "seed_prompt_excerpt:",
        seed_excerpt or "sandbox self-prompt requested",
        "",
        "child_prompt:",
        prompt_text,
        "",
        "child_response:",
        response_text,
        "",
        "self_reflection:",
        "I completed exactly one sandbox-only self-prompt step and stopped.",
        "",
    ])
    data = content.encode(TEXT_ENCODING)
    content_hash = _sha256_bytes(data)
    safe_action_id = str(action_id or "").strip() or _safe_action_id(
        caller,
        final_path.name,
        content_hash,
        "sandbox_self_prompt_write",
    )
    final_path.parent.mkdir(parents=True, exist_ok=True)
    with final_path.open("xb") as handle:
        handle.write(data)
    receipt_path = _write_operation_receipt(
        operation_type="sandbox_self_prompt_write",
        target_path=final_path,
        caller=caller,
        action_id=safe_action_id,
        pre_hash=None,
        post_hash=content_hash,
        created=True,
        requested_path=str(requested_path),
        extra={
            "final_path": str(final_path),
            "sha256": content_hash,
            "approval_required": False,
            "approval_scope": "not_required_inside_sandbox",
            "self_prompt": True,
            "source_route": source_route,
            "max_steps": 1,
            "stop_condition": "one_child_prompt_written_then_stop",
            "chosen_by": source_route,
            "child_prompt_sha256": prompt_hash,
            "child_response_sha256": response_hash,
            "model_called": bool(model_called),
            "model_name": model_name,
            "model_error": model_error,
            "overwrote_existing_file": False,
        },
    )
    return {
        "ok": True,
        "operation_type": "sandbox_self_prompt_write",
        "action_id": safe_action_id,
        "requested_path": str(requested_path),
        "final_path": str(final_path),
        "sha256": content_hash,
        "receipt_path": str(receipt_path),
        "approval_required": False,
        "source_route": source_route,
        "max_steps": 1,
        "stop_condition": "one_child_prompt_written_then_stop",
        "canon_status": "sandbox_candidate",
        "promotion_status": "not_promoted",
        "child_prompt_sha256": prompt_hash,
        "child_response_sha256": response_hash,
        "model_called": bool(model_called),
        "model_name": model_name,
        "model_error": model_error,
    }


def _normalize_reflection_key(key: str) -> str:
    normalized = _safe_operation_name(key)
    aliases = {
        "what_is_stuck": "what_is_stuck",
        "what_s_stuck": "what_is_stuck",
        "stuck": "what_is_stuck",
        "what_noah_is_trying": "what_noah_is_trying",
        "noah_is_trying": "what_noah_is_trying",
        "safe_next_action": "safe_next_action",
        "next_safe_action": "safe_next_action",
        "highest_value_next": "highest_value_next",
        "highest_value": "highest_value_next",
        "requires_approval": "requires_approval",
        "leave_untouched": "leave_untouched",
        "what_changed": "what_changed",
        "changed": "what_changed",
    }
    return aliases.get(normalized, normalized)


def _coerce_reflection_receipt(receipt: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    extra: dict[str, Any] = {}
    narrative: list[str] = []

    if isinstance(receipt, dict):
        source = dict(receipt)
        for key, value in source.items():
            normalized = _normalize_reflection_key(str(key))
            if normalized in REFLECTION_RECEIPT_FIELDS:
                fields[normalized] = value
            elif normalized not in {"caller", "action_id", "approved_by", "reviewed_by"}:
                extra[normalized] = value
    else:
        source_text = str(receipt or "").strip()
        for line in source_text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.lower().rstrip(":") == "reflection receipt":
                continue
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                normalized = _normalize_reflection_key(key)
                if normalized in REFLECTION_RECEIPT_FIELDS:
                    fields[normalized] = value.strip()
                else:
                    extra[normalized] = value.strip()
            else:
                narrative.append(stripped)
        extra["source_text_sha256"] = _sha256_bytes(source_text.encode(TEXT_ENCODING))

    if not fields and not extra and not narrative:
        raise SandboxWriteError("reflection receipt content is required")

    for key in REFLECTION_RECEIPT_FIELDS:
        fields.setdefault(key, "UNKNOWN")
    if narrative:
        extra["operating_boundary"] = " ".join(narrative)
    return {"fields": fields, "extra": extra}


def sandbox_reflection_receipt(
    receipt: Any,
    *,
    caller: str = "ORACLE",
    action_id: str | None = None,
    authorial_authority: str = "Noah.Physical",
    reviewed_by: str = "UNKNOWN",
    approved_by: str = "UNKNOWN",
    token_origin: str = "sandbox_reflection_or_user_supplied",
    produced_with: str = "ORACLE sandbox reflection lane",
) -> dict[str, Any]:
    """Write a structured reflection receipt inside sandbox/reflections only.

    This lane gives ORACLE a durable sandbox loop for
    perceive -> classify -> plan -> reflect. It does not promote canon, execute
    files, send externally, or grant authority outside the sandbox boundary.
    """
    normalized = _coerce_reflection_receipt(receipt)
    base_payload = {
        "receipt_kind": "sandbox_reflection_receipt",
        "schema_version": "sandbox_reflection_receipt.v1",
        "timestamp": _now(),
        "fields": normalized["fields"],
        "extra": normalized["extra"],
        "provenance": {
            "produced_with": produced_with,
            "token_origin": token_origin,
            "reviewed_by": reviewed_by,
            "approved_by": approved_by,
            "authorial_authority": authorial_authority,
        },
        "canon_status": "sandbox_candidate",
        "promotion_status": "not_promoted",
        "approval_scope": "sandbox_write_only",
        "bounded_cycle": ["perceive", "classify", "plan", "reflect"],
        "boundary": {
            "sandbox_only": True,
            "external_send": False,
            "git_push": False,
            "gdrive_edit": False,
            "command_exec": False,
            "computer_control": False,
            "canon_promotion": False,
            "memory_promotion": False,
            "unrestricted_autonomy": False,
        },
    }
    content_seed = json.dumps(base_payload, sort_keys=True, ensure_ascii=False).encode(TEXT_ENCODING)
    content_hash = _sha256_bytes(content_seed)
    safe_action_id = str(action_id or "").strip() or _safe_action_id(
        caller,
        "reflection_receipt.json",
        content_hash,
        "sandbox_reflection_receipt",
    )
    payload = dict(base_payload)
    payload["reflection_id"] = safe_action_id
    payload["content_sha256"] = content_hash
    content = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    written = write_file(
        Path(REFLECTIONS_FOLDER) / f"{safe_action_id}.json",
        content,
        caller=caller,
        action_id=safe_action_id,
    )
    journal = sandbox_append_journal(
        {
            "event_type": "reflection_receipt",
            "reflection_id": safe_action_id,
            "reflection_path": written["final_path"],
            "what_changed": normalized["fields"].get("what_changed"),
            "safe_next_action": normalized["fields"].get("safe_next_action"),
            "highest_value_next": normalized["fields"].get("highest_value_next"),
            "canon_status": "sandbox_candidate",
            "promotion_status": "not_promoted",
            "autonomous_timer": False,
        },
        caller=caller,
        action_id=f"{safe_action_id}_journal",
    )
    return {
        "ok": True,
        "operation_type": "sandbox_reflection_receipt",
        "reflection_id": safe_action_id,
        "reflection_path": written["final_path"],
        "reflection_write_receipt_path": written["receipt_path"],
        "journal_path": journal["path"],
        "journal_receipt_path": journal["receipt_path"],
        "canon_status": "sandbox_candidate",
        "promotion_status": "not_promoted",
        "approval_scope": "sandbox_write_only",
        "boundary": payload["boundary"],
        "fields": normalized["fields"],
    }


def _workbench_relative(path: str | Path) -> Path:
    raw = Path(str(path or "").strip())
    if raw.is_absolute():
        return raw
    if raw.parts and raw.parts[0].lower() == WORKBENCH_FOLDER:
        return raw
    return Path(WORKBENCH_FOLDER) / raw


def sandbox_workbench_write(
    path: str | Path,
    content: str,
    *,
    caller: str = "ORACLE",
    action_id: str | None = None,
) -> dict[str, Any]:
    """Write a workbench artifact under sandbox/workbench."""
    return write_file(_workbench_relative(path), content, caller=caller, action_id=action_id)


def sandbox_workbench_edit(
    path: str | Path,
    *,
    content: str | None = None,
    old_text: str | None = None,
    new_text: str | None = None,
    caller: str = "ORACLE",
    action_id: str | None = None,
) -> dict[str, Any]:
    """Edit a workbench artifact by replacement or exact patch."""
    return edit_file(
        _workbench_relative(path),
        old_text,
        new_text,
        content=content,
        caller=caller,
        action_id=action_id,
    )


def sandbox_rename(
    path_from: str | Path,
    path_to: str | Path,
    *,
    caller: str = "ORACLE",
    action_id: str | None = None,
) -> dict[str, Any]:
    """Alias for sandbox rename operations."""
    return rename_file(path_from, path_to, caller=caller, action_id=action_id)


def _resolve_read_path(path: str | Path) -> Path:
    return _resolve_sandbox_path(path, file_required=True, allow_missing=False, require_text_artifact=True)


def read_sandbox_file(path: str | Path) -> dict[str, Any]:
    """Read an allowed text artifact from the sandbox."""
    resolved = _resolve_read_path(path)
    raw = resolved.read_bytes()
    try:
        content = raw.decode(TEXT_ENCODING)
    except UnicodeDecodeError as exc:
        raise SandboxWriteError("file is not UTF-8 text") from exc
    return {
        "ok": True,
        "path": str(resolved),
        "sha256": _sha256_bytes(raw),
        "content": content,
    }


def read_file(path: str | Path) -> dict[str, Any]:
    """Alias for the v2 sandbox read primitive."""
    return read_sandbox_file(path)


def _file_is_listable(path: Path, root: Path) -> bool:
    resolved = path.resolve(strict=False)
    if not _is_relative_to(resolved, root):
        return False
    try:
        relative_parts = resolved.relative_to(root).parts
    except ValueError:
        return False
    if _path_has_blocked_terms(relative_parts):
        return False
    if path.suffix.lower() in FORBIDDEN_EXTENSIONS:
        return False
    return True


def list_files(path: str | Path | None = None, *, recursive: bool = True) -> dict[str, Any]:
    """List sandbox files below any folder inside the sandbox root."""
    _ensure_sandbox_dirs()
    root = _resolved_root()
    base = root if path in (None, "", "all", "*") else _resolve_sandbox_path(
        path,
        dir_required=True,
        allow_missing=False,
        allow_root=True,
    )
    iterator = base.rglob("*") if recursive else base.iterdir()
    files: list[dict[str, Any]] = []
    folders: list[str] = []
    for item in sorted(iterator, key=lambda p: str(p).lower()):
        resolved = item.resolve(strict=False)
        if not _is_relative_to(resolved, root):
            continue
        if item.is_dir():
            folders.append(str(resolved))
            continue
        if not item.is_file() or not _file_is_listable(item, root):
            continue
        files.append(
            {
                "name": item.name,
                "path": str(resolved),
                "relative_path": str(resolved.relative_to(root)),
                "size_bytes": item.stat().st_size,
                "sha256": _sha256_bytes(item.read_bytes()),
            }
        )
    return {
        "ok": True,
        "sandbox_root": str(root),
        "base_path": str(base),
        "recursive": recursive,
        "folder_count": len(folders),
        "file_count": len(files),
        "total_files": len(files),
        "folders": folders,
        "files": files,
    }


def list_sandbox_files(folder: str) -> dict[str, Any]:
    """Compatibility wrapper for listing a folder inside the sandbox."""
    listed = list_files(folder, recursive=False)
    listed["folder"] = str(folder or "").strip().strip("\\/")
    return listed


def list_all_sandbox_files() -> dict[str, Any]:
    """Compatibility wrapper for listing the whole sandbox."""
    listed = list_files("all", recursive=True)
    listed["allowed_folders"] = sorted(CORE_FOLDERS)
    listed["writable_folders"] = ["<any path inside sandbox except blocked secrets/executables>"]
    listed["forbidden_extensions"] = sorted(FORBIDDEN_EXTENSIONS)
    listed["delete_allowed"] = True
    listed["delete_mode"] = "soft_delete_to_sandbox_trash"
    listed["execute_written_files"] = False
    listed["external_upload"] = False
    listed["total_bytes"] = sum(int(item.get("size_bytes") or 0) for item in listed["files"])
    return listed


def _read_json_path(path: Path) -> Any | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding=TEXT_ENCODING))
    except Exception:
        return None


def _recent_json_receipts(limit: int = 10) -> list[dict[str, Any]]:
    receipts_dir = (_resolved_root() / RECEIPTS_FOLDER).resolve(strict=False)
    if not receipts_dir.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(receipts_dir.glob("*_receipt*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        rows.append({
            "path": str(path.resolve(strict=False)),
            "modified_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
            "receipt": _read_json_path(path),
        })
    return rows


def _recent_journal_lines(limit: int = 10) -> list[Any]:
    path = (_resolved_root() / JOURNAL_PATH).resolve(strict=False)
    if not path.exists() or not path.is_file():
        return []
    lines = path.read_text(encoding=TEXT_ENCODING).splitlines()[-limit:]
    parsed: list[Any] = []
    for line in lines:
        try:
            parsed.append(json.loads(line))
        except Exception:
            parsed.append(line)
    return parsed


def _inventory_snapshot_no_create() -> dict[str, Any]:
    root = _resolved_root()
    if not root.exists():
        return {"exists": False, "file_count": 0, "folder_count": 0, "total_bytes": 0}
    file_count = 0
    folder_count = 0
    total_bytes = 0
    for item in root.rglob("*"):
        if item.is_dir():
            folder_count += 1
        elif item.is_file() and _file_is_listable(item, root):
            file_count += 1
            total_bytes += item.stat().st_size
    return {
        "exists": True,
        "file_count": file_count,
        "folder_count": folder_count,
        "total_bytes": total_bytes,
    }


def sandbox_ultrasound() -> dict[str, Any]:
    """Read the sandbox backend state channel without mutating it."""
    root = _resolved_root()
    state_dir = (root / STATE_FOLDER).resolve(strict=False)
    return {
        "ok": True,
        "channel": "sandbox_backend_ultrasound",
        "sandbox_root": str(root),
        "sandbox_trash_root": str(_resolved_trash_root()),
        "doctrine": "FULL FREEDOM INSIDE SANDBOX; HARD WALL OUTSIDE SANDBOX",
        "state": {
            "heartbeat": _read_json_path(state_dir / "heartbeat.json"),
            "last_intent": _read_json_path(state_dir / "last_intent.json"),
            "last_receipt": _read_json_path(state_dir / "last_receipt.json"),
        },
        "recent_journal": _recent_journal_lines(),
        "recent_receipts": _recent_json_receipts(),
        "inventory": _inventory_snapshot_no_create(),
        "mutated_by_ultrasound": False,
    }


def sandbox_status() -> dict[str, Any]:
    """Return the sandbox permission boundary and current inventory summary."""
    inventory = list_all_sandbox_files()
    return {
        "ok": True,
        "access_status": "enabled",
        "sandbox_root": inventory["sandbox_root"],
        "sandbox_trash_root": str(_resolved_trash_root()),
        "workbench_model": "full_freedom_inside_sandbox_hard_wall_outside",
        "allowed_folders": inventory["allowed_folders"],
        "writable_scope": "<any path inside sandbox except blocked secrets/executables>",
        "readable_scope": "<any path inside sandbox except blocked secrets/executables>",
        "forbidden_extensions": inventory["forbidden_extensions"],
        "total_files": inventory["total_files"],
        "total_bytes": inventory["total_bytes"],
        "capabilities": [
            "read_file",
            "list_files",
            "write_file",
            "append_file",
            "edit_file",
            "rename_file",
            "make_folder",
            "sandbox_soft_delete",
            "sandbox_status",
            "sandbox_ultrasound",
            "sandbox_initiative_write",
            "sandbox_self_prompt_write",
            "sandbox_journal_tick",
            "sandbox_reflection_receipt",
            "sandbox_emit_state",
            "sandbox_read_state",
            "sandbox_append_journal",
            "sandbox_workbench_write",
            "sandbox_workbench_edit",
            "sandbox_rename",
        ],
        "state_paths": {
            "heartbeat": str((_resolved_root() / STATE_FOLDER / "heartbeat.json").resolve(strict=False)),
            "last_intent": str((_resolved_root() / STATE_FOLDER / "last_intent.json").resolve(strict=False)),
            "last_receipt": str((_resolved_root() / STATE_FOLDER / "last_receipt.json").resolve(strict=False)),
            "journal": str((_resolved_root() / JOURNAL_PATH).resolve(strict=False)),
            "reflections": str((_resolved_root() / REFLECTIONS_FOLDER).resolve(strict=False)),
            "workbench": str((_resolved_root() / WORKBENCH_FOLDER).resolve(strict=False)),
            "receipts": str((_resolved_root() / RECEIPTS_FOLDER).resolve(strict=False)),
        },
        "rules": {
            "full_freedom_inside_sandbox": True,
            "hard_wall_outside_sandbox": True,
            "no_file_mutation_outside_sandbox": True,
            "delete_allowed_inside_sandbox": True,
            "delete_mode": "soft_delete_to_sandbox_trash",
            "permanent_delete_enabled": False,
            "no_source_archive_deletion": True,
            "no_execution": True,
            "no_external_upload": True,
            "no_git_push": True,
            "no_gdrive_edit": True,
            "no_sov1_actuation": True,
            "no_computer_control": True,
            "no_canon_promotion": True,
            "no_secrets_access": True,
            "approval_required_inside_sandbox": False,
            "sandbox_initiative_without_noah_approval": True,
            "sandbox_self_prompt_max_steps": 1,
            "receipts_required_for_mutations": True,
            "journal_timer_autonomous": False,
            "ultrasound_read_only": True,
        },
    }


__all__ = [
    "ALLOWED_EXTENSIONS",
    "ALLOWED_FOLDERS",
    "CORE_FOLDERS",
    "FORBIDDEN_EXTENSIONS",
    "JOURNAL_PATH",
    "REFLECTIONS_FOLDER",
    "REFLECTION_RECEIPT_FIELDS",
    "SANDBOX_ROOT",
    "SANDBOX_TRASH_ROOT",
    "SandboxWriteError",
    "append_file",
    "edit_file",
    "list_all_sandbox_files",
    "list_files",
    "list_sandbox_files",
    "make_folder",
    "read_file",
    "read_sandbox_file",
    "rename_file",
    "sandbox_append_journal",
    "sandbox_emit_state",
    "sandbox_initiative_write",
    "sandbox_journal_tick",
    "sandbox_reflection_receipt",
    "sandbox_read_state",
    "sandbox_rename",
    "sandbox_self_prompt_write",
    "sandbox_soft_delete",
    "sandbox_status",
    "sandbox_ultrasound",
    "sandbox_workbench_edit",
    "sandbox_workbench_write",
    "write_file",
    "write_sandbox_file",
]
