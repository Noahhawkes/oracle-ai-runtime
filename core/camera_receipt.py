"""
camera_receipt.py — provenance receipts for explicit camera observations.

Every LOOK ONCE observation produces exactly one receipt. The receipt must
exist (be written to disk) BEFORE the observation is published to chat. If the
receipt cannot be written, the caption is not shown as an ORACLE response.

A camera observation is INFERENCE from a model caption, never verified fact.
Raw frames are never stored. The caption is not appended to durable JSONL
memory: only the single latest receipt is kept (retention: ephemeral_current).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
RECEIPT_PATH = ROOT / "Memory" / "camera_observation_receipt.json"

SCHEMA_VERSION = 1
SOURCE_TYPE = "browser_camera"
EVIDENCE_CLASS = "camera_model_observation"
RETENTION_POLICY = "ephemeral_current"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_receipt(
    *,
    observation_text: Optional[str],
    correlation_id: Optional[str],
    session_id: Optional[str],
    authorization_id: Optional[str],
    device_id: Optional[str],
    track_label: Optional[str],
    model: Optional[str],
    confidence: Optional[str],
    published_to_chat: bool,
    user_requested: bool = True,
    error: Optional[str] = None,
) -> dict[str, Any]:
    """Build a complete camera observation receipt (raw frame never stored)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "observation_id": "cam-obs-" + uuid.uuid4().hex[:16],
        "correlation_id": correlation_id or None,
        "captured_at_utc": _utc(),
        "session_id": session_id or None,
        "authorization_id": authorization_id or None,
        "device_id": device_id or "UNKNOWN",
        "track_label": track_label or "UNKNOWN",
        "source_type": SOURCE_TYPE,
        "model": model or None,
        "evidence_class": EVIDENCE_CLASS,
        "confidence": confidence,
        "user_requested": bool(user_requested),
        "raw_frame_stored": False,
        "published_to_chat": bool(published_to_chat),
        "retention_policy": RETENTION_POLICY,
        "observation_text": observation_text,
        "error": error,
    }


def save_receipt(receipt: dict[str, Any], *, path: Optional[Path] = None) -> dict[str, Any]:
    """
    Persist the latest receipt (overwrite — ephemeral_current, no durable log).
    Raises on failure so callers can refuse to publish an unreceipted caption.
    """
    target = path or RECEIPT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt


def load_latest(*, path: Optional[Path] = None) -> Optional[dict[str, Any]]:
    target = path or RECEIPT_PATH
    try:
        if not target.exists():
            return None
        data = json.loads(target.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None
