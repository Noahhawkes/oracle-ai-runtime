import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))


def _fake_obs():
    return {
        "obs_running": True,
        "obs_websocket_available": True,
        "current_scene_name": "Recursion Arena",
        "recording_active": False,
        "streaming_active": False,
        "source_names": ["ORACLE UI"],
        "timestamp": "2026-06-19T00:00:00Z",
        "warning": None,
    }


def _fake_window():
    return {
        "active_window_title": "ORACLE SourceMap",
        "active_process_name": "chrome",
        "timestamp": "2026-06-19T00:00:01Z",
        "confidence": "medium",
        "observation_mode": "metadata_only",
        "warning": None,
    }


def test_witness_defaults_off_and_does_not_call_providers(monkeypatch, tmp_path):
    import rendered_reality_witness as witness

    monkeypatch.setattr(witness, "RECEIPTS_DIR", tmp_path / "receipts")
    monkeypatch.setattr(witness, "SOURCES_DIR", tmp_path / "sources")
    monkeypatch.setattr(witness, "LATEST_MANIFEST", tmp_path / "sources" / "oracle_source_manifest_latest.json")
    witness.set_witness_mode("off")

    def boom():
        raise AssertionError("provider should not be called while witness is off")

    status = witness.get_witness_status()
    context = witness.refresh_live_context(obs_provider=boom, window_provider=boom)

    assert status["mode"] == "off"
    assert status["enabled"] is False
    assert context["observation_skipped"] is True
    assert context["obs"] is None
    assert context["window"] is None


def test_metadata_only_receipt_records_only_metadata(monkeypatch, tmp_path):
    import rendered_reality_witness as witness

    monkeypatch.setattr(witness, "RECEIPTS_DIR", tmp_path / "receipts")
    monkeypatch.setattr(witness, "SOURCES_DIR", tmp_path / "sources")
    monkeypatch.setattr(witness, "LATEST_MANIFEST", tmp_path / "sources" / "oracle_source_manifest_latest.json")
    witness.set_witness_mode("metadata_only")

    receipt = witness.write_session_receipt(
        notes="test receipt",
        obs_provider=_fake_obs,
        window_provider=_fake_window,
    )

    path = tmp_path / "receipts" / (receipt["receipt_path"].split("\\")[-1])
    if not path.exists():
        path = tmp_path / "receipts" / receipt["receipt_path"].split("/")[-1]

    assert receipt["witness_mode"] == "metadata_only"
    assert receipt["obs_scene"] == "Recursion Arena"
    assert receipt["active_process_name"] == "chrome"
    assert receipt["files_moved"] == 0
    assert receipt["files_deleted"] == 0
    assert receipt["files_renamed"] == 0
    assert receipt["files_synced"] == 0
    assert receipt["git_commits"] == 0
    assert receipt["git_pushes"] == 0
    assert receipt["no_screenshots_stored"] is True
    assert receipt["no_audio_recorded"] is True
    assert receipt["no_video_recorded"] is True
    assert receipt["no_keystrokes_captured"] is True
    assert receipt["no_clipboard_captured"] is True
    assert path.exists()


def test_manifest_entry_is_linked_source_and_not_canonical(monkeypatch, tmp_path):
    import rendered_reality_witness as witness

    sources_dir = tmp_path / "sources"
    monkeypatch.setattr(witness, "SOURCES_DIR", sources_dir)
    monkeypatch.setattr(witness, "LATEST_MANIFEST", sources_dir / "oracle_source_manifest_latest.json")
    witness.set_witness_mode("metadata_only")

    latest = json.loads((sources_dir / "oracle_source_manifest_latest.json").read_text(encoding="utf-8"))
    entries = [item for item in latest["sources"] if item["source_id"] == "rendered_reality_live_witness"]

    assert len(entries) == 1
    assert entries[0]["source_type"] == "live_context"
    assert entries[0]["canonical_status"] == "linked_source"
    assert entries[0]["write_allowed"] is False
    assert "No screenshots" in entries[0]["notes"]


def test_receipt_is_blocked_while_off(monkeypatch, tmp_path):
    import rendered_reality_witness as witness

    monkeypatch.setattr(witness, "RECEIPTS_DIR", tmp_path / "receipts")
    witness.set_witness_mode("off")

    with pytest.raises(PermissionError):
        witness.write_session_receipt(obs_provider=_fake_obs, window_provider=_fake_window)
