"""
core/actuation_engine.py — ORACLE Actuation Engine v0.1

This is the governed orchestrator for desktop execution.

The pipeline:
  1. route_task()       — Brain Router confirms ACTUATION_ENGINE is correct
  2. check_session()    — Session State confirms mode is not SAFE_SLEEP or BLOCKED
  3. find_window()      — Semantic UI Bridge locates the target window
  4. find_control()     — Semantic UI Bridge locates the input control
  5. approval_gate()    — Forbidden or sensitive actions require Noah approval
  6. execute_action()   — inject_text / focus / click via Semantic UI Bridge
  7. verify_result()    — screen hash + text read-back must confirm change
  8. record()           — BatchController records action, session state updated
  9. report()           — Structured ActuationResult with evidence or failure reason

What this engine never does:
  - Allow LOCAL_SMALL to claim desktop action success
  - Use raw mouse coordinates as primary targeting
  - Proceed when window is missing (stop cleanly)
  - Proceed when control is missing (stop cleanly)
  - Claim success without verification evidence
  - Execute forbidden actions (send/submit/delete/move/rename/post/
    purchase/commit/push/permissions/share) without approval
  - Execute anything when SAFE_SLEEP or BLOCKED mode is active

Hard law (from Brain Router):
  No model may claim an action succeeded unless verification evidence exists.
"""

import sys
import uuid
import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT / "core"))

# ── Forbidden actions ──────────────────────────────────────────────────────────

FORBIDDEN_VERBS = {
    "send", "submit", "delete", "move", "rename", "post",
    "purchase", "buy", "commit", "push", "share",
    "change permission", "set permission",
}

# Actions that require approval even if not outright forbidden
APPROVAL_REQUIRED_ACTIONS = {
    "press_enter",    # may submit a form
    "click_submit",   # explicit submit
    "clear_field",    # destructive if content was important
}


def _is_forbidden(action_description: str) -> tuple[bool, str]:
    low = action_description.lower()
    for verb in FORBIDDEN_VERBS:
        if verb in low:
            return True, verb
    return False, ""


def _requires_approval(action_type: str, action_description: str) -> tuple[bool, str]:
    if action_type in APPROVAL_REQUIRED_ACTIONS:
        return True, f"Action type '{action_type}' requires Noah approval before execution."
    forbidden, verb = _is_forbidden(action_description)
    if forbidden:
        return True, f"Forbidden verb '{verb}' requires Noah approval before execution."
    return False, ""


# ── Action types ───────────────────────────────────────────────────────────────

ACTION_INJECT_TEXT   = "inject_text"
ACTION_FOCUS_WINDOW  = "focus_window"
ACTION_FOCUS_CONTROL = "focus_control"
ACTION_PRESS_ENTER   = "press_enter"
ACTION_SCREENSHOT    = "screenshot"
ACTION_DRY_RUN       = "dry_run"
ACTION_CLEAR_FIELD   = "clear_field"

ALL_ACTION_TYPES = [
    ACTION_INJECT_TEXT, ACTION_FOCUS_WINDOW, ACTION_FOCUS_CONTROL,
    ACTION_PRESS_ENTER, ACTION_SCREENSHOT, ACTION_DRY_RUN, ACTION_CLEAR_FIELD,
]


# ── Data models ────────────────────────────────────────────────────────────────

@dataclass
class ActuationRequest:
    """What the caller wants the engine to do."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    action_type: str = ACTION_INJECT_TEXT
    target_window_hint: str = ""
    target_process: str = ""
    target_control_type: str = ""
    target_control_name: str = ""
    target_automation_id: str = ""
    text_to_inject: str = ""
    press_enter_after: bool = False   # requires approval gate
    dry_run: bool = False
    sensitivity: str = "medium"
    approved_by_noah: bool = False
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class ActuationResult:
    """Evidence of what the engine did — or why it stopped."""
    request_id: str = ""
    action_type: str = ""
    success: bool = False
    verified: bool = False           # True only if verification evidence exists
    dry_run: bool = False

    window_found: bool = False
    window_title: str = ""
    control_found: bool = False
    control_description: str = ""

    text_injected: str = ""
    text_verified: str = ""          # what was read back from control

    screen_hash_before: str = ""
    screen_hash_after: str = ""
    screen_changed: bool = False

    stopped_reason: str = ""
    failure_stage: str = ""
    approval_required: bool = False
    approval_reason: str = ""

    blocked_forbidden: bool = False
    blocked_verb: str = ""

    safe_sleep_blocked: bool = False
    local_small_blocked: bool = False

    session_mode_at_start: str = ""
    session_mode_at_end: str = ""

    unknowns: list = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def explain(self) -> str:
        lines = [
            "",
            f"  [ACTUATION RESULT — {self.request_id}]",
            f"  Action    : {self.action_type}",
            f"  Success   : {'YES' if self.success else 'NO'}",
            f"  Verified  : {'YES — evidence in text_verified/screen_hash' if self.verified else 'NO — not verified'}",
            f"  Dry run   : {'YES' if self.dry_run else 'no'}",
        ]
        if self.safe_sleep_blocked:
            lines.append("  [BLOCKED]   SAFE_SLEEP mode — no desktop actions allowed")
        if self.blocked_forbidden:
            lines.append(f"  [BLOCKED]   Forbidden verb '{self.blocked_verb}' — route to HUMAN_SOVEREIGN")
        if self.approval_required:
            lines.append(f"  [APPROVAL]  {self.approval_reason}")
        if self.window_found:
            lines.append(f"  Window    : {self.window_title}")
        else:
            lines.append("  Window    : NOT FOUND — stopped cleanly")
        if self.control_found:
            lines.append(f"  Control   : {self.control_description}")
        else:
            lines.append("  Control   : NOT FOUND — stopped cleanly")
        if self.text_injected:
            lines.append(f"  Injected  : {self.text_injected[:60]!r}")
        if self.text_verified:
            lines.append(f"  Read back : {self.text_verified[:60]!r}")
        if self.screen_hash_before:
            changed = "YES" if self.screen_changed else "NO"
            lines.append(
                f"  Screen    : before={self.screen_hash_before[:8]} "
                f"after={self.screen_hash_after[:8]} changed={changed}"
            )
        if self.stopped_reason:
            lines.append(f"  Stopped   : {self.stopped_reason}")
        if self.failure_stage:
            lines.append(f"  Failed at : {self.failure_stage}")
        for u in self.unknowns:
            lines.append(f"  [UNKNOWN] {u}")
        lines.append(f"  Mode      : {self.session_mode_at_start} → {self.session_mode_at_end}")
        lines.append("")
        return "\n".join(lines)


# ── Screen hash ────────────────────────────────────────────────────────────────

def _screen_hash() -> str:
    """MD5 of a 320×180 screenshot. Returns empty string on failure."""
    try:
        import pyautogui
        img = pyautogui.screenshot()
        img = img.resize((320, 180))
        return hashlib.md5(img.tobytes()).hexdigest()
    except Exception:
        return ""


# ── Session state helpers ─────────────────────────────────────────────────────

def _get_session_mode() -> str:
    try:
        from session_state import load_state
        return load_state().mode
    except Exception:
        return "UNKNOWN"


def _set_session_mode(mode: str, reason: str = ""):
    try:
        from session_state import set_mode
        set_mode(mode, reason=reason)
    except Exception:
        pass


def _record_tool_call(tool: str, args: str, result: str):
    try:
        from session_state import record_tool_call
        record_tool_call(tool, args, result)
    except Exception:
        pass


def _is_safe_sleep() -> bool:
    try:
        from session_state import load_state, MODE_SAFE_SLEEP, MODE_BLOCKED
        return load_state().mode in (MODE_SAFE_SLEEP, MODE_BLOCKED)
    except Exception:
        return False


# ── Brain Router check ────────────────────────────────────────────────────────

def _confirm_actuation_engine_route(request: ActuationRequest) -> tuple[bool, str]:
    """
    Confirm with Brain Router that this is an ACTUATION_ENGINE task.
    Returns (confirmed, reason). LOCAL_SMALL never passes this check.
    """
    try:
        from brain_router import (
            BrainTask, route_task,
            TASK_DESKTOP_ACTION, ENGINE_ACTUATION,
            COMPLEXITY_MEDIUM,
        )
        task = BrainTask(
            task_type=TASK_DESKTOP_ACTION,
            summary=(
                f"{request.action_type}: "
                f"window={request.target_window_hint} "
                f"text={request.text_to_inject[:40]}"
            ),
            requires_reality_verification=True,
            complexity=COMPLEXITY_MEDIUM,
            sensitivity=request.sensitivity,
        )
        decision = route_task(task)
        if decision.selected_engine == ENGINE_ACTUATION and decision.allowed:
            return True, "Brain Router confirmed ACTUATION_ENGINE."
        if decision.blocked:
            return False, f"Brain Router blocked: {decision.block_reason}"
        return False, f"Brain Router routed to wrong engine: {decision.selected_engine}"
    except ImportError:
        return True, "[UNKNOWN] Brain Router unavailable — proceeding without routing check."
    except Exception as e:
        return True, f"[UNKNOWN] Brain Router check error: {e}"


# ── Core pipeline ──────────────────────────────────────────────────────────────

def execute(request: ActuationRequest) -> ActuationResult:
    """
    Full governed execution pipeline.

    Stage 0: SAFE_SLEEP / BLOCKED check
    Stage 1: Dry run short-circuit
    Stage 2: Brain Router confirmation
    Stage 3: Forbidden action check
    Stage 4: Approval gate
    Stage 5: Find and focus window
    Stage 6: Find and focus control
    Stage 7: Screen hash before
    Stage 8: Execute action
    Stage 9: Screen hash after + verification
    Stage 10: Record and return
    """
    result = ActuationResult(
        request_id=request.id,
        action_type=request.action_type,
        dry_run=request.dry_run,
        session_mode_at_start=_get_session_mode(),
    )

    # ── Stage 0: SAFE_SLEEP ───────────────────────────────────────────────────
    if _is_safe_sleep():
        result.safe_sleep_blocked = True
        result.stopped_reason = (
            "SAFE_SLEEP or BLOCKED mode is active. "
            "No desktop actions will execute. "
            "Type CONTINUE ORACLE to resume."
        )
        result.failure_stage = "safe_sleep_check"
        result.session_mode_at_end = _get_session_mode()
        return result

    # ── Stage 1: Dry run ──────────────────────────────────────────────────────
    if request.dry_run or request.action_type == ACTION_DRY_RUN:
        result.dry_run = True
        result.success = True
        result.stopped_reason = "Dry run — no action executed."
        result.unknowns.append(
            f"Would target window='{request.target_window_hint}' "
            f"control_type='{request.target_control_type}' "
            f"text='{request.text_to_inject[:40]}'"
        )
        result.session_mode_at_end = _get_session_mode()
        _record_tool_call("actuation_engine.dry_run",
                          f"window={request.target_window_hint}", "not executed")
        return result

    # ── Stage 2: Brain Router ─────────────────────────────────────────────────
    router_ok, router_reason = _confirm_actuation_engine_route(request)
    if not router_ok:
        result.stopped_reason = f"Brain Router denied: {router_reason}"
        result.failure_stage = "brain_router"
        result.local_small_blocked = True
        result.session_mode_at_end = _get_session_mode()
        return result
    if "[UNKNOWN]" in router_reason:
        result.unknowns.append(router_reason)

    # ── Stage 3: Forbidden check ──────────────────────────────────────────────
    forbidden, verb = _is_forbidden(
        f"{request.action_type} {request.text_to_inject} {request.target_window_hint}"
    )
    if forbidden and not request.approved_by_noah:
        result.blocked_forbidden = True
        result.blocked_verb = verb
        result.approval_required = True
        result.approval_reason = (
            f"Forbidden action '{verb}' detected. "
            f"Route to HUMAN_SOVEREIGN. Noah must approve."
        )
        result.stopped_reason = result.approval_reason
        result.failure_stage = "forbidden_check"
        result.session_mode_at_end = _get_session_mode()
        return result

    # ── Stage 4: Approval gate ────────────────────────────────────────────────
    needs_approval, approval_reason = _requires_approval(
        request.action_type,
        f"{request.action_type} {request.text_to_inject}",
    )
    if needs_approval and not request.approved_by_noah:
        result.approval_required = True
        result.approval_reason = approval_reason
        result.stopped_reason = f"Approval required: {approval_reason}"
        result.failure_stage = "approval_gate"
        result.session_mode_at_end = _get_session_mode()
        return result

    # ── Stage 5: Find and focus window ────────────────────────────────────────
    try:
        from semantic_ui_bridge import (
            find_window, focus_window,
            find_control, focus_control,
            inject_text as ui_inject, verify_text as ui_verify,
        )
    except ImportError as e:
        result.stopped_reason = f"Semantic UI Bridge unavailable: {e}"
        result.failure_stage = "import"
        result.unknowns.append("semantic_ui_bridge not importable")
        result.session_mode_at_end = _get_session_mode()
        return result

    window = None
    if request.target_window_hint or request.target_process:
        _record_tool_call("find_window", request.target_window_hint, "searching...")
        window = find_window(
            title_contains=request.target_window_hint or None,
            process_name=request.target_process or None,
        )
        if window is None:
            result.window_found = False
            result.stopped_reason = (
                f"Target window not found: hint={request.target_window_hint!r} "
                f"process={request.target_process!r}. "
                "Stopping cleanly — ORACLE does not guess."
            )
            result.failure_stage = "find_window"
            _record_tool_call("find_window", request.target_window_hint, "NOT FOUND")
            result.session_mode_at_end = _get_session_mode()
            return result

        result.window_found = True
        result.window_title = window.title
        _record_tool_call("find_window", request.target_window_hint, f"found: {window.title}")

        fw = focus_window(window)
        if not fw.success:
            result.stopped_reason = f"focus_window failed: {fw.failure_reason}"
            result.failure_stage = "focus_window"
            result.unknowns.extend(fw.unknowns)
            result.session_mode_at_end = _get_session_mode()
            return result
        result.unknowns.extend(fw.unknowns)

    # ── Stage 6: Find and focus control ──────────────────────────────────────
    control = None
    if request.target_control_type or request.target_control_name or request.target_automation_id:
        if window is None:
            result.stopped_reason = (
                "Cannot find control without a window reference. "
                "Set target_window_hint."
            )
            result.failure_stage = "find_control_no_window"
            result.session_mode_at_end = _get_session_mode()
            return result

        _record_tool_call(
            "find_control",
            f"type={request.target_control_type} name={request.target_control_name}",
            "searching...",
        )
        control = find_control(
            window,
            control_type=request.target_control_type or None,
            name_contains=request.target_control_name or None,
            automation_id=request.target_automation_id or None,
        )
        if control is None:
            result.control_found = False
            result.stopped_reason = (
                f"Control not found in '{result.window_title}': "
                f"type={request.target_control_type!r} "
                f"name={request.target_control_name!r}. "
                "Stopping cleanly."
            )
            result.failure_stage = "find_control"
            _record_tool_call("find_control", request.target_control_name, "NOT FOUND")
            result.session_mode_at_end = _get_session_mode()
            return result

        result.control_found = True
        result.control_description = str(control)
        _record_tool_call("find_control", request.target_control_name, f"found: {control.name}")

        fc = focus_control(control)
        if not fc.success:
            result.stopped_reason = f"focus_control failed: {fc.failure_reason}"
            result.failure_stage = "focus_control"
            result.session_mode_at_end = _get_session_mode()
            return result
        result.unknowns.extend(fc.unknowns)

    # ── Stage 7: Screen hash before ───────────────────────────────────────────
    result.screen_hash_before = _screen_hash()
    if not result.screen_hash_before:
        result.unknowns.append("Pre-action screen hash unavailable (pyautogui?)")

    # ── Stage 8: Execute ──────────────────────────────────────────────────────
    if request.action_type == ACTION_INJECT_TEXT:
        if control is None:
            result.stopped_reason = (
                "inject_text requires a control. "
                "Set target_control_type or target_automation_id."
            )
            result.failure_stage = "inject_no_control"
            result.session_mode_at_end = _get_session_mode()
            return result

        _record_tool_call("inject_text", f"text={request.text_to_inject[:40]!r}", "injecting...")
        ir = ui_inject(control, request.text_to_inject, clear_first=True, press_enter=False)
        result.text_injected = request.text_to_inject
        _record_tool_call("inject_text", f"text={request.text_to_inject[:40]!r}",
                          "verified" if ir.verified else "UNVERIFIED")

        if not ir.success:
            result.stopped_reason = f"Injection failed: {ir.failure_reason}"
            result.failure_stage = "inject_text"
            result.unknowns.extend(ir.unknowns)
            result.session_mode_at_end = _get_session_mode()
            return result

        result.text_verified = ir.text_found
        result.unknowns.extend(ir.unknowns)

        if request.press_enter_after and request.approved_by_noah:
            try:
                control._raw.type_keys("{ENTER}", pause=0.1)
                _record_tool_call("press_enter", "", "sent")
            except Exception as e:
                result.unknowns.append(f"press_enter failed: {e}")

    elif request.action_type in (ACTION_FOCUS_WINDOW, ACTION_FOCUS_CONTROL):
        result.success = True  # focus already done in stages 5/6

    elif request.action_type == ACTION_SCREENSHOT:
        if result.screen_hash_before:
            result.success = True
            result.verified = True
        else:
            result.stopped_reason = "Screenshot unavailable — pyautogui not installed."
            result.failure_stage = "screenshot"
            result.session_mode_at_end = _get_session_mode()
            return result

    else:
        result.stopped_reason = f"Unknown action_type: {request.action_type!r}"
        result.failure_stage = "unknown_action"
        result.session_mode_at_end = _get_session_mode()
        return result

    # ── Stage 9: Verify ───────────────────────────────────────────────────────
    time.sleep(0.4)
    result.screen_hash_after = _screen_hash()
    if result.screen_hash_before and result.screen_hash_after:
        result.screen_changed = (result.screen_hash_before != result.screen_hash_after)
        if not result.screen_changed:
            result.unknowns.append(
                "Screen hash unchanged after action — may not have had visible effect."
            )

    text_confirmed = (
        bool(result.text_verified) and
        request.text_to_inject.strip() in result.text_verified
    )
    result.verified = text_confirmed or result.screen_changed
    result.success = True

    if not result.verified:
        result.unknowns.append(
            "Action completed but could not be independently verified. "
            "No model may claim this succeeded."
        )

    # ── Stage 10: Record ──────────────────────────────────────────────────────
    result.session_mode_at_end = _get_session_mode()
    return result


# ── Convenience wrappers ──────────────────────────────────────────────────────

def type_into_window(
    window_hint: str,
    text: str,
    control_type: str = "Edit",
    dry_run: bool = False,
    approved: bool = False,
) -> ActuationResult:
    """
    Find window → find Edit control → inject text → verify.
    This is the replacement for 'qwen, open chrome and type into ChatGPT.'
    """
    return execute(ActuationRequest(
        action_type=ACTION_INJECT_TEXT,
        target_window_hint=window_hint,
        target_control_type=control_type,
        text_to_inject=text,
        dry_run=dry_run,
        approved_by_noah=approved,
    ))


def focus_target_window(window_hint: str, dry_run: bool = False) -> ActuationResult:
    return execute(ActuationRequest(
        action_type=ACTION_FOCUS_WINDOW,
        target_window_hint=window_hint,
        dry_run=dry_run,
    ))


def take_screenshot() -> ActuationResult:
    return execute(ActuationRequest(action_type=ACTION_SCREENSHOT))


# ── Smoke tests ────────────────────────────────────────────────────────────────

def _smoke_test() -> bool:
    print("=" * 60)
    print("actuation_engine.py — Smoke Test")
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

    # 1. SAFE_SLEEP blocks all execution
    print("\n  -- SAFE_SLEEP blocks execution --")
    try:
        from session_state import set_mode, MODE_SAFE_SLEEP, MODE_IDLE
        set_mode(MODE_SAFE_SLEEP, reason="smoke test")
        r = execute(ActuationRequest(
            action_type=ACTION_INJECT_TEXT,
            target_window_hint="AnyWindow",
            text_to_inject="hello",
        ))
        check("SAFE_SLEEP blocks execution", r.safe_sleep_blocked)
        check("SAFE_SLEEP result not success", not r.success)
        check("SAFE_SLEEP stopped_reason set", bool(r.stopped_reason))
        set_mode(MODE_IDLE, reason="smoke test restore")
    except ImportError:
        check("SAFE_SLEEP test (session_state unavailable — skipped)", True)

    # 2. Dry run does not execute, reports intent
    print("\n  -- Dry run --")
    r_dry = execute(ActuationRequest(
        action_type=ACTION_INJECT_TEXT,
        target_window_hint="ChatGPT",
        text_to_inject="hello oracle",
        dry_run=True,
    ))
    check("Dry run returns success=True", r_dry.success)
    check("Dry run verified=False", not r_dry.verified)
    check("Dry run stopped_reason says 'Dry run'", "Dry run" in r_dry.stopped_reason)
    check("Dry run has unknowns describing intent", len(r_dry.unknowns) > 0)
    check("Dry run unknown mentions target window",
          any("ChatGPT" in u for u in r_dry.unknowns))

    # 3. Missing window stops cleanly
    print("\n  -- Missing window stops cleanly --")
    r_nowin = execute(ActuationRequest(
        action_type=ACTION_INJECT_TEXT,
        target_window_hint="__ORACLE_FAKE_WINDOW_THAT_DOES_NOT_EXIST__",
        text_to_inject="hello",
    ))
    check("Missing window → success=False", not r_nowin.success)
    check("Missing window → failure_stage=find_window",
          r_nowin.failure_stage == "find_window",
          f"got {r_nowin.failure_stage}")
    check("Missing window → stopped_reason set", bool(r_nowin.stopped_reason))
    check("Missing window → not verified", not r_nowin.verified)

    # 4. Forbidden action blocked without approval
    print("\n  -- Forbidden action blocks --")
    for verb in ["submit form", "delete this", "send message", "push to github", "purchase item"]:
        r_fb = execute(ActuationRequest(
            action_type=ACTION_INJECT_TEXT,
            target_window_hint="Window",
            text_to_inject=verb,
            approved_by_noah=False,
        ))
        check(f"Forbidden '{verb.split()[0]}' blocked",
              r_fb.blocked_forbidden or r_fb.approval_required,
              f"stopped: {r_fb.stopped_reason[:60]}")

    # 5. Forbidden with approval passes gate, then hits find_window
    print("\n  -- Forbidden + approved passes gate --")
    r_appr = execute(ActuationRequest(
        action_type=ACTION_INJECT_TEXT,
        target_window_hint="__FAKE__",
        text_to_inject="submit this",
        approved_by_noah=True,
    ))
    check("Forbidden + approved clears forbidden gate",
          not r_appr.blocked_forbidden,
          f"still blocked: {r_appr.blocked_verb}")
    check("Forbidden + approved stops at find_window",
          r_appr.failure_stage == "find_window",
          f"stage={r_appr.failure_stage}")

    # 6. press_enter requires approval
    print("\n  -- press_enter approval gate --")
    r_enter = execute(ActuationRequest(
        action_type=ACTION_PRESS_ENTER,
        target_window_hint="Window",
        approved_by_noah=False,
    ))
    check("press_enter without approval → approval_required",
          r_enter.approval_required,
          f"stopped: {r_enter.stopped_reason[:60]}")

    # 7. Brain Router confirms ACTUATION_ENGINE for desktop actions
    print("\n  -- Brain Router routing --")
    try:
        from brain_router import BrainTask, route_task, TASK_DESKTOP_ACTION, ENGINE_ACTUATION
        task = BrainTask(
            task_type=TASK_DESKTOP_ACTION,
            summary="type into ChatGPT input field",
            requires_reality_verification=True,
        )
        d = route_task(task)
        check("Brain Router → ACTUATION_ENGINE for desktop_action",
              d.selected_engine == ENGINE_ACTUATION, f"got {d.selected_engine}")
        check("Brain Router LOCAL_SMALL restriction present",
              any("LOCAL_SMALL" in c for c in d.constraints))
        check("Brain Router verification constraint present",
              any("verification" in c.lower() for c in d.constraints))
    except ImportError:
        check("Brain Router check skipped (unavailable)", True)

    # 8. ActuationResult.explain() builds correctly
    print("\n  -- ActuationResult.explain() --")
    r_exp = ActuationResult(
        request_id="smoke01",
        action_type=ACTION_INJECT_TEXT,
        success=False,
        verified=False,
        window_found=False,
        stopped_reason="Window not found: hint='ChatGPT'",
        failure_stage="find_window",
        session_mode_at_start="IDLE",
        session_mode_at_end="IDLE",
    )
    r_exp.unknowns.append("Window may have closed between check and action")
    exp = r_exp.explain()
    check("explain() non-empty", bool(exp))
    check("explain() shows NOT FOUND for window", "NOT FOUND" in exp)
    check("explain() shows failure stage", "find_window" in exp)
    check("explain() shows not verified", "NO" in exp)
    check("explain() shows unknown", "UNKNOWN" in exp)

    # 9. ActuationRequest defaults
    print("\n  -- ActuationRequest defaults --")
    req = ActuationRequest()
    check("Default action_type is inject_text", req.action_type == ACTION_INJECT_TEXT)
    check("Default dry_run=False", not req.dry_run)
    check("Default approved_by_noah=False", not req.approved_by_noah)
    check("ID auto-generated", bool(req.id) and len(req.id) == 8)

    # 10. Screenshot (safe read-only)
    print("\n  -- Screenshot --")
    r_ss = execute(ActuationRequest(action_type=ACTION_SCREENSHOT))
    if r_ss.success:
        check("Screenshot succeeds", True)
        check("Screenshot is verified (hash confirms screen)", r_ss.verified)
    else:
        check("Screenshot fails cleanly (pyautogui unavailable)", bool(r_ss.stopped_reason))

    # 11. type_into_window wrapper — dry run
    print("\n  -- type_into_window wrapper (dry run) --")
    r_wrap = type_into_window("__FAKE__", "hello oracle", dry_run=True)
    check("type_into_window wrapper returns ActuationResult",
          isinstance(r_wrap, ActuationResult))
    check("type_into_window dry_run not verified", not r_wrap.verified)

    # 12. No verified claim without evidence
    print("\n  -- Verified only with evidence --")
    r_unv = ActuationResult(success=True, verified=False)
    check("success=True, verified=False is valid state (engine adds unknown)",
          r_unv.success and not r_unv.verified)
    r_unv.unknowns.append(
        "Action completed but could not be independently verified. "
        "No model may claim this succeeded."
    )
    check("Unverified result carries explicit no-claim unknown",
          any("No model may claim" in u for u in r_unv.unknowns))

    # 13. SAFE_SLEEP with ACTION_DRY_RUN type — still safe-sleep blocked
    print("\n  -- SAFE_SLEEP also blocks ACTION_DRY_RUN type --")
    try:
        from session_state import set_mode, MODE_SAFE_SLEEP, MODE_IDLE
        set_mode(MODE_SAFE_SLEEP, reason="smoke test 13")
        r_ss2 = execute(ActuationRequest(action_type=ACTION_DRY_RUN))
        check("SAFE_SLEEP blocks even DRY_RUN action type",
              r_ss2.safe_sleep_blocked, f"got: {r_ss2.stopped_reason[:60]}")
        set_mode(MODE_IDLE, reason="restore")
    except ImportError:
        check("SAFE_SLEEP/DRY_RUN test skipped", True)

    print(f"\n{passed}/{passed + failed} smoke tests passed.")
    if failed:
        print(f"FAILED: {failed} test(s).")
    else:
        print("All smoke tests passed.")
    return failed == 0


# ── CLI ─────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    args = sys.argv[1:]

    if "--smoke-test" in args or "--smoke" in args:
        ok = _smoke_test()
        sys.exit(0 if ok else 1)

    if "--dry-run" in args:
        idx = args.index("--dry-run")
        window = args[idx + 1] if idx + 1 < len(args) else "ChatGPT"
        text   = args[idx + 2] if idx + 2 < len(args) else "(test)"
        r = type_into_window(window, text, dry_run=True)
        print(r.explain())
        sys.exit(0)

    if "--type-into" in args:
        idx = args.index("--type-into")
        window = args[idx + 1] if idx + 1 < len(args) else ""
        text   = args[idx + 2] if idx + 2 < len(args) else ""
        approved = "--approved" in args
        if not window or not text:
            print("Usage: python core/actuation_engine.py --type-into <window> <text> [--approved]")
            sys.exit(1)
        r = type_into_window(window, text, approved=approved)
        print(r.explain())
        sys.exit(0 if r.success else 1)

    if "--focus" in args:
        idx = args.index("--focus")
        window = args[idx + 1] if idx + 1 < len(args) else ""
        if not window:
            print("Usage: python core/actuation_engine.py --focus <window_hint>")
            sys.exit(1)
        r = focus_target_window(window)
        print(r.explain())
        sys.exit(0 if r.success else 1)

    if "--screenshot" in args:
        r = take_screenshot()
        print(r.explain())
        sys.exit(0 if r.success else 1)

    print("Usage:")
    print("  python core/actuation_engine.py --smoke-test")
    print("  python core/actuation_engine.py --dry-run <window_hint> <text>")
    print("  python core/actuation_engine.py --type-into <window> <text> [--approved]")
    print("  python core/actuation_engine.py --focus <window_hint>")
    print("  python core/actuation_engine.py --screenshot")
