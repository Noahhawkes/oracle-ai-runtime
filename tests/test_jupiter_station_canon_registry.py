import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "core"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import canon_registry as cr  # noqa: E402
import oracle_server as srv  # noqa: E402
import talk_synthesis as ts  # noqa: E402

REGISTRY_PATH = ROOT / "data" / "canon_registry" / "jupiter_station_2397.json"
PROFILE_PATH = ROOT / "data" / "domains" / "jupiter_station" / "domain_profile.json"
MANIFEST_PATH = ROOT / "data" / "domains" / "jupiter_station" / "source_manifest.jsonl"
DOC_PATH = ROOT / "docs" / "jupiter_station_2397_canon_registry.md"


class _FakeBootstrap:
    def source_sections(self, current_session=None):
        return {"CURRENT_SESSION": [], "IDENTITY": [], "LIVE_CONTEXT": [], "LATEST_REFLECTION": []}


def _registry():
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _profile():
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def _manifest_rows():
    return [
        json.loads(line)
        for line in MANIFEST_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_jupiter_station_registry_has_required_statuses_and_boundaries():
    registry = _registry()
    allowed = set(registry["allowed_statuses"])
    entries = registry["entries"]

    assert allowed == {
        "active_canon",
        "candidate_canon",
        "demoted_canon",
        "alternate_branch",
        "rejected",
        "unknown",
    }
    assert any(entry["id"] == "JS-ACTIVE-ERA-2397" and entry["canon_status"] == "active_canon" for entry in entries)
    assert any(entry["id"] == "JS-DEMOTED-2481-ACTIVE-ERA" and entry["canon_status"] == "demoted_canon" for entry in entries)
    assert any(entry["id"] == "JS-TANGLY-NIGHT-SHIFT" and entry["canon_status"] == "active_canon" for entry in entries)
    assert all(entry["canon_status"] in allowed for entry in entries)
    assert registry["authority"] == "Noah.Physical"
    assert registry["write_allowed"] is False


def test_jupiter_station_profile_is_read_only_and_protected():
    profile = _profile()
    text = json.dumps(profile).lower()

    assert profile["name"] == "jupiter_station"
    assert profile["canon_status"] == "active_canon"
    assert profile["read_allowed"] is True
    assert profile["write_allowed"] is False
    assert profile["approval_authority"] == "Noah.Physical"
    assert "jupiter station" in text
    assert "uss avalon" in text
    assert "tangly" in text
    assert "noah.physical" in text
    assert "generic assistant fallback" in text


def test_jupiter_station_manifest_reaches_talk_grounding():
    hits = ts.domain_grounding_lookup("What is Jupiter Station active era?", max_hits=5)

    assert hits
    assert hits[0]["source"] == "data/domains/jupiter_station/source_manifest.jsonl"
    assert any(hit.get("canon_status") == "active_canon" for hit in hits)
    assert any("2397" in (hit.get("note") or "") for hit in hits)
    assert any("2481" in (hit.get("note") or "") for hit in hits)


def test_jupiter_station_grounding_packet_uses_registry_not_missing_boundary():
    packet = ts.synthesis_grounding_packet("What is Jupiter Station active era and the Avalon timeline?", max_hits=5)
    block = packet["grounding_block"]

    assert packet["active"] is True
    assert packet["direct_reply"] is None
    assert "SOURCEMAP/MIRACLEDRIVE GROUNDING" in block
    assert "data/domains/jupiter_station/source_manifest.jsonl" in block
    assert "2397 active era" in block or "2397" in block
    assert "demote 2481" in block or "2481" in block
    assert "Do not open with generic ORACLE identity boilerplate" in block


def test_jupiter_station_gate_rejects_generic_or_old_timeline_claims():
    prompt = "What is Jupiter Station active era and the Avalon timeline?"

    assert "generic assistant fallback" in ts.violation_reasons(
        prompt,
        "How can I assist you today?",
        [],
    )[0]
    assert "missing Jupiter Station 2397 active-era lock" in ts.violation_reasons(
        prompt,
        "Jupiter Station is a Federation archive hub.",
        [],
    )
    assert "undemoted 2481 active-era claim" in ts.violation_reasons(
        prompt,
        "Jupiter Station's active era is 2481.",
        [],
    )


def test_jupiter_station_gate_accepts_2397_receipt_custody_answer():
    prompt = "What is Jupiter Station active era, Voyager boundary, and Avalon timeline?"
    answer = (
        "Jupiter Station / USS Avalon active_canon is 2397. "
        "2481 is demoted_canon unless Noah.Physical restores it. "
        "Hawkes enters Voyager in 2371 at age 16, Voyager returns in 2378, "
        "and Avalon enters active service around 2379 with Hawkes as first captain. "
        "Temporal Acceleration Service Credit: Starfleet promoted the years the "
        "timeline refused to count. Source path: "
        "C:/Oracle/ORACLE.AI-runtime/data/domains/jupiter_station/source_manifest.jsonl; "
        "sha256: d7f48434e9970c3ef074f6b07f731dd488b9382937160f1fe520d50dc5e0756a."
    )

    assert ts.violation_reasons(prompt, answer, []) == []


def test_jupiter_station_structured_boundary_renders_registry_custody():
    prompt = "What is Jupiter Station active era and Avalon timeline?"
    reply = ts.synthesis_boundary_message(
        ["missing Jupiter Station 2397 active-era lock"],
        prompt,
    )

    assert "Jupiter Station readout" in reply
    assert "2397" in reply
    assert "2481" in reply
    assert "2371" in reply
    assert "2378" in reply
    assert "2379" in reply
    assert "source=" in reply
    assert "path=" in reply or "sha256=" in reply
    assert ts.violation_reasons(prompt, reply, []) == []


def test_current_session_source_binding_covers_tangly_and_dad_domains():
    tangly_reply = srv._source_disciplined_response(
        "What does Tangly mean to the crew?",
        _FakeBootstrap(),
        [{"role": "user", "content": "Tangly is the night-shift AI Science Officer on Avalon."}],
    )
    dad_reply = srv._source_disciplined_response(
        "What does Dad mean to ORACLE?",
        _FakeBootstrap(),
        [{"role": "user", "content": "Dad is Noah.Physical authority in protected domains."}],
    )

    assert tangly_reply is not None
    assert "source_type=current_session_user_submission" in tangly_reply
    assert "night-shift AI Science Officer" in tangly_reply
    assert "canon_status=raw_capture" in tangly_reply
    assert dad_reply is not None
    assert "submitted_by=Noah.Physical" in dad_reply
    assert "Noah.Physical authority" in dad_reply
    assert "promotion_status=not_promoted" in dad_reply


def test_canon_registry_status_payload_and_api_are_read_only():
    payload = cr.status_payload()

    assert payload["ok"] is True
    assert payload["registry_id"] == "jupiter_station_2397_canon_registry"
    assert payload["canon_status_counts"]["active_canon"] >= 1
    assert payload["canon_status_counts"]["demoted_canon"] >= 1
    assert "JS-ACTIVE-ERA-2397" in payload["active_canon_ids"]
    assert "JS-DEMOTED-2481-ACTIVE-ERA" in payload["demoted_canon_ids"]
    assert payload["no_write_actions"]["drive_edit"] is False
    assert payload["no_write_actions"]["git_push"] is False

    from fastapi.testclient import TestClient

    response = TestClient(srv.app).get("/api/canon/jupiter-station")
    assert response.status_code == 200
    api_payload = response.json()
    assert api_payload["ok"] is True
    assert api_payload["no_write_actions"]["git_commit"] is False
    assert api_payload["no_write_actions"]["canon_promoted_by_runtime"] is False


def test_jupiter_station_doc_preserves_no_external_mutation_boundary():
    doc = DOC_PATH.read_text(encoding="utf-8").lower()

    assert "active jupiter station / uss avalon era: 2397" in doc
    assert "demoted active-era reference: 2481" in doc
    assert "no git commit or push" in doc
    assert "no drive edit" in doc
    assert "no executable generation" in doc
