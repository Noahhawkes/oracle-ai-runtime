from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import current_observation as co  # noqa: E402
import oracle_server as srv  # noqa: E402


def test_missing_receipt_nulls_current_fields(tmp_path):
    state = co.current_observation_state(path=tmp_path / "missing.json")

    assert state["receipt_status"] == "missing"
    assert state["fresh"] is False
    for field in co.OBSERVATION_FIELDS:
        assert state["fields"][field]["value"] is None
        assert state["fields"][field]["rendered_value"] == "UNKNOWN"

    text = co.format_current_observation_response(state)
    assert "application: UNKNOWN" in text
    assert "window_title: UNKNOWN" in text
    assert "visual_observation: UNKNOWN" in text
    assert "blocked_sources: historical_screenshot" in text


def test_webcam_receipt_does_not_infer_app_or_window(tmp_path):
    path = tmp_path / "current_observation_receipt.json"
    receipt = co.record_webcam_observation(
        {"available": True, "observation": "I can see a person near a desk.", "model": "vision-test"},
        path=path,
    )
    assert receipt is not None

    state = co.current_observation_state(path=path)
    assert state["receipt_status"] == "fresh"
    assert state["fields"]["visual_observation"]["value"] == "I can see a person near a desk."
    assert state["fields"]["application"]["value"] is None
    assert state["fields"]["window_title"]["value"] is None

    text = co.format_current_observation_response(state)
    assert "visual_observation: I can see a person near a desk." in text
    assert "application: UNKNOWN" in text
    assert "window_title: UNKNOWN" in text


def test_expired_receipt_loses_authority(tmp_path):
    path = tmp_path / "current_observation_receipt.json"
    start = datetime(2026, 6, 14, 12, 0, tzinfo=timezone.utc)
    receipt = co.create_observation_receipt(
        source="test_screen_observer",
        fields={"application": "Chrome", "window_title": "ChatGPT", "visual_observation": "Browser window"},
        ttl_seconds=1,
        now=start,
    )
    co.save_observation_receipt(receipt, path=path)

    state = co.current_observation_state(path=path, now=start + timedelta(seconds=2))
    assert state["receipt_status"] == "expired"
    assert state["expired"] is True
    assert state["fields"]["application"]["value"] is None
    assert state["fields"]["window_title"]["value"] is None

    text = co.format_current_observation_response(state)
    assert "application: UNKNOWN" in text
    assert "window_title: UNKNOWN" in text
    assert "Chrome" not in text
    assert "ChatGPT" not in text


def test_current_observation_gate_replaces_model_claim(monkeypatch, tmp_path):
    monkeypatch.setattr(co, "RECEIPT_PATH", tmp_path / "missing.json")
    monkeypatch.setattr(co, "RECEIPT_LOG_PATH", tmp_path / "missing.jsonl")

    reply = co.enforce_current_observation_boundary(
        "What application and window am I using?",
        "You are using Chrome in a ChatGPT window.",
    )

    assert reply.startswith("CURRENT_OBSERVATION")
    assert "application: UNKNOWN" in reply
    assert "window_title: UNKNOWN" in reply
    assert "Chrome" not in reply
    assert "ChatGPT" not in reply


def test_server_current_window_question_is_deterministic(monkeypatch, tmp_path):
    monkeypatch.setattr(co, "RECEIPT_PATH", tmp_path / "missing.json")
    monkeypatch.setattr(co, "RECEIPT_LOG_PATH", tmp_path / "missing.jsonl")

    reply = srv._deterministic_runtime_answer("What application and window am I using?")

    assert reply is not None
    assert reply.startswith("CURRENT_OBSERVATION")
    assert "application: UNKNOWN" in reply
    assert "window_title: UNKNOWN" in reply
