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

## Storage

Packets are written locally under:

```text
Memory/continuity_events/
```

The writer maintains:

- one JSON file per event
- `latest.json`
- `index.jsonl`

The packet writer does not read or write `sandbox/`. Sandbox remains ORACLE's
separate candidate filebase.

## Schema

Each packet carries:

- `schema_version`
- `event_id`
- `timestamp`
- `human_source`
- `transport_channel`
- `intended_audience`
- `environment_state`
- `active_session`
- `visible_ui_state`
- `user_input`
- `assistant_output`
- `route`
- `sources`
- `inferences`
- `uncertainties`
- `corrections`
- `authority_status`
- `actions_proposed`
- `actions_executed`
- `receipts`
- `memory_effect`
- `canon_status`
- `resume_point`
- `boundaries`
- `packet_hash_sha256`

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

The chat stream also attaches a `continuity_event_packet` summary to completed
responses when packet writing succeeds.

## Why It Matters

This turns "ORACLE remembers the conversation" into a stronger property:
ORACLE can preserve the operational event around the conversation.

That is the next bridge between frontend mirroring and backend recall. It makes
prompt tests auditable because each turn can be inspected as a structured event
with route, evidence, unknowns, receipts, and authority state.
