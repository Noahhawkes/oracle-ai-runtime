from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for path in (ROOT, CORE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import advanced_continuity_standard as acs  # noqa: E402


def test_standard_snapshot_is_honest_and_read_only():
    snapshot = acs.capability_standard_snapshot()

    assert snapshot["ok"] is True
    assert snapshot["standard_id"] == "advanced_continuity_standard.v1"
    assert snapshot["dimension_count"] >= 12
    assert 0 <= snapshot["readiness_fraction"] <= 1
    assert "not a sentience claim" in snapshot["current_claim"].lower()
    assert snapshot["boundaries"]["read_only"] is True
    assert snapshot["boundaries"]["sandbox_inspected"] is False
    assert snapshot["boundaries"]["sandbox_written"] is False
    assert snapshot["boundaries"]["external_send"] is False
    assert snapshot["boundaries"]["command_exec"] is False
    assert snapshot["boundaries"]["canon_promotion"] is False


def test_standard_dimensions_cover_noahs_requested_capabilities():
    dimensions = {item["id"]: item for item in acs.capability_standard_snapshot()["dimensions"]}

    expected = {
        "whole_room_memory",
        "interruption_reentry",
        "identity_boundary",
        "domain_separation",
        "execution_proof",
        "governed_recursion",
        "federated_intelligence",
        "uncertainty_preservation",
        "consequence_modeling",
        "relationship_context",
        "research_discovery",
        "restraint_and_authority",
    }
    assert expected.issubset(dimensions)
    assert dimensions["execution_proof"]["status"] in {"verified", "partial"}
    assert dimensions["restraint_and_authority"]["status"] in {"verified", "partial"}
    assert dimensions["whole_room_memory"]["holes"]
    assert "visible_ui_state" in " ".join(dimensions["whole_room_memory"]["holes"])


def test_standard_summary_does_not_certify_world_best_or_life():
    text = acs.format_standard_summary()

    lower = text.lower()
    assert "advanced continuity standard" in lower
    assert "sentient" not in lower
    assert "certified world-best" not in lower
    assert "proves life" not in lower
    assert "no sandbox" in lower
    assert "canon promotion" in lower


def test_standard_api_route_is_exposed():
    from fastapi.testclient import TestClient  # noqa: E402
    import oracle_server as srv  # noqa: E402

    client = TestClient(srv.app)
    response = client.get("/api/advanced-continuity-standard")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["standard_id"] == "advanced_continuity_standard.v1"
    assert body["boundaries"]["sandbox_inspected"] is False
