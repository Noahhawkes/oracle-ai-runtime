from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import continuity_event_packet as cep  # noqa: E402


def test_build_packet_contains_whole_event_spine():
    packet = cep.build_event_packet(
        user_text="Who is Noah Hawkes? Cite backend records.",
        assistant_output="Noah Hawkes is the approval authority. UNKNOWN where unsupported.",
        done_payload={
            "type": "done",
            "route_type": "talk_lane",
            "effective_route": "recall_orchestrator",
            "mode": "safe",
            "evidence": {
                "records_used_count": 1,
                "records_used": [{"surface": "document_atlas", "path": "C:/Oracle/doc.md"}],
                "sources_proven_used": ["document_atlas"],
                "unknowns": ["visual UI state not captured"],
            },
        },
        session_id="test-session",
        ui_mode="safe",
        conversation_turn_count=7,
    )

    assert packet["schema_version"] == "continuity_event_packet.v1"
    for key in (
        "event_id",
        "timestamp",
        "source",
        "speaker",
        "channel",
        "visible_context",
        "user_intent",
        "assistant_response",
        "evidence_used",
        "claims_extracted",
        "uncertainties",
        "corrections",
        "actions_proposed",
        "actions_taken",
        "authority_status",
        "memory_effect",
        "return_pointer",
    ):
        assert key in packet
    assert packet["human_source"] == "Noah.Physical"
    assert packet["source"] == "ORACLE /chat SSE"
    assert packet["speaker"] == "Noah.Physical"
    assert packet["channel"] == "ORACLE /chat SSE"
    assert packet["user_input"]["sha256"]
    assert packet["assistant_response"] == packet["assistant_output"]
    assert packet["evidence_used"] == packet["sources"]
    assert packet["return_pointer"] == packet["resume_point"]
    assert packet["assistant_output"]["sha256"]
    assert packet["route"]["effective_route"] == "recall_orchestrator"
    assert packet["sources"]["records_used_count"] == 1
    assert "visual UI state not captured" in packet["uncertainties"]
    assert packet["authority_status"]["approval_authority"] == "Noah.Physical"
    assert packet["canon_status"]["promotion_status"] == "not_promoted"
    assert packet["boundaries"]["sandbox_read_by_packet"] is False
    assert packet["boundaries"]["external_send"] is False


def test_source_resolution_metadata_becomes_candidate_claims():
    packet = cep.build_event_packet(
        user_text="How old am I?",
        assistant_output="You're 44.",
        done_payload={
            "type": "done",
            "route_type": "recall_orchestrator",
            "effective_route": "recall_orchestrator",
            "recall_evidence": {
                "source_resolution": {
                    "status": "RESOLVED",
                    "fact_domain": "personal_identity",
                    "field": "date_of_birth",
                    "selected_claim": {
                        "source_class": "governed_verified_identity_record",
                        "source_id": "identity-record-1",
                        "precision": "exact",
                    },
                    "candidate_claims": [{"source_id": "identity-record-1"}],
                    "conflicts": [],
                    "provenance_refs": ["remember_me"],
                }
            },
        },
        session_id="claim-test",
    )

    assert packet["claims_extracted"]
    claim = packet["claims_extracted"][0]
    assert claim["claim_type"] == "source_resolution"
    assert claim["status"] == "RESOLVED"
    assert claim["fact_domain"] == "personal_identity"
    assert claim["field"] == "date_of_birth"
    assert claim["selected_source_class"] == "governed_verified_identity_record"
    assert claim["boundary"] == "candidate extraction from resolver metadata; not canon promotion"


def test_write_packet_creates_local_candidate_files_without_sandbox(tmp_path):
    summary = cep.write_event_packet(
        user_text="Build a continuity event packet.",
        assistant_output="Done locally.",
        done_payload={"type": "done", "route_type": "talk_lane"},
        session_id="abc123",
        output_dir=tmp_path,
    )

    packet_path = Path(summary["packet_path"])
    latest_path = Path(summary["latest_path"])
    index_path = Path(summary["index_path"])

    assert summary["ok"] is True
    assert summary["canon_status"] == "candidate_event_record"
    assert summary["promotion_status"] == "not_promoted"
    assert packet_path.exists()
    assert latest_path.exists()
    assert index_path.exists()
    assert "sandbox" not in str(packet_path).lower()

    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    assert packet["memory_effect"]["continuity_packet_written"] is True
    assert packet["memory_effect"]["source_file_mutation"] is False
    assert packet["boundaries"]["command_exec"] is False
    assert packet["packet_hash_sha256"] == summary["packet_hash_sha256"]


def test_sandbox_receipt_in_visible_response_is_action_evidence_not_promotion(tmp_path):
    response = """
SANDBOX INITIATIVE RECEIPT
{
  "operation_type": "sandbox_initiative_write",
  "action_id": "sandbox_initiative_write_20260720T100000Z_abcd",
  "receipt_path": "C:\\Oracle\\ORACLE.AI-runtime\\sandbox\\receipts\\demo_receipt.json",
  "canon_status": "sandbox_candidate",
  "promotion_status": "not_promoted"
}
"""

    summary = cep.write_event_packet(
        user_text="Tell me if you wrote to sandbox.",
        assistant_output=response,
        done_payload={"type": "done", "route_type": "sandbox_initiative_write"},
        session_id="sandbox-visible-test",
        output_dir=tmp_path,
    )
    packet = json.loads(Path(summary["packet_path"]).read_text(encoding="utf-8"))

    assert packet["actions_executed"]
    assert packet["actions_executed"][0]["operation_type"] == "sandbox_initiative_write"
    assert packet["actions_executed"][0]["canon_promotion"] is False
    assert packet["boundaries"]["sandbox_read_by_packet"] is False
    assert packet["boundaries"]["sandbox_write_by_packet"] is False
    assert packet["canon_status"]["promotion_status"] == "not_promoted"
    assert any("demo_receipt.json" in item["path"] for item in packet["receipts"])


def test_status_and_latest_are_read_only_views(tmp_path):
    missing = cep.latest_event(output_dir=tmp_path)
    assert missing["ok"] is False

    cep.write_event_packet(
        user_text="round one",
        assistant_output="recorded",
        done_payload={"type": "done"},
        session_id="status-test",
        output_dir=tmp_path,
    )

    status = cep.status(output_dir=tmp_path)
    latest = cep.latest_event(output_dir=tmp_path)

    assert status["ok"] is True
    assert status["packet_count"] == 1
    assert status["boundaries"]["sandbox_touched"] is False
    assert latest["ok"] is True
    assert latest["packet"]["schema_version"] == cep.SCHEMA_VERSION
