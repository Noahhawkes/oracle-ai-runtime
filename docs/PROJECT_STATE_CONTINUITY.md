# ORACLE Project State Continuity
## ORACLE.AI — Cross-Session Goal Memory

---

## The Problem This Solves

ORACLE remembers facts. She does not remember what she was doing.

After every restart, Noah had to re-explain:
- What was being built
- What failed last time
- What was blocked
- What to do next

This module fixes that.

---

## Core Law

> **Do not invent progress.**
> **Do not mark done unless verified by test, commit, or user confirmation.**
> **Preserve blockers. Preserve unknowns. Preserve failures.**
> **One active project at a time.**

---

## ProjectState Fields

| Field | Description |
|---|---|
| `id` | Unique state ID |
| `project_name` | e.g. `ORACLE.AI` |
| `current_goal` | What we are trying to build |
| `current_phase` | Which phase of the build |
| `last_completed_step` | Last verified step |
| `last_completed_evidence` | Commit hash, test count, or "user confirmed" |
| `current_blocker` | What is blocking progress right now |
| `blocker_evidence` | Concrete proof of the blocker |
| `next_recommended_step` | Exactly what to do next |
| `next_step_reason` | Why that step and not another |
| `active_files` | Files relevant to current work |
| `relevant_commits` | Recent commits in scope |
| `pending_candidates` | Items waiting for approval |
| `failed_attempts` | Every failure recorded — never deleted |
| `lessons_learned` | What was learned from failures |
| `open_questions` | Questions requiring Noah's answer |
| `approval_required` | True when Noah must decide something |
| `approval_reason` | What decision is needed |
| `updated_at` | ISO timestamp |
| `confidence` | 0.0 – 1.0 (decreases with blockers and failures) |
| `unknowns` | Preserved unknowns — never inferred |

---

## API

```python
from project_state import (
    load_state, save_state, get_or_create,
    update_goal, record_completed_step, record_blocker,
    record_failed_attempt, set_next_step,
    add_lesson, add_open_question, add_unknown,
    clear_blocker, summarize_state, resume_prompt,
    list_projects,
)

# Load state
state = load_state("ORACLE.AI")

# Update goal
update_goal("ORACLE.AI", "Build Semantic UI Bridge")

# Record a verified completed step
record_completed_step(
    "ORACLE.AI",
    "Built project_state.py",
    evidence="commit abc1234 — 41/41 smoke tests"
)

# Record a blocker
record_blocker(
    "ORACLE.AI",
    "qwen2.5:7b cannot reliably execute multi-step computer use",
    evidence="Live test: model hallucinated success, nothing happened on screen"
)

# Record a failure
record_failed_attempt(
    "ORACLE.AI",
    "Desktop computer use via local 7b model",
    "Model hallucinates success without verifying screen state",
    evidence="focus_window x3, type_text into wrong window"
)

# Set next step
set_next_step(
    "ORACLE.AI",
    "Build core/semantic_ui_bridge.py",
    reason="Deterministic UIAutomation targeting removes model judgment from input field location"
)

# Get resume prompt
print(resume_prompt("ORACLE.AI"))
```

---

## Resume Prompt

The resume prompt is what ORACLE speaks at startup instead of waiting for Noah to re-explain.

```
Project: ORACLE.AI
Phase  : governed local system build
Goal   : Build a governed local AI operating system...

Last verified step:
  Notepad fallback fix and targeted input guard committed
  Evidence: commit 6e56ffa — 30/30 smoke tests, 8/8 sov1 smoke tests

Current blocker:
  qwen2.5:7b is unreliable for desktop computer use...
  Evidence: Live test showed hallucinated success

Next step:
  Build core/semantic_ui_bridge.py
  Why: Deterministic UIAutomation targeting removes model judgment...

Preserved unknowns:
  [UNKNOWN] Whether pywinauto can reliably find ChatGPT input in Chrome
  ...

Confidence: 72%
```

---

## REPL Commands

```
/project-state    Show current project state — what was active, blocked, next
/resume           Alias for /project-state
/where-was-i      Alias for /project-state
```

---

## CLI

```bash
python core/project_state.py --smoke       Run smoke tests (41/41)
python core/project_state.py --seed        Seed ORACLE.AI current state
python core/project_state.py --resume      Print ORACLE.AI resume prompt
python core/project_state.py --status      List all project states
```

---

## Startup Integration

At ORACLE boot, the banner now shows:

```
◆ RESUMING  governed local system build
  Next: Build core/semantic_ui_bridge.py
  Blocker: qwen2.5:7b unreliable for desktop computer use
```

This replaces the "re-explain everything" problem with a live state snapshot.

---

## Persistence

`Memory/project_states.json` — one entry per project name. No limit on stored state size. Failures are never deleted.

---

## Current ORACLE.AI State (seeded 2026-06-07)

**Phase:** governed local system build
**Last verified:** Notepad fallback fix (commit 6e56ffa, 30/30 tests)
**Blocker:** qwen2.5:7b cannot reliably do multi-step desktop control
**Next:** Build `core/semantic_ui_bridge.py`

**What's done:**
- Remember Me live
- ENDLESS CRM live
- Autonomy Readiness Gate locked
- Governed Curiosity Engine (25/25 tests)
- Self-Prompt Loop (27/27 tests)
- Extended Action Batches (30/30 tests)
- Runtime Orchestrator (25/25 tests)
- Window Janitor (20/20 tests)
- ChatGPT Bridge (23/23 tests)
- Notepad fix + targeted input guard (30/30 tests)
- Project State Continuity (41/41 tests)

**What's next:**
1. `core/semantic_ui_bridge.py` — deterministic Windows UI element targeting
2. `core/action_candidates.py` — structured work queue
3. Scheduler/daemon for timed safe cycles

---

## 2026-08-16 — Durable research update (continuity restore)

Merged from Captain's Log `docs/captains_logs/2026-08-16_continuity-restore-oracle-gateway-and-recall.md`.

**Newly built / durable this session:**
- `agent_gateway.py` — read-only, bearer-gated ORACLE → agent gateway (6 endpoints, provenance envelope, reuses existing ORACLE functions, ORACLE stays localhost). 16 tests pass; proven live. Not exposed externally.
- Self-prompt loop upgraded (staged) to read one approved, bounded, receipted corpus excerpt per cycle using the `OBSERVED / INTERPRETED / UNKNOWN / CONTRADICTION / NEXT_SOURCE_QUESTION` schema, with duplicate-family suppression and a topic-level privacy filter.
- Governance distinction established: **recall vs representation** — full recall over Noah.Self for reasoning; public representation limited to Noah.Public.

**Correction (preserved):** the 930-document corpus was believed unreachable by recall; live probes show it **is** reachable via `file_recall` / `document_atlas`. The real gap is find → read (locates the file, does not read its contents into the answer).

**Open next steps:** relight to activate the staged self-prompt patch; implement the find → read last hop; build the canon-only public projection endpoint before any external exposure.

---

*Last updated: 2026-08-16 | ORACLE.AI — prior: 2026-06-07*
