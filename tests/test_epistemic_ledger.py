"""Pytest coverage for core/epistemic_ledger.py.

The module ships its own `_smoke_test()` (run via `python core/epistemic_ledger.py
--smoke-test`) but that never executes under `pytest tests/`, so this
deterministic-approval-gate module — the load-bearing piece behind
cognitive_spine/cognitive_state/doubt_detection — had zero coverage in the
regular health pass. These tests port each smoke-test assertion into
independent pytest cases against a tmp_path ledger, so a regression here
surfaces in the normal suite instead of only on manual CLI runs.
"""

import pytest

from core.epistemic_ledger import (
    ActorMode,
    ClaimLedgerError,
    ClaimStatus,
    approve_claim,
    dispute_claim,
    get_claim,
    get_claim_revision,
    get_open_questions,
    issue_approval_token,
    link_contradiction,
    propose_claim,
    record_evidence,
    retract_claim,
    search_claims,
    supersede_claim,
)


@pytest.fixture
def ledger(tmp_path):
    return tmp_path / "claim_ledger.json"


def test_model_proposed_claim_cannot_be_verified_automatically(ledger):
    with pytest.raises(ClaimLedgerError):
        propose_claim(
            "A model is trying to verify itself.",
            status=ClaimStatus.VERIFIED,
            created_by="model",
            ledger_path=ledger,
        )


def test_unsupported_statement_remains_inference(ledger):
    claim = propose_claim(
        "ORACLE can expand knowledge without omniscience.",
        status=ClaimStatus.INFERENCE,
        confidence=0.45,
        source_ids=[],
        source_type="model_output",
        ledger_path=ledger,
    )
    assert claim["status"] == ClaimStatus.INFERENCE.value


def test_unsupported_unknown_remains_unknown(ledger):
    claim = propose_claim(
        "The next unknown variable has not been measured.",
        status=ClaimStatus.UNKNOWN,
        confidence=0.0,
        source_ids=[],
        source_type="absence_of_evidence",
        ledger_path=ledger,
    )
    assert claim["status"] == ClaimStatus.UNKNOWN.value


def test_contradictory_claims_coexist_and_cross_reference(ledger):
    c1 = propose_claim(
        "The signal originated from source A.",
        source_ids=["source_a"],
        source_type="observation",
        ledger_path=ledger,
    )
    c2 = propose_claim(
        "The signal did not originate from source A.",
        source_ids=["source_b"],
        source_type="observation",
        ledger_path=ledger,
    )
    link_contradiction(c1["claim_id"], c2["claim_id"], ledger_path=ledger)
    c1r = get_claim(c1["claim_id"], ledger_path=ledger)
    c2r = get_claim(c2["claim_id"], ledger_path=ledger)
    assert c1r and c2r
    assert c2["claim_id"] in c1r["contradiction_ids"]
    assert c1["claim_id"] in c2r["contradiction_ids"]


def test_link_contradiction_rejects_self_reference(ledger):
    claim = propose_claim("Solo claim.", source_ids=["s"], ledger_path=ledger)
    with pytest.raises(ClaimLedgerError):
        link_contradiction(claim["claim_id"], claim["claim_id"], ledger_path=ledger)


def test_supersede_claim_keeps_old_in_revision_history(ledger):
    original = propose_claim(
        "ORACLE can expand knowledge without omniscience.",
        status=ClaimStatus.INFERENCE,
        confidence=0.45,
        source_ids=[],
        source_type="model_output",
        ledger_path=ledger,
    )
    newer = supersede_claim(
        original["claim_id"],
        "ORACLE can expand knowledge while preserving epistemic labels.",
        source_ids=["source_c"],
        ledger_path=ledger,
    )
    old = get_claim(original["claim_id"], ledger_path=ledger)
    assert old["revisions"]
    assert newer["supersedes"] == original["claim_id"]
    assert old["status"] == ClaimStatus.RETRACTED.value


def test_companion_mode_cannot_mutate_ledger(ledger):
    with pytest.raises(ClaimLedgerError):
        propose_claim(
            "Companion should not mutate this.",
            actor_mode=ActorMode.COMPANION,
            ledger_path=ledger,
        )


def test_dispute_and_retract_require_non_companion_mode(ledger):
    claim = propose_claim("Disputable claim.", source_ids=["s"], ledger_path=ledger)
    with pytest.raises(ClaimLedgerError):
        dispute_claim(claim["claim_id"], reason="test", actor_mode=ActorMode.COMPANION, ledger_path=ledger)
    with pytest.raises(ClaimLedgerError):
        retract_claim(claim["claim_id"], reason="test", actor_mode=ActorMode.COMPANION, ledger_path=ledger)

    disputed = dispute_claim(claim["claim_id"], reason="test", ledger_path=ledger)
    assert disputed["status"] == ClaimStatus.DISPUTED.value
    retracted = retract_claim(claim["claim_id"], reason="test", ledger_path=ledger)
    assert retracted["status"] == ClaimStatus.RETRACTED.value


@pytest.fixture
def supported_claim_with_evidence(ledger):
    supported = propose_claim(
        "The deterministic approval contract exists.",
        status=ClaimStatus.SUPPORTED,
        confidence=0.8,
        source_ids=["design_note"],
        source_type="human_observation",
        scope="approval_contract",
        created_by="application",
        ledger_path=ledger,
    )
    evidence = record_evidence(
        evidence_text="Smoke test observed deterministic approval contract behavior.",
        source_id="smoke_test",
        source_type="deterministic_test",
        scope="approval_contract",
        ledger_path=ledger,
    )
    return supported, evidence


def test_approve_claim_rejects_non_application_caller(ledger, supported_claim_with_evidence):
    supported, evidence = supported_claim_with_evidence
    token = issue_approval_token(
        claim_id=supported["claim_id"],
        expected_revision=supported["revision"],
        approved_by="Noah",
        target_status=ClaimStatus.VERIFIED,
        ledger_path=ledger,
    )
    r = approve_claim(
        supported["claim_id"],
        approved_by="Noah",
        approval_reason="verified by deterministic smoke evidence",
        evidence_ids=[evidence["evidence_id"]],
        expected_revision=supported["revision"],
        approval_token=token["token_id"],
        actor_mode=ActorMode.BUILDER,
        ledger_path=ledger,
    )
    assert r["status"] == "BLOCKED"
    assert r["reason_code"] == "UNAUTHORIZED_CALLER"


def test_approve_claim_rejects_expired_token(ledger, supported_claim_with_evidence):
    supported, evidence = supported_claim_with_evidence
    expired = issue_approval_token(
        claim_id=supported["claim_id"],
        expected_revision=supported["revision"],
        approved_by="Noah",
        target_status=ClaimStatus.VERIFIED,
        ttl_seconds=-1,
        ledger_path=ledger,
    )
    r = approve_claim(
        supported["claim_id"],
        approved_by="Noah",
        approval_reason="expired token should fail",
        evidence_ids=[evidence["evidence_id"]],
        expected_revision=supported["revision"],
        approval_token=expired["token_id"],
        ledger_path=ledger,
    )
    assert r["status"] == "BLOCKED"
    assert r["reason_code"] == "INVALID_APPROVAL_TOKEN"


def test_approve_claim_rejects_token_bound_to_another_claim(ledger, supported_claim_with_evidence):
    supported, evidence = supported_claim_with_evidence
    other = propose_claim(
        "Another claim for token binding.",
        status=ClaimStatus.SUPPORTED,
        source_ids=["other"],
        source_type="human_observation",
        scope="approval_contract",
        created_by="application",
        ledger_path=ledger,
    )
    wrong_claim_token = issue_approval_token(
        claim_id=other["claim_id"],
        expected_revision=other["revision"],
        approved_by="Noah",
        target_status=ClaimStatus.VERIFIED,
        ledger_path=ledger,
    )
    r = approve_claim(
        supported["claim_id"],
        approved_by="Noah",
        approval_reason="wrong claim token should fail",
        evidence_ids=[evidence["evidence_id"]],
        expected_revision=supported["revision"],
        approval_token=wrong_claim_token["token_id"],
        ledger_path=ledger,
    )
    assert r["status"] == "BLOCKED"
    assert r["reason_code"] == "INVALID_APPROVAL_TOKEN"


def test_approve_claim_rejects_stale_expected_revision(ledger, supported_claim_with_evidence):
    supported, evidence = supported_claim_with_evidence
    stale_token = issue_approval_token(
        claim_id=supported["claim_id"],
        expected_revision=supported["revision"],
        approved_by="Noah",
        target_status=ClaimStatus.VERIFIED,
        ledger_path=ledger,
    )
    r = approve_claim(
        supported["claim_id"],
        approved_by="Noah",
        approval_reason="stale revision should fail",
        evidence_ids=[evidence["evidence_id"]],
        expected_revision=supported["revision"] + 1,
        approval_token=stale_token["token_id"],
        ledger_path=ledger,
    )
    assert r["status"] == "BLOCKED"
    assert r["reason_code"] == "STALE_REVISION"


def test_approve_claim_rejects_missing_evidence(ledger, supported_claim_with_evidence):
    supported, evidence = supported_claim_with_evidence
    token = issue_approval_token(
        claim_id=supported["claim_id"],
        expected_revision=supported["revision"],
        approved_by="Noah",
        target_status=ClaimStatus.VERIFIED,
        ledger_path=ledger,
    )
    r = approve_claim(
        supported["claim_id"],
        approved_by="Noah",
        approval_reason="missing evidence should fail",
        evidence_ids=["missing_evidence"],
        expected_revision=supported["revision"],
        approval_token=token["token_id"],
        ledger_path=ledger,
    )
    assert r["status"] == "BLOCKED"
    assert r["reason_code"] == "INVALID_EVIDENCE"


def test_approve_claim_rejects_model_output_as_sole_evidence(ledger, supported_claim_with_evidence):
    supported, _evidence = supported_claim_with_evidence
    model_evidence = record_evidence(
        evidence_text="A model said this is true.",
        source_id="model_output_1",
        source_type="model_output",
        scope="approval_contract",
        ledger_path=ledger,
    )
    token = issue_approval_token(
        claim_id=supported["claim_id"],
        expected_revision=supported["revision"],
        approved_by="Noah",
        target_status=ClaimStatus.VERIFIED,
        ledger_path=ledger,
    )
    r = approve_claim(
        supported["claim_id"],
        approved_by="Noah",
        approval_reason="model evidence should fail",
        evidence_ids=[model_evidence["evidence_id"]],
        expected_revision=supported["revision"],
        approval_token=token["token_id"],
        ledger_path=ledger,
    )
    assert r["status"] == "BLOCKED"
    assert r["reason_code"] == "INVALID_EVIDENCE"


def test_failed_approval_leaves_ledger_unchanged(ledger, supported_claim_with_evidence):
    from core.epistemic_ledger import _hash_payload, _load

    supported, _evidence = supported_claim_with_evidence
    model_evidence = record_evidence(
        evidence_text="A model said this is true.",
        source_id="model_output_2",
        source_type="model_output",
        scope="approval_contract",
        ledger_path=ledger,
    )
    token = issue_approval_token(
        claim_id=supported["claim_id"],
        expected_revision=supported["revision"],
        approved_by="Noah",
        target_status=ClaimStatus.VERIFIED,
        ledger_path=ledger,
    )
    before = _hash_payload(_load(ledger))
    approve_claim(
        supported["claim_id"],
        approved_by="Noah",
        approval_reason="model evidence should fail",
        evidence_ids=[model_evidence["evidence_id"]],
        expected_revision=supported["revision"],
        approval_token=token["token_id"],
        ledger_path=ledger,
    )
    after = _hash_payload(_load(ledger))
    assert before == after


def test_approve_claim_blocks_unresolved_contradiction(ledger, supported_claim_with_evidence):
    supported, evidence = supported_claim_with_evidence
    disputed = propose_claim(
        "A disputed claim cannot be verified while blocked.",
        status=ClaimStatus.SUPPORTED,
        source_ids=["dispute_a"],
        source_type="human_observation",
        scope="approval_contract",
        created_by="application",
        ledger_path=ledger,
    )
    contradictor = propose_claim(
        "A disputed claim can be verified while blocked.",
        status=ClaimStatus.SUPPORTED,
        source_ids=["dispute_b"],
        source_type="human_observation",
        scope="approval_contract",
        created_by="application",
        ledger_path=ledger,
    )
    link_contradiction(disputed["claim_id"], contradictor["claim_id"], ledger_path=ledger)
    disputed_now = get_claim(disputed["claim_id"], ledger_path=ledger)
    token = issue_approval_token(
        claim_id=disputed["claim_id"],
        expected_revision=disputed_now["revision"],
        approved_by="Noah",
        target_status=ClaimStatus.SUPPORTED,
        ledger_path=ledger,
    )
    r = approve_claim(
        disputed["claim_id"],
        approved_by="Noah",
        approval_reason="unresolved contradiction should fail",
        evidence_ids=[evidence["evidence_id"]],
        expected_revision=disputed_now["revision"],
        approval_token=token["token_id"],
        ledger_path=ledger,
    )
    assert r["status"] == "BLOCKED"
    assert r["reason_code"] == "UNRESOLVED_CONTRADICTION"


def test_valid_transition_verifies_and_creates_receipt_and_history(ledger, supported_claim_with_evidence):
    supported, evidence = supported_claim_with_evidence
    token = issue_approval_token(
        claim_id=supported["claim_id"],
        expected_revision=supported["revision"],
        approved_by="Noah",
        target_status=ClaimStatus.VERIFIED,
        ledger_path=ledger,
    )
    verified = approve_claim(
        supported["claim_id"],
        approved_by="Noah",
        approval_reason="verified by deterministic smoke evidence",
        evidence_ids=[evidence["evidence_id"]],
        expected_revision=supported["revision"],
        approval_token=token["token_id"],
        actor_mode=ActorMode.APPLICATION,
        ledger_path=ledger,
    )
    receipt = verified.get("approval_receipt", {})
    assert verified["status"] == ClaimStatus.VERIFIED.value
    assert verified["revision"] == supported["revision"] + 1
    assert receipt.get("operation") == "approve_claim"

    previous = get_claim_revision(supported["claim_id"], supported["revision"], ledger_path=ledger)
    assert previous and previous["status"] == ClaimStatus.SUPPORTED.value

    # Token reuse must be rejected.
    r = approve_claim(
        supported["claim_id"],
        approved_by="Noah",
        approval_reason="token reuse should fail",
        evidence_ids=[evidence["evidence_id"]],
        expected_revision=verified["revision"],
        approval_token=token["token_id"],
        actor_mode=ActorMode.APPLICATION,
        ledger_path=ledger,
    )
    assert r["status"] == "BLOCKED"
    assert r["reason_code"] == "INVALID_APPROVAL_TOKEN"

    retrieved = get_claim(supported["claim_id"], ledger_path=ledger)
    assert "provenance" in retrieved and retrieved["provenance"]["source_ids"]
    assert retrieved["status"] == ClaimStatus.VERIFIED.value


def test_search_claims_filters_by_query_and_status(ledger):
    propose_claim("Alpha claim about signals.", source_ids=["a"], status=ClaimStatus.INFERENCE, ledger_path=ledger)
    propose_claim("Beta claim about noise.", source_ids=["b"], status=ClaimStatus.UNKNOWN, ledger_path=ledger)

    by_text = search_claims("signals", ledger_path=ledger)
    assert len(by_text) == 1
    assert "signals" in by_text[0]["claim_text"]

    by_status = search_claims(status=ClaimStatus.UNKNOWN, ledger_path=ledger)
    assert len(by_status) == 1
    assert by_status[0]["status"] == ClaimStatus.UNKNOWN.value


def test_get_open_questions_includes_priority_score(ledger, supported_claim_with_evidence):
    supported, evidence = supported_claim_with_evidence
    token = issue_approval_token(
        claim_id=supported["claim_id"],
        expected_revision=supported["revision"],
        approved_by="Noah",
        target_status=ClaimStatus.VERIFIED,
        ledger_path=ledger,
    )
    approve_claim(
        supported["claim_id"],
        approved_by="Noah",
        approval_reason="verified by deterministic smoke evidence",
        evidence_ids=[evidence["evidence_id"]],
        expected_revision=supported["revision"],
        approval_token=token["token_id"],
        actor_mode=ActorMode.APPLICATION,
        ledger_path=ledger,
    )
    propose_claim("An open unknown.", status=ClaimStatus.UNKNOWN, source_ids=[], ledger_path=ledger)
    questions = get_open_questions(ledger_path=ledger)
    assert questions
    assert all("priority" in q for q in questions)


def test_get_claim_returns_none_for_missing_id(ledger):
    assert get_claim("does_not_exist", ledger_path=ledger) is None


def test_dispute_and_retract_raise_keyerror_for_missing_claim(ledger):
    with pytest.raises(KeyError):
        dispute_claim("missing", reason="x", ledger_path=ledger)
    with pytest.raises(KeyError):
        retract_claim("missing", reason="x", ledger_path=ledger)
