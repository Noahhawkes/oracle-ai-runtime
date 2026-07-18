from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_oracle_ui_exposes_ai_lockbox_recall_and_speech_controls():
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")

    assert 'id="ai-lockbox-btn"' in html
    assert "showAiLockboxDetail()" in html
    assert "refreshAiLockboxStatus()" in html
    assert "/api/ai-lockbox/status" in html
    assert "/api/ai-lockbox/ingest" in html
    assert "/api/ai-lockbox/search" in html
    assert "Search + Speak" in html
    assert "speak(`AI Lockbox found" in html
    assert "/ai-lockbox-status" in html
    assert "/ai-lockbox-search" in html
