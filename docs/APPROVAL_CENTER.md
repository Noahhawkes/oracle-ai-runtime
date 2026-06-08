# ORACLE Approval Center v0.1

One place to view and approve all pending candidates across ORACLE's subsystems.

## Sources

| Source | File | What it contains |
|---|---|---|
| `memory` | `Memory/remember_me/index.json` | Pending memory captures |
| `video` | `Memory/video_observation_candidates.json` | Video observation candidates |
| `mindcoin` | `Memory/mindcoin_ledger.json` | MindCoin events pending approval |
| `action_candidate` | `Memory/action_candidates.json` | Proposed desktop/system actions |
| `obs` | `Memory/obs_candidates.json` | OBS/provenance candidates |

## Rules

- **No mass approval.** Every `approve()` call takes exactly one candidate id.
- Every approval records `approved_by` and `approved_at`.
- Rejected, revoked, and quarantined candidates **never execute**.

## CLI

```bash
# List all pending approvals across all sources
python core/approval_center.py --list

# Approve a specific candidate
python core/approval_center.py --approve <id>
python core/approval_center.py --approve <id> --source action_candidate

# Reject
python core/approval_center.py --reject <id> --reason "too risky"

# Quarantine (stronger than reject — blocks permanently)
python core/approval_center.py --quarantine <id> --reason "unsafe"

# Revoke an already-approved action candidate
python core/approval_center.py --revoke <id>
```

## API

```python
from approval_center import list_pending, approve, reject, quarantine, revoke

pending = list_pending()   # all sources
for p in pending:
    print(p["source"], p["id"][:8], p["title"])

result = approve("abc-123", approved_by="noah")
# {"ok": True, "source": "action_candidate", "id": "...", "approved_by": "noah", ...}
```
