from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for path in (ROOT, CORE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import self_prompt_tasklist as spt  # noqa: E402


SAMPLE_JOURNAL = """.AI:ORACLE_SELF_PROMPT_CYCLE
child_response:
purpose_lane: memory_gap
selected_task: review install_autostart.bat for one continuity gap
self_reflection:
done
.AI:ORACLE_SELF_PROMPT_CYCLE
child_response:
purpose_lane: runtime_improvement
selected_task: compare active_context_sync.py against route receipts
self_reflection:
done
"""


def test_tasklist_context_includes_recent_active_and_dead_candidates(tmp_path):
    candidates_path = tmp_path / "action_candidates.json"
    candidates_path.write_text(
        json.dumps(
            [
                {
                    "id": "pending-123456",
                    "status": "pending",
                    "risk_level": "low",
                    "title": "compare active_context_sync.py against route receipts",
                    "updated_at": "2026-07-25T14:00:00+00:00",
                },
                {
                    "id": "quarantine-123456",
                    "status": "quarantined",
                    "risk_level": "low",
                    "title": "review install_autostart.bat for one continuity gap",
                    "updated_at": "2026-07-25T13:00:00+00:00",
                },
            ]
        ),
        encoding="utf-8",
    )

    context = spt.render_tasklist_context(
        journal_text=SAMPLE_JOURNAL,
        candidates_path=candidates_path,
    )

    assert ".AI:SELF_PROMPT_TASKLIST" in context
    assert "read_only=true" in context
    assert "recent_selected_tasks_do_not_repeat:" in context
    assert "compare active_context_sync.py against route receipts" in context
    assert "active_candidates_in_play:" in context
    assert "pending | low | pending-" in context
    assert "dead_or_quarantined_candidates_do_not_resubmit:" in context
    assert "quarantined | low | quaranti" in context
    assert "quality_gate: discard_no_write" in context


def test_tasklist_context_handles_missing_candidate_file():
    context = spt.render_tasklist_context(
        journal_text="selected_task: draft one pytest for the sandbox mirror",
        candidates_path=Path("missing-action-candidates.json"),
    )

    assert "draft one pytest for the sandbox mirror" in context
    assert "active_candidates_in_play:\n- none_found" in context
    assert "dead_or_quarantined_candidates_do_not_resubmit:\n- none_found" in context
