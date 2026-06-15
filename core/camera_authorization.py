"""
camera_authorization.py — bounded, in-memory camera session authorization.

ORACLE's webcam may only be read through an explicit, human-initiated
authorization that is created when Noah starts the camera and invalidated the
moment the camera stops, the track ends, the page unloads, or the device is
lost. There is NO durable authorization database: every authorization lives
only in this process and disappears on restart (fail-closed by construction).

`/api/see` must validate an authorization before any frame reaches the vision
model. A missing, unknown, invalidated, session-mismatched, or device-mismatched
authorization must be rejected WITHOUT invoking the model.
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

_LOCK = threading.Lock()
_STORE: dict[str, dict] = {}  # authorization_id -> record


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_authorization(session_id: str, device_id: Optional[str]) -> dict:
    """Create one active camera authorization bound to a session (+ device)."""
    auth_id = "cam-auth-" + uuid.uuid4().hex[:16]
    record = {
        "authorization_id": auth_id,
        "session_id": session_id or "",
        "device_id": (device_id or None),
        "created_at": _utc(),
        "active": True,
    }
    with _LOCK:
        _STORE[auth_id] = record
    return dict(record)


def validate(authorization_id: Optional[str], session_id: Optional[str],
             device_id: Optional[str]) -> tuple[bool, str]:
    """
    Return (ok, reason). Rejects, in order:
      - missing / unknown authorization
      - invalidated (camera stopped, track ended, page unloaded, device lost)
      - mismatched session id
      - mismatched device id (only when both sides know a device id)
    """
    with _LOCK:
        record = _STORE.get(authorization_id or "")
        record = dict(record) if record else None
    if not authorization_id or record is None:
        return False, "unknown_authorization"
    if not record.get("active"):
        return False, "authorization_invalidated"
    if record.get("session_id", "") != (session_id or ""):
        return False, "session_mismatch"
    rec_device = record.get("device_id")
    if rec_device and device_id and rec_device != device_id:
        return False, "device_mismatch"
    return True, "ok"


def invalidate(authorization_id: Optional[str]) -> bool:
    """Invalidate one authorization. Returns True if it existed and was active."""
    with _LOCK:
        record = _STORE.get(authorization_id or "")
        if record and record.get("active"):
            record["active"] = False
            return True
    return False


def invalidate_session(session_id: str) -> int:
    """Invalidate every active authorization for a session. Returns count."""
    count = 0
    with _LOCK:
        for record in _STORE.values():
            if record.get("session_id") == session_id and record.get("active"):
                record["active"] = False
                count += 1
    return count


def get(authorization_id: Optional[str]) -> Optional[dict]:
    with _LOCK:
        record = _STORE.get(authorization_id or "")
        return dict(record) if record else None


def _reset_for_tests() -> None:
    """Clear the store — test-only helper."""
    with _LOCK:
        _STORE.clear()
