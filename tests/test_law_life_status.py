"""Tests for ORACLE's Law/Life status and USER.AI -> NPC seed bridge."""
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

import camera_receipt as cr  # noqa: E402
import current_observation as co  # noqa: E402
import law_life_status as ll  # noqa: E402
import npc_seed_bridge as nsb  # noqa: E402
import oracle_server as srv  # noqa: E402


def test_observation_status_keeps_screen_and_camera_receipts_distinct(monkeypatch, tmp_path):
    monkeypatch.setattr(co, "RECEIPT_PATH", tmp_path / "missing_current.json")
    monkeypatch.setattr(co, "RECEIPT_LOG_PATH", tmp_path / "missing_current.jsonl")
    monkeypatch.setattr(cr, "RECEIPT_PATH", tmp_path / "camera_observation_receipt.json")

    receipt = cr.build_receipt(
        observation_text="UNKNOWN",
        correlation_id="corr-test",
        session_id="sess-test",
        authorization_id="auth-test",
        device_id="dev-test",
        track_label="Test Camera",
        model=None,
        confidence="none",
        published_to_chat=True,
    )
    cr.save_receipt(receipt)

    status = ll.build_observation_status()
    assert status["current_observation"]["receipt_status"] == "missing"
    assert status["camera_observation"]["receipt_status"] == "present"
    assert status["camera_observation"]["receipt_id"] == receipt["observation_id"]
    assert status["last_observation"]["source"] == "camera_observation"
    assert status["last_observation"]["text"] == "UNKNOWN"


def test_law_life_status_reports_ready_layers_and_guarded_bridge():
    status = ll.build_law_life_status()
    assert status["law"]["status"] in ("ready", "missing")
    assert status["life"]["status"] == "ready"
    assert status["bridge"]["runtime_instantiation_status"] in ("not_wired", "unknown")

    text = ll.summarize_law_life_status(status)
    assert text.startswith("VERIFIED [LAW_LIFE_STATUS]")
    assert "Law layer:" in text
    assert "Life layer:" in text
    assert "USER.AI" in text
    assert "no person-specific NPC is instantiated" in text


def test_npc_seed_bridge_blocks_other_person_without_subject_opt_in():
    seed = nsb.relationship_to_npc_seed({
        "id": "rel-brooklyn",
        "name": "Brooklyn",
        "sov_id": "SOV3.AI",
        "relationship_type": "family",
        "trust_tier": "sovereign_family",
        "status": "approved",
        "tags": ["USER.AI"],
    })
    assert seed["display_name"] == "Brooklyn"
    assert seed["consent_status"] == "requires_subject_opt_in"
    assert seed["npc_creation_allowed"] is False
    assert "ambient_surveillance" in seed["blocked_inputs"]


def test_npc_seed_bridge_allows_self_seed_after_owner_approval():
    seed = nsb.relationship_to_npc_seed({
        "id": "rel-noah",
        "name": "Noah",
        "sov_id": "SOV1.AI",
        "relationship_type": "self",
        "trust_tier": "sovereign",
        "status": "approved",
        "tags": ["USER.AI"],
    })
    assert seed["consent_status"] == "owner_approved"
    assert seed["npc_creation_allowed"] is True


def test_server_law_life_question_is_deterministic():
    reply = srv._deterministic_runtime_answer("show USER.AI law and life NPC bridge status")
    assert reply is not None
    assert reply.startswith("VERIFIED [LAW_LIFE_STATUS]") or reply.startswith("UNAVAILABLE [LAW_LIFE_STATUS]")
