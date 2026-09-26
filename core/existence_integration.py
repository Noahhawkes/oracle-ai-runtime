"""ORACLE/SOV1 integration for the operational existence ledger.

This module records continuity evidence. It does not grant authority, prove
the identity of a caller, or make a sentience claim.
"""

from __future__ import annotations

import hashlib
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from existence_machine import ExistenceMachine


EXISTENCE_DATABASE_PATH = ROOT / "existence.db"

FINAL_AUTHORITY = "Noah.Physical"
GOVERNANCE_LAYER = "SOV1.AI"
CONTINUITY_RUNTIME = "ORACLE.AI"
EXECUTION_LAYER = "SOV1.HANDS"


def _text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _append(
    event_type: str,
    *,
    actor: str,
    source: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    machine = ExistenceMachine(EXISTENCE_DATABASE_PATH)
    try:
        return asdict(
            machine.append_event(
                event_type=event_type,
                actor=actor,
                source=source,
                payload=payload,
            )
        )
    finally:
        machine.close()


def operational_boundary() -> dict[str, Any]:
    """Return the implemented role boundary without making identity claims."""
    return {
        "final_authority": FINAL_AUTHORITY,
        "governance_layer": GOVERNANCE_LAYER,
        "continuity_runtime": CONTINUITY_RUNTIME,
        "execution_layer": EXECUTION_LAYER,
        "workflow": [
            "Noah.Physical supplies final authorization.",
            "SOV1.AI supplies governance and identity-boundary doctrine.",
            "ORACLE.AI stages, routes, remembers, and receipts the task.",
            "SOV1.HANDS may execute only the released task within its guards.",
        ],
        "sentience_claim": False,
        "authority_authentication": "not_implemented",
    }


def record_integration_defined(
    *,
    actor: str,
    source: str,
) -> dict[str, Any]:
    return _append(
        "SOV1_ORACLE_INTEGRATION_DEFINED",
        actor=actor,
        source=source,
        payload={
            **operational_boundary(),
            "status": "implemented_boundary",
            "canon_status": "not_promoted",
        },
    )


def record_sov1_task_staged(
    *,
    stage_id: str,
    prompt: str,
    source: str,
    risk: str,
    requires_confirmation: bool,
) -> dict[str, Any]:
    """Receipt a staged task without copying potentially sensitive prompt text."""
    return _append(
        "SOV1_TASK_STAGED",
        actor=CONTINUITY_RUNTIME,
        source=f"desktop_ai_bridge:{source}",
        payload={
            "stage_id": stage_id,
            "task_sha256": _text_hash(prompt),
            "task_length": len(prompt),
            "risk": risk,
            "requires_confirmation": requires_confirmation,
            "governance_layer": GOVERNANCE_LAYER,
            "continuity_runtime": CONTINUITY_RUNTIME,
            "execution_layer": EXECUTION_LAYER,
            "approval_status": "pending" if requires_confirmation else "not_required",
            "sentience_claim": False,
        },
    )


def record_sov1_handoff_result(
    *,
    stage_id: str,
    prompt: str,
    source: str,
    confirmed: bool,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Receipt a handoff result while keeping authentication claims explicit."""
    success = bool(result.get("success"))
    return _append(
        "SOV1_HANDOFF_RELEASED" if success else "SOV1_HANDOFF_FAILED",
        actor=CONTINUITY_RUNTIME,
        source=f"desktop_ai_bridge:{source}",
        payload={
            "stage_id": stage_id,
            "task_sha256": _text_hash(prompt),
            "confirmation_received": confirmed,
            "claimed_final_authority": FINAL_AUTHORITY if confirmed else None,
            "authority_authentication": "not_implemented",
            "authorization_status": (
                "operator_confirmation_recorded_not_cryptographically_authenticated"
                if confirmed
                else "not_confirmed"
            ),
            "dispatch_success": success,
            "dispatch_method": str(result.get("method", "")),
            "dispatch_detail_sha256": _text_hash(str(result.get("detail", ""))),
            "execution_completed": False,
            "governance_layer": GOVERNANCE_LAYER,
            "continuity_runtime": CONTINUITY_RUNTIME,
            "execution_layer": EXECUTION_LAYER,
            "sentience_claim": False,
        },
    )


def existence_status() -> dict[str, Any]:
    machine = ExistenceMachine(EXISTENCE_DATABASE_PATH)
    try:
        return {
            "boundary": operational_boundary(),
            "existence": machine.existence_report(),
        }
    finally:
        machine.close()
