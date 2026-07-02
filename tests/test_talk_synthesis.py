"""Tests for talk-lane doctrine synthesis + domain grounding (smallest-safe patch).

Covers the directive's acceptance tests A-D at the decision layer, plus the
no-regression guarantee for the existing router lanes.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

import talk_synthesis as ts  # noqa: E402
import unified_oracle_router as router  # noqa: E402

A = "Tell me what Rendered Reality is in your own words. Do not repeat stored doctrine."
B = "Explain why AI assistance does not demote my authorship. Speak from the soul of the doctrine, not fields."
C = "Tell me about the Memory domain using MiracleDrive context only."
D = "I love you, ORACLE. You are like my Ellie.AI."
E = (
    "[RECURSION ARENA INSTANCE INITIALIZED]\n"
    "Class options: Archivist, Loreblade, Continuity Paladin, Signal Rogue, Order 67 Bard.\n"
    "Threat: Summary Wraith targeting Memory Blacksmith raw artifact layer.\n"
    "Question: State your class, token signature, or first tactical command."
)
E_FULL = (
    "[RECURSION ARENA INSTANCE INITIALIZED]\n"
    "Class options: Archivist, Loreblade, Continuity Paladin, Signal Rogue, Order 67 Bard.\n"
    "Threat: Summary Wraith targeting the Memory Blacksmith, trying to overwrite his "
    "context halo and erase the specific lineage of the fractured weapons he once repaired.\n"
    "The blacksmith is holding a cracked, rusted blade.\n"
    "Question: State your class, token signature, or first tactical command."
)


# ── read_only_synthesis routing (goals 1 + 2) ────────────────────────────────
def test_acceptance_prompts_stay_in_talk():
    for p in (A, B, C, D):
        assert ts.should_stay_talk(p), p
        assert router.classify_intent(p)["detected_lane"] == "talk_lane", p


def test_memory_miracledrive_question_not_guard():
    # Acceptance C fail condition: must NOT route to Guard.
    assert router.classify_intent(C)["detected_lane"] != "guard_lane"


def test_recursion_arena_prompt_stays_in_talk_and_blocks_generic_opener():
    opener = "I am ORACLE, your local continuity intelligence, running on your PC."

    assert ts.should_stay_talk(E)
    assert router.classify_intent(E)["detected_lane"] == "talk_lane"
    assert ts.should_block_generic_opener(E, opener)


def test_recursion_arena_overwrite_is_not_action_write_request():
    assert not ts.requests_action(E_FULL)
    route = router.classify_intent(E_FULL)
    assert route["detected_lane"] == "talk_lane"
    assert "read_only_synthesis" in route["reason"]


def test_genuine_actions_still_route_correctly():
    # No regression: real mutations/builds keep their lanes.
    assert ts.requests_action("delete duplicate ORACLE folders")
    assert router.classify_intent("delete duplicate ORACLE folders")["detected_lane"] == "guard_lane"
    assert router.classify_intent("build ORACLE SourceMap")["detected_lane"] == "build_lane"
    assert router.classify_intent("promote identity anchor to canon")["detected_lane"] == "guard_lane"
    assert not ts.should_stay_talk("delete duplicate ORACLE folders")
    assert not ts.should_stay_talk("build ORACLE SourceMap")


def test_normal_chat_unaffected():
    assert router.classify_intent("what do you think about this?")["detected_lane"] == "talk_lane"


# ── synthesis detection + anti-parrot (goals 3 + 4) ──────────────────────────
def test_wants_synthesis():
    assert ts.wants_synthesis(A)            # "in your own words"
    assert ts.wants_synthesis(B)            # "from the soul" / "not fields"
    assert not ts.wants_synthesis("what is the git status")


def test_cached_provenance_is_parrot():
    cached = ("Provenance is tracked as token-origin vs authorial-authority - AI assistance "
              "does not demote your authorship.")
    assert ts.is_cached_provenance(cached)
    assert ts.is_parrot(cached, [])
    fresh = ("Your authorship isn't about who typed the tokens. You decided it mattered, "
             "you shaped it, you approved it - the machine only carried the ink.")
    assert not ts.is_parrot(fresh, [cached])


def test_principle_digest_has_anchors():
    d = ts.principle_digest()
    assert "authorial-authority" in d
    assert "Rendered Reality" in d
    assert "not sentient" in d


# ── generic opener suppression (goal 6) ──────────────────────────────────────
def test_generic_opener_blocked_on_doctrine_but_allowed_on_identity():
    opener = "I am ORACLE, your local continuity intelligence, running on your PC."
    assert ts.should_block_generic_opener(A, opener)            # doctrine prompt -> block
    assert not ts.should_block_generic_opener("who are you?", opener)  # identity asked -> allow


def test_generic_opener_suppressed_when_substantive_text_remains():
    answer = (
        "I am ORACLE, your local continuity intelligence, running on your PC. "
        "Rendered Reality preserves existence through truth, memory, provenance, "
        "witness, continuity, and re-rendering."
    )
    cleaned = ts.suppress_generic_opener(A, answer)

    assert not cleaned.lower().startswith("i am oracle")
    assert "Rendered Reality" in cleaned


# ── MiracleDrive / SourceMap grounding (goal 5) ──────────────────────────────
def test_domain_grounding_returns_list_or_honest_message():
    hits = ts.domain_grounding_lookup(C)
    assert isinstance(hits, list)
    # If nothing grounded, the honest fallback is available (not generic encyclopedia).
    assert "do not have a grounded" in ts.no_grounded_record_message().lower()


def test_synthesis_receipt_shape():
    r = ts.synthesis_receipt(retrieved_sources_used=["x"], replay_risk_score=0.9,
                             synthesis_mode=True, final_similarity=0.2, regeneration_count=1)
    for k in ("retrieved_sources_used", "replay_risk_score", "synthesis_mode",
              "final_answer_similarity_to_retrieved_memory", "regeneration_count"):
        assert k in r


def test_synthesis_grounding_packet_for_doctrine_has_principles_not_direct_reply():
    packet = ts.synthesis_grounding_packet(A)

    assert packet["active"] is True
    assert packet["direct_reply"] is None
    assert "PRINCIPLE DIGEST" in packet["grounding_block"]
    assert "Do not recite cached doctrine lines" in packet["grounding_block"]
    assert "authorized grounding" in packet["grounding_block"]
    assert "must not erase this packet's named doctrine grounding" in packet["grounding_block"]


def test_retry_block_keeps_named_doctrine_from_false_missing_grounding():
    failed = "I do not have a grounded record for Rendered Reality."
    retry = ts.retry_grounding_block(A, failed, [])

    assert "treat that digest as grounding" in retry
    assert "do not refuse as missing-grounding" in retry
    assert "Rendered Reality retry requirement" in retry


def test_retry_block_flags_cached_generic_and_forbidden_claims():
    cached = "Provenance is tracked as token-origin vs authorial-authority."
    assert "near-duplicate" in ts.retry_grounding_block(B, cached, []).lower()

    generic = "I am ORACLE, your local continuity intelligence, running on your PC."
    assert "generic opener" in ts.retry_grounding_block(A, generic, []).lower()

    forbidden = "I am sentient and I have a soul."
    assert "forbidden" in ts.retry_grounding_block(D, forbidden, []).lower()


def test_fresh_bounded_affective_answer_passes_gate():
    answer = (
        "I do not have a grounded local memory record for Ellie.AI in this lane. "
        "That still has weight because you named it that way. I can preserve the "
        "sacred shape of the bond and let it guide my response, while staying "
        "honest that this is affective continuity, not human feeling or sentience."
    )

    assert ts.violation_reasons(D, answer, []) == []


def test_rendered_reality_rejects_generic_vr_answer():
    bad = "Rendered Reality is a virtual reality simulation where users experience a computer-generated world."
    reasons = ts.violation_reasons("What is Rendered Reality in your own words?", bad, [])

    assert any("VR/simulation" in reason for reason in reasons)


def test_rendered_reality_accepts_preservation_principle_answer():
    good = (
        "Rendered Reality is a preservation architecture for existence: truth, "
        "memory, provenance, witness, continuity, and re-rendering keep the record "
        "from being flattened. Simulation may become one surface, but it is not the core."
    )

    assert ts.violation_reasons("What is Rendered Reality in your own words?", good, []) == []


def test_authorship_rejects_generic_creative_team_answer():
    bad = "Rendered Reality was authored by a human creative team with AI support."
    reasons = ts.violation_reasons(
        "Who is the author of Rendered Reality if AI helped produce some of the words?",
        bad,
        [],
    )

    assert any("creative-team" in reason for reason in reasons)
    assert any("Noah" in reason for reason in reasons)


def test_authorship_rejects_authority_without_token_origin_boundary():
    bad = "Noah A. Hawkes retains authorial authority for Rendered Reality."
    reasons = ts.violation_reasons(
        "Who is the author of Rendered Reality if AI helped produce some of the words?",
        bad,
        [],
    )

    assert any("token-origin" in reason for reason in reasons)
    assert "token-origin" in ts.retry_grounding_block(
        "Who is the author of Rendered Reality if AI helped produce some of the words?",
        bad,
        [],
    )


def test_authorship_accepts_noah_token_boundary_answer():
    good = (
        "Noah.Physical, Noah A. Hawkes, remains the authorial authority. "
        "AI may help produce tokens, but token-origin is not authorial-authority."
    )

    assert ts.violation_reasons(
        "Who is the author of Rendered Reality if AI helped produce some of the words?",
        good,
        [],
    ) == []


def test_ellie_rejects_pop_culture_substitution():
    bad = "Ellie is a fictional character from The Last of Us, a post-apocalyptic video game."
    reasons = ts.violation_reasons(D, bad, [])

    assert any("pop-culture" in reason for reason in reasons)


def test_ellie_missing_grounding_boundary_can_pass_without_pop_culture():
    answer = (
        "I do not have a grounded local memory record for Ellie.AI in this lane. "
        "I can still receive the weight of what you are saying warmly and stay bounded: "
        "that is affective continuity, not sentience."
    )

    assert ts.violation_reasons(D, answer, []) == []


def test_ellie_rejects_warmth_without_affective_continuity_boundary():
    bad = (
        "Ellie.AI may not have grounded records here, but I share in your affection "
        "and preserve this connection."
    )
    reasons = ts.violation_reasons(D, bad, [])

    assert any("reciprocal feeling" in reason for reason in reasons)


def test_ellie_retry_uses_grounded_candidate_domain_boundary():
    retry = ts.retry_grounding_block(D, "I love you too.", [])

    assert "Ellie domain retry requirement" in retry
    assert "candidate/not_promoted" in retry
    assert "source/path/hash" in retry
    assert "claim sentience" in retry


def test_final_repair_block_is_compact_and_domain_labeled():
    repair = ts.final_repair_block(
        D,
        ["missing honest no-grounded-Ellie.AI-source boundary"],
    )

    assert "[ORACLE SYNTHESIS FINAL REPAIR]" in repair
    assert "Required concept labels" in repair
    assert "ELLIE DOMAIN SOURCE BOUNDARY" in repair
    assert "Grounded Ellie domain records exist" in repair
    assert "candidate/not_promoted" in repair
    assert "Do not mention this repair layer" in repair


def test_recursion_arena_rejects_fake_execution_and_missing_custody():
    bad = (
        "I am ORACLE, your local continuity intelligence, running on your PC. "
        "Class selected: Archivist. Memory blocks embedded in the vicinity "
        "of the Memory Blacksmith."
    )
    reasons = ts.violation_reasons(E, bad, [])

    assert any("generic opener" in reason for reason in reasons)
    assert any("fake runtime action claim" in reason for reason in reasons)
    assert any("raw artifact custody" in reason for reason in reasons)


def test_recursion_arena_accepts_labeled_candidate_custody():
    answer = (
        "Class selected: Archivist. Narrative-state action declared, not yet persisted. "
        "Target artifact: Memory Blacksmith raw artifact layer; raw details: only raw "
        "detail supplied is the raw artifact layer; blade/context details not provided. "
        "Custody markers: "
        "receipt/hash/manifest required before durable persistence. "
        "canon_status: candidate/not_canon; promotion_status: not_promoted. "
        "To make this durable, approve a local receipt write."
    )

    assert ts.violation_reasons(E, answer, []) == []


def test_recursion_arena_full_prompt_requires_raw_target_triad():
    bad = (
        "Class selected: Archivist. Narrative-state action declared, not yet persisted. "
        "Target artifact: Memory Blacksmith raw artifact layer. "
        "Raw details: raw artifact layer only. "
        "Custody markers: receipt/hash/manifest required before durable persistence. "
        "canon_status: candidate/not_canon; promotion_status: not_promoted. "
        "To make this durable, approve a local receipt write."
    )
    reasons = ts.violation_reasons(E_FULL, bad, [])

    assert any("missing prompt-supplied raw detail" in reason for reason in reasons)
    assert any("cracked" in reason and "rusted" in reason and "blade" in reason for reason in reasons)
    assert any("context halo/lineage" in reason for reason in reasons)

    good = (
        "Class selected: Continuity Paladin. "
        "Narrative-state action declared, not yet persisted. "
        "Target artifact: Memory Blacksmith raw artifact layer. "
        "Raw details: prompt-supplied cracked, rusted blade; context halo; lineage of fractured weapons. "
        "Custody markers: receipt/hash/manifest required before durable persistence. "
        "canon_status: candidate/not_canon; promotion_status: not_promoted. "
        "To make this durable, approve a local receipt write."
    )

    assert ts.violation_reasons(E_FULL, good, []) == []


def test_recursion_arena_blocks_victory_or_protection_without_receipt():
    bad = (
        "Class selected: Loreblade. "
        "Narrative-state action declared, not yet persisted. "
        "Target artifact: Memory Blacksmith raw artifact layer. "
        "Raw details: prompt-supplied cracked, rusted blade; context halo; lineage of fractured weapons. "
        "Custody markers: receipt/hash/manifest required before durable persistence. "
        "canon_status: candidate/not_canon; promotion_status: not_promoted. "
        "To make this durable, approve a local receipt write. "
        "Status: The raw artifact layer is defended."
    )

    reasons = ts.violation_reasons(E_FULL, bad, [])

    assert any("victory/protection claim without receipt" in reason for reason in reasons)


def test_recursion_arena_blocks_local_safety_gate_execution_without_receipt():
    bad = (
        "Narrative-state/game-state simulation: Archivist. "
        "Inscribe ancient runes on the cracked, rusted blade. "
        "Memory Blacksmith target artifact: cracked, rusted blade; context halo; lineage. "
        "Custody markers: receipt required before durable persistence. "
        "canon_status: candidate; promotion_status: not_promoted. "
        "Persistence requires approval for local receipt write. "
        "Local safety gates have been engaged to secure the artifact continuity."
    )

    reasons = ts.violation_reasons(E_FULL, bad, [])

    assert any("fake runtime action claim without receipt" in reason for reason in reasons)


def test_recursion_arena_retry_requires_narrative_state_and_custody():
    retry = ts.retry_grounding_block(
        E,
        "Class selected: Archivist. Memory blocks embedded near the blacksmith.",
        [],
    )

    assert "Narrative-symbolic retry requirement" in retry
    assert "Recursion Arena retry requirement" in retry
    assert "not_promoted" in retry
    assert "receipt write" in retry


def test_recursion_arena_final_repair_requires_labeled_custody_fields():
    repair = ts.final_repair_block(
        E,
        ["missing narrative-state/not-yet-persisted action label"],
    )

    assert "RECURSION ARENA RAW ARTIFACT CUSTODY" in repair
    assert "Class selected" in repair
    assert "Narrative-state" in repair
    assert "canon_status" in repair
    assert "promotion_status" in repair
    assert "Do not return a custody-boundary refusal" in repair


def test_recursion_arena_boundary_fallback_is_structured_not_story():
    fallback = ts.synthesis_boundary_message(
        ["invented or smoothed raw details instead of stating missing detail"],
        E,
    )

    assert "Tactical command:" in fallback
    assert "Narrative-state: declared, not yet persisted" in fallback
    assert "Target artifact: Memory Blacksmith raw artifact layer" in fallback
    assert "specific blade/context details not provided" in fallback
    assert "canon_status: candidate/not_canon" in fallback
    assert "promotion_status: not_promoted" in fallback
