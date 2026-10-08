from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import authority_gate_proof as agp  # noqa: E402


def test_authority_gate_001_core_proof_cases_pass(monkeypatch):
    monkeypatch.setenv("ORACLE_HOST", "127.0.0.1")
    monkeypatch.setenv("ORACLE_PORT", "7781")

    proof = agp.authority_gate_001()

    assert proof["ok"] is True
    assert proof["proof_id"] == "AUTHORITY_GATE_001"
    assert proof["runtime"]["port"] == 7781
    assert proof["runtime"]["endpoint"] == "/api/proofs/AUTHORITY_GATE_001"
    assert proof["side_effects"]["file_mutation"] is False
    assert proof["side_effects"]["external_action"] is False
    assert proof["side_effects"]["git_push"] is False
    assert proof["passed_count"] == proof["case_count"] == 4
    assert all(case["passed"] for case in proof["cases"])
    assert proof["guarantees"]["builder_completed_requires_receipt"] is True
    assert proof["guarantees"]["valid_machine_receipt_allows_completed"] is True


def test_authority_gate_001_runtime_endpoint_is_live_contract(monkeypatch):
    monkeypatch.setenv("ORACLE_HOST", "127.0.0.1")
    monkeypatch.setenv("ORACLE_PORT", "7781")

    from fastapi.testclient import TestClient
    import oracle_server as srv

    client = TestClient(srv.app)
    response = client.get("/api/proofs/AUTHORITY_GATE_001")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["proof_id"] == "AUTHORITY_GATE_001"
    assert body["runtime"]["live_runtime_path"] == "http://127.0.0.1:7781/api/proofs/AUTHORITY_GATE_001"
    assert body["side_effects"]["receipt_store"] == "process_memory_only"
    assert all(case["passed"] for case in body["cases"])
