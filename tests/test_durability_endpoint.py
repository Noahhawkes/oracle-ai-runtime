from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "core"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import oracle_server as srv  # noqa: E402
import thread_capture  # noqa: E402


def test_durability_endpoint_reports_sqlite_and_candidate_custody(monkeypatch, tmp_path):
    memory_dir = tmp_path / "Memory"
    memory_dir.mkdir()
    db_path = memory_dir / "oracle_memory.db"
    with sqlite3.connect(db_path) as con:
        con.execute("create table messages (id integer primary key, session_id integer, role text, content text)")
        con.execute("create table facts (id integer primary key, category text, content text)")
        con.execute("insert into messages (session_id, role, content) values (233, 'user', 'hello')")
        con.execute("insert into messages (session_id, role, content) values (233, 'assistant', 'hi')")
        con.execute("insert into messages (session_id, role, content) values (232, 'user', 'old')")
        con.execute("insert into facts (category, content) values ('thread_recall', 'recall fact')")
        con.execute("insert into facts (category, content) values ('thread_capture', 'capture fact')")

    receipt_dir = memory_dir / "thread_ingest" / "custody_receipts"
    receipt_dir.mkdir(parents=True)
    receipt_path = receipt_dir / "receipt.json"
    receipt_path.write_text('{"ok": true}', encoding="utf-8")

    monkeypatch.setattr(srv, "ROOT", tmp_path)
    monkeypatch.setattr(srv, "_session_id", 233)
    monkeypatch.setattr(
        thread_capture,
        "status",
        lambda: {
            "raw_artifact_count": 1,
            "parsed_transcript_count": 1,
            "custody_receipt_count": 1,
            "search_index_rows": 2,
            "raw_transcripts_dir": str(tmp_path / "raw_transcripts"),
            "search_index_jsonl": str(tmp_path / "search_index.jsonl"),
        },
    )

    response = TestClient(srv.app).get("/api/durability")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["session_id"] == 233
    assert payload["persistence_safe_to_refresh"] is True
    assert payload["canon_status_for_captures"] == "candidate"
    assert payload["promotion_status_for_captures"] == "not_promoted"
    assert payload["sqlite"]["current_session_message_count"] == 2
    assert payload["sqlite"]["message_count"] == 3
    assert payload["thread_evidence_facts"]["total_thread_evidence"] == 2
    assert payload["thread_capture"]["raw_artifact_count"] == 1
    assert payload["last_custody_receipt_path"].endswith("receipt.json")


def test_ui_durability_controls_are_interactive():
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")

    assert 'id="durability-detail"' in html
    assert "function showDurabilityDetail" in html
    assert "function showRuntimeDetail" in html
    assert "bindDurabilityControls();" in html
    assert "apiUrl('/api/durability')" in html
    assert "apiUrl('/api/status')" in html

    for kind in ("save", "history", "thread", "custody", "index", "receipt"):
        assert f'data-durability-detail="{kind}"' in html
