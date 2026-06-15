"""
Static containment guarantees on the browser UI (ui/index.html).

These assert the *absence* of the automatic recurring vision path and the
*presence* of the explicit LOOK ONCE path. They are deterministic proxies for
browser behaviors that cannot run under pytest (camera off at startup, no
recurring timer, one request per press, no auto-speak, no chat auto-insertion).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")


# ── Automatic narration removed ──────────────────────────────────────────────

def test_no_recurring_vision_loop():
    assert "VISION_SAMPLE_MS" not in UI
    assert "_scheduleVisionTick" not in UI
    assert "function visionTick" not in UI
    assert "_sceneChanged" not in UI


def test_no_auto_chat_insertion_or_speech_from_camera():
    # The old auto-publish helper and its speak() call must be gone.
    assert "addVisionMessage" not in UI
    assert "speak(data.observation)" not in UI


def test_malformed_sees_tag_removed():
    # The literal that produced "seesI can see" must be impossible.
    assert ">sees<" not in UI
    assert 'vision-tag">sees<' not in UI


# ── Explicit LOOK ONCE present ───────────────────────────────────────────────

def test_look_once_present():
    assert "function lookOnce" in UI
    assert "LOOK ONCE" in UI
    assert "look-once-btn" in UI


def test_camera_observation_label_and_receipt():
    assert "CAMERA OBSERVATION" in UI
    assert "vision-receipt" in UI


def test_camera_off_at_startup():
    assert "let watching = false" in UI


def test_authorization_wired():
    assert "/api/camera/authorize" in UI
    assert "/api/camera/stop" in UI
    assert "beforeunload" in UI
    assert "_camAuth" in UI


def test_preview_start_does_not_call_see():
    # startVision must not POST /api/see; only lookOnce may.
    start = UI.split("async function startVision()", 1)[1].split("function stopVision()", 1)[0]
    assert "/api/see" not in start
