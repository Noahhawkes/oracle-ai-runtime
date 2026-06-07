"""
core/session_state.py — ORACLE Session State Controller v0.1

The problem this solves:
  ORACLE does not know what she is currently doing.
  She gets stuck in stale modes (GitHub username prompt).
  She treats architecture notes as answers to active terminal prompts.
  ACTION_DIAGNOSTIC produces prose instead of structured state.
  The daemon keeps proposing old revenue tasks instead of reading the
  current engineering blocker.
  Loop guard fires but cannot explain what happened or what to do next.

This module is the session state controller.
Every input is classified before it reaches the LLM.
Every mode transition is recorded.
Every stale prompt is detected and cleared.
ACTION_DIAGNOSTIC is a real command, not a model response.

Core law:
  Incoming user input must not be blindly consumed by stale tool state.
  If an active prompt exists, classify whether the input is actually an
  answer to that prompt before using it.
"""

import sys
import json
import uuid
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Paths ─────────────────────────────────────────────────────────────────────

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

MEMORY_DIR = ROOT / "Memory"
STATE_FILE = MEMORY_DIR / "session_state.json"

# ── Mode constants ─────────────────────────────────────────────────────────────

MODE_IDLE              = "IDLE"
MODE_BUILD_PASS        = "BUILD_PASS"
MODE_DAEMON_CYCLE      = "DAEMON_CYCLE"
MODE_TERMINAL_PROMPT   = "TERMINAL_PROMPT"
MODE_COMPUTER_USE      = "COMPUTER_USE"
MODE_GOVERNANCE_CAPTURE = "GOVERNANCE_CAPTURE"
MODE_DIAGNOSTIC        = "DIAGNOSTIC"
MODE_SAFE_SLEEP        = "SAFE_SLEEP"
MODE_BLOCKED           = "BLOCKED"
MODE_ERROR_RECOVERY    = "ERROR_RECOVERY"

ALL_MODES = [
    MODE_IDLE, MODE_BUILD_PASS, MODE_DAEMON_CYCLE, MODE_TERMINAL_PROMPT,
    MODE_COMPUTER_USE, MODE_GOVERNANCE_CAPTURE, MODE_DIAGNOSTIC,
    MODE_SAFE_SLEEP, MODE_BLOCKED, MODE_ERROR_RECOVERY,
]

# ── Expected input types ───────────────────────────────────────────────────────

INPUT_GITHUB_USERNAME      = "github_username"
INPUT_YES_NO               = "yes_no_confirmation"
INPUT_APPROVAL             = "approval"
INPUT_COMMAND              = "command"
INPUT_BUILD_INSTRUCTION    = "build_instruction"
INPUT_GOVERNANCE_RULE      = "governance_rule"
INPUT_FREE_TEXT            = "free_text"
INPUT_UNKNOWN              = "unknown"

ALL_INPUT_TYPES = [
    INPUT_GITHUB_USERNAME, INPUT_YES_NO, INPUT_APPROVAL,
    INPUT_COMMAND, INPUT_BUILD_INSTRUCTION, INPUT_GOVERNANCE_RULE,
    INPUT_FREE_TEXT, INPUT_UNKNOWN,
]

# ── Classification signals ─────────────────────────────────────────────────────

# These patterns always take priority over any active prompt
COMMAND_PREFIXES = {
    "action_diagnostic", "stop oracle", "stop sov1", "clear_prompt",
    "reset_session_state", "set_mode", "continue oracle", "autorun safe",
    "batch status", "action_dry_run", "safe_sleep",
}

GOVERNANCE_PHRASES = {
    "oracle may not", "oracle must", "oracle is", "sov1 is", "sov1 must",
    "only noah", "must not", "consent-based", "51/49", "sovereignty",
    "governed by", "approval required before", "no model may",
    "oracle may wonder", "oracle may not wander", "zero public exposure",
    "noah holds", "sovereign", "no external send", "no invented",
}

BUILD_PASS_SIGNALS = {
    "mythic build pass", "build target:", "build pass:", "acceptance criteria:",
    "smoke tests:", "required api:", "data model:", "purpose:",
}

# These look nothing like short usernames — strong reject for TERMINAL_PROMPT capture
DEFINITELY_NOT_USERNAME = {
    "mythic", "oracle", "sov1", "build pass", "core/", "docs/",
    "purpose:", "rules:", "```", "---", "#", "import ", "def ",
    "class ", "commit", "acceptance", "smoke test",
}

# Patterns that strongly indicate a stale prompt should NOT consume input
STALE_PROMPT_REJECT_PATTERNS = [
    r"^mythic build pass",
    r"^build target:",
    r"oracle\.ai is",
    r"sov1\.ai is",
    r"^only noah",
    r"^oracle may",
    r"^no model may",
    r"```",
    r"^import ",
    r"^def ",
    r"^class ",
    r"^#\s",
    r"acceptance criteria",
    r"smoke tests?:",
]

# Default prompt staleness threshold (seconds)
DEFAULT_STALE_SECONDS = 300  # 5 minutes


# ── Data models ────────────────────────────────────────────────────────────────

@dataclass
class ToolCallRecord:
    tool_name: str = ""
    args_summary: str = ""
    result_summary: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class InputClassification:
    text: str = ""
    classified_as: str = INPUT_UNKNOWN
    is_command: bool = False
    is_governance: bool = False
    is_build_instruction: bool = False
    is_prompt_answer: bool = False
    consumed_by_stale_prompt: bool = False
    override_active_prompt: bool = False
    confidence: float = 0.0
    reason: str = ""

    def explain(self) -> str:
        lines = [
            f"  [INPUT CLASSIFICATION]",
            f"  Text      : {self.text[:80]!r}",
            f"  Type      : {self.classified_as}",
            f"  Command   : {'YES' if self.is_command else 'no'}",
            f"  Governance: {'YES' if self.is_governance else 'no'}",
            f"  Build pass: {'YES' if self.is_build_instruction else 'no'}",
            f"  Prompt ans: {'YES' if self.is_prompt_answer else 'no'}",
            f"  Stale cap : {'BLOCKED — stale prompt rejected' if self.consumed_by_stale_prompt else 'no'}",
            f"  Override  : {'YES — overrides active prompt' if self.override_active_prompt else 'no'}",
            f"  Confidence: {int(self.confidence * 100)}%",
            f"  Reason    : {self.reason}",
        ]
        return "\n".join(lines)


@dataclass
class SessionState:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    mode: str = MODE_IDLE
    mode_reason: str = ""
    active_task: str = ""
    active_prompt: str = ""
    expected_input_type: str = INPUT_UNKNOWN
    prompt_owner_tool: str = ""
    prompt_started_at: str = ""
    last_user_input: str = ""
    last_tool_calls: list = field(default_factory=list)  # list of dicts
    blocked_reason: str = ""
    recovery_hint: str = ""
    stale_after_seconds: int = DEFAULT_STALE_SECONDS
    loop_guard_triggered: bool = False
    loop_guard_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def has_active_prompt(self) -> bool:
        return bool(self.active_prompt)

    def prompt_age_seconds(self) -> float:
        if not self.prompt_started_at:
            return 0.0
        try:
            started = datetime.fromisoformat(self.prompt_started_at)
            now = datetime.now(timezone.utc)
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            return (now - started).total_seconds()
        except Exception:
            return 0.0

    def is_prompt_stale(self) -> bool:
        if not self.has_active_prompt():
            return False
        return self.prompt_age_seconds() > self.stale_after_seconds

    def recent_tool_calls(self, n: int = 10) -> list:
        return self.last_tool_calls[-n:] if self.last_tool_calls else []

    def to_dict(self) -> dict:
        return asdict(self)


# ── Persistence ────────────────────────────────────────────────────────────────

def _ensure_memory_dir():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def load_state() -> SessionState:
    """Load session state from disk, or return a fresh IDLE state."""
    _ensure_memory_dir()
    try:
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            s = SessionState()
            for k, v in data.items():
                if hasattr(s, k):
                    setattr(s, k, v)
            return s
    except Exception:
        pass
    return SessionState()


def save_state(state: SessionState):
    """Persist session state to disk."""
    _ensure_memory_dir()
    state.updated_at = datetime.now(timezone.utc).isoformat()
    STATE_FILE.write_text(
        json.dumps(state.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ── API ────────────────────────────────────────────────────────────────────────

def set_mode(mode: str, reason: str = "", persist: bool = True) -> SessionState:
    """Transition to a new mode. Clears active prompt on IDLE/SAFE_SLEEP."""
    if mode not in ALL_MODES:
        raise ValueError(f"Unknown mode: {mode!r}. Valid: {ALL_MODES}")
    state = load_state()
    state.mode = mode
    state.mode_reason = reason
    if mode in (MODE_IDLE, MODE_SAFE_SLEEP):
        # Clear any active prompts on these modes
        state.active_prompt = ""
        state.expected_input_type = INPUT_UNKNOWN
        state.prompt_owner_tool = ""
        state.prompt_started_at = ""
    if persist:
        save_state(state)
    return state


def set_active_prompt(
    prompt_text: str,
    expected_input_type: str = INPUT_UNKNOWN,
    owner_tool: str = "",
    persist: bool = True,
) -> SessionState:
    """Register an active prompt waiting for user input."""
    if expected_input_type not in ALL_INPUT_TYPES:
        raise ValueError(f"Unknown input type: {expected_input_type!r}")
    state = load_state()
    state.active_prompt = prompt_text
    state.expected_input_type = expected_input_type
    state.prompt_owner_tool = owner_tool
    state.prompt_started_at = datetime.now(timezone.utc).isoformat()
    state.mode = MODE_TERMINAL_PROMPT if expected_input_type not in (
        INPUT_APPROVAL, INPUT_COMMAND
    ) else state.mode
    if persist:
        save_state(state)
    return state


def clear_active_prompt(reason: str = "", persist: bool = True) -> SessionState:
    """Clear the active prompt. Must be called when prompt is answered or abandoned."""
    state = load_state()
    state.active_prompt = ""
    state.expected_input_type = INPUT_UNKNOWN
    state.prompt_owner_tool = ""
    state.prompt_started_at = ""
    if reason:
        state.mode_reason = reason
    if state.mode == MODE_TERMINAL_PROMPT:
        state.mode = MODE_IDLE
    if persist:
        save_state(state)
    return state


def record_tool_call(
    tool_name: str,
    args_summary: str = "",
    result_summary: str = "",
    persist: bool = True,
) -> SessionState:
    """Record a tool call to the session history (max 50 kept)."""
    state = load_state()
    record = {
        "tool_name": tool_name,
        "args_summary": args_summary[:120],
        "result_summary": result_summary[:120],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    state.last_tool_calls.append(record)
    state.last_tool_calls = state.last_tool_calls[-50:]   # rolling window
    if persist:
        save_state(state)
    return state


def detect_stale_prompt(persist: bool = True) -> tuple[bool, str]:
    """
    Check if the active prompt is stale. If so, clear it.
    Returns (was_stale, reason).
    """
    state = load_state()
    if not state.has_active_prompt():
        return False, "No active prompt."
    if state.is_prompt_stale():
        age = int(state.prompt_age_seconds())
        reason = (
            f"Active prompt '{state.active_prompt[:60]}' "
            f"(type={state.expected_input_type}, owner={state.prompt_owner_tool}) "
            f"has been waiting {age}s — exceeds stale threshold of "
            f"{state.stale_after_seconds}s. Clearing."
        )
        clear_active_prompt(reason=reason, persist=persist)
        return True, reason
    return False, "Prompt is fresh."


def enter_recovery(reason: str, hint: str = "", persist: bool = True) -> SessionState:
    """
    Enter ERROR_RECOVERY mode. Called by loop guard and other failure paths.
    Records why recovery was triggered and what Noah or ORACLE should do next.
    """
    state = load_state()
    state.mode = MODE_ERROR_RECOVERY
    state.blocked_reason = reason
    state.recovery_hint = hint or (
        "Type STOP ORACLE to halt all action. "
        "Type ACTION_DIAGNOSTIC to see current state. "
        "Type RESET_SESSION_STATE to start clean."
    )
    state.loop_guard_triggered = True
    state.loop_guard_count += 1
    # Clear any active prompt — stale state is part of the problem
    state.active_prompt = ""
    state.expected_input_type = INPUT_UNKNOWN
    state.prompt_owner_tool = ""
    if persist:
        save_state(state)
    return state


def reset_session_state(persist: bool = True) -> SessionState:
    """
    Full reset. Clears all prompts, resets mode to IDLE, preserves tool call log.
    Called by RESET_SESSION_STATE command.
    """
    old = load_state()
    state = SessionState()
    state.last_tool_calls = old.last_tool_calls  # preserve history
    state.mode = MODE_IDLE
    state.mode_reason = "Manual reset via RESET_SESSION_STATE"
    if persist:
        save_state(state)
    return state


# ── Input classification ───────────────────────────────────────────────────────

def classify_user_input(text: str) -> InputClassification:
    """
    Classify incoming user text before it reaches any tool or LLM.

    Priority order:
      1. Empty / whitespace → free_text, no override
      2. Known command prefix → command, overrides active prompt
      3. Governance phrase → governance_rule, overrides active prompt
      4. MYTHIC BUILD PASS / build instruction → build_instruction, overrides
      5. Stale prompt reject patterns → override active prompt if present
      6. Active prompt match → prompt_answer
      7. Free text

    Returns InputClassification. The caller decides what to do.
    """
    clf = InputClassification(text=text)
    stripped = text.strip()
    lower = stripped.lower()

    if not stripped:
        clf.classified_as = INPUT_FREE_TEXT
        clf.confidence = 1.0
        clf.reason = "Empty input."
        return clf

    # 1. Command check (highest priority)
    for cmd in COMMAND_PREFIXES:
        if lower == cmd or lower.startswith(cmd + " ") or lower.startswith(cmd + "\n"):
            clf.classified_as = INPUT_COMMAND
            clf.is_command = True
            clf.override_active_prompt = True
            clf.confidence = 0.99
            clf.reason = f"Matches command prefix: '{cmd}'"
            return clf

    # 2. Governance phrase check
    for phrase in GOVERNANCE_PHRASES:
        if phrase in lower:
            clf.classified_as = INPUT_GOVERNANCE_RULE
            clf.is_governance = True
            clf.override_active_prompt = True
            clf.confidence = 0.95
            clf.reason = f"Contains governance phrase: '{phrase}'"
            return clf

    # 3. Build instruction check
    for signal in BUILD_PASS_SIGNALS:
        if lower.startswith(signal) or signal in lower[:120]:
            clf.classified_as = INPUT_BUILD_INSTRUCTION
            clf.is_build_instruction = True
            clf.override_active_prompt = True
            clf.confidence = 0.95
            clf.reason = f"Matches build pass signal: '{signal}'"
            return clf

    # 4. Stale prompt rejection — does input look nothing like what was expected?
    state = load_state()
    if state.has_active_prompt():
        expected = state.expected_input_type

        # Check hard reject patterns
        for pattern in STALE_PROMPT_REJECT_PATTERNS:
            if re.search(pattern, lower):
                clf.override_active_prompt = True
                clf.consumed_by_stale_prompt = False
                clf.confidence = 0.90
                clf.reason = (
                    f"Input matches stale-prompt rejection pattern '{pattern}'. "
                    f"Active prompt expected '{expected}' but this is not that. "
                    f"Treating as free text / reclassifying."
                )
                # Reclassify properly
                if re.search(r"^mythic build pass|build target:|acceptance criteria:", lower):
                    clf.classified_as = INPUT_BUILD_INSTRUCTION
                    clf.is_build_instruction = True
                else:
                    clf.classified_as = INPUT_FREE_TEXT
                return clf

        # GitHub username: only short single-word alphanumeric strings qualify
        if expected == INPUT_GITHUB_USERNAME:
            # Valid username: 1-39 chars, alphanumeric + hyphen, no spaces
            is_valid_username = bool(re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-]{0,38}$', stripped))
            # Reject if any DEFINITELY_NOT_USERNAME keyword present
            has_reject_kw = any(kw in lower for kw in DEFINITELY_NOT_USERNAME)
            if not is_valid_username or has_reject_kw:
                clf.classified_as = INPUT_FREE_TEXT
                clf.override_active_prompt = True
                clf.confidence = 0.88
                clf.reason = (
                    f"Input does not look like a GitHub username "
                    f"(valid={is_valid_username}, has_reject_keyword={has_reject_kw}). "
                    f"Refusing stale prompt capture. Clear prompt with CLEAR_PROMPT."
                )
                return clf
            else:
                clf.classified_as = INPUT_GITHUB_USERNAME
                clf.is_prompt_answer = True
                clf.confidence = 0.85
                clf.reason = "Matches github_username pattern for active prompt."
                return clf

        # Yes/no confirmation
        if expected == INPUT_YES_NO:
            if lower in ("y", "yes", "n", "no", "approve", "reject", "cancel"):
                clf.classified_as = INPUT_YES_NO
                clf.is_prompt_answer = True
                clf.confidence = 0.95
                clf.reason = "Matches yes/no pattern for active prompt."
                return clf
            else:
                clf.classified_as = INPUT_FREE_TEXT
                clf.override_active_prompt = True
                clf.confidence = 0.75
                clf.reason = (
                    "Input does not look like yes/no. "
                    "Active prompt may be stale."
                )
                return clf

        # Approval
        if expected == INPUT_APPROVAL:
            if any(w in lower for w in ("approve", "approved", "reject", "deny", "yes", "no", "cancel")):
                clf.classified_as = INPUT_APPROVAL
                clf.is_prompt_answer = True
                clf.confidence = 0.90
                clf.reason = "Matches approval keyword for active prompt."
                return clf

    # 5. Free text default
    clf.classified_as = INPUT_FREE_TEXT
    clf.confidence = 0.70
    clf.reason = "No specific pattern matched — free text."
    return clf


def should_consume_as_prompt_answer(text: str) -> tuple[bool, InputClassification]:
    """
    High-level guard: should this text be consumed as an answer to the active prompt?
    Returns (should_consume, classification).
    If False, the caller should NOT route to the active prompt's tool.
    """
    clf = classify_user_input(text)
    state = load_state()

    if not state.has_active_prompt():
        return False, clf

    if clf.is_command or clf.override_active_prompt:
        return False, clf

    if clf.is_prompt_answer:
        return True, clf

    return False, clf


# ── ACTION_DIAGNOSTIC ─────────────────────────────────────────────────────────

def action_diagnostic(incoming_text: str = "") -> str:
    """
    Real structured diagnostic. Not model prose.
    Intercept this before any LLM call.

    Returns a formatted string with full session state.
    """
    state = load_state()
    stale, stale_reason = detect_stale_prompt(persist=False)

    # Classify incoming text if provided
    clf_text = ""
    if incoming_text:
        clf = classify_user_input(incoming_text)
        clf_text = f"\n  Incoming text analysis:\n{clf.explain()}"

    recent = state.recent_tool_calls(10)
    tool_lines = []
    for tc in recent:
        ts = tc.get("timestamp", "")[:19].replace("T", " ")
        tool_lines.append(
            f"    [{ts}] {tc.get('tool_name', '?')} "
            f"| {tc.get('args_summary', '')[:40]} "
            f"| {tc.get('result_summary', '')[:40]}"
        )
    tool_block = "\n".join(tool_lines) if tool_lines else "    (no tool calls recorded)"

    # Get project state if available
    project_next = ""
    project_blocker = ""
    try:
        sys.path.insert(0, str(ROOT / "core"))
        from project_state import load_state as ps_load
        ps = ps_load("ORACLE.AI")
        if ps:
            project_next = ps.next_recommended_step or "(none)"
            project_blocker = ps.current_blocker or "(none)"
    except Exception:
        project_next = "(project_state unavailable)"
        project_blocker = "(project_state unavailable)"

    prompt_age = f"{int(state.prompt_age_seconds())}s" if state.has_active_prompt() else "n/a"

    lines = [
        "",
        "  ╔══════════════════════════════════════════════════════════╗",
        "  ║            ACTION DIAGNOSTIC — SESSION STATE             ║",
        "  ╚══════════════════════════════════════════════════════════╝",
        "",
        f"  Mode          : {state.mode}",
        f"  Mode reason   : {state.mode_reason or '(none)'}",
        f"  Active task   : {state.active_task or '(none)'}",
        "",
        f"  Active prompt : {state.active_prompt[:80] if state.active_prompt else '(none)'}",
        f"  Expected input: {state.expected_input_type}",
        f"  Prompt owner  : {state.prompt_owner_tool or '(none)'}",
        f"  Prompt age    : {prompt_age}",
        f"  Prompt stale  : {'YES — ' + stale_reason[:60] if stale else 'no'}",
        "",
        f"  Loop guard    : {'TRIGGERED x' + str(state.loop_guard_count) if state.loop_guard_triggered else 'not triggered'}",
        f"  Blocked reason: {state.blocked_reason[:80] if state.blocked_reason else '(none)'}",
        f"  Recovery hint : {state.recovery_hint[:80] if state.recovery_hint else '(none)'}",
        "",
        f"  Project blocker: {project_blocker[:80]}",
        f"  Project next   : {project_next[:80]}",
        "",
        f"  Last tool calls (most recent 10):",
        tool_block,
        clf_text,
        "",
        "  Recommended commands:",
        "    STOP ORACLE          — halt all action, enter SAFE_SLEEP",
        "    CLEAR_PROMPT         — clear active prompt, return to IDLE",
        "    RESET_SESSION_STATE  — full session reset (keeps tool history)",
        "    SET_MODE IDLE        — force idle mode",
        "    SET_MODE BUILD_PASS  — force build mode",
        "",
    ]

    return "\n".join(lines)


# ── Daemon priority check ──────────────────────────────────────────────────────

def daemon_should_override_with_engineering(proposed_task: str) -> tuple[bool, str]:
    """
    Check if the daemon's proposed task should be overridden by the active
    engineering blocker.

    Returns (should_override, reason).
    If True, the daemon must not proceed with proposed_task.
    """
    # Revenue/stale task keywords that should not override active engineering work
    STALE_REVENUE_SIGNALS = {
        "touchflame", "morning mission", "github backup", "linkedin",
        "upwork", "kdp", "revenue", "lootdrop recap", "morning brief",
        "affiliate", "passive income",
    }

    lower = proposed_task.lower()
    is_stale_revenue = any(sig in lower for sig in STALE_REVENUE_SIGNALS)

    if not is_stale_revenue:
        return False, "Proposed task is not a stale revenue task."

    # Check project state for active engineering blocker
    try:
        sys.path.insert(0, str(ROOT / "core"))
        from project_state import load_state as ps_load
        ps = ps_load("ORACLE.AI")
        if ps and ps.current_blocker:
            return True, (
                f"Active engineering blocker exists: '{ps.current_blocker[:80]}'. "
                f"Daemon may not override with stale revenue task '{proposed_task[:60]}'. "
                f"Next engineering step: '{ps.next_recommended_step[:80]}'. "
                f"To switch to revenue mode, Noah must explicitly request it."
            )
    except Exception:
        pass

    # Check session state for BUILD_PASS mode
    state = load_state()
    if state.mode == MODE_BUILD_PASS:
        return True, (
            f"Session is in BUILD_PASS mode. "
            f"Daemon may not propose stale revenue task '{proposed_task[:60]}'. "
            f"Active task: '{state.active_task[:60]}'."
        )

    return False, "No active engineering blocker found — revenue task may proceed."


# ── Command handler ────────────────────────────────────────────────────────────

def handle_command(text: str) -> tuple[bool, str]:
    """
    Handle a session state command. Returns (handled, response_text).
    Call this BEFORE routing to any LLM.
    """
    stripped = text.strip()
    lower = stripped.lower()

    if lower in ("action_diagnostic", "action diagnostic"):
        return True, action_diagnostic()

    if lower.startswith("action_diagnostic "):
        incoming = stripped[len("action_diagnostic "):].strip()
        return True, action_diagnostic(incoming_text=incoming)

    if lower in ("stop oracle", "stop sov1"):
        state = set_mode(MODE_SAFE_SLEEP, reason="STOP ORACLE command received")
        clear_active_prompt(reason="STOP ORACLE clears all active prompts")
        return True, (
            "\n  [STOP ORACLE] — Session entering SAFE_SLEEP.\n"
            "  All active prompts cleared.\n"
            "  No further desktop actions will execute.\n"
            "  Type CONTINUE ORACLE to resume.\n"
        )

    if lower == "clear_prompt":
        state = clear_active_prompt(reason="CLEAR_PROMPT command")
        return True, (
            "\n  [CLEAR_PROMPT] — Active prompt cleared. Mode: IDLE.\n"
            "  Any pending terminal prompt has been abandoned.\n"
        )

    if lower == "reset_session_state":
        state = reset_session_state()
        return True, (
            "\n  [RESET_SESSION_STATE] — Session reset to IDLE.\n"
            "  All prompts cleared. Tool call history preserved.\n"
        )

    if lower == "set_mode idle":
        set_mode(MODE_IDLE, reason="SET_MODE IDLE command")
        return True, "\n  [SET_MODE] — Mode set to IDLE.\n"

    if lower == "set_mode build_pass":
        set_mode(MODE_BUILD_PASS, reason="SET_MODE BUILD_PASS command")
        return True, "\n  [SET_MODE] — Mode set to BUILD_PASS.\n"

    if lower == "set_mode safe_sleep":
        set_mode(MODE_SAFE_SLEEP, reason="SET_MODE SAFE_SLEEP command")
        return True, "\n  [SET_MODE] — Mode set to SAFE_SLEEP.\n"

    return False, ""


# ── Smoke tests ────────────────────────────────────────────────────────────────

def _smoke_test() -> bool:
    print("=" * 60)
    print("session_state.py — Smoke Test")
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

    # Start from a clean state
    state = reset_session_state(persist=False)

    # 1. Set terminal prompt expecting github_username
    print("\n  -- Stale prompt: GitHub username --")
    state = set_active_prompt(
        "Enter your GitHub username:",
        expected_input_type=INPUT_GITHUB_USERNAME,
        owner_tool="github_backup_tool",
        persist=False,
    )
    save_state(state)
    check("Active prompt set to github_username",
          state.expected_input_type == INPUT_GITHUB_USERNAME)
    check("Mode set to TERMINAL_PROMPT", state.mode == MODE_TERMINAL_PROMPT)

    # 2. Send governance text — must NOT be consumed as username
    print("\n  -- Governance text not consumed as username --")
    gov_text = "ORACLE.AI is a consent-based local context engine."
    clf = classify_user_input(gov_text)
    check("Governance text classified as GOVERNANCE_RULE",
          clf.classified_as == INPUT_GOVERNANCE_RULE, f"got {clf.classified_as}")
    check("Governance text overrides active prompt", clf.override_active_prompt)
    check("Governance text is NOT classified as github_username",
          clf.classified_as != INPUT_GITHUB_USERNAME)

    should_consume, clf2 = should_consume_as_prompt_answer(gov_text)
    check("should_consume_as_prompt_answer returns False for governance",
          not should_consume, f"classified_as={clf2.classified_as}")

    # 3. MYTHIC BUILD PASS text while prompt active — must override
    print("\n  -- Build pass overrides active prompt --")
    build_text = "MYTHIC BUILD PASS: SESSION STATE CONTROLLER\nBuild target: core/session_state.py"
    clf3 = classify_user_input(build_text)
    check("Build pass text classified as BUILD_INSTRUCTION",
          clf3.classified_as == INPUT_BUILD_INSTRUCTION, f"got {clf3.classified_as}")
    check("Build pass overrides active prompt", clf3.override_active_prompt)
    should_c, _ = should_consume_as_prompt_answer(build_text)
    check("Build pass not consumed as prompt answer", not should_c)

    # 4. ACTION_DIAGNOSTIC — real command, returns structured state
    print("\n  -- ACTION_DIAGNOSTIC structured output --")
    handled, response = handle_command("ACTION_DIAGNOSTIC")
    check("ACTION_DIAGNOSTIC is handled as command", handled)
    check("ACTION_DIAGNOSTIC response is non-empty", len(response) > 100)
    check("ACTION_DIAGNOSTIC contains MODE", "Mode" in response)
    check("ACTION_DIAGNOSTIC contains Active prompt", "Active prompt" in response)
    check("ACTION_DIAGNOSTIC contains Last tool calls", "Last tool calls" in response)
    check("ACTION_DIAGNOSTIC contains Recommended commands", "Recommended commands" in response)

    # 5. Valid GitHub username IS consumed
    print("\n  -- Valid GitHub username accepted --")
    # Re-set the prompt (it may have been cleared by earlier checks)
    state2 = set_active_prompt(
        "Enter your GitHub username:",
        expected_input_type=INPUT_GITHUB_USERNAME,
        owner_tool="github_tool",
        persist=True,
    )
    valid_username = "noahhawkes"
    clf4 = classify_user_input(valid_username)
    check("Valid username classified as github_username",
          clf4.classified_as == INPUT_GITHUB_USERNAME, f"got {clf4.classified_as}")
    should_c4, _ = should_consume_as_prompt_answer(valid_username)
    check("Valid username is consumed as prompt answer", should_c4)

    # 6. STOP ORACLE clears active prompt
    print("\n  -- STOP ORACLE clears active prompt --")
    handled_stop, resp_stop = handle_command("STOP ORACLE")
    check("STOP ORACLE is handled", handled_stop)
    state_after_stop = load_state()
    check("STOP ORACLE clears active_prompt", not state_after_stop.active_prompt)
    check("STOP ORACLE enters SAFE_SLEEP", state_after_stop.mode == MODE_SAFE_SLEEP)

    # 7. Loop guard → ERROR_RECOVERY with useful hint
    print("\n  -- Loop guard → ERROR_RECOVERY --")
    recovery_state = enter_recovery(
        reason="focus_window called 6 times in 10 actions without progress",
        hint="Type STOP ORACLE to halt. Type ACTION_DIAGNOSTIC to see state. The window 'SOV1.AI' may not be accepting focus.",
        persist=True,
    )
    check("enter_recovery sets mode to ERROR_RECOVERY",
          recovery_state.mode == MODE_ERROR_RECOVERY)
    check("enter_recovery sets blocked_reason", bool(recovery_state.blocked_reason))
    check("enter_recovery sets recovery_hint", bool(recovery_state.recovery_hint))
    check("enter_recovery sets loop_guard_triggered", recovery_state.loop_guard_triggered)
    check("enter_recovery clears active_prompt", not recovery_state.active_prompt)
    # Diagnostic during recovery includes hint
    diag = action_diagnostic()
    check("ACTION_DIAGNOSTIC shows ERROR_RECOVERY mode", "ERROR_RECOVERY" in diag)
    check("ACTION_DIAGNOSTIC shows blocked_reason", "focus_window" in diag)
    check("ACTION_DIAGNOSTIC shows recovery_hint", "STOP ORACLE" in diag)

    # 8. Daemon stale revenue task check
    print("\n  -- Daemon stale priority check --")
    reset_session_state(persist=True)
    override, reason = daemon_should_override_with_engineering("Morning Mission Brief")
    # This depends on whether project_state has a blocker — check both outcomes
    if "engineering blocker" in reason.lower() or "BUILD_PASS" in reason:
        check("Daemon blocks Morning Mission when blocker active", override)
    else:
        check("Daemon allows Morning Mission when no active blocker", not override)
        print(f"     (no active blocker found — revenue task not blocked)")

    # Revenue task with active blocker
    state_bp = set_mode(MODE_BUILD_PASS, reason="smoke test", persist=True)
    override2, reason2 = daemon_should_override_with_engineering("TouchFlame affiliate push")
    check("Daemon blocks TouchFlame in BUILD_PASS mode", override2,
          f"reason: {reason2}")

    # Non-revenue task is never blocked
    override3, reason3 = daemon_should_override_with_engineering("Run ORACLE smoke tests")
    check("Daemon does not block non-revenue engineering task", not override3,
          f"reason: {reason3}")

    # 9. CLEAR_PROMPT command
    print("\n  -- CLEAR_PROMPT command --")
    set_active_prompt("Test prompt", INPUT_YES_NO, persist=True)
    handled_cp, _ = handle_command("CLEAR_PROMPT")
    check("CLEAR_PROMPT is handled", handled_cp)
    s_after = load_state()
    check("CLEAR_PROMPT clears prompt", not s_after.active_prompt)

    # 10. RESET_SESSION_STATE preserves tool history
    print("\n  -- RESET_SESSION_STATE --")
    record_tool_call("focus_window", "title=ChatGPT", "focused", persist=True)
    record_tool_call("type_text", "text=Hello", "typed", persist=True)
    before_reset = load_state()
    n_before = len(before_reset.last_tool_calls)
    handled_r, _ = handle_command("RESET_SESSION_STATE")
    check("RESET_SESSION_STATE is handled", handled_r)
    after_reset = load_state()
    check("RESET_SESSION_STATE returns to IDLE", after_reset.mode == MODE_IDLE)
    check("RESET_SESSION_STATE preserves tool history",
          len(after_reset.last_tool_calls) == n_before,
          f"before={n_before} after={len(after_reset.last_tool_calls)}")

    # 11. Stale prompt detection
    print("\n  -- Stale prompt detection --")
    state_fresh = set_active_prompt("Enter something:", INPUT_UNKNOWN, persist=True)
    was_stale, _ = detect_stale_prompt(persist=False)
    check("Fresh prompt is not stale", not was_stale)
    # Force stale by setting started_at far in the past
    state_stale = load_state()
    state_stale.prompt_started_at = "2020-01-01T00:00:00+00:00"
    state_stale.stale_after_seconds = 60
    save_state(state_stale)
    was_stale2, reason_stale = detect_stale_prompt(persist=True)
    check("Old prompt correctly detected as stale", was_stale2, reason_stale)
    check("Stale prompt cleared after detection",
          not load_state().active_prompt)

    # 12. Architecture notes not consumed as any structured input type
    print("\n  -- Architecture notes not hijacked --")
    reset_session_state(persist=True)
    set_active_prompt("Enter GitHub username:", INPUT_GITHUB_USERNAME, persist=True)
    arch_notes = "```python\nclass BrainRouter:\n    def route(self, task): ...\n```"
    clf_arch = classify_user_input(arch_notes)
    check("Markdown code block not classified as github_username",
          clf_arch.classified_as != INPUT_GITHUB_USERNAME,
          f"got {clf_arch.classified_as}")
    check("Markdown code block overrides stale prompt", clf_arch.override_active_prompt)

    # Cleanup
    reset_session_state(persist=True)

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

    if "--diagnostic" in args:
        print(action_diagnostic())
        sys.exit(0)

    if "--status" in args:
        s = load_state()
        print(f"\nMode          : {s.mode}")
        print(f"Active task   : {s.active_task or '(none)'}")
        print(f"Active prompt : {s.active_prompt[:80] if s.active_prompt else '(none)'}")
        print(f"Expected input: {s.expected_input_type}")
        print(f"Loop guard    : {'triggered x' + str(s.loop_guard_count) if s.loop_guard_triggered else 'not triggered'}")
        print(f"Blocked reason: {s.blocked_reason[:80] if s.blocked_reason else '(none)'}")
        print()
        sys.exit(0)

    if "--reset" in args:
        reset_session_state()
        print("Session state reset to IDLE.")
        sys.exit(0)

    if "--classify" in args:
        idx = args.index("--classify")
        text = " ".join(args[idx + 1:]) if idx + 1 < len(args) else ""
        if not text:
            print("Usage: python core/session_state.py --classify <text>")
            sys.exit(1)
        clf = classify_user_input(text)
        print(clf.explain())
        sys.exit(0)

    print("Usage:")
    print("  python core/session_state.py --smoke")
    print("  python core/session_state.py --diagnostic")
    print("  python core/session_state.py --status")
    print("  python core/session_state.py --reset")
    print("  python core/session_state.py --classify <text>")
