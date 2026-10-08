from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_phone_ui_wires_continuity_and_chat_surfaces():
    html = (ROOT / "ui" / "phone.html").read_text(encoding="utf-8")

    assert 'name="viewport"' in html
    assert "ORACLE Phone" in html
    assert 'id="chatForm"' in html
    assert "/api/continuity/operator-dashboard" in html
    assert "/api/human-state" in html
    assert "/api/reentry-brief" in html
    assert "/api/human-state/transition" in html
    assert 'fetch("/chat"' in html
    assert "/api/history" in html


def test_phone_ui_transition_controls_are_explicit_local_actions():
    html = (ROOT / "ui" / "phone.html").read_text(encoding="utf-8")

    assert 'source_system: "ORACLE.phone"' in html
    assert 'recordTransition("Back at the workstation")' in html
    assert 'recordTransition("Working on ORACLE from phone cockpit")' in html
    assert 'recordTransition("I\'m resting now")' in html
    assert 'recordTransition("I\'m going to sleep")' in html
