from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

from fastapi.testclient import TestClient  # noqa: E402
import continuity_spine as cs  # noqa: E402
import human_state  # noqa: E402
import memory  # noqa: E402
import project_state  # noqa: E402


def _client(monkeypatch, tmp_path):
    monkeypatch.setenv("ORACLE_SKIP_SERVER_BOOT", "1")
    monkeypatch.setattr(memory, "DB_PATH", tmp_path / "Memory" / "oracle_memory.db")
    monkeypatch.setattr(project_state, "STATES_FILE", tmp_path / "Memory" / "project_states.json")
    monkeypatch.setattr(cs, "ROOT", tmp_path)
    human_state.ensure_schema()
    state = project_state.get_or_create("ORACLE")
    state.next_recommended_step = "Review continuity dashboard"
    state.current_blocker = "No dashboard endpoint"
    state.open_questions = ["Which loop is top priority?"]
    project_state.save_state(state)
    human_state.record_transition("Back at the workstation", source_system="test")
    receipt_dir = tmp_path / "sandbox" / "receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    (receipt_dir / "api_receipt.json").write_text(
        json.dumps({"receipt_id": "api", "operation_type": "api_test"}),
        encoding="utf-8",
    )
    import oracle_server as srv  # noqa: E402

    return TestClient(srv.app)


def test_continuity_spine_endpoints(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    spine = client.get("/api/continuity/spine").json()
    loops = client.get("/api/continuity/open-loops").json()
    timeline = client.get("/api/continuity/timeline").json()
    health = client.get("/api/continuity/health").json()
    dashboard = client.get("/api/continuity/operator-dashboard").json()
    digest = client.get("/api/continuity/daily-digest").json()

    assert spine["ok"] is True
    assert spine["current_project"]["project_name"] == "ORACLE"
    assert loops["count"] >= 2
    assert any(node["type"] == "human_transition" for node in timeline["timeline"])
    assert health["metric_boundary"] == "measured system counts only; no AI scoring"
    assert dashboard["suggested_resume_action"].startswith("Resolve blocker:")
    assert digest["boundary"] == "derived from ledgers only; no invented work"
