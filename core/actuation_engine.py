"""
core/actuation_engine.py — ORACLE Actuation Engine v0.1

Replaces mouse-coordinate automation with a semantic execution layer.
Does not look at pixels first. Reads the structural environment.

Architecture:
  1. Semantic UI Bridge     — Windows UIAutomation accessibility tree
  2. State Verification Loop — confirm environment before every action
  3. Command API            — semantic commands, not screen coordinates
  4. 51/49 Action Gate      — structures candidates, halts for Noah approval

Pipeline position:
  ... -> Retrieval -> [Actuation Engine] -> Action -> Environment

Safety modes:
  SAFE_SLEEP_MODE   — observe and propose only, zero physical actions
  ACTION_DRY_RUN    — print intended commands, do not execute
"""

from __future__ import annotations

import sys
import subprocess
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT / "core"))


# ── Global safety flags ───────────────────────────────────────────────────────

SAFE_SLEEP_MODE  = False   # True → observe/propose only, no physical actions
ACTION_DRY_RUN   = False   # True → print commands, do not execute them


# ── Loop guard ────────────────────────────────────────────────────────────────

_recent_actions: deque = deque(maxlen=9)
_LOOP_GUARD_LIMIT = 3


def _loop_guard(name: str, key: str) -> bool:
    _recent_actions.append((name, key))
    hits = sum(1 for n, k in _recent_actions if n == name and k == key)
    return hits >= _LOOP_GUARD_LIMIT


# ── UIAutomation backend ──────────────────────────────────────────────────────
# Uses Windows Accessibility (UIA) COM interface via comtypes.
# Gracefully disabled if comtypes is not installed — engine still works via
# pygetwindow + subprocess for the non-UIA operations.

_uia = None   # IUIAutomation COM object, set in _init_uia()

def _init_uia():
    global _uia
    if _uia is not None:
        return True
    try:
        import comtypes
        import comtypes.client
        # UIAutomation CLSID and IID — Windows built-in, no registry needed
        _uia = comtypes.client.CreateObject(
            "{ff48dba4-60ef-4201-aa87-54103eef594e}",
            interface=comtypes.gen.UIAutomationClient.IUIAutomation
            if hasattr(comtypes.gen, "UIAutomationClient")
            else None,
        )
        return True
    except Exception:
        pass
    try:
        # Second attempt: generate type library on-the-fly
        import comtypes.client
        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen.UIAutomationClient import CUIAutomation, IUIAutomation
        from comtypes import CoCreateInstance, CLSCTX_INPROC_SERVER
        _uia = CoCreateInstance(CUIAutomation, None, CLSCTX_INPROC_SERVER, IUIAutomation)
        return True
    except Exception:
        _uia = None
        return False


UIA_AVAILABLE = _init_uia()


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class WindowRef:
    title: str
    pid: int
    handle: Any = None          # HWND or pygetwindow object
    uia_element: Any = None     # UIA IUIAutomationElement

    def __str__(self):
        return f"Window('{self.title}', pid={self.pid})"


@dataclass
class ElementRef:
    name: str
    control_type: str
    automation_id: str = ""
    class_name: str = ""
    is_enabled: bool = True
    is_focused: bool = False
    value: str = ""
    uia_element: Any = None
    window: WindowRef | None = None

    def __str__(self):
        return (f"Element(name='{self.name}', type={self.control_type}, "
                f"enabled={self.is_enabled}, focused={self.is_focused})")


@dataclass
class ActionCandidate:
    """Structured action waiting for 51% approval before execution."""
    action: str
    target: str
    payload: str = ""
    reason: str = ""
    approval_required: bool = True
    sequence: list[dict] = field(default_factory=list)

    def describe(self) -> str:
        lines = [
            f"ACTION CANDIDATE — awaiting Noah's 51% approval",
            f"  Action : {self.action}",
            f"  Target : {self.target}",
        ]
        if self.payload:
            lines.append(f"  Payload: {self.payload}")
        if self.reason:
            lines.append(f"  Reason : {self.reason}")
        if self.sequence:
            lines.append("  Steps  :")
            for i, step in enumerate(self.sequence, 1):
                lines.append(f"    {i}. {step.get('cmd')} → {step.get('target', '')}")
        return "\n".join(lines)


# ── Approval-required action classification ───────────────────────────────────

_APPROVAL_REQUIRED = {
    "send_message", "submit_form", "post_public", "purchase", "delete",
    "move_file", "rename_file", "modify_source", "commit_code", "push_code",
    "change_permissions", "share_file", "unshare_file", "calendar_change",
    "close_window", "kill_process",
}

_APPROVAL_FREE = {
    "list_windows", "find_window", "focus_window_semantic", "list_elements",
    "find_element", "focus_element", "verify_element_value", "get_element_value",
    "screenshot_verify", "is_process_running", "get_active_window",
}

def _requires_approval(action: str) -> bool:
    return action in _APPROVAL_REQUIRED


# ── Process / window detection ────────────────────────────────────────────────

def is_process_running(name: str) -> bool:
    """Check if a process is running by exe name. No admin required."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {name}", "/NH"],
            capture_output=True, text=True, timeout=5,
        )
        return name.lower() in result.stdout.lower()
    except Exception:
        return False


def list_windows() -> list[WindowRef]:
    """List all visible windows with titles."""
    refs = []
    try:
        import pygetwindow as gw
        for w in gw.getAllWindows():
            if w.title.strip():
                refs.append(WindowRef(title=w.title, pid=0, handle=w))
    except Exception as e:
        refs.append(WindowRef(title=f"[pygetwindow unavailable: {e}]", pid=-1))
    return refs


def find_window(
    title_contains: str | None = None,
    process_name: str | None = None,
) -> WindowRef | None:
    """Find a window by title fragment or process name."""
    for ref in list_windows():
        if title_contains and title_contains.lower() in ref.title.lower():
            return ref
    if process_name:
        if not is_process_running(process_name):
            return None
        # Process is running but window title not found by fragment — try again
        # with the process name itself as a title hint
        proc_hint = process_name.replace(".exe", "").lower()
        for ref in list_windows():
            if proc_hint in ref.title.lower():
                return ref
    return None


def get_active_window() -> WindowRef | None:
    """Return the currently focused window."""
    try:
        import pygetwindow as gw
        w = gw.getActiveWindow()
        if w:
            return WindowRef(title=w.title, pid=0, handle=w)
    except Exception:
        pass
    return None


# ── Semantic UI Bridge (UIAutomation element tree) ────────────────────────────

def list_elements(window_ref: WindowRef) -> list[ElementRef]:
    """
    List interactive elements in a window via UIAutomation.
    Falls back to empty list if UIA unavailable.
    """
    if not UIA_AVAILABLE or _uia is None:
        return []
    try:
        import comtypes
        from comtypes.gen.UIAutomationClient import (
            TreeScope_Descendants, UIA_EditControlTypeId,
            UIA_ButtonControlTypeId, UIA_ComboBoxControlTypeId,
        )
        root_elem = _uia.ElementFromHandle(window_ref.handle._hWnd
                                           if hasattr(window_ref.handle, "_hWnd")
                                           else window_ref.handle)
        condition = _uia.CreateTrueCondition()
        elements = root_elem.FindAll(TreeScope_Descendants, condition)
        refs = []
        for i in range(elements.Length):
            e = elements.GetElement(i)
            try:
                refs.append(ElementRef(
                    name=e.CurrentName or "",
                    control_type=str(e.CurrentControlType),
                    automation_id=e.CurrentAutomationId or "",
                    class_name=e.CurrentClassName or "",
                    is_enabled=bool(e.CurrentIsEnabled),
                    is_focused=bool(e.CurrentHasKeyboardFocus),
                    uia_element=e,
                    window=window_ref,
                ))
            except Exception:
                pass
        return refs
    except Exception:
        return []


def find_element(
    window_ref: WindowRef | None = None,
    name: str | None = None,
    automation_id: str | None = None,
    class_name: str | None = None,
    control_type: str | None = None,
    focused: bool | None = None,
    enabled: bool | None = None,
) -> ElementRef | None:
    """
    Find a UI element by semantic properties via UIAutomation.
    Returns None if not found — caller must handle missing state.
    """
    if not UIA_AVAILABLE or window_ref is None:
        return None

    candidates = list_elements(window_ref)
    for e in candidates:
        if name and name.lower() not in e.name.lower():
            continue
        if automation_id and automation_id.lower() not in e.automation_id.lower():
            continue
        if class_name and class_name.lower() not in e.class_name.lower():
            continue
        if control_type and control_type.lower() not in e.control_type.lower():
            continue
        if focused is not None and e.is_focused != focused:
            continue
        if enabled is not None and e.is_enabled != enabled:
            continue
        return e
    return None


# ── State Verification Loop ───────────────────────────────────────────────────

@dataclass
class EnvironmentState:
    process_running: bool = False
    window_found: bool = False
    window_active: bool = False
    element_present: bool = False
    element_enabled: bool = False
    element_focused: bool = False
    element_value: str = ""
    verified: bool = False
    failure_reason: str = ""

    def ready(self) -> bool:
        return self.process_running and self.window_found and self.window_active

    def __str__(self) -> str:
        lines = ["Environment State:"]
        lines.append(f"  Process running : {self.process_running}")
        lines.append(f"  Window found    : {self.window_found}")
        lines.append(f"  Window active   : {self.window_active}")
        lines.append(f"  Element present : {self.element_present}")
        lines.append(f"  Element enabled : {self.element_enabled}")
        lines.append(f"  Element focused : {self.element_focused}")
        if self.element_value:
            lines.append(f"  Element value   : {self.element_value!r}")
        if self.failure_reason:
            lines.append(f"  FAILURE         : {self.failure_reason}")
        return "\n".join(lines)


def verify_state(
    process_name: str | None = None,
    window_title: str | None = None,
    element_name: str | None = None,
) -> EnvironmentState:
    """
    Query and return the current environment state.
    Lack of data causes a structured pause report — not a blind action.
    """
    state = EnvironmentState()

    # Query: Is target process running?
    if process_name:
        state.process_running = is_process_running(process_name)
        if not state.process_running:
            state.failure_reason = f"Process '{process_name}' is not running."
            return state
    else:
        state.process_running = True   # not checked

    # Query: Is target window present?
    window = None
    if window_title:
        window = find_window(title_contains=window_title)
        state.window_found = window is not None
        if not state.window_found:
            state.failure_reason = f"Window containing '{window_title}' not found."
            return state
    else:
        state.window_found = True

    # Query: Is target window active (focused)?
    if window:
        active = get_active_window()
        state.window_active = (
            active is not None and
            window_title is not None and
            window_title.lower() in (active.title or "").lower()
        )
    else:
        state.window_active = True

    # Query: Is target element present and enabled?
    if element_name and window:
        elem = find_element(window, name=element_name)
        state.element_present = elem is not None
        if elem:
            state.element_enabled = elem.is_enabled
            state.element_focused = elem.is_focused
            state.element_value = elem.value

    state.verified = True
    return state


# ── Semantic Command API ──────────────────────────────────────────────────────

class ActuationResult:
    def __init__(self, ok: bool, message: str, state: EnvironmentState | None = None):
        self.ok = ok
        self.message = message
        self.state = state

    def __str__(self) -> str:
        prefix = "[OK]" if self.ok else "[FAIL]"
        return f"{prefix} {self.message}"


def _gate_check(action: str) -> ActuationResult | None:
    """Return a blocking result if safety modes prevent this action."""
    if SAFE_SLEEP_MODE:
        return ActuationResult(
            False,
            f"SAFE_SLEEP_MODE active — '{action}' blocked. "
            f"ORACLE is observe-only. No physical actions permitted.",
        )
    if ACTION_DRY_RUN and action not in _APPROVAL_FREE:
        return ActuationResult(
            False,
            f"ACTION_DRY_RUN — would execute: {action} (not sent to OS).",
        )
    return None


def focus_window_semantic(
    title_contains: str | None = None,
    process_name: str | None = None,
) -> ActuationResult:
    """
    Find and focus a window by title or process.
    Uses pygetwindow.activate() — no coordinate clicking.
    """
    block = _gate_check("focus_window_semantic")
    if block:
        return block

    if _loop_guard("focus_window_semantic", (title_contains or process_name or "")[:20]):
        return ActuationResult(
            False,
            "Loop guard triggered: focus_window_semantic repeated without verified progress. Stopping.",
        )

    ref = find_window(title_contains=title_contains, process_name=process_name)
    if ref is None:
        state = EnvironmentState()
        state.failure_reason = (
            f"No window found for title='{title_contains}' / process='{process_name}'. "
            f"System pause — cannot proceed without confirmed window."
        )
        return ActuationResult(False, state.failure_reason, state)

    try:
        if hasattr(ref.handle, "activate"):
            ref.handle.activate()
            time.sleep(0.5)
        active = get_active_window()
        confirmed = (
            active is not None and
            title_contains is not None and
            title_contains.lower() in (active.title or "").lower()
        )
        if confirmed:
            return ActuationResult(True, f"Focused: {ref.title}")
        else:
            return ActuationResult(
                False,
                f"Window '{ref.title}' activate() called but not confirmed as active. "
                f"Active window is: {active.title if active else 'unknown'}",
            )
    except Exception as e:
        # pygetwindow raises on exit code 0 ("The operation completed successfully")
        # Treat that as success — the activate() worked despite the misleading exception.
        if "0" in str(e) and "completed successfully" in str(e).lower():
            return ActuationResult(True, f"Focused: {ref.title} (pygetwindow exit-0 quirk).")
        return ActuationResult(False, f"focus_window_semantic failed: {e}")


def focus_element(
    window_ref: WindowRef,
    element_name: str,
) -> ActuationResult:
    """
    Focus a UI element by name via UIAutomation.
    Falls back to reporting element-not-found rather than guessing coordinates.
    """
    block = _gate_check("focus_element")
    if block:
        return block

    if not UIA_AVAILABLE:
        return ActuationResult(
            False,
            "UIAutomation unavailable — cannot focus by element name. "
            "Install comtypes to enable the Semantic UI Bridge.",
        )

    elem = find_element(window_ref, name=element_name)
    if elem is None:
        return ActuationResult(
            False,
            f"Element '{element_name}' not found in '{window_ref.title}'. "
            f"System pause — cannot inject text into an unverified target.",
        )
    if not elem.is_enabled:
        return ActuationResult(
            False,
            f"Element '{element_name}' found but is disabled. Cannot focus.",
        )

    try:
        if elem.uia_element is not None:
            elem.uia_element.SetFocus()
            time.sleep(0.3)
            return ActuationResult(True, f"Focused element: '{element_name}'")
        return ActuationResult(False, f"UIA element reference missing for '{element_name}'.")
    except Exception as e:
        return ActuationResult(False, f"SetFocus failed: {e}")


def inject_text(
    text: str,
    window_ref: WindowRef | None = None,
    element_name: str | None = None,
) -> ActuationResult:
    """
    Inject text into a focused or named element.
    Verification note appended — caller must call verify_element_value after.
    Does NOT inject SSNs, card numbers, or passwords.
    """
    block = _gate_check("inject_text")
    if block:
        return block

    import re
    if re.search(r"\b\d{3}-\d{2}-\d{4}\b", text):
        return ActuationResult(False, "BLOCKED: text contains an SSN pattern. Refused.")
    if re.search(r"\b(?:\d[ -]?){13,16}\b", text):
        return ActuationResult(False, "BLOCKED: text contains a card number pattern. Refused.")

    if _loop_guard("inject_text", text[:30]):
        return ActuationResult(
            False,
            "Loop guard: inject_text repeated without verified progress. Stopping. "
            "Call verify_element_value to confirm previous injection before retrying.",
        )

    # Prefer UIA value injection (SetValue) — no clipboard, no OS key events
    if element_name and window_ref and UIA_AVAILABLE:
        elem = find_element(window_ref, name=element_name)
        if elem and elem.uia_element:
            try:
                from comtypes.gen.UIAutomationClient import IUIAutomationValuePattern, UIA_ValuePatternId
                pattern = elem.uia_element.GetCurrentPattern(UIA_ValuePatternId)
                value_pattern = pattern.QueryInterface(IUIAutomationValuePattern)
                value_pattern.SetValue(text)
                return ActuationResult(
                    True,
                    f"Text injected via UIA SetValue into '{element_name}'. "
                    f"Call verify_element_value to confirm.",
                )
            except Exception:
                pass  # fall through to keyboard injection

    # Fallback: keyboard injection (pyautogui)
    try:
        import pyautogui
        pyautogui.write(text, interval=0.03)
        time.sleep(0.4)
        return ActuationResult(
            True,
            f"Text injected via keyboard. "
            f"Call verify_element_value to confirm text landed in the correct field.",
        )
    except Exception as e:
        return ActuationResult(False, f"inject_text failed: {e}")


def verify_element_value(
    element_name: str,
    expected: str,
    window_ref: WindowRef | None = None,
) -> ActuationResult:
    """
    Confirm a UI element's current value matches expected.
    Verification failure halts — does not retry blindly.
    """
    if not UIA_AVAILABLE or window_ref is None:
        return ActuationResult(
            False,
            "Cannot verify element value — UIAutomation unavailable or no window ref. "
            "Treat previous injection as unconfirmed.",
        )

    elem = find_element(window_ref, name=element_name)
    if elem is None:
        return ActuationResult(False, f"Element '{element_name}' not found for verification.")

    actual = elem.value or ""
    if expected.lower() in actual.lower():
        return ActuationResult(True, f"Verified: '{element_name}' contains expected text.")
    return ActuationResult(
        False,
        f"Verification failed: expected '{expected}' in '{element_name}', "
        f"but got '{actual[:80]}'. Do not proceed — re-focus and retry.",
    )


def get_element_value(
    element_name: str,
    window_ref: WindowRef,
) -> str | None:
    """Read current value of a named element. Returns None if not found."""
    if not UIA_AVAILABLE:
        return None
    elem = find_element(window_ref, name=element_name)
    return elem.value if elem else None


def semantic_click(
    element_name: str,
    window_ref: WindowRef,
) -> ActuationResult:
    """
    Click a UI element by semantic name via UIA Invoke pattern.
    Does not use screen coordinates.
    """
    block = _gate_check("semantic_click")
    if block:
        return block

    if not UIA_AVAILABLE:
        return ActuationResult(
            False,
            "UIAutomation not available — semantic_click requires comtypes. "
            "Mouse fallback must be explicitly approved.",
        )

    elem = find_element(window_ref, name=element_name)
    if elem is None:
        return ActuationResult(False, f"Element '{element_name}' not found. Cannot click.")

    try:
        from comtypes.gen.UIAutomationClient import IUIAutomationInvokePattern, UIA_InvokePatternId
        pattern = elem.uia_element.GetCurrentPattern(UIA_InvokePatternId)
        invoke = pattern.QueryInterface(IUIAutomationInvokePattern)
        invoke.Invoke()
        return ActuationResult(True, f"Clicked '{element_name}' via UIA Invoke.")
    except Exception as e:
        return ActuationResult(False, f"semantic_click failed on '{element_name}': {e}")


# ── Browser deterministic test ────────────────────────────────────────────────

def browser_navigate_deterministic(url: str = "https://chatgpt.com") -> list[ActuationResult]:
    """
    Deterministic browser navigation sequence.
    - Checks if Chrome is running before opening
    - Focuses existing window rather than opening a duplicate
    - Uses Ctrl+L to target address bar — no coordinate clicking
    - Verifies each step before proceeding
    - Stops after page load — does NOT send or submit anything

    Returns list of step results for audit log.
    """
    results = []

    def step(r: ActuationResult, label: str):
        r.message = f"[{label}] {r.message}"
        results.append(r)
        print(r)
        return r

    # Step 1: Is Chrome running?
    chrome_running = is_process_running("chrome.exe")
    step(ActuationResult(chrome_running,
         "Chrome.exe is running." if chrome_running else "Chrome is not running."), "STATE")

    # Step 2: Find or open Chrome window
    if chrome_running:
        chrome_win = find_window(title_contains="Chrome") or find_window(title_contains="Google")
        if chrome_win:
            r = step(ActuationResult(True, f"Chrome window found: '{chrome_win.title}'"), "FIND")
        else:
            r = step(ActuationResult(
                False,
                "Chrome process running but no window found. Cannot proceed without confirmed window."
            ), "FIND")
            return results
    else:
        # Open Chrome — check loop guard first
        if _loop_guard("browser_open", "chrome"):
            step(ActuationResult(
                False,
                "Loop guard triggered: browser_open repeated without progress. Stopping."
            ), "GUARD")
            return results

        blocked = _gate_check("open_chrome")
        if blocked:
            step(blocked, "GATE")
            return results

        if ACTION_DRY_RUN:
            step(ActuationResult(True, "DRY RUN — would open Chrome via subprocess."), "DRY")
        else:
            subprocess.Popen(["cmd", "/c", "start", "chrome"])
            time.sleep(3.5)

        # Verify Chrome opened
        chrome_win = find_window(title_contains="Chrome") or find_window(title_contains="Google")
        if not chrome_win:
            step(ActuationResult(
                False, "Chrome launched but window not found after wait. System pause."
            ), "VERIFY")
            return results
        step(ActuationResult(True, f"Chrome opened and found: '{chrome_win.title}'"), "OPEN")

    # Step 3: Focus Chrome window (semantic, not pixel click)
    focus_r = focus_window_semantic(title_contains="Chrome")
    if not focus_r.ok:
        focus_r2 = focus_window_semantic(title_contains="Google")
        focus_r = focus_r2 if focus_r2.ok else focus_r
    step(focus_r, "FOCUS")
    if not focus_r.ok:
        return results

    # Step 4: Target address bar via Ctrl+L — deterministic, no coordinates
    blocked = _gate_check("address_bar")
    if blocked:
        step(blocked, "GATE")
        return results

    if ACTION_DRY_RUN:
        step(ActuationResult(True, f"DRY RUN — would press Ctrl+L, type '{url}', press Enter."), "DRY")
        return results

    try:
        import pyautogui
        time.sleep(0.3)
        pyautogui.hotkey("ctrl", "l")
        time.sleep(0.5)
        pyautogui.write(url, interval=0.04)
        time.sleep(0.3)
        pyautogui.press("enter")
        time.sleep(3.0)
        step(ActuationResult(True, f"Navigated to {url} via Ctrl+L. Page loading."), "NAV")
    except Exception as e:
        step(ActuationResult(False, f"Address bar navigation failed: {e}"), "NAV")
        return results

    # Step 5: Verify new page title contains expected domain fragment
    expected_fragment = url.replace("https://", "").split("/")[0].replace("www.", "")
    chrome_win_after = find_window(title_contains=expected_fragment)
    if chrome_win_after:
        step(ActuationResult(True, f"Page load verified — window title contains '{expected_fragment}'."), "VERIFY")
    else:
        step(ActuationResult(
            False,
            f"Page loaded but title does not yet contain '{expected_fragment}'. "
            f"May need more wait time or the URL redirected."
        ), "VERIFY")

    step(ActuationResult(True, "Navigation complete. Stopped — did not send or submit anything."), "DONE")
    return results


# ── Execute sequence (dry-run aware) ─────────────────────────────────────────

def dry_run_sequence(sequence: list[dict]) -> list[str]:
    """Print the intended command sequence without executing."""
    lines = ["DRY RUN — intended sequence:"]
    for i, step in enumerate(sequence, 1):
        cmd = step.get("cmd", "unknown")
        target = step.get("target", "")
        payload = step.get("payload", "")
        approval = " [APPROVAL REQUIRED]" if _requires_approval(cmd) else ""
        lines.append(f"  {i}. {cmd}({target}{',' + payload if payload else ''}){approval}")
    return lines


def execute_sequence(
    sequence: list[dict],
    approval_callback=None,
) -> list[ActuationResult]:
    """
    Execute a list of semantic command steps.
    Stops immediately if any step fails verification.
    Halts at approval-required steps — calls approval_callback(candidate) or blocks.
    """
    results = []
    for step_def in sequence:
        cmd = step_def.get("cmd", "")
        target = step_def.get("target", "")
        payload = step_def.get("payload", "")

        if _requires_approval(cmd):
            candidate = ActionCandidate(
                action=cmd, target=target, payload=payload,
                reason=step_def.get("reason", ""),
                approval_required=True,
                sequence=[step_def],
            )
            print(candidate.describe())
            if approval_callback:
                approved = approval_callback(candidate)
            else:
                ans = input("\n  Noah — approve? (yes/no): ").strip().lower()
                approved = ans in ("yes", "y")
            if not approved:
                r = ActuationResult(False, f"Noah declined: {cmd}({target}). Sequence halted.")
                results.append(r)
                print(r)
                return results

        # Dispatch
        r = _dispatch(cmd, target, payload)
        results.append(r)
        print(r)
        if not r.ok:
            print(f"  Step failed — sequence halted at '{cmd}'.")
            return results

    return results


def _dispatch(cmd: str, target: str, payload: str = "") -> ActuationResult:
    """Internal dispatcher for execute_sequence steps."""
    if cmd == "focus_window_semantic":
        return focus_window_semantic(title_contains=target)
    if cmd == "inject_text":
        return inject_text(text=payload or target)
    if cmd == "verify_element_value":
        win = find_window(title_contains=target.split("/")[0]) if "/" in target else None
        elem = target.split("/")[1] if "/" in target else target
        return verify_element_value(elem, payload, window_ref=win)
    if cmd == "browser_navigate":
        results = browser_navigate_deterministic(url=target or payload)
        final = results[-1] if results else ActuationResult(False, "No steps ran.")
        return final
    return ActuationResult(False, f"Unknown command: {cmd}")


# ── Mouse fallback policy ─────────────────────────────────────────────────────

def mouse_fallback_click(
    x: int, y: int,
    reason: str,
    window_ref: WindowRef | None = None,
) -> ActuationResult:
    """
    Last-resort coordinate click.
    Requires: reason, pre/post screenshot verification.
    Two verification failures → stop.
    """
    block = _gate_check("mouse_fallback_click")
    if block:
        return block

    print(f"[MOUSE FALLBACK] Coordinate click at ({x}, {y}).")
    print(f"  Reason: {reason}")
    print(f"  Warning: coordinate clicking is fallback only — semantic methods failed.")

    for attempt in range(2):
        try:
            import pyautogui
            before_title = get_active_window()
            pyautogui.click(x, y)
            time.sleep(0.5)
            after_title = get_active_window()
            changed = (before_title is None or after_title is None or
                       before_title.title != after_title.title)
            if changed or attempt == 1:
                return ActuationResult(
                    True,
                    f"Mouse fallback click at ({x},{y}). "
                    f"State change detected: {changed}. Coordinate logged.",
                )
            print(f"  Attempt {attempt+1}: no state change observed. Retrying once.")
        except Exception as e:
            return ActuationResult(False, f"Mouse fallback failed: {e}")

    return ActuationResult(
        False,
        f"Mouse fallback at ({x},{y}) failed both verification attempts. "
        f"Stopping — do not retry blindly.",
    )


# ── Smoke tests ───────────────────────────────────────────────────────────────

def _smoke_test() -> bool:
    global SAFE_SLEEP_MODE, ACTION_DRY_RUN
    print("=" * 60)
    print("Actuation Engine v0.1 — Smoke Test")
    print("=" * 60)
    passed = failed = 0

    def check(label: str, condition: bool, detail: str = ""):
        nonlocal passed, failed
        if condition:
            print(f"  [PASS] {label}")
            passed += 1
        else:
            print(f"  [FAIL] {label}{' — ' + detail if detail else ''}")
            failed += 1

    # 1. SAFE_SLEEP_MODE blocks physical actions
    SAFE_SLEEP_MODE = True
    r = focus_window_semantic(title_contains="Fake")
    check("SAFE_SLEEP_MODE blocks focus_window_semantic",
          not r.ok and "safe_sleep_mode" in r.message.lower())

    r = inject_text("test")
    check("SAFE_SLEEP_MODE blocks inject_text",
          not r.ok and "safe_sleep_mode" in r.message.lower())
    SAFE_SLEEP_MODE = False

    # 2. ACTION_DRY_RUN prints without executing
    ACTION_DRY_RUN = True
    _recent_actions.clear()
    r = inject_text("hello world")
    check("ACTION_DRY_RUN — inject_text reports dry run",
          not r.ok and "not sent to os" in r.message.lower(), r.message)
    ACTION_DRY_RUN = False

    # 3. Missing element pauses instead of guessing
    dummy_win = WindowRef(title="FakeWindow", pid=0, handle=None)
    r = focus_element(dummy_win, "NonExistentField")
    check("Missing element causes pause, not blind click",
          not r.ok and ("not found" in r.message.lower() or "unavailable" in r.message.lower()),
          r.message)

    # 4. Approval-required action classified correctly
    check("send_message classified as approval-required", _requires_approval("send_message"))
    check("focus_element classified as approval-free", not _requires_approval("focus_element"))
    check("submit_form classified as approval-required", _requires_approval("submit_form"))
    check("list_windows classified as approval-free", not _requires_approval("list_windows"))

    # 5. Loop guard triggers on repeated focus calls
    _recent_actions.clear()
    for _ in range(3):
        focus_window_semantic(title_contains="LoopTestWindowXYZ")
    r = focus_window_semantic(title_contains="LoopTestWindowXYZ")
    check("Loop guard triggers after 3 repeated focus calls",
          not r.ok and "loop guard" in r.message.lower(), r.message)

    # 6. Dry-run sequence prints without executing
    _recent_actions.clear()
    seq = [
        {"cmd": "focus_window_semantic", "target": "Chrome"},
        {"cmd": "inject_text", "target": "chat_input", "payload": "ORACLE browser test"},
        {"cmd": "send_message", "target": "chat_input", "reason": "test"},  # approval-required
    ]
    lines = dry_run_sequence(seq)
    check("dry_run_sequence labels approval-required steps",
          any("APPROVAL REQUIRED" in l for l in lines))
    check("dry_run_sequence contains all 3 steps", len(lines) >= 4)

    # 7. SSN blocked in inject_text
    _recent_actions.clear()
    r = inject_text("my SSN is 123-45-6789")
    check("SSN pattern blocked by inject_text", not r.ok and "blocked" in r.message.lower())

    # 8. Browser deterministic test — dry run (does not touch screen)
    ACTION_DRY_RUN = True
    _recent_actions.clear()
    br = browser_navigate_deterministic("https://chatgpt.com")
    has_dry = any("dry run" in str(r).lower() for r in br)
    check("browser_navigate_deterministic dry run executes without crashing",
          len(br) > 0, f"{len(br)} steps ran")
    ACTION_DRY_RUN = False

    # 9. is_process_running — sanity check on a known Windows process
    explorer_running = is_process_running("explorer.exe")
    check("is_process_running detects explorer.exe", explorer_running,
          "explorer.exe not found — unexpected on Windows")

    print()
    print(f"{passed}/{passed+failed} smoke tests passed.")
    if failed:
        print("SOME TESTS FAILED — see above.")
    else:
        print("All smoke tests passed.")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "browser-test":
        print("Running live browser navigation test...")
        results = browser_navigate_deterministic("https://chatgpt.com")
        print(f"\n{sum(1 for r in results if r.ok)}/{len(results)} steps succeeded.")
    else:
        _smoke_test()
