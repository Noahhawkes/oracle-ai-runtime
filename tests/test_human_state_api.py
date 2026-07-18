from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

from fastapi.testclient import TestClient  # noqa: E402
import human_state  # noqa: E402
import memory  # noqa: E402
import project_state  # noqa: E402


def _client(monkeypatch, tmp_path):
    monkeypatch.setenv("ORACLE_SKIP_SERVER_BOOT", "1")
    monkeypatch.setattr(memory, "DB_PATH", tmp_path / "Memory" / "oracle_memory.db")
    monkeypatch.setattr(project_state, "STATES_FILE", tmp_path / "Memory" / "project_states.json")
    human_state.ensure_schema()
    import oracle_server as srv  # noqa: E402

    return TestClient(srv.app)


async def _collect_stream_payloads(srv, prompt: str) -> list[dict]:
    payloads: list[dict] = []
    async for chunk in srv._stream_reply(prompt):
        if chunk.startswith("data: "):
            payloads.append(json.loads(chunk[len("data: "):].strip()))
    return payloads


def test_human_state_api_defaults_unknown(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    response = client.get("/api/human-state")

    assert response.status_code == 200
    assert response.json()["current_mode"] == "UNKNOWN"


def test_human_state_transition_api_records_explicit_local_event(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    response = client.post(
        "/api/human-state/transition",
        json={
            "source_text": "I'm in bed now",
            "source_system": "test",
            "open_loops": ["do not start build work"],
        },
    )
    state = client.get("/api/human-state").json()
    brief = client.get("/api/reentry-brief").json()

    assert response.status_code == 200
    assert response.json()["recorded"] is True
    assert state["current_mode"] == "SLEEP"
    assert brief["last_known_mode"] == "SLEEP"
    assert brief["open_loops"] == ["do not start build work"]
    assert brief["boundary"] == "read-only brief; no build action triggered"
    assert client.get("/api/status").json()["human_state"]["current_mode"] == "SLEEP"


def test_human_state_transition_api_rejects_missing_text(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    response = client.post("/api/human-state/transition", json={})

    assert response.status_code == 400
    assert response.json()["error"] == "source_text required"


def test_human_state_transition_api_accepts_noah_correction(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    response = client.post(
        "/api/human-state/transition",
        json={"source_text": "correct this state", "new_mode": "WORK_WRITING"},
    )

    assert response.status_code == 200
    assert response.json()["event"]["new_mode"] == "WORK_WRITING"


def test_chat_workstation_return_records_transition_and_returns_reentry(monkeypatch, tmp_path):
    monkeypatch.setenv("ORACLE_SKIP_SERVER_BOOT", "1")
    monkeypatch.setattr(memory, "DB_PATH", tmp_path / "Memory" / "oracle_memory.db")
    monkeypatch.setattr(project_state, "STATES_FILE", tmp_path / "Memory" / "project_states.json")
    monkeypatch.setattr(memory, "save_message", lambda *_, **__: None)
    human_state.ensure_schema()
    import oracle_server as srv  # noqa: E402

    payloads = asyncio.run(_collect_stream_payloads(srv, "Back at the workstation"))
    route = next(item for item in payloads if item.get("type") == "route")
    token = next(item for item in payloads if item.get("type") == "token")
    done = next(item for item in payloads if item.get("type") == "done")

    assert route["route_type"] == "human_reentry"
    assert route["human_state_transition"]["recorded"] is True
    assert "Human transition recorded: WORK_ORACLE" in token["text"]
    assert "RE-ENTRY BRIEF" in token["text"]
    assert done["effective_route"] == "human_reentry"
    assert human_state.current_state()["current_mode"] == "WORK_ORACLE"


def test_chat_reentry_command_is_read_only(monkeypatch, tmp_path):
    monkeypatch.setenv("ORACLE_SKIP_SERVER_BOOT", "1")
    monkeypatch.setattr(memory, "DB_PATH", tmp_path / "Memory" / "oracle_memory.db")
    monkeypatch.setattr(project_state, "STATES_FILE", tmp_path / "Memory" / "project_states.json")
    monkeypatch.setattr(memory, "save_message", lambda *_, **__: None)
    human_state.ensure_schema()
    human_state.record_transition("I'm in bed now", source_system="test")
    import oracle_server as srv  # noqa: E402

    payloads = asyncio.run(_collect_stream_payloads(srv, "/reentry"))
    route = next(item for item in payloads if item.get("type") == "route")
    token = next(item for item in payloads if item.get("type") == "token")

    assert route["route_type"] == "human_reentry"
    assert route["human_state_transition"] is None
    assert "last_known_mode: SLEEP" in token["text"]
    assert "boundary: read-only brief; no build action triggered" in token["text"]
