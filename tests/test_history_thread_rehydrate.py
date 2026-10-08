from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "core"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import memory  # noqa: E402
import oracle_server as srv  # noqa: E402


def _client(monkeypatch, tmp_path: Path) -> TestClient:
    memory.DB_PATH = tmp_path / "oracle_memory.db"
    memory.init_db()
    monkeypatch.setattr(srv, "_history", [])
    monkeypatch.setattr(srv, "_session_id", 999999)
    return TestClient(srv.app)


def test_history_durable_fallback_returns_thread_resume_pointer(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    sid = memory.new_session()
    memory.save_message(sid, "user", "where were we with ORACLE?")
    memory.save_message(sid, "assistant", "Thread registry was the next bridge.")

    response = client.get("/api/history")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "durable"
    assert payload["session_id"] == sid
    assert payload["thread_source"] == "thread_registry"
    assert payload["thread_id"].startswith("thread_")
    assert payload["thread"]["thread_id"] == payload["thread_id"]
    assert payload["thread"]["session_id"] == str(sid)
    assert payload["thread"]["title"] == "where were we with ORACLE?"
    assert [turn["content"] for turn in payload["history"]] == [
        "where were we with ORACLE?",
        "Thread registry was the next bridge.",
    ]


def test_history_live_response_includes_current_thread_identity(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    sid = memory.new_session()
    memory.save_message(sid, "user", "live thread bridge")
    monkeypatch.setattr(srv, "_session_id", sid)
    monkeypatch.setattr(srv, "_history", [{"role": "user", "content": "live thread bridge"}])

    response = client.get("/api/history")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "live"
    assert payload["session_id"] == sid
    assert payload["thread_source"] == "thread_registry"
    assert payload["thread"]["session_id"] == str(sid)
