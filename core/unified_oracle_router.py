"""Unified ORACLE intent lanes and route receipts.

The UI presents one ORACLE mode. This module classifies each message into an
internal lane and records local route evidence without moving, deleting,
syncing, uploading, committing, pushing, recording, or calling cloud APIs.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from root_map import RATIFIED_STATE_ROOT
except Exception:  # pragma: no cover - direct execution fallback
    RATIFIED_STATE_ROOT = Path(r"C:\Oracle\state")


STATE_ROOT = Path(RATIFIED_STATE_ROOT)
ROUTING_DIR = STATE_ROOT / "routing"
RECEIPTS_DIR = STATE_ROOT / "receipts"
COMPANION_DIR = STATE_ROOT / "companion"

LANES = {
    "talk_lane": "Talk",
    "build_lane": "Build",
    "capture_lane": "Capture",
    "witness_lane": "Witness",
    "guard_lane": "Guard",
}

SAFETY_SAFE = "Safe"
SAFETY_RECEIPT = "Receipt Written"
SAFETY_APPROVAL = "Approval Required"
SAFETY_BLOCKED = "Blocked"

BUILD_TERMS = (
    "build", "implement", "fix", "patch", "edit", "write file", "update ui",
    "create module", "add module", "run test", "run tests", "pytest", "api route",
    "endpoint", "refactor", "code", "coding", "scaffold", "compile",
)
CAPTURE_TERMS = (
    "capture", "preserve", "receipt", "lootdrop", "mindcoin", "artifact",
    "thread", "source map", "sourcemap", "game artifact", "captain's log",
    "captains log", "memory", "remember this", "store this",
)
WITNESS_TERMS = (
    "obs", "screenshot", "screen shot", "screenshare", "screen share",
    "current window", "watch", "recording", "video", "audio", "camera",
    "transcript", "live video",
)
GUARD_TERMS = (
    "delete", "remove file", "move", "rename", "sync", "commit", "push",
    "upload", "cloud", "cloud api", "drive canonical", "make drive canonical",
    "promote identity", "identity anchor", "reset memory", "clear memory",
    "cleanup", "clean up", "quarantine", "archive old", "raw recording",
)
ACTIVE_CONTEXT_TERMS = (
    "active context sync",
    "refresh context", "pull current context", "pull current updates",
    "update active context", "sync local state", "show context diff",
    "show what changed", "without reset", "do not reset",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _excerpt(text: str, limit: int = 220) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    return cleaned[:limit]


def _contains_any(lower: str, terms: tuple[str, ...]) -> bool:
    return any(term in lower for term in terms)


def classify_intent(user_message: str) -> dict[str, Any]:
    lower = str(user_message or "").strip().lower()
    if not lower:
        lane = "talk_lane"
        reason = "empty message defaults to talk lane"
        confidence = "medium"
    elif _contains_any(lower, ACTIVE_CONTEXT_TERMS):
        lane = "capture_lane"
        reason = "active local context refresh request"
        confidence = "high"
    elif _contains_any(lower, GUARD_TERMS):
        lane = "guard_lane"
        reason = "message contains risky action requiring approval or block"
        confidence = "high"
    elif _contains_any(lower, BUILD_TERMS):
        lane = "build_lane"
        reason = "implementation or tool-backed work request"
        confidence = "high"
    elif _contains_any(lower, CAPTURE_TERMS):
        lane = "capture_lane"
        reason = "artifact, receipt, continuity, or memory capture request"
        confidence = "high"
    elif _contains_any(lower, WITNESS_TERMS):
        lane = "witness_lane"
        reason = "live context, OBS, screen, recording, or transcript request"
        confidence = "medium"
    else:
        lane = "talk_lane"
        reason = "normal conversation or question"
        confidence = "medium"

    requires_approval = lane == "guard_lane"
    if lane == "witness_lane" and any(term in lower for term in ("record", "watch", "audio", "video", "screenshot", "screenshare", "screen share")):
        requires_approval = True

    blocked_actions = [
        "delete",
        "move",
        "rename",
        "sync",
        "commit",
        "push",
        "upload",
        "cloud_api_use",
        "raw_recording",
        "identity_anchor_promotion",
        "drive_canonical_declaration",
    ]
    allowed_by_lane = {
        "talk_lane": ["answer", "reflect", "brainstorm", "draft", "explain"],
        "build_lane": ["prepare_local_task", "execute_explicit_allowed_writes", "run_local_tests", "write_receipts"],
        "capture_lane": ["write_local_artifact", "write_local_receipt", "append_symbolic_ledger", "link_source_metadata"],
        "witness_lane": ["read_metadata_after_consent", "write_metadata_receipt", "report_status"],
        "guard_lane": ["block_risky_action", "request_noah_physical_approval", "write_guard_receipt"],
    }

    safety = SAFETY_SAFE
    if lane != "talk_lane":
        safety = SAFETY_RECEIPT
    if requires_approval:
        safety = SAFETY_APPROVAL
    if lane == "guard_lane":
        safety = SAFETY_BLOCKED

    return {
        "route_id": _id("route"),
        "timestamp": _now(),
        "user_message_excerpt": _excerpt(user_message),
        "detected_lane": lane,
        "lane_label": LANES[lane],
        "confidence": confidence,
        "reason": reason,
        "requires_approval": requires_approval,
        "allowed_actions": allowed_by_lane[lane],
        "blocked_actions": blocked_actions,
        "receipt_required": lane != "talk_lane",
        "human_authority": "Noah.Physical",
        "safety_status": safety,
    }


def write_route(route: dict[str, Any]) -> dict[str, Any]:
    ROUTING_DIR.mkdir(parents=True, exist_ok=True)
    path = ROUTING_DIR / f"unified_oracle_route_{_stamp()}.json"
    payload = dict(route)
    payload.update(
        {
            "ui_mode": "unified_oracle",
            "conversation_reset": False,
            "files_moved": 0,
            "files_deleted": 0,
            "files_renamed": 0,
            "files_synced": 0,
            "cloud_uploads": 0,
            "cloud_api_calls": 0,
            "git_commits": 0,
            "git_pushes": 0,
            "recordings_created": 0,
        }
    )
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    payload["route_path"] = str(path)
    return payload


def write_route_receipt(route: dict[str, Any], *, actions_taken: list[str] | None = None, notes: str = "") -> dict[str, Any]:
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    receipt = {
        "receipt_id": _id("unified_oracle_receipt"),
        "timestamp": _now(),
        "operation": "unified_oracle_route",
        "detected_lane": route.get("detected_lane"),
        "lane_label": route.get("lane_label"),
        "user_message_excerpt": route.get("user_message_excerpt"),
        "actions_taken": list(actions_taken or ["classified_internal_lane"]),
        "files_written": [route.get("route_path")] if route.get("route_path") else [],
        "files_moved": 0,
        "files_deleted": 0,
        "files_renamed": 0,
        "files_synced": 0,
        "git_commits": 0,
        "git_pushes": 0,
        "cloud_uploads": 0,
        "cloud_api_calls": 0,
        "recordings_created": 0,
        "conversation_reset": False,
        "human_authority": "Noah.Physical",
        "approval_required": bool(route.get("requires_approval")),
        "notes": notes,
    }
    path = RECEIPTS_DIR / f"unified_oracle_receipt_{_stamp()}.json"
    path.write_text(json.dumps(receipt, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    receipt["receipt_path"] = str(path)
    return receipt


def route_message(user_message: str, *, write_receipt: bool = True, notes: str = "") -> dict[str, Any]:
    route = write_route(classify_intent(user_message))
    receipt = None
    if write_receipt and route.get("receipt_required"):
        receipt = write_route_receipt(route, notes=notes)
    return {
        "route": route,
        "receipt": receipt,
        "mode": "unified_oracle",
        "conversation_reset": False,
    }


def latest_route_status() -> dict[str, Any]:
    try:
        routes = sorted(ROUTING_DIR.glob("unified_oracle_route_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:
        routes = []
    if not routes:
        route = classify_intent("")
        return {
            "mode": "unified_oracle",
            "current_lane": route["detected_lane"],
            "lane_label": route["lane_label"],
            "safety_status": route["safety_status"],
            "latest_route_path": None,
            "latest_receipt_path": None,
            "conversation_reset": False,
        }
    try:
        route = json.loads(routes[0].read_text(encoding="utf-8"))
    except Exception:
        route = classify_intent("")
    receipt_path = None
    try:
        receipts = sorted(RECEIPTS_DIR.glob("unified_oracle_receipt_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        receipt_path = str(receipts[0]) if receipts else None
    except Exception:
        pass
    return {
        "mode": "unified_oracle",
        "current_lane": route.get("detected_lane", "talk_lane"),
        "lane_label": route.get("lane_label", "Talk"),
        "safety_status": route.get("safety_status", SAFETY_SAFE),
        "latest_route_path": str(routes[0]),
        "latest_receipt_path": receipt_path,
        "conversation_reset": False,
    }


def format_lane_boundary(route: dict[str, Any]) -> str:
    lane = route.get("lane_label") or LANES.get(str(route.get("detected_lane")), "Talk")
    if route.get("detected_lane") == "build_lane":
        return (
            "I routed this to Build lane. I can prepare the task and execute only allowed local changes. "
            "Approval is required before commit, push, delete, move, sync, upload, or identity-anchor promotion."
        )
    if route.get("detected_lane") == "capture_lane":
        return (
            "I routed this to Capture lane. I can write a local artifact and receipt under C:\\Oracle\\state, "
            "without making the source canonical."
        )
    if route.get("detected_lane") == "witness_lane":
        return (
            "I routed this to Witness lane. Metadata can be read only under consent, and raw screen/audio/video "
            "capture remains blocked by default."
        )
    if route.get("detected_lane") == "guard_lane":
        return (
            "I routed this to Guard lane. This action requires Noah.Physical approval because it may be irreversible."
        )
    return f"I routed this to {lane} lane."


if __name__ == "__main__":
    import sys

    message = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
    print(json.dumps(classify_intent(message), indent=2, ensure_ascii=True, sort_keys=True))
