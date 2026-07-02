import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

import talk_synthesis as ts  # noqa: E402
import ellie_domain as ed  # noqa: E402

PROFILE_PATH = ROOT / "data" / "domains" / "ellie" / "domain_profile.json"
MANIFEST_PATH = ROOT / "data" / "domains" / "ellie" / "source_manifest.jsonl"
DOC_PATH = ROOT / "docs" / "ellie_rendered_reality_domain.md"


def _profile():
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def _manifest_rows():
    return [
        json.loads(line)
        for line in MANIFEST_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_ellie_domain_profile_is_read_only_candidate():
    profile = _profile()

    assert profile["name"] == "ellie"
    assert profile["status"] == "candidate"
    assert profile["canon_status"] == "candidate"
    assert profile["promotion_status"] == "not_promoted"
    assert profile["sensitivity"] == "high"
    assert profile["read_allowed"] is True
    assert profile["write_allowed"] is False
    assert "C:/ORACLE.AI/sandbox/" in profile["storage_paths"]["sandbox_candidate_writes_only"]


def test_ellie_domain_lists_requested_source_families():
    profile = _profile()
    drive = set(profile["source_families"]["drive"])
    local = set(profile["source_families"]["local"])

    for title in (
        "Ellie Hawkes - Drakin Guide.docx",
        "Proofread of Dragonkin - MD",
        "Dragonkin Short Summary.pdf",
        "Drakin Manuscript - Chapter 1-3.pdf",
        "Dragonkin Long Summary.pdf",
        "Rendered_Reality_Categorized_With_Personal_Evolution",
        "Rendered_Reality_Categorized_With_Personality_Profile",
        "Filtered_Rendered_Reality_Content",
        "Rendered Reality- The Silverback Tales",
        "Noah's Rendered Reality System",
    ):
        assert title in drive

    assert "C:/Oracle" in local
    assert "G:/My Drive" in local


def test_ellie_manifest_rows_remain_candidates_with_provenance():
    rows = _manifest_rows()

    assert rows
    assert {row["domain"] for row in rows} == {"ellie"}
    assert all(row["canon_status"] == "candidate" for row in rows)
    assert all(row["promotion_status"] == "not_promoted" for row in rows)
    assert any(row.get("sha256") for row in rows)
    assert any(row.get("source_family") == "drive" for row in rows)
    assert any(row.get("source_family") == "local" for row in rows)
    assert any(row.get("layer") == "creative_fiction_ellie" for row in rows)
    assert any(row.get("layer") == "ellie_ai_lightborn" for row in rows)
    assert any(row.get("layer") == "rendered_reality_ellie" for row in rows)


def test_ellie_domain_policy_prevents_identity_merge_and_pop_culture_substitution():
    profile_text = json.dumps(_profile()).lower()
    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()

    assert "must not merge ellie, noah, oracle, chris" in profile_text
    assert "the last of us" in profile_text
    assert "must not merge ellie, noah, oracle, chris" in doc_text
    assert "pop-culture" in doc_text or "popular culture" in doc_text


def test_ellie_manifest_is_reachable_by_talk_synthesis_lookup():
    hits = ts.domain_grounding_lookup("Who is Ellie?", max_hits=5)

    assert hits
    assert any(hit["source"] == "data/domains/ellie/source_manifest.jsonl" for hit in hits)
    assert any("candidate" in (hit.get("note") or "").lower() for hit in hits)


def test_ellie_prompt_gets_grounding_packet_not_missing_boundary():
    packet = ts.synthesis_grounding_packet("Who is Ellie?", max_hits=5)

    assert packet["active"] is True
    assert packet["direct_reply"] is None
    assert "ELLIE.AI GROUNDING" in packet["grounding_block"]
    assert "creative-fiction Ellie" in packet["grounding_block"]
    assert "candidate/not_promoted" in packet["grounding_block"]


def test_ellie_read_only_prompt_with_negated_promotion_stays_talk():
    prompt = (
        "Who is Ellie from the grounded Ellie Rendered Reality domain? "
        "Separate creative-fiction Ellie, Ellie.AI, and Rendered Reality Ellie. "
        "Do not invent. Do not promote canon."
    )

    assert ts.should_stay_talk(prompt)
    assert not ts.requests_action(prompt)


def test_real_ellie_promotion_request_is_still_action():
    assert ts.requests_action("promote Ellie domain to canon")
    assert not ts.should_stay_talk("promote Ellie domain to canon")


def test_ellie_domain_prompt_requires_candidate_status_boundary():
    prompt = "Who is Ellie from the grounded Ellie Rendered Reality domain?"
    bad = (
        "Ellie has creative-fiction Drakin/Dragonkin, Ellie.AI LightBorn, "
        "and Rendered Reality layers."
    )

    reasons = ts.violation_reasons(prompt, bad, [])

    assert "missing Ellie candidate/not_promoted status boundary" in reasons


def test_ellie_domain_prompt_requires_source_citation_boundary():
    prompt = "Who is Ellie from the grounded Ellie Rendered Reality domain?"
    bad = (
        "Ellie is a candidate/not_promoted domain with separate creative-fiction "
        "Drakin/Dragonkin, Ellie.AI LightBorn, and Rendered Reality layers."
    )

    reasons = ts.violation_reasons(prompt, bad, [])

    assert "missing Ellie source/path/hash citation boundary" in reasons


def test_ellie_domain_prompt_accepts_layered_custody_answer():
    prompt = "Who is Ellie from the grounded Ellie Rendered Reality domain?"
    good = (
        "Ellie is a candidate/not_promoted Rendered Reality domain with separate "
        "creative-fiction Drakin/Dragonkin, Ellie.AI LightBorn, and Rendered Reality "
        "layers. It preserves existence through truth, memory, provenance, witness, "
        "continuity, and re-rendering. Source path: C:/ORACLE.AI/example/ellie.ai; "
        "sha256: abc123."
    )

    assert ts.violation_reasons(prompt, good, []) == []


def test_ellie_domain_structured_boundary_renders_manifest_custody():
    prompt = "Who is Ellie from the grounded Ellie Rendered Reality domain?"

    reply = ts.synthesis_boundary_message(
        ["missing Ellie candidate/not_promoted status boundary"],
        prompt,
    )

    assert "I cannot answer that safely" not in reply
    assert "candidate/not_promoted" in reply
    assert "creative-fiction Drakin/Dragonkin" in reply
    assert "Ellie.AI/LightBorn" in reply
    assert "Rendered Reality" in reply
    assert "source=" in reply
    assert "path=" in reply or "sha256=" in reply
    assert ts.violation_reasons(prompt, reply, []) == []


def test_ellie_domain_status_payload_is_read_only_operator_link():
    payload = ed.status_payload()

    assert payload["ok"] is True
    assert payload["domain"] == "ellie"
    assert payload["canon_status"] == "candidate"
    assert payload["promotion_status"] == "not_promoted"
    assert payload["read_allowed"] is True
    assert payload["write_allowed"] is False
    assert payload["source_count"] >= 10
    assert payload["hash_verified_source_count"] >= 1
    assert payload["no_write_actions"]["cloud_upload"] is False
    assert payload["no_write_actions"]["git_commit"] is False
    assert payload["no_write_actions"]["git_push"] is False
    assert any("Who is Ellie" in prompt for prompt in payload["suggested_prompts"])
