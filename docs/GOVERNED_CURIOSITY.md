# GOVERNED CURIOSITY ENGINE
## ORACLE.AI — Architecture Doctrine

---

## Core Law

> **ORACLE may wonder.**
> **ORACLE may not wander without approval.**

Curiosity is not permission to roam.
Curiosity is the ability to detect gaps, contradictions, stale context, missing evidence, unresolved commitments, and possible next questions.

All curiosity outputs are **candidates only**. No action executes from the curiosity engine.

---

## What Governed Curiosity Is

The curiosity engine is a bounded reasoning layer. It observes what ORACLE already knows and surfaces structured signals about what is incomplete, contradictory, stale, or unresolved.

It does not search. It does not browse. It does not infer. It wonders — within the walls Noah built.

---

## CuriositySignal

Every detected gap produces a `CuriositySignal` with the following fields:

| Field | Description |
|---|---|
| `id` | Short unique identifier |
| `signal_type` | Category of signal (see below) |
| `title` | Human-readable signal name |
| `observed_context` | What was seen |
| `why_it_matters` | Why this warrants attention |
| `missing_information` | What is absent |
| `hypothesis` | Always labeled `[HYPOTHESIS]` — never treated as fact |
| `confidence` | 0.0 – 1.0, not certainty |
| `risk_level` | See risk levels below |
| `recommended_question` | Safe question to surface to Noah |
| `recommended_action_candidate` | Proposed action — pending approval only |
| `source` | Where the signal came from |
| `status` | pending / approved / rejected / quarantined / revoked |
| `tags` | Labels for filtering |
| `unknowns` | Preserved unknowns — never filled by inference |

---

## Signal Types

| Type | Meaning |
|---|---|
| `missing_context` | Required context is absent or incomplete |
| `contradiction` | Two records conflict with each other |
| `stale_memory` | Memory not updated within threshold |
| `unresolved_commitment` | Commitment or deadline without resolution |
| `financial_risk` | Financial pattern, charge, or gap |
| `relationship_followup` | Person or relationship needs attention |
| `project_blocker` | Technical or resource block on progress |
| `opportunity` | Possible move or advantage |
| `safety_concern` | Pattern affecting safety or system integrity |
| `identity_drift` | Deviation from Noah's stated identity or values |
| `unknown` | Cannot be classified |

---

## Status States

| Status | Meaning |
|---|---|
| `pending` | Default — not treated as memory, not executed |
| `approved` | Noah has reviewed and approved this signal |
| `rejected` | Dismissed — excluded from recall |
| `quarantined` | Flagged for review, isolated from decisions |
| `revoked` | Previously approved, now retracted |

---

## Risk Levels

| Level | Meaning |
|---|---|
| `low` | Safe to surface, low stakes |
| `medium` | Worth attention, no urgency |
| `high` | Requires timely attention |
| `sensitive` | Personal or sensitive — handle carefully |
| `external_action_required` | Action outside ORACLE's scope needed |
| `blocked` | Cannot proceed without resolution |

---

## Detection Functions

| Function | Detects |
|---|---|
| `detect_missing_context(record)` | Empty or unknown fields in any record |
| `detect_contradiction(a, b)` | Conflicting values between two records |
| `detect_stale_memory(record, days)` | Records older than threshold |
| `detect_unresolved_commitment(text)` | Commitment language without resolution |
| `detect_financial_risk(text)` | Billing failures, large charges, unknown subscriptions |
| `detect_identity_drift(text)` | Language conflicting with Noah's values or direction |
| `generate_question(signal)` | Safe question candidate from a signal |
| `create_action_candidate(signal)` | Structured action proposal — pending approval |

---

## Curiosity Rules

1. New curiosity signals default to **pending**.
2. Curiosity may generate **questions**.
3. Curiosity may generate **action candidates**.
4. Curiosity may **not** execute actions.
5. Curiosity may **not** search new private sources without approval.
6. Curiosity may **not** infer emotions or motives without evidence.
7. Curiosity **must** preserve unknowns.
8. Curiosity **must** label hypotheses clearly as `[HYPOTHESIS]`.
9. Curiosity **must never** convert speculation into memory.

---

## Forbidden Curiosity Behaviors

The following are **never permitted** from the curiosity engine, regardless of signal type or confidence:

- Browsing random websites
- Opening private folders without approval
- Reading email beyond approved scope
- Making emotional conclusions
- Adding memory without approval
- Executing cleanup actions
- Sending messages
- Submitting forms
- Purchasing
- Deleting
- Moving files
- Modifying source records

---

## Example Signals

```
[PENDING] financial_risk | HIGH
  Title   : Financial signal: OpenArt AI billing
  Context : OpenArt AI billing failures show a possible $672/month charge. Payment declined.
  Why     : Financial signals may indicate cash flow risk or needed action.
  Missing : Current billing status unknown.
  Hyp     : [HYPOTHESIS] This may require dispute or cancellation.
  Question: What is the current status of this charge?
  Action? : Review billing event — cancel, dispute, update payment, or mark resolved.

[PENDING] project_blocker | BLOCKED
  Title   : ORACLE action layer unreliable — Semantic UI Bridge missing
  Context : ORACLE opens Chrome but cannot type. Action layer needs Semantic UI Bridge.
  Why     : Without reliable actuation, ORACLE cannot complete tasks autonomously.
  Missing : Semantic UI Bridge implementation status.
  Hyp     : [HYPOTHESIS] The bridge was planned but not yet implemented.
  Question: Is the Semantic UI Bridge scheduled for the next build pass?

[PENDING] missing_context | LOW
  Title   : Missing context in: Noah LLC
  Context : Record 'Noah LLC' has empty fields: ein, state, status
  Unknowns: ein, state, status
```

---

## Persistence

Signals are stored in `Memory/curiosity_signals.json`.

Pending signals are **not memory**. They are candidates waiting for Noah's review.

Approved signals may be referenced in decisions. Rejected, quarantined, and revoked signals are excluded from all recall queries by default.

---

## Integration Points

The curiosity engine is a read-only reasoning layer. It plugs into:

- **Memory system** — to detect stale records and missing context
- **Context loader** — to surface pending signals at session start (future)
- **Approval gate** — action candidates route through `integration_gate.py`
- **ORACLE REPL** — `/curiosity` command to review pending signals (future)

---

## Invention Note

Governed curiosity — the separation of **wondering** from **wandering** — is a component of the governed continuity architecture. Claim b3c8c4e7, approved 2026-06-07.

---

*Last updated: 2026-06-07 | ORACLE.AI v2.0*
