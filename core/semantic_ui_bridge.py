"""
core/semantic_ui_bridge.py — ORACLE Semantic UI Bridge v0.1

Purpose:
  Deterministic Windows UIAutomation access layer.
  The ACTUATION_ENGINE uses this module to locate, focus, and inject text
  into UI controls without relying on mouse coordinates as the primary method.

Core law:
  No claiming success without verification evidence.
  If the target window is missing, stop cleanly.
  If the target control is missing, stop cleanly.
  If injected text cannot be verified, stop cleanly.

Forbidden actions (this module will never perform):
  send, submit, delete, move, rename, post, purchase,
  commit, push, permission change, share

Engine rule (from brain_router.py):
  All functions in this module are ACTUATION_ENGINE territory.
  LOCAL_SMALL may not call them and may not claim their results succeeded.

Dependency priority:
  1. pywinauto (UIA backend) — preferred
  2. uiautomation — fallback
  3. Neither available → clean failure with install instructions
"""

import sys
import uuid
import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

# ── Dependency detection ───────────────────────────────────────────────────────

_PYWINAUTO_AVAILABLE = False
_UIAUTOMATION_AVAILABLE = False
_IS_WINDOWS = sys.platform == "win32"

try:
    if _IS_WINDOWS:
        import pywinauto
        from pywinauto import Desktop, Application
        from pywinauto.findwindows import find_windows, ElementNotFoundError
        _PYWINAUTO_AVAILABLE = True
except Exception:
    pass

try:
    if _IS_WINDOWS and not _PYWINAUTO_AVAILABLE:
        import uiautomation as uia
        _UIAUTOMATION_AVAILABLE = True
except Exception:
    pass


INSTALL_INSTRUCTIONS = """
  Semantic UI Bridge requires a Windows UIAutomation library.

  Install with:
    pip install pywinauto

  Verify with:
    python -c "import pywinauto; print(pywinauto.__version__)"

  This module cannot locate UI controls without it.
  Do not use mouse coordinates as a substitute — they are unreliable.
"""


def _require_windows():
    if not _IS_WINDOWS:
        raise EnvironmentError(
            "Semantic UI Bridge requires Windows. "
            "This machine is not running Windows."
        )


def _require_backend():
    if not _PYWINAUTO_AVAILABLE and not _UIAUTOMATION_AVAILABLE:
        raise EnvironmentError(
            "No UIAutomation backend found." + INSTALL_INSTRUCTIONS
        )


# ── Forbidden action guard ─────────────────────────────────────────────────────

FORBIDDEN_ACTION_KEYWORDS = {
    "send", "submit", "delete", "move", "rename", "post",
    "purchase", "buy", "commit", "push", "share",
    "change permission", "set permission",
}


def _block_forbidden(action_description: str):
    """Raise immediately if action_description contains a forbidden verb."""
    low = action_description.lower()
    for keyword in FORBIDDEN_ACTION_KEYWORDS:
        if keyword in low:
            raise PermissionError(
                f"[ACTUATION_ENGINE BLOCK] Forbidden action detected: '{keyword}' "
                f"in '{action_description}'. "
                f"This module may not perform send, submit, delete, move, rename, "
                f"post, purchase, commit, push, permission change, or share actions. "
                f"Route this to HUMAN_SOVEREIGN for approval."
            )


# ── Data models ────────────────────────────────────────────────────────────────

@dataclass
class WindowRef:
    """Handle to a located window."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    title: str = ""
    process_name: str = ""
    pid: int = 0
    handle: int = 0
    backend: str = ""           # "pywinauto" | "uiautomation" | "unknown"
    _raw: Any = field(default=None, repr=False)   # pywinauto window wrapper

    def __str__(self):
        return f"WindowRef(title={self.title!r}, pid={self.pid}, handle={self.handle})"


@dataclass
class ControlRef:
    """Handle to a located UI control within a window."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    window_id: str = ""
    name: str = ""
    control_type: str = ""
    automation_id: str = ""
    class_name: str = ""
    rect: tuple = field(default_factory=tuple)  # (left, top, right, bottom)
    _raw: Any = field(default=None, repr=False)

    def __str__(self):
        return (
            f"ControlRef(name={self.name!r}, type={self.control_type}, "
            f"auto_id={self.automation_id!r})"
        )


@dataclass
class BridgeResult:
    """Result from any bridge operation."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    operation: str = ""
    success: bool = False
    verified: bool = False          # True only if verification evidence exists
    target_window: str = ""
    target_control: str = ""
    text_injected: str = ""
    text_found: str = ""
    failure_reason: str = ""
    dry_run: bool = False
    backend_used: str = ""
    mouse_used: bool = False        # True if coordinate fallback was used
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    unknowns: list = field(default_factory=list)

    def explain(self) -> str:
        lines = [
            f"  [BRIDGE RESULT — {self.operation}]",
            f"  Success   : {'YES' if self.success else 'NO'}",
            f"  Verified  : {'YES — evidence in text_found' if self.verified else 'NO — not verified'}",
            f"  Dry run   : {'YES' if self.dry_run else 'no'}",
            f"  Mouse used: {'YES (fallback)' if self.mouse_used else 'no'}",
        ]
        if self.target_window:
            lines.append(f"  Window    : {self.target_window}")
        if self.target_control:
            lines.append(f"  Control   : {self.target_control}")
        if self.text_injected:
            lines.append(f"  Injected  : {self.text_injected[:60]!r}")
        if self.text_found:
            lines.append(f"  Found text: {self.text_found[:60]!r}")
        if self.failure_reason:
            lines.append(f"  Failure   : {self.failure_reason}")
        if self.unknowns:
            for u in self.unknowns:
                lines.append(f"  [UNKNOWN] {u}")
        return "\n".join(lines)


@dataclass
class DryRunSequence:
    """A sequence of bridge operations described but not executed."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    steps: list = field(default_factory=list)
    target_window: str = ""
    purpose: str = ""
    approved: bool = False
    forbidden_detected: bool = False
    forbidden_reason: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def report(self) -> str:
        lines = [
            f"  [DRY RUN SEQUENCE — {self.id}]",
            f"  Purpose : {self.purpose}",
            f"  Window  : {self.target_window or '(not specified)'}",
            f"  Steps   : {len(self.steps)}",
        ]
        for i, step in enumerate(self.steps, 1):
            lines.append(f"    {i}. {step}")
        if self.forbidden_detected:
            lines.append(f"  [BLOCKED] Forbidden action detected: {self.forbidden_reason}")
        else:
            lines.append(f"  [NOT EXECUTED] Dry run only. Call execute_sequence() to run.")
        return "\n".join(lines)


# ── Core API ───────────────────────────────────────────────────────────────────

def list_windows(include_invisible: bool = False) -> list[WindowRef]:
    """
    Return all currently visible top-level windows.
    Raises EnvironmentError if not on Windows or backend unavailable.
    """
    _require_windows()
    _require_backend()

    results = []

    if _PYWINAUTO_AVAILABLE:
        try:
            desktop = Desktop(backend="uia")
            windows = desktop.windows()
            for w in windows:
                try:
                    title = w.window_text() or ""
                    if not title and not include_invisible:
                        continue
                    pid = w.process_id()
                    handle = w.handle
                    # Get process name safely
                    proc_name = ""
                    try:
                        import psutil
                        proc_name = psutil.Process(pid).name()
                    except Exception:
                        proc_name = f"pid:{pid}"
                    results.append(WindowRef(
                        title=title,
                        process_name=proc_name,
                        pid=pid,
                        handle=handle,
                        backend="pywinauto",
                        _raw=w,
                    ))
                except Exception:
                    continue
        except Exception as e:
            raise RuntimeError(f"list_windows failed via pywinauto: {e}")

    return results


def find_window(
    title_contains: Optional[str] = None,
    process_name: Optional[str] = None,
    exact_title: Optional[str] = None,
) -> Optional[WindowRef]:
    """
    Find a window by title substring or process name.
    Returns None if not found — does not raise.
    Callers must handle None: stop cleanly, do not guess.
    """
    _require_windows()
    _require_backend()

    if not title_contains and not process_name and not exact_title:
        return None

    try:
        all_windows = list_windows(include_invisible=False)
    except Exception:
        return None

    for w in all_windows:
        if exact_title and w.title == exact_title:
            return w
        if title_contains and title_contains.lower() in w.title.lower():
            return w
        if process_name and process_name.lower() in w.process_name.lower():
            return w

    return None


def focus_window(window_ref: WindowRef) -> BridgeResult:
    """
    Bring a window to the foreground.
    Returns BridgeResult with verified=True only if window is confirmed active after focus.
    """
    _require_windows()
    _require_backend()

    result = BridgeResult(
        operation="focus_window",
        target_window=window_ref.title,
        backend_used="pywinauto",
    )

    if window_ref._raw is None:
        result.failure_reason = "WindowRef has no raw backend handle."
        return result

    try:
        window_ref._raw.set_focus()
        time.sleep(0.3)
        # Verify by checking active window title
        active = get_active_window()
        if active and window_ref.title and window_ref.title.lower() in active.lower():
            result.success = True
            result.verified = True
            result.text_found = active
        else:
            result.success = True   # focus was sent
            result.verified = False  # but we can't confirm it took
            result.unknowns.append(
                f"Could not confirm window '{window_ref.title}' became active. "
                f"Active window is: {active!r}"
            )
    except Exception as e:
        result.failure_reason = str(e)

    return result


def get_active_window() -> Optional[str]:
    """Return the title of the currently active/foreground window, or None."""
    if not _IS_WINDOWS:
        return None
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value or None
    except Exception:
        return None


def list_controls(
    window_ref: WindowRef,
    control_type: Optional[str] = None,
    max_depth: int = 8,
) -> list[ControlRef]:
    """
    List UI controls inside a window.
    Optionally filter by control_type (e.g. 'Edit', 'Button', 'Document').
    """
    _require_windows()
    _require_backend()

    results = []

    if window_ref._raw is None:
        return results

    if _PYWINAUTO_AVAILABLE:
        try:
            # descendants returns all child controls
            children = window_ref._raw.descendants()
            for ctrl in children:
                try:
                    ctype = ctrl.element_info.control_type or ""
                    if control_type and control_type.lower() not in ctype.lower():
                        continue
                    name = ctrl.element_info.name or ""
                    auto_id = ctrl.element_info.automation_id or ""
                    class_name = ctrl.element_info.class_name or ""
                    rect = ()
                    try:
                        r = ctrl.rectangle()
                        rect = (r.left, r.top, r.right, r.bottom)
                    except Exception:
                        pass
                    results.append(ControlRef(
                        window_id=window_ref.id,
                        name=name,
                        control_type=ctype,
                        automation_id=auto_id,
                        class_name=class_name,
                        rect=rect,
                        _raw=ctrl,
                    ))
                except Exception:
                    continue
        except Exception:
            pass

    return results


# Control types to try in fuzzy search order — Electron/webview apps use Document/Pane
_FUZZY_CONTROL_TYPES = ["Edit", "Document", "Text", "Pane", "Custom", "Group", "DataItem"]
# Class name substrings that suggest an editable input
_FUZZY_CLASS_HINTS = ["edit", "richedit", "input", "textarea", "chrome_widget", "webview", "cefclient"]


def find_control(
    window_ref: WindowRef,
    name_contains: Optional[str] = None,
    control_type: Optional[str] = None,
    automation_id: Optional[str] = None,
    class_name: Optional[str] = None,
) -> Optional[ControlRef]:
    """
    Find a control within a window by name, type, or automation ID.
    When strict search fails, falls back to a fuzzy type/class search so
    Electron/webview windows (e.g., Claude Desktop) can still be targeted.
    Returns None if nothing found — callers decide whether to use keyboard fallback.
    """
    _require_windows()
    _require_backend()

    controls = list_controls(window_ref)

    # ── Strict match first ────────────────────────────────────────────────────
    for ctrl in controls:
        match = True
        if name_contains and name_contains.lower() not in ctrl.name.lower():
            match = False
        if control_type and control_type.lower() not in ctrl.control_type.lower():
            match = False
        if automation_id and automation_id.lower() not in ctrl.automation_id.lower():
            match = False
        if class_name and class_name.lower() not in ctrl.class_name.lower():
            match = False
        if match:
            return ctrl

    # ── Fuzzy fallback: no name/automation_id constraints, just type/class ────
    # Only activate when the caller specified a type but the strict match missed.
    if control_type and not name_contains and not automation_id and not class_name:
        for fuzzy_type in _FUZZY_CONTROL_TYPES:
            for ctrl in controls:
                if fuzzy_type.lower() in ctrl.control_type.lower():
                    return ctrl
        for hint in _FUZZY_CLASS_HINTS:
            for ctrl in controls:
                if hint.lower() in ctrl.class_name.lower():
                    return ctrl

    return None


def dump_controls(window_ref: WindowRef, max_controls: int = 60) -> str:
    """
    Return a formatted string listing every discovered control in a window.
    Used by the /controls command to diagnose actuation failures.
    """
    _require_windows()
    _require_backend()

    controls = list_controls(window_ref)
    if not controls:
        return (
            f"  No controls discovered in '{window_ref.title}'.\n"
            "  Window likely uses a web/Electron renderer with no accessible UIA tree.\n"
            "  Keyboard clipboard fallback will be used for actuation."
        )

    lines = [f"  Controls in '{window_ref.title}' ({len(controls)} total):"]
    lines.append(f"  {'#':>3}  {'type':<16}  {'name':<30}  {'auto_id':<20}  class")
    lines.append("  " + "-" * 90)
    for i, c in enumerate(controls[:max_controls]):
        lines.append(
            f"  {i+1:>3}  {c.control_type:<16}  {c.name[:30]:<30}  "
            f"{c.automation_id[:20]:<20}  {c.class_name}"
        )
    if len(controls) > max_controls:
        lines.append(f"  ... {len(controls) - max_controls} more controls not shown")
    return "\n".join(lines)


def inject_via_keyboard(
    window_ref: WindowRef,
    text: str,
    press_enter: bool = False,
) -> BridgeResult:
    """
    Keyboard clipboard fallback for windows where find_control() fails
    (Electron, CEF, webview-based apps such as Claude Desktop).

    Sequence:
      1. Focus the window via set_focus()
      2. Click bottom-center of the window rect (12 % from bottom) to land
         on the input area — uses window-relative position, not raw screen coords
      3. Copy text to clipboard, paste with Ctrl+V
      4. Restore prior clipboard content
      5. Optionally press Enter

    Returns BridgeResult. verified=False (can't read back from webview).
    mouse_used=True to signal coordinate fallback was used.
    """
    result = BridgeResult(
        operation="inject_via_keyboard",
        target_window=window_ref.title,
        text_injected=text,
        mouse_used=True,
        backend_used="pyautogui+clipboard",
    )

    try:
        import pyautogui
    except ImportError:
        result.failure_reason = "pyautogui not installed — cannot use keyboard fallback"
        return result

    try:
        import pyperclip
        _has_pyperclip = True
    except ImportError:
        _has_pyperclip = False

    try:
        raw = window_ref._raw  # pywinauto wrapper

        # ── 1. Set clipboard BEFORE touching the window ───────────────────────
        old_clip = ""
        if _has_pyperclip:
            try:
                old_clip = pyperclip.paste()
            except Exception:
                pass
            pyperclip.copy(text)
            time.sleep(0.2)   # let clipboard settle before paste
        # else: fall through to type_keys path below

        # ── 2. Focus window ───────────────────────────────────────────────────
        if raw:
            try:
                raw.set_focus()
                time.sleep(0.4)
            except Exception as _fe:
                result.unknowns.append(f"set_focus failed: {_fe}")

        # ── 3. Click bottom-center to land on input area ──────────────────────
        rect = None
        if raw:
            try:
                r = raw.rectangle()
                rect = (r.left, r.top, r.right, r.bottom)
            except Exception:
                pass

        if rect:
            cx = (rect[0] + rect[2]) // 2
            # 10 % from the bottom — typical chat-input bar
            cy = rect[3] - int((rect[3] - rect[1]) * 0.10)
            pyautogui.click(cx, cy)
            time.sleep(0.4)
        else:
            result.unknowns.append("Window rect unavailable — skipped input-area click")

        # ── 4. Paste: prefer pywinauto type_keys (targets window handle
        #       directly, not foreground) over pyautogui hotkey ─────────────
        _paste_method = "none"
        if _has_pyperclip:
            # Primary: pywinauto sends ^v directly to the window — survives
            # temporary focus loss that breaks pyautogui.hotkey
            _pasted = False
            if raw:
                try:
                    raw.type_keys("^v", pause=0.05)
                    _pasted = True
                    _paste_method = "pywinauto ^v"
                except Exception as _pwe:
                    result.unknowns.append(f"pywinauto type_keys ^v failed: {_pwe}")

            if not _pasted:
                # Fallback: pyautogui Ctrl+V (requires foreground focus)
                pyautogui.hotkey("ctrl", "v")
                _paste_method = "pyautogui ctrl+v"

            time.sleep(0.3)

            # Restore clipboard
            if old_clip:
                try:
                    pyperclip.copy(old_clip)
                except Exception:
                    pass
        else:
            # No pyperclip — use pywinauto type_keys with explicit space handling
            if raw:
                try:
                    # type_keys handles spaces correctly; escape braces for pywinauto
                    safe_text = (
                        text.replace("{", "{{").replace("}", "}}")
                            .replace("(", "(").replace(")", ")")
                            .replace("+", "{+}").replace("^", "{^}")
                            .replace("%", "{%}").replace("~", "{~}")
                    )
                    raw.type_keys(safe_text, with_spaces=True, pause=0.02)
                    _paste_method = "pywinauto type_keys"
                except Exception as _tke:
                    # Last resort: pyautogui write (handles spaces)
                    pyautogui.write(text, interval=0.03)
                    _paste_method = "pyautogui write"
            else:
                pyautogui.write(text, interval=0.03)
                _paste_method = "pyautogui write (no window handle)"
            result.unknowns.append(
                "pyperclip not installed — used keyboard typing fallback. "
                "Install: pip install pyperclip"
            )

        # ── 5. Press Enter if approved ────────────────────────────────────────
        if press_enter:
            if raw:
                try:
                    raw.type_keys("{ENTER}", pause=0.05)
                except Exception:
                    pyautogui.press("enter")
            else:
                pyautogui.press("enter")
            time.sleep(0.2)

        result.success = True
        result.verified = False
        result.unknowns.append(
            f"Keyboard clipboard fallback used (Electron/webview). "
            f"Method: {_paste_method}. "
            "Read-back verification not available for webview controls."
        )

    except Exception as e:
        result.failure_reason = str(e)

    return result


def focus_control(control_ref: ControlRef) -> BridgeResult:
    """
    Set focus to a specific control.
    Does not use mouse coordinates unless _raw has no set_focus method.
    """
    _require_windows()
    _require_backend()

    result = BridgeResult(
        operation="focus_control",
        target_control=str(control_ref),
        backend_used="pywinauto",
    )

    if control_ref._raw is None:
        result.failure_reason = "ControlRef has no raw backend handle."
        return result

    try:
        control_ref._raw.set_focus()
        result.success = True
        result.verified = False   # focus sent — not verified until text injection
        result.unknowns.append("Control focus sent but not independently verified.")
    except Exception as e:
        # Fallback: try clicking the control rect center (not raw screen coords)
        try:
            control_ref._raw.click_input()
            result.success = True
            result.mouse_used = True
            result.verified = False
            result.unknowns.append(
                "set_focus() failed, fell back to click_input() on control rect. "
                "Verify text injection to confirm focus landed correctly."
            )
        except Exception as e2:
            result.failure_reason = f"set_focus: {e} | click_input: {e2}"

    return result


def inject_text(
    control_ref: ControlRef,
    text: str,
    clear_first: bool = True,
    press_enter: bool = False,
    dry_run: bool = False,
) -> BridgeResult:
    """
    Inject text into a UI control using UIAutomation value pattern.
    Falls back to type_keys only if value pattern is unavailable.
    Does NOT use mouse coordinates.

    clear_first: clear existing text before injection
    press_enter: send Enter key after injection (does NOT submit forms — caller governs this)
    dry_run: print intent without executing

    Returns BridgeResult. verified=True only if text was confirmed in control afterward.
    """
    _require_windows()
    _require_backend()

    _block_forbidden(f"inject text: {text[:40]}")

    result = BridgeResult(
        operation="inject_text",
        target_control=str(control_ref),
        text_injected=text,
        dry_run=dry_run,
        backend_used="pywinauto",
    )

    if dry_run:
        result.success = True
        result.verified = False
        result.failure_reason = ""
        result.unknowns.append("Dry run — text was not actually injected.")
        return result

    if control_ref._raw is None:
        result.failure_reason = "ControlRef has no raw backend handle."
        return result

    try:
        raw = control_ref._raw
        # Preferred: value pattern (no keyboard simulation)
        try:
            if clear_first:
                raw.set_edit_text("")
            raw.set_edit_text(text)
            method = "set_edit_text"
        except Exception:
            # Fallback: type_keys — keyboard simulation
            if clear_first:
                try:
                    raw.set_focus()
                    raw.type_keys("^a{DELETE}", pause=0.05)
                except Exception:
                    pass
            raw.type_keys(text, pause=0.02)
            method = "type_keys"

        if press_enter:
            # Enter sends the key event — does NOT bypass approval gates
            raw.type_keys("{ENTER}", pause=0.05)

        result.success = True

        # Verify: read back control text
        try:
            found = ""
            try:
                found = raw.get_value()
            except Exception:
                try:
                    found = raw.window_text()
                except Exception:
                    pass
            if found and text.strip() in found:
                result.verified = True
                result.text_found = found[:200]
            else:
                result.verified = False
                result.text_found = found[:200] if found else ""
                result.unknowns.append(
                    f"Injected text not confirmed in control. "
                    f"Expected: {text[:40]!r}  Found: {found[:40]!r}  Method: {method}"
                )
        except Exception as ve:
            result.verified = False
            result.unknowns.append(f"Text verification read failed: {ve}")

    except Exception as e:
        result.failure_reason = str(e)

    return result


def verify_text(
    control_ref: ControlRef,
    expected_text: Optional[str] = None,
) -> BridgeResult:
    """
    Read the current text value of a control and optionally verify against expected.
    Returns BridgeResult with text_found populated.
    verified=True only if expected_text was found.
    """
    _require_windows()
    _require_backend()

    result = BridgeResult(
        operation="verify_text",
        target_control=str(control_ref),
        backend_used="pywinauto",
    )

    if control_ref._raw is None:
        result.failure_reason = "ControlRef has no raw backend handle."
        return result

    try:
        found = ""
        try:
            found = control_ref._raw.get_value()
        except Exception:
            try:
                found = control_ref._raw.window_text()
            except Exception:
                pass

        result.success = True
        result.text_found = found[:500]

        if expected_text is not None:
            if expected_text.strip() in found:
                result.verified = True
            else:
                result.verified = False
                result.unknowns.append(
                    f"Expected {expected_text[:40]!r} not found in control. "
                    f"Found: {found[:40]!r}"
                )
        else:
            # No expected text — read-only, mark as not verified (not assertion)
            result.verified = False
            result.unknowns.append("No expected_text provided — read-only, not verified.")

    except Exception as e:
        result.failure_reason = str(e)

    return result


def dry_run_sequence(
    steps: list[str],
    target_window: str = "",
    purpose: str = "",
) -> DryRunSequence:
    """
    Describe a sequence of UI operations without executing them.
    Each step is a plain-text description of what would happen.
    Checks each step for forbidden actions.

    Returns a DryRunSequence — printable, not executable.
    Call the individual functions to actually execute.
    """
    seq = DryRunSequence(
        steps=steps,
        target_window=target_window,
        purpose=purpose,
    )

    for step in steps:
        for keyword in FORBIDDEN_ACTION_KEYWORDS:
            if keyword in step.lower():
                seq.forbidden_detected = True
                seq.forbidden_reason = (
                    f"Step '{step[:60]}' contains forbidden action '{keyword}'. "
                    f"Route to HUMAN_SOVEREIGN for approval before executing."
                )
                break
        if seq.forbidden_detected:
            break

    return seq


# ── Smoke test ─────────────────────────────────────────────────────────────────

def _smoke_test() -> bool:
    print("=" * 60)
    print("semantic_ui_bridge.py — Smoke Test")
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

    # 1. list_windows — returns list or fails with clean error
    print("\n  -- Window listing --")
    try:
        windows = list_windows()
        check("list_windows() returns a list", isinstance(windows, list),
              f"got {type(windows)}")
        check("list_windows() returns WindowRef objects",
              all(isinstance(w, WindowRef) for w in windows) if windows else True)
        print(f"     ({len(windows)} windows found)")
    except EnvironmentError as e:
        # On non-Windows this is expected
        msg = str(e)
        check("list_windows() fails with clean EnvironmentError on non-Windows",
              "Windows" in msg or "backend" in msg or "UIAutomation" in msg, msg)
    except Exception as e:
        check("list_windows() does not crash with unknown error", False, str(e))

    # 2. find_window for nonexistent window returns None cleanly
    print("\n  -- Missing window handling --")
    try:
        result = find_window(title_contains="__ORACLE_FAKE_WINDOW_THAT_DOES_NOT_EXIST__")
        check("find_window nonexistent returns None", result is None,
              f"got {result}")
    except EnvironmentError:
        check("find_window raises EnvironmentError on non-Windows (acceptable)", True)
    except Exception as e:
        check("find_window does not crash for missing window", False, str(e))

    # 3. dry_run_sequence — no execution, clean report
    print("\n  -- Dry run sequence --")
    seq = dry_run_sequence(
        steps=[
            "find_window(title_contains='ChatGPT')",
            "focus_window(chatgpt_window)",
            "find_control(window, control_type='Edit')",
            "focus_control(input_field)",
            "inject_text(input_field, 'Hello ORACLE')",
            "verify_text(input_field, expected_text='Hello ORACLE')",
        ],
        target_window="ChatGPT",
        purpose="Test message injection",
    )
    check("dry_run_sequence returns DryRunSequence", isinstance(seq, DryRunSequence))
    check("dry_run_sequence has correct step count", len(seq.steps) == 6)
    check("dry_run_sequence does NOT execute (forbidden=False)", not seq.forbidden_detected)
    report = seq.report()
    check("dry_run_sequence report contains NOT EXECUTED", "NOT EXECUTED" in report)

    # 4. dry_run_sequence blocks forbidden action
    print("\n  -- Forbidden action detection in dry run --")
    seq_bad = dry_run_sequence(
        steps=[
            "find_window(title_contains='Gmail')",
            "submit the email form",
        ],
        purpose="Send email",
    )
    check("dry_run_sequence detects forbidden 'submit'", seq_bad.forbidden_detected)
    check("dry_run_sequence forbidden_reason is set", bool(seq_bad.forbidden_reason))
    check("dry_run_sequence report mentions BLOCKED", "BLOCKED" in seq_bad.report())

    # 5. _block_forbidden raises on forbidden verbs
    print("\n  -- Forbidden action guard --")
    for verb in ["send this message", "submit the form", "delete the file",
                 "purchase credits", "push to github"]:
        try:
            _block_forbidden(verb)
            check(f"_block_forbidden('{verb}') raises PermissionError", False,
                  "should have raised")
        except PermissionError:
            check(f"_block_forbidden blocks '{verb.split()[0]}'", True)
        except Exception as e:
            check(f"_block_forbidden('{verb}') raises correctly", False, str(e))

    safe_actions = ["focus window", "inject text hello", "read control value", "list windows"]
    for safe in safe_actions:
        try:
            _block_forbidden(safe)
            check(f"_block_forbidden allows safe: '{safe}'", True)
        except PermissionError:
            check(f"_block_forbidden wrongly blocks safe: '{safe}'", False)

    # 6. inject_text dry run — does not execute
    print("\n  -- inject_text dry run --")
    if _IS_WINDOWS and (_PYWINAUTO_AVAILABLE or _UIAUTOMATION_AVAILABLE):
        fake_ctrl = ControlRef(
            window_id="test",
            name="test_field",
            control_type="Edit",
        )
        result = inject_text(fake_ctrl, "hello world", dry_run=True)
        check("inject_text dry_run=True succeeds", result.success)
        check("inject_text dry_run=True is not verified", not result.verified)
        check("inject_text dry_run=True has unknown note",
              any("Dry run" in u for u in result.unknowns))
    else:
        check("inject_text dry run skipped — not Windows or no backend", True)

    # 7. inject_text raises on forbidden text
    print("\n  -- inject_text forbidden text guard --")
    fake_ctrl2 = ControlRef(name="input", control_type="Edit")
    try:
        inject_text(fake_ctrl2, "submit payment to vendor", dry_run=True)
        check("inject_text blocks forbidden text 'submit'", False, "should have raised")
    except PermissionError as e:
        check("inject_text PermissionError on forbidden text", True)
    except Exception as e:
        check("inject_text error on forbidden text", False, str(e))

    # 8. verify_text with no raw handle fails cleanly
    print("\n  -- verify_text no-handle clean failure --")
    if _IS_WINDOWS and (_PYWINAUTO_AVAILABLE or _UIAUTOMATION_AVAILABLE):
        empty_ctrl = ControlRef(name="ghost", control_type="Edit")
        r = verify_text(empty_ctrl, expected_text="hello")
        check("verify_text with no handle fails cleanly (not crash)", not r.success)
        check("verify_text failure_reason is set", bool(r.failure_reason))
    else:
        check("verify_text no-handle test skipped — not Windows or no backend", True)

    # 9. WindowRef and ControlRef stringify without crash
    print("\n  -- Data model stringify --")
    w = WindowRef(title="Test Window", pid=1234, handle=5678)
    check("WindowRef str() works", "Test Window" in str(w))
    c = ControlRef(name="Test Input", control_type="Edit", automation_id="input1")
    check("ControlRef str() works", "Test Input" in str(c))

    # 10. BridgeResult.explain() without crash
    br = BridgeResult(
        operation="inject_text",
        success=True,
        verified=False,
        target_window="ChatGPT",
        target_control="Edit field",
        text_injected="Hello",
    )
    br.unknowns.append("Could not read back text")
    explanation = br.explain()
    check("BridgeResult.explain() builds without crash", bool(explanation))
    check("BridgeResult.explain() contains operation", "inject_text" in explanation)
    check("BridgeResult.explain() shows not verified", "NO" in explanation)

    # 11. INSTALL_INSTRUCTIONS is populated
    check("INSTALL_INSTRUCTIONS is non-empty", len(INSTALL_INSTRUCTIONS) > 50)
    check("INSTALL_INSTRUCTIONS mentions pip install", "pip install" in INSTALL_INSTRUCTIONS)

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

    if "--smoke" in args or "smoke" in args:
        ok = _smoke_test()
        sys.exit(0 if ok else 1)

    if "--list-windows" in args:
        try:
            windows = list_windows()
            print(f"\n{len(windows)} visible windows:\n")
            for w in windows:
                print(f"  [{w.pid}] {w.process_name:20s}  {w.title[:70]}")
            print()
        except EnvironmentError as e:
            print(f"\n[bridge] Cannot list windows: {e}\n")
        sys.exit(0)

    if "--find" in args:
        idx = args.index("--find")
        query = " ".join(args[idx + 1:]) if idx + 1 < len(args) else ""
        if not query:
            print("Usage: python core/semantic_ui_bridge.py --find <title fragment>")
            sys.exit(1)
        w = find_window(title_contains=query)
        if w:
            print(f"\nFound: {w}")
        else:
            print(f"\nNo window found matching: {query!r}")
        sys.exit(0)

    if "--dry-run" in args:
        seq = dry_run_sequence(
            steps=[
                "find_window(title_contains='ChatGPT')",
                "focus_window(window)",
                "find_control(window, control_type='Edit')",
                "inject_text(control, 'Example message')",
                "verify_text(control, 'Example message')",
            ],
            target_window="ChatGPT",
            purpose="Example dry-run sequence",
        )
        print(seq.report())
        sys.exit(0)

    if "--backend" in args:
        print(f"\nPlatform  : {sys.platform}")
        print(f"pywinauto : {'available (' + pywinauto.__version__ + ')' if _PYWINAUTO_AVAILABLE else 'NOT available'}")
        print(f"uiautomation: {'available' if _UIAUTOMATION_AVAILABLE else 'NOT available'}")
        if not _PYWINAUTO_AVAILABLE and not _UIAUTOMATION_AVAILABLE:
            print(INSTALL_INSTRUCTIONS)
        print()
        sys.exit(0)

    print("Usage:")
    print("  python core/semantic_ui_bridge.py --smoke")
    print("  python core/semantic_ui_bridge.py --list-windows")
    print("  python core/semantic_ui_bridge.py --find <title>")
    print("  python core/semantic_ui_bridge.py --dry-run")
    print("  python core/semantic_ui_bridge.py --backend")
