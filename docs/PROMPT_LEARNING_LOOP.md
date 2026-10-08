# Prompt Learning Loop v0.1

Implements oracle-ai-core issue #8.

> Every prompt can teach. No prompt can rule until approved.

## Why this exists

Noah's principle is that AI should improve from every prompt. The naive reading of
that principle is dangerous: an assistant that updates its own behavior from
whatever you last said is not learning, it is drifting, and it drifts fastest when
you are tired or frustrated.

The correct reading separates observing from believing. Every prompt may produce a
learning **candidate**. No prompt becomes memory or behavioral doctrine without
Noah.Physical approval.

### The worked example

Noah's preference to avoid em dashes was written into issue #8 on 2026-06-08. On
2026-07-18 it was still being violated across an entire working session, because
nothing captured it as a durable candidate. The preference existed, was stated
clearly, and had no mechanism to survive.

That is the gap this module closes. Not intelligence. Retention.

## One loop, two producers

ORACLE has two things that produce governed candidates. They are deliberately not
two systems.

```
  reflection_candidates.py  ── her sandbox reflections ──┐
                                                          ├──> action_candidates
  prompt_learning_loop.py   ── Noah's prompts ───────────┘     (approval gate)
                    │
                    └── both share core/candidate_drift.py
                        (redaction, anti-amplification, similarity)
```

Sharing `candidate_drift` is load-bearing. If the two producers each carried their
own copy of the drift check, a fix to one would silently leave the other exposed.
A test asserts they are literally the same function object.

## What it does

| Step | Behavior |
|---|---|
| Classify | correction, preference, boundary_rule, operational_lesson, instruction, question, unknown |
| Band risk | boundary and sensitive material are high, corrections medium, preferences low |
| Redact | credential-shaped material is detected and the prompt is refused, not stored |
| Summarize | only a bounded, redacted summary is persisted, never the raw prompt |
| Group | repeated similar low-risk preferences increment `recurrence_count` |
| Preserve | uncertain classification stores UNKNOWN, listed in `unknowns` |

Repetition can raise `promotion_status` from `observed` to `hypothesis` and
confidence from low to medium. It can never reach `approved_meaning`. Only the
Approval Center, driven by Noah, does that.

## What it will never do

- Promote a candidate to memory or behavioral rule
- Store raw prompts, transcripts, emails, journals, or screen contents
- Store secrets; credential patterns are blocked before persistence
- Export anything to cloud
- Write while governance is in SAFE_SLEEP, unless explicitly overridden

`can_create_behavioral_rule()` returns False. That is structural, not a policy note.

## Anti-drift rules

- One prompt is never enough to create doctrine
- Corrections may guide the active session, but durable memory still requires approval
- Repeated low-risk preferences group into one candidate rather than multiplying
- High-risk claims require explicit human approval
- Private and personal claims are tagged sensitive
- When unsure, store UNKNOWN rather than a guess

## Persistence

```
Memory/prompt_learning_candidates.json
Memory/prompt_learning_events.jsonl   (append-only, local)
```

Both are local. Neither leaves the machine.

## CLI

```bash
python core/prompt_learning_loop.py --ingest "keep replies short and do not use em dashes"
python core/prompt_learning_loop.py --status
python core/prompt_learning_loop.py --smoke-test
```

`--smoke-test` runs the twelve checks from the spec against a temporary store and
never touches the live one.

## Test isolation warning

Any test that ingests a prompt or runs a self-prompt cycle will write real
candidates into `Memory/` unless isolated. `tests/conftest.py` redirects both
candidate stores to temp paths for every test.

**Every new candidate producer must be added to that fixture.** This failure is
silent: the suite passes green while quietly polluting durable memory and
surfacing fake items in Noah's approval queue. It has already happened once.

## Status

Candidate implementation. Not wired into Resident Runtime yet. The spec's stated
next step is integrating so every interaction can create governed candidates,
which should not happen until Noah has reviewed the classification quality on real
prompts rather than smoke-test fixtures.
