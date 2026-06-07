# ORACLE Window Janitor
## ORACLE.AI — Desktop Governance Doctrine

---

## Core Doctrine

> **If ORACLE opens it, ORACLE is responsible for cleaning it.**
> **If Noah opened it, ORACLE must not assume ownership.**
> **Visibility is not ownership.**

---

## Purpose

When ORACLE/SOV1 takes actions, it opens Chrome, Command Prompt, PowerShell, or other windows and leaves the desktop messy. The Window Janitor tracks task-owned windows and restores the desktop cleanly after ORACLE completes, fails, or stops a task.

---

## Safety Rules

1. **dry_run=True by default** — nothing closes without explicit approval
2. **Unknown ownership = skip and preserve** — if unsure, do nothing
3. **Prefer minimize over close** when ownership is uncertain
4. **Protected windows are NEVER closed** regardless of any instruction

---

## Ownership Model

```
opened_by_oracle=True  + safe process + no unsaved indicator  →  cleanup_pending (closeable)
opened_by_oracle=True  + unsaved indicator in title           →  approval_required
opened_by_oracle=True  + unknown process                      →  approval_required
touched_by_oracle=True + opened_by_oracle=False               →  approval_required
always-protected titles (bank, 1Password, ORACLE terminal)    →  protected (never asked)
unknown ownership                                              →  skipped (preserved)
```

---

## WindowRecord

| Field | Description |
|---|---|
| `id` | Unique record ID |
| `task_id` | The task that owns this window |
| `window_title` | Window title at registration time |
| `process_name` | Executable name (lowercase) |
| `pid` | Process ID |
| `handle` | Win32 window handle |
| `opened_by_oracle` | True if ORACLE opened it |
| `touched_by_oracle` | True if ORACLE interacted with it |
| `safe_to_close` | True only when all safety conditions are met |
| `requires_approval_to_close` | True when human review needed |
| `reason` | Why this classification was given |
| `status` | Current status (see below) |
| `unknowns` | Preserved unknowns |

## Status Values

| Status | Meaning |
|---|---|
| `observed` | Seen but not claimed |
| `claimed` | ORACLE opened this window |
| `protected` | Never close — hardware-locked |
| `cleanup_pending` | Safe to close with dry_run=False |
| `closed` | Successfully closed |
| `skipped` | Unknown ownership, preserved |
| `failed` | Close attempt failed |
| `approval_required` | Needs Noah decision |

---

## Protected Forever (Never Close)

- ORACLE terminal / Claude Code / Codex sessions
- 1Password, Bitwarden, KeePass
- Banking and financial sites
- Email compose windows
- Unsaved documents
- Terminals running active processes
- Windows with unknown ownership

---

## API

```python
from window_janitor import get_janitor

wj = get_janitor()

# At task start — snapshot current window state
wj.snapshot_task_start(task_id)

# As ORACLE opens windows — register them
rec = wj.register_task_window(
    task_id="task_001",
    window_title="ChatGPT - Google Chrome",
    process_name="chrome.exe",
    pid=1234,
    handle=9999,
    reason="oracle_navigated_to_chatgpt",
)

# If ORACLE touched but didn't open
wj.mark_touched(task_id, window_title="Some Doc", handle=5555)

# After task — dry run first (default)
report = wj.cleanup_task_windows(task_id, dry_run=True)
print(report.summary())

# If Noah approves:
report = wj.cleanup_task_windows(task_id, dry_run=False)
```

---

## CleanupReport Fields

- `closed` — windows successfully closed
- `minimized` — windows minimized (uncertain ownership)
- `skipped` — unknown ownership, preserved
- `approval_required` — need Noah decision
- `protected` — always-protected, no action taken
- `errors` — close attempts that failed

---

## REPL Commands

```
/window-snapshot        List currently visible windows
/window-cleanup-dry-run Propose cleanup for current task (dry run)
```

---

## Persistence

`Memory/window_janitor_records.json`

Records survive session restarts. Task records can be cleared after confirmed cleanup.

---

## Integration Points

- `sov1.py` / `actuation_engine.py` — register windows as SOV1 opens them
- `oracle_runtime.py` — call restore_desktop() at task end
- Future `action_queue.py` — attach window tracking to queued actions

---

*Last updated: 2026-06-07 | ORACLE.AI*
