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


def _require_hands():
    if not HANDS_AVAILABLE:
        return (
            "The hands are not installed. In a terminal run:\n"
            "    python -m pip install pyautogui mss pygetwindow\n"
            "then restart Oracle."
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
    err = _require_hands()
    if err:
        return err
    pyautogui.moveTo(x, y, duration=duration)
    _log("move_mouse", f"({x},{y})")
    return f"Moved mouse to ({x}, {y})."


def click(x: int = None, y: int = None, button: str = "left", clicks: int = 1) -> str:
    err = _require_hands()
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
    err = _require_hands()
    if err:
        return err
    pyautogui.scroll(amount)
    _log("scroll", str(amount))
    return f"Scrolled {amount}."


# ── Keyboard ──────────────────────────────────────────────────────────────────

def type_text(text: str, interval: float = 0.03) -> str:
    err = _require_hands()
    if err:
        return err
    pyautogui.write(text, interval=interval)
    _log("type_text", text[:60])
    return f"Typed: {text[:60]}" + ("..." if len(text) > 60 else "")


def press(key: str) -> str:
    """Press a single key, e.g. 'enter', 'tab', 'esc', 'win'."""
    err = _require_hands()
    if err:
        return err
    pyautogui.press(key)
    _log("press", key)
    return f"Pressed {key}."


def hotkey(*keys: str) -> str:
    """Press a key combo, e.g. hotkey('ctrl','c') or hotkey('win','r')."""
    err = _require_hands()
    if err:
        return err
    pyautogui.hotkey(*keys)
    _log("hotkey", "+".join(keys))
    return f"Pressed {'+'.join(keys)}."


# ── Windows / programs ────────────────────────────────────────────────────────

def open_program(name: str) -> str:
    """Open a program via the Windows Run dialog (Win+R)."""
    err = _require_hands()
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
