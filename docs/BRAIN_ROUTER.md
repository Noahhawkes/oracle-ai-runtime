# ORACLE Brain Router v0.1
## `core/brain_router.py`

---

## The Problem This Solves

ORACLE was routing every task to qwen2.5:7b (LOCAL_SMALL).

- "Summarize this message" → qwen2.5:7b ✓ reliable
- "Open Chrome and navigate to ChatGPT" → qwen2.5:7b ✗ hallucinates success
- "Design the semantic_ui_bridge architecture" → qwen2.5:7b ✗ shallow output
- "Approve this payment" → qwen2.5:7b ✗ should never reach an LLM

The 7B model predicts what *should have happened* instead of verifying what *did* happen. That is not a bug in the model — that is what language models do. The fix is not to blame the model. The fix is to stop asking it to do things it is not reliable enough to do.

---

## Core Law

> **No model may claim an action succeeded unless verification evidence exists.**

This is a hard rule. Not a guideline. Not aspirational.

- Verified = screen hash changed, UI element found, test passed, commit exists, user confirmed
- Predicted = model generated text saying it worked

These are not the same. The router enforces the distinction.

---

## The Five Cognitive Engines

| Engine | Name | What it does | What it may NOT do |
|---|---|---|---|
| `LOCAL_SMALL` | qwen2.5:7b / llama3.2 | Summarize, classify, compress, generate draft proposals | Desktop control, code architecture, financial decisions, claim verified completion |
| `LOCAL_DETERMINISTIC` | Pure Python rules | Policy decisions, approval gates, project state updates, risk classification | LLM inference, action execution |
| `REMOTE_STRONG` | Claude Sonnet / GPT-4o | Complex architecture, debugging, code generation, strategic planning, multi-document synthesis | Execute actions directly, claim desktop success without verification |
| `HUMAN_SOVEREIGN` | Noah Hawkes | Final approval on all irreversible, external, or high-stakes actions | Nothing — Noah holds 51% |
| `ACTUATION_ENGINE` | verified desktop execution layer | All desktop actions (click, type, navigate, focus, screenshot) | Proceed without screen hash verification, skip approval gate for irreversible actions |

---

## Routing Priority Order

Every task passes through this cascade. First match wins.

```
1. UNKNOWN + no preferred engine     → BLOCKED → HUMAN_SOVEREIGN
2. financial / sensitive identity / external send / critical sensitivity
                                     → HUMAN_SOVEREIGN (approval required)
3. desktop_action                    → ACTUATION_ENGINE (verification required)
4. policy_decision / project_state   → LOCAL_DETERMINISTIC
5. code_architecture / debug / high complexity
                                     → REMOTE_STRONG (or blocked if unavailable)
6. summarize / classify / compress / generate candidate + low complexity
                                     → LOCAL_SMALL
7. anything else                     → BLOCKED → HUMAN_SOVEREIGN
```

---

## Task Types

| Task type | Default engine | Notes |
|---|---|---|
| `summarize` | LOCAL_SMALL | Low-complexity only |
| `classify` | LOCAL_SMALL | Low-complexity only |
| `compress_memory` | LOCAL_SMALL | Low-complexity only |
| `generate_candidate` | LOCAL_SMALL | Produces draft — not a verified result |
| `code_architecture` | REMOTE_STRONG | Multi-step reasoning beyond 7B capacity |
| `debug_failure` | REMOTE_STRONG | Same reason |
| `desktop_action` | ACTUATION_ENGINE | LOCAL_SMALL explicitly forbidden |
| `policy_decision` | LOCAL_DETERMINISTIC | No LLM judgment |
| `project_state_update` | LOCAL_DETERMINISTIC | Use project_state.py API |
| `financial_review` | HUMAN_SOVEREIGN | Always requires Noah |
| `sensitive_identity` | HUMAN_SOVEREIGN | Always requires Noah |
| `external_message` | HUMAN_SOVEREIGN | Always requires Noah |
| `unknown` | BLOCKED | No engine guesses |

---

## What LOCAL_SMALL May NOT Do

This is an explicit list, not a default fallback.

```python
LOCAL_SMALL_FORBIDDEN_TASKS = {
    TASK_DESKTOP_ACTION,
    TASK_CODE_ARCHITECTURE,
    TASK_DEBUG_FAILURE,
    TASK_FINANCIAL_REVIEW,
    TASK_SENSITIVE_IDENTITY,
    TASK_EXTERNAL_MESSAGE,
    TASK_POLICY_DECISION,
}
```

Any call to `can_local_small_handle()` with these task types returns `(False, <reason>)` immediately. No exceptions.

Additionally, LOCAL_SMALL is restricted from high-complexity tasks even within its allowed task types (summarize, classify, compress, generate candidate). COMPLEXITY_MEDIUM and above bump to REMOTE_STRONG.

---

## BrainTask Fields

```python
@dataclass
class BrainTask:
    id: str                                  # auto-generated 8-char hex
    task_type: str                           # one of the TASK_* constants
    summary: str                             # plain-text description
    input_source: str                        # where the task came from
    sensitivity: str                         # low / medium / high / critical
    complexity: str                          # trivial / low / medium / high / critical
    requires_reality_verification: bool      # must verify screen state before success claim
    requires_external_action: bool           # affects something outside local machine
    requires_code_change: bool               # modifies source files
    requires_human_approval: bool            # Noah must approve before execution
    preferred_engine: str                    # hint — router may override
    created_at: str                          # ISO timestamp
```

---

## BrainRouteDecision Fields

```python
@dataclass
class BrainRouteDecision:
    task_id: str
    selected_engine: str        # the engine to use
    reason: str                 # why this engine was chosen
    allowed: bool               # False = blocked
    approval_required: bool     # True = Noah must approve before proceeding
    approval_reason: str
    blocked: bool               # True = cannot route at all
    block_reason: str
    fallback_engine: str        # suggested fallback if selected_engine unavailable
    confidence: float           # 0.0 – 1.0
    unknowns: list              # preserved — not inferred
    constraints: list           # what the selected engine may NOT do in this task
    created_at: str
```

---

## API

```python
from brain_router import (
    BrainTask, BrainRouteDecision,
    route_task,
    can_local_small_handle,
    requires_strong_model,
    requires_human,
    requires_deterministic,
    requires_actuation,
    explain_route,
    create_task_from_text,
    get_engine_description,
    # Engine constants
    ENGINE_LOCAL_SMALL,
    ENGINE_LOCAL_DETERMINISTIC,
    ENGINE_REMOTE_STRONG,
    ENGINE_HUMAN_SOVEREIGN,
    ENGINE_ACTUATION,
    # Task type constants
    TASK_SUMMARIZE, TASK_CLASSIFY, TASK_DESKTOP_ACTION,
    TASK_CODE_ARCHITECTURE, TASK_POLICY_DECISION, ...
)

# Route a task
task = BrainTask(
    task_type=TASK_DESKTOP_ACTION,
    summary="Click the ChatGPT input field and type the message",
    requires_reality_verification=True,
    complexity=COMPLEXITY_MEDIUM,
)
decision = route_task(task)
print(decision.explain())

# Route from plain text
task = create_task_from_text("open chrome and navigate to chatgpt.com")
decision = route_task(task)
# → ACTUATION_ENGINE, verification required, LOCAL_SMALL forbidden

# Check if local small can handle something
ok, reason = can_local_small_handle(task)
# ok=False, reason="LOCAL_SMALL is explicitly forbidden from task type 'desktop_action'..."
```

---

## REPL Command

```
/route-task <describe what you want to do>
```

Classifies the text into a task, runs the router, and prints the routing decision with engine, reason, constraints, and approval requirements.

Example:
```
> /route-task open chrome and go to chatgpt

  Task text  : open chrome and go to chatgpt
  Classified : desktop_action  complexity=medium  sensitivity=medium

  [BRAIN ROUTE DECISION — task a3f1b2c9]
  Engine   : ACTUATION_ENGINE
  Allowed  : YES
  Blocked  : NO
  Reason   : Desktop actions must go through ACTUATION_ENGINE with verification. LOCAL_SMALL cannot claim desktop action success.
  Approval : not required
  Fallback : (none)
  Confidence: 90%
  Constraints (what this engine may NOT do):
    [RESTRICTED] LOCAL_SMALL may not claim this action succeeded
    [RESTRICTED] Screen hash verification required before reporting completion
    [RESTRICTED] Approval gate required for irreversible actions
    [RESTRICTED] Notepad is blocked as fallback
```

---

## CLI

```bash
python core/brain_router.py --smoke
python core/brain_router.py --route "open chrome and navigate to chatgpt"
python core/brain_router.py --engines
```

---

## Smoke Tests

34/34 — all passing.

Covers:
- Summary → LOCAL_SMALL
- Desktop action → ACTUATION_ENGINE + verification + LOCAL_SMALL restriction
- Code architecture → REMOTE_STRONG or blocked (never LOCAL_SMALL)
- Financial → HUMAN_SOVEREIGN + approval required
- Policy → LOCAL_DETERMINISTIC + no LLM constraint
- Unknown → blocked + zero confidence + HUMAN_SOVEREIGN escalation
- LOCAL_SMALL explicitly rejects desktop_action with explanation
- External message → HUMAN_SOVEREIGN + approval required
- `create_task_from_text`: click, summarize, architecture, purchase, send email
- `explain_route` builds without crash, contains engine name
- `get_engine_description` covers all 5 engines
- Classify → LOCAL_SMALL
- Project state → LOCAL_DETERMINISTIC
- HIGH complexity summarize rejected from LOCAL_SMALL

---

## Design Notes

**Why not train a better model?**
Training a new foundation model does not happen tonight and doesn't need to. The routing layer is the intelligence. qwen2.5:7b is excellent at what it is allowed to do. It is forbidden from what it is not reliable enough to do. That is the complete solution.

**Why deterministic routing?**
The router itself uses no LLM. It is pure Python keyword heuristics and rule tables. If the router needed an LLM to decide which LLM to call, we would have an infinite regress problem. Deterministic routing is fast, auditable, and never hallucinates.

**Why are unknowns preserved?**
A routing decision that says "we don't know if REMOTE_STRONG is available" is more honest and more useful than one that silently falls back to a weaker model without explanation.

---

*Last updated: 2026-06-07 | ORACLE.AI — Brain Router v0.1*
