# ORACLE Context Compiler + DeepCut Memory Bus V1

**Timestamp:** 2026-08-27T11:24-05:00  
**Authority:** Noah.Physical  
**Status:** Build order, not proof of implementation  
**Mode:** Inspect -> Build -> Test -> Receipt

## Mission

Fix the fundamental continuity limitation: Noah can mention something important without re-supplying its history. ORACLE must recover relevant history before generation rather than depending on whichever model happens to have the old conversation in its context window.

The model is replaceable working cognition. ORACLE continuity must survive new chats, model swaps, runtime restarts, desktop restarts, context-window exhaustion, time away, and UI changes.

## 1. Canonical Context Compiler

Trace the current real message path before changing it. Then implement the smallest deterministic Context Compiler that accepts:

- current message
- durable thread_id
- speaker/source identity when known
- active goal when known
- detected entities
- recent turns

It should produce a bounded `ContextPacket` containing only relevant, provenance-bound material:

- current thread
- active goal
- important entities
- relationships
- canonical facts
- historical facts
- corrections and supersession
- conflicts
- open loops
- relevant journal/events
- relevant source records
- unresolved unknowns
- current runtime state when relevant

The LLM may reason over this packet. It must not decide what memory exists merely from its prompt.

## 2. Durable Entity Resolution

Use database-backed entity resolution rather than one-file-per-memory storage.

Example aliases/canon layers that must be preservable rather than flattened:

- USS Avalon
- Avalon
- NCC-75154
- NCC-75154-JS
- historical NCC-2376-A layer

Important entities should support, where evidence exists:

- entity_id
- aliases
- domain
- relationships
- importance
- source references
- historical states
- current/canonical state
- corrections
- conflicts
- last retrieval metadata

Do not silently merge conflicting canon or identity claims.

## 3. Importance-Aware Deep Retrieval

Not every noun needs an expensive retrieval pass.

For continuity-significant entities, perform deep retrieval before generation. For ordinary entities, use normal retrieval. When entity resolution is uncertain, perform a bounded resolution check rather than guessing.

## 4. Remember-Before-Answering Gate

For continuity-significant requests, generation must wait for retrieval to resolve to one of:

- SUFFICIENT
- PARTIAL
- CONFLICT
- NOT_FOUND
- SOURCE_UNAVAILABLE

PARTIAL means answer only what is supported and preserve the hole. CONFLICT means expose the conflict. NOT_FOUND and SOURCE_UNAVAILABLE must never be converted into invented continuity.

## 5. Threads Are Not the Whole Memory

A durable thread is a conversation container, not Noah's entire world. Entity history, relationships, research, creative canon, corrections, project state, journals, and provenance must remain retrievable across threads.

New threads must be able to recover old knowledge without rewriting old threads.

## 6. Rehydration

On startup, load a compact return pointer, not the entire corpus.

On interaction:

`turn -> entity/topic resolution -> relevant retrieval -> bounded ContextPacket -> reasoning -> response -> receipt/event`

This is the path to large durable memory without enormous prompts.

## 7. Source Priority and Correction Law

Respect existing provenance/governance rules. Prefer direct human-authored and current canonical evidence over later AI summaries. Explicit corrections and supersession must be represented rather than erased.

Repeated AI summaries do not become independent verification.

Candidate is not canon. Historical state is not current state. Preserve unknowns.

## 8. Cold-Start Regression Tests

Do not hide answers in fixtures or system prompts. Start with no relevant subject context in the conversational prompt and require retrieval.

Minimum cold-start questions:

1. `What is the registry of the USS Avalon?`
2. `Who is Ashley?`
3. `What is Dual Hemispheric Cohesion?`
4. `What is MindCoin?`
5. `Who is Ellie?`
6. `What is Rendered Reality?`
7. `Where were we?`

For Avalon, pass only when the system retrieves supported canon layers and preserves differences between them rather than choosing one by fluency.

For any question lacking sufficient evidence, the correct result is PARTIAL, CONFLICT, NOT_FOUND, or SOURCE_UNAVAILABLE, not an invented answer.

## 9. Restart and Model-Swap Proof

For at least one high-value continuity test:

1. cold-start runtime
2. ask through the real interaction endpoint
3. capture retrieval receipt and ContextPacket
4. capture answer
5. restart runtime
6. repeat
7. if practical, swap the underlying local model
8. repeat

Prose may change. Provenance-bound factual continuity should not depend on model weights.

## 10. Storage Constraint

No file explosion.

Prefer:

- structured state -> SQLite
- dense event history -> database or compact append-only ledger
- original large artifacts -> stored once
- relationships/entity state -> database
- indexes -> database/index store
- ContextPackets -> ephemeral unless an audit receipt requires retention

One memory must never imply one new file.

## 11. UI Contract

The future Windows ORACLE application should use the same backend continuity path.

Normal interaction stays simple and text-first. Voice, files, images, code, agent messages, and system events are modalities into the same durable interaction/event system, not separate memory universes.

When useful, the UI may expose a `Why do you remember this?` view showing source, canon state, correction history, conflicts, and confidence. Engineering details remain hidden by default.

## 12. Required Engineering Discipline

Before implementation, identify the canonical branch/runtime path and current implementations of thread storage, retrieval, source resolution, Continuity Event Packets, Cognitive Spine, Self-State, and the real `/chat` or equivalent interaction route.

Do not import Drive-only candidate modules merely because their names match this design. Reconcile ideas against canonical repository code first.

Do not merge without Noah.Physical approval.

## Required Receipt

Return:

```text
CONTEXT_COMPILER =
ENTITY_RESOLUTION =
DEEPCUT_GATE =
SOURCE_PRIORITY =
THREAD_INDEPENDENCE =
REHYDRATION =
STORAGE_MODEL =
FILES_CHANGED =
TESTS =
AVALON_COLD_START =
ASHLEY_COLD_START =
DUAL_HEMISPHERIC_COLD_START =
RESTART_TEST =
MODEL_SWAP_TEST =
LIVE_ENDPOINT_TEST =
KNOWN_FAILURES =
NEXT_SMALLEST_BUILD =
```

## Final Law

**The model is allowed to forget. ORACLE is not.**

Remember before answering. Retrieve before reconstructing. Preserve the hole when evidence ends.
