# ORACLE Session State Controller v0.1
## `core/session_state.py`

---

## The Problem This Solves

ORACLE was treating all incoming text as equivalent input to whatever was last active.

When the GitHub backup tool opened a username prompt, and Noah typed architecture notes, ORACLE consumed the notes as a GitHub username. When the daemon proposed its next task, it ignored the active engineering blocker and pushed stale revenue tasks. When the loop guard fired, it produced prose ("I made 12 tool calls") instead of structured recovery state. When Noah typed `ACTION_DIAGNOSTIC`, qwen answered it as if it were a conversation topic.

The problem is not the LLM. The problem is that there was no session state. Every input entered a context with no knowledge of what mode ORACLE was in, what prompt was active, or what the input was actually supposed to be.

---

## Core Law

> **Incoming user input must not be blindly consumed by stale tool state.**
> **If an active prompt exists, classify whether the input is actually an answer to that prompt before using it.**

---

## Modes

| Mode | Meaning |
|---|---|
| `IDLE` | No active task. Ready for input. |
| `BUILD_PASS` | MYTHIC BUILD PASS active. All input is build instruction. |
| `DAEMON_CYCLE` | Runtime heartbeat cycle running. |
| `TERMINAL_PROMPT` | A tool is waiting for specific input (e.g. GitHub username). |
| `COMPUTER_USE` | Desktop action in progress via ACTUATION_ENGINE. |
| `GOVERNANCE_CAPTURE` | Noah is dictating doctrine or governance rules. |
| `DIAGNOSTIC` | ACTION_DIAGNOSTIC output being generated. |
| `SAFE_SLEEP` | STOP ORACLE received. No desktop actions allowed. |
| `BLOCKED` | Something is blocking progress. Needs Noah intervention. |
| `ERROR_RECOVERY` | Loop guard triggered or unrecoverable error. Structured hint provided. |

---

## Input Classification

Every input is classified before it reaches any LLM or tool.

### Priority order (first match wins):

1. **Empty input** → free_text, no action
2. **Known command** (`ACTION_DIAGNOSTIC`, `STOP ORACLE`, `CLEAR_PROMPT`, `RESET_SESSION_STATE`, `SET_MODE *`) → `command`, **overrides active prompt**
3. **Governance phrase** → `governance_rule`, **overrides active prompt**
4. **Build pass signal** (`MYTHIC BUILD PASS`, `Build target:`, etc.) → `build_instruction`, **overrides active prompt**
5. **Stale prompt reject patterns** (markdown, `import`, `class`, code blocks) → override active prompt, reclassify
6. **Active prompt match** → `prompt_answer` (only if input actually fits expected type)
7. **Free text** → pass to LLM normally

### Expected input types:

| Type | Pattern |
|---|---|
| `github_username` | 1-39 chars, alphanumeric + hyphen, no spaces |
| `yes_no_confirmation` | y / yes / n / no / approve / reject / cancel |
| `approval` | approve / approved / reject / deny / yes / no / cancel |
| `command` | command prefix match |
| `build_instruction` | MYTHIC BUILD PASS and related signals |
| `governance_rule` | governance phrasing |
| `free_text` | everything else |
| `unknown` | unclassified |

---

## What Cannot Hijack a Prompt

When a terminal prompt is expecting a GitHub username, **none of the following will be consumed as a username:**

- Any text containing `mythic`, `oracle`, `sov1`, `build pass`, `core/`, `docs/`
- Any markdown (` ``` `, `---`, `#`)
- Any Python (`import`, `def`, `class`)
- Any governance phrase (`ORACLE may`, `SOV1 must`, `Only Noah`, etc.)
- Any text longer than 39 characters
- Any text with spaces

If the input fails the username pattern check, it is returned with `override_active_prompt=True` and the caller is instructed to route it normally instead.

---

## ACTION_DIAGNOSTIC

`ACTION_DIAGNOSTIC` is a **real command**, not a model response.

It is intercepted at the top of the input loop, before any LLM call, and returns structured session state:

```
  ╔══════════════════════════════════════════════════════════╗
  ║            ACTION DIAGNOSTIC — SESSION STATE             ║
  ╚══════════════════════════════════════════════════════════╝

  Mode          : ERROR_RECOVERY
  Mode reason   : focus_window called 6 times without progress
  Active task   : (none)

  Active prompt : (none)
  Expected input: unknown
  Prompt owner  : (none)
  Prompt age    : n/a
  Prompt stale  : no

  Loop guard    : TRIGGERED x1
  Blocked reason: focus_window called 6 times in 10 actions without progress
  Recovery hint : Type STOP ORACLE to halt. Type ACTION_DIAGNOSTIC to see state.

  Project blocker: qwen2.5:7b unreliable for desktop computer use
  Project next   : Build core/actuation_engine.py

  Last tool calls (most recent 10):
    [2026-06-07 18:23:01] focus_window | title=ChatGPT | no change detected
    [2026-06-07 18:23:02] focus_window | title=ChatGPT | no change detected
    ...

  Recommended commands:
    STOP ORACLE          — halt all action, enter SAFE_SLEEP
    CLEAR_PROMPT         — clear active prompt, return to IDLE
    RESET_SESSION_STATE  — full session reset (keeps tool history)
    SET_MODE IDLE        — force idle mode
    SET_MODE BUILD_PASS  — force build mode
```

---

## Daemon Priority Override

The daemon is blocked from proposing stale revenue tasks when an active engineering blocker exists.

```python
override, reason = daemon_should_override_with_engineering("Morning Mission Brief")
# → (True, "Active engineering blocker: 'qwen2.5:7b unreliable...' Daemon may not override...")

override, reason = daemon_should_override_with_engineering("Run ORACLE smoke tests")
# → (False, "Proposed task is not a stale revenue task.")
```

Stale revenue signals that get blocked:
`touchflame, morning mission, github backup, linkedin, upwork, kdp, revenue, morning brief, affiliate, passive income`

**The only way to switch to revenue mode is Noah explicitly requesting it.**

---

## API

```python
from session_state import (
    # State
    load_state, save_state,
    # Mode control
    set_mode, MODE_IDLE, MODE_BUILD_PASS, MODE_ERROR_RECOVERY, MODE_SAFE_SLEEP,
    MODE_TERMINAL_PROMPT, MODE_DAEMON_CYCLE, MODE_COMPUTER_USE,
    # Prompt control
    set_active_prompt, clear_active_prompt, detect_stale_prompt,
    # Input classification
    classify_user_input, should_consume_as_prompt_answer,
    INPUT_GITHUB_USERNAME, INPUT_YES_NO, INPUT_APPROVAL, INPUT_BUILD_INSTRUCTION,
    INPUT_GOVERNANCE_RULE, INPUT_COMMAND, INPUT_FREE_TEXT,
    # Recovery
    enter_recovery, reset_session_state,
    # Tool tracking
    record_tool_call,
    # Diagnostic
    action_diagnostic,
    # Command handler
    handle_command,
    # Daemon check
    daemon_should_override_with_engineering,
)

# Register that a terminal prompt is active
set_active_prompt(
    "Enter your GitHub username:",
    expected_input_type=INPUT_GITHUB_USERNAME,
    owner_tool="github_backup_tool",
)

# On next user input:
clf = classify_user_input(user_input)
should_consume, clf = should_consume_as_prompt_answer(user_input)
if not should_consume:
    # Route normally — do not send to GitHub tool
    pass

# When loop guard fires:
enter_recovery(
    reason="focus_window called 6 times without progress",
    hint="Type STOP ORACLE. Check ChatGPT window title.",
)

# Daemon check before proposing task:
override, reason = daemon_should_override_with_engineering(proposed_task)
if override:
    print(f"Blocked: {reason}")
```

---

## Commands (intercepted before LLM)

| Command | Effect |
|---|---|
| `ACTION_DIAGNOSTIC` | Print structured session state |
| `STOP ORACLE` | Clear prompts → SAFE_SLEEP |
| `CLEAR_PROMPT` | Clear active prompt → IDLE |
| `RESET_SESSION_STATE` | Full reset → IDLE, preserve tool history |
| `SET_MODE IDLE` | Force IDLE |
| `SET_MODE BUILD_PASS` | Force BUILD_PASS |
| `SET_MODE SAFE_SLEEP` | Force SAFE_SLEEP |

All commands are intercepted in `handle_command()` which is called **before any LLM or tool invocation** in oracle.py.

REPL alias: `/session` or `/session-state` shows `action_diagnostic()` output.

---

## Loop Guard Integration

When the loop guard fires in `chat()`:

**Before:** `"I made 12 tool calls without finishing. Tell me what you'd like to do next."`

**After:**
```
[Loop guard] 12 tool calls without finishing.

  [ACTION DIAGNOSTIC — SESSION STATE]
  Mode          : ERROR_RECOVERY
  Blocked reason: Loop guard: 12 tool calls without finishing.
  Recovery hint : Type ACTION_DIAGNOSTIC to see which tool repeated.
                  Type STOP ORACLE to halt. Type CLEAR_PROMPT for stale prompt.
  Last tool calls:
    [18:23:01] focus_window | ChatGPT | no change
    [18:23:02] focus_window | ChatGPT | no change
    ...
```

---

## Persistence

`Memory/session_state.json` — single live session state file. Overwritten on every transition. Tool call history kept as rolling window of last 50 calls.

---

## CLI

```bash
python core/session_state.py --smoke
python core/session_state.py --diagnostic
python core/session_state.py --status
python core/session_state.py --reset
python core/session_state.py --classify "ORACLE.AI is a consent-based engine"
```

---

## Smoke Tests

41/41 — all passing.

Covers:
- Terminal prompt set → TERMINAL_PROMPT mode
- Governance text not consumed as GitHub username
- Governance text overrides active prompt
- `should_consume_as_prompt_answer` returns False for governance
- MYTHIC BUILD PASS text classified as BUILD_INSTRUCTION, overrides prompt
- Build pass not consumed as prompt answer
- ACTION_DIAGNOSTIC handled as real command, returns structured state
- Valid GitHub username accepted when prompt expects it
- STOP ORACLE clears prompt → SAFE_SLEEP
- `enter_recovery` → ERROR_RECOVERY, reason set, hint set, prompt cleared
- ACTION_DIAGNOSTIC shows ERROR_RECOVERY, blocked reason, recovery hint
- Daemon blocks Morning Mission when engineering blocker active
- Daemon blocks TouchFlame in BUILD_PASS mode
- Daemon allows non-revenue engineering tasks
- CLEAR_PROMPT clears prompt
- RESET_SESSION_STATE → IDLE, preserves tool history
- Stale prompt detection (fresh = not stale, 2020 timestamp = stale → cleared)
- Markdown code block not classified as github_username, overrides prompt

---

*Last updated: 2026-06-07 | ORACLE.AI — Session State Controller v0.1*
