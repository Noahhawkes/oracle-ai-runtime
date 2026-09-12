from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for path in (ROOT, CORE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import oracle_tuneup as tuneup  # noqa: E402


SAMPLE_JOURNAL = """.AI:ORACLE_SELF_PROMPT_JOURNAL
created_at=2026-07-17T00:00:00Z

.AI:ORACLE_SELF_PROMPT_CYCLE
timestamp=2026-07-17T20:00:00Z
caller=ORACLE.self_prompt.autonomous_loop
source_route=ORACLE.self_prompt.autonomous_loop
sandbox_only=true
external_send=false
git_push=false
gdrive_edit=false
command_exec=false
computer_control=false
canon_promotion=false
model_called=true
model_name=test-model
child_prompt_sha256=abc
child_response_sha256=def
canon_status=sandbox_candidate
promotion_status=not_promoted

seed_prompt_excerpt:
autonomous tick

child_prompt:
choose one bounded task

child_response:
selected_task: inspect continuity
evidence_it_worked: candidate reflection only

self_reflection:
I completed exactly one sandbox-only self-prompt step and stopped.
"""


def test_self_prompt_journal_payload_is_read_only(tmp_path):
    sandbox = tmp_path / "sandbox"
    workbench = sandbox / "workbench"
    workbench.mkdir(parents=True)
    (workbench / "oracle_self_prompt_journal.ai").write_text(SAMPLE_JOURNAL, encoding="utf-8")

    payload = tuneup.self_prompt_journal_payload(3, sandbox_root=sandbox)

    assert payload["ok"] is True
    assert payload["operation_type"] == "self_prompt_journal_read"
    assert payload["entry_count"] == 1
    assert payload["boundary"]["read_only"] is True
    assert payload["boundary"]["sandbox_write"] is False
    assert payload["boundary"]["external_send"] is False
    assert payload["entries"][0]["child_response"].startswith("selected_task")
    assert payload["entries"][0]["boundary"]["sandbox_only"] is True


def test_connector_status_shape_uses_read_only_boundary():
    payload = tuneup.connector_status_payload({
        "current_state": "SANDBOX_AUTONOMOUS_ENABLED",
        "daily_count": 9,
        "daily_cap": 10,
        "journal_entry_count": 2,
        "loop_running": True,
        "journal_exists": True,
    })

    assert payload["ok"] is True
    assert payload["boundary"]["read_only"] is True
    assert payload["boundary"]["sandbox_write"] is False
    assert any(item["id"] == "self_prompt" for item in payload["connectors"])
    assert any("daily cap" in item for item in payload["priorities"])


def test_oracle_tuneup_routes_and_ui_are_exposed():
    server = (ROOT / "oracle_server.py").read_text(encoding="utf-8")
    ui = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")

    assert '@app.get("/api/self-prompt/journal")' in server
    assert '@app.get("/api/connectors/status")' in server
    assert 'id="self-notes-btn"' in ui
    assert 'id="tuneup-btn"' in ui
    assert "showSelfPromptJournal" in ui
    assert "showTuneupPanel" in ui
