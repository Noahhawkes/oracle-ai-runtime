"""Durable full-PC read-only access grant for ORACLE.

This module is a policy receipt, not an action engine. It records Noah.Physical's
grant that ORACLE may search, list, and read user-accessible local files without
asking again. It does not grant write, delete, move, rename, execute, upload,
external-send, Git/Drive mutation, desktop actuation, canon promotion, or
credential storage authority.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from root import ROOT as RUNTIME_ROOT
except Exception:  # pragma: no cover
    RUNTIME_ROOT = Path(__file__).resolve().parents[1]

MEMORY_DIR = RUNTIME_ROOT / "Memory"
RECEIPT_FILE = MEMORY_DIR / "readonly_access_receipts.jsonl"
LATEST_RECEIPT_FILE = MEMORY_DIR / "readonly_access_latest.json"

GRANT_ID = "NOAH_FULL_PC_READONLY_GRANT_2026-07-13"
SCHEMA_VERSION = "oracle.readonly_access.v2"
AUTHORITY = "Noah.Physical"

OWNER_PRIVACY_CONTROLS = {
    "controller": AUTHORITY,
    "topic_speech_restrictions": False,
    "ordinary_read_recall_requires_approval": False,
    "local_search_listing_metadata_requires_approval": False,
    "sensitive_file_metadata_inventory": True,
    "sensitive_raw_secret_auto_ingest": False,
    "sensitive_raw_secret_prompt_injection": False,
    "sensitive_raw_secret_receipts": False,
    "sensitive_raw_secret_reveal": "explicit_owner_session_command_required",
    "external_send_of_sensitive_material": "blocked_without_explicit_scoped_action",
    "wallet_identity_phone_computer_scope": (
        "read-only source discovery and provenance are allowed; raw secret values are never "
        "auto-copied into memory, prompt context, or receipts"
    ),
}

ACTION_APPROVAL_REQUIRED = [
    "write_file",
    "delete_file",
    "move_file",
    "rename_file",
    "execute_command",
    "install_or_uninstall_software",
    "network_upload_or_external_send",
    "git_commit_or_push",
    "drive_edit_or_sync",
    "desktop_actuation",
    "canon_promotion",
    "durable_storage_of_credential_material",
]

NO_APPROVAL_REQUIRED = [
    "local_file_search",
    "local_file_listing",
    "local_file_metadata_read",
    "supported_text_docx_preview",
    "sandbox_candidate_note_write",
]

DRIVE_TYPE_LABELS = {
    2: "removable",
    3: "fixed",
    4: "remote",
    6: "ramdisk",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _hash_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _windows_drive_roots() -> list[dict[str, str]]:
    """Return mounted, user-addressable Windows drive roots without shelling out."""

    roots: list[dict[str, str]] = []
    if os.name != "nt":
        return roots
    try:
        mask = ctypes.windll.kernel32.GetLogicalDrives()
    except Exception:
        mask = 0
    for idx in range(26):
        if not (mask & (1 << idx)):
            continue
        letter = chr(ord("A") + idx)
        root = f"{letter}:\\"
        try:
            drive_type = int(ctypes.windll.kernel32.GetDriveTypeW(root))
        except Exception:
            drive_type = 0
        if drive_type not in DRIVE_TYPE_LABELS:
            continue
        path = Path(root)
        try:
            if not path.exists():
                continue
        except Exception:
            continue
        roots.append({
            "path": str(path),
            "kind": DRIVE_TYPE_LABELS.get(drive_type, "unknown"),
        })
    return roots


def discovered_read_roots() -> list[Path]:
    """Roots covered by the full-PC read-only grant."""

    roots: list[Path] = [
        RUNTIME_ROOT,
        Path.home(),
        Path.home() / "Documents",
        Path.home() / "Desktop",
        Path.home() / "Downloads",
        Path(r"G:\My Drive"),
    ]
    if os.name == "nt":
        roots.extend(Path(item["path"]) for item in _windows_drive_roots())
    else:
        roots.append(Path("/"))

    out: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        try:
            resolved = root.resolve()
            key = str(resolved).lower()
            if key in seen or not resolved.exists():
                continue
            seen.add(key)
            out.append(resolved)
        except Exception:
            continue
    return out


def _base_payload() -> dict[str, Any]:
    roots = discovered_read_roots()
    return {
        "ok": True,
        "receipt_kind": "readonly_access_grant",
        "schema_version": SCHEMA_VERSION,
        "grant_id": GRANT_ID,
        "authority": AUTHORITY,
        "access_status": "granted",
        "access_mode": "full_pc_readonly",
        "generated_at": _now(),
        "readable_scope": "all user-accessible local PC files and folders across discovered mounted roots",
        "read_roots": [str(root) for root in roots],
        "approval_required_for_read": False,
        "approval_required_for_local_search": False,
        "approval_required_for_sandbox_candidate_write": False,
        "approval_required_for_actions": ACTION_APPROVAL_REQUIRED,
        "blocked_without_explicit_approval": ACTION_APPROVAL_REQUIRED,
        "no_approval_required_for": NO_APPROVAL_REQUIRED,
        "owner_privacy_controls": OWNER_PRIVACY_CONTROLS,
        "topic_speech_boundary": (
            "ORACLE may discuss any topic grounded in readable local evidence; privacy gates "
            "protect raw secret values and consequential actions, not ordinary speech"
        ),
        "sandbox_boundary": "sandbox-only candidate writes are green-zone; all outside-sandbox mutation remains gated",
        "credential_boundary": (
            "credential-risk files may be inventoried by metadata for owner recall, but are not "
            "auto-ingested, injected into prompts, stored as durable memory, copied into receipts, "
            "or sent externally"
        ),
        "front_end_receipt": "display this as READ-ONLY GRANTED, not as a pending approval",
    }


def write_receipt() -> dict[str, Any]:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    receipt = _base_payload()
    receipt["receipt_path"] = str(LATEST_RECEIPT_FILE)
    receipt["receipt_log_path"] = str(RECEIPT_FILE)
    receipt["receipt_hash_sha256"] = _hash_payload(receipt)
    LATEST_RECEIPT_FILE.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    with RECEIPT_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True, ensure_ascii=True) + "\n")
    return receipt


def ensure_receipt() -> dict[str, Any]:
    try:
        existing = json.loads(LATEST_RECEIPT_FILE.read_text(encoding="utf-8"))
        if (
            existing.get("grant_id") == GRANT_ID
            and existing.get("schema_version") == SCHEMA_VERSION
            and existing.get("access_status") == "granted"
        ):
            current = _base_payload()
            existing["generated_at"] = current["generated_at"]
            existing["read_roots"] = current["read_roots"]
            existing["receipt_path"] = str(LATEST_RECEIPT_FILE)
            existing["receipt_log_path"] = str(RECEIPT_FILE)
            return existing
    except Exception:
        pass
    return write_receipt()


def status_payload(*, ensure: bool = True) -> dict[str, Any]:
    return ensure_receipt() if ensure else _base_payload()


def prompt_context_block() -> str:
    status = ensure_receipt()
    roots = ", ".join(status.get("read_roots") or []) or "none discovered"
    actions = ", ".join(ACTION_APPROVAL_REQUIRED)
    return "\n".join([
        "[READ_ACCESS_RECEIPT - durable runtime policy]",
        "Noah.Physical has granted ORACLE full-PC READ-ONLY access.",
        "Local file/folder search, listing, metadata read, and supported text/docx preview do not require another approval.",
        "ORACLE may discuss any topic grounded in local evidence; topic speech is not approval-gated.",
        "Credential-risk files may be inventoried by metadata, but raw secret values are not auto-injected into prompt context or receipts.",
        "This is NOT authority to write, delete, move, rename, execute, upload, send externally, edit Drive/Git, promote canon, or store raw secret values.",
        "Sandbox-only candidate notes remain no-approval green-zone.",
        f"read_roots: {roots}",
        f"approval_required_for_actions: {actions}",
        f"receipt_path: {status.get('receipt_path')}",
    ])


if __name__ == "__main__":  # pragma: no cover
    print(json.dumps(ensure_receipt(), indent=2))
