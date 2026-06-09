# ORACLE Actuation Scope Enforcement

**Module:** `core/actuation_engine.py` — v0.2
**Gate added:** Drive Scope gate (Stage 0.5)
**Depends on:** `core/drive_scope.py`

---

## What changed in v0.2

Drive Scope is now wired into the Actuation Engine as a hard gate.
ORACLE cannot take any file-affecting action on a path outside approved
Drive Scope — not because she is polite, but because the gate stops
the pipeline before execution reaches the file system.

---

## The gate: Stage 0.5

The full `execute()` pipeline is now:

```
Stage 0   — SAFE_SLEEP / BLOCKED check          (blocks all actuation)
Stage 0.5 — Drive Scope gate                    (blocks out-of-scope file actions)
Stage 1   — Dry run short-circuit
Stage 2   — Brain Router confirmation
Stage 3   — Forbidden action check
Stage 4   — Approval gate
Stage 5+  — Window / control / inject / verify
```

Stage 0.5 only fires when `target_file_path` is set on the request.
UI-only actions (inject_text into a window) with no file path skip it.

---

## Risk levels

Every file-affecting action carries a risk level with its own gate:

| Action | Risk | Gate |
|--------|------|------|
| `file_read` | Low | In approved scope |
| `file_write` | Medium | In approved scope + `approved_for_write=True` |
| `file_create` | Medium | In approved scope + `approved_for_write=True` |
| `file_edit` | Medium | In approved scope + `approved_for_write=True` |
| `file_copy` | Medium | In approved scope + `approved_for_write=True` |
| `file_delete` | High | In approved scope + `approved_by_noah=True` |
| `file_move` | High | In approved scope + `approved_by_noah=True` |
| `file_rename` | High | In approved scope + `approved_by_noah=True` |
| `file_upload` | High | In approved scope + `approved_by_noah=True` |
| `file_sync` | High | In approved scope + `approved_by_noah=True` |
| `file_permission` | High | In approved scope + `approved_by_noah=True` |

Destructive actions (delete, move, rename, upload, sync, permission) always
require explicit Noah approval even when the path is inside approved scope.

---

## Block conditions

The gate blocks and returns a reason string for:

| Condition | Reason |
|-----------|--------|
| System path (`C:\Windows`, `Program Files`, etc.) | `BLOCKED — system path: ...` |
| Sensitive folder pattern (tax, legal, Chrome, etc.) | `BLOCKED — sensitive folder pattern matched: ...` |
| Path outside approved Drive Scope | `BLOCKED — path is outside approved Drive Scope: ...` |
| Write action without `approved_for_write` | `BLOCKED — file_write requires approved_for_write=True ...` |
| Destructive action without `approved_by_noah` | `BLOCKED — file_delete always requires explicit Noah approval ...` |
| Drive Scope module unavailable | `BLOCKED — Drive Scope unavailable (error): ...` |

All block reasons are human-readable. `ActuationResult.scope_blocked = True`
and `scope_block_reason` carries the exact reason string.

---

## Usage

```python
from actuation_engine import execute, ActuationRequest, FILE_ACTION_READ, FILE_ACTION_WRITE

# Read from an approved path — allowed
r = execute(ActuationRequest(
    action_type="file_read",
    target_file_path="C:\\Users\\noahh\\Documents\\notes.txt",
    file_action=FILE_ACTION_READ,
))

# Write to an approved path — requires approved_for_write
r = execute(ActuationRequest(
    action_type="file_write",
    target_file_path="C:\\Users\\noahh\\Documents\\notes.txt",
    file_action=FILE_ACTION_WRITE,
    approved_for_write=True,
))

# Delete — always requires Noah's explicit approval
r = execute(ActuationRequest(
    action_type="file_delete",
    target_file_path="C:\\Users\\noahh\\Documents\\old.txt",
    file_action=FILE_ACTION_DELETE,
    approved_by_noah=True,
))

# Out-of-scope — blocked immediately
r = execute(ActuationRequest(
    action_type="file_read",
    target_file_path="C:\\Windows\\System32\\config",
    file_action=FILE_ACTION_READ,
))
assert r.scope_blocked
assert "system path" in r.scope_block_reason
```

---

## Approved scope

Approved paths are defined by `core/drive_scope.py`. On this machine:

| Path | Status |
|------|--------|
| `C:\Users\noahh\Desktop` | proposed |
| `C:\Users\noahh\Documents` | proposed |
| `C:\Users\noahh\Downloads` | proposed |
| `C:\Users\noahh\OneDrive` | proposed |
| `C:\Users\noahh\OneDrive - sov1.ai` | proposed |
| `C:\Users\noahh\OneDrive - Eh3 Holdings LLC` | proposed |
| `G:\My Drive` | proposed |
| `G:\My Drive\HawkesNest LLC\ORACLE.AI` | oracle root |

`proposed` = discovered but awaiting Noah's review in `Memory/scoped_paths_proposed.json`.
Until reviewed, all paths in `scoped_paths.json` (written by `--discover`) are treated as approved.

---

## Smoke tests

```
python core/actuation_engine.py --smoke-test   # 49/49
python core/drive_scope.py --smoke-test        # 30/30
```

The 10 new scope tests (13–22) cover:
- Approved read path allowed
- System path blocked
- Out-of-scope path blocked
- Write without `approved_for_write` blocked
- Write with `approved_for_write` allowed
- Delete without Noah approval blocked inside scope
- `execute()` pipeline scope gate fires
- No `target_file_path` skips gate
- Block reason is non-empty and human-readable
- SAFE_SLEEP fires before scope gate (correct order)
