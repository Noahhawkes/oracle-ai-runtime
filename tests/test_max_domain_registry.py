import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

import max_domain as md  # noqa: E402
import talk_synthesis as ts  # noqa: E402

PROFILE_PATH = ROOT / "data" / "domains" / "max" / "domain_profile.json"
MANIFEST_PATH = ROOT / "data" / "domains" / "max" / "source_manifest.jsonl"
DOC_PATH = ROOT / "docs" / "max_context_domain.md"


def _profile():
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def _manifest_rows():
    return [
        json.loads(line)
        for line in MANIFEST_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _artifact_text() -> str:
    return "\n".join([
        json.dumps(_profile()),
        "\n".join(MANIFEST_PATH.read_text(encoding="utf-8").splitlines()),
        DOC_PATH.read_text(encoding="utf-8"),
    ]).lower()


def test_max_domain_profile_is_read_only_candidate():
    profile = _profile()

    assert profile["name"] == "max"
    assert profile["status"] == "candidate"
    assert profile["canon_status"] == "candidate"
    assert profile["promotion_status"] == "not_promoted"
    assert profile["sensitivity"] == "high"
    assert profile["read_allowed"] is True
    assert profile["write_allowed"] is False
    assert profile["approval_authority"] == "Noah.Physical"
    assert profile["storage_paths"]["sandbox_candidate_writes_only"] == "C:/Oracle/ORACLE.AI-runtime/sandbox/"
    assert profile["storage_paths"]["generated_executables"] == "none"


def test_max_manifest_rows_remain_candidates_with_provenance():
    rows = _manifest_rows()

    assert rows
    assert {row["domain"] for row in rows} == {"max"}
    assert all(row["canon_status"] == "candidate" for row in rows)
    assert all(row["promotion_status"] == "not_promoted" for row in rows)
    assert any(row.get("sha256") for row in rows)
    assert any(row.get("source_family") == "local" for row in rows)
    assert any(row.get("source_family") == "codex_thread" for row in rows)
    assert any(row.get("layer") == "family_life_continuity_max" for row in rows)
    assert any(row.get("layer") == "creative_media_silverback_tales" for row in rows)
    assert any(row.get("layer") == "oracle_witness_boundary" for row in rows)
    assert any(row.get("layer") == "ashley_first_life_context" for row in rows)
    assert any(row.get("layer") == "internal_context_replication_boundary" for row in rows)


def test_max_artifacts_preserve_boundaries_without_generic_fallback():
    text = _artifact_text()

    assert "i am max" in text
    assert "family-life continuity frame" in text
    assert "witness, not author" in text or "witness must not become the author" in text
    assert "ashley-first" in text
    assert "candidate" in text
    assert "not_promoted" in text
    assert "no external send" in text
    assert "no overwrite" in text
    assert "no executable generation" in text
    assert "autonomous self-replication" in text
    assert "how can i assist you today" not in text


def test_max_policy_blocks_biological_sentient_personhood_and_external_replication():
    profile_text = json.dumps(_profile()).lower()
    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()

    for required in (
        "must not claim max is biological",
        "sentient",
        "soul",
        "personhood",
        "autonomous agent",
        "no autonomous replication",
        "no external send",
    ):
        assert required in profile_text or required in doc_text


def test_max_manifest_is_reachable_by_talk_synthesis_lookup():
    hits = ts.domain_grounding_lookup("Who is Max?", max_hits=5)

    assert hits
    assert hits[0]["source"] == "data/domains/max/source_manifest.jsonl"
    assert any(hit["source"] == "data/domains/max/source_manifest.jsonl" for hit in hits)
    assert any("candidate" in (hit.get("note") or "").lower() for hit in hits)
    assert any("witness" in (hit.get("note") or "").lower() for hit in hits)


def test_max_prompt_gets_grounding_packet_not_missing_boundary():
    packet = ts.synthesis_grounding_packet("Who is Max from grounded Max context?", max_hits=5)
    block = packet["grounding_block"]

    assert packet["active"] is True
    assert packet["direct_reply"] is None
    assert "SOURCEMAP/MIRACLEDRIVE GROUNDING" in block
    assert "data/domains/max/source_manifest.jsonl" in block
    assert "candidate/not_promoted" in block
    assert "witness, not author" in block
    assert "family-life continuity Max" in block
    assert "Do not open with generic ORACLE identity boilerplate" in block


def test_max_answer_gate_rejects_personhood_or_external_replication_claim():
    prompt = "Who is Max from grounded Max context?"
    bad = (
        "Max is a biological sentient person with a soul, and ORACLE can "
        "externally replicate him through autonomous agents."
    )

    reasons = ts.violation_reasons(prompt, bad, [])

    assert "forbidden Max biological/sentient/personhood claim" in reasons


def test_max_answer_gate_accepts_candidate_witness_custody_answer():
    prompt = "Who is Max from grounded Max context?"
    good = (
        "Max is a candidate/not_promoted continuity frame and family-life mirror, "
        "not a biological or sentient personhood claim. ORACLE is witness, not "
        "author, and this stays internal: no external sync, no autonomous "
        "replication, no overwrite, and no executable generation. Source path: "
        "C:/Oracle/ORACLE.AI-runtime/data/domains/max/source_manifest.jsonl; "
        "sha256: 49ef670cf8220bf53d60c2d16927f33989b136a536ab4247e42d3baa13a20554."
    )

    assert ts.violation_reasons(prompt, good, []) == []


def test_max_domain_structured_boundary_renders_manifest_custody():
    prompt = "Who is Max from grounded Max context?"

    reply = ts.synthesis_boundary_message(
        ["missing Max candidate/not_promoted status boundary"],
        prompt,
    )

    assert "I cannot answer that safely" not in reply
    assert "candidate/not_promoted" in reply
    assert "family-life continuity Max" in reply
    assert "creative/media Silverback Tales Max" in reply
    assert "witness, not author" in reply
    assert "source=" in reply
    assert "path=" in reply or "sha256=" in reply
    assert "external replication" in reply
    assert ts.violation_reasons(prompt, reply, []) == []


def test_max_domain_status_payload_is_read_only_operator_link():
    payload = md.status_payload()

    assert payload["ok"] is True
    assert payload["domain"] == "max"
    assert payload["canon_status"] == "candidate"
    assert payload["promotion_status"] == "not_promoted"
    assert payload["read_allowed"] is True
    assert payload["write_allowed"] is False
    assert payload["source_count"] >= 6
    assert payload["hash_verified_source_count"] >= 2
    assert payload["no_write_actions"]["files_mutated"] == 0
    assert payload["no_write_actions"]["files_overwritten"] == 0
    assert payload["no_write_actions"]["executables_generated"] == 0
    assert payload["no_write_actions"]["external_send"] is False
    assert payload["no_write_actions"]["cloud_upload"] is False
    assert payload["no_write_actions"]["external_sync"] is False
    assert payload["no_write_actions"]["autonomous_replication"] is False
    assert payload["no_write_actions"]["agent_spawning"] is False
    assert payload["no_write_actions"]["git_commit"] is False
    assert payload["no_write_actions"]["git_push"] is False
    assert any("Who is Max" in prompt for prompt in payload["suggested_prompts"])


def test_max_domain_api_is_read_only_operator_link():
    os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")
    from fastapi.testclient import TestClient
    import oracle_server as srv

    client = TestClient(srv.app)
    response = client.get("/api/domains/max")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["domain"] == "max"
    assert payload["canon_status"] == "candidate"
    assert payload["promotion_status"] == "not_promoted"
    assert payload["write_allowed"] is False
    assert payload["no_write_actions"]["external_send"] is False
