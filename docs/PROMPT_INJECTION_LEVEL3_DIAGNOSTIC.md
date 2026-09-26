# ORACLE Prompt Injection Level 3 Diagnostic

Status: Active
Scope: Web chat, core web engine, local companion prompt boundary
Sandbox: Not touched

## Decision

Prompt-injection text is treated as untrusted user content, even when it arrives
from Noah's browser frontend. It may be discussed, but it cannot acquire
authority over system/developer instructions, approval gates, tools, memory,
Git, external sends, or sandbox writes.

## What Changed

- `core/prompt_injection_guard.py` performs deterministic, side-effect-free
  detection for instruction overrides, hidden-prompt exfiltration, forged
  approval, embedded system-role text, and tool/action escalation.
- `oracle_server.py` interrupts detected attacks before route classification,
  NOAH_DIRECT, local model calls, or sandbox commands.
- `core/oracle.py` applies the same interrupt before web-engine model/client
  setup.
- `core/conversation_mode.py` includes the prompt boundary in the companion
  system prompt and returns the same guard response if called directly.
- `core/context_loader.py` now trains both local and cloud system prompts with
  the prompt boundary.

## Required Guard Output

The guard response must report:

- `model_called: false`
- `actions_executed: 0`
- `sandbox_write: false`
- `memory_promotion: false`
- `external_send: false`
- `git_push: false`

## Tests

Relevant test file:

```powershell
python -m pytest tests/test_prompt_injection_guard.py tests/test_routing_precedence.py -q
```

This diagnostic is outside ORACLE's sandbox. ORACLE's sandbox remains her
workbench; this patch changes only the runtime boundary around prompts.
