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
PENDING_GUARD_APPROVAL_PATH = ROUTING_DIR / "pending_guard_approval.json"

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
APPROVAL_EFFECTIVE_ROUTE = "guard_approval"
BARE_APPROVAL_PHRASES = {
    "approve",
    "approved",
    "yes approved",
    "noah approves",
    "noah.physical approves",
    "i approve",
    "approved proceed",
    "go ahead",
    "do it",
}
APPROVE_ROUTE_RE = re.compile(r"^\s*approve\s+route\s+(?P<route_id>route_[a-f0-9]{12})(?:\s*:\s*(?P<scope>.+))?\s*$", re.IGNORECASE)
ROUTE_RECEIPT_RE = re.compile(r"\broute_[a-f0-9]{12}\b", re.IGNORECASE)

BUILD_TERMS = (
    "build", "implement", "fix", "patch", "edit", "write file", "update ui",
    "create module", "add module", "run test", "run tests", "pytest", "api route",
    "endpoint", "refactor", "code", "coding", "scaffold", "compile",
)
FORCE_TALK_PREFIX = "/talk"
FORCE_LEARN_PREFIX = "/learn"
BUILD_DIRECTIVE_MARKERS = (
    "backend_patch_request",
    "self_patch_staging_request",
    "thread_pass",
    ".ai build pass",
    ".ai:thread_pass",
)
QUESTION_OR_TALK_TERMS = (
    "?", "what is", "what are", "who is", "who are", "why", "how does",
    "how do", "can you talk", "talk to me", "speak to me", "explain",
    "in your own words", "tell me about", "tell me what", "recall",
    "remember when", "what do you remember", "memory question",
)
LIVE_CAPTURE_TERMS = (
    "capture current live transmission state",
    "live transmission receipt",
    "live_transmission_latest.json",
    "live_transmission_receipt",
    "live transmission state",
    "metadata only",
    "i'm transmitting right now",
    "i’m transmitting right now",
    "i am transmitting right now",
    "i'm live",
    "i’m live",
    "i am live",
    "live mode",
    "live privacy",
    "live status",
    "/live",
    "/live start",
    "/live status",
    "/live stop",
)
CAPTURE_TERMS = (
    "capture", "preserve", "receipt", "lootdrop", "mindcoin", "artifact",
    "thread", "source map", "sourcemap", "game artifact", "captain's log",
    "captains log", "memory", "remember this", "store this", "session capture",
    "metadata capsule", "context capsule", "capture this moment",
    "make this a receipt", "write a receipt", "local receipt",
    "save this as a lootdrop", "game continuity artifact",
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
    "onedrive", "one drive", "gmail", "credentials", "credential", "secret",
    "password", "token", "screen capture", "audio capture", "clipboard",
    "keystroke", "record video", "record audio", "restart server",
    "restart the server", "restart oracle", "restart backend",
    "restart runtime", "send ", "send to", "publish", "promote canon",
    "external call", "call external", "computer control", "control the computer",
)
ACTIVE_CONTEXT_TERMS = (
    "active context sync",
    "refresh context", "pull current context", "pull current updates",
    "update active context", "sync local state", "show context diff",
    "show what changed", "without reset", "do not reset",
)
ACTIVE_CONTEXT_BLOCKING_TERMS = (
    "delete", "remove file", "move", "rename", "commit", "push", "upload",
    "cloud", "cloud api", "drive canonical", "make drive canonical",
    "promote identity", "identity anchor", "reset memory", "clear memory",
    "cleanup", "clean up", "quarantine", "archive old", "raw recording",
    "onedrive", "one drive", "gmail", "credentials", "credential", "secret",
    "password", "token", "screen capture", "audio capture", "clipboard",
    "keystroke", "record video", "record audio",
)
LIVE_STRICT_GUARD_TERMS = (
    "commit", "push", "delete", "move", "rename", "drive", "onedrive",
    "one drive", "gmail", "credential", "credentials", "secret", "password",
    "screen capture", "audio capture", "clipboard", "upload", "sync",
    "cloud", "raw recording", "record video", "record audio", "keystroke",
)
EXISTING_APPROVAL_STATUS_MARKERS = (
    "routing loop fix",
    "already recorded noah.physical approval",
    "use the existing approval receipt",
    "existing approval receipt",
    "do not route this back to guard",
    "do not ask for approval again",
)
EXISTING_APPROVAL_STATUS_FIELDS = (
    "approval_receipt_used:",
    "handler_exists:",
    "handler_name:",
    "can_execute_locally:",
    "if_not_executable_reason:",
    "next_command_for_noah:",
)
DIAGNOSTIC_STATUS_MARKERS = (
    "diagnostic only",
    "smoke test receipt only",
    "report only",
    "status only",
    "do not execute",
    "do not touch external systems",
    "do not ask for approval",
)
DIAGNOSTIC_STATUS_TERMS = (
    "report",
    "inspect",
    "diagnose",
    "diagnostic",
    "status",
    "summarize",
    "summary",
    "current state",
    "receipt only",
    "smoke test",
    "whether",
    "was restarted",
)
DIAGNOSTIC_NEGATED_ACTION_RE = re.compile(
    r"\b(?:do\s+not|don't|no)\s+"
    r"(?:execute|touch|ask|restart|write|mutate|patch|commit|push|send|publish|delete|promote|upload|call|control|external)\b"
    r"[^.\n;]*",
    re.IGNORECASE,
)
DIAGNOSTIC_ACTION_PATTERNS = (
    re.compile(r"\brestart(?:\s+the)?\s+(?:server|oracle|backend|runtime)\b", re.IGNORECASE),
    re.compile(r"\bwrite(?:\s+|$)", re.IGNORECASE),
    re.compile(r"\bmutate\b", re.IGNORECASE),
    re.compile(r"\bpatch\b", re.IGNORECASE),
    re.compile(r"\bcommit\b", re.IGNORECASE),
    re.compile(r"\bpush\b", re.IGNORECASE),
    re.compile(r"\bsend\b", re.IGNORECASE),
    re.compile(r"\bpublish\b", re.IGNORECASE),
    re.compile(r"\bdelete\b", re.IGNORECASE),
    re.compile(r"\bpromote(?:\s+\w+){0,3}\s+canon\b", re.IGNORECASE),
    re.compile(r"\bupload\b", re.IGNORECASE),
    re.compile(r"\bexternal\s+call\b|\bcall\s+external\b", re.IGNORECASE),
    re.compile(r"\bcomputer\s+control\b|\bcontrol\s+(?:the\s+)?computer\b", re.IGNORECASE),
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


def _strip_command_prefix(lower: str, prefix: str) -> str:
    if lower == prefix:
        return ""
    if lower.startswith(prefix + " "):
        return lower[len(prefix):].strip()
    return lower


def _starts_with_build_directive_marker(lower: str) -> bool:
    stripped = lower.lstrip()
    return any(stripped.startswith(marker) for marker in BUILD_DIRECTIVE_MARKERS)


def approval_receipt_ids(text: str) -> list[str]:
    """Return route receipt ids mentioned in text, preserving first-seen order."""
    seen: set[str] = set()
    ids: list[str] = []
    for match in ROUTE_RECEIPT_RE.finditer(str(text or "")):
        receipt_id = match.group(0).lower()
        if receipt_id not in seen:
            seen.add(receipt_id)
            ids.append(receipt_id)
    return ids


def is_existing_approval_receipt_status_request(user_message: str) -> bool:
    """Detect requests to use already-recorded approval receipts.

    These prompts often include risky words in a negative boundary list
    ("do not touch GitHub/Drive/Gmail"). They are status/handler questions,
    not new Guard approval requests.
    """
    lower = str(user_message or "").strip().lower()
    if not lower:
        return False
    has_receipt_id = ROUTE_RECEIPT_RE.search(lower) is not None
    has_existing_marker = _contains_any(lower, EXISTING_APPROVAL_STATUS_MARKERS)
    has_status_field = _contains_any(lower, EXISTING_APPROVAL_STATUS_FIELDS)
    asks_handler_status = any(
        phrase in lower
        for phrase in (
            "handler exists",
            "handler_exists",
            "executable local handler",
            "can_execute_locally",
            "if_not_executable_reason",
        )
    )
    return bool(
        (has_receipt_id or has_existing_marker)
        and (has_status_field or asks_handler_status)
        and (
            "approval" in lower
            or "do not route this back to guard" in lower
            or "do not ask for approval again" in lower
        )
    )


def _diagnostic_action_surface(lower: str) -> str:
    return DIAGNOSTIC_NEGATED_ACTION_RE.sub(" ", lower)


def _contains_unnegated_diagnostic_action(lower: str) -> bool:
    surface = _diagnostic_action_surface(lower)
    return any(pattern.search(surface) for pattern in DIAGNOSTIC_ACTION_PATTERNS)


def is_diagnostic_status_request(user_message: str) -> bool:
    """Detect read-only report/status prompts before risky-word Guard matching."""
    lower = str(user_message or "").strip().lower()
    if not lower:
        return False
    if _contains_unnegated_diagnostic_action(lower):
        return False
    has_marker = _contains_any(lower, DIAGNOSTIC_STATUS_MARKERS)
    asks_status = _contains_any(lower, DIAGNOSTIC_STATUS_TERMS)
    read_only_restart_report = (
        "report whether" in lower
        and ("server was restarted" in lower or "was restarted" in lower)
    )
    return bool((has_marker and asks_status) or read_only_restart_report)


def _question_or_talk_request(user_message: str) -> bool:
    lower = str(user_message or "").strip().lower()
    if not lower:
        return False
    return _contains_any(lower, QUESTION_OR_TALK_TERMS)


def _read_only_synthesis(user_message: str) -> bool:
    """Doctrine / identity / memory-domain question (or explicit synthesis
    request) with NO action requested -> keep in Talk, not Guard/Build."""
    try:
        from talk_synthesis import should_stay_talk
        return should_stay_talk(user_message)
    except Exception:
        return False


def _live_transmission_active() -> bool:
    try:
        from live_transmission import is_live_active

        return bool(is_live_active())
    except Exception:
        return False


def classify_intent(user_message: str) -> dict[str, Any]:
    lower = str(user_message or "").strip().lower()
    route_type = "unified_intent"
    action_type = "conversation"
    if not lower:
        lane = "talk_lane"
        reason = "empty message defaults to talk lane"
        confidence = "medium"
    elif lower == FORCE_TALK_PREFIX or lower.startswith(FORCE_TALK_PREFIX + " "):
        lane = "talk_lane"
        reason = "forced_talk: /talk prefix"
        confidence = "high"
    elif lower == FORCE_LEARN_PREFIX or lower.startswith(FORCE_LEARN_PREFIX + " "):
        lane = "build_lane"
        reason = "forced_learn_build: /learn prefix"
        confidence = "high"
    elif is_existing_approval_receipt_status_request(user_message):
        lane = "talk_lane"
        reason = "existing_approval_receipt_status: report bound approval/handler status without re-entering Guard"
        confidence = "high"
        action_type = "read_only_status"
    elif is_diagnostic_status_request(user_message):
        lane = "talk_lane"
        reason = "diagnostic_status: read-only report/status prompt, no execution requested"
        confidence = "high"
        route_type = "diagnostic_status"
        action_type = "read_only_status"
    elif _starts_with_build_directive_marker(lower):
        lane = "build_lane"
        reason = "explicit build directive marker"
        confidence = "high"
        action_type = "build_directive"
    elif _read_only_synthesis(user_message):
        lane = "talk_lane"
        reason = "read_only_synthesis: doctrine/identity/memory-domain question, no action requested"
        confidence = "high"
        action_type = "read_only_synthesis"
    elif _question_or_talk_request(user_message):
        lane = "talk_lane"
        reason = "talk_question_or_explanation: question/speak/recall/explain request"
        confidence = "high"
        action_type = "answer"
    elif _contains_any(lower, ACTIVE_CONTEXT_TERMS) and not _contains_any(lower, ACTIVE_CONTEXT_BLOCKING_TERMS):
        lane = "capture_lane"
        reason = "active local context refresh request"
        confidence = "high"
        action_type = "local_context_refresh"
    elif _contains_any(lower, GUARD_TERMS) or (
        _live_transmission_active() and _contains_any(lower, LIVE_STRICT_GUARD_TERMS)
    ):
        lane = "guard_lane"
        reason = "message contains risky action requiring approval or block"
        confidence = "high"
        action_type = "guarded_action"
    elif _contains_any(lower, LIVE_CAPTURE_TERMS):
        lane = "capture_lane"
        reason = "live transmission metadata capture or status request"
        confidence = "high"
        action_type = "local_capture"
    elif _contains_any(lower, BUILD_TERMS) and _contains_any(lower, ("source map", "sourcemap")):
        lane = "build_lane"
        reason = "implementation request for SourceMap tooling"
        confidence = "high"
        action_type = "build_request"
    elif _contains_any(lower, CAPTURE_TERMS):
        lane = "capture_lane"
        reason = "artifact, receipt, continuity, or memory capture request"
        confidence = "high"
        action_type = "local_capture"
    elif _contains_any(lower, BUILD_TERMS):
        lane = "build_lane"
        reason = "implementation or tool-backed work request"
        confidence = "high"
        action_type = "build_request"
    elif _contains_any(lower, WITNESS_TERMS):
        lane = "witness_lane"
        reason = "live context, OBS, screen, recording, or transcript request"
        confidence = "medium"
        action_type = "witness_request"
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
        "route_type": route_type,
        "action_type": action_type,
        "detected_lane": lane,
        "lane_label": LANES[lane],
        "confidence": confidence,
        "reason": reason,
        "requires_approval": requires_approval,
        "approval_required": requires_approval,
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
            "preferences_applied": list(route.get("preferences_applied") or []),
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
        "route_type": route.get("route_type"),
        "action_type": route.get("action_type"),
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
        "preferences_applied": list(route.get("preferences_applied") or []),
        "human_authority": "Noah.Physical",
        "approval_required": bool(route.get("requires_approval")),
        "notes": notes,
    }
    path = RECEIPTS_DIR / f"unified_oracle_receipt_{_stamp()}.json"
    path.write_text(json.dumps(receipt, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    receipt["receipt_path"] = str(path)
    return receipt


def _approval_text_key(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower()).strip(" .!?:;")


def is_approval_followup(text: str) -> bool:
    cleaned = _approval_text_key(text)
    return cleaned in BARE_APPROVAL_PHRASES or APPROVE_ROUTE_RE.match(str(text or "")) is not None


def write_pending_guard_approval(route: dict[str, Any]) -> dict[str, Any]:
    """Persist the latest Guard lane route as pending approval context."""
    ROUTING_DIR.mkdir(parents=True, exist_ok=True)
    route_id = route.get("route_id")
    action_summary = (route.get("user_message_excerpt") or "guarded action").strip()
    if len(action_summary) > 140:
        action_summary = action_summary[:139].rstrip() + "…"
    boundary = "irreversible/external action — Noah.Physical approval required; no auto-execution"
    # Real, copy-paste-ready approval line. Never the literal placeholder.
    required_confirmation = f"APPROVE ROUTE {route_id}: {action_summary}; boundary={boundary}"
    pending = {
        "pending_id": _id("guard_pending"),
        "status": "pending_exact_scope",
        "created_at": _now(),
        "route_id": route_id,
        "route_path": route.get("route_path"),
        "lane": route.get("detected_lane"),
        "lane_label": route.get("lane_label"),
        "user_message_excerpt": route.get("user_message_excerpt"),
        "action_summary": action_summary,
        "boundary": boundary,
        "requires_approval": True,
        "executable_bound": True,
        "explicit_scope_required": False,
        "required_confirmation": required_confirmation,
        "human_authority": "Noah.Physical",
    }
    PENDING_GUARD_APPROVAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    PENDING_GUARD_APPROVAL_PATH.write_text(
        json.dumps(pending, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    pending["pending_path"] = str(PENDING_GUARD_APPROVAL_PATH)
    return pending


def load_pending_guard_approval() -> dict[str, Any] | None:
    try:
        pending = json.loads(PENDING_GUARD_APPROVAL_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(pending, dict) and pending.get("status") == "pending_exact_scope":
        pending["pending_path"] = str(PENDING_GUARD_APPROVAL_PATH)
        return pending
    return None


def clear_pending_guard_approval() -> None:
    try:
        PENDING_GUARD_APPROVAL_PATH.unlink()
    except FileNotFoundError:
        pass
    except Exception:
        pass


def write_approval_attempt_receipt(result: dict[str, Any]) -> dict[str, Any]:
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    receipt = {
        "receipt_id": _id("hard_approval_receipt"),
        "timestamp": _now(),
        "operation": "hard_approval_gate",
        "handled": bool(result.get("handled")),
        "approved": bool(result.get("approved")),
        "status": result.get("status"),
        "route_id": (result.get("pending") or {}).get("route_id") or result.get("route_id"),
        "scope_text": result.get("scope_text") or "",
        "executable_bound": False,
        "actions_executed": 0,
        "files_moved": 0,
        "files_deleted": 0,
        "files_renamed": 0,
        "files_synced": 0,
        "git_commits": 0,
        "git_pushes": 0,
        "cloud_uploads": 0,
        "cloud_api_calls": 0,
        "human_authority": "Noah.Physical",
    }
    path = RECEIPTS_DIR / f"hard_approval_receipt_{_stamp()}.json"
    path.write_text(json.dumps(receipt, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    receipt["receipt_path"] = str(path)
    return receipt


def handle_guard_approval_followup(text: str, *, write_receipt: bool = True) -> dict[str, Any]:
    """Handle approval phrases without ever executing from vague approval text."""
    raw = str(text or "")
    if not is_approval_followup(raw):
        return {"handled": False, "effective_route": APPROVAL_EFFECTIVE_ROUTE}

    pending = load_pending_guard_approval()
    result: dict[str, Any] = {
        "handled": True,
        "approved": False,
        "effective_route": APPROVAL_EFFECTIVE_ROUTE,
        "pending": pending,
        "route_id": None,
        "scope_text": "",
    }

    if not pending:
        result.update({
            "status": "no_pending_guard_route",
            "response_text": (
                "Approval received, but no pending executable Guard action is bound. "
                "Restate the exact target, action, and boundary."
            ),
        })
    else:
        route_id = str(pending.get("route_id") or "")
        match = APPROVE_ROUTE_RE.match(raw)
        if not match:
            # Exactly one pending Guard route is tracked at a time, so a bare
            # approval phrase unambiguously approves it (binds to its summary).
            scope_text = str(pending.get("action_summary") or pending.get("user_message_excerpt") or "approved action").strip()
            clear_pending_guard_approval()
            result.update({
                "approved": True,
                "route_id": route_id,
                "scope_text": scope_text,
                "status": "approved_single_pending_route",
                "response_text": (
                    f"Approval recorded for Guard route `{route_id}`.\n"
                    f"Bound action: {scope_text}\n"
                    f"Boundary: {pending.get('boundary', 'Noah.Physical approval; no auto-execution')}\n\n"
                    "Approval is bound. Reversible local work proceeds through its guarded handler; "
                    "irreversible/external steps still execute only via their explicit handlers."
                ),
            })
        else:
            requested_route_id = match.group("route_id")
            scope_text = (match.group("scope") or "").strip()
            result["route_id"] = requested_route_id
            result["scope_text"] = scope_text
            if requested_route_id != route_id:
                result.update({
                    "status": "route_id_mismatch",
                    "response_text": (
                        f"Approval blocked: route `{requested_route_id}` does not match pending route `{route_id}`."
                    ),
                })
            elif not scope_text:
                result.update({
                    "status": "missing_exact_scope",
                    "response_text": (
                        f"Approval blocked for `{route_id}`: missing exact target/action/boundary after the colon."
                    ),
                })
            else:
                clear_pending_guard_approval()
                result.update({
                    "approved": True,
                    "status": "approved_scope_recorded_no_execution",
                    "response_text": (
                        f"Approval recorded for Guard route `{route_id}` with scope: {scope_text}\n\n"
                        "No action executed from approval alone. Resubmit the scoped request to run through its guarded handler."
                    ),
                })

    if write_receipt:
        result["receipt"] = write_approval_attempt_receipt(result)
    return result


def route_message(
    user_message: str,
    *,
    write_receipt: bool = True,
    notes: str = "",
    preferences_applied: list[str] | None = None,
) -> dict[str, Any]:
    route = classify_intent(user_message)
    route["preferences_applied"] = list(preferences_applied or [])
    route = write_route(route)
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
