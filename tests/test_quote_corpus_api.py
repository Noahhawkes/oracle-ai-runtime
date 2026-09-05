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
import file_recall as fr  # noqa: E402
import quote_corpus as qc  # noqa: E402


def _wire_tmp_quote_corpus(monkeypatch, tmp_path):
    quote_root = tmp_path / "Memory" / "quote_corpus"
    monkeypatch.setattr(qc, "QUOTE_DIR", quote_root)
    monkeypatch.setattr(qc, "PACKET_DIR", quote_root / "packets")
    monkeypatch.setattr(qc, "MANIFEST_FILE", quote_root / "manifest.jsonl")
    monkeypatch.setattr(qc, "RECEIPT_FILE", quote_root / "receipts.jsonl")
    monkeypatch.setattr(qc, "LATEST_STATUS_FILE", quote_root / "latest_status.json")
    monkeypatch.setattr(qc, "DEFAULT_ROOTS", [tmp_path])
    monkeypatch.setattr(fr, "DEFAULT_ROOTS", [tmp_path])
    monkeypatch.setattr(fr, "MEMORY_DIR", tmp_path / "Memory")
    monkeypatch.setattr(fr, "RECEIPT_FILE", tmp_path / "Memory" / "file_recall_receipts.jsonl")


def test_quote_corpus_api_ingest_status_search_and_packet(tmp_path, monkeypatch):
    _wire_tmp_quote_corpus(monkeypatch, tmp_path)
    source = tmp_path / "rendered_reality.md"
    source.write_text(
        "Rendered Reality quote packets preserve exact Noah-authored excerpts with hashes. "
        "ORACLE can then cite evidence without converting summaries into proof.",
        encoding="utf-8",
    )

    import oracle_server as srv  # noqa: E402

    client = TestClient(srv.app)

    ingest = client.post("/api/quote-corpus/ingest", json={"query": "rendered", "limit": 5})
    assert ingest.status_code == 200
    assert ingest.json()["created_count"] == 1

    status = client.get("/api/quote-corpus/status")
    assert status.status_code == 200
    assert status.json()["source_count"] == 1

    search = client.get("/api/quote-corpus/search", params={"q": "Noah-authored excerpts", "limit": 5})
    assert search.status_code == 200
    assert search.json()["result_count"] == 1

    single = tmp_path / "single.ai"
    single.write_text(
        "Single exact quote source packet for ORACLE recall verification and source discipline.",
        encoding="utf-8",
    )
    packet = client.get("/api/quote-corpus/packet", params={"path": str(single)})
    assert packet.status_code == 200
    assert packet.json()["source_path"] == str(single.resolve())


def test_quote_corpus_search_requires_query(tmp_path, monkeypatch):
    _wire_tmp_quote_corpus(monkeypatch, tmp_path)
    import oracle_server as srv  # noqa: E402

    response = TestClient(srv.app).get("/api/quote-corpus/search")

    assert response.status_code == 400
    assert "query is required" in response.text
