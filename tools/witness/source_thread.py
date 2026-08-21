"""Append-only canonical source thread for ORACLE's OBS/media evidence."""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

THREAD_ID = "oracle_obs_media_thread_v1"
THREAD_DIR = Path(r"C:\Oracle\state\threads")
THREAD_PATH = THREAD_DIR / f"{THREAD_ID}.jsonl"
LOCK_PATH = THREAD_DIR / f"{THREAD_ID}.lock"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _acquire_lock(timeout_s: float = 10.0) -> int:
    THREAD_DIR.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            return os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                if time.time() - LOCK_PATH.stat().st_mtime > 60:
                    LOCK_PATH.unlink()
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"timed out waiting for source-thread lock: {LOCK_PATH}")
            time.sleep(0.05)


def append_event(
    event_type: str,
    *,
    source_path: str | Path | None,
    content: dict[str, Any],
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one evidence event and return the exact stored record."""
    record = {
        "event_id": str(uuid.uuid4()),
        "thread_id": THREAD_ID,
        "ts_utc": _utc_now(),
        "event_type": event_type,
        "source_path": str(source_path) if source_path else None,
        "provenance": provenance or {},
        "content": content,
        "canon_status": "candidate",
    }
    lock_fd = _acquire_lock()
    try:
        with THREAD_PATH.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    finally:
        os.close(lock_fd)
        try:
            LOCK_PATH.unlink()
        except FileNotFoundError:
            pass
    return record
