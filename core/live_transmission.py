"""Metadata-only live transmission state for ORACLE.

This module never starts raw recording, screen capture, audio capture,
clipboard capture, keystroke capture, uploads, sync, Drive mutation, OneDrive
mutation, Git mutation, or credential access. It only writes local metadata
state and receipts under the ratified private state root.
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
CONTEXT_DIR = STATE_ROOT / "context"
RECEIPTS_DIR = STATE_ROOT / "receipts"
LIVE_STATE_PATH = CONTEXT_DIR / "live_transmission_latest.json"

LIVE_CAPTURE_RESPONSE = (
    "Live transmission captured. ORACLE is in elevated privacy posture. "
    "I will treat live state as metadata only unless Noah.Physical approves a specific capture."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _safety_flags() -> dict[str, bool]:
    return {
        "conversation_reset": False,
        "cloud_api_used": False,
        "upload": False,
        "sync": False,
        "drive_modified": False,
        "onedrive_modified": False,
        "git_commit": False,
        "git_push": False,
        "recording_started_by_oracle": False,
        "screen_capture_started_by_oracle": False,
        "audio_capture_started_by_oracle": False,
        "clipboard_capture_started_by_oracle": False,
        "keystroke_capture_started_by_oracle": False,
        "credential_touched": False,
    }


def _base_payload(*, active: bool, action: str, notes: str = "") -> dict[str, Any]:
    return {
        "timestamp": _now(),
        "action": action,
        "session_state": "active_live_transmission" if active else "inactive_live_transmission",
        "live_transmission_active": active,
        "noah_physical_present": True,
        "oracle_runtime_active": True,
        "unified_mode_active": True,
        "cognition_fabric_active": True,
        "model_dependency_reduced": True,
        "privacy_posture": "elevated" if active else "normal",
        "recommended_mode": "metadata_only",
        "raw_recording": "off",
        "network_boundary": "local-only",
        "human_authority": "Noah.Physical",
        "notes": notes,
        **_safety_flags(),
    }


def read_live_state(*, state_path: Path | None = None) -> dict[str, Any]:
    path = Path(state_path or LIVE_STATE_PATH)
    if not path.exists():
        return {
            "live_transmission_active": False,
            "session_state": "inactive_live_transmission",
            "privacy_posture": "normal",
            "recommended_mode": "metadata_only",
            "raw_recording": "off",
            "state_path": str(path),
            **_safety_flags(),
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("state_path", str(path))
            return data
    except Exception as exc:
        return {
            "live_transmission_active": False,
            "session_state": "unknown",
            "privacy_posture": "unknown",
            "recommended_mode": "metadata_only",
            "raw_recording": "off",
            "state_path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
            **_safety_flags(),
        }
    return {
        "live_transmission_active": False,
        "session_state": "unknown",
        "privacy_posture": "unknown",
        "recommended_mode": "metadata_only",
        "raw_recording": "off",
        "state_path": str(path),
        **_safety_flags(),
    }


def is_live_active(*, state_path: Path | None = None) -> bool:
    state = read_live_state(state_path=state_path)
    return bool(state.get("live_transmission_active")) or state.get("session_state") == "active_live_transmission"


def write_live_transmission_capture(
    *,
    active: bool = True,
    action: str = "live_transmission_capture",
    notes: str = "",
    state_path: Path | None = None,
    receipts_dir: Path | None = None,
) -> dict[str, Any]:
    target_state = Path(state_path or LIVE_STATE_PATH)
    target_receipts = Path(receipts_dir or RECEIPTS_DIR)
    target_state.parent.mkdir(parents=True, exist_ok=True)
    target_receipts.mkdir(parents=True, exist_ok=True)

    payload = _base_payload(active=active, action=action, notes=notes)
    target_state.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")

    receipt = dict(payload)
    receipt["receipt_id"] = _id("live_transmission_receipt")
    receipt["state_path"] = str(target_state)
    receipt_path = target_receipts / f"live_transmission_receipt_{_stamp()}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    receipt["receipt_path"] = str(receipt_path)

    result = dict(payload)
    result["state_path"] = str(target_state)
    result["receipt_path"] = str(receipt_path)
    result["response_text"] = LIVE_CAPTURE_RESPONSE if active else format_live_status(result)
    return result


def format_live_status(state: dict[str, Any] | None = None) -> str:
    state = state or read_live_state()
    if state.get("live_transmission_active") or state.get("session_state") == "active_live_transmission":
        return (
            "Live transmission active. LIVE PRIVACY ELEVATED. RAW RECORDING OFF. "
            "LOCAL ONLY. Recommended mode: metadata_only."
        )
    return "Live transmission inactive. RAW RECORDING OFF. LOCAL ONLY."


def handle_live_command(command: str, *, notes: str = "") -> dict[str, Any]:
    lower = str(command or "").strip().lower()
    if lower in ("/live status", "live status", "live privacy"):
        state = read_live_state()
        state["response_text"] = format_live_status(state)
        return state
    if lower in ("/live stop", "live stop"):
        return write_live_transmission_capture(
            active=False,
            action="live_transmission_stop",
            notes=notes or "manual live transmission stop",
        )
    return write_live_transmission_capture(
        active=True,
        action="live_transmission_capture",
        notes=notes or "manual live transmission capture",
    )


if __name__ == "__main__":
    print(json.dumps(read_live_state(), indent=2, ensure_ascii=True, sort_keys=True))
