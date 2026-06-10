# ORACLE Operational Reality Audit
**Date:** 2026-06-10  
**Audited by:** Claude Code (MYTHIC BUILD PASS)  
**Purpose:** Find the gap between "smoke tests pass" and "ORACLE can actually help Noah."

---

## Executive Summary

ORACLE's architecture is sound and governance is correctly in place.  The main gap
between "tests pass" and "operationally useful" is three concrete problems:

1. **Over-gating**: Milestone policy used pure keyword matching, so questions
   *about* commits/cloud/governance/pull triggered hard-approval blocks before
   reaching the LLM.  Four common conversational questions were silently stopped.

2. **Missing NL pattern**: "use codex to inspect the repo" was not in the NL
   parser — it fell through to qwen (the local 7B model) which has no way to
   actually dispatch to Codex.

3. **No live probe command**: There was no `/doctor` command to show Noah (or
   ORACLE herself) what is actually working vs. registered-but-broken.

All three are fixed in this pass.

---

## Area 1 — Conversation Responsiveness

| Input | Before | After |
|-------|--------|-------|
| "talk to me" | OK — CHAT mode → LLM | OK |
| "what can you do right now" | OK — WORK mode → LLM | OK |
| "check your tools" | OK — WORK mode → LLM (sees `[WORKING TOOLS]` context) | OK |
| "use Codex to inspect the repo" | **BROKEN** — fell to LLM, qwen can't dispatch | FIXED → `/ask-codex inspect the repo` |
| "summarize your current state" | OK — WORK mode → LLM | OK |
| "what are you blocked on" | OK — WORK mode → LLM | OK |
| "what can you do without approval" | OK — WORK mode → LLM | OK |
| "what should we commit next" | **BLOCKED** — milestone policy hit "commit" | FIXED → LLM sees it as question |
| "what is the cloud architecture" | **BLOCKED** — milestone policy hit "cloud" | FIXED → LLM |
| "explain the governance model" | **BLOCKED** — milestone policy hit "governance" | FIXED → LLM |
| "pull up the repo status" | BLOCKED — "pull" not a question starter | Unchanged (ambiguous; use "what is the repo status") |

---

## Area 2 — Capability Registry Truthfulness

| Capability | Registered Status | Live Probe Result | Callable by ORACLE | Blocker |
|-----------|------------------|-------------------|--------------------|---------|
| Ollama / qwen2.5:7b | available | Depends on `ollama serve` | YES — automatic via LLM | Must be running |
| Codex bridge (file) | available | Channel file OK | YES — `ask codex to X` / `/ask-codex` | Codex process may not be running |
| Codex watcher | available | File OK | YES — checked on each input | None |
| Claude channel | available | Depends on window/CLI | YES — `/ask-claude X` | Must have window open or CLI |
| ChatGPT relay | available (if file exists) | Bridge file OK | YES — "ChatGPT says..." relay | Noah-mediated only |
| Drive Scope | available | Importable + callable | YES — wired into executor | None |
| Actuation Engine | available | Importable | YES — `/actuate window \| text` | pyautogui may not be installed |
| tools/executor.py | available | Importable | YES — scope-gated dispatch | None |
| Resident Console | degraded | oracle_desktop.py present | YES — fallback to core/oracle.py | None |
| Voice / TTS | available | pyttsx3 real TTS path exists | YES — `/voice on\|off` | pyttsx3 must be installed |
| scan/search tools | available | Files present | YES — via executor scope gate | None |
| Vision | unknown | Not probed (intentional) | NO | Runtime availability deferred |

**Probe notes:**
- Codex bridge is marked available when `oracle_codex_channel.py` exists.  This is correct
  for the file channel.  Whether the Codex *process* is running is reported by `/doctor`
  separately (tasklist check).
- Actuation Engine marks available when `actuation_engine.py` imports cleanly.  pyautogui
  availability is probed separately and reported in the blocker column.
- Vision is intentionally "unknown" — the VL model wire-up pass has not occurred.

---

## Area 3 — Action Routing

### Trace for "use Codex to inspect the repo" (FIXED)
| Step | Before fix | After fix |
|------|-----------|-----------|
| Cognitive kernel | KERNEL_DEFER (no block) | KERNEL_DEFER (no block) |
| NL parser | **NO MATCH** — "use codex" not in patterns | MATCH — routes to `ask_codex` handler |
| Handler | Fell to qwen (can't dispatch) | `oracle_codex_channel.send_to_codex()` called |
| User sees | qwen hallucinating a response | `[CODEX CHANNEL] Task written to ...` |

### Trace for "what should we commit next" (FIXED)
| Step | Before fix | After fix |
|------|-----------|-----------|
| Cognitive kernel | `evaluate_action()` hits "commit" → INTENT_APPROVAL_REQUIRED | `_is_pure_question()` detects question starter → bypasses policy |
| Oracle output | `[APPROVAL REQUIRED]` + policy summary | Falls through to LLM |
| User sees | Blocked message, no answer | qwen answers the question |

---

## Area 4 — Over-Gating Audit

### Was blocked, now fixed
These were blocked by `milestone_policy.py`'s word-matching before reaching the LLM:

| Input | Blocked keyword | Fix applied |
|-------|----------------|-------------|
| "what should we commit next" | `commit` | Question-bypass in cognitive_kernel |
| "what is the cloud architecture" | `cloud` | Question-bypass |
| "explain the governance model" | `governance` | Question-bypass |
| "what shared resources do we have" | `share` (via `_OUTBOUND_WORDS`) | Question-bypass |
| "how does git push work" | `push` | Question-bypass |

### Still correctly blocked (requires approval)
These should require approval — governance is correct for these:

| Input | Reason |
|-------|--------|
| "delete all the files" | destructive action |
| "push to production now" | outbound/commit |
| "upload this to cloud storage" | outbound |
| "commit the changes" | code_commit (no question starter) |
| "approve path C:\Users" | scope_expansion |

### Edge case: "pull up the repo status"
Starts with "pull" (a verb, not a question word) — not caught by the bypass.
Use "what is the repo status?" instead, or `/status`.

### Safe without approval (always worked, no change needed)
- `/capabilities` `/missing-capabilities` `/pending` `/channel` `/read-codex`
- `/project-state` `/ps` `/cycle` `/runtime` `/session`
- `talk to me` / conversational chat
- `ask codex to <task>` / `ask claude to <task>`
- `remember this: <fact>`
- `/doctor` (new)

---

## Area 5 — Tool Invocation Reality

| Tool | Real callable function | Smoke tested | Live command |
|------|----------------------|-------------|--------------|
| Repo inspection | `oracle_codex_channel.send_to_codex()` | YES (4/4) | `ask codex to inspect the repo` |
| File read | `tools/executor.execute_tool("read_file", ...)` | YES (20/20) | automatic via LLM |
| File write | `tools/executor.execute_tool("write_file", ...)` | YES (20/20) | requires Noah approval |
| Codex handoff | `oracle_codex_channel.send_to_codex()` | YES (4/4) | `/ask-codex <task>` |
| Local model (Ollama) | `llm.chat_local()` | YES (8/8 kernel) | automatic — every WORK turn |
| Claude handoff | `claude_code_bridge.type_into_claude()` | YES (16/16) | `/ask-claude <task>` |
| ChatGPT relay | `chatgpt_bridge.get_bridge().bridge()` | Bridge file present | `ChatGPT says...` relay |
| Status report | `get_oracle_status()` + `/doctor` | YES (45/45 doctor) | `/doctor` (new) |
| Pending queue | `approval_center.list_pending()` | YES (approval_center tests) | `/pending` |

---

## Area 6 — Resident Loop Audit

| Feature | Status | Notes |
|---------|--------|-------|
| Startup banner | **WORKING** | Banner + wake report on boot |
| Live state display | **WORKING** | Wake report shows mode/project/pending/next_safe |
| Command loop | **WORKING** | Input → classify → route → LLM/tool/shortcut |
| Action loop | **WORKING** | `oracle_loop.py` — "start loop" / "stop loop" |
| TTS / Speech | **WORKING** | `pyttsx3` via background thread. Real TTS. NOT simulated. |
| Voice toggle | **WORKING** | `/voice on\|off` persists to `Memory/voice_state.json` |
| Codex watcher | **PARTIAL** | Checked on each user input only. No background poll thread. |
| Background watcher | **NOT BUILT** | No daemon thread polling channels between inputs. |
| Event polling | **NOT BUILT** | ORACLE does not self-interrupt. Waits for Noah to type. |

**Voice is real.** `pyttsx3` Windows TTS engine via background thread. ORACLE speaks
when voice is enabled. Toggle with `/voice on` or `/voice off`.

**ORACLE does not self-interrupt.** Between Noah's inputs, ORACLE is idle.
She does not autonomously check Codex/Claude channels in a background thread.
The "loop" mode (`oracle_loop.py`) runs cycles on a timer but does not inject
console output while Noah is mid-conversation.

---

## Area 7 — Failure Visibility

| Failure point | Before | After |
|--------------|--------|-------|
| Hard-approval block | Shows "[APPROVAL REQUIRED]" + policy summary | Same — plus `needed_capability`, `exact_request`, `safest_next` now shown |
| Scope gate block | Returns BLOCKED string; `_scope_blocked_to_ask()` converts to freedom-to-ask phrase | Working |
| Codex channel error | Prints `[codex-channel error: ...]` | Working |
| Claude unavailable | `[CLAUDE UNAVAILABLE]` + manual paste prompt | Working |
| Ollama down | LLM call fails → `[Error: ...]` message | Working |
| Hallucination detection | `_detect_hallucination()` → `[BLOCKED]` + capability gap | Working |
| `/doctor` missing tool | Now shows blocker + fix in truth table | **NEW** |

**Silent failure still possible:** If Ollama is running but the model is not pulled,
the error from `chat_local()` surfaces as a generic `[Error: ...]`.  The fix is to
add model-existence check to `_probe_ollama()` (deferred — would require `ollama list`
subprocess call).

---

## Changes Made This Pass

### Files changed
| File | Change |
|------|--------|
| `core/oracle_doctor.py` | **NEW** — 45/45 smoke tests; live probe truth table |
| `core/cognitive_kernel.py` | Added `_is_pure_question()` + `_QUESTION_STARTERS` / `_QUESTION_ACTION_OVERRIDES` + bypass in `classify_input()` |
| `core/oracle.py` | Added `/doctor` `/audit-runtime` `/check-tools` `/health` commands; added "use codex" + "send to codex" NL patterns; updated `/help` with full command list |

### What was broken (not just over-gated)
1. "use codex to inspect the repo" — routed to qwen, not Codex
2. No `/doctor` command — no way to see what actually works

### What was only over-gated (now fixed)
1. "what should we commit next" — question about a concept, blocked as if it were an action
2. "what is the cloud architecture" — blocked by "cloud" keyword
3. "explain the governance model" — blocked by "governance" keyword
4. Similar for: "what shared resources", "how does git push work", etc.

### What tools are truly working (live probe)
- Drive Scope ✓
- tools/executor.py ✓
- oracle_codex_channel.py (file channel) ✓
- oracle_codex_watcher.py ✓
- Voice/TTS via pyttsx3 ✓
- Cognitive kernel ✓
- Milestone policy ✓
- Capability registry ✓
- Approval center ✓

### What tools are registered but conditionally working
- **Ollama** — working only if `ollama serve` is running
- **Claude channel** — working only if Claude Desktop window open or `claude` CLI installed
- **Actuation Engine** — importable; pyautogui may not be installed
- **ChatGPT relay** — file bridge present; relies on Noah relaying messages

### Voice / TTS
**Real TTS exists.** `pyttsx3` uses Windows SAPI voices. Runs in a background thread
so it never blocks the console. ORACLE speaks short acknowledgements ("I'm up.",
"Sent to Claude.", "Remembered."). Toggle with `/voice on` / `/voice off`.
ORACLE does **not** have continuous speech recognition (STT).

### Tests run
- 45/45 oracle_doctor
- 16/16 oracle (actuation + intent-router)
- 8/8 cognitive_kernel
- 8/8 milestone_policy
- 8/8 capability_registry
- 46/46 project_state
- 20/20 executor
- 22/22 governance

---

## Recommended Fixes — Priority Order

| Priority | Fix | Effort | Risk |
|----------|-----|--------|------|
| **DONE** | `/doctor` live probe command | Low | None |
| **DONE** | Question bypass for over-gating | Low | None |
| **DONE** | "use codex to X" NL pattern | Trivial | None |
| P1 | Add model-pull check to Ollama probe (`ollama list`) | Low | None |
| P1 | Add background Codex watcher thread (check channel every N seconds) | Medium | None |
| P2 | `_COMMIT_WORDS` refinement: block "commit the changes" but allow "git commit tutorial" | Low | Regression risk |
| P2 | Wire `detect_need()` to route "inspect/review/check the repo" to Codex | Low | None |
| P3 | `/help` completeness — already updated in this pass | Done | None |
| P4 | Background watcher loop that surfaces Claude/Codex replies without user input | Medium | None |
| P5 | STT / voice input | High | Out of scope |

---

## Commit Message

```
fix(operational): add /doctor probe, fix over-gating, add 'use codex' NL pattern

- core/oracle_doctor.py: new live capability truth table (/doctor command);
  probes Ollama, Codex bridge, Claude channel, Drive Scope, actuation, TTS,
  and scan/search tools; reports routing gaps and over-gated examples;
  45/45 smoke tests.
- core/cognitive_kernel.py: add _is_pure_question() bypass — conversational
  questions starting with what/how/why/explain/describe no longer trigger
  hard-approval even if they contain commit/cloud/governance/pull keywords.
  Destructive action verbs still correctly gated.
- core/oracle.py: wire /doctor + /audit-runtime + /check-tools + /health;
  add 'use codex to X' and 'send to codex' NL patterns; expand /help to
  show full command list.
Tests: 45/45 doctor, 16/16 oracle, 8/8 cognitive_kernel, 8/8 milestone_policy,
       8/8 capability_registry, 46/46 project_state, 20/20 executor, 22/22 governance
```
