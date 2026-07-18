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
import evidence_cockpit as ec  # noqa: E402


def test_cockpit_snapshot_is_read_only_and_enumerates_surfaces():
    snapshot = ec.cockpit_snapshot()

    assert snapshot["ok"] is True
    assert snapshot["surface_count"] >= 6
    assert snapshot["boundaries"]["sandbox_touched"] is False
    assert snapshot["boundaries"]["external_send"] is False
    assert snapshot["boundaries"]["canon_promotion"] is False
    assert any(item["id"] == "document_atlas" for item in snapshot["surfaces"])
    assert all("records" in item for item in snapshot["surfaces"])


def test_response_evidence_does_not_invent_record_usage():
    evidence = ec.response_evidence(
        "What did ORACLE use to answer this?",
        mode="talk_lane",
        effective_route="talk_lane",
        route_type="done",
    )

    assert evidence["ok"] is True
    assert evidence["mode"] == "witness"
    assert evidence["records_used_count"] == 0
    assert evidence["records_used"] == []
    assert "current_session_user_message" in evidence["sources_proven_used"]
    assert any("not yet instrumented" in item for item in evidence["unknowns"])


def test_evidence_cockpit_api_and_page():
    import oracle_server as srv  # noqa: E402

    client = TestClient(srv.app)
    status = client.get("/api/evidence-cockpit")
    assert status.status_code == 200
    assert status.json()["ok"] is True

    turn = client.post("/api/evidence-cockpit/turn", json={"message": "scan my QR tattoo"})
    assert turn.status_code == 200
    assert turn.json()["capability"] == "qr_scan"

    page = client.get("/evidence")
    assert page.status_code == 200
    assert "Evidence Cockpit" in page.text
