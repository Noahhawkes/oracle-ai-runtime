"""Local-only OBS live transcript support for ORACLE SourceMap.

This module finds the active OBS recording from local OBS logs, detects whether
trusted local transcription support exists, and writes transcript receipts under
the ratified private state root. It never uploads media, never copies raw video,
and never falls back to cloud transcription.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from root_map import RATIFIED_STATE_ROOT
except Exception:  # pragma: no cover - direct execution fallback
    RATIFIED_STATE_ROOT = Path(r"C:\Oracle\state")


STATE_ROOT = Path(RATIFIED_STATE_ROOT)
TRANSCRIPTS_DIR = STATE_ROOT / "transcripts" / "obs"
RECEIPTS_DIR = STATE_ROOT / "receipts"
OBS_LOG_DIR = Path(os.environ.get("APPDATA", r"C:\Users\noahh\AppData\Roaming")) / "obs-studio" / "logs"

VIDEO_SUFFIXES = {".mkv", ".mp4", ".mov", ".flv", ".ts", ".m4v"}
TRANSCRIPT_SUFFIXES = {".txt", ".md", ".srt", ".vtt", ".json"}
MAX_TRANSCRIPT_CHARS = 250_000
WHISPER_CPP_ENV_VARS = (
    "ORACLE_WHISPER_CPP_EXE",
    "ORACLE_WHISPER_CPP_PATH",
    "ORACLE_WHISPER_CPP_BINARY",
)
WHISPER_CPP_BINARY_NAMES = (
    "whisper-cli",
    "whisper-cli.exe",
    "whisper.cpp",
    "whisper.cpp.exe",
    "whisper-cpp",
    "whisper-cpp.exe",
)

_WRITING_RE = re.compile(r"Writing file ['\"](?P<path>[^'\"]+)['\"]", re.IGNORECASE)
_STOPPED_RE = re.compile(r"Output of file ['\"](?P<path>[^'\"]+)['\"] stopped", re.IGNORECASE)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _path_key(path: Path | str) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def _obs_path(value: str) -> Path:
    return Path(value.replace("/", "\\"))


def _file_meta(path: Path | None) -> dict[str, Any]:
    if not path:
        return {
            "exists": False,
            "size_bytes": 0,
            "modified_timestamp": None,
        }
    try:
        stat = path.stat()
    except Exception:
        return {
            "exists": False,
            "size_bytes": 0,
            "modified_timestamp": None,
        }
    return {
        "exists": True,
        "size_bytes": stat.st_size,
        "modified_timestamp": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def _read_text(path: Path, *, limit_chars: int | None = None) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if limit_chars is not None and len(text) > limit_chars:
        return text[:limit_chars] + "\n\n[TRUNCATED BY ORACLE LOCAL TRANSCRIPT GUARD]\n"
    return text


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")


def _latest_file(directory: Path, pattern: str) -> Path | None:
    try:
        paths = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:
        return None
    return paths[0] if paths else None


def _obs_logs(log_dir: Path | None = None, *, limit: int = 30) -> list[Path]:
    base = Path(log_dir or OBS_LOG_DIR)
    if not base.exists():
        return []
    try:
        logs = sorted(base.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:
        return []
    return list(reversed(logs[:limit]))


def scan_obs_recordings(log_dir: Path | None = None) -> dict[str, Any]:
    """Scan bounded OBS logs for recording start/stop events."""
    logs = _obs_logs(log_dir)
    started: list[dict[str, Any]] = []
    stopped_keys: set[str] = set()
    warnings: list[str] = []

    for log_path in logs:
        try:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception as exc:
            warnings.append(f"OBS log unreadable: {log_path}: {type(exc).__name__}: {exc}")
            continue
        for line_number, line in enumerate(lines, start=1):
            write_match = _WRITING_RE.search(line)
            if write_match:
                recording_path = _obs_path(write_match.group("path"))
                if recording_path.suffix.lower() in VIDEO_SUFFIXES:
                    started.append(
                        {
                            "recording_path": str(recording_path),
                            "path_key": _path_key(recording_path),
                            "source_log_path": str(log_path),
                            "source_log_line": line_number,
                            "source_log_text": line.strip(),
                        }
                    )
            stop_match = _STOPPED_RE.search(line)
            if stop_match:
                stopped_keys.add(_path_key(_obs_path(stop_match.group("path"))))

    latest = started[-1] if started else None
    active = None
    for event in reversed(started):
        path = Path(event["recording_path"])
        if event["path_key"] not in stopped_keys and path.exists():
            active = event
            break

    active_path = Path(active["recording_path"]) if active else None
    latest_path = Path(latest["recording_path"]) if latest else None
    return {
        "obs_log_dir": str(Path(log_dir or OBS_LOG_DIR)),
        "searched_log_count": len(logs),
        "recording_active": bool(active),
        "active_recording_path": str(active_path) if active_path else None,
        "active_recording": {
            **(active or {}),
            **_file_meta(active_path),
        } if active else None,
        "latest_started_recording": {
            **(latest or {}),
            **_file_meta(latest_path),
            "stopped_in_logs": bool(latest and latest.get("path_key") in stopped_keys),
        } if latest else None,
        "warnings": warnings,
    }


def find_transcript_sidecars(recording_path: str | Path | None) -> list[dict[str, Any]]:
    if not recording_path:
        return []
    path = Path(recording_path)
    directory = path.parent
    if not directory.exists():
        return []
    candidates: list[Path] = []
    try:
        candidates.extend(directory.glob(path.stem + ".*"))
        candidates.extend(directory.glob(path.stem + "_transcript.*"))
        candidates.extend(directory.glob(path.stem + ".en.*"))
    except Exception:
        return []

    sidecars: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate == path or candidate.suffix.lower() not in TRANSCRIPT_SUFFIXES:
            continue
        key = _path_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        meta = _file_meta(candidate)
        if meta["exists"]:
            sidecars.append(
                {
                    "path": str(candidate),
                    "suffix": candidate.suffix.lower(),
                    **meta,
                }
            )
    sidecars.sort(key=lambda item: item.get("modified_timestamp") or "", reverse=True)
    return sidecars


def _env_existing_file(var_names: tuple[str, ...]) -> str | None:
    for var_name in var_names:
        value = os.environ.get(var_name, "").strip()
        if value and Path(value).is_file():
            return value
    return None


def _which_any(names: tuple[str, ...]) -> str | None:
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def probe_local_stt_dependencies() -> dict[str, Any]:
    """Probe local STT dependencies without transcribing, installing, or networking."""
    ffmpeg_path = shutil.which("ffmpeg")
    whisper_cpp_path = _env_existing_file(WHISPER_CPP_ENV_VARS) or _which_any(WHISPER_CPP_BINARY_NAMES)
    python_whisper_available = _module_available("whisper")
    faster_whisper_available = _module_available("faster_whisper")

    ffmpeg_available = bool(ffmpeg_path)
    whisper_cpp_available = bool(whisper_cpp_path)
    engine_available = whisper_cpp_available or python_whisper_available or faster_whisper_available
    selected_engine = None
    blocker_reason = ""

    if not engine_available:
        blocker_reason = "No validated local STT binaries or python packages discovered on system PATH."
    elif not ffmpeg_available:
        blocker_reason = "Local STT engine detected, but ffmpeg is required for OBS media audio extraction."
    elif whisper_cpp_available:
        selected_engine = "whisper.cpp"
    elif faster_whisper_available:
        selected_engine = "faster_whisper"
    elif python_whisper_available:
        selected_engine = "whisper"

    local_stt_available = bool(selected_engine)

    return {
        "local_stt_available": local_stt_available,
        "ffmpeg_available": ffmpeg_available,
        "whisper_cpp_available": whisper_cpp_available,
        "python_whisper_available": python_whisper_available,
        "faster_whisper_available": faster_whisper_available,
        "selected_engine": selected_engine,
        "blocker_reason": blocker_reason,
        "network_boundary": "local-only",
        "transcription_allowed": False,
        "media_copied": False,
        "cloud_fallback_used": False,
    }


def detect_local_transcript_stack() -> dict[str, Any]:
    """Detect only local transcript options. Cloud providers are always refused."""
    dependency_probe = probe_local_stt_dependencies()
    executables = {
        "ffmpeg": shutil.which("ffmpeg"),
        "ffprobe": shutil.which("ffprobe"),
        "whisper": shutil.which("whisper") or shutil.which("whisper.exe"),
    }
    modules = {
        "whisper": importlib.util.find_spec("whisper") is not None,
        "faster_whisper": importlib.util.find_spec("faster_whisper") is not None,
        "vosk": importlib.util.find_spec("vosk") is not None,
        "torch": importlib.util.find_spec("torch") is not None,
        "speech_recognition": importlib.util.find_spec("speech_recognition") is not None,
    }

    whisper_model = os.environ.get("ORACLE_LOCAL_WHISPER_MODEL_PATH", "")
    whisper_cpp_exe = os.environ.get("ORACLE_WHISPER_CPP_EXE", "")
    whisper_cpp_model = os.environ.get("ORACLE_WHISPER_CPP_MODEL", "")
    vosk_model = os.environ.get("ORACLE_VOSK_MODEL_PATH", "")

    model_paths = {
        "ORACLE_LOCAL_WHISPER_MODEL_PATH": whisper_model,
        "ORACLE_WHISPER_CPP_EXE": whisper_cpp_exe,
        "ORACLE_WHISPER_CPP_MODEL": whisper_cpp_model,
        "ORACLE_VOSK_MODEL_PATH": vosk_model,
    }
    existing_model_paths = {
        key: value
        for key, value in model_paths.items()
        if value and Path(value).exists()
    }

    whisper_cpp_ready = bool(
        whisper_cpp_exe
        and whisper_cpp_model
        and Path(whisper_cpp_exe).exists()
        and Path(whisper_cpp_model).exists()
    )
    whisper_python_ready = bool(
        executables["ffmpeg"]
        and whisper_model
        and Path(whisper_model).exists()
        and (modules["whisper"] or modules["faster_whisper"] or executables["whisper"])
    )
    vosk_ready = bool(
        executables["ffmpeg"]
        and modules["vosk"]
        and vosk_model
        and Path(vosk_model).exists()
    )

    ready = whisper_cpp_ready or whisper_python_ready or vosk_ready
    warnings: list[str] = []
    if not ready:
        warnings.append(
            "No verified local transcription stack is available. ORACLE will not call cloud transcription."
        )
    if modules["speech_recognition"]:
        warnings.append(
            "speech_recognition detected but ignored unless paired with an explicit local engine; cloud recognizers are refused."
        )

    return {
        "local_only": True,
        "cloud_transcription_refused": True,
        "cloud_providers_allowed": [],
        "dependency_probe": dependency_probe,
        "executables": executables,
        "python_modules": modules,
        "model_paths": model_paths,
        "existing_model_paths": existing_model_paths,
        "can_transcribe_locally": ready,
        "ready_engines": {
            "whisper_cpp": whisper_cpp_ready,
            "whisper_python": whisper_python_ready,
            "vosk": vosk_ready,
        },
        "warnings": warnings,
    }


def latest_transcript_record() -> dict[str, Any] | None:
    path = _latest_file(TRANSCRIPTS_DIR, "obs_transcript_*.json")
    if not path:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"path": str(path), "unreadable": True}
    if isinstance(data, dict):
        data["path"] = str(path)
        return data
    return {"path": str(path), "unreadable": True}


def latest_receipt_record() -> dict[str, Any] | None:
    path = _latest_file(RECEIPTS_DIR, "obs_transcript_receipt_*.json")
    if not path:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"receipt_path": str(path), "unreadable": True}
    if isinstance(data, dict):
        data["receipt_path"] = str(path)
        return data
    return {"receipt_path": str(path), "unreadable": True}


def status_payload(log_dir: Path | None = None) -> dict[str, Any]:
    scan = scan_obs_recordings(log_dir)
    active_path = scan.get("active_recording_path")
    sidecars = find_transcript_sidecars(active_path)
    stack = detect_local_transcript_stack()
    warnings = []
    warnings.extend(scan.get("warnings") or [])
    warnings.extend(stack.get("warnings") or [])
    if scan.get("recording_active") and not sidecars and not stack.get("can_transcribe_locally"):
        warnings.append("Active OBS recording found, but no transcript sidecar or verified local STT stack is available.")

    return {
        "name": "Captain's Log OBS Transcript",
        "timestamp": _now(),
        "local_only": True,
        "operation_mode": "read_existing_obs_recording_metadata",
        "recording_scan": scan,
        "active_recording_path": active_path,
        "transcript_sidecars": sidecars,
        "local_transcript_stack": stack,
        "latest_transcript": latest_transcript_record(),
        "latest_receipt": latest_receipt_record(),
        "writes_allowed": {
            "transcripts": str(TRANSCRIPTS_DIR),
            "receipts": str(RECEIPTS_DIR),
        },
        "privacy_boundary": {
            "records_screen": False,
            "records_audio": False,
            "copies_raw_video": False,
            "uploads_media": False,
            "uses_cloud_transcription": False,
            "captures_keystrokes": False,
            "captures_clipboard": False,
        },
        "warnings": warnings,
    }


def _receipt_payload(
    *,
    operation: str,
    recording_path: str | None,
    transcript_path: str | None = None,
    source_sidecar_path: str | None = None,
    transcript_available: bool = False,
    blocker: str = "",
    notes: str = "",
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "receipt_id": _id("obs_transcript_receipt"),
        "timestamp": _now(),
        "operation": operation,
        "recording_path": recording_path,
        "transcript_path": transcript_path,
        "source_sidecar_path": source_sidecar_path,
        "transcript_available": transcript_available,
        "blocker": blocker,
        "local_only": True,
        "cloud_transcription_refused": True,
        "cloud_uploads": 0,
        "files_moved": 0,
        "files_deleted": 0,
        "files_renamed": 0,
        "files_synced": 0,
        "raw_recording_copied": False,
        "screen_recorded_by_oracle": False,
        "audio_recorded_by_oracle": False,
        "video_recorded_by_oracle": False,
        "keystrokes_captured": False,
        "clipboard_captured": False,
        "git_commits": 0,
        "git_pushes": 0,
        "human_authority": "Noah.Physical",
        "notes": notes,
        "warnings": list(warnings or []),
    }


def write_status_receipt(*, notes: str = "", log_dir: Path | None = None) -> dict[str, Any]:
    status = status_payload(log_dir)
    receipt = _receipt_payload(
        operation="obs_transcript_status_receipt",
        recording_path=status.get("active_recording_path"),
        blocker="status_only_no_transcript_written",
        notes=notes,
        warnings=status.get("warnings") or [],
    )
    path = RECEIPTS_DIR / f"obs_transcript_receipt_{_stamp()}.json"
    _write_json(path, receipt)
    receipt["receipt_path"] = str(path)
    return receipt


def _write_transcript_from_sidecar(
    *,
    recording_path: str,
    sidecar: dict[str, Any],
    notes: str = "",
) -> dict[str, Any]:
    source_path = Path(sidecar["path"])
    text = _read_text(source_path, limit_chars=MAX_TRANSCRIPT_CHARS)
    timestamp = _now()
    transcript_id = _id("obs_transcript")
    transcript = {
        "transcript_id": transcript_id,
        "timestamp": timestamp,
        "source": "existing_local_transcript_sidecar",
        "recording_path": recording_path,
        "source_sidecar_path": str(source_path),
        "evidence_state": "CONTENT_OBSERVED",
        "local_only": True,
        "raw_recording_copied": False,
        "cloud_uploads": 0,
        "text_char_count": len(text),
        "notes": notes,
        "text": text,
    }
    json_path = TRANSCRIPTS_DIR / f"obs_transcript_{_stamp()}.json"
    md_path = TRANSCRIPTS_DIR / f"obs_transcript_{_stamp()}.md"
    _write_json(json_path, transcript)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(
        "\n".join(
            [
                "# Captain's Log OBS Transcript",
                "",
                f"- Transcript ID: {transcript_id}",
                f"- Timestamp: {timestamp}",
                f"- Recording path: {recording_path}",
                f"- Source sidecar: {source_path}",
                "- Local only: true",
                "- Raw recording copied: false",
                "- Cloud uploads: 0",
                "",
                "## Transcript",
                "",
                text,
                "",
            ]
        ),
        encoding="utf-8",
    )
    receipt = _receipt_payload(
        operation="obs_transcript_sidecar_pull",
        recording_path=recording_path,
        transcript_path=str(json_path),
        source_sidecar_path=str(source_path),
        transcript_available=True,
        notes=notes,
    )
    receipt["transcript_markdown_path"] = str(md_path)
    receipt_path = RECEIPTS_DIR / f"obs_transcript_receipt_{_stamp()}.json"
    _write_json(receipt_path, receipt)
    receipt["receipt_path"] = str(receipt_path)
    return {
        "transcript": {**transcript, "path": str(json_path), "markdown_path": str(md_path)},
        "receipt": receipt,
        "status": status_payload(),
    }


def pull_active_transcript(*, notes: str = "", log_dir: Path | None = None) -> dict[str, Any]:
    """Pull an existing local transcript, or write a blocker receipt.

    Direct speech-to-text is intentionally disabled unless a verified local
    engine is present and explicitly integrated later. This prevents hidden
    cloud fallback while still preserving a receipt of the attempt.
    """
    status = status_payload(log_dir)
    recording_path = status.get("active_recording_path")
    warnings = list(status.get("warnings") or [])
    if not recording_path:
        blocker = "No active OBS recording was found in local OBS logs."
    else:
        sidecars = status.get("transcript_sidecars") or []
        if sidecars:
            return _write_transcript_from_sidecar(
                recording_path=str(recording_path),
                sidecar=sidecars[0],
                notes=notes,
            )
        if status.get("local_transcript_stack", {}).get("can_transcribe_locally"):
            blocker = (
                "A local transcript stack appears available, but ORACLE direct STT execution is not enabled in this "
                "bounded build. Add an explicit local engine runner before transcribing raw media."
            )
        else:
            blocker = (
                "Active OBS recording found, but no transcript sidecar or verified local transcription stack is "
                "available. Cloud transcription was refused."
            )

    receipt = _receipt_payload(
        operation="obs_transcript_pull_blocked",
        recording_path=recording_path,
        transcript_available=False,
        blocker=blocker,
        notes=notes,
        warnings=warnings,
    )
    receipt_path = RECEIPTS_DIR / f"obs_transcript_receipt_{_stamp()}.json"
    _write_json(receipt_path, receipt)
    receipt["receipt_path"] = str(receipt_path)
    return {
        "transcript": None,
        "receipt": receipt,
        "status": status,
    }


if __name__ == "__main__":
    print(json.dumps(status_payload(), indent=2, ensure_ascii=True, sort_keys=True))
