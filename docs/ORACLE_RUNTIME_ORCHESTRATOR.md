# ORACLE Runtime Orchestrator
## ORACLE.AI — Architecture Doctrine

---

## The Problem This Solves

Before this module, ORACLE sat in PowerShell waiting for Noah to type the next instruction.
She had memory, curiosity, self-prompt logic, and SOV1 hands — but no heartbeat.

This is the heartbeat.

---

## Core Law

> **ORACLE may run cycles.**
> **ORACLE may not grant herself authority.**
> **ORACLE may propose, classify, compress, and queue.**
> **ORACLE may not execute external or destructive actions without Noah approval.**

---

## One Cycle = One Priority = One Module = One Result

The orchestrator does not sprawl. It does not open ten projects.
It wakes, selects exactly one priority, invokes exactly one module, saves the result, and stops.

---

## Runtime Cycle

### 1 — Wake
- Load config from `.env`
- Detect mode: MANUAL, DAEMON_SAFE, SAFE_SLEEP_MODE, ACTION_DRY_RUN, DISABLED
- Connect to available modules

### 2 — State Check
- SOV1 hands available?
- Ollama running?
- Local mode or cloud mode?
- Approved sources

### 3 — Memory Check
- Pending curiosity signals
- Pending integration candidates
- Total facts in memory DB
- Pending relationship records

### 4 — Gap Check
- Financial risk signals
- Blocker signals
- Stale memory
- Contradictions

### 5 — Priority Selection
One priority is selected per cycle. No branching.

| Priority | Label | Trigger |
|---|---|---|
| P1 | `safety_security_financial_risk` | High-risk curiosity signal pending |
| P2 | `broken_action_layer` | SOV1 unavailable / Semantic UI Bridge missing |
| P3 | `pending_approval_queues` | Items in memory or curiosity queues |
| P4 | `project_blocker` | Unresolved commitment flagged as blocker |
| P5 | `revenue_opportunity` | Stale revenue-related context |
| P6 | `relationship_followup` | CRM candidates pending |
| P7 | `file_cleanup` | Thin memory database |
| P8 | `curiosity_signals` | Pending curiosity signals |
| P9 | `general_maintenance` | No urgent priorities — recommend /self-build |

### 6 — Invoke Module
Based on selected priority, one module is called:
- `curiosity_engine` — for P1, P4, P8
- `integration_gate` — for P3
- `relationship_memory` — for P6
- `live_context` — for P5
- `self_prompt_loop` — for P9
- None — for DISABLED or SAFE_SLEEP

### 7 — Persist Result
`Memory/runtime_cycles.json` — last 100 cycles retained.

### 8 — Report
Every cycle produces a full report:
- Selected priority and why
- Module invoked
- Action taken (or not taken)
- What requires approval
- Blocked actions (always populated)
- Next recommended step
- Confidence score

### 9 — Stop
- `MANUAL` mode: run one cycle, stop.
- `DAEMON_SAFE` mode: run interval cycles, propose only.
- `SAFE_SLEEP_MODE`: observe/propose only. No hands, no browser, no file changes.
- `DISABLED`: do nothing.

---

## RuntimeCycleResult

| Field | Description |
|---|---|
| `id` | Short unique identifier |
| `mode` | Operating mode for this cycle |
| `started_at` | ISO timestamp |
| `completed_at` | ISO timestamp |
| `selected_priority` | The single selected priority label |
| `selected_module` | Which module was invoked |
| `action_taken` | What was done |
| `candidates_created` | IDs or titles of candidates generated |
| `approval_required` | True if Noah review is needed |
| `approval_reason` | Why approval is needed |
| `blocked_actions` | Full list of forbidden actions (always populated) |
| `confidence` | 0.0 – 1.0 |
| `unknowns` | Preserved unknowns — never filled by inference |
| `next_recommended_step` | Exact next command or action for Noah |
| `stopped_reason` | Why the cycle stopped |

---

## Forbidden Actions

The following are **never permitted** from the runtime orchestrator:

- External send
- Submit
- Purchase
- Delete
- Move / rename files
- Commit / push code
- Permission changes
- Raw surveillance storage
- New source expansion without Noah approval
- Claiming sovereign authority
- Infinite loop

---

## CLI Usage

```bash
python core/oracle_runtime.py --cycle        # Run one manual cycle
python core/oracle_runtime.py --status       # Show state without running
python core/oracle_runtime.py --safe-sleep   # Propose-only cycle
python core/oracle_runtime.py --smoke        # Run smoke tests
```

## REPL Commands

```
/runtime           Run one governed runtime cycle
/runtime-status    Show current state and next priority
/cycle             Alias — same as /self-prompt (runs self-prompt loop)
```

---

## Integration Points

- `curiosity_engine.py` — reads pending signals, generates questions
- `integration_gate.py` — reads pending approval candidates
- `memory.py` — reads fact counts
- `relationship_memory.py` — reads contact records
- `self_prompt_loop.py` — called for P9 maintenance cycles
- `oracle.py` REPL — `/runtime` command

---

## Persistence

Cycles are stored in `Memory/runtime_cycles.json`.
Last 100 cycles retained.
Results are observations and proposals — not memory.
Noah reviews before any action proceeds.

---

## What This Changes

Before: ORACLE waits for Noah.
After: ORACLE wakes, checks state, picks work, proposes, stops.

She still needs Noah's 51% to act. But she no longer needs him to know what to ask.

---

*Last updated: 2026-06-07 | ORACLE.AI*
