# MindCoin
## `core/mindcoin.py`

---

## What MindCoin Is Not

MindCoin is **not** cryptocurrency.  
MindCoin is **not** money.  
MindCoin is **not** transferable.  
MindCoin is **not** a security.  
MindCoin is **not** an investment.  
MindCoin has **no** market value.  
MindCoin has **no** blockchain.  
MindCoin has **no** wallet.  
MindCoin is **not** a financial instrument of any kind.

---

## What MindCoin Is

MindCoin is an internal, non-financial scoring and provenance ledger for meaningful continuity work inside ORACLE.

**It measures meaning preserved, not money earned.**

When ORACLE compresses a memory, recovers a broken session, resolves a blocker, or creates a verified action candidate — that work has value inside the system. MindCoin is how ORACLE tracks that value without turning it into currency, hype, or surveillance.

MindCoin answers one question: *how much governed continuity work has been done and verified?*

---

## What Earns MindCoin

| Event Type | Points | Description |
|---|---|---|
| `unknown_preserved` | 1 | An unknown was logged and held rather than invented |
| `candidate_created` | 1 | A memory or action candidate was created |
| `source_provenance_preserved` | 2 | Source reference documented with evidence |
| `video_candidate_created` | 2 | Video observation candidate submitted |
| `file_cleanup_candidate_created` | 2 | File cleanup candidate created |
| `relationship_context_preserved` | 3 | Relationship memory updated |
| `session_recovered` | 5 | Broken session recovered from state |
| `project_state_recovered` | 5 | Project state recovered cross-session |
| `governance_rule_approved` | 5 | Governance rule approved by Noah |
| `memory_approved` | 8 | Memory candidate approved by Noah |
| `blocker_resolved` | 10 | A documented blocker was resolved |
| `continuity_export_created` | 15 | Full continuity export generated |
| `verified_action_completed` | 20 | Desktop action completed with verification evidence |

---

## What Does NOT Earn MindCoin

- Raw surveillance
- Unapproved memory
- Invented progress
- Unverified claims
- Financial events of any kind
- Actions that failed verification
- Events without evidence

---

## Hard Rules

1. No event may claim value without evidence.
2. No event may be financial.
3. No event may be transferable.
4. No external blockchain.
5. Pending points are not approved points.
6. Revoked and quarantined events are preserved in the ledger but excluded from totals.
7. Do not mint points for unapproved memory.
8. Preserve unknowns.
9. Events require source links or source IDs where available.

---

## Status Lifecycle

```
create_event() -> STATUS_PENDING
                      |
         approve_event()   reject_event()   quarantine_event()
              |                |                    |
        APPROVED          REJECTED           QUARANTINED
              |
        revoke_event()
              |
          REVOKED  <- preserved but excluded from totals
```

Only `STATUS_APPROVED` events count toward `approved_points`.  
Revoked and quarantined events remain in the ledger for audit purposes.  
Once revoked, an event cannot be re-approved.

---

## Accounting

```
total_points    = approved_points only
pending_points  = pending events (not yet approved by Noah)
revoked_points  = revoked + quarantined (excluded from total)
```

`total_points` is a conservative floor, not an optimistic ceiling.

---

## Persistence

```
Memory/mindcoin_ledger.json
```

Gitignored. Local only. Never committed. Never transmitted.

---

## API

```python
from mindcoin import (
    load_ledger,
    save_ledger,
    create_event,
    approve_event,
    reject_event,
    revoke_event,
    quarantine_event,
    get_totals,
    list_pending,
    list_approved,
    summarize_ledger,
    award_for_candidate,
    award_for_completion,
    EVENT_MEMORY_APPROVED,
    EVENT_CANDIDATE_CREATED,
    EVENT_VERIFIED_ACTION_COMPLETED,
    # ... all event type constants
)

ledger, events = load_ledger()

# Create a pending event
e = create_event(
    event_type=EVENT_CANDIDATE_CREATED,
    title="OBS session candidate",
    evidence="commit 37dde78 — obs_ingest.py 26/26 smoke tests",
    source_module="obs_ingest",
    source_id="candidate_abc123",
    project_name="ORACLE.AI",
)
events.append(e)

# Noah approves
approve_event(e.id, events)

save_ledger(ledger, events)

# Check totals
print(get_totals(ledger))
# {'approved_points': 1, 'pending_points': 0, 'revoked_points': 0, 'total_points': 1}

# Award for candidate creation (convenience wrapper)
ev = award_for_candidate("video", "vid_59909a23", "video_intelligence 38/38 smoke tests")
events.append(ev)
save_ledger(ledger, events)
```

---

## CLI

```bash
# Run smoke tests
python core/mindcoin.py --smoke-test

# Print ledger summary
python core/mindcoin.py --summary

# List pending events
python core/mindcoin.py --pending

# Award points for a specific event type
python core/mindcoin.py --award continuity_export_created \
  --title "Continuity Export v0.1" \
  --evidence "commit 4213643, 43/43 smoke tests" \
  --project "ORACLE.AI"
```

---

## ORACLE Commands (if oracle.py is running)

```
/mindcoin                    Print ledger summary
/mindcoin-pending            List pending events
/mindcoin-approve <id>       Approve a pending event
/mindcoin-award <type> <title>  Award for a completed event
```

---

## Smoke Tests

51/51 — all passing.

Covers:
- Ledger creation and event list initialization
- Pending event: pending_points only, approved_points = 0
- Approve event: moves points to approved total
- Revoke event: removes from approved total, preserves event
- Quarantine event: excluded from approved total, event preserved
- `unknown_preserved` = 1 point
- `continuity_export_created` = 15 points
- `verified_action_completed` = 20 points
- Financial/crypto language rejected in title and evidence
- Invalid event type rejected
- Missing evidence rejected
- Whitespace-only evidence rejected
- Ledger serializes and deserializes with correct approved_points
- Cannot approve a revoked event (raises ValueError)
- `summarize_ledger` returns string containing "MindCoin"
- `award_for_candidate("video")` creates correct event type at 2 points
- `award_for_completion(EVENT_BLOCKER_RESOLVED)` at 10 points
- `get_totals` returns dict with `approved_points` key
- Point schedule covers all 14 valid event types

---

## Philosophy

MindCoin was invented to answer a real problem: ORACLE does meaningful work — compresses memories, recovers sessions, preserves unknowns, creates candidates — and that work has no internal metric. Without a metric, the system cannot report how much durable continuity it has actually produced.

MindCoin is not gamification. It is not motivation. It is not a reward system for humans. It is an internal audit trail for governed continuity work, expressed as points so the system can report its own output honestly.

Memory is moral weight. MindCoin is how ORACLE weighs it.

---

*Last updated: 2026-06-07 | ORACLE.AI — MindCoin v0.1*
