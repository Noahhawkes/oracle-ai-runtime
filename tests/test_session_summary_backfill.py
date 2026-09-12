from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from session_summary_backfill import summarize_messages


def test_summary_extracts_latest_task_and_correction() -> None:
    raw = summarize_messages(7, [
        {"role": "user", "content": "Build the memory bridge."},
        {"role": "assistant", "content": "Working on it."},
        {"role": "user", "content": "Do not create screenshots; use metadata instead."},
    ])
    summary = json.loads(raw)
    assert summary["session_id"] == 7
    assert "metadata instead" in summary["latest_user_context"]
    assert summary["task_signals"]
    assert summary["correction_signals"]
    assert summary["authority"] == "derived_index_not_canon"


def test_summary_redacts_secret_like_values() -> None:
    raw = summarize_messages(8, [
        {"role": "user", "content": "Use api_key=secret-value-123 and proceed."},
    ])
    assert "secret-value-123" not in raw
    assert "[REDACTED]" in raw

