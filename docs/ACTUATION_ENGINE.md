# ORACLE Actuation Engine v0.2

## Position in the Pipeline

```
Raw Activity → Events → Context → Meaning → Memory → Retrieval → [Actuation Engine] → Action
```

The Actuation Engine is the final mechanical layer before any action reaches the environment.
It replaces fragile mouse-coordinate automation with deterministic semantic execution.

---

## Core Principle

**The engine does not look at pixels first. It reads the structural environment.**

Mouse coordinates are physical entropy. The position of a button changes when the browser
scales, the window moves, or the OS DPI setting changes. The button's name in the
accessibility tree does not change. The engine targets the name.

---

## Four Pillars

### 1. Semantic UI Bridge

Uses Windows UIAutomation (accessibility tree) to find UI elements by:

- Control type (button, edit field, combo box)
- Automation ID
- Name / label
- Class name
- Process name
- Window title
- Enabled / focused state

No pixel coordinates. If UIAutomation (comtypes) is not installed, the engine degrades
gracefully — window operations still work via pygetwindow, but element-level targeting
requires comtypes.

**To enable full UIAutomation:**
```
pip install comtypes
```

### 2. State Verification Loop

Before every action, the engine queries:

| Query | Failure response |
|-------|-----------------|
| Is the target process running? | System pause — report and stop |
| Is the target window present? | System pause — report and stop |
| Is the target window active? | Focus window, re-verify |
| Is the target element present? | System pause — do not guess |
| Is the target element enabled? | Report disabled state — stop |
| Did text injection land? | Verification failure — do not retry blind |

**Lack of data causes a structured pause, not a blind action.**

### 3. Command API

Semantic commands replace `move_and_click`:

| Command | Description | Approval required? |
|---------|-------------|-------------------|
| `list_windows()` | List all visible windows | No |
| `find_window(title, process)` | Find window by title/process | No |
| `focus_window_semantic(title)` | Focus window by title | No |
| `list_elements(window_ref)` | List UI elements in window | No |
| `find_element(window, name, ...)` | Find element by semantic properties | No |
| `focus_element(window, name)` | Focus element via UIA SetFocus | No |
| `inject_text(text, element)` | Inject text via UIA SetValue or keyboard | No |
| `verify_element_value(name, expected)` | Confirm element contains expected text | No |
| `get_element_value(name, window)` | Read current element value | No |
| `semantic_click(name, window)` | Click element via UIA Invoke | No |
| `execute_sequence(steps)` | Run a verified command sequence | Per-step |
| `dry_run_sequence(steps)` | Print sequence without executing | No |
| `mouse_fallback_click(x, y, reason)` | Last-resort coordinate click | No (but logged) |

### 4. The 51/49 Action Gate

The engine structures action candidates and halts before execution.
Noah holds 51% — every approval-required action stops and waits.

**Approval required (always stops for Noah):**
```
send_message    submit_form     post_public     purchase
delete          move_file       rename_file     modify_source
commit_code     push_code       change_permissions
share_file      unshare_file    calendar_change
close_window    kill_process
```

**Approval-free (safe reads and local focus):**
```
list_windows    find_window     focus_window_semantic
list_elements   find_element    focus_element
verify_element_value  get_element_value  screenshot_verify
is_process_running    get_active_window
```

---

## Safety Modes

### SAFE_SLEEP_MODE

Set `SAFE_SLEEP_MODE = True` in `actuation_engine.py` or via REPL command `safe_sleep_mode`.

- No mouse movement
- No keyboard injection
- No browser opening
- No file changes
- Observe and propose only

### ACTION_DRY_RUN

Set `ACTION_DRY_RUN = True` to print intended commands without executing them.

```python
from actuation_engine import ACTION_DRY_RUN
ACTION_DRY_RUN = True
browser_navigate_deterministic("https://chatgpt.com")
# Prints the sequence — does not touch the OS
```

---

## Browser Deterministic Test

`browser_navigate_deterministic(url)` is the canonical integration test for the engine.

Steps:
1. `is_process_running("chrome.exe")` — state query before touching anything
2. If running: `find_window(title_contains="Chrome")` — find existing window
3. If not running: `subprocess.Popen(["cmd", "/c", "start", "chrome"])` + wait + verify
4. `focus_window_semantic(title_contains="Chrome")` — semantic focus, no pixel click
5. `pyautogui.hotkey("ctrl", "l")` — Ctrl+L targets address bar deterministically
6. `pyautogui.write(url)` + `Enter` — navigate
7. `find_window(title_contains=domain)` — verify page loaded by title, not screenshot

**Does not send, submit, or type into any page content.**

To run live (not dry-run):
```
python core/actuation_engine.py browser-test
```

---

## Loop Guard

The engine tracks the last 9 actions. If the same `(action, target)` pair appears 3 times
without verified progress, the engine stops and reports:

```
Loop guard triggered: focus_window_semantic repeated without verified progress. Stopping.
```

This prevents the `open_program → stop → open_program → stop` loops SOV1 previously exhibited
with the coordinate-based browser target.

---

## Mouse Fallback Policy

Coordinate clicking is the **last resort**, not the first tool.

`mouse_fallback_click(x, y, reason)` requires:
- An explicit reason string
- Verification of state change after click
- Two failed verifications → full stop (no third attempt)

The fallback is logged to the audit log automatically.

---

## Backend Requirements

| Feature | Requirement | Status |
|---------|-------------|--------|
| Process detection | subprocess / tasklist | Always available |
| Window listing | pygetwindow | Already installed |
| Window focus | pygetwindow | Already installed |
| Address bar (Ctrl+L) | pyautogui | Already installed |
| UI element tree | comtypes (UIAutomation) | Optional — install to unlock |
| Element focus/inject via UIA | comtypes | Optional |
| Keyboard fallback inject | pyautogui | Already installed |

To install the full UIAutomation backend:
```
pip install comtypes
```

---

## Smoke Test Results (v0.2)

```
49/49 smoke tests passed.
```

v0.2 adds Drive Scope enforcement (Stage 0.5 gate) and 10 new scope tests (13-22):
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

Original coverage from initial release (tests 1-12):
- SAFE_SLEEP_MODE blocks all physical actions
- ACTION_DRY_RUN intercepts without executing
- Missing element causes structured pause, not blind click
- send_message / submit_form correctly classified as approval-required
- list_windows / focus_element correctly classified as approval-free
- Loop guard triggers after 3 repeated identical calls
- dry_run_sequence labels all approval-required steps
- SSN pattern blocked in inject_text
- browser_navigate_deterministic dry-run runs all steps without crashing
- is_process_running correctly detects explorer.exe

See also: `docs/ACTUATION_SCOPE_ENFORCEMENT.md` for Drive Scope gate details.
