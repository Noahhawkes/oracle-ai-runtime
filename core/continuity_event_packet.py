"""Continuity Event Packet v1.

This is the local black-box recorder for ORACLE chat turns. It records the
whole governed event around an answer: prompt, output, route, evidence,
uncertainties, authority boundary, executed action claims, and resume point.

It does not read or write sandbox files, mutate source files, call external
systems, promote canon, execute commands, or approve anything.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from root import ROOT
except Exception:  # pragma: no cover
    ROOT = Path(__file__).resolve().parents[1]


SCHEMA_VERSION = "continuity_event_packet.v1"
OUTPUT_DIR = ROOT / "Memory" / "continuity_events"
INDEX_PATH = OUTPUT_DIR / "index.jsonl"
LATEST_PATH = OUTPUT_DIR / "latest.json"

MAX_PREVIEW_CHARS = 280

_RECEIPT_PATH_RE = re.compile(
    r"(?:receipt_path|receipts?)['\"\s:=]+(?P<path>[A-Za-z]:[\\/][^\r\n\"'`]+)",
    re.IGNORECASE,
)
_ACTION_ID_RE = re.compile(r"(sandbox_[A-Za-z0-9_]+_[0-9TZ_a-f-]+)", re.IGNORECASE)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime | None = None) -> str:
    return (value or _utc_now()).isoformat().replace("+00:00", "Z")


def _stamp_for_path(value: datetime | None = None) -> str:
    return (value or _utc_now()).strftime("%Y%m%dT%H%M%S%fZ")


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _preview(value: Any, limit: int = MAX_PREVIEW_CHARS) -> str:
    text = _clean(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _sha256_text(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _sha256_json(data: Any) -> str:
    return hashlib.sha256(_stable_json(data).encode("utf-8")).hexdigest()


def _coerce_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _coerce_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _route_payload(done_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "route_type": done_payload.get("route_type") or done_payload.get("type") or "done",
        "effective_route": (
            done_payload.get("effective_route")
            or done_payload.get("lane")
            or done_payload.get("current_lane")
            or ""
        ),
        "lane": done_payload.get("lane") or done_payload.get("current_lane") or "",
        "mode": done_payload.get("mode") or "",
        "reason": done_payload.get("reason"),
        "fallback_used": bool(done_payload.get("fallback_used", False)),
    }


def _source_payload(done_payload: dict[str, Any]) -> dict[str, Any]:
    evidence = _coerce_dict(done_payload.get("evidence"))
    recall = _coerce_dict(done_payload.get("recall_evidence"))
    records = _coerce_list(evidence.get("records_used"))
    sources = _coerce_list(evidence.get("sources_proven_used"))
    if recall:
        for source in _coerce_list(recall.get("sources_proven_used")):
            if source not in sources:
                sources.append(source)
    return {
        "sources_proven_used": sources,
        "records_used_count": int(evidence.get("records_used_count") or len(records)),
        "records_used": records,
        "recall_orchestrator": recall or None,
    }


def _uncertainties(done_payload: dict[str, Any], assistant_output: str) -> list[str]:
    evidence = _coerce_dict(done_payload.get("evidence"))
    items: list[str] = []
    for value in _coerce_list(evidence.get("unknowns")):
        text = _clean(value)
        if text and text not in items:
            items.append(text)
    citation_guard = _coerce_list(done_payload.get("citation_guard"))
    if citation_guard:
        items.append("citation_guard flagged unverified path claims in streamed text")
    if not assistant_output.strip():
        items.append("assistant output text was empty when packet was written")
    return items


def _correction_payload(user_text: str) -> dict[str, Any]:
    lowered = user_text.lower()
    detected = any(
        token in lowered
        for token in (
            "correction",
            "correct this",
            "not what i meant",
            "reject",
            "supersede",
            "that is wrong",
            "that's wrong",
            "dont assume",
            "don't assume",
        )
    )
    return {
        "detected_correction_request": detected,
        "status": "preserved_for_human_review" if detected else "none_detected",
    }


def _receipt_mentions(done_payload: dict[str, Any], assistant_output: str) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for key in ("receipt_path", "path"):
        value = done_payload.get(key)
        if value:
            receipts.append({"source": f"done_payload.{key}", "path": str(value)})
    for match in _RECEIPT_PATH_RE.finditer(assistant_output or ""):
        path = match.group("path").rstrip(" .,:;)]}")
        if path:
            receipts.append({"source": "assistant_output", "path": path})

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in receipts:
        key = str(item.get("path") or "").lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


def _executed_actions(done_payload: dict[str, Any], assistant_output: str) -> list[dict[str, Any]]:
    route = _route_payload(done_payload)
    route_text = " ".join(
        str(route.get(key) or "") for key in ("route_type", "effective_route", "lane", "reason")
    ).lower()
    output_lower = assistant_output.lower()
    actions: list[dict[str, Any]] = []

    sandbox_markers = (
        "sandbox_initiative_write" in route_text
        or "sandbox initiative receipt" in output_lower
        or '"operation_type": "sandbox_initiative_write"' in output_lower
        or "'operation_type': 'sandbox_initiative_write'" in output_lower
    )
    if sandbox_markers:
        action_id = done_payload.get("action_id")
        if not action_id:
            match = _ACTION_ID_RE.search(assistant_output or "")
            action_id = match.group(1) if match else None
        actions.append({
            "operation_type": "sandbox_initiative_write",
            "action_id": action_id,
            "evidence": "done_payload_or_visible_response_text",
            "external": False,
            "canon_promotion": False,
            "boundary": "sandbox candidate only; Codex packet did not read or write sandbox",
        })

    if done_payload.get("citation_guard"):
        actions.append({
            "operation_type": "citation_guard",
            "evidence": "streaming_text_guard",
            "external": False,
            "canon_promotion": False,
        })
    return actions


def _source_resolution_payload(done_payload: dict[str, Any]) -> dict[str, Any]:
    recall = _coerce_dict(done_payload.get("recall_evidence"))
    if recall.get("source_resolution"):
        return _coerce_dict(recall.get("source_resolution"))
    evidence = _coerce_dict(done_payload.get("evidence"))
    recall_from_evidence = _coerce_dict(evidence.get("recall_orchestrator"))
    return _coerce_dict(recall_from_evidence.get("source_resolution"))


def _claims_extracted(done_payload: dict[str, Any]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    resolution = _source_resolution_payload(done_payload)
    if resolution:
        selected = _coerce_dict(resolution.get("selected_claim"))
        claims.append({
            "claim_type": "source_resolution",
            "status": resolution.get("status") or "UNKNOWN",
            "fact_domain": resolution.get("fact_domain") or "UNKNOWN",
            "field": resolution.get("field") or "UNKNOWN",
            "selected_source_class": selected.get("source_class") or None,
            "selected_source_id": selected.get("source_id") or None,
            "selected_precision": selected.get("precision") or None,
            "conflict_count": len(_coerce_list(resolution.get("conflicts"))),
            "candidate_count": len(_coerce_list(resolution.get("candidate_claims"))),
            "provenance_refs": _coerce_list(resolution.get("provenance_refs")),
            "boundary": "candidate extraction from resolver metadata; not canon promotion",
        })

    evidence = _coerce_dict(done_payload.get("evidence"))
    for record in _coerce_list(evidence.get("records_used"))[:10]:
        if not isinstance(record, dict):
            continue
        claims.append({
            "claim_type": "evidence_record_used",
            "surface": record.get("surface") or "UNKNOWN",
            "title": record.get("title") or "UNKNOWN",
            "path": record.get("path") or "",
            "line_range": record.get("line_range") or "",
            "boundary": "record was used as evidence context; content claims require source citation",
        })
    return claims


def _user_intent(done_payload: dict[str, Any], user_text: str, route: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": done_payload.get("intent") or route.get("route_type") or "UNKNOWN",
        "route_type": route.get("route_type") or "UNKNOWN",
        "effective_route": route.get("effective_route") or "UNKNOWN",
        "lane": route.get("lane") or "UNKNOWN",
        "reason": route.get("reason") or "",
        "user_text_sha256": _sha256_text(user_text),
        "user_text_preview": _preview(user_text),
    }


def _runtime_environment(session_id: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "runtime_root": str(ROOT),
        "local_only": True,
        "entrypoint": "oracle_server.py",
        "session_id": session_id or "UNKNOWN",
    }
    try:
        import runtime_config

        payload.update({
            "host": runtime_config.runtime_host(),
            "port": runtime_config.runtime_port(),
            "base_url": runtime_config.runtime_base_url(host="127.0.0.1"),
        })
    except Exception:
        payload.update({"host": "UNKNOWN", "port": "UNKNOWN", "base_url": "UNKNOWN"})
    return payload


def build_event_packet(
    *,
    user_text: str,
    assistant_output: str,
    done_payload: dict[str, Any] | None = None,
    session_id: str | None = None,
    ui_mode: str | None = None,
    conversation_turn_count: int | None = None,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a Continuity Event Packet without writing it."""
    done = dict(done_payload or {})
    now = created_at or _utc_now()
    event_id = f"cep_{_stamp_for_path(now)}_{uuid.uuid4().hex[:10]}"
    route = _route_payload(done)
    sources = _source_payload(done)
    receipts = _receipt_mentions(done, assistant_output)
    actions_executed = _executed_actions(done, assistant_output)
    uncertainties = _uncertainties(done, assistant_output)
    claims_extracted = _claims_extracted(done)
    visible_context = {
        "status": "not_captured_by_backend_v1",
        "note": "Backend packet records chat payloads; browser DOM/screenshot capture is a later layer.",
    }
    assistant_response = {
        "text": assistant_output or "",
        "sha256": _sha256_text(assistant_output),
        "preview": _preview(assistant_output),
    }
    return_pointer = {
        "last_user_preview": _preview(user_text),
        "last_assistant_preview": _preview(assistant_output),
        "session_id": session_id or "UNKNOWN",
        "route_type": route.get("route_type"),
        "effective_route": route.get("effective_route"),
        "unknown_count": len(uncertainties),
    }

    packet: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "event_id": event_id,
        "timestamp": _timestamp(now),
        "source": "ORACLE /chat SSE",
        "speaker": "Noah.Physical",
        "channel": "ORACLE /chat SSE",
        "human_source": "Noah.Physical",
        "transport_channel": "ORACLE /chat SSE",
        "intended_audience": "Noah.Physical",
        "environment_state": _runtime_environment(session_id),
        "active_session": {
            "session_id": session_id or "UNKNOWN",
            "conversation_turn_count": conversation_turn_count,
            "ui_mode": ui_mode or done.get("mode") or "UNKNOWN",
        },
        "visible_context": visible_context,
        "visible_ui_state": visible_context,
        "user_intent": _user_intent(done, user_text or "", route),
        "user_input": {
            "text": user_text or "",
            "sha256": _sha256_text(user_text),
            "preview": _preview(user_text),
        },
        "assistant_response": assistant_response,
        "assistant_output": assistant_response,
        "route": route,
        "evidence_used": sources,
        "sources": sources,
        "claims_extracted": claims_extracted,
        "inferences": {
            "capability": _coerce_dict(done.get("evidence")).get("capability"),
            "intent_summary": done.get("intent") or done.get("route_type") or route.get("route_type"),
            "model_claims_not_treated_as_receipts": True,
        },
        "uncertainties": uncertainties,
        "corrections": _correction_payload(user_text or ""),
        "authority_status": {
            "approval_authority": "Noah.Physical",
            "external_action_requires_approval": True,
            "canon_promotion_requires_approval": True,
            "packet_writes_are_local_memory_records": True,
        },
        "actions_proposed": [],
        "actions_taken": actions_executed,
        "actions_executed": actions_executed,
        "receipts": receipts,
        "memory_effect": {
            "conversation_history_append": True,
            "continuity_packet_written": False,
            "source_file_mutation": False,
            "external_send": False,
            "canon_promotion": False,
        },
        "canon_status": {
            "status": "candidate_event_record",
            "promotion_status": "not_promoted",
        },
        "return_pointer": return_pointer,
        "resume_point": return_pointer,
        "boundaries": {
            "sandbox_read_by_packet": False,
            "sandbox_write_by_packet": False,
            "source_file_mutation": False,
            "drive_mutation": False,
            "external_send": False,
            "command_exec": False,
            "canon_promotion": False,
        },
    }
    packet["packet_hash_sha256"] = _sha256_json(packet)
    return packet


def write_event_packet(
    *,
    user_text: str,
    assistant_output: str,
    done_payload: dict[str, Any] | None = None,
    session_id: str | None = None,
    ui_mode: str | None = None,
    conversation_turn_count: int | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Write a local packet and return a compact receipt payload."""
    root = Path(output_dir) if output_dir is not None else OUTPUT_DIR
    root.mkdir(parents=True, exist_ok=True)
    index_path = root / "index.jsonl"
    latest_path = root / "latest.json"

    packet = build_event_packet(
        user_text=user_text,
        assistant_output=assistant_output,
        done_payload=done_payload or {},
        session_id=session_id,
        ui_mode=ui_mode,
        conversation_turn_count=conversation_turn_count,
    )
    packet["memory_effect"]["continuity_packet_written"] = True
    packet["packet_hash_sha256"] = _sha256_json({k: v for k, v in packet.items() if k != "packet_hash_sha256"})

    packet_path = root / f"{packet['event_id']}.json"
    packet_path.write_text(
        json.dumps(packet, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    latest_path.write_text(
        json.dumps(packet, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    index_row = {
        "schema_version": SCHEMA_VERSION,
        "event_id": packet["event_id"],
        "timestamp": packet["timestamp"],
        "packet_path": str(packet_path),
        "packet_hash_sha256": packet["packet_hash_sha256"],
        "session_id": session_id or "UNKNOWN",
        "route_type": packet["route"].get("route_type"),
        "effective_route": packet["route"].get("effective_route"),
        "user_preview": packet["user_input"]["preview"],
        "assistant_preview": packet["assistant_output"]["preview"],
        "canon_status": packet["canon_status"]["status"],
        "promotion_status": packet["canon_status"]["promotion_status"],
    }
    with index_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(index_row, ensure_ascii=True, sort_keys=True) + "\n")

    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "event_id": packet["event_id"],
        "packet_path": str(packet_path),
        "latest_path": str(latest_path),
        "index_path": str(index_path),
        "packet_hash_sha256": packet["packet_hash_sha256"],
        "canon_status": packet["canon_status"]["status"],
        "promotion_status": packet["canon_status"]["promotion_status"],
        "boundary": "local Memory record only; no sandbox touch, external send, command execution, or canon promotion",
    }


def latest_event(output_dir: Path | None = None) -> dict[str, Any]:
    root = Path(output_dir) if output_dir is not None else OUTPUT_DIR
    latest_path = root / "latest.json"
    if not latest_path.exists():
        return {
            "ok": False,
            "error": "no continuity event packet has been written",
            "latest_path": str(latest_path),
        }
    try:
        packet = json.loads(latest_path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "latest_path": str(latest_path)}
    return {"ok": True, "latest_path": str(latest_path), "packet": packet}


def status(output_dir: Path | None = None) -> dict[str, Any]:
    root = Path(output_dir) if output_dir is not None else OUTPUT_DIR
    index_path = root / "index.jsonl"
    count = 0
    latest: dict[str, Any] | None = None
    if index_path.exists():
        try:
            with index_path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    count += 1
                    try:
                        latest = json.loads(line)
                    except Exception:
                        continue
        except OSError:
            pass
    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "packet_count": count,
        "output_dir": str(root),
        "index_path": str(index_path),
        "latest": latest,
        "boundaries": {
            "sandbox_touched": False,
            "source_file_mutation": False,
            "drive_mutation": False,
            "external_send": False,
            "command_exec": False,
            "canon_promotion": False,
        },
    }
