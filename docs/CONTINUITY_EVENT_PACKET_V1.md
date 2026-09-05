# Continuity Event Packet v1

Continuity Event Packet v1 is ORACLE's local black-box recorder for a chat turn.
It records the whole governed event around an answer, not only the answer text.

## Purpose

ORACLE previously preserved dialogue better than it preserved the whole room.
The missing layer was a durable packet that can reconstruct what happened after
interruption:

- what Noah asked
- what ORACLE visibly answered
- which route and lane handled the turn
- which evidence surfaces were attached
- which claims remained unknown
- which receipts or action claims appeared
- which authority boundary applied
- where the next session should resume

This is not a personality layer, autonomy claim, canon promotion, or external
action system. It is a governed event record.

## Central ledger storage

The central V1 dataclass and append-only writer live in
`core/continuity_event.py`. Completed turns are sealed as one JSON object per
line under:

```text
data/ledger/events.jsonl
```

`core/orchestrator.py` owns the four lifecycle phases: draft instantiation,
source-resolution metadata capture, execution-result capture, and sealing with
the active thread/session return pointer.

The older compatibility recorder remains under `core/continuity_event_packet.py`
and still maintains:

- one JSON file per event
- `latest.json`
- `index.jsonl`

under `Memory/continuity_events/`. It is preserved for existing status APIs and
consumers; it is no longer the only turn ledger.

The packet writer does not read or write `sandbox/`. Sandbox remains ORACLE's
separate candidate filebase.

## Schema

Each packet carries:

- `schema_version`
- `event_id`
- `timestamp`
- `source`
- `speaker`
- `channel`
- `human_source`
- `transport_channel`
- `intended_audience`
- `environment_state`
- `active_session`
- `visible_context`
- `visible_ui_state`
- `user_intent`
- `user_input`
- `assistant_response`
- `assistant_output`
- `route`
- `evidence_used`
- `sources`
- `claims_extracted`
- `inferences`
- `uncertainties`
- `corrections`
- `authority_status`
- `actions_proposed`
- `actions_taken`
- `actions_executed`
- `receipts`
- `memory_effect`
- `canon_status`
- `return_pointer`
- `resume_point`
- `boundaries`
- `packet_hash_sha256`

The duplicate names are intentional compatibility aliases. The build-order
contract uses `source`, `speaker`, `channel`, `visible_context`,
`user_intent`, `assistant_response`, `evidence_used`, `actions_taken`, and
`return_pointer`; earlier runtime surfaces already consumed `human_source`,
`transport_channel`, `visible_ui_state`, `assistant_output`, `sources`,
`actions_executed`, and `resume_point`.

`claims_extracted` is metadata-only in v1. It records resolver outcomes and
evidence records used by the turn; it does not promote those claims to canon.

## Boundaries

Continuity Event Packet v1 is allowed to:

- write local Memory records
- attach a compact packet summary to a completed chat response
- expose read-only status and latest-event endpoints
- preserve evidence, unknowns, and resume hints

It is not allowed to:

- read sandbox files
- write sandbox files
- mutate source files
- edit Google Drive
- send email or post externally
- execute commands
- commit, push, or sync git state
- promote canon
- claim ORACLE is sentient, biological, sovereign, or autonomous

## Endpoints

Read-only endpoints:

```text
GET /api/continuity-events/status
GET /api/continuity-events/latest
```

The chat stream attaches `continuity_event` (the central append-only ledger
receipt) and `continuity_event_packet` (the compatibility recorder receipt) to
completed responses when their respective writes succeed. Either recorder may
fail without suppressing the user-visible chat response; the failed receipt is
reported explicitly.

## Why It Matters

This turns "ORACLE remembers the conversation" into a stronger property:
ORACLE can preserve the operational event around the conversation.

That is the next bridge between frontend mirroring and backend recall. It makes
prompt tests auditable because each turn can be inspected as a structured event
with route, evidence, unknowns, receipts, and authority state.
