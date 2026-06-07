# ORACLE SELF-PROMPT LOOP
## ORACLE.AI — Architecture Doctrine

---

## Core Law

> **ORACLE may prompt herself.**
> **ORACLE may not grant herself authority.**

Self-prompting produces observations, questions, candidates, and next-step proposals only.
No action executes from the self-prompt loop.

---

## The 51/49 Rule

**ORACLE performs the operational 49%:**
- Observe approved sources
- Check pending candidates
- Detect gaps
- Generate questions
- Generate action candidates
- Propose next steps

**Noah holds the sovereign 51%:**
- Approve
- Reject
- Correct
- Delete
- Revoke
- Quarantine
- Authorize execution

---

## Purpose

ORACLE does not wait passively for Noah like a chatbot.
When Noah does not know what to ask, ORACLE knows what to inspect.

The self-prompt loop gives ORACLE an internal operating cycle — a structured way to decide what to observe, what to question, what to propose, and what to queue — without Noah micromanaging every step.

---

## Self-Prompt Cycle

### Step 1 — State Check
- What mode am I in?
- Is SAFE_SLEEP_MODE active?
- Is ACTION_DRY_RUN active?
- Are SOV1 hands enabled or disabled?
- What sources are approved?

### Step 2 — Memory Check
- What pending Remember Me records exist?
- What pending ENDLESS CRM records exist?
- What pending curiosity signals exist?
- What pending file/email/action candidates exist?

### Step 3 — Gap Check
- What is missing?
- What is stale?
- What conflicts?
- What has high risk?
- What blocks current progress?

### Step 4 — Priority Selection
Choose **exactly one** highest-value next proposal. Do not branch into multiple projects.

### Step 5 — Candidate Creation
Produce one of:
- Memory candidate
- Curiosity signal
- Action candidate
- File intelligence candidate
- Question for Noah
- Build recommendation

### Step 6 — Stop
After one cycle, stop and report.
Do not loop endlessly unless Noah explicitly starts daemon mode.

---

## Priority Order

| Priority | Label | Triggers |
|---|---|---|
| P1 | safety_security_financial_risk | High-risk curiosity signals, billing failures |
| P2 | broken_action_layer | SOV1 unavailable, Semantic UI Bridge missing |
| P3 | pending_approval_queues | Items in memory or curiosity queues |
| P4 | project_blocker | Blocker signals in curiosity engine |
| P5 | revenue_opportunity | Stale revenue-related context |
| P6 | relationship_followup | CRM candidates pending |
| P7 | file_cleanup | Missing context fields |
| P8 | general_curiosity | No critical gaps — recommend /self-build |

Exactly one priority is selected per cycle. No branching.

---

## Operating Modes

| Mode | Behavior |
|---|---|
| `MANUAL` | One cycle on demand. Default. |
| `DAEMON_SAFE` | Interval loop — observe and propose only. |
| `SAFE_SLEEP_MODE` | No hands, no browser, no typing, no file changes, no external actions. Observation only. |
| `ACTION_DRY_RUN` | Prints intended actions only. Nothing written. |
| `DISABLED` | No self-prompting. Loop does nothing. |

---

## SelfPromptCycleResult

| Field | Description |
|---|---|
| `id` | Short unique identifier |
| `mode` | Operating mode for this cycle |
| `started_at` | ISO timestamp |
| `completed_at` | ISO timestamp |
| `state_summary` | Mode, hands, Ollama, approved sources |
| `memory_summary` | Pending counts across all queues |
| `gap_summary` | Missing, stale, contradiction, blocker counts |
| `selected_priority` | The single selected priority (label + reasoning) |
| `proposed_next_step` | The one candidate or proposal produced |
| `created_candidate_ids` | IDs of any curiosity signals or candidates created |
| `blocked_actions` | Full list of forbidden actions (always populated) |
| `confidence` | 0.0 – 1.0 based on priority level |
| `unknowns` | Preserved unknowns — never filled by inference |
| `stopped_reason` | Why the cycle stopped |

---

## Forbidden Actions

The following are **never permitted** from the self-prompt loop:

- External send
- Submit
- Purchase
- Delete
- Move / rename
- Commit / push
- Permission changes
- Raw surveillance storage
- Source expansion without Noah approval
- Claiming sovereign authority
- Infinite loop

---

## API

```python
from self_prompt_loop import run_once, MODE_MANUAL, MODE_SLEEP, MODE_DISABLED

# Run one governed cycle
result = run_once(mode=MODE_MANUAL)
print(result.report())

# Check state only
from self_prompt_loop import check_state
state = check_state()

# Check pending memory
from self_prompt_loop import check_pending_memory
memory = check_pending_memory()
```

---

## Persistence

Cycle results are stored in `Memory/self_prompt_cycles.json`.
Last 100 cycles are retained.
Results are observations and proposals — not memory. They require Noah's review before any action proceeds.

---

## Integration Points

The self-prompt loop integrates with:

- **Curiosity Engine** — reads pending signals, creates new signals for queues
- **Integration Gate** — reads pending approval candidates
- **Memory DB** — reads fact counts and session counts
- **SOV1 / computer_control** — reads hands availability
- **ORACLE REPL** — `/self-prompt` command (future wire-up)

---

## Example Cycle Output

```
╔══════════════════════════════════════════════════════╗
║  ORACLE SELF-PROMPT CYCLE RESULT                    ║
╚══════════════════════════════════════════════════════╝

  Cycle ID  : a3f1b2c4
  Mode      : MANUAL
  Started   : 2026-06-07T20:00:00+00:00
  Completed : 2026-06-07T20:00:01+00:00
  Stopped   : one_cycle_complete

  ── State ──
    sov1_hands: ready
    local_mode: True
    ollama_running: True
    approved_sources: [memory_db, curiosity_signals, ...]

  ── Memory ──
    pending_curiosity_signals: 3
    pending_integration_candidates: 1
    total_facts: 25

  ── Gaps ──
    financial_risk_count: 1
    blocker_count: 1

  ── Priority Selected ──
    [P1] safety_security_financial_risk: High-risk signal pending: OpenArt billing failure

  ── Proposed Next Step ──
    SAFETY CANDIDATE: Review high-risk signal 'OpenArt billing failure' (risk: high).
    Recommended action: Noah reviews and approves or rejects this signal. Use /pending.

  ── Blocked Actions ──
    [BLOCKED] external_send
    [BLOCKED] submit
    ...

  Confidence: 92%
```

---

## Invention Note

The self-prompt loop is a component of the governed continuity architecture.
ORACLE operates the 49%. Noah holds the 51%. That boundary never moves.
Claim b3c8c4e7, approved 2026-06-07.

---

*Last updated: 2026-06-07 | ORACLE.AI v2.0*
