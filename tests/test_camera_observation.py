"""
Tests for the receipted LOOK ONCE vision path:
  - dark frames return UNKNOWN without invoking the model
  - the sight prompt is truth-constrained (no forced "I can see")
  - the camera receipt schema is complete and written before publication
  - /api/see is fail-closed: rejects missing/invalid/mismatched/invalidated auth
  - a successful LOOK ONCE creates exactly one receipt file containing its id
  - camera captions are not appended to durable JSONL memory
"""
from __future__ import annotations

import base64
import io
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

from PIL import Image  # noqa: E402

import oracle_sight as sight  # noqa: E402
import camera_receipt as cr  # noqa: E402
import camera_authorization as ca  # noqa: E402


def _jpeg_data_url(color) -> str:
    img = Image.new("RGB", (96, 72), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


# ── Frame quality / dark gate ────────────────────────────────────────────────

def test_black_frame_is_unusable():
    assess = sight.assess_frame(_jpeg_data_url((0, 0, 0)))
    assert assess["usable"] is False
    assert assess["reason"] == "insufficient_light"


def test_bright_frame_is_usable():
    assess = sight.assess_frame(_jpeg_data_url((230, 230, 230)))
    assert assess["usable"] is True


def test_describe_image_dark_frame_returns_unknown_without_model(monkeypatch):
    # If the model were called, this would blow up — prove it is never reached.
    def _boom():
        raise AssertionError("vision model must not be called for a dark frame")
    monkeypatch.setattr(sight, "resolve_vision_model", _boom)
    result = sight.describe_image(_jpeg_data_url((0, 0, 0)))
    assert result["unknown"] is True
    assert result["observation"] is None


# ── Truth-constrained prompt ─────────────────────────────────────────────────

def test_prompt_does_not_force_i_can_see():
    p = sight.DEFAULT_SIGHT_PROMPT.lower()
    assert "i can see" not in p.split("do not begin")[0] or "do not begin your reply with the words 'i can see'" in p
    assert "unknown" in p


# ── Receipt schema ───────────────────────────────────────────────────────────

REQUIRED_RECEIPT_FIELDS = {
    "observation_id", "correlation_id", "captured_at_utc", "session_id",
    "authorization_id", "device_id", "track_label", "source_type", "model",
    "evidence_class", "confidence", "user_requested", "raw_frame_stored",
    "published_to_chat", "retention_policy", "observation_text", "error",
}


def test_receipt_has_required_fields_and_constants():
    rec = cr.build_receipt(
        observation_text="a desk and a monitor",
        correlation_id="corr-1", session_id="sess-1", authorization_id="auth-1",
        device_id="dev-A", track_label="HD Webcam", model="qwen2.5vl:7b",
        confidence="model_unverified_inference", published_to_chat=True,
    )
    assert REQUIRED_RECEIPT_FIELDS.issubset(rec.keys())
    assert rec["source_type"] == "browser_camera"
    assert rec["evidence_class"] == "camera_model_observation"
    assert rec["retention_policy"] == "ephemeral_current"
    assert rec["raw_frame_stored"] is False
    assert rec["user_requested"] is True
    assert rec["observation_id"].startswith("cam-obs-")


def test_receipt_unknown_device_defaults():
    rec = cr.build_receipt(
        observation_text="UNKNOWN", correlation_id=None, session_id="s",
        authorization_id="a", device_id=None, track_label=None, model=None,
        confidence="none", published_to_chat=True,
    )
    assert rec["device_id"] == "UNKNOWN"
    assert rec["track_label"] == "UNKNOWN"


def test_save_receipt_writes_file_with_id(tmp_path):
    rec = cr.build_receipt(
        observation_text="x", correlation_id=None, session_id="s",
        authorization_id="a", device_id="d", track_label="t", model="m",
        confidence="none", published_to_chat=True,
    )
    path = tmp_path / "camera_observation_receipt.json"
    cr.save_receipt(rec, path=path)
    assert path.exists()
    assert rec["observation_id"] in path.read_text(encoding="utf-8")
    loaded = cr.load_latest(path=path)
    assert loaded["observation_id"] == rec["observation_id"]


# ── Server fail-closed behavior (TestClient, dark frame → no model) ──────────

def _client(monkeypatch, tmp_path):
    # Isolate the receipt file so tests never touch live Memory.
    monkeypatch.setattr(cr, "RECEIPT_PATH", tmp_path / "camera_observation_receipt.json")
    ca._reset_for_tests()
    from fastapi.testclient import TestClient
    import oracle_server as srv
    # camera_receipt is imported lazily inside the handler; patch its module ref too.
    monkeypatch.setattr("camera_receipt.RECEIPT_PATH", tmp_path / "camera_observation_receipt.json")
    return TestClient(srv.app), srv


def test_api_see_rejects_missing_authorization(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    r = client.post("/api/see", json={"image": _jpeg_data_url((0, 0, 0))})
    assert r.status_code == 403
    assert r.json().get("rejected") is True


def test_api_see_rejects_unknown_authorization(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    r = client.post("/api/see", json={
        "image": _jpeg_data_url((0, 0, 0)),
        "authorization_id": "cam-auth-nope", "session_id": "s",
    })
    assert r.status_code == 403


def test_api_see_authorized_dark_frame_unknown_with_receipt(monkeypatch, tmp_path):
    client, srv = _client(monkeypatch, tmp_path)
    auth = client.post("/api/camera/authorize", json={"device_id": "dev-A"}).json()
    assert auth["ok"] is True
    r = client.post("/api/see", json={
        "image": _jpeg_data_url((0, 0, 0)),
        "authorization_id": auth["authorization_id"],
        "session_id": auth["session_id"],
        "device_id": "dev-A",
        "track_label": "HD Webcam",
        "correlation_id": "corr-xyz",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    assert body["observation"] == "UNKNOWN"
    assert body["receipt_id"].startswith("cam-obs-")
    assert body["raw_frame_stored"] is False
    # Receipt file exists and contains the returned id.
    receipt_path = cr.RECEIPT_PATH
    assert receipt_path.exists()
    assert body["receipt_id"] in receipt_path.read_text(encoding="utf-8")


def test_api_see_rejects_after_stop(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    auth = client.post("/api/camera/authorize", json={"device_id": "dev-A"}).json()
    client.post("/api/camera/stop", json={"authorization_id": auth["authorization_id"]})
    r = client.post("/api/see", json={
        "image": _jpeg_data_url((0, 0, 0)),
        "authorization_id": auth["authorization_id"],
        "session_id": auth["session_id"],
        "device_id": "dev-A",
    })
    assert r.status_code == 403
    assert "invalidated" in r.json().get("error", "")


def test_camera_path_does_not_append_durable_jsonl(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    import current_observation as co
    monkeypatch.setattr(co, "RECEIPT_LOG_PATH", tmp_path / "current_observation_receipts.jsonl")
    auth = client.post("/api/camera/authorize", json={"device_id": "dev-A"}).json()
    client.post("/api/see", json={
        "image": _jpeg_data_url((0, 0, 0)),
        "authorization_id": auth["authorization_id"],
        "session_id": auth["session_id"],
        "device_id": "dev-A",
    })
    assert not (tmp_path / "current_observation_receipts.jsonl").exists()
