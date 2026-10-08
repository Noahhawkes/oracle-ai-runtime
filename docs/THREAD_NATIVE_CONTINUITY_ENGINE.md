# Thread-Native Continuity Engine

Status: implemented as additive candidate infrastructure
Schema: `thread_native_continuity.v1`
Authority: Noah.Physical
Canon status: candidate
Promotion status: not_promoted

## Purpose

Thread-Native Continuity Intelligence moves ORACLE beyond loose memory retrieval by making the thread a first-class durable object.

A thread is not just a chat transcript, summary, or fact list. In this implementation, a thread is a persistent project/story/work-state container with provenance, heartbeat, candidate claims, reversible audit events, and relationships to other threads.

## Existing Architecture Observed

The repository already contains several continuity foundations:

- `core/thread_capture.py`: explicit local ingestion of supplied thread artifacts with raw custody copies, parsed transcripts, manifests, receipts, and search index entries.
- `core/thread_archive.py`: local thread export/import helpers against `Memory/oracle_memory.db`.
- `core/continuity_merge_engine.py`: deterministic conversation normalization, claim extraction, correction handling, conflict detection, diffs, review status, and merge receipts.
- `core/continuity_event_packet.py`: event-packet style continuity framing.
- `core/witness_custody.py`: source receipts, routed claims, memory status, contradiction records, and conservative promotion boundaries.
- `core/memory.py`: SQLite-backed session, message, fact, project, people, durable fact, and audit chain tables.

The missing layer was a durable thread object that owns:

- identity
- heartbeat
- source-to-thread membership
- current candidate state
- reversible updates
- links to other threads
- operational brief output

## Implemented Files

- `core/thread_native_continuity.py`
- `core/thread_engine.py`
- `tests/test_thread_native_continuity.py`
- `tests/test_thread_engine.py`

No runtime route, server restart, sandbox write, Drive mutation, GitHub push, or canon promotion was performed.

## Continuity Event Packet Projection

`core/thread_engine.py` is the Step 3 projection layer from Continuity Event
Packets into simple persistent thread snapshots. It is intentionally small and
deterministic: it reads a supplied event packet, appends the `event_id` to the
thread timeline, carries `claims_extracted` as candidate facts, preserves
`uncertainties` as open questions, stores correction metadata only when a
correction was detected, links evidence records, and exposes a compact
`where_were_we()` summary.

Default storage:

`Memory/thread_engine/`

This is a projection over event packets, not a second canon system. The older
`ThreadStore` remains the richer SQLite-backed store for source records,
thread items, relationships, heartbeats, and operational briefings.

## Minimal Thread Object

The implemented `ThreadRecord` contains:

- `thread_id`
- `human_title`
- `aliases`
- `creation_date`
- `last_activity`
- `participants`
- `related_organizations`
- `related_projects`
- `decisions`
- `active_questions`
- `open_problems`
- `assumptions`
- `confirmed_facts`
- `corrections`
- `evidence`
- `linked_documents`
- `linked_emails`
- `linked_voice_notes`
- `related_git_commits`
- `related_issues`
- `related_threads`
- `tasks`
- `waiting_on`
- `next_actions`
- `thread_health`
- `confidence`
- `provenance`
- `approval_state`
- `canon_status`
- `promotion_status`

Default governance values:

- `approval_state=pending_review`
- `canon_status=candidate`
- `promotion_status=not_promoted`

## Persistence Layer

The engine uses local SQLite.

Default path:

`Memory/thread_native_continuity.db`

Tables:

- `threads`: durable thread identity and base metadata.
- `source_records`: immutable source records with timestamp, origin, source identifier, SHA-256, provenance, ingestion metadata, and optional raw content.
- `thread_items`: candidate facts, decisions, tasks, questions, corrections, evidence, links, and related references.
- `thread_edges`: non-destructive thread-to-thread relationships.
- `heartbeats`: operational thread state snapshots.
- `audit_events`: reversible local audit events.

## Source Discipline

The implemented source statuses are:

- `OBSERVED`
- `SOURCED`
- `INFERRED`
- `PROPOSED`
- `CORRECTED`
- `UNKNOWN`

The engine does not promote repeated assistant text into fact. Ingested items remain candidate records unless a separate approval layer promotes them.

## Source-To-Thread Ingestion

`ThreadStore.ingest_source()` performs the minimal safe ingestion flow:

1. Preserve the source record.
2. Match likely existing threads by title or alias, or create a candidate thread when none exists.
3. Extract structured thread items from explicit lines such as:
   - `FACT[key]: value`
   - `DECISION[key]: value`
   - `TASK[key]: value`
   - `CORRECTION[key]: value`
   - `QUESTION[key]: value`
   - `PROBLEM[key]: value`
   - `WAITING_ON[key]: value`
   - `NEXT_ACTION[key]: value`
4. Attach every item to the source record.
5. Preserve corrections by superseding prior current items with the same key, without deleting history.
6. Write a reversible audit event.

This is intentionally deterministic and explicit. It does not call a model to infer hidden meaning.

## Thread Heartbeat

`ThreadStore.generate_heartbeat()` creates a persisted `ThreadHeartbeat` with:

- `thread_id`
- `state`
- `last_meaningful_change`
- `waiting_on`
- `urgency`
- `downstream_dependencies`
- `next_expected_event`
- `confidence`
- `generated_at`

Supported states:

- `ACTIVE`
- `WAITING`
- `BLOCKED`
- `MONITORING`
- `STALE`
- `COMPLETED`
- `ARCHIVED`

State inference is conservative:

- open problems imply `BLOCKED`
- waiting-on entries imply `WAITING`
- tasks or next actions imply `ACTIVE`
- archived/completed health overrides normal activity
- otherwise the thread is `MONITORING`

## Relationship Graph

`ThreadStore.link_threads()` creates non-destructive relationships between threads.

Example:

`Dealer Locator -> Costco Expansion`

The threads stay distinct. The graph records the relationship, confidence, evidence source, and timestamp. It does not merge identity, overwrite titles, or collapse timelines.

## Operational Briefing

`ThreadStore.daily_operational_briefing()` produces a local briefing directly from thread state.

The briefing includes:

- schema version
- generation time
- thread count
- active entries
- thread state
- waiting-on values
- next expected event
- confidence
- approval state
- canon status
- confirmation that no canon promotion or external action occurred

This is the first small version of ORACLE noticing which threads are alive, waiting, blocked, or ready for action.

## What This Is Not

This implementation is not:

- a new chatbot
- a model prompt rewrite
- an autonomous self-modification system
- a sandbox writer
- a GitHub pusher
- a Drive editor
- a canon promotion mechanism
- a background watcher
- a claim that ORACLE is conscious, sentient, biological, sovereign, or alive

It is durable local infrastructure for organizing continuity.

## Gap Analysis

Implemented now:

- persistent thread records
- source records with hashes and provenance
- structured source-to-thread ingestion
- correction preservation without deletion
- thread heartbeat generation
- thread relationship graph
- operational briefing
- focused deterministic tests

Still needed before runtime integration:

- API route for thread status and briefing
- UI panel for thread heartbeat review
- integration with `core/continuity_merge_engine.py` claim objects
- integration with existing `Memory/oracle_memory.db` sessions and receipts
- approval workflow for review/edit/reject/defer
- reversible rollback command for thread item changes
- richer source membership scoring
- native display of competing evidence and contradictions
- import bridge from `thread_capture.py` manifests
- model-free daily briefing route exposed to the local UI

## Recommended Next Step

Add a read-only API surface:

- `GET /api/threads`
- `GET /api/threads/<thread_id>`
- `GET /api/threads/<thread_id>/heartbeat`
- `GET /api/threads/briefing`

Then add a compact UI panel that shows thread title, state, waiting-on, next action, confidence, and provenance. Keep all mutation endpoints behind explicit approval.

## Validation

Focused validation:

`python -m py_compile core\thread_native_continuity.py`

`python -m pytest tests\test_thread_native_continuity.py -vv`

Expected result:

Six tests pass, covering restart survival, source hashing, item extraction, correction supersession, heartbeat state, relationship graph behavior, and operational briefing output.
