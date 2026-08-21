"""Continuity Event Packet V1 lifecycle for ORACLE web turns.

This module orchestrates event recording only.  It consumes route and resolver
metadata already produced by the chat path; it does not call models, execute
actions, mutate sources, or create new authority claims.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .continuity_event import ContinuityEventPacket, ContinuityLedgerWriter
except ImportError:  # direct module import used by the existing runtime
    from continuity_event import ContinuityEventPacket, ContinuityLedgerWriter

try:
    from .source_resolver import CONFLICT, PARTIAL, RESOLVED, SOURCE_UNAVAILABLE
except Exception:  # pragma: no cover - conservative fallback during partial boot
    try:
        from source_resolver import CONFLICT, PARTIAL, RESOLVED, SOURCE_UNAVAILABLE
    except Exception:
        CONFLICT = "CONFLICT"
        PARTIAL = "PARTIAL"
        RESOLVED = "RESOLVED"
        SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"


@dataclass
class ContinuityTurnLifecycle:
    """Mutable draft held only for the duration of one streamed chat turn."""

    packet: ContinuityEventPacket
    sealed: bool = False


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _unique_text(values: Sequence[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def instantiate_turn(
    user_payload: str,
    *,
    thread_id: str | None,
    channel: str = "localhost_7781",
    visible_context: Sequence[str] = (),
) -> ContinuityTurnLifecycle:
    context = _unique_text([*visible_context, f"thread_id:{thread_id or 'UNKNOWN'}"])
    return ContinuityTurnLifecycle(
        packet=ContinuityEventPacket(
            source="Noah.Physical",
            speaker="user",
            channel=channel,
            visible_context=context,
            user_intent=str(user_payload or "").strip(),
            authority_status="UNVERIFIED",
            return_pointer=str(thread_id) if thread_id is not None else None,
        )
    )


def _source_resolution(done_payload: Mapping[str, Any]) -> dict[str, Any]:
    recall = _mapping(done_payload.get("recall_evidence"))
    resolution = _mapping(recall.get("source_resolution"))
    if resolution:
        return resolution
    evidence = _mapping(done_payload.get("evidence"))
    recall = _mapping(evidence.get("recall_orchestrator"))
    return _mapping(recall.get("source_resolution"))


def _authority_status(done_payload: Mapping[str, Any], evidence: Mapping[str, Any]) -> str:
    resolution = _source_resolution(done_payload)
    status = str(resolution.get("status") or "").upper()
    if status == RESOLVED:
        return "VERIFIED"
    if status == CONFLICT:
        return "CONFLICT"
    if status == SOURCE_UNAVAILABLE:
        return "SOURCE_UNAVAILABLE"
    if status == PARTIAL:
        return "DEGRADED"
    if evidence.get("ok") is True and (
        evidence.get("records_used_count") or evidence.get("sources_proven_used")
    ):
        return "VERIFIED"
    if evidence.get("ok") is False:
        return "DEGRADED"
    return "UNVERIFIED"


def _evidence_rows(done_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    evidence = _mapping(done_payload.get("evidence"))
    rows: list[dict[str, Any]] = []
    for item in _list(evidence.get("records_used")):
        record = _mapping(item)
        if not record:
            continue
        rows.append({
            "source_id": record.get("source_id") or record.get("title") or record.get("surface") or "UNKNOWN",
            "path": record.get("path") or "",
            "line": record.get("line") or record.get("line_range") or "",
            "hash": record.get("hash") or record.get("sha256") or "",
        })

    resolution = _source_resolution(done_payload)
    selected = _mapping(resolution.get("selected_claim"))
    if selected:
        row = {
            "source_id": selected.get("source_id") or "UNKNOWN",
            "path": selected.get("source_path") or "",
            "line": selected.get("line") or "",
            "hash": selected.get("hash") or selected.get("sha256") or "",
        }
        if row not in rows:
            rows.append(row)
    return rows


def resolve_turn(lifecycle: ContinuityTurnLifecycle, done_payload: Mapping[str, Any]) -> None:
    if lifecycle.sealed:
        raise RuntimeError("continuity turn is already sealed")
    evidence = _mapping(done_payload.get("evidence"))
    lifecycle.packet.evidence_used = _evidence_rows(done_payload)
    lifecycle.packet.authority_status = _authority_status(done_payload, evidence)
    lifecycle.packet.uncertainties = _unique_text([
        *_list(evidence.get("unknowns")),
        *_list(_source_resolution(done_payload).get("unavailable_sources")),
    ])
    resolution = _source_resolution(done_payload)
    if str(resolution.get("status") or "").upper() == CONFLICT:
        lifecycle.packet.uncertainties.append("source resolver reported conflicting high-authority claims")


def execute_turn(
    lifecycle: ContinuityTurnLifecycle,
    *,
    assistant_response: str,
    done_payload: Mapping[str, Any],
) -> None:
    if lifecycle.sealed:
        raise RuntimeError("continuity turn is already sealed")
    lifecycle.packet.assistant_response = str(assistant_response or "")
    claims = _list(done_payload.get("claims_extracted"))
    resolution = _source_resolution(done_payload)
    selected = _mapping(resolution.get("selected_claim"))
    if resolution:
        claims.append(
            "source_resolution:"
            f"{resolution.get('fact_domain') or 'UNKNOWN'}:"
            f"{resolution.get('field') or 'UNKNOWN'}:"
            f"{resolution.get('status') or 'UNKNOWN'}:"
            f"{selected.get('source_id') or 'no_selected_source'}"
        )
    lifecycle.packet.claims_extracted = _unique_text(claims)
    lifecycle.packet.corrections = [
        {str(key): str(value) for key, value in _mapping(item).items()}
        for item in _list(done_payload.get("corrections"))
        if _mapping(item)
    ]
    lifecycle.packet.actions_proposed = [
        _mapping(item) for item in _list(done_payload.get("actions_proposed")) if _mapping(item)
    ]
    lifecycle.packet.actions_taken = [
        _mapping(item) for item in _list(done_payload.get("actions_taken")) if _mapping(item)
    ]

    route = str(
        done_payload.get("effective_route")
        or done_payload.get("route_type")
        or done_payload.get("lane")
        or "unknown"
    )
    mode = str(done_payload.get("mode") or "unknown")
    lifecycle.packet.visible_context = _unique_text([
        *lifecycle.packet.visible_context,
        f"route:{route}",
        f"mode:{mode}",
    ])


def seal_turn(
    lifecycle: ContinuityTurnLifecycle,
    *,
    writer: ContinuityLedgerWriter | None = None,
    memory_effect: str = "LEDGER_SEAL",
    return_pointer: str | None = None,
) -> dict[str, Any]:
    if lifecycle.sealed:
        raise RuntimeError("continuity turn is already sealed")
    packet = lifecycle.packet
    packet.memory_effect = memory_effect
    if return_pointer is not None:
        packet.return_pointer = str(return_pointer)
    ledger_writer = writer or ContinuityLedgerWriter()
    ledger_path = ledger_writer.record_event(packet)
    lifecycle.sealed = True
    return {
        "ok": True,
        "schema_version": "CONTINUITY_EVENT_PACKET_V1",
        "event_id": packet.event_id,
        "ledger_path": str(ledger_path),
        "authority_status": packet.authority_status,
        "memory_effect": packet.memory_effect,
        "return_pointer": packet.return_pointer,
    }


def record_completed_turn(
    lifecycle: ContinuityTurnLifecycle,
    *,
    assistant_response: str,
    done_payload: Mapping[str, Any],
    writer: ContinuityLedgerWriter | None = None,
    memory_effect: str = "LEDGER_SEAL",
    return_pointer: str | None = None,
) -> dict[str, Any]:
    """Run resolution, execution capture, and sealing for one draft turn."""
    resolve_turn(lifecycle, done_payload)
    execute_turn(
        lifecycle,
        assistant_response=assistant_response,
        done_payload=done_payload,
    )
    return seal_turn(
        lifecycle,
        writer=writer,
        memory_effect=memory_effect,
        return_pointer=return_pointer,
    )
