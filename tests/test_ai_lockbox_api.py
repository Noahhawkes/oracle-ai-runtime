from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

from fastapi.testclient import TestClient  # noqa: E402
import ai_lockbox as lb  # noqa: E402
import file_recall as fr  # noqa: E402


def _wire_tmp_lockbox(monkeypatch, tmp_path):
    lockbox = tmp_path / "Memory" / "ai_lockbox"
    monkeypatch.setattr(lb, "LOCKBOX_DIR", lockbox)
    monkeypatch.setattr(lb, "CAPSULE_DIR", lockbox / "capsules")
    monkeypatch.setattr(lb, "MANIFEST_FILE", lockbox / "manifest.jsonl")
    monkeypatch.setattr(lb, "RECEIPT_FILE", lockbox / "receipts.jsonl")
    monkeypatch.setattr(lb, "LATEST_STATUS_FILE", lockbox / "latest_status.json")
    monkeypatch.setattr(lb, "DEFAULT_ROOTS", [tmp_path])
    monkeypatch.setattr(fr, "DEFAULT_ROOTS", [tmp_path])
    monkeypatch.setattr(fr, "MEMORY_DIR", tmp_path / "Memory")
    monkeypatch.setattr(fr, "RECEIPT_FILE", tmp_path / "Memory" / "file_recall_receipts.jsonl")


def test_ai_lockbox_api_ingest_status_search_and_capsule(tmp_path, monkeypatch):
    _wire_tmp_lockbox(monkeypatch, tmp_path)
    source = tmp_path / "oracle_recall.md"
    source.write_text("ORACLE recall capsule with Rendered Reality continuity.", encoding="utf-8")

    import oracle_server as srv  # noqa: E402

    client = TestClient(srv.app)

    ingest = client.post("/api/ai-lockbox/ingest", json={"query": "", "limit": 5})
    assert ingest.status_code == 200
    assert ingest.json()["created_count"] == 1

    status = client.get("/api/ai-lockbox/status")
    assert status.status_code == 200
    assert status.json()["capsule_count"] == 1

    search = client.get("/api/ai-lockbox/search", params={"q": "Rendered Reality", "limit": 5})
    assert search.status_code == 200
    assert search.json()["result_count"] == 1

    single = tmp_path / "single.ai"
    single.write_text("Single source shorthand.", encoding="utf-8")
    capsule = client.get("/api/ai-lockbox/capsule", params={"path": str(single)})
    assert capsule.status_code == 200
    assert capsule.json()["name"] == "single.ai"


def test_ai_lockbox_search_requires_query(tmp_path, monkeypatch):
    _wire_tmp_lockbox(monkeypatch, tmp_path)
    import oracle_server as srv  # noqa: E402

    response = TestClient(srv.app).get("/api/ai-lockbox/search")

    assert response.status_code == 400
    assert "query is required" in response.text
