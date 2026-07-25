from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import continuity_merge_engine as cme  # noqa: E402


def test_normalization_preserves_event_provenance_and_hashes():
    result = cme.normalize_conversation(
        {
            "thread_id": "thread-alpha",
            "source_ref": "chatgpt_export.json",
            "messages": [
                {
                    "message_id": "m1",
                    "timestamp": "2026-07-20T10:00:00Z",
                    "speaker": "Noah.Physical",
                    "role": "user",
                    "content": "FACT[oracle_port]: ORACLE listens on 7781.",
                    "attachments": ["source.txt"],
                }
            ],
        }
    )

    event = result[0]
    assert event.thread_id == "thread-alpha"
    assert event.message_id == "m1"
    assert event.source_ref == "chatgpt_export.json"
    assert event.attachments == ("source.txt",)
    assert event.evidence_class == cme.EvidenceClass.UPLOADED_SOURCE
    assert len(event.content_sha256) == 64
    assert event.canon_status == "candidate"
    assert event.promotion_status == "not_promoted"


def test_assistant_repetition_is_not_treated_as_human_evidence():
    result = cme.merge_conversations(
        [
            {
                "thread_id": "assistant-repeat",
                "messages": [
                    {
                        "message_id": "a1",
                        "timestamp": "2026-07-20T10:00:00Z",
                        "role": "assistant",
                        "speaker": "ChatGPT",
                        "content": "FACT[oracle_alive]: ORACLE is alive.",
                    },
                    {
                        "message_id": "a2",
                        "timestamp": "2026-07-20T10:01:00Z",
                        "role": "assistant",
                        "speaker": "Claude",
                        "content": "FACT[oracle_alive]: ORACLE is alive.",
                    },
                ],
            }
        ],
        merged_at="2026-07-20T10:02:00Z",
    )

    assert len(result.claims) == 2
    assert all(claim.evidence_class == cme.EvidenceClass.ASSISTANT_GENERATED for claim in result.claims)
    assert all(claim.confidence == 0.25 for claim in result.claims)
    assert result.duplicates
    assert result.receipt.canon_promoted is False


def test_corrections_supersede_older_claims_without_deleting_history():
    result = cme.merge_conversations(
        [
            {
                "thread_id": "port-correction",
                "messages": [
                    {
                        "message_id": "m1",
                        "timestamp": "2026-07-20T10:00:00Z",
                        "role": "user",
                        "speaker": "Noah.Physical",
                        "content": "FACT[oracle_port]: ORACLE listens on 7777.",
                    },
                    {
                        "message_id": "m2",
                        "timestamp": "2026-07-20T10:05:00Z",
                        "role": "user",
                        "speaker": "Noah.Physical",
                        "content": "CORRECTION[oracle_port]: 7777 -> 7781.",
                    },
                ],
            }
        ],
        merged_at="2026-07-20T10:06:00Z",
    )

    old_claim = next(claim for claim in result.claims if claim.claim_type == cme.ClaimType.FACT)
    correction = next(claim for claim in result.claims if claim.claim_type == cme.ClaimType.CORRECTION)

    assert old_claim.superseded_by == (correction.claim_id,)
    assert correction.supersedes == (old_claim.claim_id,)
    assert len(result.events) == 2
    assert result.current_state["deprecated_claims"][0]["claim_id"] == old_claim.claim_id
    assert result.diff["superseded"]
    assert result.diff["corrected"]


def test_conflicts_are_preserved_for_human_review():
    result = cme.merge_conversations(
        [
            {
                "thread_id": "conflict-a",
                "messages": [
                    {
                        "message_id": "m1",
                        "timestamp": "2026-07-20T10:00:00Z",
                        "role": "user",
                        "speaker": "Noah.Physical",
                        "content": "PROJECT_STATE[github_backup]: GitHub backup is PENDING.",
                    }
                ],
            },
            {
                "thread_id": "conflict-b",
                "messages": [
                    {
                        "message_id": "m2",
                        "timestamp": "2026-07-20T10:01:00Z",
                        "role": "user",
                        "speaker": "Noah.Physical",
                        "content": "PROJECT_STATE[github_backup]: GitHub backup is VERIFIED.",
                    }
                ],
            },
        ],
        merged_at="2026-07-20T10:02:00Z",
    )

    assert len(result.conflicts) == 1
    conflict = result.conflicts[0]
    assert conflict.normalized_key == "github_backup"
    assert conflict.status == "requires_review"
    assert conflict.resolution == "unresolved"
    assert len(conflict.claim_ids) == 2
    assert result.current_state["conflicts"][0]["conflict_id"] == conflict.conflict_id


def test_current_state_groups_tasks_decisions_preferences_and_relationships():
    result = cme.merge_conversations(
        [
            {
                "thread_id": "state-map",
                "messages": [
                    {
                        "message_id": "m1",
                        "timestamp": "2026-07-20T10:00:00Z",
                        "role": "user",
                        "speaker": "Noah.Physical",
                        "content": "\n".join(
                            [
                                "PREFERENCE[voice]: Use concise readbacks.",
                                "DECISION[cme_scope]: Build CME milestone 1 as pure core.",
                                "TASK[cme_tests]: DONE write deterministic tests.",
                                "TASK[cme_ui]: Add review UI later.",
                                "RELATIONSHIP[ashley_role]: Ashley is reality gravity in Silverback Tales.",
                            ]
                        ),
                    }
                ],
            }
        ],
        merged_at="2026-07-20T10:01:00Z",
    )

    state = result.current_state
    assert state["preferences"][0]["key"] == "voice"
    assert state["active_decisions"][0]["key"] == "cme_scope"
    assert state["completed_tasks"][0]["key"] == "cme_tests"
    assert state["open_tasks"][0]["key"] == "cme_ui"
    assert state["relationship_context"][0]["key"] == "ashley_role"
    assert state["receipts"]["canon_promoted"] is False


def test_review_approval_does_not_promote_canon():
    result = cme.merge_conversations(
        [
            {
                "thread_id": "review",
                "messages": [
                    {
                        "message_id": "m1",
                        "timestamp": "2026-07-20T10:00:00Z",
                        "role": "user",
                        "speaker": "Noah.Physical",
                        "content": "FACT[authority]: Noah.Physical is approval authority.",
                    }
                ],
            }
        ],
        merged_at="2026-07-20T10:01:00Z",
    )
    claim_id = result.claims[0].claim_id

    reviewed = cme.apply_review_action(result.claims, claim_id, cme.ReviewStatus.APPROVED)
    decision = cme.build_review_decision(claim_id, cme.ReviewStatus.APPROVED)

    assert reviewed[0].review_status == cme.ReviewStatus.APPROVED
    assert reviewed[0].approved_by == "Noah.Physical"
    assert reviewed[0].canon_status == "candidate"
    assert reviewed[0].promotion_status == "not_promoted"
    assert decision.canon_promoted is False


def test_merge_receipt_proves_no_external_or_destructive_action():
    result = cme.merge_conversations(
        [
            {
                "thread_id": "receipt",
                "messages": [
                    {
                        "message_id": "m1",
                        "timestamp": "2026-07-20T10:00:00Z",
                        "role": "user",
                        "speaker": "Noah.Physical",
                        "content": "TASK[cme]: Implement governed merge core.",
                    }
                ],
            }
        ],
        merged_at="2026-07-20T10:01:00Z",
    )

    receipt = result.receipt
    assert receipt.operation == "continuity_merge"
    assert receipt.source_thread_ids == ("receipt",)
    assert receipt.external_action is False
    assert receipt.raw_records_mutated is False
    assert receipt.history_destroyed is False
    assert receipt.deterministic_core is True
    assert len(receipt.receipt_hash_sha256) == 64
    assert result.to_dict()["schema_version"] == cme.SCHEMA_VERSION
