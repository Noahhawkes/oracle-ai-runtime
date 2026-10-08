"""Focused tests for agent_gateway.py (ORACLE -> ChatGPT read-only gateway V1).

Covers: auth required, bad token rejected, health/state succeed, recall reuses
ORACLE's existing memory path, missing recall returns empty (not fabrication),
all endpoints read-only, path traversal impossible, no command-exec surface,
no secret leakage, no canon/approval mutation surface.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "core"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")
TOKEN = "test-token-abc123"
os.environ["ORACLE_AGENT_GATEWAY_TOKEN"] = TOKEN
# Point runtime probes at an unreachable port so tests never depend on a live
# ORACLE and prove the "subsystem down -> unavailable, not fabricated" path.
os.environ["ORACLE_RUNTIME_URL"] = "http://127.0.0.1:9"
os.environ["OLLAMA_URL"] = "http://127.0.0.1:9"

import agent_gateway as gw  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(gw.app)
AUTH = {"Authorization": f"Bearer {TOKEN}"}
ENVELOPE_KEYS = {"status", "retrieved_at", "source", "data"}


# ── authentication ──

def test_auth_required():
    assert client.get("/agent/health").status_code == 401


def test_bad_token_rejected():
    r = client.get("/agent/health", headers={"Authorization": "Bearer wrong-token"})
    assert r.status_code == 401


def test_malformed_auth_header_rejected():
    assert client.get("/agent/health", headers={"Authorization": TOKEN}).status_code == 401


# ── envelope + core endpoints succeed ──

def test_health_endpoint_succeeds():
    r = client.get("/agent/health", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert ENVELOPE_KEYS.issubset(body)
    # runtime is unreachable in tests -> honest 'offline/unavailable', never faked online.
    assert body["status"] in {"verified", "partial", "unavailable"}
    if body["status"] == "unavailable":
        assert body["data"].get("runtime") == "offline"


def test_state_endpoint_succeeds():
    r = client.get("/agent/state", headers=AUTH)
    assert r.status_code == 200
    assert ENVELOPE_KEYS.issubset(r.json())


def test_models_and_open_questions_and_receipts_return_envelope():
    for path in ("/agent/models", "/agent/open-questions", "/agent/receipts/latest"):
        r = client.get(path, headers=AUTH)
        assert r.status_code == 200, path
        assert ENVELOPE_KEYS.issubset(r.json()), path


# ── recall reuses ORACLE's existing memory path ──

def _patch_recall(monkeypatch, records):
    ro = pytest.importorskip("recall_orchestrator")
    calls = {}

    def spy_build_context(user_text, **kw):
        calls["query"] = user_text
        return {"records": list(records)}

    monkeypatch.setattr(ro, "build_context", spy_build_context)
    monkeypatch.setattr(ro, "evidence_payload", lambda ctx: {"evidence_class": "spy"})
    return calls


def test_recall_uses_existing_oracle_recall_path(monkeypatch):
    calls = _patch_recall(monkeypatch, [{"id": "rec1", "source": "document_atlas"}])
    r = client.post("/agent/recall", headers=AUTH, json={"query": "SOV1", "limit": 5})
    assert r.status_code == 200
    body = r.json()
    # Proves the gateway routed the query through recall_orchestrator.build_context.
    assert calls.get("query") == "SOV1"
    assert body["source"].startswith("recall_orchestrator")
    assert body["data"]["records"] == [{"id": "rec1", "source": "document_atlas"}]
    assert body["data"]["evidence"] == {"evidence_class": "spy"}


def test_missing_memory_returns_empty_not_fabrication(monkeypatch):
    _patch_recall(monkeypatch, [])
    r = client.post("/agent/recall", headers=AUTH, json={"query": "nonexistent-xyz", "limit": 10})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["records"] == []            # empty, not invented
    assert data["record_count"] == 0
    assert "no matching records" in (data["note"] or "")
    assert r.json()["status"] == "verified"  # verified-empty, an honest 'nothing on record'


def test_recall_requires_nonempty_query():
    assert client.post("/agent/recall", headers=AUTH, json={"query": "", "limit": 5}).status_code == 422


# ── read-only hard boundary ──

def test_all_v1_endpoints_are_read_only():
    mutating = {"PUT", "PATCH", "DELETE"}
    for route in gw.app.routes:
        methods = getattr(route, "methods", set()) or set()
        path = getattr(route, "path", "")
        assert not (methods & mutating), f"{path} exposes a mutating method: {methods}"
        if path == "/agent/recall":
            assert "POST" in methods
        elif path.startswith("/agent/"):
            assert methods <= {"GET", "HEAD", "OPTIONS"}, f"{path} unexpectedly non-GET: {methods}"


def test_mutating_verb_on_readonly_endpoint_rejected():
    assert client.delete("/agent/state", headers=AUTH).status_code in (404, 405)
    assert client.put("/agent/health", headers=AUTH).status_code in (404, 405)


# ── security guarantees (source-level: the capability simply is not present) ──

GATEWAY_SRC = (ROOT / "agent_gateway.py").read_text(encoding="utf-8")


def test_no_command_execution_surface():
    for danger in ("subprocess", "os.system", "os.popen", "eval(", "exec(", "__import__("):
        assert danger not in GATEWAY_SRC, f"command-exec surface present: {danger}"


def test_no_filesystem_mutation_or_traversal_surface():
    # no writes / deletes anywhere in the gateway
    for danger in (".write_text(", ".write_bytes(", "os.remove(", ".unlink(", "shutil.rmtree", "rmtree"):
        assert danger not in GATEWAY_SRC, f"filesystem-mutation surface present: {danger}"
    # endpoints take no filesystem path input: recall query is passed to build_context
    # (corpus recall), never opened as a path. A traversal string is treated as text.
    import recall_orchestrator as ro  # type: ignore

    seen = {}
    ro_build = getattr(ro, "build_context")

    def _spy(t, **k):
        seen["q"] = t
        return {"records": []}

    try:
        ro.build_context = _spy
        ro.evidence_payload = lambda c: {}
        r = client.post("/agent/recall", headers=AUTH,
                        json={"query": "../../../../etc/passwd", "limit": 3})
        assert r.status_code == 200
        # the traversal string was handled as an opaque query, not a file path
        assert seen.get("q") == "../../../../etc/passwd"
        assert r.json()["data"]["records"] == []
    finally:
        ro.build_context = ro_build


def test_no_canon_or_approval_mutation_surface():
    for danger in ("update_status", "save_state(", "promote", "approve(", "reject(",
                   "canon_write", "write_route", "sandbox_self_prompt_write", "git "):
        assert danger not in GATEWAY_SRC, f"mutation surface present: {danger}"


def test_no_secret_leaks_into_responses():
    for path in ("/agent/health", "/agent/state", "/agent/models",
                 "/agent/open-questions", "/agent/receipts/latest"):
        body = client.get(path, headers=AUTH).text
        assert TOKEN not in body, f"token leaked in {path}"
        assert "ORACLE_AGENT_GATEWAY_TOKEN" not in body, f"secret env name leaked in {path}"


def test_gateway_fails_closed_without_token(monkeypatch):
    monkeypatch.delenv("ORACLE_AGENT_GATEWAY_TOKEN", raising=False)
    monkeypatch.setattr(gw, "_load_token", lambda: None)
    # even with a bearer header, no configured token -> refuse (503), never open access
    assert client.get("/agent/health", headers=AUTH).status_code == 503
