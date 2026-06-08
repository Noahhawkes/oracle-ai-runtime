# ORACLE Action Candidates v0.1

ORACLE proposes actions before executing them. This module is the gate between
intent and actuation. No candidate executes unless it is **approved** and
passed explicitly to the Actuation Engine.

## Candidate lifecycle

```
pending → approved → [executed via Actuation Engine]
                  ↘ revoked   (changed mind after approval)
        → rejected             (Noah said no)
        → quarantined          (unsafe — never executes)
```

## Candidate fields

| Field | Type | Description |
|---|---|---|
| `id` | str (UUID4) | Unique candidate identifier |
| `title` | str | Short human-readable label |
| `description` | str | What the action does and why |
| `risk_level` | low/medium/high/critical | Assessed risk |
| `required_approval` | bool | Whether Noah must approve (always True for risky actions) |
| `target_module` | str | Which module executes it (e.g. `actuation_engine`) |
| `proposed_steps` | list[str] | Ordered execution steps |
| `reversibility` | str | reversible / irreversible / unknown |
| `evidence` | str | Supporting context (screen state, session state, etc.) |
| `status` | str | pending / approved / rejected / revoked / quarantined |
| `approved_by` | str or None | Who approved |
| `approved_at` | ISO datetime or None | When approved |
| `rejected_by` | str or None | Who rejected |
| `rejected_at` | ISO datetime or None | When rejected |
| `rejection_reason` | str or None | Why rejected/revoked/quarantined |
| `created_at` | ISO datetime | Created |
| `updated_at` | ISO datetime | Last modified |

## Rules

- All candidates **default to `pending`**.
- Only `approved` candidates may be passed to Actuation Engine.
- `rejected`, `revoked`, and `quarantined` candidates **never execute**.
- No mass approval. Each candidate is approved individually.
- Every approval records `approved_by` and `approved_at`.

## API

```python
from action_candidates import new_candidate, submit, approve, reject, revoke, quarantine, is_executable, list_candidates

c = new_candidate(
    title="Click Submit",
    description="Submit the open form",
    risk_level="low",
    target_module="actuation_engine",
    proposed_steps=["find Submit button", "click it"],
    reversibility="irreversible",
)
c = submit(c)

# Later — after Noah reviews:
approved = approve(c["id"], approved_by="noah")

# Pass to Actuation Engine only if executable:
if is_executable(approved):
    execute(build_actuation_request(approved))
```

## CLI

```
python core/action_candidates.py --list
python core/action_candidates.py --smoke-test
```

## Storage

`Memory/action_candidates.json` — flat JSON list, append-only by design.
