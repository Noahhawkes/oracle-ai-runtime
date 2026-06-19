"""Model-agnostic cognition fabric for ORACLE.

ORACLE identity and state should remain online when a model is slow, missing,
or swapped. This module provides deterministic runtime/retrieval fallbacks plus
an injectable local-model runner. It does not call cloud APIs, read credentials,
upload, sync, commit, push, move, rename, or delete files.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from root_map import RATIFIED_RUNTIME_ROOT, RATIFIED_STATE_ROOT
except Exception:  # pragma: no cover - direct execution fallback
    RATIFIED_RUNTIME_ROOT = Path(r"C:\Oracle\ORACLE.AI-runtime")
    RATIFIED_STATE_ROOT = Path(r"C:\Oracle\state")


STATE_ROOT = Path(RATIFIED_STATE_ROOT)
RUNTIME_ROOT = Path(RATIFIED_RUNTIME_ROOT)
RECEIPTS_DIR = STATE_ROOT / "receipts"

TIER_RUNTIME_STATUS = "tier_0_runtime_status"
TIER_RETRIEVAL_STATUS = "tier_1_retrieval_status"
TIER_SMALL_LOCAL = "tier_2_small_local_model"
TIER_LARGE_LOCAL = "tier_3_large_local_model"
TIER_EXTERNAL_DISABLED = "tier_4_external_model_disabled"
TIER_PENDING_ACTION = "tier_5_pending_action"

MODEL_FAILURE_MARKERS = (
    "local model response exceeded",
    "local model is currently processing another request",
    "local model is unreachable",
    "local model returned an empty response",
    "local model errored before producing an answer",
    "no model answer was received",
    "cognition is unavailable",
    "no verified local model",
    "offline_no_model",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _safe_boot_status(boot_provider: Callable[[], dict[str, Any]] | None = None) -> dict[str, Any]:
    if boot_provider is not None:
        try:
            value = boot_provider()
            return value if isinstance(value, dict) else {}
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}
    try:
        from boot_receipt import boot_status_payload

        value = boot_status_payload()
        return value if isinstance(value, dict) else {}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _safe_active_context(context_provider: Callable[[], dict[str, Any]] | None = None) -> dict[str, Any]:
    if context_provider is not None:
        try:
            value = context_provider()
            return value if isinstance(value, dict) else {}
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}
    try:
        from active_context_sync import status_payload

        value = status_payload()
        return value if isinstance(value, dict) else {}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _safe_route(route: dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(route, dict):
        return route
    return {
        "detected_lane": "talk_lane",
        "lane_label": "Talk",
        "requires_approval": False,
        "safety_status": "Safe",
    }


def _status_label(status: dict[str, Any]) -> str:
    if not status.get("runtime_ready"):
        return "runtime_unavailable"
    if status.get("last_fallback_reason"):
        reason = str(status.get("last_fallback_reason") or "").lower()
        if "timeout" in reason:
            return "local_timeout"
        if "unavailable" in reason or "missing" in reason:
            return "local_unavailable"
        return "runtime_ready"
    if status.get("local_ready"):
        return "local_ready"
    if status.get("retrieval_ready"):
        return "retrieval_ready"
    return "runtime_ready"


def health_check_engines(
    *,
    boot_provider: Callable[[], dict[str, Any]] | None = None,
    context_provider: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    boot = _safe_boot_status(boot_provider)
    context = _safe_active_context(context_provider)
    latest = context.get("latest") or {}
    source_count = int((latest or {}).get("source_count") or 0)
    latest_receipts = (latest or {}).get("latest_receipts") or []
    cognition_mode = boot.get("cognition_mode") or ((boot.get("receipt") or {}).get("cognition") or {}).get("mode")
    local_ready = cognition_mode == "local_only"
    status = {
        "runtime_ready": not bool(boot.get("error")),
        "retrieval_ready": bool(context.get("loaded")) or source_count > 0 or bool(latest_receipts),
        "local_ready": local_ready,
        "local_loading": False,
        "local_timeout": False,
        "local_unavailable": not local_ready,
        "external_disabled": True,
        "pending_action": False,
        "boot": {
            "cognition_mode": cognition_mode,
            "verified_model_name": boot.get("verified_model_name"),
            "verified_local_engine": boot.get("verified_local_engine"),
            "network_boundary": boot.get("network_boundary"),
            "boot_receipt_path": boot.get("boot_receipt_path"),
        },
        "active_context": {
            "loaded": bool(context.get("loaded")),
            "latest_context_path": context.get("latest_context_path"),
            "last_refresh_time": context.get("last_refresh_time"),
            "source_count": source_count,
            "receipt_count": len(latest_receipts),
            "lootdrop_count": len((latest or {}).get("latest_lootdrops") or []),
            "mindcoin_event_count": len((latest or {}).get("latest_mindcoin_events") or []),
            "routing_state": (latest or {}).get("routing_state") or {},
        },
        "cloud_api_used": False,
        "cloud_apis_enabled": False,
        "external_models_require_approval": True,
        "conversation_reset": False,
        "tiers": [
            {"tier": TIER_RUNTIME_STATUS, "available": True, "engine": "template_runtime"},
            {"tier": TIER_RETRIEVAL_STATUS, "available": True, "engine": "template_retrieval"},
            {"tier": TIER_SMALL_LOCAL, "available": local_ready, "engine": boot.get("verified_local_engine") or "local_model"},
            {"tier": TIER_LARGE_LOCAL, "available": False, "engine": "not_configured"},
            {"tier": TIER_EXTERNAL_DISABLED, "available": False, "engine": "disabled_requires_approval"},
            {"tier": TIER_PENDING_ACTION, "available": True, "engine": "local_pending_action"},
        ],
        "last_local_model_status": "ready" if local_ready else "unavailable",
        "last_timeout": None,
        "last_fallback_reason": None,
    }
    status["status_label"] = _status_label(status)
    return status


def get_cognition_status(
    *,
    boot_provider: Callable[[], dict[str, Any]] | None = None,
    context_provider: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    status = health_check_engines(boot_provider=boot_provider, context_provider=context_provider)
    current_tier = TIER_RUNTIME_STATUS
    if status["local_ready"]:
        current_tier = TIER_SMALL_LOCAL
    elif status["retrieval_ready"]:
        current_tier = TIER_RETRIEVAL_STATUS
    return {
        "current_cognition_tier": current_tier,
        "available_tiers": status["tiers"],
        "configured_local_engines": [
            tier for tier in status["tiers"] if tier["tier"] in {TIER_SMALL_LOCAL, TIER_LARGE_LOCAL}
        ],
        "last_local_model_status": status["last_local_model_status"],
        "last_timeout": status["last_timeout"],
        "last_fallback_reason": status["last_fallback_reason"],
        "cloud_apis_enabled": False,
        "external_models_require_approval": True,
        "cloud_api_used": False,
        "conversation_reset": False,
        "fabric_status": status,
        "status_label": status["status_label"],
    }


def _runtime_question(message: str) -> bool:
    lower = message.lower()
    return any(
        term in lower
        for term in (
            "are you there",
            "are you awake",
            "current mode",
            "safety state",
            "current session",
            "what can you do",
            "what is loaded",
            "what's loaded",
            "cognition",
        )
    )


def _retrieval_question(message: str) -> bool:
    lower = message.lower()
    return any(
        term in lower
        for term in (
            "what changed",
            "changed tonight",
            "files loaded",
            "receipts",
            "last lootdrop",
            "lootdrop",
            "sourcemap count",
            "source map count",
            "source count",
            "active context",
        )
    )


def select_cognition_tier(
    message: str,
    route: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    *,
    retrieval_only: bool = False,
    retry_local: bool = False,
    force_tier: str | None = None,
) -> str:
    if force_tier:
        return force_tier
    route = _safe_route(route)
    lane = route.get("detected_lane")
    if lane == "guard_lane":
        return TIER_RUNTIME_STATUS
    if lane == "build_lane":
        return TIER_PENDING_ACTION
    if retrieval_only:
        return TIER_RETRIEVAL_STATUS
    if retry_local:
        return TIER_SMALL_LOCAL
    if _runtime_question(message):
        return TIER_RUNTIME_STATUS
    if _retrieval_question(message):
        return TIER_RETRIEVAL_STATUS
    status = (context or {}).get("fabric_status") or {}
    if status.get("local_ready"):
        return TIER_SMALL_LOCAL
    if status.get("retrieval_ready"):
        return TIER_RETRIEVAL_STATUS
    return TIER_RUNTIME_STATUS


def _result(
    *,
    tier: str,
    engine_name: str,
    engine_status: str,
    used_model: str | None,
    response_text: str,
    fallback_used: bool = False,
    fallback_reason: str = "",
    latency_ms: int = 0,
) -> dict[str, Any]:
    return {
        "cognition_tier": tier,
        "engine_name": engine_name,
        "engine_status": engine_status,
        "used_model": used_model,
        "response_text": response_text,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "latency_ms": latency_ms,
        "cloud_api_used": False,
        "conversation_reset": False,
    }


def runtime_status_response(status: dict[str, Any] | None = None) -> str:
    status = status or health_check_engines()
    boot = status.get("boot") or {}
    route = (status.get("active_context") or {}).get("routing_state") or {}
    return (
        "ORACLE awake. Runtime, routing, receipts, and safety boundaries are online. "
        f"Cognition status is {status.get('status_label', 'runtime_ready')}. "
        f"Current lane is {route.get('lane_label') or 'Talk'}. "
        f"Network boundary is {boot.get('network_boundary') or 'local-only'}. "
        "Conversation reset remains false."
    )


def retrieval_status_response(status: dict[str, Any] | None = None) -> str:
    status = status or health_check_engines()
    active = status.get("active_context") or {}
    return (
        "ORACLE retrieval fabric online. "
        f"SourceMap count: {active.get('source_count', 0)}. "
        f"Receipts loaded: {active.get('receipt_count', 0)}. "
        f"LootDrops loaded: {active.get('lootdrop_count', 0)}. "
        f"MindCoin events loaded: {active.get('mindcoin_event_count', 0)}. "
        f"Latest context: {active.get('latest_context_path') or 'unavailable'}. "
        "Conversation reset remains false."
    )


def pending_action_response(message: str, route: dict[str, Any] | None = None) -> str:
    route = _safe_route(route)
    lane = route.get("lane_label") or "Build"
    return (
        f"I routed this to {lane} lane and staged it as a pending action boundary. "
        "This web path will not pretend to execute tool-backed work. Codex, Claude Code, "
        "or Noah.Physical can take the task under explicit local-write rules and receipts. "
        "No commit, push, upload, sync, delete, move, rename, or cloud API call occurred."
    )


def fallback_response(
    message: str,
    route: dict[str, Any] | None,
    context: dict[str, Any] | None,
    *,
    reason: str,
) -> dict[str, Any]:
    status = (context or {}).get("fabric_status") or health_check_engines()
    status = dict(status)
    status["last_fallback_reason"] = reason
    if "timeout" in reason.lower():
        status["local_timeout"] = True
        status["status_label"] = "local_timeout"
    else:
        status["status_label"] = _status_label(status)
    active = status.get("active_context") or {}
    text = (
        "ORACLE awake. I am responding from verified local runtime state because "
        f"{reason}. Runtime is online, SourceMap is "
        f"{'available' if active.get('source_count', 0) else 'not fully loaded'}, "
        "and conversation reset remains false."
    )
    return _result(
        tier=TIER_RUNTIME_STATUS if not active.get("source_count") else TIER_RETRIEVAL_STATUS,
        engine_name="cognition_fabric_fallback",
        engine_status=status.get("status_label", "runtime_ready"),
        used_model=None,
        response_text=text,
        fallback_used=True,
        fallback_reason=reason,
    )


def is_model_failure_text(text: str) -> bool:
    lower = str(text or "").lower()
    return any(marker in lower for marker in MODEL_FAILURE_MARKERS)


def run_cognition(
    message: str,
    route: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    *,
    local_model_runner: Callable[[str], str] | None = None,
    boot_provider: Callable[[], dict[str, Any]] | None = None,
    context_provider: Callable[[], dict[str, Any]] | None = None,
    retrieval_only: bool = False,
    retry_local: bool = False,
    force_tier: str | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    status = get_cognition_status(boot_provider=boot_provider, context_provider=context_provider)
    context = dict(context or {})
    context["fabric_status"] = status.get("fabric_status") or {}
    route = _safe_route(route)
    tier = select_cognition_tier(
        message,
        route,
        context,
        retrieval_only=retrieval_only,
        retry_local=retry_local,
        force_tier=force_tier,
    )

    if tier == TIER_RUNTIME_STATUS:
        return _result(
            tier=tier,
            engine_name="template_runtime",
            engine_status="runtime_ready",
            used_model=None,
            response_text=runtime_status_response(context["fabric_status"]),
            latency_ms=int((time.monotonic() - started) * 1000),
        )
    if tier == TIER_RETRIEVAL_STATUS:
        return _result(
            tier=tier,
            engine_name="template_retrieval",
            engine_status="retrieval_ready",
            used_model=None,
            response_text=retrieval_status_response(context["fabric_status"]),
            latency_ms=int((time.monotonic() - started) * 1000),
        )
    if tier == TIER_PENDING_ACTION:
        return _result(
            tier=tier,
            engine_name="local_pending_action",
            engine_status="pending_action",
            used_model=None,
            response_text=pending_action_response(message, route),
            latency_ms=int((time.monotonic() - started) * 1000),
        )
    if tier == TIER_EXTERNAL_DISABLED:
        return fallback_response(message, route, context, reason="external model tier is disabled without Noah.Physical approval")

    if tier in {TIER_SMALL_LOCAL, TIER_LARGE_LOCAL}:
        if local_model_runner is None:
            return fallback_response(message, route, context, reason="local model runner unavailable")
        try:
            text = local_model_runner(message)
        except TimeoutError:
            return fallback_response(message, route, context, reason="the local model did not answer before timeout")
        except Exception as exc:
            return fallback_response(message, route, context, reason=f"the local model failed: {type(exc).__name__}: {exc}")
        if not str(text or "").strip():
            return fallback_response(message, route, context, reason="the local model returned an empty response")
        if is_model_failure_text(text):
            return fallback_response(message, route, context, reason="the local model did not answer before timeout")
        return _result(
            tier=tier,
            engine_name="local_model_runner",
            engine_status="local_ready",
            used_model=(context["fabric_status"].get("boot") or {}).get("verified_model_name"),
            response_text=str(text).strip(),
            latency_ms=int((time.monotonic() - started) * 1000),
        )

    return fallback_response(message, route, context, reason=f"unsupported cognition tier {tier}")


def format_cognition_status(status: dict[str, Any] | None = None) -> str:
    status = status or get_cognition_status()
    fabric = status.get("fabric_status") or {}
    active = fabric.get("active_context") or {}
    tiers = status.get("available_tiers") or []
    tier_lines = [
        f"- {item.get('tier')}: {'available' if item.get('available') else 'unavailable'} ({item.get('engine')})"
        for item in tiers
    ]
    return (
        "ORACLE Cognition Fabric\n"
        f"current_cognition_tier: {status.get('current_cognition_tier')}\n"
        f"status_label: {status.get('status_label')}\n"
        f"source_count: {active.get('source_count', 0)}\n"
        f"receipt_count: {active.get('receipt_count', 0)}\n"
        f"last_local_model_status: {status.get('last_local_model_status')}\n"
        f"last_timeout: {status.get('last_timeout')}\n"
        f"last_fallback_reason: {status.get('last_fallback_reason')}\n"
        "cloud_apis_enabled: false\n"
        "external_models_require_approval: true\n"
        "cloud_api_used: false\n"
        "conversation_reset: false\n"
        "available_tiers:\n"
        + "\n".join(tier_lines)
    )


def write_cognition_fabric_receipt(
    *,
    receipt_dir: Path | None = None,
    status: dict[str, Any] | None = None,
    notes: str = "",
) -> dict[str, Any]:
    status = status or get_cognition_status()
    tiers = [item.get("tier") for item in status.get("available_tiers", []) if item.get("available")]
    receipt = {
        "receipt_id": _id("cognition_fabric_receipt"),
        "timestamp": _now(),
        "action": "cognition_fabric",
        "cognition_tiers_available": tiers,
        "cloud_api_used": False,
        "external_model_enabled": False,
        "conversation_reset": False,
        "upload": False,
        "sync": False,
        "drive_modified": False,
        "git_commit": False,
        "git_push": False,
        "credential_touched": False,
        "files_moved": 0,
        "files_deleted": 0,
        "files_renamed": 0,
        "cloud_uploads": 0,
        "cloud_api_calls": 0,
        "human_authority": "Noah.Physical",
        "notes": notes,
    }
    target_dir = Path(receipt_dir or RECEIPTS_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"cognition_fabric_receipt_{_stamp()}.json"
    path.write_text(json.dumps(receipt, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    receipt["receipt_path"] = str(path)
    return receipt


if __name__ == "__main__":
    print(format_cognition_status())
