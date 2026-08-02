# Recursive Journal Custody Design

Status: candidate
Canon status: candidate
Promotion status: not_promoted
Authority: Noah.Physical

> A recursive journal does not remember better. It catches memory changing.

## Purpose

The recursive journal is an append-only custody view over continuity events. It records what changed between a new claim and prior claims without converting repetition, fluency, or transport into evidence.

The existing deterministic `core/continuity_merge_engine.py` supplies normalization, corrections, contradiction detection, current-state projection, and conversation diff. The journal is a future storage adapter over that pure core, not a second merge algorithm.

## Entry contract

| Field | Meaning |
|---|---|
| `entry_id` | Stable identifier derived from source reference and claim hash |
| `source_channel` | Transport such as ORACLE, ChatGPT export, file ingest, or witness |
| `source_reference` | Immutable pointer to the source record or receipt |
| `submitted_by` | Actor who supplied the record; not automatically its author |
| `authorial_authority` | Declared or verified author when known |
| `created_at` | Source timestamp; import time is stored separately |
| `claim_type` | witnessed, declared, inferred, generated, disputed, or unknown |
| `claim_text` | Exact candidate claim text |
| `known_fields` | Fields supported by the source |
| `unknown_fields` | Explicit evidence gaps |
| `delta_pass` | Deterministic comparison with referenced prior entries |
| `drift_flag` | Meaning changed without adequate source evidence |
| `rollback_anchor` | Projection/version that can be restored without deleting history |
| `receipt_reference` | Receipt covering source and journal append |
| `canon_status` | Candidate/status label; never inferred from repetition |
| `promotion_status` | Defaults to `not_promoted` |

## Delta pass

A delta pass emits four lists:

- `added_fields`
- `changed_fields`
- `removed_or_unknown_fields`
- `unchanged_fields`

Each changed field includes prior entry IDs and evidence classes. A change is not a correction unless an explicit correction source or Noah.Physical decision says so.

## Drift rules

Set `drift_flag=true` when any of these occur without adequate evidence:

- inferred text becomes declared fact;
- generated text becomes attributed to the submitter;
- an unknown field becomes known;
- candidate material becomes canon;
- a contradiction disappears from the projection;
- meaning changes while the source reference stays the same.

## Append and rollback

Journal entries are immutable. Review decisions append new entries referencing the older entry. Rollback selects an earlier projection anchor; it never deletes events or receipts.

## Boundaries

- No external action.
- No automatic canon promotion.
- No authorship rebinding from copy/paste or transport.
- No model confidence used as evidence.
- Noah.Physical remains the final correction and promotion authority.

## Acceptance mapping

- Known facts and unknowns are separate fields.
- `delta_pass` compares a new entry with prior entries.
- `drift_flag` exposes unsupported meaning changes.
- `submitted_by` and `authorial_authority` are distinct.
- Candidate/not-promoted status is the default.
