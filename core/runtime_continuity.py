"""Restart-safe ORACLE runtime continuity frame.

This module builds a compact continuity frame from internal providers. It does
not call ORACLE's HTTP endpoints, invoke models, route to external agents, or
store OBS audio/video. Persistence is explicit and atomic.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


SCHEMA_VERSION = 1
SNAPSHOT_RELATIVE_PATH = Path("state") / "oracle_runtime_continuity.json"
ACTIVE_GOAL_RELATIVE_PATH = Path("state") / "oracle_active_goal.json"
TEST_SUMMARY_RELATIVE_PATH = Path("state") / "oracle_last_test_summary.json"

FIELD_STATES = {"live", "verified", "persisted", "stale", "unavailable", "unknown", "invalid"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def snapshot_path(root: Path) -> Path:
    return root.resolve() / SNAPSHOT_RELATIVE_PATH


def _field(value: Any, status: str, source: str, observed_at: str | None = None, error: str | None = None) -> dict:
    if status not in FIELD_STATES:
        status = "unknown"
    item = {
        "value": value,
        "status": status,
        "source": source,
        "observed_at": observed_at or utc_now(),
    }
    if error:
        item["error"] = error
    return item


def _unknown(source: str, value: Any = None, error: str | None = None) -> dict:
    return _field(value, "unknown", source, error=error)


def _safe_read_json(path: Path) -> tuple[dict | None, str | None]:
    try:
        if not path.exists():
            return None, "missing"
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None, "snapshot root is not an object"
        if data.get("schema_version") != SCHEMA_VERSION:
            return None, f"unsupported schema_version: {data.get('schema_version')!r}"
        return data, None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def load_snapshot(root: Path) -> tuple[dict | None, list[str]]:
    data, error = _safe_read_json(snapshot_path(root))
    return data, ([] if error is None else [error])


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def persist_frame(root: Path, frame: dict) -> dict:
    payload = json.loads(json.dumps(frame))
    payload["persisted_at"] = utc_now()
    atomic_write_json(snapshot_path(root), payload)
    return payload


def _call_provider(provider: Callable[[], dict] | None, source: str) -> tuple[dict, str | None]:
    if provider is None:
        return {}, f"{source} provider unavailable"
    try:
        result = provider()
        if not isinstance(result, dict):
            return {}, f"{source} provider returned {type(result).__name__}"
        return result, None
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {exc}"


def _read_active_goal(root: Path) -> tuple[dict, str | None]:
    path = root.resolve() / ACTIVE_GOAL_RELATIVE_PATH
    data, error = _safe_read_json(path)
    if error == "missing":
        return _unknown("explicit_local_goal_state"), None
    if error:
        return _field(None, "invalid", "explicit_local_goal_state", error=error), error
    goal = data.get("active_goal")
    if isinstance(goal, dict):
        return _field(
            goal.get("value"),
            goal.get("status") if goal.get("status") in FIELD_STATES else "verified",
            "explicit_local_goal_state",
            goal.get("observed_at"),
        ), None
    if isinstance(goal, str) and goal.strip():
        return _field(goal.strip(), "verified", "explicit_local_goal_state", data.get("updated_at")), None
    return _unknown("explicit_local_goal_state"), None


def set_active_goal(root: Path, goal: str) -> dict:
    now = utc_now()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": now,
        "active_goal": {
            "value": goal,
            "status": "verified",
            "source": "explicit_local_goal_state",
            "observed_at": now,
        },
    }
    atomic_write_json(root.resolve() / ACTIVE_GOAL_RELATIVE_PATH, payload)
    return payload


def _read_test_summary(root: Path) -> tuple[dict, str | None]:
    path = root.resolve() / TEST_SUMMARY_RELATIVE_PATH
    data, error = _safe_read_json(path)
    if error == "missing":
        return _unknown("local_test_summary", []), None
    if error:
        return _field([], "invalid", "local_test_summary", error=error), error
    tests = data.get("last_successful_tests")
    if not isinstance(tests, list):
        return _field([], "invalid", "local_test_summary", error="last_successful_tests is not a list"), "invalid test summary"
    verified = []
    for item in tests:
        if not isinstance(item, dict):
            continue
        if item.get("result") == "pass" and int(item.get("exit_code", 1)) == 0 and item.get("command"):
            verified.append({
                "command": item.get("command"),
                "timestamp": item.get("timestamp") or data.get("updated_at"),
                "result": "pass",
                "exit_code": 0,
                "passed_count": item.get("passed_count"),
                "failed_count": item.get("failed_count", 0),
                "commit": item.get("commit"),
                "dirty": item.get("dirty"),
            })
    status = "verified" if verified else "unknown"
    return _field(verified, status, "local_test_summary", data.get("updated_at")), None


def _runtime_fields(runtime: dict, mode_state: dict, previous: dict | None, now: str) -> dict:
    server = runtime.get("server") if isinstance(runtime.get("server"), dict) else {}
    current_session = mode_state.get("session_id") or server.get("session_id")
    previous_session = None
    if previous:
        previous_runtime = previous.get("runtime") or {}
        snapshot_session = (previous_runtime.get("session_id") or {}).get("value")
        snapshot_previous = (previous_runtime.get("previous_session_id") or {}).get("value")
        previous_session = snapshot_session if snapshot_session != current_session else snapshot_previous
    canonical_root = runtime.get("canonical_root")
    memory = runtime.get("memory") if isinstance(runtime.get("memory"), dict) else {}
    return {
        "canonical_root": _field(canonical_root, "verified" if canonical_root else "unknown", "runtime_diagnostics", runtime.get("observed_at", now)),
        "active_runtime_command": _field(runtime.get("active_runtime_command"), "verified" if runtime.get("active_runtime_command") else "unknown", "runtime_diagnostics", runtime.get("observed_at", now)),
        "current_mode": _field(mode_state.get("mode") or server.get("mode"), "verified" if (mode_state.get("mode") or server.get("mode")) else "unknown", "runtime_state", now),
        "session_id": _field(current_session, "verified" if current_session else "unknown", "runtime_state", now),
        "previous_session_id": _field(previous_session, "persisted" if previous_session is not None else "unknown", "continuity_snapshot", now),
        "memory_db_path": _field(memory.get("db_path"), "verified" if memory.get("exists") else ("invalid" if memory.get("db_path") else "unknown"), "approved_memory_configuration", runtime.get("observed_at", now)),
    }


def _memory_fields(runtime: dict, now: str) -> dict:
    memory = runtime.get("memory") if isinstance(runtime.get("memory"), dict) else {}
    return {
        "memory_db_path": _field(memory.get("db_path"), "verified" if memory.get("exists") else ("invalid" if memory.get("db_path") else "unknown"), "approved_memory_configuration", runtime.get("observed_at", now)),
        "approved_memory_sources": _field([], "verified", "approved_memory_configuration", runtime.get("observed_at", now)),
    }


def _obs_fields(obs: dict, now: str) -> dict:
    observed = obs.get("observed_at", now)
    if not obs.get("available"):
        return {
            "available": _field(False, "unavailable", "obs_websocket", observed, obs.get("last_obs_error")),
            "scene": _field(None, "unavailable", "obs_websocket", observed, obs.get("last_obs_error")),
            "recording": _field(None, "unavailable", "obs_websocket", observed, obs.get("last_obs_error")),
            "recording_duration_seconds": _field(None, "unavailable", "obs_websocket", observed, obs.get("last_obs_error")),
            "streaming": _field(None, "unavailable", "obs_websocket", observed, obs.get("last_obs_error")),
            "virtual_camera": _field(None, "unavailable", "obs_websocket", observed, obs.get("last_obs_error")),
            "sources": _field([], "unavailable", "obs_websocket", observed, obs.get("last_obs_error")),
        }
    return {
        "available": _field(True, "live", "obs_websocket", observed),
        "scene": _field(obs.get("scene"), "live" if obs.get("scene") else "unknown", "obs_websocket", observed),
        "recording": _field(obs.get("recording"), "live", "obs_websocket", observed),
        "recording_duration_seconds": _field(obs.get("recording_duration_seconds"), "live" if obs.get("recording_duration_seconds") is not None else "unknown", "obs_websocket", observed),
        "streaming": _field(obs.get("streaming"), "live", "obs_websocket", observed),
        "virtual_camera": _field(obs.get("virtual_camera"), "live", "obs_websocket", observed),
        "sources": _field(obs.get("sources", []), "live", "obs_websocket", observed),
    }


def _latest_event(runtime: dict, now: str) -> dict:
    error = runtime.get("latest_runtime_error")
    if error and error != "none found in recent logs":
        return _field(str(error), "verified", "runtime_event_log", runtime.get("observed_at", now))
    return _unknown("runtime_event_log")


def build_frame(
    *,
    root: Path,
    runtime_provider: Callable[[], dict] | None,
    obs_provider: Callable[[], dict] | None,
    mode_provider: Callable[[], dict] | None,
    persist: bool = False,
) -> dict:
    """Build the continuity frame from internal providers.

    ``persist=False`` is side-effect free and is what API GET handlers should use.
    """
    root = root.resolve()
    now = utc_now()
    previous, snapshot_errors = load_snapshot(root)
    runtime, runtime_error = _call_provider(runtime_provider, "runtime_diagnostics")
    obs, obs_error = _call_provider(obs_provider, "obs_websocket")
    mode_state, mode_error = _call_provider(mode_provider, "runtime_state")
    active_goal, active_goal_error = _read_active_goal(root)
    tests, tests_error = _read_test_summary(root)
    errors = [e for e in [runtime_error, obs_error, mode_error, active_goal_error, tests_error, *snapshot_errors] if e and e != "missing"]

    runtime_section = _runtime_fields(runtime, mode_state, previous, now)
    memory_section = _memory_fields(runtime, now)
    obs_section = _obs_fields(obs, now)
    work_section = {
        "active_goal": active_goal,
        "latest_verified_runtime_event": _latest_event(runtime, now),
        "unresolved_blockers": _field(errors, "verified" if errors else "verified", "structured_runtime_status", now),
        "last_successful_tests": tests,
    }

    stale_fields: list[str] = []
    unknown_fields: list[str] = []
    for section_name, section in (("runtime", runtime_section), ("memory", memory_section), ("obs", obs_section), ("work", work_section)):
        for field_name, value in section.items():
            if not isinstance(value, dict):
                continue
            status = value.get("status")
            if status == "stale":
                stale_fields.append(f"{section_name}.{field_name}")
            if status in {"unknown", "unavailable", "invalid"}:
                unknown_fields.append(f"{section_name}.{field_name}")

    frame = {
        "schema_version": SCHEMA_VERSION,
        "continuity_id": f"CONT-{uuid.uuid4().hex[:12]}",
        "generated_at": now,
        "persisted_at": previous.get("persisted_at") if previous else None,
        "runtime": runtime_section,
        "memory": memory_section,
        "obs": obs_section,
        "work": work_section,
        "governance": {
            "authority_boundary": "Noah.Physical is the final authority.",
            "external_agents_boundary": "Codex, Claude, ChatGPT, and Gemini are advisers or builders and have no independent sovereign authority.",
            "raw_video_stored": False,
            "raw_audio_stored": False,
            "obs_write_permissions": False,
        },
        "frame_status": "healthy" if not errors else "degraded",
        "stale_fields": stale_fields,
        "unknown_fields": unknown_fields,
        "errors": errors,
    }
    if persist:
        frame = persist_frame(root, frame)
    return frame


def summarize_updates(frame: dict) -> str:
    runtime = frame.get("runtime", {})
    memory = frame.get("memory", {})
    obs = frame.get("obs", {})
    work = frame.get("work", {})
    goal = work.get("active_goal", {})
    tests = work.get("last_successful_tests", {})
    return "\n".join([
        "VERIFIED [CONTINUITY_FRAME]: ORACLE continuity frame is available.",
        f"VERIFIED [RUNTIME_STATE]: Mode `{(runtime.get('current_mode') or {}).get('value')}`; session `{(runtime.get('session_id') or {}).get('value')}`; root `{(runtime.get('canonical_root') or {}).get('value')}`.",
        f"VERIFIED [MEMORY]: Memory DB `{(memory.get('memory_db_path') or {}).get('value')}`.",
        f"VERIFIED [WORK]: Active goal status `{goal.get('status')}`; value `{goal.get('value') or 'unknown'}`.",
        f"VERIFIED [OBS_RUNTIME_CONTEXT]: OBS available `{(obs.get('available') or {}).get('value')}`; scene `{(obs.get('scene') or {}).get('value') or 'unknown'}`; recording `{(obs.get('recording') or {}).get('value')}`.",
        f"VERIFIED [TESTS]: Last successful tests status `{tests.get('status')}`; count `{len(tests.get('value') or [])}`.",
        f"BOUNDARY [CONTINUITY_FRAME]: Unknown fields: {', '.join(frame.get('unknown_fields', [])[:12]) or 'none'}."
    ])


def summarize_active_goal(frame: dict) -> str:
    goal = ((frame.get("work") or {}).get("active_goal") or {})
    if goal.get("status") == "verified" and goal.get("value"):
        return f"VERIFIED [CONTINUITY_FRAME]: Active goal: {goal.get('value')}"
    return "UNAVAILABLE [CONTINUITY_FRAME]: I do not currently have a verified active goal recorded."


def summarize_observable_channels(frame: dict) -> str:
    obs = frame.get("obs", {})
    if (obs.get("available") or {}).get("value") is True:
        return "\n".join([
            "VERIFIED [OBS_RUNTIME_CONTEXT]: I can read OBS runtime metadata, including scene, recording state, streaming state, virtual camera state, and source visibility.",
            f"VERIFIED [OBS_RUNTIME_CONTEXT]: Current scene is `{(obs.get('scene') or {}).get('value') or 'unknown'}`.",
            "BOUNDARY [OBS_RUNTIME_CONTEXT]: I cannot interpret the raw video feed through this bridge, and I am not storing raw audio or video.",
        ])
    return "UNAVAILABLE [OBS_RUNTIME_CONTEXT]: I cannot currently reach OBS WebSocket, so I cannot verify scene, recording, or source state."
