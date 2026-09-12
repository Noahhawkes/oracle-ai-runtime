"""Acceptance tests for the ORACLE Memory Intake Contract (Phase 1).

Pure governance: classify memory candidates before storage/recall. These tests
assert the doctrine rules and the module's inertness (no IO/DB/network).
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "core")):
    if p not in sys.path:
        sys.path.insert(0, p)

import memory_intake_contract as mic
from memory_intake_contract import (
    MemoryCandidate, MemoryKind, MemorySource, MemoryStatus,
    RecallPermission, PrivacyTier, route_memory_candidate,
)


def _cand(**kw):
    base = dict(candidate_id="c", text="something meaningful",
                source=MemorySource.USER_DECLARED, kind=MemoryKind.SEMANTIC)
    base.update(kw)
    return MemoryCandidate(**base)


def test_user_preference_durable_not_canon():
    d = route_memory_candidate(_cand(
        text="Noah prefers build-don't-buy.",
        source=MemorySource.USER_DECLARED, kind=MemoryKind.PREFERENCE))
    assert d.accepted
    assert d.memory_status == MemoryStatus.DURABLE
    assert d.memory_status != MemoryStatus.CANON
    assert "request_user_approval_for_canon" in d.allowed_next_actions


def test_user_preference_canon_only_with_approval():
    d = route_memory_candidate(_cand(
        source=MemorySource.USER_DECLARED, kind=MemoryKind.PREFERENCE, user_approved=True))
    assert d.memory_status == MemoryStatus.CANON


def test_generated_summary_without_sources_stays_temporary():
    d = route_memory_candidate(_cand(
        source=MemorySource.GENERATED_SUMMARY, kind=MemoryKind.SEMANTIC,
        has_source_references=False))
    assert d.memory_status == MemoryStatus.TEMPORARY
    assert any("source reference" in h for h in d.open_holes)


def test_generated_summary_with_sources_can_be_durable():
    d = route_memory_candidate(_cand(
        source=MemorySource.GENERATED_SUMMARY, has_source_references=True))
    assert d.memory_status == MemoryStatus.DURABLE


def test_model_inference_cannot_become_canon():
    d = route_memory_candidate(_cand(
        source=MemorySource.MODEL_INFERRED, kind=MemoryKind.STRATEGIC, user_approved=True))
    assert d.memory_status != MemoryStatus.CANON
    assert d.memory_status == MemoryStatus.CANDIDATE


def test_financial_memory_restricted_from_action_planning():
    d = route_memory_candidate(_cand(
        text="card balance 8180", source=MemorySource.USER_DECLARED,
        kind=MemoryKind.PROJECT, privacy_tier=PrivacyTier.FINANCIAL))
    assert d.recall_permission != RecallPermission.RECALL_FOR_ACTION_PLANNING
    assert d.recall_permission == RecallPermission.RECALL_ONLY_AFTER_USER_CONFIRMS


def test_contradiction_becomes_disputed():
    d = route_memory_candidate(_cand(contradictions=("claim-a", "claim-b")))
    assert d.memory_status == MemoryStatus.DISPUTED
    assert d.accepted  # preserved, not dropped
    assert any("contradiction" in h for h in d.open_holes)


def test_uploaded_file_with_receipt_is_durable_without_becomes_candidate():
    with_receipt = route_memory_candidate(_cand(
        source=MemorySource.UPLOADED_FILE, kind=MemoryKind.PROJECT, has_receipt=True))
    without = route_memory_candidate(_cand(
        source=MemorySource.UPLOADED_FILE, kind=MemoryKind.PROJECT, has_receipt=False))
    assert with_receipt.memory_status == MemoryStatus.DURABLE
    assert without.memory_status == MemoryStatus.CANDIDATE
    assert without.required_receipts  # needs a receipt to upgrade


def test_credential_content_rejected_never_recall():
    d = route_memory_candidate(_cand(text="my api_key=sk-abcdefghijklmnopqrstuv1234"))
    assert d.accepted is False
    assert d.memory_status == MemoryStatus.REJECTED
    assert d.recall_permission == RecallPermission.NEVER_RECALL
    assert d.privacy_tier == PrivacyTier.CREDENTIAL_SECRET
    assert d.open_holes  # left an open hole, not a fabricated memory


def test_runtime_observation_without_receipt_is_candidate_with_open_hole():
    d = route_memory_candidate(_cand(
        source=MemorySource.RUNTIME_OBSERVED, kind=MemoryKind.EPISODIC, has_receipt=False))
    assert d.memory_status == MemoryStatus.CANDIDATE
    assert any("receipt" in h for h in d.open_holes)
    assert "runtime observation receipt" in d.required_receipts


def test_relationship_memory_requires_label_and_privacy_tier():
    d = route_memory_candidate(_cand(
        text="Ashley is Noah's partner.", source=MemorySource.USER_DECLARED,
        kind=MemoryKind.RELATIONSHIP, privacy_tier=PrivacyTier.PERSONAL))
    assert d.privacy_tier == PrivacyTier.FAMILY            # escalated
    assert d.recall_permission == RecallPermission.RECALL_WITH_LABEL
    assert "label_on_recall" in d.allowed_next_actions


def test_open_thread_remains_candidate():
    d = route_memory_candidate(_cand(
        source=MemorySource.USER_DECLARED, kind=MemoryKind.OPEN_THREAD, closed=False))
    assert d.memory_status == MemoryStatus.CANDIDATE
    closed = route_memory_candidate(_cand(
        source=MemorySource.USER_DECLARED, kind=MemoryKind.OPEN_THREAD, closed=True))
    assert closed.memory_status != MemoryStatus.CANDIDATE  # may promote once closed


def test_external_connector_preserves_source_and_timestamp():
    missing = route_memory_candidate(_cand(source=MemorySource.EXTERNAL_CONNECTOR))
    assert missing.memory_status == MemoryStatus.CANDIDATE
    assert missing.required_receipts
    present = route_memory_candidate(_cand(
        source=MemorySource.EXTERNAL_CONNECTOR, source_id="gmail:123", timestamp="2026-06-27T00:00:00Z"))
    assert present.memory_status == MemoryStatus.DURABLE


def test_risk_guardrail_recallable_for_action_planning():
    d = route_memory_candidate(_cand(
        text="HANDS_OFF by default.", source=MemorySource.USER_DECLARED,
        kind=MemoryKind.RISK_GUARDRAIL, privacy_tier=PrivacyTier.PUBLIC))
    assert d.recall_permission == RecallPermission.RECALL_FOR_ACTION_PLANNING


def test_empty_candidate_rejected_with_open_hole():
    d = route_memory_candidate(_cand(text="   "))
    assert d.accepted is False
    assert d.memory_status == MemoryStatus.REJECTED
    assert d.open_holes


def test_decision_is_json_safe():
    d = route_memory_candidate(_cand())
    js = d.to_dict()
    assert js["memory_status"] in {s.value for s in MemoryStatus}
    assert js["recall_permission"] in {r.value for r in RecallPermission}


def test_module_is_inert_no_io_db_network():
    """Purity guard: the module must not import IO/DB/network/embedding libs."""
    src = Path(mic.__file__).read_text(encoding="utf-8")
    forbidden = [
        r"\bimport\s+sqlite3", r"\bimport\s+socket", r"\bimport\s+requests",
        r"\bimport\s+urllib", r"\bfrom\s+urllib", r"\bimport\s+httpx",
        r"chromadb", r"qdrant", r"neo4j", r"openai", r"sentence_transformers",
        r"\bopen\s*\(", r"\.write\s*\(", r"subprocess", r"\bos\.",
    ]
    for pat in forbidden:
        assert not re.search(pat, src), f"forbidden pattern in module: {pat}"
    # Only stdlib imports expected.
    imports = re.findall(r"^(?:from|import)\s+(\w+)", src, re.MULTILINE)
    assert set(imports) <= {"__future__", "re", "dataclasses", "enum", "typing", "json"}
