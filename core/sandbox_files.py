"""Harmless local file-write training wheels for ORACLE.

This module permits text writes only inside C:\\ORACLE.AI\\sandbox and only in
named safe folders. It never deletes, executes, or overwrites files.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SANDBOX_ROOT = Path(r"C:\ORACLE.AI\sandbox")
ALLOWED_FOLDERS = frozenset({"notes", "drafts", "handoffs", "receipts", "tests"})
WRITABLE_FOLDERS = frozenset({"notes", "drafts", "handoffs", "tests"})
RECEIPTS_FOLDER = "receipts"
ALLOWED_EXTENSIONS = frozenset({".txt", ".md", ".json", ".ai"})
FORBIDDEN_EXTENSIONS = frozenset({".py", ".bat", ".ps1", ".exe", ".cmd", ".sh"})
TEXT_ENCODING = "utf-8"


class SandboxWriteError(ValueError):
    """Raised when a sandbox operation would violate the write boundary."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_action_id(caller: str, requested_filename: str, content_hash: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    seed = f"{caller}|{requested_filename}|{content_hash}|{stamp}".encode(TEXT_ENCODING)
    return f"sandbox_write_{stamp}_{_sha256_bytes(seed)[:10]}"


def _resolved_root() -> Path:
    return SANDBOX_ROOT.resolve(strict=False)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _ensure_sandbox_dirs() -> None:
    root = _resolved_root()
    root.mkdir(parents=True, exist_ok=True)
    for folder in ALLOWED_FOLDERS:
        (root / folder).mkdir(parents=True, exist_ok=True)


def _validate_folder(folder: str, *, for_write: bool = False) -> str:
    value = str(folder or "").strip().strip("\\/")
    if not value:
        raise SandboxWriteError("folder is required")
    if "\\" in value or "/" in value or value in {".", ".."}:
        raise SandboxWriteError("folder must be one approved sandbox folder name")
    allowed = WRITABLE_FOLDERS if for_write else ALLOWED_FOLDERS
    if value not in allowed:
        raise SandboxWriteError(f"folder is not allowed: {value}")
    return value


def _validate_filename(filename: str) -> str:
    value = str(filename or "").strip()
    if not value:
        raise SandboxWriteError("filename is required")
    p = Path(value)
    if p.name != value or any(sep in value for sep in ("/", "\\")):
        raise SandboxWriteError("filename must not include a path")
    if value in {".", ".."}:
        raise SandboxWriteError("filename is invalid")
    suffix = p.suffix.lower()
    if suffix in FORBIDDEN_EXTENSIONS:
        raise SandboxWriteError(f"file type is forbidden: {suffix}")
    if suffix not in ALLOWED_EXTENSIONS:
        raise SandboxWriteError(f"file type is not allowed: {suffix or '(none)'}")
    return value


def _folder_path(folder: str, *, for_write: bool = False) -> Path:
    folder_name = _validate_folder(folder, for_write=for_write)
    _ensure_sandbox_dirs()
    root = _resolved_root()
    path = (root / folder_name).resolve(strict=False)
    if not _is_relative_to(path, root):
        raise SandboxWriteError("resolved folder escaped sandbox root")
    return path


def _unique_path(folder: str, filename: str) -> Path:
    folder_dir = _folder_path(folder, for_write=True)
    safe_name = _validate_filename(filename)
    candidate = (folder_dir / safe_name).resolve(strict=False)
    root = _resolved_root()
    if not _is_relative_to(candidate, root):
        raise SandboxWriteError("resolved file escaped sandbox root")
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    for version in range(2, 10_000):
        versioned = (folder_dir / f"{stem}_v{version}{suffix}").resolve(strict=False)
        if not _is_relative_to(versioned, root):
            raise SandboxWriteError("resolved versioned file escaped sandbox root")
        if not versioned.exists():
            return versioned
    raise SandboxWriteError("could not create a non-overwriting versioned filename")


def _receipt_path(action_id: str) -> Path:
    receipts_dir = _folder_path(RECEIPTS_FOLDER, for_write=False)
    base = f"{action_id}_receipt.json"
    candidate = (receipts_dir / base).resolve(strict=False)
    root = _resolved_root()
    if not _is_relative_to(candidate, root):
        raise SandboxWriteError("resolved receipt path escaped sandbox root")
    if not candidate.exists():
        return candidate
    for version in range(2, 10_000):
        versioned = (receipts_dir / f"{action_id}_receipt_v{version}.json").resolve(strict=False)
        if not _is_relative_to(versioned, root):
            raise SandboxWriteError("resolved receipt version escaped sandbox root")
        if not versioned.exists():
            return versioned
    raise SandboxWriteError("could not create a non-overwriting receipt filename")


def write_sandbox_file(
    folder: str,
    filename: str,
    content: str,
    *,
    caller: str = "ORACLE",
    action_id: str | None = None,
) -> dict[str, Any]:
    """Write a text file inside the approved sandbox and emit a receipt."""
    safe_filename = _validate_filename(filename)
    data = str(content).encode(TEXT_ENCODING)
    final_path = _unique_path(folder, safe_filename)
    content_hash = _sha256_bytes(data)
    safe_action_id = str(action_id or "").strip() or _safe_action_id(caller, safe_filename, content_hash)

    final_path.parent.mkdir(parents=True, exist_ok=True)
    with final_path.open("xb") as handle:
        handle.write(data)

    receipt = {
        "receipt_kind": "sandbox_file_write_receipt",
        "schema_version": "sandbox_files.v1",
        "timestamp": _now(),
        "requested_filename": safe_filename,
        "requested_folder": _validate_folder(folder, for_write=True),
        "final_path": str(final_path),
        "sha256": content_hash,
        "caller": str(caller or "unknown"),
        "action_id": safe_action_id,
        "operation": "write_sandbox_file",
        "sandbox_root": str(_resolved_root()),
        "executed_written_file": False,
        "overwrote_existing_file": False,
        "cloud_upload": False,
        "git_push": False,
    }
    receipt["receipt_hash_sha256"] = _sha256_bytes(
        json.dumps(receipt, sort_keys=True, ensure_ascii=False).encode(TEXT_ENCODING)
    )
    receipt_path = _receipt_path(safe_action_id)
    with receipt_path.open("xb") as handle:
        handle.write(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False).encode(TEXT_ENCODING))

    return {
        "ok": True,
        "action_id": safe_action_id,
        "requested_filename": safe_filename,
        "final_path": str(final_path),
        "sha256": content_hash,
        "receipt_path": str(receipt_path),
        "receipt_hash_sha256": receipt["receipt_hash_sha256"],
    }


def _resolve_read_path(path: str | Path) -> Path:
    _ensure_sandbox_dirs()
    root = _resolved_root()
    raw = Path(str(path or "").strip())
    if not str(raw):
        raise SandboxWriteError("path is required")
    candidate = raw if raw.is_absolute() else root / raw
    resolved = candidate.resolve(strict=False)
    if not _is_relative_to(resolved, root):
        raise SandboxWriteError("read path escaped sandbox root")
    if resolved.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise SandboxWriteError("read file type is not allowed")
    if not resolved.exists() or not resolved.is_file():
        raise SandboxWriteError("file not found")
    return resolved


def read_sandbox_file(path: str | Path) -> dict[str, Any]:
    """Read an allowed text file from the sandbox."""
    resolved = _resolve_read_path(path)
    raw = resolved.read_bytes()
    return {
        "ok": True,
        "path": str(resolved),
        "sha256": _sha256_bytes(raw),
        "content": raw.decode(TEXT_ENCODING),
    }


def list_sandbox_files(folder: str) -> dict[str, Any]:
    """List allowed files in one approved sandbox folder."""
    folder_dir = _folder_path(folder, for_write=False)
    files: list[dict[str, Any]] = []
    for path in sorted(folder_dir.iterdir(), key=lambda p: p.name.lower()):
        resolved = path.resolve(strict=False)
        if not path.is_file() or not _is_relative_to(resolved, _resolved_root()):
            continue
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        files.append(
            {
                "name": path.name,
                "path": str(resolved),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256_bytes(path.read_bytes()),
            }
        )
    return {"ok": True, "folder": _validate_folder(folder), "path": str(folder_dir), "files": files}


__all__ = [
    "ALLOWED_EXTENSIONS",
    "ALLOWED_FOLDERS",
    "SANDBOX_ROOT",
    "SandboxWriteError",
    "list_sandbox_files",
    "read_sandbox_file",
    "write_sandbox_file",
]
