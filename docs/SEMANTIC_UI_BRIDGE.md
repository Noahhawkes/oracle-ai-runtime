# ORACLE Semantic UI Bridge v0.1
## `core/semantic_ui_bridge.py`

---

## The Problem This Solves

The ACTUATION_ENGINE needs to find, focus, and type into UI controls without guessing mouse coordinates.

Mouse coordinates fail because:
- Window positions change
- Browser zoom changes element positions
- Multiple monitors change coordinate offsets
- Applications resize, scroll, and reflow

Windows UIAutomation solves this: controls have names, types, and automation IDs that are stable regardless of position.

---

## Core Law

> **No claiming success without verification evidence.**
> If the target window is missing → stop cleanly.
> If the target control is missing → stop cleanly.
> If injected text cannot be verified → report unverified, do not claim success.

---

## Forbidden Actions

This module will **never** perform:

```
send  submit  delete  move  rename  post
purchase  buy  commit  push  share
change permission  set permission
```

Any call containing these verbs raises `PermissionError` immediately, before any action is taken.

---

## Engine Rule (from Brain Router)

All functions in this module are **`ACTUATION_ENGINE` territory**.

- `LOCAL_SMALL` (qwen2.5:7b) may not call them
- `LOCAL_SMALL` may not claim their results succeeded
- The Brain Router routes all `desktop_action` tasks here, not to any LLM

---

## Backend Priority

```
1. pywinauto (UIA backend)   — preferred
2. uiautomation              — fallback
3. Neither available         → clean failure with install instructions
```

Install:
```bash
pip install pywinauto
```

---

## API

### Window Operations

```python
from semantic_ui_bridge import list_windows, find_window, focus_window, get_active_window

# List all visible windows
windows = list_windows()
for w in windows:
    print(w.title, w.process_name, w.pid)

# Find a specific window
window = find_window(title_contains="ChatGPT")
if window is None:
    # Stop cleanly — do not guess
    raise RuntimeError("ChatGPT window not found")

# Focus it
result = focus_window(window)
print(result.verified)   # True only if confirmed active

# Active window title
title = get_active_window()   # → "ChatGPT - Google Chrome"
```

### Control Operations

```python
from semantic_ui_bridge import list_controls, find_control, focus_control

# List all controls in a window
controls = list_controls(window, control_type="Edit")

# Find a specific input field
field = find_control(window, control_type="Edit", automation_id="prompt-textarea")
if field is None:
    raise RuntimeError("Input field not found — stop cleanly")

# Focus the control
r = focus_control(field)
```

### Text Injection and Verification

```python
from semantic_ui_bridge import inject_text, verify_text

# Inject text (does NOT send, does NOT submit)
result = inject_text(field, "Hello from ORACLE")
print(result.success)    # True if injection completed
print(result.verified)   # True only if text read back and confirmed
print(result.mouse_used) # True if coordinate fallback was used

# Verify what's in the field
r = verify_text(field, expected_text="Hello from ORACLE")
print(r.verified)        # True if text is there
print(r.text_found)      # What was actually read

# Dry run — inspect intent without executing
result = inject_text(field, "Hello", dry_run=True)
```

### Dry Run Sequences

```python
from semantic_ui_bridge import dry_run_sequence

seq = dry_run_sequence(
    steps=[
        "find_window(title_contains='ChatGPT')",
        "focus_window(window)",
        "find_control(window, control_type='Edit')",
        "inject_text(field, 'Hello ORACLE')",
        "verify_text(field, 'Hello ORACLE')",
    ],
    target_window="ChatGPT",
    purpose="Draft message injection",
)
print(seq.report())
# → [DRY RUN SEQUENCE — abc12345]
#   Purpose : Draft message injection
#   Steps   : 5
#     1. find_window(title_contains='ChatGPT')
#     ...
#   [NOT EXECUTED] Dry run only.

# Forbidden actions detected:
bad_seq = dry_run_sequence(steps=["submit the form"])
print(bad_seq.forbidden_detected)   # True
print(bad_seq.forbidden_reason)     # "Step contains forbidden action 'submit'..."
```

---

## Data Models

### `WindowRef`
```python
@dataclass
class WindowRef:
    id: str              # auto-generated
    title: str           # window title text
    process_name: str    # e.g. "chrome.exe"
    pid: int
    handle: int          # HWND
    backend: str         # "pywinauto" | "uiautomation"
```

### `ControlRef`
```python
@dataclass
class ControlRef:
    id: str
    window_id: str
    name: str            # control's accessible name
    control_type: str    # "Edit", "Button", "Document", etc.
    automation_id: str   # UIA automation ID (stable)
    class_name: str      # Win32 class name
    rect: tuple          # (left, top, right, bottom)
```

### `BridgeResult`
```python
@dataclass
class BridgeResult:
    operation: str        # what was attempted
    success: bool         # did the call complete without error
    verified: bool        # was the result independently confirmed
    target_window: str
    target_control: str
    text_injected: str
    text_found: str       # what was read back
    failure_reason: str   # non-empty only on failure
    dry_run: bool
    mouse_used: bool      # True if coordinate fallback was used
    unknowns: list        # preserved — never inferred
```

`verified=True` means verification evidence exists. `success=True` without `verified=True` means the call ran but the result is unconfirmed.

---

## Rules

1. **Structural UI access first.** Use `set_edit_text()` (value pattern) before `type_keys()` (keyboard simulation). Never use raw screen coordinates as primary method.
2. **Mouse coordinates are a fallback only.** If `set_focus()` fails, `click_input()` on the control's own rect is acceptable. Raw coordinate clicks are not.
3. **Stop cleanly on missing window.** `find_window()` returns `None`. Callers must handle `None` explicitly.
4. **Stop cleanly on missing control.** `find_control()` returns `None`. Callers must handle `None` explicitly.
5. **Stop cleanly on unverified injection.** `inject_text()` returns `verified=False` with unknowns populated. The action layer must not claim success.
6. **No forbidden actions.** `_block_forbidden()` is called before every injection.
7. **HUMAN_SOVEREIGN for irreversibles.** Send, submit, delete, purchase, commit, push — always escalate first.

---

## CLI

```bash
python core/semantic_ui_bridge.py --smoke
python core/semantic_ui_bridge.py --list-windows
python core/semantic_ui_bridge.py --find "ChatGPT"
python core/semantic_ui_bridge.py --dry-run
python core/semantic_ui_bridge.py --backend
```

---

## Smoke Tests

32/32 — all passing.

Covers:
- `list_windows()` returns list of `WindowRef` objects (10 live windows found)
- `find_window()` for nonexistent returns `None` cleanly
- `dry_run_sequence()` — correct steps, NOT EXECUTED, no forbidden
- `dry_run_sequence()` detects forbidden 'submit' and marks BLOCKED
- `_block_forbidden()` raises `PermissionError` on all 5 forbidden verbs
- `_block_forbidden()` allows all 4 safe verbs
- `inject_text(dry_run=True)` — succeeds, not verified, unknown note present
- `inject_text()` raises `PermissionError` on forbidden text ("submit payment")
- `verify_text()` with no raw handle — fails cleanly, reason set, no crash
- `WindowRef.__str__()` and `ControlRef.__str__()` without crash
- `BridgeResult.explain()` — builds, contains operation name, shows NOT verified
- `INSTALL_INSTRUCTIONS` — non-empty, contains `pip install`

---

## Live Test (2026-06-07)

`--list-windows` returned 10 windows including:
```
[18232]  pid:18232    ChatGPT - Google Chrome
[6012]   pid:6012     ORACLE.AI
[36420]  pid:36420    SOV1.AI Role Definition
```

ChatGPT window is visible and findable. Control enumeration (`list_controls`) and text injection are the next integration targets.

---

## Router Integration

```
/route-task type a message into ChatGPT

  Engine   : ACTUATION_ENGINE
  Allowed  : YES
  Constraints:
    [RESTRICTED] LOCAL_SMALL may not claim this action succeeded
    [RESTRICTED] Screen hash verification required before reporting completion
    [RESTRICTED] Approval gate required for irreversible actions
```

The Brain Router correctly routes "type a message into ChatGPT" to `ACTUATION_ENGINE`. This module is what `ACTUATION_ENGINE` calls to do the actual work.

---

## What's Next

`core/actuation_engine.py` — the governed execution layer that:
1. Calls `brain_router.route_task()` to confirm `ACTUATION_ENGINE` is selected
2. Uses `semantic_ui_bridge` to find window and control
3. Calls `inject_text()` with `dry_run=False` only after approval gate passes
4. Checks `result.verified` before reporting completion
5. Records screen hash before and after (from `action_batch.py`)
6. Never claims success without all three: injection complete + text verified + screen changed

---

*Last updated: 2026-06-07 | ORACLE.AI — Semantic UI Bridge v0.1*
