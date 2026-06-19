"""SourceMap Witness Governance doctrine.

This module upgrades Observe.Copy.Store into:

Observe. Link. Receipt. Store by consent. Copy only by Noah.Physical approval.

It is doctrine and local governance support only. It never records screen/audio,
captures keys/clipboard, deletes files, syncs roots, uploads, or copies raw
recordings.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from root_map import RATIFIED_STATE_ROOT
except Exception:  # pragma: no cover - direct execution fallback
    RATIFIED_STATE_ROOT = Path(r"C:\Oracle\state")


STATE_ROOT = Path(RATIFIED_STATE_ROOT)
GOVERNANCE_DIR = STATE_ROOT / "governance"
RECEIPTS_DIR = STATE_ROOT / "receipts"
SOURCES_LATEST = STATE_ROOT / "sources" / "oracle_source_manifest_latest.json"
COMPANION_PROFILE = STATE_ROOT / "companion" / "companion_profile.json"
GOVERNANCE_PATH = GOVERNANCE_DIR / "sourcemap_witness_governance.json"

GOVERNANCE_VERSION = "1.0"
DEFAULT_WATCH_STATE = "watch_off"
DEFAULT_STORAGE_TIER = "do_not_store"
DEFAULT_EVIDENCE_STATE = "DISCOVERED"

GOVERNANCE_STATES = {
    "watch_off",
    "metadata_only",
    "link_only",
    "receipt_only",
    "store_selected",
    "copy_approved",
    "forget_requested",
    "human_review_required",
}

ALLOWED_COMMANDS = {
    "preserve_this",
    "forget_this",
    "show_me_what_you_know",
    "do_not_watch",
    "link_this",
    "write_receipt",
    "promote_to_project_memory",
    "request_identity_anchor_review",
    "metadata_only",
}

STORAGE_TIERS = {
    "do_not_store",
    "link_only",
    "receipt_only",
    "store_summary",
    "store_selected_artifact",
    "store_raw_source_with_approval",
    "archive_copy_with_approval",
}

EVIDENCE_STATES = {
    "DISCOVERED",
    "METADATA_READ",
    "CONTENT_OBSERVED",
    "INTERPRETED",
    "HUMAN_CONFIRMED",
    "FORGET_REQUESTED",
    "REDACTED",
}

FORBIDDEN_BEHAVIORS = [
    "No hidden recording.",
    "No silent copying.",
    "No surprise cloud sync.",
    "No always-on raw memory.",
    "No keylogging.",
    "No clipboard capture without separate consent.",
    "No screenshots by default.",
    "No audio or video recording by default.",
    "No treating discovered file paths as understood content.",
    "No making Drive canonical by accident.",
    "No irreversible actions without Noah.Physical approval.",
]

CONSENT_REQUIRED_FOR = [
    "Preserve raw source",
    "Copy file",
    "Archive file",
    "Promote to identity anchor",
    "Sync to Drive",
    "Delete source",
    "Store raw recordings",
    "Store screenshots",
    "Store audio",
    "Store video",
    "Capture clipboard",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def default_governance() -> dict[str, Any]:
    now = _now()
    return {
        "governance_version": GOVERNANCE_VERSION,
        "created_at": now,
        "human_authority": "Noah.Physical",
        "doctrine_name": "SourceMap Witness Governance",
        "doctrine_statement": (
            "Observe. Link. Receipt. Store by consent. "
            "Copy only by Noah.Physical approval."
        ),
        "default_watch_state": DEFAULT_WATCH_STATE,
        "current_watch_state": DEFAULT_WATCH_STATE,
        "current_storage_tier": DEFAULT_STORAGE_TIER,
        "allowed_commands": sorted(ALLOWED_COMMANDS),
        "governance_states": sorted(GOVERNANCE_STATES),
        "storage_tiers": sorted(STORAGE_TIERS),
        "evidence_states": sorted(EVIDENCE_STATES),
        "observation_policy": {
            "default": "watch_off",
            "metadata_only_requires_explicit_enablement": True,
            "raw_observation_requires_noah_physical_approval": True,
            "allowed_without_explicit_enablement": [],
        },
        "link_policy": {
            "default": "link paths and metadata without duplicating raw source",
            "do_not_treat_path_as_understood_content": True,
        },
        "receipt_policy": {
            "write_when_it_mattered": True,
            "record_what_was_not_touched": True,
            "receipt_before_raw_storage": True,
        },
        "storage_policy": {
            "default_storage_tier": DEFAULT_STORAGE_TIER,
            "do_not_store_raw_by_default": True,
            "approved_tiers": sorted(STORAGE_TIERS),
        },
        "copy_policy": {
            "default": "do_not_copy",
            "copy_requires_noah_physical_approval": True,
        },
        "forget_policy": {
            "forget_this_marks_forget_requested": True,
            "no_deletion_implemented_here": True,
            "human_review_required": True,
        },
        "audit_policy": {
            "receipt_required_for_governance_transitions": True,
            "zero_action_counts_required": True,
        },
        "forbidden_behaviors": FORBIDDEN_BEHAVIORS,
        "consent_required_for": CONSENT_REQUIRED_FOR,
        "last_receipt_path": None,
        "last_updated_at": now,
    }


def load_governance(*, create: bool = True) -> dict[str, Any]:
    data = _read_json(GOVERNANCE_PATH)
    if data is None:
        data = default_governance()
        if create:
            _write_json(GOVERNANCE_PATH, data)
    return data


def save_governance(data: dict[str, Any]) -> dict[str, Any]:
    data["last_updated_at"] = _now()
    _write_json(GOVERNANCE_PATH, data)
    return data


def _receipt_payload(
    *,
    operation: str,
    governance_state: str,
    storage_tier: str,
    source_reference: str = "",
    linked_path: str = "",
    artifact_type: str = "",
    evidence_state: str = DEFAULT_EVIDENCE_STATE,
    why_it_mattered: str = "",
    what_was_observed: str = "None. Governance action only.",
    what_was_linked: str = "",
    what_was_stored: str = "Governance receipt only.",
    what_was_copied: str = "Nothing.",
    notes: str = "",
    approval_required_for_next_step: list[str] | None = None,
) -> dict[str, Any]:
    if governance_state not in GOVERNANCE_STATES:
        raise ValueError(f"invalid governance_state: {governance_state}")
    if storage_tier not in STORAGE_TIERS:
        raise ValueError(f"invalid storage_tier: {storage_tier}")
    if evidence_state not in EVIDENCE_STATES:
        raise ValueError(f"invalid evidence_state: {evidence_state}")
    return {
        "receipt_id": _id("witness_governance_receipt"),
        "timestamp": _now(),
        "operation": operation,
        "governance_state": governance_state,
        "storage_tier": storage_tier,
        "source_reference": source_reference,
        "linked_path": linked_path,
        "artifact_type": artifact_type,
        "evidence_state": evidence_state,
        "human_authority": "Noah.Physical",
        "why_it_mattered": why_it_mattered,
        "what_was_observed": what_was_observed,
        "what_was_linked": what_was_linked,
        "what_was_stored": what_was_stored,
        "what_was_copied": what_was_copied,
        "what_was_not_touched": [
            "raw recordings",
            "screenshots",
            "audio",
            "video",
            "clipboard",
            "keystrokes",
            "source files",
            "Drive canonical status",
        ],
        "files_moved": 0,
        "files_deleted": 0,
        "files_renamed": 0,
        "files_synced": 0,
        "cloud_uploads": 0,
        "git_commits": 0,
        "git_pushes": 0,
        "approval_required_for_next_step": approval_required_for_next_step or [],
        "notes": notes,
    }


def write_receipt(**kwargs: Any) -> dict[str, Any]:
    receipt = _receipt_payload(**kwargs)
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RECEIPTS_DIR / f"witness_governance_receipt_{_stamp()}.json"
    _write_json(path, receipt)
    receipt["receipt_path"] = str(path)
    data = load_governance(create=True)
    data["last_receipt_path"] = str(path)
    save_governance(data)
    return receipt


def _set_watch_off(data: dict[str, Any]) -> None:
    data["current_watch_state"] = "watch_off"
    data["current_storage_tier"] = "do_not_store"
    try:
        from rendered_reality_witness import set_witness_mode

        set_witness_mode("off")
    except Exception:
        pass


def handle_command(
    command: str,
    *,
    source_reference: str = "",
    linked_path: str = "",
    artifact_type: str = "",
    why_it_mattered: str = "",
    notes: str = "",
) -> dict[str, Any]:
    cmd = str(command or "").strip().lower()
    if cmd not in ALLOWED_COMMANDS:
        raise ValueError(f"invalid governance command: {command}")

    data = load_governance(create=True)
    receipt: dict[str, Any] | None = None
    response: dict[str, Any] = {"command": cmd, "action_taken": "none"}

    if cmd == "do_not_watch":
        _set_watch_off(data)
        save_governance(data)
        receipt = write_receipt(
            operation="do_not_watch",
            governance_state="watch_off",
            storage_tier="do_not_store",
            evidence_state="HUMAN_CONFIRMED",
            why_it_mattered=why_it_mattered or "Noah.Physical requested watch_off.",
            notes=notes,
        )
        response["action_taken"] = "watch_off"

    elif cmd == "metadata_only":
        data["current_watch_state"] = "metadata_only"
        data["current_storage_tier"] = "link_only"
        save_governance(data)
        receipt = write_receipt(
            operation="metadata_only_enabled",
            governance_state="metadata_only",
            storage_tier="link_only",
            evidence_state="HUMAN_CONFIRMED",
            what_was_observed="Metadata-only observation may be performed after explicit enablement.",
            what_was_stored="Governance state and receipt only.",
            why_it_mattered=why_it_mattered or "Explicit metadata-only witness consent selected.",
            notes=notes,
        )
        response["action_taken"] = "metadata_only"

    elif cmd == "link_this":
        data["current_watch_state"] = "link_only"
        data["current_storage_tier"] = "link_only"
        save_governance(data)
        receipt = write_receipt(
            operation="link_this",
            governance_state="link_only",
            storage_tier="link_only",
            source_reference=source_reference,
            linked_path=linked_path,
            artifact_type=artifact_type,
            evidence_state="METADATA_READ" if linked_path else "DISCOVERED",
            what_was_linked=linked_path or source_reference,
            what_was_stored="Link/reference metadata and receipt only.",
            why_it_mattered=why_it_mattered,
            notes=notes,
        )
        response["action_taken"] = "linked_reference_only"

    elif cmd == "write_receipt":
        data["current_watch_state"] = "receipt_only"
        data["current_storage_tier"] = "receipt_only"
        save_governance(data)
        receipt = write_receipt(
            operation="write_receipt",
            governance_state="receipt_only",
            storage_tier="receipt_only",
            source_reference=source_reference,
            linked_path=linked_path,
            artifact_type=artifact_type,
            evidence_state="METADATA_READ" if (source_reference or linked_path) else "DISCOVERED",
            what_was_linked=linked_path or source_reference,
            why_it_mattered=why_it_mattered,
            notes=notes,
        )
        response["action_taken"] = "receipt_written"

    elif cmd == "preserve_this":
        data["current_watch_state"] = "human_review_required"
        data["current_storage_tier"] = "receipt_only"
        save_governance(data)
        receipt = write_receipt(
            operation="preserve_this_proposal",
            governance_state="human_review_required",
            storage_tier="receipt_only",
            source_reference=source_reference,
            linked_path=linked_path,
            artifact_type=artifact_type,
            evidence_state="HUMAN_CONFIRMED",
            what_was_linked=linked_path or source_reference,
            what_was_stored="Receipt proposal only; raw source was not stored.",
            why_it_mattered=why_it_mattered or "Preservation requested; raw storage requires approval.",
            approval_required_for_next_step=[
                "store_selected_artifact",
                "store_raw_source_with_approval",
                "archive_copy_with_approval",
            ],
            notes=notes,
        )
        response["action_taken"] = "receipt_proposal_before_storage"

    elif cmd == "forget_this":
        data["current_watch_state"] = "forget_requested"
        data["current_storage_tier"] = "do_not_store"
        save_governance(data)
        receipt = write_receipt(
            operation="forget_this_request",
            governance_state="forget_requested",
            storage_tier="do_not_store",
            source_reference=source_reference,
            linked_path=linked_path,
            artifact_type=artifact_type,
            evidence_state="FORGET_REQUESTED",
            what_was_linked=linked_path or source_reference,
            what_was_stored="Forget request audit receipt only.",
            why_it_mattered=why_it_mattered or "Forget requested; deletion is not implemented in this doctrine layer.",
            approval_required_for_next_step=["human_review_required", "redaction_plan", "audit_stub_review"],
            notes=notes,
        )
        response["action_taken"] = "marked_forget_requested_no_delete"

    elif cmd in {"show_me_what_you_know", "promote_to_project_memory", "request_identity_anchor_review"}:
        if cmd == "show_me_what_you_know":
            response["action_taken"] = "reported_known_references"
            response["known"] = show_me_what_you_know()
        else:
            data["current_watch_state"] = "human_review_required"
            data["current_storage_tier"] = "receipt_only"
            save_governance(data)
            receipt = write_receipt(
                operation=f"{cmd}_proposal",
                governance_state="human_review_required",
                storage_tier="receipt_only",
                source_reference=source_reference,
                linked_path=linked_path,
                artifact_type=artifact_type,
                evidence_state="DISCOVERED",
                what_was_linked=linked_path or source_reference,
                why_it_mattered=why_it_mattered,
                approval_required_for_next_step=[cmd],
                notes=notes,
            )
            response["action_taken"] = "proposal_requires_noah_physical_review"

    if receipt:
        response["receipt"] = receipt
    response["governance"] = load_governance(create=True)
    return response


def show_me_what_you_know() -> dict[str, Any]:
    governance = load_governance(create=True)
    source_manifest = _read_json(SOURCES_LATEST)
    companion_profile = _read_json(COMPANION_PROFILE)
    receipt_paths = []
    if RECEIPTS_DIR.exists():
        receipt_paths = [
            str(path)
            for path in sorted(
                RECEIPTS_DIR.glob("*receipt_*.json"),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )[:20]
        ]
    return {
        "profile_reference": str(COMPANION_PROFILE) if COMPANION_PROFILE.exists() else None,
        "profile_loaded": companion_profile is not None,
        "governance_path": str(GOVERNANCE_PATH),
        "governance_loaded": bool(governance),
        "source_manifest_path": str(SOURCES_LATEST) if SOURCES_LATEST.exists() else None,
        "source_manifest_source_count": (
            source_manifest.get("source_count")
            if isinstance(source_manifest, dict)
            else None
        ),
        "recent_receipts": receipt_paths,
        "uncertainty": (
            "This report lists known local references and metadata only. "
            "Discovered paths are not treated as understood content."
        ),
    }


def status_payload() -> dict[str, Any]:
    governance = load_governance(create=True)
    return {
        "governance": governance,
        "governance_path": str(GOVERNANCE_PATH),
        "last_receipt_path": governance.get("last_receipt_path"),
        "current_watch_state": governance.get("current_watch_state", DEFAULT_WATCH_STATE),
        "current_storage_tier": governance.get("current_storage_tier", DEFAULT_STORAGE_TIER),
        "allowed_to_observe": governance.get("observation_policy", {}),
        "allowed_to_store": governance.get("storage_policy", {}),
        "forbidden_to_capture": FORBIDDEN_BEHAVIORS,
        "consent_status": "explicit consent required for metadata_only and all storage beyond receipts",
        "dangerous_actions_require_confirmation": CONSENT_REQUIRED_FOR,
    }


def initialize_governance_with_receipt() -> dict[str, Any]:
    governance = load_governance(create=True)
    if governance.get("last_receipt_path"):
        return {"governance": governance, "receipt": None}
    receipt = write_receipt(
        operation="governance_initialized",
        governance_state=governance.get("current_watch_state", DEFAULT_WATCH_STATE),
        storage_tier=governance.get("current_storage_tier", DEFAULT_STORAGE_TIER),
        evidence_state="HUMAN_CONFIRMED",
        why_it_mattered="SourceMap Witness Governance doctrine initialized.",
        notes="No files were moved, deleted, copied, synced, uploaded, committed, pushed, recorded, or captured.",
    )
    return {"governance": load_governance(create=True), "receipt": receipt}


if __name__ == "__main__":
    print(json.dumps(status_payload(), indent=2, ensure_ascii=True, sort_keys=True))
