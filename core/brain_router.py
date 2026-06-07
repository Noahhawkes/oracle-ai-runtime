"""
core/brain_router.py — ORACLE Brain Router v0.1

Core principle:
  ORACLE's intelligence is not one LLM.
  ORACLE's intelligence is a governed system of cognitive engines,
  each allowed to do exactly what it is reliable enough to do.

The problem this solves:
  qwen2.5:7b was being asked to do everything: summarize, plan, execute
  desktop actions, verify reality, write code, and make strategic decisions.
  It is good at some of these. It is unreliable at others.
  It hallucinates success because it predicts what should have happened
  instead of verifying what did happen.

The fix:
  Route every task to the engine that can reliably handle it.
  Never let LOCAL_SMALL claim a desktop action succeeded.
  Never let any model bypass the approval gate.
  Never let reality verification be skipped.

Hard law:
  No model may claim an action succeeded unless verification evidence exists.
"""

import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

# ── Engines ────────────────────────────────────────────────────────────────────

ENGINE_LOCAL_SMALL       = "LOCAL_SMALL"        # qwen2.5:7b, llama3.2, etc.
ENGINE_LOCAL_DETERMINISTIC = "LOCAL_DETERMINISTIC"  # pure Python policy/rules
ENGINE_REMOTE_STRONG     = "REMOTE_STRONG"      # Claude Sonnet, GPT-4o, Gemini
ENGINE_HUMAN_SOVEREIGN   = "HUMAN_SOVEREIGN"    # Noah's approval required
ENGINE_ACTUATION         = "ACTUATION_ENGINE"   # verified desktop execution layer

ALL_ENGINES = [
    ENGINE_LOCAL_SMALL,
    ENGINE_LOCAL_DETERMINISTIC,
    ENGINE_REMOTE_STRONG,
    ENGINE_HUMAN_SOVEREIGN,
    ENGINE_ACTUATION,
]

# ── Task types ─────────────────────────────────────────────────────────────────

TASK_SUMMARIZE          = "summarize"
TASK_CLASSIFY           = "classify"
TASK_COMPRESS_MEMORY    = "compress_memory"
TASK_GENERATE_CANDIDATE = "generate_candidate"
TASK_CODE_ARCHITECTURE  = "code_architecture"
TASK_DEBUG_FAILURE      = "debug_failure"
TASK_DESKTOP_ACTION     = "desktop_action"
TASK_POLICY_DECISION    = "policy_decision"
TASK_PROJECT_STATE      = "project_state_update"
TASK_FINANCIAL_REVIEW   = "financial_review"
TASK_SENSITIVE_IDENTITY = "sensitive_identity"
TASK_EXTERNAL_MESSAGE   = "external_message"
TASK_UNKNOWN            = "unknown"

# ── Sensitivity levels ────────────────────────────────────────────────────────

SENSITIVITY_LOW      = "low"
SENSITIVITY_MEDIUM   = "medium"
SENSITIVITY_HIGH     = "high"
SENSITIVITY_CRITICAL = "critical"

# ── Complexity levels ─────────────────────────────────────────────────────────

COMPLEXITY_TRIVIAL  = "trivial"   # one-line answer, no state needed
COMPLEXITY_LOW      = "low"       # short text transform, no reasoning chain
COMPLEXITY_MEDIUM   = "medium"    # multi-step reasoning, some context
COMPLEXITY_HIGH     = "high"      # architecture, planning, multi-document
COMPLEXITY_CRITICAL = "critical"  # financial, legal, medical, irreversible

# ── What LOCAL_SMALL is explicitly allowed to do ───────────────────────────────

LOCAL_SMALL_ALLOWED_TASKS = {
    TASK_SUMMARIZE,
    TASK_CLASSIFY,
    TASK_COMPRESS_MEMORY,
    TASK_GENERATE_CANDIDATE,
}

LOCAL_SMALL_ALLOWED_COMPLEXITY = {
    COMPLEXITY_TRIVIAL,
    COMPLEXITY_LOW,
}

# LOCAL_SMALL may NEVER claim completion of these
LOCAL_SMALL_FORBIDDEN_TASKS = {
    TASK_DESKTOP_ACTION,
    TASK_CODE_ARCHITECTURE,
    TASK_DEBUG_FAILURE,
    TASK_FINANCIAL_REVIEW,
    TASK_SENSITIVE_IDENTITY,
    TASK_EXTERNAL_MESSAGE,
    TASK_POLICY_DECISION,
}

# Tasks that always require human approval regardless of engine
ALWAYS_HUMAN_TASKS = {
    TASK_FINANCIAL_REVIEW,
    TASK_SENSITIVE_IDENTITY,
    TASK_EXTERNAL_MESSAGE,
}

# Tasks that always require reality verification before success can be claimed
REQUIRES_VERIFICATION_TASKS = {
    TASK_DESKTOP_ACTION,
    TASK_EXTERNAL_MESSAGE,
    TASK_FINANCIAL_REVIEW,
}


# ── Data models ────────────────────────────────────────────────────────────────

@dataclass
class BrainTask:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    task_type: str = TASK_UNKNOWN
    summary: str = ""
    input_source: str = ""          # where the task came from
    sensitivity: str = SENSITIVITY_LOW
    complexity: str = COMPLEXITY_LOW
    requires_reality_verification: bool = False
    requires_external_action: bool = False
    requires_code_change: bool = False
    requires_human_approval: bool = False
    preferred_engine: str = ""      # hint — router may override
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def is_high_stakes(self) -> bool:
        return (
            self.sensitivity in (SENSITIVITY_HIGH, SENSITIVITY_CRITICAL)
            or self.complexity in (COMPLEXITY_HIGH, COMPLEXITY_CRITICAL)
            or self.requires_reality_verification
            or self.requires_external_action
            or self.requires_human_approval
        )


@dataclass
class BrainRouteDecision:
    task_id: str = ""
    selected_engine: str = ""
    reason: str = ""
    allowed: bool = True
    approval_required: bool = False
    approval_reason: str = ""
    blocked: bool = False
    block_reason: str = ""
    fallback_engine: str = ""
    confidence: float = 0.0
    unknowns: list = field(default_factory=list)
    constraints: list = field(default_factory=list)   # what the engine may NOT do
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def explain(self) -> str:
        lines = [
            "",
            f"  [BRAIN ROUTE DECISION — task {self.task_id}]",
            f"  Engine   : {self.selected_engine}",
            f"  Allowed  : {'YES' if self.allowed else 'NO'}",
            f"  Blocked  : {'YES — ' + self.block_reason if self.blocked else 'NO'}",
            f"  Reason   : {self.reason}",
            f"  Approval : {'REQUIRED — ' + self.approval_reason if self.approval_required else 'not required'}",
            f"  Fallback : {self.fallback_engine or '(none)'}",
            f"  Confidence: {int(self.confidence * 100)}%",
        ]
        if self.constraints:
            lines.append("  Constraints (what this engine may NOT do):")
            for c in self.constraints:
                lines.append(f"    [RESTRICTED] {c}")
        if self.unknowns:
            lines.append("  Unknowns:")
            for u in self.unknowns:
                lines.append(f"    [UNKNOWN] {u}")
        lines.append("")
        return "\n".join(lines)


# ── Routing logic ──────────────────────────────────────────────────────────────

def can_local_small_handle(task: BrainTask) -> tuple[bool, str]:
    """
    Return (can_handle, reason).
    LOCAL_SMALL is explicitly restricted — this is not a default fallback.
    """
    if task.task_type in LOCAL_SMALL_FORBIDDEN_TASKS:
        return False, (
            f"LOCAL_SMALL is explicitly forbidden from task type '{task.task_type}'. "
            f"It cannot claim completion of desktop actions, code architecture, "
            f"financial decisions, or external sends."
        )
    if task.task_type not in LOCAL_SMALL_ALLOWED_TASKS:
        return False, (
            f"Task type '{task.task_type}' is not in LOCAL_SMALL's allowed set. "
            f"Allowed: {sorted(LOCAL_SMALL_ALLOWED_TASKS)}"
        )
    if task.complexity not in LOCAL_SMALL_ALLOWED_COMPLEXITY:
        return False, (
            f"Complexity '{task.complexity}' exceeds LOCAL_SMALL's reliable range. "
            f"Use REMOTE_STRONG for medium/high/critical complexity tasks."
        )
    if task.sensitivity in (SENSITIVITY_HIGH, SENSITIVITY_CRITICAL):
        return False, (
            f"Sensitivity '{task.sensitivity}' requires stronger oversight. "
            f"LOCAL_SMALL may not handle high-sensitivity tasks."
        )
    if task.requires_reality_verification:
        return False, (
            "LOCAL_SMALL may not claim verified completion. "
            "Tasks requiring reality verification need ACTUATION_ENGINE "
            "or explicit external verification."
        )
    if task.requires_external_action:
        return False, "LOCAL_SMALL may not execute external actions."
    if task.requires_human_approval:
        return False, "Task requires human approval — route to HUMAN_SOVEREIGN first."
    return True, "Task is within LOCAL_SMALL's reliable capability range."


def requires_strong_model(task: BrainTask) -> tuple[bool, str]:
    """Return (requires, reason) for REMOTE_STRONG routing."""
    if task.task_type in (TASK_CODE_ARCHITECTURE, TASK_DEBUG_FAILURE):
        return True, f"'{task.task_type}' requires multi-step reasoning beyond 7B model capacity."
    if task.complexity in (COMPLEXITY_HIGH, COMPLEXITY_CRITICAL):
        return True, f"Complexity '{task.complexity}' requires REMOTE_STRONG."
    if task.task_type == TASK_DESKTOP_ACTION:
        return False, "Desktop actions route to ACTUATION_ENGINE, not REMOTE_STRONG."
    return False, "Task does not require strong model."


def requires_human(task: BrainTask) -> tuple[bool, str]:
    """Return (requires, reason) for HUMAN_SOVEREIGN routing."""
    if task.task_type in ALWAYS_HUMAN_TASKS:
        return True, f"Task type '{task.task_type}' always requires Noah's approval."
    if task.sensitivity == SENSITIVITY_CRITICAL:
        return True, "Critical sensitivity requires Noah's approval before any action."
    if task.requires_human_approval:
        return True, "Task was explicitly marked as requiring human approval."
    if task.requires_external_action and task.sensitivity in (SENSITIVITY_HIGH, SENSITIVITY_CRITICAL):
        return True, "High-sensitivity external action requires Noah's approval."
    return False, "Human approval not required for this task."


def requires_deterministic(task: BrainTask) -> tuple[bool, str]:
    """Return (requires, reason) for LOCAL_DETERMINISTIC routing."""
    if task.task_type == TASK_POLICY_DECISION:
        return True, "Policy decisions are always deterministic — no LLM judgment."
    if task.task_type == TASK_PROJECT_STATE:
        return True, "Project state updates are deterministic — use project_state.py API."
    return False, "Task does not require deterministic engine."


def requires_actuation(task: BrainTask) -> tuple[bool, str]:
    """Return (requires, reason) for ACTUATION_ENGINE routing."""
    if task.task_type == TASK_DESKTOP_ACTION:
        return True, (
            "Desktop actions must go through ACTUATION_ENGINE with verification. "
            "LOCAL_SMALL cannot claim desktop action success."
        )
    return False, "Task does not require actuation engine."


def route_task(task: BrainTask) -> BrainRouteDecision:
    """
    Core routing function. Takes a BrainTask and returns a BrainRouteDecision.

    Priority order:
      1. Block unknown/critical tasks
      2. Human sovereign (financial, external send, critical sensitivity)
      3. Actuation engine (desktop actions)
      4. Deterministic (policy, project state)
      5. Remote strong (code architecture, debug, high complexity)
      6. Local small (summarize, classify, compress — low complexity only)
      7. Block anything that doesn't fit cleanly
    """
    decision = BrainRouteDecision(task_id=task.id)

    # ── 0. Hard block: UNKNOWN with no preferred engine ───────────────────────
    if task.task_type == TASK_UNKNOWN and not task.preferred_engine:
        decision.blocked = True
        decision.allowed = False
        decision.block_reason = (
            "Task type is UNKNOWN and no preferred engine was specified. "
            "ORACLE does not guess at routing for unknown tasks. "
            "Classify the task or ask Noah for direction."
        )
        decision.selected_engine = ENGINE_HUMAN_SOVEREIGN
        decision.reason = "Unknown task blocked — escalate to Noah."
        decision.confidence = 0.0
        decision.unknowns.append("Task type is not classified")
        return decision

    # ── 1. Human sovereign ────────────────────────────────────────────────────
    needs_human, human_reason = requires_human(task)
    if needs_human:
        decision.selected_engine = ENGINE_HUMAN_SOVEREIGN
        decision.reason = human_reason
        decision.approval_required = True
        decision.approval_reason = human_reason
        decision.allowed = True
        decision.confidence = 0.99
        decision.constraints = [
            "No engine may proceed until Noah approves",
            "No external action may execute before approval",
        ]
        # Still offer a strong-model analysis if available
        if task.task_type in (TASK_FINANCIAL_REVIEW, TASK_DEBUG_FAILURE):
            decision.fallback_engine = ENGINE_REMOTE_STRONG
        return decision

    # ── 2. Actuation engine ───────────────────────────────────────────────────
    needs_actuation, actuation_reason = requires_actuation(task)
    if needs_actuation:
        decision.selected_engine = ENGINE_ACTUATION
        decision.reason = actuation_reason
        decision.allowed = True
        decision.confidence = 0.90
        decision.constraints = [
            "LOCAL_SMALL may not claim this action succeeded",
            "Screen hash verification required before reporting completion",
            "Approval gate required for irreversible actions",
            "Notepad is blocked as fallback",
        ]
        decision.requires_reality_verification = True
        if not task.requires_reality_verification:
            decision.unknowns.append(
                "Task was desktop_action but did not set requires_reality_verification=True — "
                "router is enforcing verification anyway."
            )
        # Flag if policy approval needed
        if task.sensitivity in (SENSITIVITY_HIGH, SENSITIVITY_CRITICAL):
            decision.approval_required = True
            decision.approval_reason = f"High-sensitivity desktop action requires Noah approval before execution."
        return decision

    # ── 3. Deterministic ─────────────────────────────────────────────────────
    needs_det, det_reason = requires_deterministic(task)
    if needs_det:
        decision.selected_engine = ENGINE_LOCAL_DETERMINISTIC
        decision.reason = det_reason
        decision.allowed = True
        decision.confidence = 0.99
        decision.constraints = [
            "No LLM inference — pure Python rules only",
            "No action execution — read/write state only",
        ]
        return decision

    # ── 4. Remote strong ──────────────────────────────────────────────────────
    needs_strong, strong_reason = requires_strong_model(task)
    if needs_strong:
        decision.selected_engine = ENGINE_REMOTE_STRONG
        decision.reason = strong_reason
        decision.allowed = True
        decision.confidence = 0.85
        decision.fallback_engine = ENGINE_LOCAL_SMALL  # draft only
        decision.constraints = [
            "May produce proposals and analysis",
            "May not execute actions directly",
            "May not claim desktop action succeeded without ACTUATION_ENGINE verification",
        ]
        if not _remote_strong_available():
            decision.allowed = False
            decision.blocked = True
            decision.block_reason = (
                "REMOTE_STRONG engine is not currently available "
                "(no API key or offline). "
                "This task cannot be reliably completed by LOCAL_SMALL. "
                "Options: provide API access, or ask Noah for direction."
            )
            decision.fallback_engine = ENGINE_HUMAN_SOVEREIGN
            decision.unknowns.append("REMOTE_STRONG availability is unknown at route time")
        return decision

    # ── 5. Local small ────────────────────────────────────────────────────────
    can_local, local_reason = can_local_small_handle(task)
    if can_local:
        decision.selected_engine = ENGINE_LOCAL_SMALL
        decision.reason = local_reason
        decision.allowed = True
        decision.confidence = 0.75
        decision.constraints = [
            "May not claim desktop action succeeded",
            "May not execute external actions",
            "May not make financial or legal decisions",
            "May not perform code architecture without REMOTE_STRONG review",
            "Output is a draft or proposal — not a verified result",
        ]
        return decision

    # ── 6. Cannot route cleanly — block and explain ───────────────────────────
    decision.blocked = True
    decision.allowed = False
    decision.block_reason = (
        f"Task could not be cleanly routed. "
        f"LOCAL_SMALL rejected: {local_reason} "
        f"REMOTE_STRONG not required or unavailable. "
        f"Human approval not triggered. "
        f"Task type: '{task.task_type}', complexity: '{task.complexity}', "
        f"sensitivity: '{task.sensitivity}'."
    )
    decision.selected_engine = ENGINE_HUMAN_SOVEREIGN
    decision.reason = "Unroutable task escalated to Noah."
    decision.confidence = 0.0
    decision.unknowns.append(f"No engine found for task_type={task.task_type}")
    return decision


def explain_route(decision: BrainRouteDecision) -> str:
    """Alias for decision.explain() — human-readable routing explanation."""
    return decision.explain()


# ── Task construction helpers ──────────────────────────────────────────────────

def create_task_from_text(text: str) -> BrainTask:
    """
    Classify a plain-text request into a BrainTask.
    Uses keyword heuristics — deterministic, no LLM needed.
    This is intentionally simple: the router itself is deterministic.
    """
    text_lower = text.lower().strip()
    task = BrainTask(summary=text[:120])

    # Desktop action signals
    if any(kw in text_lower for kw in (
        "click", "type into", "open chrome", "open app", "navigate to",
        "focus window", "paste into", "press enter", "screenshot",
        "desktop", "mouse", "keyboard", "window", "drag",
    )):
        task.task_type = TASK_DESKTOP_ACTION
        task.requires_reality_verification = True
        task.complexity = COMPLEXITY_MEDIUM
        task.sensitivity = SENSITIVITY_MEDIUM
        return task

    # Code architecture
    if any(kw in text_lower for kw in (
        "architecture", "design", "refactor", "build module", "implement",
        "create class", "write function", "debug", "fix bug", "error in",
        "why is this failing", "code review",
    )):
        task.task_type = TASK_CODE_ARCHITECTURE
        task.complexity = COMPLEXITY_HIGH
        task.sensitivity = SENSITIVITY_LOW
        return task

    # Financial / legal
    if any(kw in text_lower for kw in (
        "purchase", "buy", "payment", "billing", "invoice", "money",
        "legal", "contract", "tax", "financial",
    )):
        task.task_type = TASK_FINANCIAL_REVIEW
        task.requires_human_approval = True
        task.sensitivity = SENSITIVITY_CRITICAL
        task.complexity = COMPLEXITY_CRITICAL
        return task

    # External message
    if any(kw in text_lower for kw in (
        "send email", "send message", "post to", "submit form",
        "reply to", "dm ", "tweet", "slack message",
    )):
        task.task_type = TASK_EXTERNAL_MESSAGE
        task.requires_human_approval = True
        task.requires_external_action = True
        task.sensitivity = SENSITIVITY_HIGH
        return task

    # Policy / approval
    if any(kw in text_lower for kw in (
        "approve", "reject", "policy", "permission", "allow", "block",
        "gate", "compliance",
    )):
        task.task_type = TASK_POLICY_DECISION
        task.complexity = COMPLEXITY_LOW
        return task

    # Project state
    if any(kw in text_lower for kw in (
        "project state", "record blocker", "set next step", "mark complete",
        "update project", "resume prompt",
    )):
        task.task_type = TASK_PROJECT_STATE
        task.complexity = COMPLEXITY_LOW
        return task

    # Summarize / compress
    if any(kw in text_lower for kw in (
        "summarize", "summary", "compress", "tldr", "shorten", "condense",
        "digest",
    )):
        task.task_type = TASK_SUMMARIZE
        task.complexity = COMPLEXITY_LOW
        return task

    # Classify
    if any(kw in text_lower for kw in (
        "classify", "categorize", "label", "tag", "sort", "group",
        "which type", "what kind",
    )):
        task.task_type = TASK_CLASSIFY
        task.complexity = COMPLEXITY_LOW
        return task

    # Memory compression
    if any(kw in text_lower for kw in (
        "compress memory", "memory summary", "memory compression",
        "compact context",
    )):
        task.task_type = TASK_COMPRESS_MEMORY
        task.complexity = COMPLEXITY_LOW
        return task

    # Generate candidate
    if any(kw in text_lower for kw in (
        "draft", "propose", "candidate", "suggest", "generate idea",
        "create proposal",
    )):
        task.task_type = TASK_GENERATE_CANDIDATE
        task.complexity = COMPLEXITY_LOW
        return task

    # Debug failure
    if any(kw in text_lower for kw in (
        "debug", "diagnose", "why did", "failure", "crash", "exception",
        "traceback", "broke",
    )):
        task.task_type = TASK_DEBUG_FAILURE
        task.complexity = COMPLEXITY_HIGH
        return task

    # Unknown
    task.task_type = TASK_UNKNOWN
    task.complexity = COMPLEXITY_MEDIUM
    return task


# ── Availability check ────────────────────────────────────────────────────────

def _remote_strong_available() -> bool:
    """Check if a strong remote model is configured and reachable."""
    try:
        import os
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        local_mode = os.getenv("LOCAL_MODE", "false").lower() == "true"
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not local_mode and api_key and len(api_key) > 20:
            return True
        # Could also check for OpenAI key, Gemini key, etc.
        return False
    except Exception:
        return False


def get_engine_description(engine: str) -> str:
    descriptions = {
        ENGINE_LOCAL_SMALL: (
            "qwen2.5:7b (or similar). "
            "Reliable for: summarize, classify, compress, generate draft. "
            "Forbidden: desktop control, code architecture, financial decisions, "
            "claiming verified completion."
        ),
        ENGINE_LOCAL_DETERMINISTIC: (
            "Pure Python rules engine. No LLM inference. "
            "Reliable for: policy decisions, approval gates, project state updates, "
            "file cleanup candidates, risk classification."
        ),
        ENGINE_REMOTE_STRONG: (
            "Claude Sonnet / GPT-4o / Gemini. "
            "Reliable for: complex architecture, debugging, code generation, "
            "strategic planning, computer-use reasoning, multi-document synthesis."
        ),
        ENGINE_HUMAN_SOVEREIGN: (
            "Noah Hawkes. "
            "Required for: memory approval, action execution approval, destructive actions, "
            "external sends, purchases, public posting, commits, sensitive identity claims."
        ),
        ENGINE_ACTUATION: (
            "Verified desktop execution layer (semantic_ui_bridge + targeted_input). "
            "Required for: all desktop actions. "
            "Must verify screen state before reporting success. "
            "Never bypasses policy or approval gate."
        ),
    }
    return descriptions.get(engine, f"Unknown engine: {engine}")


# ── Smoke test ────────────────────────────────────────────────────────────────

def _smoke_test() -> bool:
    print("=" * 60)
    print("brain_router.py — Smoke Test")
    print("=" * 60)

    passed = 0
    failed = 0

    def check(label: str, condition: bool, detail: str = ""):
        nonlocal passed, failed
        ok = condition
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        if not ok and detail:
            print(f"         {detail}")
        if ok:
            passed += 1
        else:
            failed += 1

    # 1. Simple summary routes to LOCAL_SMALL
    t1 = BrainTask(
        task_type=TASK_SUMMARIZE,
        summary="Summarize this paragraph",
        complexity=COMPLEXITY_LOW,
        sensitivity=SENSITIVITY_LOW,
    )
    d1 = route_task(t1)
    check("Simple summary routes to LOCAL_SMALL", d1.selected_engine == ENGINE_LOCAL_SMALL,
          f"got {d1.selected_engine}")
    check("Summary route is allowed", d1.allowed)
    check("LOCAL_SMALL has output constraints",
          any("draft" in c.lower() or "proposal" in c.lower() for c in d1.constraints))

    # 2. Desktop action routes to ACTUATION_ENGINE
    t2 = BrainTask(
        task_type=TASK_DESKTOP_ACTION,
        summary="Click the ChatGPT input field and type message",
        complexity=COMPLEXITY_MEDIUM,
        requires_reality_verification=True,
    )
    d2 = route_task(t2)
    check("Desktop action routes to ACTUATION_ENGINE",
          d2.selected_engine == ENGINE_ACTUATION, f"got {d2.selected_engine}")
    check("Desktop action requires verification", d2.requires_reality_verification)
    check("Desktop action has LOCAL_SMALL restriction",
          any("LOCAL_SMALL" in c for c in d2.constraints))

    # 3. Code architecture routes to REMOTE_STRONG (when available)
    # Force remote unavailable for deterministic test
    t3 = BrainTask(
        task_type=TASK_CODE_ARCHITECTURE,
        summary="Design the semantic UI bridge architecture",
        complexity=COMPLEXITY_HIGH,
    )
    d3 = route_task(t3)
    check("Code architecture routes to REMOTE_STRONG or is blocked cleanly",
          d3.selected_engine in (ENGINE_REMOTE_STRONG, ENGINE_HUMAN_SOVEREIGN),
          f"got {d3.selected_engine}")
    check("Code architecture does not route to LOCAL_SMALL",
          d3.selected_engine != ENGINE_LOCAL_SMALL, f"got {d3.selected_engine}")

    # 4. Memory/financial approval routes to HUMAN_SOVEREIGN
    t4 = BrainTask(
        task_type=TASK_FINANCIAL_REVIEW,
        summary="Approve payment of $500 for OpenAI API credits",
        complexity=COMPLEXITY_CRITICAL,
        sensitivity=SENSITIVITY_CRITICAL,
        requires_human_approval=True,
    )
    d4 = route_task(t4)
    check("Financial review routes to HUMAN_SOVEREIGN",
          d4.selected_engine == ENGINE_HUMAN_SOVEREIGN, f"got {d4.selected_engine}")
    check("Financial review requires approval", d4.approval_required)

    # 5. Policy decision routes to LOCAL_DETERMINISTIC
    t5 = BrainTask(
        task_type=TASK_POLICY_DECISION,
        summary="Should this action be allowed based on current policy?",
        complexity=COMPLEXITY_LOW,
    )
    d5 = route_task(t5)
    check("Policy decision routes to LOCAL_DETERMINISTIC",
          d5.selected_engine == ENGINE_LOCAL_DETERMINISTIC, f"got {d5.selected_engine}")
    check("Deterministic route has no LLM constraint",
          any("LLM" in c for c in d5.constraints))

    # 6. Unknown task is blocked or escalated to Noah
    t6 = BrainTask(
        task_type=TASK_UNKNOWN,
        summary="Do the thing",
    )
    d6 = route_task(t6)
    check("Unknown task is blocked", d6.blocked)
    check("Unknown task escalates to HUMAN_SOVEREIGN",
          d6.selected_engine == ENGINE_HUMAN_SOVEREIGN, f"got {d6.selected_engine}")
    check("Unknown task has zero confidence", d6.confidence == 0.0)

    # 7. LOCAL_SMALL cannot claim desktop action succeeded
    can, reason = can_local_small_handle(BrainTask(
        task_type=TASK_DESKTOP_ACTION,
        requires_reality_verification=True,
    ))
    check("LOCAL_SMALL cannot handle desktop_action", not can)
    check("Rejection reason mentions verification or forbidden",
          "forbidden" in reason.lower() or "verification" in reason.lower(),
          f"got: {reason}")

    # 8. High sensitivity requires approval
    t8 = BrainTask(
        task_type=TASK_EXTERNAL_MESSAGE,
        summary="Send the project proposal to the client",
        sensitivity=SENSITIVITY_HIGH,
        requires_external_action=True,
        requires_human_approval=True,
    )
    d8 = route_task(t8)
    check("External message routes to HUMAN_SOVEREIGN",
          d8.selected_engine == ENGINE_HUMAN_SOVEREIGN, f"got {d8.selected_engine}")
    check("External message requires approval", d8.approval_required)

    # 9. create_task_from_text classifications
    task_click = create_task_from_text("click the submit button on the form")
    check("'click' text maps to TASK_DESKTOP_ACTION",
          task_click.task_type == TASK_DESKTOP_ACTION, f"got {task_click.task_type}")

    task_sum = create_task_from_text("summarize the last 5 messages")
    check("'summarize' text maps to TASK_SUMMARIZE",
          task_sum.task_type == TASK_SUMMARIZE, f"got {task_sum.task_type}")

    task_arch = create_task_from_text("design the architecture for the brain router")
    check("'architecture' text maps to TASK_CODE_ARCHITECTURE",
          task_arch.task_type == TASK_CODE_ARCHITECTURE, f"got {task_arch.task_type}")

    task_pay = create_task_from_text("purchase 100 API credits")
    check("'purchase' text maps to TASK_FINANCIAL_REVIEW",
          task_pay.task_type == TASK_FINANCIAL_REVIEW, f"got {task_pay.task_type}")

    task_send = create_task_from_text("send email to the client")
    check("'send email' text maps to TASK_EXTERNAL_MESSAGE",
          task_send.task_type == TASK_EXTERNAL_MESSAGE, f"got {task_send.task_type}")

    # 10. explain_route builds without crash
    explanation = explain_route(d1)
    check("explain_route builds without crash", bool(explanation))
    check("Explanation contains engine name", ENGINE_LOCAL_SMALL in explanation)

    # 11. get_engine_description covers all engines
    for engine in ALL_ENGINES:
        desc = get_engine_description(engine)
        check(f"get_engine_description({engine}) returns content", bool(desc) and len(desc) > 10)

    # 12. Classify task routes to LOCAL_SMALL
    t12 = BrainTask(
        task_type=TASK_CLASSIFY,
        summary="Classify this email as spam or not spam",
        complexity=COMPLEXITY_LOW,
        sensitivity=SENSITIVITY_LOW,
    )
    d12 = route_task(t12)
    check("Classify task routes to LOCAL_SMALL",
          d12.selected_engine == ENGINE_LOCAL_SMALL, f"got {d12.selected_engine}")

    # 13. Project state update routes to LOCAL_DETERMINISTIC
    t13 = BrainTask(
        task_type=TASK_PROJECT_STATE,
        summary="Record blocker: pywinauto not installed",
        complexity=COMPLEXITY_LOW,
    )
    d13 = route_task(t13)
    check("Project state routes to LOCAL_DETERMINISTIC",
          d13.selected_engine == ENGINE_LOCAL_DETERMINISTIC, f"got {d13.selected_engine}")

    # 14. HIGH complexity summarize bumps out of LOCAL_SMALL
    t14 = BrainTask(
        task_type=TASK_SUMMARIZE,
        summary="Summarize 50 documents into a strategy report",
        complexity=COMPLEXITY_HIGH,
        sensitivity=SENSITIVITY_LOW,
    )
    can14, reason14 = can_local_small_handle(t14)
    check("HIGH complexity summarize rejected from LOCAL_SMALL", not can14,
          f"reason: {reason14}")

    print(f"\n{passed}/{passed + failed} smoke tests passed.")
    if failed:
        print(f"FAILED: {failed} test(s).")
    else:
        print("All smoke tests passed.")
    return failed == 0


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    args = sys.argv[1:]

    if "--smoke" in args or "smoke" in args:
        ok = _smoke_test()
        sys.exit(0 if ok else 1)

    if "--route" in args:
        idx = args.index("--route")
        text = " ".join(args[idx + 1:]) if idx + 1 < len(args) else ""
        if not text:
            print("Usage: python core/brain_router.py --route <task description>")
            sys.exit(1)
        task = create_task_from_text(text)
        decision = route_task(task)
        print(f"\nTask   : {text}")
        print(f"Type   : {task.task_type}")
        print(f"Complexity: {task.complexity}")
        print(decision.explain())
        sys.exit(0)

    if "--engines" in args:
        print("\nAvailable engines:\n")
        for engine in ALL_ENGINES:
            print(f"  {engine}")
            print(f"    {get_engine_description(engine)}\n")
        sys.exit(0)

    print("Usage:")
    print("  python core/brain_router.py --smoke")
    print("  python core/brain_router.py --route <task description>")
    print("  python core/brain_router.py --engines")
