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


def test_sensitive_inventory_api_is_metadata_only(tmp_path, monkeypatch):
    monkeypatch.setattr(fr, "DEFAULT_ROOTS", [tmp_path])
    monkeypatch.setattr(fr, "MEMORY_DIR", tmp_path / "Memory")
    monkeypatch.setattr(fr, "RECEIPT_FILE", tmp_path / "Memory" / "receipts.jsonl")
    secret = tmp_path / "wallet_secret.txt"
    secret.write_text("DO_NOT_LEAK_WALLET_VALUE", encoding="utf-8")

    import oracle_server as srv  # noqa: E402

    response = TestClient(srv.app).get("/api/file-recall/sensitive-inventory", params={"q": "wallet", "limit": 5})
    payload = response.json()

    assert response.status_code == 200
    assert payload["operation_type"] == "file_recall_sensitive_inventory"
    assert payload["result_count"] == 1
    assert payload["results"][0]["name"] == "wallet_secret.txt"
    assert payload["results"][0]["content_available"] is False
    assert "DO_NOT_LEAK_WALLET_VALUE" not in response.text
