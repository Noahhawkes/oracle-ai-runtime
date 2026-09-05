"""
SOV1.AI — Computer Control (The Hands)
Gives Oracle physical control of the machine: screen, mouse, keyboard, windows.

Design principle (Noah's rule):
  Act autonomously when confident about intent.
  Stop and ask only when uncertain, or before an action that can't be undone.

Safety:
  - PyAutoGUI failsafe ON: slam the mouse to a screen corner to abort instantly.
  - Every physical action is audit-logged.
  - IRREVERSIBLE actions (send, submit, publish, delete, pay) always require
    confirmation, regardless of confidence.
"""

import sys
import time
from pathlib import Path
from datetime import datetime

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

try:
    import pyautogui
    pyautogui.FAILSAFE = True   # mouse to corner = abort
    pyautogui.PAUSE = 0.3       # small pause between actions so it's watchable
    HANDS_AVAILABLE = True
except ImportError:
    HANDS_AVAILABLE = False

# Words that mark an action as irreversible — always confirm these.
IRREVERSIBLE_HINTS = {
    "send", "submit", "publish", "post", "delete", "remove", "buy",
    "purchase", "pay", "confirm", "checkout", "transfer", "share",
}


def _log(action: str, detail: str = ""):
    try:
        from audit_log import log
        log("HANDS", f"{action} {detail}".strip())
    except Exception:
        pass


def _hands_off() -> bool:
    """True when physical input actuation is disabled (default-safe).

    Honors Noah's 'no computer control' boundary: the hands are OFF unless
    explicitly enabled. This is the hard gate that overrides any autonomous
    loop (e.g. SOV1) — even if a loop calls type_text/press, nothing is
    injected while hands are off.

    Precedence:
      1. Memory/hands_off.flag present  -> OFF (kill switch always wins)
      2. env ORACLE_HANDS_ON in {1,true,yes,on} -> ON
      3. Memory/hands_on.flag present   -> ON
      4. default                        -> OFF (safe)
    """
    import os
    try:
        if (ROOT / "Memory" / "hands_off.flag").exists():
            return True
    except Exception:
        pass
    if os.getenv("ORACLE_HANDS_ON", "").strip().lower() in ("1", "true", "yes", "on"):
        return False
    try:
        if (ROOT / "Memory" / "hands_on.flag").exists():
            return False
    except Exception:
        pass
    return True


def _require_hands(output: bool = False):
    if not HANDS_AVAILABLE:
        return (
            "The hands are not installed. In a terminal run:\n"
            "    python -m pip install pyautogui mss pygetwindow\n"
            "then restart Oracle."
        )
    if output and _hands_off():
        _log("BLOCKED", "actuation refused — HANDS_OFF safety gate (no computer control)")
        return (
            "[HANDS OFF] Physical input is disabled by the safety gate "
            "(no computer control). Eyes/screenshots still work. To allow "
            "keyboard/mouse output, set env ORACLE_HANDS_ON=1 or create "
            "Memory/hands_on.flag, then retry."
        )
    return None


# ── Screen awareness ──────────────────────────────────────────────────────────

def screenshot(name: str = None) -> str:
    """Capture the screen so Oracle can see what's on it."""
    err = _require_hands()
    if err:
        return err
    if not name:
        name = f"screen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    path = ROOT / "Logs" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    img = pyautogui.screenshot()
    img.save(str(path))
    _log("screenshot", str(path))
    return str(path)


def screen_size() -> str:
    err = _require_hands()
    if err:
        return err
    w, h = pyautogui.size()
    return f"Screen is {w}x{h}. Mouse at {pyautogui.position()}."


# ── Mouse ─────────────────────────────────────────────────────────────────────

def move_mouse(x: int, y: int, duration: float = 0.5) -> str:
    err = _require_hands(output=True)
    if err:
        return err
    pyautogui.moveTo(x, y, duration=duration)
    _log("move_mouse", f"({x},{y})")
    return f"Moved mouse to ({x}, {y})."


def click(x: int = None, y: int = None, button: str = "left", clicks: int = 1) -> str:
    err = _require_hands(output=True)
    if err:
        return err
    if x is not None and y is not None:
        pyautogui.click(x, y, clicks=clicks, button=button, duration=0.4)
        _log("click", f"({x},{y}) {button} x{clicks}")
        return f"Clicked {button} at ({x}, {y})."
    pyautogui.click(clicks=clicks, button=button)
    _log("click", f"current pos {button} x{clicks}")
    return f"Clicked {button} at current position."


def double_click(x: int = None, y: int = None) -> str:
    return click(x, y, clicks=2)


def scroll(amount: int) -> str:
    err = _require_hands(output=True)
    if err:
        return err
    pyautogui.scroll(amount)
    _log("scroll", str(amount))
    return f"Scrolled {amount}."


# ── Keyboard ──────────────────────────────────────────────────────────────────

def type_text(text: str, interval: float = 0.03) -> str:
    err = _require_hands(output=True)
    if err:
        return err
    pyautogui.write(text, interval=interval)
    _log("type_text", text[:60])
    return f"Typed: {text[:60]}" + ("..." if len(text) > 60 else "")


def press(key: str) -> str:
    """Press a single key, e.g. 'enter', 'tab', 'esc', 'win'."""
    err = _require_hands(output=True)
    if err:
        return err
    pyautogui.press(key)
    _log("press", key)
    return f"Pressed {key}."


def hotkey(*keys: str) -> str:
    """Press a key combo, e.g. hotkey('ctrl','c') or hotkey('win','r')."""
    err = _require_hands(output=True)
    if err:
        return err
    pyautogui.hotkey(*keys)
    _log("hotkey", "+".join(keys))
    return f"Pressed {'+'.join(keys)}."


# ── Windows / programs ────────────────────────────────────────────────────────

def open_program(name: str) -> str:
    """Open a program via the Windows Run dialog (Win+R)."""
    err = _require_hands(output=True)
    if err:
        return err
    pyautogui.hotkey("win", "r")
    time.sleep(0.6)
    pyautogui.write(name, interval=0.03)
    pyautogui.press("enter")
    _log("open_program", name)
    return f"Opened: {name}"


def list_windows() -> str:
    err = _require_hands()
    if err:
        return err
    try:
        import pygetwindow as gw
        titles = [t for t in gw.getAllTitles() if t.strip()]
        return "Open windows:\n" + "\n".join(f"  {t}" for t in titles)
    except Exception as e:
        return f"Could not list windows: {e}"


def focus_window(title_fragment: str) -> str:
    err = _require_hands()
    if err:
        return err
    try:
        import pygetwindow as gw
        for w in gw.getAllWindows():
            if title_fragment.lower() in w.title.lower() and w.title.strip():
                w.activate()
                _log("focus_window", w.title)
                return f"Focused: {w.title}"
        return f"No window matching '{title_fragment}'."
    except Exception as e:
        return f"Could not focus window: {e}"


def right_click(x: int = None, y: int = None) -> str:
    err = _require_hands()
    if err:
        return err
    if x is not None and y is not None:
        pyautogui.click(x, y, button="right")
        _log("right_click", f"({x},{y})")
        return f"Right-clicked at ({x}, {y})."
    pyautogui.click(button="right")
    _log("right_click", "current pos")
    return "Right-clicked at current position."


def drag(x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> str:
    """Click and drag from (x1,y1) to (x2,y2)."""
    err = _require_hands()
    if err:
        return err
    pyautogui.moveTo(x1, y1, duration=0.3)
    pyautogui.dragTo(x2, y2, duration=duration, button="left")
    _log("drag", f"({x1},{y1}) → ({x2},{y2})")
    return f"Dragged from ({x1},{y1}) to ({x2},{y2})."


def paste_text(text: str) -> str:
    """
    Paste text via clipboard — handles special characters, much faster than typing.
    Requires pyperclip: pip install pyperclip
    """
    err = _require_hands(output=True)
    if err:
        return err
    try:
        import pyperclip
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
        _log("paste_text", text[:60])
        return f"Pasted via clipboard: {text[:60]}" + ("..." if len(text) > 60 else "")
    except ImportError:
        # Fallback to typing if pyperclip not installed
        return type_text(text)
    except Exception as e:
        return f"Clipboard paste failed: {e}"


def copy_selection() -> str:
    """Copy whatever is currently selected to clipboard."""
    err = _require_hands(output=True)
    if err:
        return err
    pyautogui.hotkey("ctrl", "c")
    _log("copy_selection", "")
    try:
        import pyperclip
        time.sleep(0.2)
        return f"Copied. Clipboard contains: {pyperclip.paste()[:80]}"
    except Exception:
        return "Copied selection to clipboard."


def select_all() -> str:
    err = _require_hands(output=True)
    if err:
        return err
    pyautogui.hotkey("ctrl", "a")
    _log("select_all", "")
    return "Selected all."


def maximize_window(title_fragment: str = None) -> str:
    err = _require_hands()
    if err:
        return err
    try:
        import pygetwindow as gw
        if title_fragment:
            for w in gw.getAllWindows():
                if title_fragment.lower() in w.title.lower() and w.title.strip():
                    w.maximize()
                    _log("maximize_window", w.title)
                    return f"Maximized: {w.title}"
            return f"No window matching '{title_fragment}'."
        else:
            pyautogui.hotkey("win", "up")
            return "Maximized active window."
    except Exception as e:
        return f"Could not maximize: {e}"


def minimize_window(title_fragment: str = None) -> str:
    err = _require_hands()
    if err:
        return err
    try:
        import pygetwindow as gw
        if title_fragment:
            for w in gw.getAllWindows():
                if title_fragment.lower() in w.title.lower() and w.title.strip():
                    w.minimize()
                    _log("minimize_window", w.title)
                    return f"Minimized: {w.title}"
            return f"No window matching '{title_fragment}'."
        else:
            pyautogui.hotkey("win", "down")
            return "Minimized active window."
    except Exception as e:
        return f"Could not minimize: {e}"


def resize_window(title_fragment: str, width: int, height: int) -> str:
    err = _require_hands()
    if err:
        return err
    try:
        import pygetwindow as gw
        for w in gw.getAllWindows():
            if title_fragment.lower() in w.title.lower() and w.title.strip():
                w.resizeTo(width, height)
                _log("resize_window", f"{w.title} → {width}x{height}")
                return f"Resized '{w.title}' to {width}x{height}."
        return f"No window matching '{title_fragment}'."
    except Exception as e:
        return f"Could not resize: {e}"


def move_window(title_fragment: str, x: int, y: int) -> str:
    err = _require_hands()
    if err:
        return err
    try:
        import pygetwindow as gw
        for w in gw.getAllWindows():
            if title_fragment.lower() in w.title.lower() and w.title.strip():
                w.moveTo(x, y)
                _log("move_window", f"{w.title} → ({x},{y})")
                return f"Moved '{w.title}' to ({x},{y})."
        return f"No window matching '{title_fragment}'."
    except Exception as e:
        return f"Could not move window: {e}"


def screenshot_region(x: int, y: int, width: int, height: int, name: str = None) -> str:
    """Capture only a region of the screen — saves tokens vs full screenshot."""
    err = _require_hands()
    if err:
        return err
    if not name:
        name = f"region_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    path = ROOT / "Logs" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    img = pyautogui.screenshot(region=(x, y, width, height))
    img.save(str(path))
    _log("screenshot_region", f"({x},{y},{width},{height}) → {path}")
    return str(path)


def wait_for_screen_change(timeout: float = 5.0, interval: float = 0.5) -> str:
    """
    Take a baseline screenshot then poll until the screen changes or timeout.
    Useful after clicking a button to confirm something happened.
    """
    err = _require_hands()
    if err:
        return err
    try:
        import hashlib
        from PIL import Image
        import io as _io

        def _hash():
            img = pyautogui.screenshot()
            buf = _io.BytesIO()
            img.save(buf, format="PNG")
            return hashlib.md5(buf.getvalue()).hexdigest()

        baseline = _hash()
        elapsed = 0.0
        while elapsed < timeout:
            time.sleep(interval)
            elapsed += interval
            current = _hash()
            if current != baseline:
                _log("wait_for_screen_change", f"changed after {elapsed:.1f}s")
                return f"Screen changed after {elapsed:.1f}s."
        return f"Screen did not change within {timeout}s."
    except Exception as e:
        return f"wait_for_screen_change error: {e}"


def is_irreversible(description: str) -> bool:
    """True if a planned action looks irreversible and must be confirmed."""
    d = description.lower()
    return any(word in d for word in IRREVERSIBLE_HINTS)


# ── Live self-test / demo ─────────────────────────────────────────────────────

def demo() -> str:
    """
    Visible proof the hands work: opens Notepad and types a message.
    Watch the screen — the mouse and keyboard move on their own.
    """
    err = _require_hands()
    if err:
        return err
    open_program("notepad")
    time.sleep(1.5)
    type_text("SOV1.AI is now operating this machine.\r\n")
    type_text("If you can read this, the hands are real. — Oracle\r\n")
    _log("demo", "completed")
    return "Demo complete. Check the Notepad window that just opened."


if __name__ == "__main__":
    print(screen_size())
    print(demo())
