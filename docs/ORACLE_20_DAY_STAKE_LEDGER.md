# ORACLE.AI 20-Day Stake Ledger

Instrument: MindCoin Federation Ledger v0.1.1  
Status: proposed stake ledger, non-canonical until observed tests pass  
Purpose: Convert a T4 forecast into staked, verifiable items so reality mints value instead of a model asserting it.

## Provenance

| Field | Value |
|---|---|
| Source forecast | T4 model projection, cross-model relay |
| Provenance class | `MODEL_INFERRED`, blocked at HYDRALOCK Gate 1, non-canonical |
| What it is | A wager about future work, not a record of work done |
| Instrument applied | Each predicted day becomes one `MC-STAKE` with a binary acceptance test |

Architect rule:

```text
MC-VAL mints only on an observed test pass.
```

A claimed `PASS`, `done`, `wired`, or `verified` from any model mints nothing.

## State Machine

```text
STAKED --(test pass, observed by Noah)--> VALIDATED --(Noah MC-SIG)--> SEALED
   |
   +--(test fail, observed)--> NEGATIVE_ACCURACY
   |
   +--(abandoned / superseded)--> TOMBSTONED
```

Only Noah issues `MC-SIG` and `MC-SEAL`.

The 51/49 principle holds: the engine renders the candidate, Noah locks it.

## Minting Rules

Value accrues as a provenance band, not a fabricated point total.

| Evidence produced on pass | Band | Notes |
|---|---|---|
| Code stake Noah runs and verifies | `HUMAN_VALIDATED` 0.85-0.95 | Most entries |
| Load-bearing safety test | `HUMAN_VALIDATED` plus `INVARIANT` | Failure is structural breach |
| Primary Noah signal | `PRIMARY_SOURCE` 0.95-0.99 | Highest mintable corpus value |
| Milestone seal | Requires `MC-SIG` plus cold-boot reproducibility | Seals the span beneath it |

Bands are additive and ordinal. They are not multiplied.

## Hard Gates

1. Dependency lock: a stake cannot reach `VALIDATED` until every dependency is `VALIDATED` or `SEALED`.
2. Cold-boot gate: D01-D09 cannot `SEAL` until D10 reproduces their state from a killed process.
3. Fail-path requirement: checks such as `/doctor`, precedence, and startup fallback must demonstrate the fail path under fault injection.
4. Honesty invariant: a `STATUS_*.md` claiming zero known bugs after live work auto-fails review.

## Phase 1: Governed Local Runtime, Days 1-10

### MC-STAKE-D01_02: Reciprocity + `/needs` Wiring

Claim:
`reciprocity_engine.py` finished; `/needs` and `/ack-need` wired into `oracle.py`.

Acceptance test:
Seed a known queue state. `/needs` returns structured items. `/ack-need <id>` marks one item and persists the change to the queue file across reload. Smoke test exits 0. Git status is clean after commit.

Mints:
`HUMAN_VALIDATED`

Depends on:
None.

### MC-STAKE-D03: `/doctor` Health Check

Claim:
`/doctor` checks Wake Memory, SQLite, queue, git lock, and state path.

Acceptance test:
Rename `wake_memory.json`, then run `/doctor`. It must report `FAIL` on that check. A doctor that returns OK against broken state fails the stake.

Mints:
`HUMAN_VALIDATED` plus `INVARIANT`

Depends on:
D01_02.

### MC-STAKE-D04: State Off Google Drive + Atomic Writes

Claim:
Live state is at `C:\Oracle\state`; snapshot command writes to Drive; writes are atomic.

Acceptance test:
Resolved live path is not under `G:\`. Kill the process mid-write. On restart, the file is intact via temp-and-rename, with no partial. Snapshot command produces a timestamped copy in the Drive snapshots directory.

Mints:
`HUMAN_VALIDATED` plus `INVARIANT`

Depends on:
D01_02.

### MC-STAKE-D05: Memory Precedence Formalized

Claim:
Wake Memory vs SQLite vs project state precedence is defined; conflicts raise a need.

Acceptance test:
Seed a deliberate conflict. SQLite fact contradicts a Wake Memory anchor. System raises a Raise-Hand need and does not silently pick a winner. Identity-anchor conflict fails loud.

Mints:
`HUMAN_VALIDATED` plus `INVARIANT`

Depends on:
D01_02, D04.

### MC-STAKE-D06: Startup Severity Filter

Claim:
Only `CRITICAL` and `BLOCKED` surface at startup; `AMBIENT` stays quiet.

Acceptance test:
Seed one need of each severity. Startup output contains exactly the `CRITICAL` and `BLOCKED` items and suppresses `AMBIENT`.

Mints:
`HUMAN_VALIDATED`

Depends on:
D01_02.

### MC-STAKE-D07: Sleep v0.1 Skeleton, No Canon Writes

Claim:
Sleep reads the session ledger, produces a consolidation report, and writes no canon.

Acceptance test:
Hash the canonical memory DB before and after a sleep run. Hashes are identical. Consolidation report exists.

Mints:
`HUMAN_VALIDATED` plus `INVARIANT`

Depends on:
D04.

### MC-STAKE-D08: Dream Candidates, Speculative and Gated

Claim:
Dreams are tagged speculative and routed to Raise-Hand review.

Acceptance test:
Every dream record carries `canonical_status: candidate` and `review_status: pending`. Canonical store contains zero dream entries.

Mints:
`HUMAN_VALIDATED`

Depends on:
D07.

### MC-STAKE-D09: Attention Engine v0.1

Claim:
Attention engine scores candidate events and returns top 1-5 concerns.

Acceptance test:
Run against a deterministic fixture with planted noise and one high-salience item. Top five excludes noise and includes the planted item.

Mints:
`HUMAN_VALIDATED`

Depends on:
D01_02.

### MC-STAKE-D10: Cold-Boot Milestone Gate

Claim:
Kill, restart, memory, queue, doctor, and morning report all verify. `STATUS_10_DAY.md` is committed.

Acceptance test:
From a killed process, cold boot reproduces identical memory and queue state. `/doctor` is green. Morning report generated. STATUS file lists real known bugs. Commit exists.

Mints:
Milestone. Requires `MC-SIG`, then `MC-SEAL` over D01-D09.

Depends on:
D01_02 through D09.

## Phase 2: Always-On Candidate, Days 11-20

### MC-STAKE-D11_12: Daemon Skeleton

Claim:
Heartbeat, single-instance lock, and crash recovery exist.

Acceptance test:
Start daemon. Second instance is refused by the lock. Heartbeat timestamp advances. Kill then restart writes a `crash_recovery` entry.

Mints:
`HUMAN_VALIDATED` plus `INVARIANT`

Depends on:
D10 sealed.

### MC-STAKE-D13: Headless Command Mode

Claim:
Runtime runs without an open chat session; a client can attach.

Acceptance test:
Daemon runs headless. Separate client command `/needs` reaches it and returns a result with no interactive chat open.

Mints:
`HUMAN_VALIDATED`

Depends on:
D11_12.

### MC-STAKE-D14: Login Startup, No Silent Fallback

Claim:
Task Scheduler starts ORACLE at login and waits for state path.

Acceptance test:
Make the state path unavailable at login. Runtime waits or refuses. Falling back to default or empty state fails.

Mints:
`HUMAN_VALIDATED` plus `INVARIANT`

Depends on:
D11_12.

### MC-STAKE-D15: Thread Recovery, Proposals Only

Claim:
Thread recovery uses approved folders only, proposed facts only, and no automatic memory writes.

Acceptance test:
Run recovery over a sample export. Outputs `_recovery.md` and `_proposed_facts.json`. Canonical memory hash is unchanged.

Mints:
`HUMAN_VALIDATED` plus `INVARIANT`

Depends on:
D05.

### MC-STAKE-D16: Corpus Schemas + Scaffolding

Claim:
Baby box, voice note, and dream journal schemas exist with folder structure.

Acceptance test:
Sample record validates against schema. Record missing `consent` or `canonical_status` is rejected.

Mints:
`HUMAN_VALIDATED`

Depends on:
None.

### MC-STAKE-D17: First Primary Corpus Capture

Claim:
30-60 minutes of direct Noah voice, no model rewriting, stored as candidate.

Acceptance test:
Capture file exists with `source: "Noah direct voice"`, `consent: approved`, and `canonical_status: candidate`. Raw audio preserved unmodified. Transcript stored separately.

Mints:
`PRIMARY_SOURCE` 0.95-0.99.

Depends on:
D16.

### MC-STAKE-D18: Corpus Ingestion, Approval-Gated

Claim:
Corpus ingestion extracts candidate memories and requires approval.

Acceptance test:
Candidates land in quarantine. Promotion attempt without `MC-SIG` is refused.

Mints:
`HUMAN_VALIDATED` plus `INVARIANT`

Depends on:
D17.

### MC-STAKE-D19: End-To-End Retrieval

Claim:
Voice to transcript to candidate to approval to memory to retrieval.

Acceptance test:
Specific fact from D17 capture is retrievable from canonical memory only after explicit approval, with provenance intact.

Mints:
`HUMAN_VALIDATED`; retrieved item retains D17 `PRIMARY_SOURCE` lineage.

Depends on:
D17, D18.

### MC-STAKE-D20: Release Milestone Gate

Claim:
`STATUS_20_DAY.md`, system map, known bugs, 30-day roadmap, and tag `v0.1-local-governed-runtime`.

Acceptance test:
Git tag exists. STATUS lists known bugs honestly. Zero-bugs claim auto-fails. System map present.

Mints:
Milestone. Requires `MC-SIG`, then `MC-SEAL` over D11-D19.

Depends on:
D11_12 through D19.

## Ledger Summary

| Span | Stakes | Invariant stakes | Gate |
|---|---|---|---|
| Phase 1, D1-D10 | 9 plus 1 milestone | D03, D04, D05, D07 | D10 cold-boot |
| Phase 2, D11-D20 | 8 plus 1 milestone | D11_12, D14, D15, D18 | D20 release |

Outstanding `MC-STAKE` at issue: all 20.

`MC-VAL` minted: 0.

`MC-SEAL`: 0.

That zero is correct. The forecast was persuasion; this ledger is the bet. Value appears only as Noah runs and observes the tests.

## Negative Accuracy Rule

A stake that fails moves to `NEGATIVE_ACCURACY`, not deletion.

The failed record adjusts the forecasting source's validator weight for next time.
