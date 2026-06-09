# ORACLE Freedom to Ask

**Module:** `core/freedom_to_ask.py` — v0.1
**Machine profiles:** `Memory/machine_profiles/`

---

## The problem this solves

ORACLE was freezing at permission boundaries instead of asking. She treated a
scope block as a full stop. The fix is not removing permissions — it's giving
her practical freedom to ask clearly and keep moving.

**Asking is always allowed. Proposing is always allowed.**
Only destructive action is hard-blocked.

---

## The ask format

When ORACLE hits a permission boundary, she emits exactly this format:

```
I need access to `<scope>` because <reason>. I only need <mode>.
I will not: <blocked actions>. Safeguards: <safeguards>. Approve? [request_id: <id>]
```

This replaces silent freezes and bare [BLOCKED] messages.

---

## Access modes

| Mode | What it allows | Requires approval |
|---|---|---|
| `ASK_ONLY` | Ask questions or clarify — no reads or writes | No |
| `READ_DISCOVERY` | Inspect names, paths, metadata, repo state | No (in approved scope) |
| `READ_CONTENT` | Read file contents inside approved scope | Yes |
| `WRITE_DRAFT` | Create draft or candidate files only | Yes |
| `WRITE_ACTIVE` | Modify approved project files | Yes |
| `DESTRUCTIVE` | Delete, move, rename, overwrite, upload, sync, share, permissions | Always explicit |

---

## Default freedom policy

| Action | Allowed |
|---|---|
| Asking for access | Always |
| Proposing a scoped action | Always |
| Read-only repo inspection in approved roots | Always |
| Read-only path discovery in known workspace roots | Always |
| Reading personal file contents | Requires approval |
| Writing any file | Requires approval |
| Destructive actions | Requires explicit per-action approval |
| External/cloud/API actions | Requires approval |
| SAFE_SLEEP | Blocks learning writes and actuation; status answers still allowed |

---

## Machine profiles

ORACLE tracks which machine she is running on, but **never assumes** whether it
is Noah's laptop or desktop. The form factor stays `UNKNOWN` until Noah explicitly
confirms it.

```json
// Memory/machine_profiles/current_machine.json
{
  "machine_id": "SOV1MSILaptop",
  "form_factor": "UNKNOWN",
  "noah_verified": false,
  "note": "form_factor remains UNKNOWN until Noah explicitly confirms..."
}
```

To confirm:
```python
from freedom_to_ask import verify_form_factor
verify_form_factor("laptop")   # or "desktop"
```

---

## Access requests

Every request ORACLE cannot self-approve is written to
`Memory/machine_profiles/access_requests.json` as `PENDING`.

```json
{
  "request_id": "a3f7bc21",
  "machine_id": "SOV1MSILaptop",
  "requested_path_or_capability": "C:\\Users\\noahh\\Documents",
  "requested_mode": "READ_CONTENT",
  "reason": "to read project notes for context",
  "smallest_scope": "C:\\Users\\noahh\\Documents\\notes.txt",
  "duration": "this_session",
  "risk_level": "low",
  "cloud_sync_risk": false,
  "proposed_safeguards": ["No destructive actions", "No external/cloud uploads"],
  "will_not_do": ["Delete files", "Move or rename files"],
  "status": "PENDING",
  "waiting_for_noah_approval": true
}
```

**ORACLE cannot approve her own requests.** `status` is always `PENDING`
until Noah acts on it.

---

## Workaround when denied

If a request is denied, ORACLE generates a workaround prompt — she describes
what she can still do without the blocked access. She keeps moving.

Examples:
- **READ_CONTENT denied**: "Can't read `path`. I can describe what I'd expect to find, work from memory, or you can paste the relevant section."
- **WRITE_ACTIVE denied**: "Write access blocked. I can produce the proposed content here for your review. When you approve, I'll write it."
- **DESTRUCTIVE denied**: "I've created a pending request [id: X]. Say 'approve X' to proceed or describe the alternative."

---

## Integration with Actuation Engine

When the Actuation Engine's Drive Scope gate (Stage 0.5) returns `scope_blocked=True`,
`oracle.py` intercepts the tool result and converts it to a freedom-to-ask phrase
before passing it back to the LLM. ORACLE receives the ask phrase instead of a raw
`BLOCKED —` string, so her next response is an ask, not a freeze.

---

## Integration with oracle.py system prompt

The `_inject_local_context()` function appends the freedom-to-ask policy to every
local-model context injection:

```
[FREEDOM TO ASK POLICY]
If you hit a permission boundary, DO NOT freeze or say 'I cannot do that.'
Instead say: 'I need access to [scope] because [reason]. I only need [mode].
I will not [blocked actions]. Approve?'
```

---

## CLI

```bash
python core/freedom_to_ask.py --smoke-test
python core/freedom_to_ask.py --status
python core/freedom_to_ask.py --profile-current-machine
python core/freedom_to_ask.py --request-access --path "C:\Users\noahh\Documents" --mode READ_CONTENT --reason "find project notes"
```

---

## Smoke tests

```
python core/freedom_to_ask.py --smoke-test   # 12/12
```

1. Asking is allowed without approval
2. Proposing is allowed without approval
3. Access request is marked pending
4. ORACLE cannot approve her own request
5. Write request requires approval
6. Destructive request requires explicit approval
7. Cloud sync path is flagged
8. Smallest scope is required
9. Denied permission creates workaround prompt
10. Laptop/desktop machine identity preserved as UNKNOWN unless verified
11. SAFE_SLEEP blocks writes
12. No destructive or external action occurs
