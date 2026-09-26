from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for path in (ROOT, CORE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

from continuity_event import ContinuityEventPacket, ContinuityLedgerWriter  # noqa: E402
import orchestrator  # noqa: E402


def test_event_packet_durability(tmp_path):
    ledger_file = tmp_path / "test_events.jsonl"
    writer = ContinuityLedgerWriter(ledger_path=ledger_file)

    packet = ContinuityEventPacket(
        source="Noah.Physical",
        speaker="user",
        user_intent="Verify source resolver grounding",
        visible_context=["thread_001"],
        evidence_used=[{"path": "core/source_resolver.py", "hash": "a1b2c3d4"}],
        authority_status="VERIFIED",
        memory_effect="THREAD_APPEND",
        return_pointer="th_20260820_01",
    )

    writer.record_event(packet)

    assert ledger_file.exists()
    lines = ledger_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1

    data = json.loads(lines[0])
    assert data["event_id"].startswith("evt_")
    assert data["authority_status"] == "VERIFIED"
    assert data["evidence_used"][0]["hash"] == "a1b2c3d4"


def test_turn_lifecycle_resolves_executes_and_seals_once(tmp_path):
    ledger_file = tmp_path / "events.jsonl"
    writer = ContinuityLedgerWriter(ledger_path=ledger_file)
    lifecycle = orchestrator.instantiate_turn(
        "Verify source resolver grounding",
        thread_id="thread_001",
        visible_context=["mode:companion"],
    )

    receipt = orchestrator.record_completed_turn(
        lifecycle,
        assistant_response="Grounded response.",
        done_payload={
            "type": "done",
            "mode": "companion",
            "effective_route": "recall_orchestrator",
            "evidence": {
                "ok": True,
                "records_used_count": 1,
                "records_used": [{
                    "source_id": "resolver-test",
                    "path": "core/source_resolver.py",
                    "line_range": "1-20",
                    "sha256": "a1b2c3d4",
                }],
                "unknowns": ["one unresolved detail"],
            },
            "recall_evidence": {"source_resolution": {"status": "RESOLVED"}},
        },
        writer=writer,
        return_pointer="thread_001",
    )

    assert receipt["ok"] is True
    assert receipt["authority_status"] == "VERIFIED"
    assert receipt["memory_effect"] == "LEDGER_SEAL"
    packet = json.loads(ledger_file.read_text(encoding="utf-8").strip())
    assert packet["assistant_response"] == "Grounded response."
    assert packet["return_pointer"] == "thread_001"
    assert packet["evidence_used"][0]["hash"] == "a1b2c3d4"
    assert "one unresolved detail" in packet["uncertainties"]

    try:
        orchestrator.seal_turn(lifecycle, writer=writer)
    except RuntimeError as exc:
        assert "already sealed" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("a turn must not be sealed twice")
    assert len(ledger_file.read_text(encoding="utf-8").splitlines()) == 1


def test_invalid_authority_status_is_not_written(tmp_path):
    ledger_file = tmp_path / "events.jsonl"
    writer = ContinuityLedgerWriter(ledger_path=ledger_file)
    packet = ContinuityEventPacket(authority_status="CERTAIN")

    try:
        writer.record_event(packet)
    except ValueError as exc:
        assert "unsupported authority_status" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("invalid packet should be refused")
    assert not ledger_file.exists()


def test_chat_endpoint_seals_one_central_event(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    import oracle_server as server

    ledger_file = tmp_path / "chat_events.jsonl"
    real_writer = ContinuityLedgerWriter(ledger_path=ledger_file)
    monkeypatch.setattr(orchestrator, "ContinuityLedgerWriter", lambda: real_writer)

    response = TestClient(server.app).post(
        "/chat",
        json={"message": "/help", "mode": "companion"},
    )

    assert response.status_code == 200
    events = [
        json.loads(line[len("data: "):])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    done = [event for event in events if event.get("type") == "done"][-1]
    receipt = done["continuity_event"]
    assert receipt["ok"] is True
    assert receipt["ledger_path"] == str(ledger_file)
    assert receipt["return_pointer"] == str(server._session_id)
    assert len(ledger_file.read_text(encoding="utf-8").splitlines()) == 1

    packet = json.loads(ledger_file.read_text(encoding="utf-8").strip())
    assert packet["user_intent"] == "/help"
    assert "ORACLE Commands" in packet["assistant_response"]
    assert packet["memory_effect"] == "LEDGER_SEAL"
