import hashlib
import json
from pathlib import Path

import pytest

from core import witness_telemetry as wt


def _event(*, title: str = "Secret draft - Browser", store_title: bool = False):
    return wt.public_event(
        observed_at="2026-08-02T00:00:00Z",
        process_name="browser.exe",
        state="active",
        keyboard_activity_count=4,
        mouse_click_count=1,
        window_title=title,
        store_window_titles=store_title,
    )


def test_default_event_stores_counts_not_key_content_or_title():
    event = _event()
    serialized = json.dumps(event)
    assert event["keyboard_activity_count"] == 4
    assert event["mouse_click_count"] == 1
    assert event["window_title_sha256"] == hashlib.sha256(b"Secret draft - Browser").hexdigest()
    assert "window_title" not in event
    for forbidden in ("keystroke", "key_code", "clipboard", "password", "Secret draft", "url"):
        assert forbidden not in serialized


def test_window_title_requires_explicit_opt_in():
    assert _event(store_title=True)["window_title"] == "Secret draft - Browser"


def test_safe_output_blocks_escape_and_forbidden_extensions(tmp_path: Path):
    with pytest.raises(ValueError, match="escapes"):
        wt._safe_output(tmp_path, "../outside.json")
    with pytest.raises(ValueError, match="extension"):
        wt._safe_output(tmp_path, "payload.exe")


def test_write_run_stays_inside_root_and_creates_hash_receipt(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(wt, "DEFAULT_TELEMETRY_ROOT", tmp_path)
    result = wt.write_run([_event(title="")])
    for key in ("session", "summary", "receipt"):
        assert result[key].resolve().is_relative_to(tmp_path.resolve())
        assert result[key].exists()

    summary = json.loads(result["summary"].read_text(encoding="utf-8"))
    receipt = json.loads(result["receipt"].read_text(encoding="utf-8"))
    assert summary["canon_status"] == "raw_signal"
    assert summary["promotion_status"] == "not_promoted"
    assert summary["content_capture"] is False
    assert receipt["external_action"] is False
    assert receipt["automatic_boot_start"] is False
    assert receipt["session_sha256"] == hashlib.sha256(result["session"].read_bytes()).hexdigest()
    assert receipt["summary_sha256"] == hashlib.sha256(result["summary"].read_bytes()).hexdigest()


def test_duration_and_interval_are_bounded():
    with pytest.raises(ValueError):
        wt.collect(0)
    with pytest.raises(ValueError):
        wt.collect(3601)
    with pytest.raises(ValueError):
        wt.collect(1, interval=0.01)
