"""Consent-gated RenderedReality Live Witness metadata.

This module is intentionally narrow:
* default mode is off
* no observation happens while off
* metadata-only mode reads OBS/window metadata only
* no screenshots, audio, video, keystrokes, or clipboard contents are captured
* receipts are written only when explicitly requested
"""

from __future__ import annotations

import json
import platform
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from root_map import RATIFIED_STATE_ROOT
except Exception:  # pragma: no cover - import fallback for direct execution
    RATIFIED_STATE_ROOT = Path(r"C:\Oracle\state")


VALID_MODES = {"off", "metadata_only", "human_confirmed_session"}
DEFAULT_MODE = "off"
STATE_ROOT = Path(RATIFIED_STATE_ROOT)
RECEIPTS_DIR = STATE_ROOT / "receipts"
SOURCES_DIR = STATE_ROOT / "sources"
LATEST_MANIFEST = SOURCES_DIR / "oracle_source_manifest_latest.json"

_WITNESS_MODE = DEFAULT_MODE
_LAST_CONTEXT: dict[str, Any] | None = None
_LAST_RECEIPT_PATH: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _receipt_id() -> str:
    return f"rrw-{uuid.uuid4().hex[:12]}"


def _safe_bool(value: Any) -> bool:
    return bool(value) if value is not None else False


def get_witness_mode() -> str:
    return _WITNESS_MODE


def set_witness_mode(mode: str) -> dict[str, Any]:
    """Set process-local consent mode. Enabling does not itself observe."""
    normalized = str(mode or "").strip().lower()
    if normalized not in VALID_MODES:
        raise ValueError(f"invalid RenderedReality Live Witness mode: {mode}")

    global _WITNESS_MODE
    _WITNESS_MODE = normalized

    manifest_paths: dict[str, str] = {}
    warnings: list[str] = []
    if normalized != "off":
        try:
            manifest_paths = ensure_manifest_entry()
        except Exception as exc:
            warnings.append(f"source manifest integration unavailable: {type(exc).__name__}: {exc}")

    status = get_witness_status()
    status["manifest_paths"] = manifest_paths
    status["warnings"].extend(warnings)
    return status


def get_witness_status() -> dict[str, Any]:
    return {
        "name": "RenderedReality Live Witness",
        "mode": _WITNESS_MODE,
        "default_mode": DEFAULT_MODE,
        "enabled": _WITNESS_MODE != "off",
        "allowed_modes": sorted(VALID_MODES),
        "last_context": _LAST_CONTEXT,
        "last_session_receipt_path": _LAST_RECEIPT_PATH,
        "governance_line": (
            "RenderedReality Live Witness observes metadata only when Noah.Physical enables it. "
            "It does not record the screen, audio, video, keystrokes, or clipboard by default. "
            "It writes receipts, not surveillance archives."
        ),
        "writes_allowed": {
            "receipts": str(RECEIPTS_DIR),
            "source_manifests": str(SOURCES_DIR),
        },
        "screenshots_stored_by_default": False,
        "audio_recorded": False,
        "video_recorded": False,
        "keystrokes_captured": False,
        "clipboard_captured": False,
        "warnings": [],
    }


def detect_obs_running() -> bool:
    if platform.system().lower() != "windows":
        return False
    for image in ("obs64.exe", "obs32.exe", "obs.exe"):
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {image}", "/NH"],
                capture_output=True,
                text=True,
                timeout=1.5,
                check=False,
            )
            if image.lower() in (result.stdout or "").lower():
                return True
        except Exception:
            continue
    return False


def get_obs_metadata() -> dict[str, Any]:
    timestamp = _now()
    running = detect_obs_running()
    base = {
        "obs_running": running,
        "obs_websocket_available": False,
        "current_scene_name": None,
        "recording_active": None,
        "streaming_active": None,
        "source_names": [],
        "timestamp": timestamp,
        "warning": None,
    }
    if not running:
        return base

    try:
        from obs_runtime_context import get_obs_context

        obs = get_obs_context()
    except Exception as exc:
        base["warning"] = f"OBS detected, but OBS WebSocket is unavailable or not authorized. {type(exc).__name__}: {exc}"
        return base

    if not obs.get("available"):
        base["warning"] = "OBS detected, but OBS WebSocket is unavailable or not authorized."
        return base

    base.update(
        {
            "obs_websocket_available": True,
            "current_scene_name": obs.get("scene"),
            "recording_active": obs.get("recording"),
            "streaming_active": obs.get("streaming"),
            "source_names": [
                str(item.get("name"))
                for item in (obs.get("sources") or [])
                if item.get("name")
            ],
        }
    )
    return base


def _process_name_from_pid(pid: int) -> str | None:
    if not pid:
        return None
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-Process -Id {int(pid)} -ErrorAction Stop).ProcessName",
            ],
            capture_output=True,
            text=True,
            timeout=1.5,
            check=False,
        )
        value = (result.stdout or "").strip().splitlines()
        return value[0].strip() if value else None
    except Exception:
        return None


def get_active_window_metadata() -> dict[str, Any]:
    timestamp = _now()
    base = {
        "active_window_title": None,
        "active_process_name": None,
        "timestamp": timestamp,
        "confidence": "low",
        "observation_mode": "metadata_only",
        "warning": None,
    }
    if platform.system().lower() != "windows":
        base["warning"] = "Current-window metadata is implemented for Windows only."
        return base

    try:
        import ctypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            base["warning"] = "No active foreground window handle was available."
            return base

        length = user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)

        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        base.update(
            {
                "active_window_title": buffer.value or None,
                "active_process_name": _process_name_from_pid(int(pid.value)),
                "confidence": "medium" if (buffer.value or pid.value) else "low",
            }
        )
    except Exception as exc:
        base["warning"] = f"Current-window metadata unavailable: {type(exc).__name__}: {exc}"
    return base


def refresh_live_context(
    *,
    obs_provider: Callable[[], dict[str, Any]] | None = None,
    window_provider: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return live metadata only when consent mode is enabled."""
    if _WITNESS_MODE == "off":
        return {
            "operation": "rendered_reality_live_witness",
            "mode": "off",
            "enabled": False,
            "timestamp": _now(),
            "observation_skipped": True,
            "obs": None,
            "window": None,
            "warnings": ["RenderedReality Live Witness is OFF; no OBS or window context was read."],
        }

    obs_fn = obs_provider or get_obs_metadata
    window_fn = window_provider or get_active_window_metadata
    obs = obs_fn()
    window = window_fn()
    warnings = [
        str(item)
        for item in (obs.get("warning"), window.get("warning"))
        if item
    ]
    context = {
        "operation": "rendered_reality_live_witness",
        "mode": _WITNESS_MODE,
        "enabled": True,
        "timestamp": _now(),
        "observation_skipped": False,
        "obs": obs,
        "window": window,
        "warnings": warnings,
        "screenshots_stored": False,
        "audio_recorded": False,
        "video_recorded": False,
        "keystrokes_captured": False,
        "clipboard_captured": False,
    }

    global _LAST_CONTEXT
    _LAST_CONTEXT = context
    return context


def write_session_receipt(
    *,
    notes: str = "",
    source_manifest_id: str = "rendered_reality_live_witness",
    obs_provider: Callable[[], dict[str, Any]] | None = None,
    window_provider: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if _WITNESS_MODE == "off":
        raise PermissionError("RenderedReality Live Witness is OFF; no session receipt was written.")

    context = refresh_live_context(obs_provider=obs_provider, window_provider=window_provider)
    obs = context.get("obs") or {}
    window = context.get("window") or {}
    receipt = {
        "receipt_id": _receipt_id(),
        "timestamp": _now(),
        "operation": "rendered_reality_live_witness",
        "witness_mode": _WITNESS_MODE,
        "obs_running": _safe_bool(obs.get("obs_running")),
        "obs_scene": obs.get("current_scene_name"),
        "obs_recording_active": obs.get("recording_active"),
        "obs_streaming_active": obs.get("streaming_active"),
        "active_window_title": window.get("active_window_title"),
        "active_process_name": window.get("active_process_name"),
        "source_manifest_id": source_manifest_id,
        "files_moved": 0,
        "files_deleted": 0,
        "files_renamed": 0,
        "files_synced": 0,
        "git_commits": 0,
        "git_pushes": 0,
        "human_authority": "Noah.Physical",
        "notes": notes,
        "warnings": list(context.get("warnings") or []),
        "no_screenshots_stored": True,
        "no_audio_recorded": True,
        "no_video_recorded": True,
        "no_keystrokes_captured": True,
        "no_clipboard_captured": True,
    }
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RECEIPTS_DIR / f"rendered_reality_session_{_stamp()}.json"
    path.write_text(json.dumps(receipt, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")

    global _LAST_RECEIPT_PATH
    _LAST_RECEIPT_PATH = str(path)
    receipt["receipt_path"] = str(path)
    return receipt


def _manifest_entry() -> dict[str, Any]:
    return {
        "source_id": "rendered_reality_live_witness",
        "full_path": "local://rendered_reality_live_witness",
        "source_type": "live_context",
        "exists": True,
        "inside_cloud_sync": False,
        "is_git_repo": False,
        "git_branch": "",
        "git_head_sha": "",
        "git_remote_urls": [],
        "git_status_summary": "",
        "file_count": 0,
        "directory_count": 0,
        "approximate_size": "0 B",
        "approximate_size_bytes": 0,
        "newest_modified_timestamp": _now(),
        "contains_oracle_runtime_code": False,
        "contains_oracle_state": False,
        "contains_logs": False,
        "contains_doctrine": False,
        "contains_backups": False,
        "contains_private_evidence": False,
        "contains_media": False,
        "contains_env_or_secret_like_files": False,
        "retrieval_allowed": True,
        "write_allowed": False,
        "canonical_status": "linked_source",
        "recommended_role": "live_context_witness",
        "confidence": "medium",
        "evidence_state": "DISCOVERED" if _WITNESS_MODE == "off" else "METADATA_READ",
        "notes": (
            "Consent-gated live working context. Metadata only. "
            "No screenshots, audio, video, or keystrokes captured by default."
        ),
    }


def ensure_manifest_entry() -> dict[str, str]:
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    if LATEST_MANIFEST.exists():
        try:
            manifest = json.loads(LATEST_MANIFEST.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}
    else:
        manifest = {}

    if not isinstance(manifest, dict):
        manifest = {}
    manifest.setdefault("manifest_name", "ORACLE Universal Source Link Map")
    manifest.setdefault("mode", "read_only_source_linking")
    manifest["updated_at"] = _now()
    manifest["rendered_reality_live_witness"] = {
        "mode": _WITNESS_MODE,
        "write_allowed": False,
        "default_mode": DEFAULT_MODE,
    }

    sources = manifest.get("sources")
    if not isinstance(sources, list):
        sources = []
    entry = _manifest_entry()
    replaced = False
    for idx, source in enumerate(sources):
        if isinstance(source, dict) and source.get("source_id") == entry["source_id"]:
            sources[idx] = entry
            replaced = True
            break
    if not replaced:
        sources.append(entry)
    manifest["sources"] = sources
    manifest["source_count"] = len(sources)

    timestamp_path = SOURCES_DIR / f"oracle_source_manifest_{_stamp()}.json"
    text = json.dumps(manifest, indent=2, ensure_ascii=True, sort_keys=True) + "\n"
    timestamp_path.write_text(text, encoding="utf-8")
    LATEST_MANIFEST.write_text(text, encoding="utf-8")
    return {
        "manifest_path": str(timestamp_path),
        "latest_manifest_path": str(LATEST_MANIFEST),
    }


if __name__ == "__main__":
    print(json.dumps(get_witness_status(), indent=2, ensure_ascii=True))
