"""Explicit Human State and Re-entry support for ORACLE.

This module records only Noah.Physical's explicit transition statements or
verified local system events. It does not infer mood, location, health,
relationship state, or hidden intent.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

import memory


MODES = (
    "WORK_ECOWATER",
    "WORK_ORACLE",
    "WORK_WRITING",
    "FAMILY",
    "ERRAND",
    "TRAVEL",
    "RECREATION",
    "REST",
    "SLEEP",
    "UNKNOWN",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _compact(text: Any) -> str:
    return " ".join(str(text or "").split())


def _lower(text: Any) -> str:
    return _compact(text).lower()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _json_hash(data: dict[str, Any]) -> str:
    return _sha256_text(json.dumps(data, sort_keys=True, ensure_ascii=False))


def ensure_schema() -> None:
    with memory.get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS human_state_transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                timestamp TEXT NOT NULL,
                human_event_time TEXT,
                previous_mode TEXT NOT NULL,
                new_mode TEXT NOT NULL,
                source_text TEXT NOT NULL,
                source_system TEXT NOT NULL,
                source_receipt TEXT,
                confidence REAL NOT NULL,
                related_project TEXT,
                active_task TEXT,
                open_loops_json TEXT NOT NULL DEFAULT '[]',
                reentry_hint TEXT,
                authorial_authority TEXT NOT NULL,
                canon_status TEXT NOT NULL,
                dedupe_key TEXT NOT NULL UNIQUE,
                receipt_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL
            )
            """
        )


def classify_transition(
    source_text: str,
    *,
    related_project: str | None = None,
    active_task: str | None = None,
) -> dict[str, Any]:
    text = _lower(source_text)
    project = _compact(related_project)
    task = _compact(active_task)
    if not text:
        return _classification("UNKNOWN", 0.0, project, task, "No explicit transition statement.")

    if _has_any(text, ("going to sleep", "go to sleep", "going to bed", "bed now", "sleeping")):
        return _classification("SLEEP", 0.95, project, task, "Preserve open loops; do not start build work.")
    if _has_any(text, ("in bed", "resting", "rest now", "laying down", "lying down")):
        return _classification("REST", 0.9, project, task, "Preserve open loops; do not start build work.")
    if _has_any(text, ("walk with ashley", "walking with ashley", "with ashley", "family time")):
        return _classification("FAMILY", 0.9, project, task, "Preserve prior work context for later re-entry.")
    if _has_any(text, ("ecowater", "dealer", "dealership", "bdm", "central region", "water softener")):
        return _classification("WORK_ECOWATER", 0.9, project or "EcoWater", task, "Resume EcoWater work context when Noah returns.")
    if _has_any(text, ("costco", "errand", "running errands", "store visit")):
        return _classification("ERRAND", 0.85, project, task, "Preserve prior work context for later re-entry.")
    if _has_any(text, ("driving", "drive to", "on the road", "airport", "travel", "travelling", "traveling")):
        return _classification("TRAVEL", 0.85, project, task, "Preserve prior work context for later re-entry.")
    if _has_any(text, ("writing", "writer mode", "book", "chapter", "manuscript", "novel")):
        return _classification("WORK_WRITING", 0.86, project or "Writing", task, "Resume writing context and latest open loop.")
    if _has_any(text, ("oracle", "oracle.ai", "runtime", "sov1", "codex", "claude code", "back at the workstation", "workstation")):
        return _classification("WORK_ORACLE", 0.86, project or "ORACLE", task, "Generate a re-entry brief before selecting the next build action.")
    if _has_any(text, ("hearthstone", "game", "gaming", "recreation")):
        return _classification("RECREATION", 0.82, project, task, "Preserve prior work context for later re-entry.")

    return _classification("UNKNOWN", 0.2, project, task, "Ambiguous statement; do not change state without Noah correction.")


def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _classification(mode: str, confidence: float, project: str, task: str, hint: str) -> dict[str, Any]:
    return {
        "new_mode": mode if mode in MODES else "UNKNOWN",
        "confidence": float(confidence),
        "related_project": project or None,
        "active_task": task or None,
        "reentry_hint": hint,
        "inference_boundary": "explicit_statement_only",
    }


def latest_transition() -> dict[str, Any] | None:
    ensure_schema()
    with memory.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM human_state_transitions ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return _row_to_event(row) if row else None


def current_state() -> dict[str, Any]:
    event = latest_transition()
    if not event:
        return {
            "ok": True,
            "current_mode": "UNKNOWN",
            "last_transition": None,
            "continuity_gap": "no human state transition recorded yet",
            "boundary": "explicit statements and verified local events only",
        }
    return {
        "ok": True,
        "current_mode": event["new_mode"],
        "last_transition": event,
        "continuity_gap": None,
        "boundary": "explicit statements and verified local events only",
    }


def record_transition(
    source_text: str,
    *,
    source_system: str = "ORACLE.chat",
    source_receipt: str | None = None,
    human_event_time: str | None = None,
    related_project: str | None = None,
    active_task: str | None = None,
    open_loops: list[str] | None = None,
    correction_mode: str | None = None,
    authorial_authority: str = "Noah.Physical",
    canon_status: str = "event_receipt_only",
) -> dict[str, Any]:
    ensure_schema()
    source = _compact(source_text)
    classification = classify_transition(source, related_project=related_project, active_task=active_task)
    if correction_mode:
        mode = _normalize_mode(correction_mode)
        classification.update({
            "new_mode": mode,
            "confidence": 1.0,
            "reentry_hint": "Noah.Physical corrected the current human state.",
        })
    mode = classification["new_mode"]
    if mode == "UNKNOWN" and not correction_mode:
        return {
            "ok": True,
            "recorded": False,
            "reason": "ambiguous_transition_not_recorded",
            "classification": classification,
            "current_state": current_state(),
        }

    previous = latest_transition()
    previous_mode = previous["new_mode"] if previous else "UNKNOWN"
    loops = list(open_loops or _project_open_loops(classification.get("related_project")))
    timestamp = _utc_now()
    event_basis = "|".join([
        _lower(source),
        mode,
        _compact(human_event_time),
        _compact(source_system),
    ])
    dedupe_key = _sha256_text(event_basis)
    event_id = f"hst_{dedupe_key[:16]}"
    receipt = {
        "receipt_kind": "human_state_transition_receipt",
        "schema_version": "human_state.v1",
        "operation_type": "human_state_transition",
        "event_id": event_id,
        "timestamp": timestamp,
        "human_event_time": human_event_time,
        "previous_mode": previous_mode,
        "new_mode": mode,
        "source_text": source,
        "source_system": source_system,
        "source_receipt": source_receipt,
        "confidence": classification["confidence"],
        "related_project": classification.get("related_project"),
        "active_task": classification.get("active_task"),
        "open_loops": loops,
        "reentry_hint": classification.get("reentry_hint"),
        "authorial_authority": authorial_authority,
        "canon_status": canon_status,
        "external_systems_touched": False,
        "mood_inference": False,
        "ambient_monitoring": False,
    }
    receipt_hash = _json_hash(receipt)
    receipt["receipt_hash"] = receipt_hash
    try:
        with memory.get_conn() as conn:
            conn.execute(
                """
                INSERT INTO human_state_transitions (
                    event_id, timestamp, human_event_time, previous_mode, new_mode,
                    source_text, source_system, source_receipt, confidence,
                    related_project, active_task, open_loops_json, reentry_hint,
                    authorial_authority, canon_status, dedupe_key, receipt_hash,
                    receipt_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    timestamp,
                    human_event_time,
                    previous_mode,
                    mode,
                    source,
                    source_system,
                    source_receipt,
                    float(classification["confidence"]),
                    classification.get("related_project"),
                    classification.get("active_task"),
                    json.dumps(loops, ensure_ascii=False),
                    classification.get("reentry_hint"),
                    authorial_authority,
                    canon_status,
                    dedupe_key,
                    receipt_hash,
                    json.dumps(receipt, sort_keys=True, ensure_ascii=False),
                ),
            )
    except Exception as exc:
        if "UNIQUE" not in str(exc).upper():
            raise
        return {
            "ok": True,
            "recorded": False,
            "duplicate": True,
            "event": _event_by_dedupe_key(dedupe_key),
        }

    try:
        memory.append_audit_chain("human_state", "transition", receipt)
    except Exception:
        pass
    return {
        "ok": True,
        "recorded": True,
        "duplicate": False,
        "event": _event_by_dedupe_key(dedupe_key),
        "receipt": receipt,
    }


def reentry_brief() -> dict[str, Any]:
    state = current_state()
    event = state.get("last_transition")
    project = _project_snapshot((event or {}).get("related_project"))
    pending = _pending_approvals()
    open_loops = list((event or {}).get("open_loops") or [])
    open_loops.extend(project.get("open_loops") or [])
    open_loops = _dedupe_keep_order(open_loops)
    continuity_gaps = []
    if not event:
        continuity_gaps.append("No explicit human-state transition has been recorded yet.")
    if state.get("current_mode") == "UNKNOWN":
        continuity_gaps.append("Current mode is UNKNOWN; ask Noah.Physical for correction before acting.")
    recommended = (
        project.get("next_recommended_step")
        or (event or {}).get("reentry_hint")
        or "Ask Noah.Physical which lane to resume."
    )
    return {
        "ok": True,
        "last_known_mode": state.get("current_mode"),
        "time_since_last_explicit_transition": _elapsed_label((event or {}).get("timestamp")),
        "project_noah_was_working_on": project.get("project_name") or (event or {}).get("related_project"),
        "last_completed_action": project.get("last_completed_step"),
        "open_loops": open_loops,
        "items_waiting_for_approval": pending,
        "recommended_next_action": recommended,
        "continuity_gaps": continuity_gaps,
        "last_transition": event,
        "boundary": "read-only brief; no build action triggered",
    }


def _normalize_mode(mode: str) -> str:
    normalized = _compact(mode).upper().replace("-", "_").replace(" ", "_")
    if normalized not in MODES:
        raise ValueError(f"unknown human state mode: {mode}")
    return normalized


def _event_by_dedupe_key(dedupe_key: str) -> dict[str, Any] | None:
    ensure_schema()
    with memory.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM human_state_transitions WHERE dedupe_key = ?",
            (dedupe_key,),
        ).fetchone()
    return _row_to_event(row) if row else None


def _row_to_event(row: Any) -> dict[str, Any]:
    data = dict(row)
    try:
        data["open_loops"] = json.loads(data.pop("open_loops_json") or "[]")
    except Exception:
        data["open_loops"] = []
    try:
        data["receipt"] = json.loads(data.get("receipt_json") or "{}")
    except Exception:
        data["receipt"] = {}
    return data


def _project_snapshot(project_name: str | None) -> dict[str, Any]:
    try:
        import project_state
    except Exception:
        return {}
    candidates = []
    if project_name:
        candidates.append(project_name)
    candidates.extend(["ORACLE", "ORACLE.AI", "EcoWater", "Writing"])
    seen = set()
    for candidate in candidates:
        name = _compact(candidate)
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        state = project_state.load_state(name)
        if state:
            return {
                "project_name": state.project_name,
                "last_completed_step": state.last_completed_step,
                "next_recommended_step": state.next_recommended_step,
                "open_loops": _dedupe_keep_order(
                    list(state.open_questions or [])
                    + ([state.current_blocker] if state.current_blocker else [])
                    + [str(item) for item in (state.pending_candidates or [])[:5]]
                ),
                "approval_required": state.approval_required,
                "approval_reason": state.approval_reason,
            }
    return {}


def _project_open_loops(project_name: str | None) -> list[str]:
    return list((_project_snapshot(project_name).get("open_loops") or [])[:8])


def _pending_approvals(limit: int = 5) -> list[dict[str, str]]:
    try:
        from approval_center import list_pending

        pending = list_pending()
    except Exception:
        return []
    items = []
    for idx, item in enumerate(pending[:limit], 1):
        if not isinstance(item, dict):
            continue
        items.append({
            "id": str(item.get("id") or item.get("approval_id") or f"pending-{idx}"),
            "summary": _compact(item.get("summary") or item.get("title") or item.get("action") or item.get("source") or "pending approval"),
        })
    return items


def _elapsed_label(timestamp: str | None) -> str | None:
    if not timestamp:
        return None
    try:
        dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except Exception:
        return "unknown"
    seconds = max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h {minutes % 60}m"
    days = hours // 24
    return f"{days}d {hours % 24}h"


def _dedupe_keep_order(values: list[Any]) -> list[str]:
    out: list[str] = []
    seen = set()
    for value in values:
        text = _compact(value)
        key = text.lower()
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return out
