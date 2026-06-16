"""Unified Law/Life status for ORACLE.

Law is the USER.AI sovereignty and consent layer.
Life is the active_npc persistent simulation layer.
Observation truth is reported from explicit receipts, never model availability.
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from root import ROOT


USER_AI_DOC = ROOT / "docs" / "USER_AI_NETWORK_DESIGN.md"
ACTIVE_NPC_DOC = ROOT / "modules" / "active_npc" / "ACTIVE_NPC_ARCHITECTURE.md"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, default: str = "UNKNOWN") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def build_observation_status() -> dict[str, Any]:
    """Return one truthful observation summary across current + camera receipts."""
    current = {
        "receipt_status": "unavailable",
        "receipt_id": None,
        "fresh": False,
        "visual_observation": "UNKNOWN",
    }
    try:
        from current_observation import current_observation_state, rendered_value

        state = current_observation_state()
        current = {
            "receipt_status": state.get("receipt_status") or "UNKNOWN",
            "receipt_id": state.get("receipt_id"),
            "fresh": bool(state.get("fresh")),
            "observed_at": state.get("observed_at"),
            "visual_observation": rendered_value(state, "visual_observation"),
        }
    except Exception as exc:
        current["error"] = f"{type(exc).__name__}: {exc}"

    camera = {
        "receipt_status": "missing",
        "receipt_id": None,
        "fresh": False,
        "observation_text": "UNKNOWN",
        "raw_frame_stored": False,
    }
    try:
        from camera_receipt import load_latest

        receipt = load_latest()
        if isinstance(receipt, dict):
            raw_observation = _text(receipt.get("observation_text"))
            safe_observation = "UNKNOWN" if raw_observation == "UNKNOWN" else "receipt present"
            camera = {
                "receipt_status": "present",
                "receipt_id": receipt.get("observation_id"),
                "fresh": True,
                "captured_at_utc": receipt.get("captured_at_utc"),
                "observation_text": safe_observation,
                "observation_text_status": "unknown" if safe_observation == "UNKNOWN" else "present_redacted",
                "confidence": receipt.get("confidence"),
                "evidence_class": receipt.get("evidence_class"),
                "published_to_chat": bool(receipt.get("published_to_chat")),
                "raw_frame_stored": bool(receipt.get("raw_frame_stored")),
                "retention_policy": receipt.get("retention_policy"),
                "source_type": receipt.get("source_type"),
            }
    except Exception as exc:
        camera["receipt_status"] = "unavailable"
        camera["error"] = f"{type(exc).__name__}: {exc}"

    last = None
    if current.get("fresh") and current.get("visual_observation") != "UNKNOWN":
        last = {
            "source": "current_observation",
            "text": current.get("visual_observation"),
            "id": current.get("receipt_id"),
            "at": current.get("observed_at"),
            "status": current.get("receipt_status"),
        }
    elif camera.get("receipt_status") == "present":
        last = {
            "source": "camera_observation",
            "text": camera.get("observation_text") or "UNKNOWN",
            "id": camera.get("receipt_id"),
            "at": camera.get("captured_at_utc"),
            "status": camera.get("receipt_status"),
        }

    return {
        "current_observation": current,
        "camera_observation": camera,
        "last_observation": last,
        "boundary": (
            "Screen/window current observation and camera LOOK ONCE receipts are distinct; "
            "model availability is not observation evidence."
        ),
    }


def build_law_status() -> dict[str, Any]:
    """Report USER.AI law layer readiness without exposing raw private memory."""
    out = {
        "status": "missing",
        "user_ai_doc": USER_AI_DOC.exists(),
        "relationship_memory": "unavailable",
        "approved_relationships": 0,
        "pending_relationships": 0,
        "approved_sovereigns": [],
    }
    try:
        from relationship_memory import RelationshipMemoryStore

        store = RelationshipMemoryStore()
        approved = store.list_approved()
        pending = store.list_pending()
        out.update({
            "relationship_memory": "ready",
            "approved_relationships": len(approved),
            "pending_relationships": len(pending),
            "approved_sovereigns": [
                {
                    "name": item.name,
                    "sov_id": item.sov_id,
                    "relationship_type": item.relationship_type,
                    "trust_tier": item.trust_tier,
                }
                for item in approved[:8]
            ],
        })
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
    if out["user_ai_doc"] and out["relationship_memory"] == "ready":
        out["status"] = "ready"
    return out


def build_life_status() -> dict[str, Any]:
    """Report active_npc life-layer readiness without running a simulation."""
    module_spec = importlib.util.find_spec("modules.active_npc")
    return {
        "status": "ready" if ACTIVE_NPC_DOC.exists() and module_spec is not None else "missing",
        "active_npc_doc": ACTIVE_NPC_DOC.exists(),
        "active_npc_module": module_spec is not None,
        "engine": "modules.active_npc",
        "runtime_wired_to_server": False,
        "test_command": "python -m modules.active_npc.tests",
    }


def build_law_life_status() -> dict[str, Any]:
    """Build the complete read-only status object consumed by UI and chat."""
    law = build_law_status()
    life = build_life_status()
    try:
        from npc_seed_bridge import bridge_status

        bridge = bridge_status()
    except Exception as exc:
        bridge = {
            "available": False,
            "server_bridge_status": "unavailable",
            "runtime_instantiation_status": "unknown",
            "error": f"{type(exc).__name__}: {exc}",
            "seed_candidates": [],
        }
    return {
        "schema_version": 1,
        "generated_at": _now(),
        "law": law,
        "life": life,
        "bridge": bridge,
        "observation": build_observation_status(),
    }


def summarize_law_life_status(status: dict[str, Any] | None = None) -> str:
    """Format a deterministic, receipt-aware answer for ORACLE chat."""
    s = status or build_law_life_status()
    law = s.get("law", {})
    life = s.get("life", {})
    bridge = s.get("bridge", {})
    obs = s.get("observation", {})
    cur = obs.get("current_observation", {})
    cam = obs.get("camera_observation", {})
    last = obs.get("last_observation")

    lines = ["VERIFIED [LAW_LIFE_STATUS] — reconciled live just now:"]
    lines.append(
        f"- Law layer: {law.get('status')} "
        f"(USER.AI doc: {bool(law.get('user_ai_doc'))}; "
        f"relationship memory: {law.get('relationship_memory')}; "
        f"approved: {law.get('approved_relationships', 0)}; pending: {law.get('pending_relationships', 0)})"
    )
    lines.append(
        f"- Life layer: {life.get('status')} "
        f"(active_npc module: {bool(life.get('active_npc_module'))}; "
        f"server wired: {bool(life.get('runtime_wired_to_server'))})"
    )
    lines.append(
        f"- USER.AI → NPC bridge: {bridge.get('server_bridge_status')} "
        f"(seed candidates: {bridge.get('seed_candidate_count', 0)}; "
        f"runtime instantiation: {bridge.get('runtime_instantiation_status')})"
    )
    camera_detail = cam.get("receipt_status")
    if cam.get("receipt_status") == "present":
        camera_detail = f"present [{cam.get('receipt_id') or 'NO_RECEIPT_ID'}]"
    lines.append(
        f"- Observation truth: current screen receipt {cur.get('receipt_status')}; "
        f"latest camera receipt {camera_detail}"
    )
    if isinstance(last, dict):
        lines.append(
            f"- Unified last observation receipt: {last.get('source')} "
            f"[{last.get('id') or 'NO_RECEIPT_ID'}]"
        )
    seeds = bridge.get("seed_candidates") or []
    if seeds:
        labels = []
        for seed in seeds[:5]:
            labels.append(
                f"{seed.get('display_name')}:{seed.get('consent_status')}"
            )
        lines.append(f"- Seed candidates: {', '.join(labels)}")
    lines.append(
        "BOUNDARY: Law can propose seeds from approved relationship memory; life can run "
        "NPC cognition; no person-specific NPC is instantiated until the consent gate passes."
    )
    return "\n".join(lines)


if __name__ == "__main__":
    print(summarize_law_life_status())
