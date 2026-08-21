from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "core"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

from fastapi.testclient import TestClient  # noqa: E402
import oracle_server as srv  # noqa: E402


def test_human_baseline_api_private_and_public_views():
    client = TestClient(srv.app)

    private = client.get("/api/human-baseline")
    public = client.get("/api/human-baseline", params={"audience": "public"})

    assert private.status_code == 200
    assert public.status_code == 200
    private_body = private.json()
    public_body = public.json()
    assert private_body["ok"] is True
    assert private_body["baseline"]["human_id"] == "Noah.Physical"
    assert private_body["baseline"]["birth_date"] == "1982-02-02"
    assert private_body["baseline"]["birth_date_verification"] == "VERIFIED"
    assert private_body["baseline"]["family_summary"]["spouse"]["name"] == "Ashley"
    assert public_body["audience"] == "public"
    assert public_body["baseline"]["privacy_scope"]["default"] == "PUBLIC_SAFE"
    assert public_body["baseline"]["birth_date"] == "1982"
    assert "family_summary" not in public_body["baseline"]
    assert "Ashley" not in str(public_body["baseline"])
    assert "1982-02-02" not in str(public_body["baseline"])
    assert "C:\\Oracle" not in str(public_body["baseline"])
