# ORACLE Runtime Continuity Loop

**Status:** Minimum viable end-to-end loop implemented and tested.
**Date:** 2026-06-13

---

## Modules That Participate

| Module | Role | Status |
|---|---|---|
| `core/continuity_pipeline.py` | Orchestrator — wires all steps together | NEW (this PR) |
| `core/memory.py` | SQLite persistence — `durable_facts` + `audit_chain` tables | EXTENDED |
| `core/light_compression.py` | Salience scoring via `score_signal()` | EXISTING, wired in |
| `core/governance.py` | Policy gate via `is_approval_required()` | EXISTING, wired in |
| `tests/test_continuity_loop.py` | End-to-end integration test | NEW |

---

## Actual Call Path

```
run_continuity_pipeline(session)
  |
  ├─ 1. memory.init_db()
  |       Creates tables if absent (sessions, facts, durable_facts, audit_chain)
  |
  ├─ 2. memory.append_audit_chain(session_id, "session_received")
  |
  ├─ 3. continuity_pipeline.extract_candidates(session)
  |       For each message:
  |         classify_source_type() → "human_stated" | "inferred" | "generated"
  |         light_compression.score_signal() → salience score
  |         human_stated + >5 words → always a candidate (override)
  |         score < 0.30 AND not human_stated_override → discarded
  |
  ├─ 4. memory.append_audit_chain(session_id, "candidate_extracted")
  |
  ├─ For each non-discarded candidate:
  |   ├─ 5. continuity_pipeline.assign_provenance()
  |   |       human_stated  → canonical_status="accepted", approval_status="auto_approved"
  |   |       inferred      → canonical_status="staged",   approval_status="pending"
  |   |       generated     → canonical_status="staged",   approval_status="pending"
  |   |       Provenance fields: source_type, source_id, observed_at, confidence,
  |   |                          transformation_history, canonical_status, approval_status
  |   |
  |   ├─ 6. memory.append_audit_chain(session_id, "provenance_assigned")
  |   |
  |   ├─ 7. continuity_pipeline.evaluate_policy()
  |   |       governance.is_approval_required() consulted
  |   |       inferred/generated → write_allowed=True but staged/pending (never canonical)
  |   |       human_stated       → write_allowed=True, auto_approved
  |   |
  |   └─ 8. continuity_pipeline.write_durable_memory()
  |           Validates provenance (raises if fields missing)
  |           memory.insert_durable_fact() → SQLite INSERT
  |           memory.append_audit_chain(session_id, "memory_written")
  |
  └─ 9. memory.append_audit_chain(session_id, "pipeline_complete")

ContinuityRuntime.wake_memory_search(query)
  └─ memory.search_durable_facts(query) → LIKE search → rows ordered by id DESC
       Prefers canonical_status="accepted" rows
```

---

## Provenance Contract

Every durable memory candidate must carry:

```python
{
    "source_type":            str,   # "human_stated" | "inferred" | "observed" | "generated"
    "source_id":              str,   # session id
    "observed_at":            str,   # ISO timestamp
    "confidence":             float, # 0.0–1.0
    "transformation_history": list,  # ordered list of processing steps
    "canonical_status":       str,   # "accepted" | "staged" | "rejected"
    "approval_status":        str,   # "auto_approved" | "pending" | "denied"
}
```

**Rules enforced in code:**
- Missing provenance fields → `ValueError` raised, write does not proceed
- `inferred` source_type → `canonical_status` is always `"staged"` and `approval_status` is always `"pending"`, regardless of governance setting
- Every durable write (success or blocked) produces an `audit_chain` record

---

## Dormant / Bypassed Modules

The following modules exist and are complete but are NOT wired into this loop:

| Module | What it does | Why it's dormant |
|---|---|---|
| `core/epistemic_ledger.py` | Full claim ledger with versioned approval tokens, evidence receipts, contradiction tracking | Designed for deep human-approval workflow; not wired to automatic session processing |
| `core/session_reflection.py` | LLM-powered session reflection generator | Manual-only (`/reflect` command); no session-end hook in oracle.py |
| `core/meaning_engine.py` | OBS recording → memory candidate watcher | OBS-specific; not general conversation memory |
| `core/wake_memory.py` | Human-readable summary injected at startup | Not a searchable store; contains summary text only |
| `core/salience_filter.py` | Signal pool with multi-axis scoring | Exists standalone; `light_compression.score_signal()` used instead for simplicity |
| `core/cognitive_salience.py` | (If present) additional salience layer | Not wired |
| `core/audit_log.py` | Flat-file audit log (per-day .log files) | Still works for existing callers; new structured `audit_chain` table added to memory.py |

The largest gap that still exists in production (`oracle.py`): **session end only calls `log("SESSION_END")` and exits.** The `run_continuity_pipeline()` function is not yet called from the oracle.py REPL exit path. That wiring is the next step.

---

## Test Output

```
Original statement : My preferred dealer visit cadence is Tuesday through Thursday.
Classification     : human_stated
Canonical status   : accepted
Approval status    : auto_approved
Confidence         : 0.675
Transformation history: source_classification -> salience_scoring ->
                        human_stated_override -> provenance_assigned ->
                        policy_evaluated -> memory_written

Audit chain:
  session_received -> candidate_extracted -> provenance_assigned -> memory_written -> pipeline_complete

Fresh-restart recall:
  fact_text   : My preferred dealer visit cadence is Tuesday through Thursday.
  source_type : human_stated
  canonical   : accepted
```

---

## Files Changed

| File | Change |
|---|---|
| `core/memory.py` | Added `durable_facts` table, `audit_chain` table, `insert_durable_fact()`, `search_durable_facts()`, `append_audit_chain()`, `get_audit_chain()`, `_validate_provenance()` |
| `core/continuity_pipeline.py` | NEW: full pipeline orchestrator |
| `tests/test_continuity_loop.py` | NEW: 8-assertion integration test |
| `docs/RUNTIME_CONTINUITY_LOOP.md` | NEW: this document |
