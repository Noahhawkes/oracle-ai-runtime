from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ui_exposes_human_state_reentry_control():
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")

    assert 'id="human-state-btn"' in html
    assert "showHumanStatePanel()" in html
    assert "/api/human-state" in html
    assert "/api/reentry-brief" in html
    assert "Human State and Re-entry" in html
    assert "read-only brief; no build action triggered" in html


def test_ui_exposes_operator_dashboard_control():
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")

    assert 'id="operator-dashboard-btn"' in html
    assert "showOperatorDashboard()" in html
    assert "/api/continuity/operator-dashboard" in html
    assert "Operator Dashboard" in html
    assert "Top five open loops" in html
