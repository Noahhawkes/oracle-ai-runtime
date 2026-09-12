from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import live_transmission as live  # noqa: E402


FALSE_FLAGS = (
    "conversation_reset",
    "cloud_api_used",
    "upload",
    "sync",
    "drive_modified",
    "onedrive_modified",
    "git_commit",
    "git_push",
    "recording_started_by_oracle",
    "screen_capture_started_by_oracle",
    "audio_capture_started_by_oracle",
    "clipboard_capture_started_by_oracle",
    "keystroke_capture_started_by_oracle",
    "credential_touched",
)


def test_live_start_writes_state_and_receipt(tmp_path):
    state_path = tmp_path / "context" / "live_transmission_latest.json"
    receipts_dir = tmp_path / "receipts"

    result = live.write_live_transmission_capture(
        state_path=state_path,
        receipts_dir=receipts_dir,
        notes="test live capture",
    )
    state = json.loads(state_path.read_text(encoding="utf-8"))
    receipt = json.loads(Path(result["receipt_path"]).read_text(encoding="utf-8"))

    assert result["response_text"].startswith("Live transmission captured.")
    assert state["action"] == "live_transmission_capture"
    assert state["session_state"] == "active_live_transmission"
    assert state["noah_physical_present"] is True
    assert state["oracle_runtime_active"] is True
    assert state["unified_mode_active"] is True
    assert state["cognition_fabric_active"] is True
    assert state["model_dependency_reduced"] is True
    assert state["privacy_posture"] == "elevated"
    assert state["recommended_mode"] == "metadata_only"
    assert receipt["receipt_id"].startswith("live_transmission_receipt_")

    for key in FALSE_FLAGS:
        assert state[key] is False
        assert receipt[key] is False


def test_live_status_reports_elevated_privacy(tmp_path):
    state_path = tmp_path / "context" / "live_transmission_latest.json"
    receipts_dir = tmp_path / "receipts"
    live.write_live_transmission_capture(state_path=state_path, receipts_dir=receipts_dir)

    state = live.read_live_state(state_path=state_path)
    text = live.format_live_status(state)

    assert state["live_transmission_active"] is True
    assert "LIVE PRIVACY ELEVATED" in text
    assert "RAW RECORDING OFF" in text
    assert "LOCAL ONLY" in text


def test_live_stop_keeps_raw_recording_off(tmp_path):
    state_path = tmp_path / "context" / "live_transmission_latest.json"
    receipts_dir = tmp_path / "receipts"

    result = live.write_live_transmission_capture(
        active=False,
        action="live_transmission_stop",
        state_path=state_path,
        receipts_dir=receipts_dir,
    )

    assert result["session_state"] == "inactive_live_transmission"
    assert result["raw_recording"] == "off"
    for key in FALSE_FLAGS:
        assert result[key] is False
