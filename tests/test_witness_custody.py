from core.witness_custody import (
    ClaimType,
    GenerationMode,
    MemoryStatus,
    SourceReceipt,
    WitnessClaim,
    promote_contradiction,
    refusal_boundary_message,
    route_claim,
)


def _source(distance=0):
    return SourceReceipt(
        source_id="chat-2026-06-27-001",
        source_type="chat_message",
        source_distance=distance,
        location="current_thread",
        timestamp="2026-06-27T00:00:00Z",
        verification_authority="Noah.Physical",
    )


def test_witnessed_claim_with_receipt_promotes_to_durable_recitation():
    claim = WitnessClaim(
        claim_id="rr_claim_0001",
        claim_text="Noah declared that witnessing must precede performance.",
        claim_type=ClaimType.DECLARED,
        source=_source(),
        confidence_level="high",
        confidence_basis="user_attested",
        consent_scope="project_memory",
    )

    routed = route_claim(claim)

    assert routed.authorized is True
    assert routed.generation_mode == GenerationMode.RECITE
    assert routed.memory_status == MemoryStatus.DURABLE
    assert "recited within its refusal boundary" in routed.reason


def test_claim_without_receipt_refuses_before_generation():
    claim = WitnessClaim(
        claim_id="rr_claim_0002",
        claim_text="An unsupported claim that should not become memory.",
        claim_type=ClaimType.DECLARED,
        source=SourceReceipt(source_id="", source_type="", source_distance=2),
    )

    routed = route_claim(claim)

    assert routed.authorized is False
    assert routed.generation_mode == GenerationMode.REFUSE
    assert routed.memory_status == MemoryStatus.REJECTED
    assert routed.reason == "I do not have enough verified evidence to claim that."


def test_generated_claim_is_temporary_hypothesis_not_durable_memory():
    claim = WitnessClaim(
        claim_id="rr_claim_0003",
        claim_text="AI-generated synthesis of a doctrine chapter.",
        claim_type=ClaimType.GENERATED,
        source=_source(distance=2),
        confidence_level="medium",
        confidence_basis="generated_synthesis",
    )

    routed = route_claim(claim)

    assert routed.authorized is True
    assert routed.generation_mode == GenerationMode.HYPOTHESIZE
    assert routed.memory_status == MemoryStatus.TEMPORARY


def test_inferred_claim_is_candidate_interpretation():
    claim = WitnessClaim(
        claim_id="rr_claim_0004",
        claim_text="The doctrine implies refusal must occur before generation.",
        claim_type=ClaimType.INFERRED,
        source=_source(distance=1),
        confidence_level="medium",
        confidence_basis="inferred_from_context",
    )

    routed = route_claim(claim)

    assert routed.authorized is True
    assert routed.generation_mode == GenerationMode.INTERPRET
    assert routed.memory_status == MemoryStatus.CANDIDATE


def test_unsupported_claim_refuses_even_with_receipt():
    claim = WitnessClaim(
        claim_id="rr_claim_0005",
        claim_text="A claim explicitly marked unsupported.",
        claim_type=ClaimType.UNSUPPORTED,
        source=_source(distance=2),
    )

    routed = route_claim(claim)

    assert routed.authorized is False
    assert routed.generation_mode == GenerationMode.REFUSE
    assert routed.memory_status == MemoryStatus.CANDIDATE


def test_contradiction_promotes_as_disputed_custody_not_single_fact():
    diary = WitnessClaim(
        claim_id="diary_001",
        claim_text="The diary asserts X.",
        claim_type=ClaimType.WITNESSED,
        source=_source(distance=0),
        contradictions=("video_1985",),
    )
    video = WitnessClaim(
        claim_id="video_1985",
        claim_text="The later video recants X.",
        claim_type=ClaimType.WITNESSED,
        source=_source(distance=0),
        contradictions=("diary_001",),
    )

    routed = route_claim(diary)
    record = promote_contradiction(
        "contradiction_001",
        [diary, video],
        "The diary asserts X, while the later video recants X. No third-party corroboration resolves the contradiction.",
    )

    assert routed.memory_status == MemoryStatus.DISPUTED
    assert routed.authorized is True
    assert record.memory_status == MemoryStatus.DISPUTED
    assert record.claim_ids == ("diary_001", "video_1985")
    assert "Surface all linked claims" in record.retrieval_rule


def test_refusal_boundary_message_includes_enforced_limit():
    claim = WitnessClaim(
        claim_id="rr_claim_0006",
        claim_text="Do not overclaim public reception.",
        claim_type=ClaimType.DECLARED,
        source=_source(),
        refusal_boundary="Do not claim impact, metrics, or reception without receipts.",
    )

    message = refusal_boundary_message(claim)

    assert message.startswith("I do not have enough verified evidence")
    assert "Do not claim impact" in message
