"""Typed current-observation receipts for ORACLE.

This module is deliberately narrow. It answers questions about what is visible
or active *right now* only from a fresh local observation receipt. Historical
screenshots, project state, inferred tasks, ambient memory, and model
availability are not accepted as evidence of current observation.
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
MEMORY = ROOT / "Memory"
RECEIPT_PATH = MEMORY / "current_observation_receipt.json"
RECEIPT_LOG_PATH = MEMORY / "current_observation_receipts.jsonl"

SCHEMA_VERSION = 1
DEFAULT_TTL_SECONDS = float(os.environ.get("ORACLE_CURRENT_OBSERVATION_TTL", "30"))

OBSERVATION_FIELDS = (
    "application",
    "window_title",
    "visual_observation",
    "screen_text",
)

FRESH_STATUSES = {"verified", "live"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _receipt_id() -> str:
    return f"obs-{uuid.uuid4().hex[:12]}"


@dataclass
class ObservationField:
    value: Any
    status: str
    source: str
    observed_at: str | None
    expires_at: str | None
    receipt_id: str
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["rendered_value"] = "UNKNOWN" if data.get("value") is None else data.get("value")
        return data


@dataclass
class ObservationReceipt:
    receipt_id: str
    source: str
    observed_at: str
    expires_at: str
    ttl_seconds: float
    fields: dict[str, ObservationField]
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "receipt_id": self.receipt_id,
            "source": self.source,
            "observed_at": self.observed_at,
            "expires_at": self.expires_at,
            "ttl_seconds": self.ttl_seconds,
            "fields": {name: item.to_dict() for name, item in self.fields.items()},
            "metadata": self.metadata,
        }


def _unknown_field(
    name: str,
    *,
    source: str,
    reason: str,
    receipt_id: str = "",
    observed_at: str | None = None,
    expires_at: str | None = None,
) -> ObservationField:
    return ObservationField(
        value=None,
        status="unknown",
        source=source,
        observed_at=observed_at,
        expires_at=expires_at,
        receipt_id=receipt_id,
        reason=reason or f"{name} not observed",
    )


def create_observation_receipt(
    *,
    source: str,
    fields: dict[str, Any],
    ttl_seconds: float | None = None,
    metadata: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> ObservationReceipt:
    """Create a typed receipt. Missing/null fields remain null, never inferred."""
    if not source:
        raise ValueError("source is required")
    observed = now or _now()
    ttl = DEFAULT_TTL_SECONDS if ttl_seconds is None else float(ttl_seconds)
    expires = observed + timedelta(seconds=max(ttl, 0.0))
    rid = _receipt_id()
    observed_at = _iso(observed)
    expires_at = _iso(expires)

    typed_fields: dict[str, ObservationField] = {}
    for name in OBSERVATION_FIELDS:
        value = fields.get(name)
        if value is None or (isinstance(value, str) and not value.strip()):
            typed_fields[name] = _unknown_field(
                name,
                source=source,
                reason="field not supplied by current observation source",
                receipt_id=rid,
                observed_at=observed_at,
                expires_at=expires_at,
            )
            continue
        typed_fields[name] = ObservationField(
            value=value,
            status="verified",
            source=source,
            observed_at=observed_at,
            expires_at=expires_at,
            receipt_id=rid,
        )

    return ObservationReceipt(
        receipt_id=rid,
        source=source,
        observed_at=observed_at,
        expires_at=expires_at,
        ttl_seconds=ttl,
        fields=typed_fields,
        metadata=metadata or {},
    )


def save_observation_receipt(receipt: ObservationReceipt, *, path: Path | None = None) -> dict[str, Any]:
    """Persist the latest receipt and append a JSONL audit row."""
    target = path or RECEIPT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = receipt.to_dict()
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    try:
        log_path = RECEIPT_LOG_PATH if path is None else target.with_suffix(".jsonl")
        with log_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")
    except Exception:
        pass
    return payload


def record_webcam_observation(
    result: dict[str, Any],
    *,
    ttl_seconds: float | None = None,
    path: Path | None = None,
) -> dict[str, Any] | None:
    """Convert a successful /api/see result into a current visual receipt."""
    if not result.get("available") or not result.get("observation"):
        return None
    receipt = create_observation_receipt(
        source="/api/see:webcam_frame",
        fields={
            "visual_observation": str(result.get("observation") or "").strip(),
            # A webcam frame does not prove the active application or window.
            "application": None,
            "window_title": None,
            "screen_text": None,
        },
        ttl_seconds=ttl_seconds,
        metadata={
            "model": result.get("model"),
            "raw_frame_stored": False,
        },
    )
    return save_observation_receipt(receipt, path=path)


def _active_window() -> tuple[str | None, str | None]:
    """Read the LIVE foreground window (process name, title). Windows only.
    Returns (None, None) on any failure or non-Windows platform. This is a live,
    on-demand read of the current window — not a stored stream, not history."""
    try:
        import ctypes
        import os as _os
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None, None
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = (buf.value or "").strip() or None
        app = None
        try:
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
            if handle:
                size = ctypes.c_ulong(260)
                pbuf = ctypes.create_unicode_buffer(size.value)
                if kernel32.QueryFullProcessImageNameW(handle, 0, pbuf, ctypes.byref(size)):
                    app = _os.path.basename(pbuf.value) or None
                kernel32.CloseHandle(handle)
        except Exception:
            pass
        return app, title
    except Exception:
        return None, None


def capture_active_window_observation(*, path: Path | None = None) -> dict[str, Any] | None:
    """Capture the live foreground window into a fresh current-observation
    receipt so `application` and `window_title` reflect what is on screen RIGHT
    NOW — verified, receipted, on-demand. Visual/screen_text stay UNKNOWN unless
    a vision frame is supplied (no fabrication). Returns None if nothing readable."""
    app, title = _active_window()
    if not app and not title:
        return None
    receipt = create_observation_receipt(
        source="active_window:live_foreground",
        fields={"application": app, "window_title": title,
                "visual_observation": None, "screen_text": None},
        metadata={"capture": "live_foreground_window_on_demand", "raw_frame_stored": False},
    )
    return save_observation_receipt(receipt, path=path)


def load_latest_receipt(*, path: Path | None = None) -> dict[str, Any] | None:
    target = path or RECEIPT_PATH
    try:
        if not target.exists():
            return None
        data = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
            return None
        return data
    except Exception:
        return None


def _state_from_missing(reason: str) -> dict[str, Any]:
    fields = {
        name: _unknown_field(name, source="current_observation_receipt", reason=reason).to_dict()
        for name in OBSERVATION_FIELDS
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso(_now()),
        "receipt_id": None,
        "receipt_status": "missing",
        "fresh": False,
        "expired": False,
        "observed_at": None,
        "expires_at": None,
        "fields": fields,
        "unknown_fields": list(OBSERVATION_FIELDS),
        "blocked_sources": [
            "historical_screenshot",
            "project_state",
            "inferred_task",
            "available_model",
            "ambient_memory",
        ],
        "boundary": "When current evidence is unavailable, dependent claims remain UNKNOWN.",
    }


def current_observation_state(
    *,
    receipt: dict[str, Any] | None = None,
    path: Path | None = None,
    now: datetime | None = None,
    live_capture: bool = False,
) -> dict[str, Any]:
    """Return current observation state with strict null propagation.

    When live_capture is True and no fresh receipt exists, the live foreground
    window (application + title) is captured on demand so those fields reflect
    what is on screen now instead of UNKNOWN. Visual/screen_text still require a
    real frame — never inferred."""
    if live_capture and receipt is None:
        existing = load_latest_receipt(path=path)
        fresh = False
        if existing:
            exp = _parse_iso(str(existing.get("expires_at") or ""))
            fresh = exp is not None and exp > (now or _now())
        if not fresh:
            try:
                capture_active_window_observation(path=path)
            except Exception:
                pass
    data = receipt if receipt is not None else load_latest_receipt(path=path)
    if data is None:
        return _state_from_missing("no current observation receipt exists")

    generated = now or _now()
    expires = _parse_iso(str(data.get("expires_at") or ""))
    observed = str(data.get("observed_at") or "") or None
    rid = str(data.get("receipt_id") or "")
    expired = expires is None or expires <= generated

    if expired:
        state = _state_from_missing("latest current observation receipt is expired")
        state.update({
            "generated_at": _iso(generated),
            "receipt_id": rid or None,
            "receipt_status": "expired",
            "expired": True,
            "observed_at": observed,
            "expires_at": str(data.get("expires_at") or "") or None,
        })
        for field in state["fields"].values():
            field["receipt_id"] = rid
            field["observed_at"] = observed
            field["expires_at"] = str(data.get("expires_at") or "") or None
        return state

    raw_fields = data.get("fields") if isinstance(data.get("fields"), dict) else {}
    fields: dict[str, dict[str, Any]] = {}
    unknown_fields: list[str] = []
    for name in OBSERVATION_FIELDS:
        raw = raw_fields.get(name) if isinstance(raw_fields.get(name), dict) else {}
        value = raw.get("value")
        status = str(raw.get("status") or "unknown").lower()
        if value is None or status not in FRESH_STATUSES:
            unknown_fields.append(name)
            fields[name] = _unknown_field(
                name,
                source=str(raw.get("source") or data.get("source") or "current_observation_receipt"),
                reason=str(raw.get("reason") or "field has no fresh verified value"),
                receipt_id=rid,
                observed_at=observed,
                expires_at=str(data.get("expires_at") or "") or None,
            ).to_dict()
            continue
        fields[name] = ObservationField(
            value=value,
            status="verified",
            source=str(raw.get("source") or data.get("source") or "current_observation_receipt"),
            observed_at=str(raw.get("observed_at") or observed or ""),
            expires_at=str(raw.get("expires_at") or data.get("expires_at") or ""),
            receipt_id=str(raw.get("receipt_id") or rid),
            reason=str(raw.get("reason") or ""),
        ).to_dict()

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso(generated),
        "receipt_id": rid or None,
        "receipt_status": "fresh",
        "fresh": True,
        "expired": False,
        "observed_at": observed,
        "expires_at": str(data.get("expires_at") or "") or None,
        "fields": fields,
        "unknown_fields": unknown_fields,
        "blocked_sources": [
            "historical_screenshot",
            "project_state",
            "inferred_task",
            "available_model",
            "ambient_memory",
        ],
        "boundary": "When current evidence is unavailable, dependent claims remain UNKNOWN.",
    }


def rendered_value(state: dict[str, Any], field: str) -> str:
    item = ((state.get("fields") or {}).get(field) or {})
    value = item.get("value")
    return "UNKNOWN" if value is None else str(value)


def format_current_observation_response(state: dict[str, Any] | None = None) -> str:
    s = state or current_observation_state(live_capture=True)
    receipt = s.get("receipt_id") or "NONE"
    observed = s.get("observed_at") or "UNKNOWN"
    expires = s.get("expires_at") or "UNKNOWN"
    lines = [
        "CURRENT_OBSERVATION",
        f"receipt_id: {receipt}",
        f"receipt_status: {s.get('receipt_status') or 'UNKNOWN'}",
        f"observed_at: {observed}",
        f"expires_at: {expires}",
        f"application: {rendered_value(s, 'application')}",
        f"window_title: {rendered_value(s, 'window_title')}",
        f"visual_observation: {rendered_value(s, 'visual_observation')}",
        f"screen_text: {rendered_value(s, 'screen_text')}",
        "blocked_sources: historical_screenshot, project_state, inferred_task, available_model, ambient_memory",
        "boundary: When current evidence is unavailable, dependent claims remain UNKNOWN.",
    ]
    return "\n".join(lines)


def asks_current_observation_question(text: str) -> bool:
    lower = (text or "").lower()
    if not lower.strip():
        return False
    phrases = (
        "what application",
        "what app",
        "which app",
        "what window",
        "which window",
        "what program",
        "what am i using",
        "what am i looking at",
        "what is on my screen",
        "what's on my screen",
        "what do you see",
        "can you see me",
        "can you see my screen",
        "current observation",
        "visual observation",
    )
    return any(phrase in lower for phrase in phrases)


def enforce_current_observation_boundary(user_text: str, reply: str) -> str:
    """Replace model output for current-observation questions with receipt truth."""
    if not asks_current_observation_question(user_text):
        return reply
    return format_current_observation_response()


if __name__ == "__main__":
    print(format_current_observation_response())
