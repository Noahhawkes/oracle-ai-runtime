"""Thread Engine v1: Continuity Event Packet to thread-state projection.

This module gives ORACLE a small, deterministic "where were we?" layer over
Continuity Event Packets. It stores candidate thread snapshots only. It does
not call models, inspect sandbox, mutate source files, promote canon, execute
commands, or perform external actions.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from root import ROOT
except Exception:  # pragma: no cover
    ROOT = Path(__file__).resolve().parents[1]


SCHEMA_VERSION = "thread_engine.v1"
DEFAULT_THREADS_DIR = ROOT / "Memory" / "thread_engine"
DEFAULT_EVENTS_DIR = ROOT / "Memory" / "continuity_events"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _safe_thread_id(thread_id: str) -> str:
    value = _clean(thread_id)
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._-")
    return value or "untitled_thread"


def _stable_key(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=True, default=str)
    except TypeError:
        return str(value)


def _append_unique(items: list[Any], value: Any) -> None:
    if value in (None, "", [], {}):
        return
    key = _stable_key(value)
    if all(_stable_key(item) != key for item in items):
        items.append(value)


def _coerce_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _title_from_event(event_packet: dict[str, Any]) -> str:
    intent = event_packet.get("user_intent")
    if isinstance(intent, str):
        title = intent
    elif isinstance(intent, dict):
        title = (
            intent.get("summary")
            or intent.get("user_text_preview")
            or intent.get("route_type")
            or intent.get("effective_route")
            or ""
        )
    else:
        title = ""
    if not title:
        user_input = event_packet.get("user_input")
        if isinstance(user_input, dict):
            title = user_input.get("preview") or user_input.get("text") or ""
    return (_clean(title) or "Untitled Thread")[:80]


def _correction_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        if value.get("detected_correction_request"):
            return [dict(value)]
        return []
    out: list[dict[str, Any]] = []
    for item in _coerce_list(value):
        if isinstance(item, dict):
            out.append(dict(item))
        elif item:
            out.append({"text": str(item)})
    return out


def _evidence_items(value: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for record in _coerce_list(value.get("records_used")):
            if isinstance(record, dict):
                out.append(dict(record))
        if not out:
            compact = {
                "records_used_count": value.get("records_used_count"),
                "sources_proven_used": value.get("sources_proven_used"),
            }
            if compact["records_used_count"] or compact["sources_proven_used"]:
                out.append(compact)
        return out
    for item in _coerce_list(value):
        if isinstance(item, dict):
            out.append(dict(item))
        elif item:
            out.append({"value": str(item)})
    return out


def _next_action_from_event(event_packet: dict[str, Any]) -> str | None:
    pointer = event_packet.get("return_pointer") or event_packet.get("resume_point")
    if isinstance(pointer, dict):
        route = pointer.get("effective_route") or pointer.get("route_type")
        if route:
            return f"Resume via {route}"
    return None


@dataclass
class ContinuityThread:
    """First-class candidate thread state derived from event packets."""

    thread_id: str
    title: str
    aliases: list[str] = field(default_factory=list)
    timeline: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    facts: list[Any] = field(default_factory=list)
    corrections: list[dict[str, Any]] = field(default_factory=list)
    linked_documents: list[str] = field(default_factory=list)
    related_threads: list[str] = field(default_factory=list)
    status: str = "active"
    next_action: str | None = None
    evidence_refs: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    schema_version: str = SCHEMA_VERSION
    canon_status: str = "candidate"
    promotion_status: str = "not_promoted"
    approval_authority: str = "Noah.Physical"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContinuityThread":
        allowed = {item.name for item in fields(cls)}
        payload = {key: value for key, value in dict(data or {}).items() if key in allowed}
        return cls(**payload)


class ThreadEngine:
    """Manage thread snapshots derived from Continuity Event Packets."""

    def __init__(self, threads_dir: str | Path | None = None) -> None:
        self.threads_dir = Path(threads_dir) if threads_dir is not None else DEFAULT_THREADS_DIR
        self.threads_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, thread_id: str) -> Path:
        return self.threads_dir / f"{_safe_thread_id(thread_id)}.json"

    def load_thread(self, thread_id: str) -> ContinuityThread | None:
        path = self._get_path(thread_id)
        if not path.exists():
            return None
        try:
            return ContinuityThread.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, TypeError):
            return None

    def save_thread(self, thread: ContinuityThread) -> Path:
        thread.thread_id = _safe_thread_id(thread.thread_id)
        thread.updated_at = _now()
        thread.schema_version = SCHEMA_VERSION
        path = self._get_path(thread.thread_id)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(thread.to_dict(), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(path)
        return path

    def update_from_event(self, thread_id: str, event_packet: dict[str, Any]) -> ContinuityThread:
        safe_id = _safe_thread_id(thread_id)
        thread = self.load_thread(safe_id) or ContinuityThread(
            thread_id=safe_id,
            title=_title_from_event(event_packet),
        )

        event_id = _clean(event_packet.get("event_id"))
        if event_id:
            _append_unique(thread.timeline, event_id)

        for claim in _coerce_list(event_packet.get("claims_extracted")):
            _append_unique(thread.facts, claim)

        for uncertainty in _coerce_list(event_packet.get("uncertainties")):
            if isinstance(uncertainty, dict):
                text = _clean(uncertainty.get("text") or uncertainty.get("value") or uncertainty)
            else:
                text = _clean(uncertainty)
            if text:
                _append_unique(thread.open_questions, text)

        for correction in _correction_items(event_packet.get("corrections")):
            _append_unique(thread.corrections, correction)

        for evidence in _evidence_items(event_packet.get("evidence_used") or event_packet.get("sources")):
            _append_unique(thread.evidence_refs, evidence)
            path = _clean(evidence.get("path")) if isinstance(evidence, dict) else ""
            if path:
                _append_unique(thread.linked_documents, path)

        if thread.next_action is None:
            thread.next_action = _next_action_from_event(event_packet)

        self.save_thread(thread)
        return thread

    def update_from_latest_event(
        self,
        thread_id: str,
        *,
        events_dir: str | Path | None = None,
    ) -> ContinuityThread | None:
        root = Path(events_dir) if events_dir is not None else DEFAULT_EVENTS_DIR
        latest = root / "latest.json"
        if not latest.exists():
            return None
        try:
            event_packet = json.loads(latest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return self.update_from_event(thread_id, event_packet)

    def rebuild_from_events(
        self,
        thread_id: str,
        *,
        events_dir: str | Path | None = None,
        limit: int | None = None,
    ) -> ContinuityThread | None:
        root = Path(events_dir) if events_dir is not None else DEFAULT_EVENTS_DIR
        if not root.exists():
            return None
        event_paths = sorted(
            path for path in root.glob("cep_*.json")
            if path.name not in {"latest.json", "index.jsonl"}
        )
        if limit is not None:
            event_paths = event_paths[-max(0, int(limit)):]
        thread: ContinuityThread | None = None
        for path in event_paths:
            try:
                packet = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            thread = self.update_from_event(thread_id, packet)
        return thread

    def get_summary(self, thread_id: str) -> dict[str, Any]:
        thread = self.load_thread(thread_id)
        if not thread:
            return {"status": "NOT_FOUND", "thread_id": _safe_thread_id(thread_id)}

        return {
            "schema_version": thread.schema_version,
            "thread_id": thread.thread_id,
            "title": thread.title,
            "status": thread.status,
            "event_count": len(thread.timeline),
            "latest_event_id": thread.timeline[-1] if thread.timeline else None,
            "decisions": thread.decisions,
            "open_questions": thread.open_questions,
            "next_action": thread.next_action,
            "latest_facts": thread.facts[-5:],
            "evidence_ref_count": len(thread.evidence_refs),
            "linked_documents": thread.linked_documents,
            "canon_status": thread.canon_status,
            "promotion_status": thread.promotion_status,
            "approval_authority": thread.approval_authority,
            "updated_at": thread.updated_at,
        }

    def where_were_we(self, thread_id: str) -> dict[str, Any]:
        summary = self.get_summary(thread_id)
        if summary.get("status") == "NOT_FOUND":
            return summary
        return {
            "status": "FOUND",
            "thread_id": summary["thread_id"],
            "title": summary["title"],
            "latest_event_id": summary["latest_event_id"],
            "open_questions": summary["open_questions"],
            "next_action": summary["next_action"],
            "latest_facts": summary["latest_facts"],
            "evidence_ref_count": summary["evidence_ref_count"],
            "boundary": "candidate thread projection from continuity event packets; no canon promotion",
        }


__all__ = [
    "ContinuityThread",
    "DEFAULT_EVENTS_DIR",
    "DEFAULT_THREADS_DIR",
    "SCHEMA_VERSION",
    "ThreadEngine",
]
