"""
core/targeted_input.py — Deterministic Targeted Text Input

The problem it solves:
  SOV1 was opening Notepad as a fallback when it couldn't type into Claude/ChatGPT.
  Blind mouse clicks were the primary text entry path. That doesn't work reliably.

The fix:
  1. Gate Notepad — only allowed when Noah explicitly requests it.
  2. Verify target before typing — active window must match intent.
  3. Clipboard paste is primary — type_text is last resort.
  4. Verify text appeared (screen hash or active window title check).
  5. 2-try limit — stop and report, never spiral.

Core law:
  ORACLE uses the keyboard and clipboard.
  ORACLE does not use mouse clicks as the primary way to type.
  If ORACLE cannot verify the typed text appeared, it stops and reports why.
"""

import sys
import time
import hashlib
import io
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

# ── App classification ─────────────────────────────────────────────────────────
# Apps where text should go via clipboard paste + verification, not blind click

CHAT_APPS = {
    "chatgpt", "claude", "chat.openai.com", "anthropic",
}
BROWSER_APPS = {
    "chrome", "msedge", "edge", "firefox", "brave", "opera",
}
TERMINAL_APPS = {
    "powershell", "cmd", "command prompt", "terminal", "windows terminal",
    "oracle", "python",
}
FILE_EDITOR_APPS = {
    "notepad++", "vscode", "code", "sublime", "atom", "vim",
}

# Notepad is ONLY allowed when Noah explicitly says one of these
NOTEPAD_EXPLICIT_TRIGGERS = {
    "open notepad", "open note", "notepad", "draft in notepad",
    "use notepad", "launch notepad", "start notepad",
}

# Apps that must NOT fall back to Notepad
NO_NOTEPAD_FALLBACK = CHAT_APPS | BROWSER_APPS | TERMINAL_APPS | {"write_file", "file"}


# ── Result dataclass ───────────────────────────────────────────────────────────

@dataclass
class TargetedTextInputResult:
    target_app: str = ""
    target_window: str = ""
    target_control: str = ""
    intended_text: str = ""
    method_used: str = ""          # clipboard_paste | type_text | semantic_inject | skipped
    success: bool = False
    verification: str = ""         # verified | unverified | not_attempted
    failure_reason: str = ""
    retries: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def summary(self) -> str:
        status = "OK" if self.success else "FAILED"
        lines = [
            f"  [{status}] TargetedTextInput",
            f"  Target    : {self.target_app} / {self.target_window[:50]}",
            f"  Method    : {self.method_used}",
            f"  Verified  : {self.verification}",
            f"  Retries   : {self.retries}",
        ]
        if self.failure_reason:
            lines.append(f"  FAILURE   : {self.failure_reason}")
        return "\n".join(lines)


# ── Notepad gate ───────────────────────────────────────────────────────────────

def is_notepad_allowed(goal: str) -> bool:
    """Return True only if Noah explicitly asked for Notepad."""
    goal_lower = goal.lower().strip()
    return any(trigger in goal_lower for trigger in NOTEPAD_EXPLICIT_TRIGGERS)


def check_notepad_fallback(program_name: str, current_goal: str = "") -> Optional[str]:
    """
    Return a blocking message if Notepad is about to be opened as a fallback.
    Returns None if Notepad is allowed.
    """
    if "notepad" not in program_name.lower():
        return None
    # Check if current goal explicitly requests Notepad
    if current_goal and is_notepad_allowed(current_goal):
        return None
    # Block it
    return (
        "NOTEPAD BLOCKED: Notepad was not explicitly requested by Noah. "
        "Do not use Notepad as a fallback for typing into Claude, ChatGPT, or any browser. "
        "To type into a chat app: focus the window, then use paste_text(). "
        "To write a file: use write_file() directly. "
        "If Noah wants Notepad, he will say 'open Notepad' explicitly."
    )


# ── Active window detection ────────────────────────────────────────────────────

def get_active_window_title() -> str:
    """Return the title of the currently active/foreground window."""
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value
    except Exception:
        pass

    try:
        import pygetwindow as gw
        active = gw.getActiveWindow()
        return active.title if active else ""
    except Exception:
        return ""


def window_matches_target(active_title: str, target_app: str) -> bool:
    """Check if the active window matches the intended target."""
    title_lower = active_title.lower()
    target_lower = target_app.lower()

    # Direct match
    if target_lower in title_lower:
        return True

    # App family matches
    if target_lower in CHAT_APPS:
        return any(app in title_lower for app in CHAT_APPS)
    if target_lower in BROWSER_APPS:
        return any(app in title_lower for app in BROWSER_APPS)
    if target_lower in TERMINAL_APPS:
        return any(app in title_lower for app in TERMINAL_APPS)

    return False


# ── Screen state hashing ───────────────────────────────────────────────────────

def _screen_hash() -> str:
    """Fast screen hash for before/after comparison."""
    try:
        import pyautogui
        img = pyautogui.screenshot()
        buf = io.BytesIO()
        img.resize((320, 180)).save(buf, format="PNG")
        return hashlib.md5(buf.getvalue()).hexdigest()
    except Exception:
        return ""


# ── Semantic input field finder ────────────────────────────────────────────────

def find_input_field(window_title: str) -> Optional[object]:
    """
    Use UIAutomation to find the text input control in the active window.
    Returns control object if found, None otherwise.
    """
    try:
        from pywinauto import Desktop
        desk = Desktop(backend="uia")
        for win in desk.windows():
            try:
                t = win.window_text() or ""
                if any(frag in t.lower() for frag in window_title.lower().split()):
                    for ctrl_type in ("Edit", "Document", "Text", "RichEdit"):
                        try:
                            ctrl = win.child_window(control_type=ctrl_type)
                            if ctrl.exists():
                                return ctrl
                        except Exception:
                            pass
            except Exception:
                pass
    except Exception:
        pass
    return None


# ── Primary text injection ─────────────────────────────────────────────────────

def inject_text(
    text: str,
    target_app: str = "",
    target_window_title: str = "",
    press_enter: bool = False,
    approved_send: bool = False,
    max_retries: int = 2,
) -> TargetedTextInputResult:
    """
    Primary text injection function.

    Strategy:
      1. Verify active window matches target_app.
      2. Try semantic UIAutomation inject (pywinauto).
      3. Fall back to clipboard paste (Ctrl+V).
      4. Verify text appeared via screen hash change.
      5. If not verified after max_retries, stop and report.
      6. Only press Enter if press_enter=True AND approved_send=True.

    Never opens Notepad. Never clicks blindly to focus.
    """
    result = TargetedTextInputResult(
        target_app=target_app,
        target_window=target_window_title,
        intended_text=text[:80] + ("..." if len(text) > 80 else ""),
    )

    # Step 1: verify active window
    active = get_active_window_title()
    if target_app and not window_matches_target(active, target_app):
        result.failure_reason = (
            f"Active window is '{active[:60]}', not '{target_app}'. "
            f"Use focus_window('{target_app}') first, then call inject_text() again."
        )
        result.verification = "not_attempted"
        return result

    result.target_window = active

    # Step 2: screen hash before
    h_before = _screen_hash()

    # Step 3a: try semantic UIAutomation inject
    ctrl = find_input_field(active)
    if ctrl:
        try:
            ctrl.set_focus()
            time.sleep(0.2)
            import pyperclip
            pyperclip.copy(text)
            ctrl.type_keys("^a", pause=0.05)
            ctrl.type_keys("^v", pause=0.1)
            time.sleep(0.4)
            h_after = _screen_hash()
            result.method_used = "semantic_inject"
            result.retries = 0
            if h_before != h_after:
                result.success = True
                result.verification = "verified"
            else:
                result.verification = "unverified"
                result.failure_reason = "Screen hash unchanged after semantic inject. Text may not have appeared."
        except Exception as e:
            result.method_used = "semantic_inject_failed"
            result.failure_reason = f"UIAutomation inject failed: {e}"
    else:
        result.method_used = "clipboard_paste"

    # Step 3b: clipboard paste fallback
    if not result.success and result.retries < max_retries:
        for attempt in range(max_retries):
            result.retries = attempt + 1
            try:
                import pyperclip
                import pyautogui
                pyperclip.copy(text)
                time.sleep(0.2)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.5)
                h_after = _screen_hash()
                result.method_used = "clipboard_paste"
                if h_before != h_after:
                    result.success = True
                    result.verification = "verified"
                    break
                else:
                    result.verification = "unverified"
                    if attempt < max_retries - 1:
                        time.sleep(0.5)  # brief pause before retry
            except Exception as e:
                result.failure_reason = f"Clipboard paste failed on attempt {attempt + 1}: {e}"

    if not result.success and not result.failure_reason:
        result.failure_reason = (
            f"Text could not be verified after {result.retries} attempt(s). "
            f"The input field may not be focused, or the app may not show the text. "
            f"Run ACTION_DIAGNOSTIC to inspect the current state."
        )

    # Step 4: Enter gate — only if explicitly approved
    if result.success and press_enter:
        if not approved_send:
            result.failure_reason = (
                "Text injected but ENTER NOT PRESSED. "
                "Sending requires Noah's approval. "
                "Type APPROVE_SEND to confirm, then re-run with approved_send=True."
            )
        else:
            try:
                import pyautogui
                time.sleep(0.2)
                pyautogui.press("enter")
                result.verification = "sent_with_approval"
            except Exception as e:
                result.failure_reason = f"Could not press Enter: {e}"

    return result


# ── No-progress loop guard ─────────────────────────────────────────────────────

class TypingLoopGuard:
    """
    Tracks typing attempts and kills spirals.

    Stop conditions:
    - open_program called 2x without any verified typing
    - focus_window called 3x without verified typing
    - type_text / paste_text returned unverified 2x
    - Notepad opened without explicit user request
    - Step limit reached without any verified typed progress
    """

    def __init__(self):
        self.open_program_count: int = 0
        self.focus_window_count: int = 0
        self.unverified_type_count: int = 0
        self.verified_type_count: int = 0
        self.notepad_opened: bool = False
        self.last_open_program: str = ""
        self.last_focus_target: str = ""
        self._history: list = []   # (action, arg, verified)

    def record(self, action: str, arg: str, verified: bool = False):
        self._history.append((action, arg[:40], verified))
        self._history = self._history[-20:]

        if action == "open_program":
            if "notepad" in arg.lower():
                self.notepad_opened = True
            self.open_program_count += 1
            self.last_open_program = arg

        elif action == "focus_window":
            self.focus_window_count += 1
            self.last_focus_target = arg

        elif action in ("type_text", "paste_text"):
            if verified:
                self.verified_type_count += 1
                # Progress detected — reset failure counters
                self.unverified_type_count = 0
                self.open_program_count = 0
                self.focus_window_count = 0
            else:
                self.unverified_type_count += 1

    def check(self, current_goal: str = "") -> Optional[str]:
        """Return stop message if a spiral is detected, else None."""

        if self.notepad_opened and not is_notepad_allowed(current_goal):
            return (
                "LOOP GUARD: Notepad was opened but not explicitly requested. "
                "Stop and refocus. To type into Claude/ChatGPT: "
                "use focus_window() then paste_text(). "
                "Do not use Notepad as a workaround."
            )

        if self.open_program_count >= 2 and self.verified_type_count == 0:
            return (
                f"LOOP GUARD: open_program called {self.open_program_count} times "
                f"(last: '{self.last_open_program}') without any verified text input. "
                f"The program is already open or the target is not responding. "
                f"Use focus_window() to bring it to the front, then paste_text()."
            )

        if self.focus_window_count >= 3 and self.verified_type_count == 0:
            return (
                f"LOOP GUARD: focus_window called {self.focus_window_count} times "
                f"(last: '{self.last_focus_target}') without verified text input. "
                f"The window may not exist or may have a different title. "
                f"Use ACTION_DIAGNOSTIC to check the current state."
            )

        if self.unverified_type_count >= 2:
            return (
                f"LOOP GUARD: type_text/paste_text returned unverified {self.unverified_type_count} times. "
                f"The input field is not receiving the text. "
                f"Use ACTION_DIAGNOSTIC, then try: "
                f"1) focus_window again  2) click the input field  3) paste_text()."
            )

        return None

    def reset(self):
        self.open_program_count = 0
        self.focus_window_count = 0
        self.unverified_type_count = 0
        self.verified_type_count = 0
        self.notepad_opened = False
        self._history.clear()

    def history(self) -> list:
        return list(self._history)


# ── ACTION_DIAGNOSTIC ──────────────────────────────────────────────────────────

def action_diagnostic(
    intended_target: str = "",
    last_actions: list = None,
    guard: Optional[TypingLoopGuard] = None,
) -> str:
    """
    Print a diagnostic snapshot of the current typing/action state.
    Called when Noah types ACTION_DIAGNOSTIC, or when SOV1 gives up.
    """
    active = get_active_window_title()
    lines = [
        "",
        "  [ACTION DIAGNOSTIC]",
        f"  Current active window : {active or '(unknown)'}",
        f"  Intended target       : {intended_target or '(not set)'}",
        f"  Window matches target : {window_matches_target(active, intended_target) if intended_target else 'N/A'}",
        "",
    ]

    if guard:
        lines += [
            f"  open_program calls    : {guard.open_program_count}",
            f"  focus_window calls    : {guard.focus_window_count}",
            f"  unverified type calls : {guard.unverified_type_count}",
            f"  verified type count   : {guard.verified_type_count}",
            f"  Notepad opened?       : {guard.notepad_opened}",
            "",
        ]
        if guard.history():
            lines.append("  Last actions:")
            for action, arg, verified in guard.history()[-10:]:
                v = "verified" if verified else "unverified"
                lines.append(f"    {action}({arg}) [{v}]")
            lines.append("")

    if last_actions:
        lines.append("  Last SOV1 actions:")
        for a in last_actions[-10:]:
            lines.append(f"    {a}")
        lines.append("")

    # Recommendations
    lines.append("  Recommendations:")
    if active and "notepad" in active.lower():
        lines.append("    - Notepad is active. Close it and use focus_window(target) + paste_text().")
    if intended_target and not window_matches_target(active, intended_target):
        lines.append(f"    - Target '{intended_target}' is not in focus.")
        lines.append(f"      Run: focus_window('{intended_target}')")
        lines.append(f"      Then: paste_text('<your message>')")
    else:
        lines.append("    - Window appears to match target. Try paste_text() directly.")
    lines.append("")

    return "\n".join(lines)


# ── Module-level guard (used by sov1.py) ──────────────────────────────────────

_typing_guard = TypingLoopGuard()


def get_typing_guard() -> TypingLoopGuard:
    return _typing_guard


def reset_typing_guard():
    _typing_guard.reset()


# ── Smoke test ────────────────────────────────────────────────────────────────

def _smoke_test() -> bool:
    print("=" * 60)
    print("targeted_input.py — Smoke Test (no desktop actions)")
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

    # ── Notepad gate tests ────────────────────────────────────────────────────

    # 1. Notepad blocked when not requested
    msg = check_notepad_fallback("notepad", current_goal="type a message to ChatGPT")
    check("Notepad blocked when goal is ChatGPT typing", msg is not None)
    check("Block message mentions Notepad", msg and "NOTEPAD BLOCKED" in msg)

    # 2. Notepad allowed when explicitly requested
    msg2 = check_notepad_fallback("notepad", current_goal="open Notepad and write a note")
    check("Notepad allowed when explicitly requested", msg2 is None)

    # 3. Notepad blocked for file write goal
    msg3 = check_notepad_fallback("notepad", current_goal="write output to a file")
    check("Notepad blocked for file write goal", msg3 is not None)

    # 4. Non-notepad programs are not blocked
    msg4 = check_notepad_fallback("chrome", current_goal="open chrome")
    check("Non-notepad programs pass gate", msg4 is None)

    # ── is_notepad_allowed ────────────────────────────────────────────────────
    check("'open notepad' allows Notepad", is_notepad_allowed("open notepad please"))
    check("'use notepad' allows Notepad", is_notepad_allowed("use notepad for this"))
    check("'type in chatgpt' does NOT allow Notepad", not is_notepad_allowed("type in chatgpt"))
    check("'write file' does NOT allow Notepad", not is_notepad_allowed("write the config file"))

    # ── Window match tests ────────────────────────────────────────────────────
    check("'ChatGPT - Chrome' matches chatgpt target",
          window_matches_target("ChatGPT - Google Chrome", "chatgpt"))
    check("'ORACLE Terminal' matches powershell target",
          window_matches_target("Windows PowerShell", "powershell"))
    check("'Notepad' does NOT match chatgpt target",
          not window_matches_target("Untitled - Notepad", "chatgpt"))
    check("'Claude' matches claude target",
          window_matches_target("Claude - Google Chrome", "claude"))

    # ── TypingLoopGuard tests ─────────────────────────────────────────────────
    guard = TypingLoopGuard()

    # 5. open_program 2x without verified typing -> stop
    guard.record("open_program", "chrome")
    guard.record("open_program", "chrome")
    stop = guard.check(current_goal="navigate to chatgpt")
    check("Loop guard triggers after 2 open_program without typing", stop is not None)
    check("Loop guard message mentions open_program", stop and "open_program" in stop)

    # 6. reset clears state
    guard.reset()
    stop2 = guard.check()
    check("Guard is clear after reset", stop2 is None)

    # 7. focus_window 3x without typing -> stop
    guard2 = TypingLoopGuard()
    guard2.record("focus_window", "chatgpt")
    guard2.record("focus_window", "chatgpt")
    guard2.record("focus_window", "chatgpt")
    stop3 = guard2.check()
    check("Loop guard triggers after 3 focus_window without typing", stop3 is not None)
    check("Loop guard message mentions focus_window", stop3 and "focus_window" in stop3)

    # 8. verified typing resets open_program and focus_window counts
    guard3 = TypingLoopGuard()
    guard3.record("open_program", "chrome")
    guard3.record("focus_window", "chatgpt")
    guard3.record("type_text", "hello world", verified=True)
    guard3.record("open_program", "chrome")   # only 1 after reset
    stop4 = guard3.check()
    check("Verified typing resets spiral counters", stop4 is None)

    # 9. unverified type 2x -> stop
    guard4 = TypingLoopGuard()
    guard4.record("type_text", "hello", verified=False)
    guard4.record("paste_text", "hello", verified=False)
    stop5 = guard4.check()
    check("Loop guard triggers after 2 unverified type_text/paste_text", stop5 is not None)
    check("Message mentions unverified", stop5 and "unverified" in stop5.lower())

    # 10. Notepad-opened guard
    guard5 = TypingLoopGuard()
    guard5.record("open_program", "notepad")
    stop6 = guard5.check(current_goal="answer a question in chatgpt")
    check("Loop guard triggers when Notepad opened without request", stop6 is not None)
    check("Message mentions Notepad fallback", stop6 and "Notepad" in stop6)

    # 11. Notepad opened with explicit request is NOT stopped
    guard6 = TypingLoopGuard()
    guard6.record("open_program", "notepad")
    stop7 = guard6.check(current_goal="open notepad and write a note")
    check("Notepad allowed when explicitly requested in goal", stop7 is None)

    # ── ACTION_DIAGNOSTIC ─────────────────────────────────────────────────────
    diag = action_diagnostic(
        intended_target="chatgpt",
        last_actions=["open_program(notepad)", "type_text(hello)", "focus_window(chatgpt)"],
        guard=guard4,
    )
    check("action_diagnostic builds without crash", True)
    check("Diagnostic mentions active window", "active window" in diag.lower())
    check("Diagnostic has recommendations", "Recommendations" in diag)

    # ── TargetedTextInputResult ───────────────────────────────────────────────
    r = TargetedTextInputResult(
        target_app="chatgpt",
        target_window="ChatGPT - Chrome",
        intended_text="What is the best architecture?",
        method_used="clipboard_paste",
        success=True,
        verification="verified",
        retries=1,
    )
    summary = r.summary()
    check("TargetedTextInputResult.summary() builds", True)
    check("Summary contains method", "clipboard_paste" in summary)
    check("Summary contains verification", "verified" in summary)

    print(f"\n{passed}/{passed + failed} smoke tests passed.")
    if failed:
        print(f"FAILED: {failed} test(s).")
    else:
        print("All smoke tests passed.")
    return failed == 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if "--smoke" in sys.argv or "smoke" in sys.argv:
        ok = _smoke_test()
        sys.exit(0 if ok else 1)
    else:
        # Quick status when run directly
        print(f"Active window: {get_active_window_title()}")
        diag = action_diagnostic(intended_target="chatgpt")
        print(diag)
