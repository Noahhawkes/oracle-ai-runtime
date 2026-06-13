import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))

import runtime_continuity as rc  # noqa: E402


def runtime_provider(session_id=2):
    return {
        "observed_at": "2026-06-13T22:00:00+00:00",
        "canonical_root": str(ROOT),
        "active_runtime_command": "python.exe oracle_server.py --port 7777",
        "server": {"mode": "companion", "session_id": session_id},
        "memory": {"db_path": str(ROOT / "Memory" / "oracle_memory.db"), "exists": True},
        "latest_runtime_error": "none found in recent logs",
    }


def mode_provider(session_id=2):
    return {"mode": "companion", "no_route": False, "session_id": session_id}


def obs_available():
    return {
        "available": True,
        "observed_at": "2026-06-13T22:01:00+00:00",
        "scene": "Rendered Reality",
        "recording": True,
        "recording_duration_seconds": 1200,
        "streaming": False,
        "virtual_camera": False,
        "sources": [{"name": "Display Capture", "visible": True}],
        "raw_video_stored": False,
        "raw_audio_stored": False,
        "write_permissions": False,
    }


def obs_unavailable():
    return {
        "available": False,
        "observed_at": "2026-06-13T22:01:00+00:00",
        "last_obs_error": "ConnectionRefusedError",
        "raw_video_stored": False,
        "raw_audio_stored": False,
        "write_permissions": False,
    }


def test_missing_snapshot_produces_valid_unknown_fields(tmp_path):
    frame = rc.build_frame(
        root=tmp_path,
        runtime_provider=runtime_provider,
        obs_provider=obs_unavailable,
        mode_provider=mode_provider,
        persist=False,
    )
    assert frame["schema_version"] == 1
    assert frame["work"]["active_goal"]["status"] == "unknown"
    assert "work.active_goal" in frame["unknown_fields"]
    assert not rc.snapshot_path(tmp_path).exists()


def test_persisted_snapshot_survives_and_previous_session_is_historical(tmp_path):
    first = rc.build_frame(
        root=tmp_path,
        runtime_provider=lambda: runtime_provider(10),
        obs_provider=obs_available,
        mode_provider=lambda: mode_provider(10),
        persist=True,
    )
    assert rc.snapshot_path(tmp_path).exists()
    second = rc.build_frame(
        root=tmp_path,
        runtime_provider=lambda: runtime_provider(11),
        obs_provider=obs_available,
        mode_provider=lambda: mode_provider(11),
        persist=False,
    )
    assert first["runtime"]["session_id"]["value"] == 10
    assert second["runtime"]["session_id"]["value"] == 11
    assert second["runtime"]["previous_session_id"]["value"] == 10
    assert second["runtime"]["previous_session_id"]["status"] == "persisted"


def test_current_session_snapshot_does_not_become_previous_session(tmp_path):
    rc.build_frame(
        root=tmp_path,
        runtime_provider=lambda: runtime_provider(10),
        obs_provider=obs_available,
        mode_provider=lambda: mode_provider(10),
        persist=True,
    )
    rc.build_frame(
        root=tmp_path,
        runtime_provider=lambda: runtime_provider(11),
        obs_provider=obs_available,
        mode_provider=lambda: mode_provider(11),
        persist=True,
    )
    frame = rc.build_frame(
        root=tmp_path,
        runtime_provider=lambda: runtime_provider(11),
        obs_provider=obs_available,
        mode_provider=lambda: mode_provider(11),
        persist=False,
    )
    assert frame["runtime"]["session_id"]["value"] == 11
    assert frame["runtime"]["previous_session_id"]["value"] == 10


def test_corrupt_snapshot_fails_safely(tmp_path):
    rc.snapshot_path(tmp_path).parent.mkdir(parents=True)
    rc.snapshot_path(tmp_path).write_text("{not-json", encoding="utf-8")
    frame = rc.build_frame(
        root=tmp_path,
        runtime_provider=runtime_provider,
        obs_provider=obs_available,
        mode_provider=mode_provider,
        persist=False,
    )
    assert frame["frame_status"] == "degraded"
    assert any("JSONDecodeError" in error for error in frame["errors"])


def test_unsupported_schema_fails_safely(tmp_path):
    rc.snapshot_path(tmp_path).parent.mkdir(parents=True)
    rc.snapshot_path(tmp_path).write_text(json.dumps({"schema_version": 999}), encoding="utf-8")
    frame = rc.build_frame(
        root=tmp_path,
        runtime_provider=runtime_provider,
        obs_provider=obs_available,
        mode_provider=mode_provider,
        persist=False,
    )
    assert frame["frame_status"] == "degraded"
    assert any("unsupported schema_version" in error for error in frame["errors"])


def test_obs_available_uses_live_bridge_data_and_no_raw_media(tmp_path):
    frame = rc.build_frame(
        root=tmp_path,
        runtime_provider=runtime_provider,
        obs_provider=obs_available,
        mode_provider=mode_provider,
        persist=False,
    )
    assert frame["obs"]["available"]["value"] is True
    assert frame["obs"]["available"]["status"] == "live"
    assert frame["obs"]["scene"]["value"] == "Rendered Reality"
    assert frame["obs"]["recording_duration_seconds"]["value"] == 1200
    assert frame["governance"]["raw_video_stored"] is False
    assert frame["governance"]["raw_audio_stored"] is False
    assert frame["governance"]["obs_write_permissions"] is False


def test_obs_unavailable_is_not_reported_as_current_scene(tmp_path):
    rc.build_frame(
        root=tmp_path,
        runtime_provider=lambda: runtime_provider(1),
        obs_provider=obs_available,
        mode_provider=lambda: mode_provider(1),
        persist=True,
    )
    frame = rc.build_frame(
        root=tmp_path,
        runtime_provider=lambda: runtime_provider(2),
        obs_provider=obs_unavailable,
        mode_provider=lambda: mode_provider(2),
        persist=False,
    )
    assert frame["obs"]["available"]["value"] is False
    assert frame["obs"]["scene"]["value"] is None
    assert frame["obs"]["scene"]["status"] == "unavailable"
    assert frame["obs"]["recording_duration_seconds"]["value"] is None


def test_active_goal_requires_explicit_local_state(tmp_path):
    missing = rc.build_frame(
        root=tmp_path,
        runtime_provider=runtime_provider,
        obs_provider=obs_available,
        mode_provider=mode_provider,
        persist=False,
    )
    assert missing["work"]["active_goal"]["status"] == "unknown"
    rc.set_active_goal(tmp_path, "Implement restart-safe ORACLE continuity")
    frame = rc.build_frame(
        root=tmp_path,
        runtime_provider=runtime_provider,
        obs_provider=obs_available,
        mode_provider=mode_provider,
        persist=False,
    )
    assert frame["work"]["active_goal"]["value"] == "Implement restart-safe ORACLE continuity"
    assert frame["work"]["active_goal"]["status"] == "verified"


def test_unverified_test_claims_are_not_loaded(tmp_path):
    path = tmp_path / rc.TEST_SUMMARY_RELATIVE_PATH
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "schema_version": 1,
        "updated_at": "2026-06-13T22:00:00+00:00",
        "last_successful_tests": [{"command": "pytest", "result": "said pass", "exit_code": 1}],
    }), encoding="utf-8")
    frame = rc.build_frame(
        root=tmp_path,
        runtime_provider=runtime_provider,
        obs_provider=obs_available,
        mode_provider=mode_provider,
        persist=False,
    )
    assert frame["work"]["last_successful_tests"]["status"] == "unknown"
    assert frame["work"]["last_successful_tests"]["value"] == []


def test_verified_structured_test_summary_is_loaded(tmp_path):
    path = tmp_path / rc.TEST_SUMMARY_RELATIVE_PATH
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "schema_version": 1,
        "updated_at": "2026-06-13T22:00:00+00:00",
        "last_successful_tests": [{
            "command": "python -m pytest tests -q",
            "result": "pass",
            "exit_code": 0,
            "passed_count": 26,
            "failed_count": 0,
            "commit": "876ec1a",
            "dirty": True,
        }],
    }), encoding="utf-8")
    frame = rc.build_frame(
        root=tmp_path,
        runtime_provider=runtime_provider,
        obs_provider=obs_available,
        mode_provider=mode_provider,
        persist=False,
    )
    tests = frame["work"]["last_successful_tests"]
    assert tests["status"] == "verified"
    assert tests["value"][0]["command"] == "python -m pytest tests -q"
    assert tests["value"][0]["passed_count"] == 26
