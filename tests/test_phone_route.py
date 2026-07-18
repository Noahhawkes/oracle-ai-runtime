from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

from fastapi.testclient import TestClient  # noqa: E402


def _client() -> TestClient:
    import oracle_server as srv  # noqa: E402

    return TestClient(srv.app)


def test_phone_route_serves_mobile_cockpit():
    response = _client().get("/phone")

    assert response.status_code == 200
    assert "<title>ORACLE Phone</title>" in response.text
    assert "/api/continuity/operator-dashboard" in response.text
    assert "/api/human-state/transition" in response.text


def test_mobile_route_aliases_phone_cockpit():
    response = _client().get("/mobile")

    assert response.status_code == 200
    assert "<title>ORACLE Phone</title>" in response.text
    assert 'id="chatForm"' in response.text
