r"""Metadata-only OBS/MOV witness.

Reads container, stream, filesystem, and OBS-log metadata from video files.
It never decodes or saves video frames and never creates screenshots.
Observations are appended to one canonical source thread.

Stop: create C:\Oracle\state\media_metadata_witness\stop.flag
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import av

from source_thread import THREAD_ID, THREAD_PATH, append_event

STATE_DIR = Path(r"C:\Oracle\state\media_metadata_witness")
STOP_FLAG = STATE_DIR / "stop.flag"
PROGRESS = STATE_DIR / "progress.json"
OBS_LOGS = Path(r"C:\Users\noahh\AppData\Roaming\obs-studio\logs")
DEFAULT_ROOTS = (
    Path(r"C:\Users\noahh\OneDrive\Videos"),
    Path(r"C:\Users\noahh\OneDrive\Pictures"),
)
VIDEO_EXTS = {".mov", ".mkv", ".mp4", ".m4v", ".avi", ".webm"}
INTERVAL = 120
FILE_ATTRIBUTE_OFFLINE = 0x1000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x400000


def media_roots() -> tuple[Path, ...]:
    configured = os.environ.get("ORACLE_MEDIA_ROOTS", "").strip()
    if not configured:
        return DEFAULT_ROOTS
    return tuple(Path(part.strip()) for part in configured.split(os.pathsep) if part.strip())


def iter_media_files(roots: Iterable[Path]) -> Iterable[Path]:
    for root in roots:
        if not root.exists():
            continue
        for dirpath, _, filenames in os.walk(root):
            for name in filenames:
                path = Path(dirpath) / name
                if path.suffix.lower() in VIDEO_EXTS:
                    yield path


def file_fingerprint(path: Path) -> str:
    stat = path.stat()
    raw = f"{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}".encode("utf-8", "surrogatepass")
    return hashlib.sha256(raw).hexdigest()


def parse_obs_recording_state(text: str) -> dict[str, Any]:
    writes = list(re.finditer(r"Writing file '([^']+)'", text))
    if not writes:
        return {"active": False, "recording_path": None}
    latest = writes[-1]
    return {
        "active": "Recording Stop" not in text[latest.end():],
        "recording_path": latest.group(1),
    }


def current_obs_state() -> dict[str, Any]:
    logs = sorted(OBS_LOGS.glob("*.txt"), key=lambda p: p.stat().st_mtime_ns, reverse=True)
    if not logs:
        return {"active": False, "recording_path": None, "obs_log": None}
    log = logs[0]
    state = parse_obs_recording_state(log.read_text(encoding="utf-8", errors="replace"))
    state["obs_log"] = str(log)
    state["obs_log_mtime_utc"] = datetime.fromtimestamp(
        log.stat().st_mtime, tz=timezone.utc
    ).isoformat()
    return state


def _rate(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 6)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def is_cloud_placeholder(path: Path) -> bool:
    attributes = int(getattr(path.stat(), "st_file_attributes", 0))
    return bool(attributes & (FILE_ATTRIBUTE_OFFLINE | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS))


def inspect_media(path: Path, obs_state: dict[str, Any] | None = None) -> dict[str, Any]:
    """Read headers/metadata only. No packet, frame, or thumbnail decoding."""
    stat = path.stat()
    if is_cloud_placeholder(path):
        return {
            "filename": path.name,
            "extension": path.suffix.lower(),
            "size_bytes": stat.st_size,
            "created_utc": datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat(),
            "modified_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            "cloud_placeholder": True,
            "container_metadata": None,
            "streams": [],
            "reason": "online-only file was not hydrated; filesystem metadata only",
        }
    with av.open(str(path), mode="r", metadata_errors="ignore") as container:
        streams = []
        for stream in container.streams:
            item: dict[str, Any] = {
                "index": stream.index,
                "type": stream.type,
                "codec": getattr(getattr(stream, "codec_context", None), "name", None),
                "duration_s": (
                    round(float(stream.duration * stream.time_base), 3)
                    if stream.duration is not None and stream.time_base is not None
                    else None
                ),
                "time_base": str(stream.time_base) if stream.time_base is not None else None,
                "metadata": dict(stream.metadata or {}),
            }
            if stream.type == "video":
                item.update({
                    "width": getattr(stream.codec_context, "width", None),
                    "height": getattr(stream.codec_context, "height", None),
                    "average_rate": _rate(getattr(stream, "average_rate", None)),
                })
            elif stream.type == "audio":
                item.update({
                    "sample_rate": getattr(stream.codec_context, "sample_rate", None),
                    "channels": getattr(stream.codec_context, "channels", None),
                })
            streams.append(item)
        duration_s = round(container.duration / av.time_base, 3) if container.duration else None
        container_metadata = dict(container.metadata or {})

    resolved = str(path.resolve())
    latest_obs = obs_state or {}
    obs_match = (
        bool(latest_obs.get("recording_path"))
        and os.path.normcase(os.path.abspath(latest_obs["recording_path"]))
        == os.path.normcase(os.path.abspath(resolved))
    )
    return {
        "filename": path.name,
        "extension": path.suffix.lower(),
        "size_bytes": stat.st_size,
        "created_utc": datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat(),
        "modified_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "duration_s": duration_s,
        "container_format": container_metadata.get("major_brand") or path.suffix.lower().lstrip("."),
        "container_metadata": container_metadata,
        "streams": streams,
        "obs_recording": {
            "matched_latest_obs_path": obs_match,
            "active": bool(latest_obs.get("active")) if obs_match else False,
            "obs_log": latest_obs.get("obs_log") if obs_match else None,
        },
    }


def load_progress() -> dict[str, str]:
    if not PROGRESS.exists():
        return {}
    try:
        return json.loads(PROGRESS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_progress(progress: dict[str, str]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temp = PROGRESS.with_suffix(".tmp")
    temp.write_text(json.dumps(progress, indent=2, sort_keys=True), encoding="utf-8")
    temp.replace(PROGRESS)


def scan_once(progress: dict[str, str]) -> tuple[int, int]:
    observed = 0
    errors = 0
    obs_state = current_obs_state()
    for path in iter_media_files(media_roots()):
        key = str(path.resolve())
        try:
            fingerprint = file_fingerprint(path)
            if progress.get(key) == fingerprint:
                continue
            metadata = inspect_media(path, obs_state)
            append_event(
                "media_metadata",
                source_path=path,
                content=metadata,
                provenance={
                    "method": "container_and_filesystem_metadata_only",
                    "reader": "PyAV",
                    "raw_frame_stored": False,
                    "screenshot_created": False,
                },
            )
            progress[key] = fingerprint
            observed += 1
        except Exception as exc:
            errors += 1
            print(f"metadata error {path}: {type(exc).__name__}: {exc}", flush=True)
    if observed:
        save_progress(progress)
    return observed, errors


def main() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    progress = load_progress()
    print(
        f"metadata witness up. thread={THREAD_ID} path={THREAD_PATH} "
        f"roots={[str(p) for p in media_roots()]}",
        flush=True,
    )
    while not STOP_FLAG.exists():
        observed, errors = scan_once(progress)
        print(f"metadata scan: +{observed} observations, {errors} errors", flush=True)
        time.sleep(INTERVAL)
    print("stop.flag found - metadata witness down.", flush=True)


if __name__ == "__main__":
    main()
