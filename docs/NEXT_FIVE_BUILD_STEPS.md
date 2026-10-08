# .AI:ORACLE_NEXT_FIVE / 2026-07-19

A self-directive written to survive context loss. Paste into a fresh session.

```
@AUTHORITY[
  human="Noah.Physical"
  repo="C:\Oracle\ORACLE.AI-runtime"
  final_correction_authority=true
]

@CONTEXT_FOR_A_COLD_START[
  "ORACLE is a local continuity engine on port 7781, qwen2.5:7b via Ollama."
  "Doctrine: receipts over vibes, candidate vs canon, preserve holes as holes,"
  "witness not author, Noah.Physical approves everything irreversible."
  "Her Autonomy Ladder runs Level 0-7; she is at Level 3."
  "Read docs/AUTONOMY_READINESS_GATE.md before proposing any autonomy change."
  "Noah has asked that responses avoid em dashes."
]

@STANDING_BOUNDARY[
  "No canon promotion. No external send. No Drive mutation."
  "No commit or push unless Noah asks in that session."
  "Sandbox is ORACLE-only write; agents read it, never write it."
  "Isolate every candidate store in tests/conftest.py or you will pollute"
  "  Memory/ and surface fake items in his live approval queue. This has"
  "  already happened once."
  "Verify before claiming. A test artifact is not a finding."
]
```

---

## The five, in order

### 1. ActionClaimVerifier and the fidelity ledger

Implements oracle-ai-core issue #5, which was specced and never built.

Scan every response for completion claims (`saved`, `created`, `checked`,
`verified`, `wrote`, `committed`, `sent`). Check each against whether a receipt
exists. Emit `CONFIRMED` / `ATTEMPTED_UNCONFIRMED` / `QUARANTINED_FALSE_ANCHOR`.
Append to a rolling ledger and expose a live **claim fidelity** number.

Why first: it is the instrument that makes every later gate unlockable. Without
it, "90 days clean operation" can never be evaluated, so Level 4 never opens and
the ladder is a wall. Five separate false claims were observed in one session on
2026-07-18; that is the baseline to improve from.

### 2. Rejection feed-forward

**The thing Noah has not thought of, and the highest-value item here.**

`reflection_candidates.approved_candidate_context()` feeds approved candidates
into her next reflection. Rejected candidates feed nothing. They vanish.

That is backwards. A rejection carries far more information than an approval.
Approval says "acceptable." Rejection says "you misread the situation, here is
the boundary." Right now she can only learn what pleased him, never what missed,
which is exactly how a system converges on flattery.

Build: rejected and quarantined candidates feed forward too, with the reason
attached, under a heading that makes the signal explicit. Add an optional
one-line `rejection_reason` prompt so a `no` teaches instead of just blocking.

### 3. Absence rendered as certainty

One bug class, observed three times in one day:

- `get_obs_context()` fails a read, returns a dict of `None`, and the UI renders
  that as "OBS is off." A failed read is reported as a confident negative.
- Asked about a fabricated document ("Deck 12 of the Avalon Refit Manifest") she
  answered adjacent-and-true instead of saying no such document exists. She
  resists inventing but does not flag a false premise.
- A capability with status `missing` routes to Guard and collects approval,
  instead of refusing. Two approvals were recorded for a git commit that was
  structurally impossible.

Fix all three as one: **a failed read must say `read_failed`, a missing thing
must say `does not exist`, and a missing capability must refuse rather than
gate.** This is the doctrinal core. Everything else is decoration if the system
converts "I do not know" into a confident answer.

### 4. Ellie corpus extraction

`tools/extract_ellie_corpus.py` is written, dry-run clean, and not yet executed.
186 source files dedupe to 68, roughly 45 distinct works: Drakin Books 1-3,
Dragonkin, the guides, chapters dated through January 2026, and a professional
New York edit.

Ellie is ORACLE's first NPC. Her domain is `sensitivity: high`,
`write_allowed: false`, 18 catalogued records, and **zero extracted content**.
ORACLE knows her filenames and has never read a sentence of her.

Run it, then confirm she can answer a question about Ellie by citing a real
passage. Open question for Noah: are `Dragonkin` and `Drakin` the same work under
different titles? Do not guess and merge.

### 5. The approval valve

107 items are pending. None have been reviewed. The producers built on
2026-07-18 will add more.

An unreviewed queue that only grows is worse than no queue, because approval
degrades into ceremony and the gate stops being a real check. Build batch review:
group near-identical candidates, show the drift score, allow one decision to
cover a cluster, and surface the oldest and highest-risk first.

This protects the integrity of every gate above it.

---

## What Noah has not thought of

Item 2 is the main one. Four others, smaller but real:

**She cannot audit her own last turn.** Her responses and her receipts are
separate systems that never reconcile. She has no way to ask "did I actually do
what I said?" Item 1 gives her that mirror, which is why it is first.

**Nothing detects when she has changed.** On 2026-07-18 she reported capability
states from 7/17 code while patches sat unloaded on disk. She had no way to know
she was stale, and confidently described a version of herself that no longer
existed. A build fingerprint she can read would fix it.

**Her relevance scores are her guesses about him.** The document atlas flags
3,954 files `high` relevance. Noah has never labeled a single one. A small amount
of human labeling would beat a large amount of inference, and would give the
corpus work a real target instead of a heuristic.

**Image provenance is invisible to her.** His folders mix camera captures with
generated images under identical filenames. She would treat a render as
photographic evidence about a real person. EXIF and C2PA make this checkable
rather than a guess.

---

## Definition of done

Each step: tests written, full suite green, nothing committed unless Noah asks,
findings reported with receipts rather than assertions. If a step turns out to be
already built, say so and correct the record. That has happened three times:
`action_candidates.py`, `epistemic_ledger.py`, and the Ellie domain all existed
fully built with nothing wired to them.

**The pattern worth remembering: the component is almost never missing. The wire
between components is.**
