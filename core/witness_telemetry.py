"""Manual, bounded, content-free activity telemetry for ORACLE.

The collector counts input activity but never stores key identities, typed text,
clipboard contents, URLs, camera frames, or audio. It writes only to the configured
telemetry root and is never started automatically by the runtime.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "oracle.witness_telemetry.v1"
DEFAULT_TELEMETRY_ROOT = Path(r"C:\ORACLE.AI\sandbox\telemetry")
ALLOWED_SUFFIXES = {".json", ".jsonl"}
MOUSE_KEYS = {0x01, 0x02, 0x04, 0x05, 0x06}
KEYBOARD_KEYS = tuple(vk for vk in range(0x08, 0x100) if vk not in MOUSE_KEYS)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _env_true(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in {"1", "true", "yes", "on"}


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _safe_output(root: Path, filename: str) -> Path:
    candidate = (root / filename).resolve()
    if not _inside(candidate, root):
        raise ValueError("telemetry output escapes configured root")
    if candidate.suffix.lower() not in ALLOWED_SUFFIXES:
        raise ValueError("telemetry output extension is not allowed")
    return candidate


def _process_name(pid: int) -> str:
    if pid <= 0:
        return "unknown"
    try:
        import psutil  # type: ignore

        return psutil.Process(pid).name()
    except Exception:
        return f"pid-{pid}"


def _foreground_context() -> tuple[str, str]:
    if os.name != "nt":
        return "unsupported-platform", ""
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return "unknown", ""
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(max(1, length + 1))
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    return _process_name(int(pid.value)), buffer.value


def _pressed(vk: int) -> bool:
    if os.name != "nt":
        return False
    return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)


def public_event(
    *,
    observed_at: str,
    process_name: str,
    state: str,
    keyboard_activity_count: int,
    mouse_click_count: int,
    window_title: str,
    store_window_titles: bool,
) -> dict[str, Any]:
    """Return the only event shape permitted to reach disk."""
    event: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "observed_at": observed_at,
        "process_name": process_name,
        "state": state,
        "keyboard_activity_count": int(keyboard_activity_count),
        "mouse_click_count": int(mouse_click_count),
        "canon_status": "raw_signal",
        "promotion_status": "not_promoted",
    }
    if window_title:
        event["window_title_sha256"] = _sha256_bytes(window_title.encode("utf-8"))
        if store_window_titles:
            event["window_title"] = window_title
    return event


@dataclass
class ActivitySampler:
    idle_after_seconds: float = 30.0
    store_window_titles: bool = False
    _down_keys: set[int] = field(default_factory=set)
    _down_buttons: set[int] = field(default_factory=set)
    _last_activity: float = field(default_factory=time.monotonic)

    def sample(self) -> dict[str, Any]:
        process_name, title = _foreground_context()
        current_keys = {vk for vk in KEYBOARD_KEYS if _pressed(vk)}
        current_buttons = {vk for vk in MOUSE_KEYS if _pressed(vk)}
        key_count = len(current_keys - self._down_keys)
        click_count = len(current_buttons - self._down_buttons)
        self._down_keys = current_keys
        self._down_buttons = current_buttons
        if key_count or click_count:
            self._last_activity = time.monotonic()
        state = "active" if time.monotonic() - self._last_activity < self.idle_after_seconds else "idle"
        return public_event(
            observed_at=_utc_now(),
            process_name=process_name,
            state=state,
            keyboard_activity_count=key_count,
            mouse_click_count=click_count,
            window_title=title,
            store_window_titles=self.store_window_titles,
        )


def write_run(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Write a run only to the fixed telemetry root.

    Tests replace ``DEFAULT_TELEMETRY_ROOT`` with a temporary directory. Runtime
    callers cannot supply an alternate output path.
    """
    root = DEFAULT_TELEMETRY_ROOT.resolve()
    root.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:10]
    session_path = _safe_output(root, f"session_{run_id}.jsonl")
    summary_path = _safe_output(root, f"summary_{run_id}.json")
    receipt_path = _safe_output(root, f"receipt_{run_id}.json")

    rows = list(events)
    session_payload = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    session_path.write_text(session_payload, encoding="utf-8")
    summary = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "event_count": len(rows),
        "keyboard_activity_count": sum(int(row.get("keyboard_activity_count", 0)) for row in rows),
        "mouse_click_count": sum(int(row.get("mouse_click_count", 0)) for row in rows),
        "process_seconds": {},
        "canon_status": "raw_signal",
        "promotion_status": "not_promoted",
        "content_capture": False,
    }
    for row in rows:
        name = str(row.get("process_name", "unknown"))
        summary["process_seconds"][name] = summary["process_seconds"].get(name, 0) + 1
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "operation": "manual_witness_telemetry",
        "created_at": _utc_now(),
        "run_id": run_id,
        "session_path": str(session_path),
        "summary_path": str(summary_path),
        "session_sha256": _sha256_file(session_path),
        "summary_sha256": _sha256_file(summary_path),
        "canon_status": "raw_signal",
        "promotion_status": "not_promoted",
        "external_action": False,
        "automatic_boot_start": False,
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"session": session_path, "summary": summary_path, "receipt": receipt_path, "receipt_data": receipt}


def collect(duration: float, interval: float = 1.0) -> dict[str, Any]:
    if duration <= 0 or duration > 3600:
        raise ValueError("duration must be between 0 and 3600 seconds")
    if interval < 0.1 or interval > 60:
        raise ValueError("interval must be between 0.1 and 60 seconds")
    sampler = ActivitySampler(store_window_titles=_env_true("TELEMETRY_STORE_WINDOW_TITLES"))
    events: list[dict[str, Any]] = []
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        events.append(sampler.sample())
        time.sleep(min(interval, max(0.0, deadline - time.monotonic())))
    return write_run(events)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run manual, content-free ORACLE activity telemetry")
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()
    result = collect(args.duration, args.interval)
    print(json.dumps({key: str(value) for key, value in result.items() if key != "receipt_data"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
