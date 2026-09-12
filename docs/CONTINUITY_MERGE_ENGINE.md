# Continuity Merge Engine

Status: milestone 1 candidate  
Authority: Noah.Physical  
Canon status: candidate  
Promotion status: not_promoted  
Module: `core/continuity_merge_engine.py`

## One-Line Definition

Continuity Merge Engine (CME) is a deterministic, governed conversation version-control core for merging long-running AI threads into reviewable continuity state without inventing, overwriting, or silently promoting memory.

## What This Is

CME is not a text concatenation tool. It is the first "Git for conversational continuity" layer in ORACLE.

It takes multiple conversation sources, normalizes them into events, extracts candidate claims, detects duplicates and contradictions, applies explicit corrections, generates current-state projections, and produces a receipt proving that no source record was mutated and no canon promotion happened.

## What This Is Not

- Not a memory promotion engine.
- Not a model or embedding pipeline.
- Not a source of legal, personal, or creative canon.
- Not a browser scraper, Drive mutator, GitHub pusher, or external sender.
- Not proof that ORACLE is conscious, sentient, alive, autonomous, or sovereign.
- Not a replacement for Noah.Physical approval.

## Existing Spine It Builds On

CME follows existing ORACLE custody conventions:

- `core/thread_capture.py` preserves raw transcript custody and parsed message records.
- `core/thread_continuity_ingest.py` extracts candidate packs without storing raw thread text.
- `core/continuity_event_packet.py` records whole-turn event packets for chat continuity.
- `core/witness_custody.py` separates witnessed, declared, uploaded, generated, inferred, disputed, unsupported, and unresolved claims.
- `core/memory_intake_contract.py` separates source, status, privacy, recall permission, receipts, and open holes.
- `rendered_reality/receipts/receipt.py` preserves receipts, authorship, approval status, canon status, and Return-from-Dark honesty.

CME sits above those surfaces. It merges what has been captured. It does not capture hidden sources itself.

## Folder Structure

Current milestone:

```text
core/continuity_merge_engine.py
tests/test_continuity_merge_engine.py
docs/CONTINUITY_MERGE_ENGINE.md
```

Planned later milestones:

```text
Memory/continuity_merge/
  raw_event_refs/
  merge_receipts/
  review_queue/
  current_state/

ui/
  existing ORACLE interface extension only; no second localhost app
```

## Data Models

### ConversationMessage

Input message shape:

- `thread_id`
- `message_id`
- `timestamp`
- `speaker`
- `role`
- `content`
- `attachments`
- `quoted_text`
- `tool_output`
- `imported_summary`
- `source_ref`

### ContinuityEvent

Normalized event shape:

- `event_id`
- `thread_id`
- `message_id`
- `timestamp`
- `ordinal`
- `speaker`
- `role`
- `content`
- `content_sha256`
- `evidence_class`
- `attachments`
- `quoted_text`
- `tool_output`
- `imported_summary`
- `source_ref`
- `canon_status`
- `promotion_status`

### ContinuityClaim

Candidate claim shape:

- `claim_id`
- `claim_type`
- `claim_text`
- `normalized_key`
- `source_event_ids`
- `thread_ids`
- `evidence_class`
- `confidence`
- `provenance`
- `metadata`
- `review_status`
- `canon_status`
- `promotion_status`
- `approved_by`
- `reviewed_by`
- `supersedes`
- `superseded_by`
- `contradicts`

### MergeReceipt

Merge receipt shape:

- `schema_version`
- `operation`
- `source_thread_ids`
- `event_count`
- `claim_count`
- `duplicate_count`
- `conflict_count`
- `merged_at`
- `canon_promoted`
- `external_action`
- `raw_records_mutated`
- `history_destroyed`
- `deterministic_core`
- `receipt_hash_sha256`

## Evidence Classes

CME uses explicit evidence labels:

- `human_declared`
- `machine_observed`
- `uploaded_source`
- `assistant_generated`
- `tool_output`
- `imported_summary`
- `inference`
- `unknown`

Repeated assistant output is never treated as human evidence. Assistant-generated claims remain low-confidence candidates until reviewed against sources.

## Claim Types

CME recognizes:

- `fact`
- `preference`
- `correction`
- `decision`
- `task`
- `relationship`
- `project_state`
- `unknown`

The deterministic extractor prefers tagged lines:

```text
FACT[oracle_port]: ORACLE listens on 7781.
PREFERENCE[voice]: Use concise readbacks.
DECISION[cme_scope]: Build milestone 1 as pure core.
TASK[cme_tests]: DONE write deterministic tests.
CORRECTION[oracle_port]: 7777 -> 7781.
```

This tag-first contract is deliberate. It avoids pretending that vague model prose is reliable structured truth.

## Merge Algorithm

1. Accept one or more conversation batches.
2. Normalize every message into a `ContinuityEvent`.
3. Hash event content.
4. Assign evidence class from role, speaker, attachments, tool output, and imported summaries.
5. Extract tagged or conservative prefix-based candidate claims.
6. Apply explicit corrections by marking older same-key claims as superseded.
7. Detect exact or keyed duplicates without deleting older claims.
8. Detect active same-key contradictions and emit conflict records.
9. Generate current-state projections.
10. Generate conversation diff.
11. Generate a merge receipt.

Raw events and older claims remain visible. CME does not erase history.

## Conflict Algorithm

CME groups active, non-superseded claims by `normalized_key`.

If the same key has multiple distinct active claim texts, CME:

- marks the claims as contradicting one another,
- emits a `ConflictRecord`,
- leaves the conflict unresolved,
- requires human review.

CME does not choose a winner based on fluency, repetition, confidence, or recency alone.

## Current State Generator

The current-state projection produces:

- `current_facts`
- `current_projects`
- `open_tasks`
- `completed_tasks`
- `active_decisions`
- `relationship_context`
- `preferences`
- `deprecated_claims`
- `conflicts`
- `timeline`
- `receipts`

This is a projection, not canon. It is a review surface.

## Conversation Diff

CME reports:

- `added`
- `removed`
- `corrected`
- `superseded`
- `changed_authority`
- `changed_canon`
- `changed_evidence`

Normal merges should not remove claims. If a comparison shows removed claims, the UI should treat that as a review concern, not as deletion authority.

## Review Workflow

Milestone 1 includes a pure review action function.

A reviewer may:

- approve
- reject
- edit
- defer

Approval changes `review_status`. It does not promote canon.

Canon promotion remains a separate, explicit Noah.Physical authority path.

## Interfaces

Current pure-Python entrypoints:

```python
normalize_conversation(batch)
extract_claims(events)
apply_corrections(claims)
find_duplicates(claims)
detect_conflicts(claims)
generate_current_state(claims, conflicts)
conversation_diff(base_claims, merged_claims)
apply_review_action(claims, claim_id, action)
build_review_decision(claim_id, action)
merge_conversations(conversations)
```

## Determinism Rules

- No model calls.
- No embeddings.
- No network access.
- No database access.
- No filesystem writes.
- No runtime restart.
- Stable IDs use hashes of stable input fields.
- Receipt hashes exclude wall-clock timestamp so the core proof remains reproducible.

## Risks And Edge Cases

- Untagged prose may hide important claims. That is acceptable for milestone 1 because false structure is worse than missed structure.
- Semantic duplicate detection is currently key/exact only. Embedding-based matching can be added later only with clear provenance and test boundaries.
- Human speech captured through another system may still have uncertain audience or source authority. CME preserves event provenance but does not solve intent by itself.
- Imported summaries remain low authority unless source references are attached.
- Review approval is not canon approval.
- Relationship and family context require privacy handling before broader recall or publication.

## Incremental Implementation Plan

### Milestone 1: Pure Core

Completed by this package:

- deterministic event normalization
- tagged claim extraction
- duplicate detection
- explicit correction supersession
- conflict detection
- current-state projection
- conversation diff
- review action model
- merge receipt
- tests and architecture doc

### Milestone 2: Storage Adapter

Add a local adapter that reads existing ORACLE sources and writes only CME records:

- `core/thread_capture.py` parsed transcript output
- `core/continuity_event_packet.py` event packet output
- `Memory/thread_ingest/` candidate packs

No raw source mutation.

### Milestone 3: Existing UI Review Pane

Extend the current ORACLE UI with a CME review pane:

- pending claims
- conflicts
- superseded claims
- evidence trail
- approve/reject/edit/defer controls

Do not create a second localhost interface.

### Milestone 4: Current State API

Expose read-only endpoints:

```text
GET /api/continuity-merge/status
GET /api/continuity-merge/current-state
GET /api/continuity-merge/conflicts
```

Write endpoints require explicit scoped approval.

### Milestone 5: Multi-Thread Merge Runs

Run CME against selected ChatGPT, Claude, Gemini, Codex, and ORACLE exports. Produce a review queue, not canon memory.

## Human Authority

Noah.Physical remains final approval authority.

CME may organize continuity. CME may not redefine identity, promote canon, publish, push, send, or mutate external systems.
