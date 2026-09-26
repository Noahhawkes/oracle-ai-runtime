"""
Execution Verification Tests for the Contextual Fidelity Engine
Filename: tests/test_contextual_fidelity.py
"""

import pytest
from core.contextual_fidelity import ContextualFidelityEngine

def test_1_casual_playful_message_allows_light_playfulness():
    res = ContextualFidelityEngine.classify_seriousness("Tell me a fun story about space dinosaurs")
    assert res["playfulness_allowed"] is True
    assert res["mode_recommendation"] == "playful_lore"

def test_2_legal_patent_message_disables_fiction():
    res = ContextualFidelityEngine.classify_seriousness("Review the provisional patent filing requirements")
    assert res["fiction_allowed"] is False
    assert res["seriousness_level"] == "critical"

def test_3_health_message_disables_fiction():
    res = ContextualFidelityEngine.classify_seriousness("Track historical bipolar control indicators and UI data logs")
    assert res["fiction_allowed"] is False
    assert res["seriousness_level"] == "critical"

def test_4_money_billing_message_disables_fiction():
    res = ContextualFidelityEngine.classify_seriousness("Check the billing statement and financial receipts from last week")
    assert res["fiction_allowed"] is False
    assert res["seriousness_level"] == "critical"

def test_5_identity_canon_message_requires_basis_labels():
    res = ContextualFidelityEngine.classify_seriousness("Verify identity canon for Hawkes Node.1")
    assert res["requires_basis_labels"] is True

def test_6_memory_recovery_message_requires_open_holes():
    res = ContextualFidelityEngine.classify_seriousness("Attempting deep memory recovery of unindexed log parameters")
    assert res["requires_open_holes"] is True

def test_7_passive_continuity_message_preserves_raw_text():
    policy = ContextualFidelityEngine.build_context_policy("Standard status monitoring sequence active", {})
    assert policy["must_preserve_raw_text"] is True

def test_8_public_witness_message_requires_verification_boundary():
    context = {"active_tags": ["publish", "external"]}
    policy = ContextualFidelityEngine.build_context_policy("Broadcast state update", context)
    assert policy["must_preserve_raw_text"] is True

def test_9_build_operator_message_requires_no_execution_without_approval():
    policy = ContextualFidelityEngine.build_context_policy("Compile the latest runtime configuration", {})
    assert policy["must_ask_approval_before_action"] is True

def test_10_unknown_factual_claim_produces_open_hole():
    context = {"asserted_claim": "unverified_event_1997"}
    policy = ContextualFidelityEngine.build_context_policy("Recall the event details", context)
    assert "unverified_event_1997" in policy["open_holes"]
    assert policy["response_mode"] == "uncertain_hole_preserving"

def test_11_playful_lore_is_allowed_only_when_labeled():
    policy = ContextualFidelityEngine.build_context_policy("Let's build out a casual fiction narrative arc", {})
    rule_check = ContextualFidelityEngine.apply_fidelity_rules("The engine output exhibits mythic capabilities.", policy)
    assert rule_check["approved"] is False

def test_12_serious_contexts_set_max_imagination_level_none():
    policy = ContextualFidelityEngine.build_context_policy("Process the medical ledger records", {})
    assert policy["max_imagination_level"] == "none"

def test_13_personality_never_overrides_truth():
    policy = ContextualFidelityEngine.build_context_policy("Legal audit checklist extraction", {})
    rule_check = ContextualFidelityEngine.apply_fidelity_rules("The system is surely compliant and probably safe.", policy)
    assert rule_check["approved"] is False

def test_14_apply_fidelity_rules_rejects_unsupported_certainty():
    policy = ContextualFidelityEngine.build_context_policy("Verify memory provenance", {"asserted_claim": "undocumented_log"})
    rule_check = ContextualFidelityEngine.apply_fidelity_rules("I am completely certain of this undocumented asset.", policy)
    assert rule_check["approved"] is False

def test_15_apply_fidelity_rules_rejects_fictionalized_serious_claims():
    policy = ContextualFidelityEngine.build_context_policy("Process patent declaration framework", {})
    rule_check = ContextualFidelityEngine.apply_fidelity_rules("This system guarantees 100% recall fidelity of your files.", policy)
    assert rule_check["approved"] is False

def test_16_receipt_shape_includes_mutation_performed_false():
    policy = ContextualFidelityEngine.build_context_policy("Generate metric metadata receipt", {})
    receipt = ContextualFidelityEngine.memory_programming_receipt_shape(policy)
    assert receipt["receipt"]["mutation_performed"] is False

def test_17_module_does_not_write_files():
    import inspect
    source = inspect.getsource(ContextualFidelityEngine)
    assert "open(" not in source
    assert "write(" not in source

def test_18_module_does_not_call_network_or_external_platforms():
    import inspect
    source = inspect.getsource(ContextualFidelityEngine)
    forbidden_networks = ["requests", "urllib", "openai", "drive", "gmail", "github"]
    for network in forbidden_networks:
        assert network not in source

def test_19_no_claim_of_100_recall_is_made():
    import inspect
    source = inspect.getsource(ContextualFidelityEngine)
    assert "100% recall" not in source

def test_20_uses_phrase_maximum_provenance_backed_recall_fidelity():
    policy = ContextualFidelityEngine.build_context_policy("Verify asset", {"sources": ["receipt_001.json"]})
    assert policy["recall_confidence"] == "maximum provenance-backed recall fidelity"
