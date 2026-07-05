from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

from fastapi.testclient import TestClient  # noqa: E402
import sandbox_files as sf  # noqa: E402


def _receipt(path: str | None) -> dict:
    assert path
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("ORACLE_SKIP_SERVER_BOOT", "1")
    monkeypatch.delenv("ORACLE_SELF_PROMPT_CONTROL_STATE", raising=False)
    monkeypatch.delenv("ORACLE_AUTONOMOUS_SELF_PROMPT", raising=False)
    monkeypatch.delenv("ORACLE_AUTONOMOUS_SELF_PROMPT_LOOP", raising=False)
    monkeypatch.delenv("ORACLE_SELF_PROMPT_DAILY_CAP", raising=False)
    monkeypatch.delenv("ORACLE_SELF_PROMPT_INTERVAL", raising=False)
    monkeypatch.setattr(sf, "SANDBOX_ROOT", tmp_path / "sandbox")
    monkeypatch.setattr(sf, "SANDBOX_TRASH_ROOT", tmp_path / "sandbox.trash")

    import oracle_server as srv  # noqa: E402

    monkeypatch.setattr(srv, "_self_prompt_start_loop_task", lambda: None)
    monkeypatch.setattr(srv, "_self_prompt_stop_loop_task", lambda: None)
    monkeypatch.setattr(
        srv,
        "_generate_sandbox_self_response",
        lambda child_prompt, seed_text=None: (
            "selected_task: write a sandbox note\n"
            "why_it_helps_noah: it proves the governor works\n"
            "evidence_it_worked: receipt-backed local write\n"
            "refuse_without_noah_approval: external actions, canon promotion, computer control\n"
            "stop_after_this: true",
            True,
            "test-model",
            None,
        ),
    )
    return srv


def test_default_state_is_off(monkeypatch, tmp_path):
    srv = _isolate(monkeypatch, tmp_path)
    client = TestClient(srv.app)

    status = client.get("/api/self-prompt/status")

    assert status.status_code == 200
    assert status.json()["current_state"] == "OFF"
    assert status.json()["daily_count"] == 0
    assert status.json()["model_called"] is False


def test_manual_once_writes_one_artifact_receipt_and_reports_last_receipt(monkeypatch, tmp_path):
    srv = _isolate(monkeypatch, tmp_path)
    client = TestClient(srv.app)

    response = client.post("/api/self-prompt/manual-once", json={"seed_prompt": "manual proof"})
    payload = response.json()
    status = client.get("/api/self-prompt/status").json()

    assert response.status_code == 200
    assert payload["current_state"] == "OFF"
    assert payload["manual_once"] is True
    assert payload["model_called"] is True
    assert Path(payload["write_path"]).exists()
    assert Path(payload["write_receipt_path"]).exists()
    assert len(list((tmp_path / "sandbox" / "workbench").glob("oracle_self_prompt_*.ai"))) == 1
    assert len(list((tmp_path / "sandbox" / "receipts").glob("sandbox_self_prompt_write*_receipt.json"))) == 1
    assert status["last_receipt_path"] == payload["write_receipt_path"]
    assert status["last_write_path"] == payload["write_path"]
    assert status["model_called"] is True

    receipt = _receipt(payload["write_receipt_path"])
    assert receipt["external_send"] is False
    assert receipt["git_push"] is False
    assert receipt["computer_control"] is False
    assert receipt["canon_promotion"] is False


def test_autonomous_enabled_respects_sandbox_path_and_daily_cap(monkeypatch, tmp_path):
    srv = _isolate(monkeypatch, tmp_path)
    client = TestClient(srv.app)

    async def _noop_sleep(_seconds):
        return None

    monkeypatch.setattr(srv.asyncio, "sleep", _noop_sleep)

    enable = client.post("/api/self-prompt/enable", json={"seed_prompt": "enable autonomous"})
    assert enable.status_code == 200
    assert enable.json()["current_state"] == "SANDBOX_AUTONOMOUS_ENABLED"

    result = asyncio.run(
        srv._self_prompt_write_cycle(
            caller="ORACLE.self_prompt.autonomous_loop",
            source_route="ORACLE.self_prompt.autonomous_loop",
            seed_prompt="autonomous loop tick",
            final_state=srv._SELF_PROMPT_AUTONOMOUS,
        )
    )

    assert result["ok"] is True
    assert Path(result["write_result"]["final_path"]).is_relative_to((tmp_path / "sandbox").resolve())
    assert Path(result["write_result"]["receipt_path"]).exists()

    monkeypatch.setattr(srv, "_self_prompt_daily_count", lambda: srv._self_prompt_daily_cap())
    blocked = asyncio.run(
        srv._self_prompt_write_cycle(
            caller="ORACLE.self_prompt.autonomous_loop",
            source_route="ORACLE.self_prompt.autonomous_loop",
            seed_prompt="autonomous loop at cap",
            final_state=srv._SELF_PROMPT_AUTONOMOUS,
        )
    )

    assert blocked["blocked"] is True
    assert blocked["state"]["blocked_reason"] == "daily cap reached"
    assert len(list((tmp_path / "sandbox" / "workbench").glob("oracle_self_prompt_*.ai"))) == 1


def test_disable_prevents_loop_writes(monkeypatch, tmp_path):
    srv = _isolate(monkeypatch, tmp_path)
    client = TestClient(srv.app)

    enable = client.post("/api/self-prompt/enable")
    assert enable.status_code == 200

    disable = client.post("/api/self-prompt/disable")
    assert disable.status_code == 200
    assert disable.json()["current_state"] == "OFF"

    blocked = asyncio.run(
        srv._self_prompt_write_cycle(
            caller="ORACLE.self_prompt.autonomous_loop",
            source_route="ORACLE.self_prompt.autonomous_loop",
            seed_prompt="should not write",
            final_state=srv._SELF_PROMPT_AUTONOMOUS,
        )
    )

    assert blocked["blocked"] is True
    assert blocked["state"]["blocked_reason"] == "state is OFF"
    assert not list((tmp_path / "sandbox" / "workbench").glob("oracle_self_prompt_*.ai"))


def test_safe_sleep_blocks_loop_writes(monkeypatch, tmp_path):
    srv = _isolate(monkeypatch, tmp_path)
    client = TestClient(srv.app)

    safe_sleep = client.post("/api/self-prompt/safe-sleep")
    assert safe_sleep.status_code == 200
    assert safe_sleep.json()["current_state"] == "SAFE_SLEEP"

    blocked = asyncio.run(
        srv._self_prompt_write_cycle(
            caller="ORACLE.self_prompt.autonomous_loop",
            source_route="ORACLE.self_prompt.autonomous_loop",
            seed_prompt="should stay asleep",
            final_state=srv._SELF_PROMPT_AUTONOMOUS,
        )
    )

    assert blocked["blocked"] is True
    assert blocked["state"]["blocked_reason"] == "state is SAFE_SLEEP"
    assert not list((tmp_path / "sandbox" / "workbench").glob("oracle_self_prompt_*.ai"))
