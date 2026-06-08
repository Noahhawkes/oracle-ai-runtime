"""
core/claude_code_bridge.py — ORACLE → Claude Code Bridge

ORACLE routes code questions, build tasks, and implementation requests to
Claude Code rather than attempting them with the local model. Claude Code
has full codebase context; qwen2.5:7b does not.

Three modes:
  ask_claude(prompt)         — subprocess `claude -p`, returns answer as text
  type_into_claude(prompt)   — finds the live Claude Code terminal window and
                               types the message directly into it (autonomous)
  open_claude_session(prompt)— launches a new Claude Code terminal with a
                               handoff message

type_into_claude is the autonomous path: ORACLE takes over the mouse and
keyboard to deliver a message to Claude Code without Noah having to type
anything. It is governed — SAFE_SLEEP blocks it, and the audit log records
every injection.

Usage:
    from claude_code_bridge import ask_claude, type_into_claude, open_claude_session, is_code_task
"""

import re
import subprocess
import sys
import shutil
import time
from pathlib import Path
from datetime import datetime, timezone

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

# Window title fragments that identify a Claude Code terminal
_CLAUDE_TITLE_FRAGMENTS = [
    "claude", "claude code", "claude-code",
    # common terminal hosts
    "windows powershell", "powershell", "cmd.exe", "windows terminal",
    "conemu", "cmder",
]
# We narrow by title AND by checking if the process is running `claude`
_CLAUDE_PROCESS_NAMES = {"node.exe", "claude.exe", "claude"}


# ── Secret scanner ────────────────────────────────────────────────────────────

_SECRET_PATTERNS = [
    r"sk-[A-Za-z0-9]{20,}",                      # OpenAI / Anthropic keys
    r"api[_\-]?key\s*[=:]\s*\S+",                # api_key = ...
    r"secret\s*[=:]\s*\S{6,}",                   # secret = ...
    r"password\s*[=:]\s*\S{4,}",                 # password = ...
    r"token\s*[=:]\s*[A-Za-z0-9\-._~+/]{20,}",  # token = long_value
    r"bearer\s+[A-Za-z0-9\-._~+/]{20,}",         # Bearer <token>
]


def contains_secret(text: str) -> bool:
    """Return True if text appears to contain a credential or secret pattern."""
    for pat in _SECRET_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def scrub_secrets(text: str) -> str:
    """Replace secret patterns with [REDACTED]."""
    for pat in _SECRET_PATTERNS:
        text = re.sub(pat, "[REDACTED]", text, flags=re.IGNORECASE)
    return text


# ── Claude Code CLI detection ──────────────────────────────────────────────────

def _claude_exe() -> str | None:
    # 1. Standard PATH lookup
    found = shutil.which("claude")
    if found:
        return found

    # 2. Windows npm global install locations — shutil.which misses these when
    #    Python's subprocess PATH doesn't include AppData\Roaming\npm
    import os
    candidates = []
    appdata = os.environ.get("APPDATA", "")
    userprofile = os.environ.get("USERPROFILE", "")
    if appdata:
        candidates += [
            os.path.join(appdata, "npm", "claude.cmd"),
            os.path.join(appdata, "npm", "claude"),
        ]
    if userprofile:
        candidates += [
            os.path.join(userprofile, "AppData", "Roaming", "npm", "claude.cmd"),
            os.path.join(userprofile, "AppData", "Local", "npm", "claude.cmd"),
            os.path.join(userprofile, ".npm-global", "bin", "claude"),
        ]
    # Also try nvm / fnm / volta install paths
    for env_var in ("NVM_HOME", "VOLTA_HOME", "FNM_DIR"):
        base = os.environ.get(env_var, "")
        if base:
            candidates.append(os.path.join(base, "bin", "claude"))
            candidates.append(os.path.join(base, "bin", "claude.cmd"))

    # Claude Code desktop app on Windows bundles claude.exe in a versioned subdir
    # under %APPDATA%\Claude\claude-code\<version>\claude.exe — glob for latest version
    if appdata:
        versioned_base = os.path.join(appdata, "Claude", "claude-code")
        if os.path.isdir(versioned_base):
            try:
                versions = sorted(
                    [d for d in os.listdir(versioned_base)
                     if os.path.isdir(os.path.join(versioned_base, d))],
                    reverse=True,
                )
                for v in versions:
                    exe = os.path.join(versioned_base, v, "claude.exe")
                    if os.path.isfile(exe):
                        candidates.insert(0, exe)  # highest priority — known good path
                        break
            except Exception:
                pass

    for path in candidates:
        if os.path.isfile(path):
            return path

    return None


def claude_available() -> bool:
    return _claude_exe() is not None


# ── SAFE_SLEEP gate ────────────────────────────────────────────────────────────

def _is_safe_sleep() -> bool:
    try:
        from governance import get
        return bool(get("ORACLE_SAFE_SLEEP_DEFAULT", False))
    except Exception:
        return False


def _audit(action: str, detail: str = ""):
    try:
        from audit_log import log
        log("CLAUDE_BRIDGE", f"{action} {detail}".strip())
    except Exception:
        pass


# ── Window finder ──────────────────────────────────────────────────────────────

def find_claude_window() -> dict | None:
    """
    Search open windows for a Claude Code terminal session.

    Strategy:
      1. pywinauto UIA — find windows whose title contains 'claude'
      2. pygetwindow fallback — same title scan
      3. If no title match, look for any terminal window running node.exe
         (the Claude Code process tree) via psutil

    Returns a dict with title/handle/method, or None.
    """
    # 1. pywinauto UIA
    try:
        from pywinauto import Desktop
        desk = Desktop(backend="uia")
        for win in desk.windows():
            try:
                title = (win.window_text() or "").lower()
                if "claude" in title:
                    return {
                        "title": win.window_text(),
                        "handle": win.handle,
                        "method": "pywinauto_title",
                    }
            except Exception:
                pass
    except Exception:
        pass

    # 2. pygetwindow
    try:
        import pygetwindow as gw
        for w in gw.getAllWindows():
            if "claude" in w.title.lower():
                return {
                    "title": w.title,
                    "handle": getattr(w, "_hWnd", 0),
                    "method": "pygetwindow_title",
                }
    except Exception:
        pass

    # 3. psutil: find a terminal whose child is node (Claude Code runs on Node)
    try:
        import psutil
        import ctypes

        def get_window_for_pid(pid: int) -> int | None:
            """Return the top-level HWND for a given PID, or None."""
            result = []

            def callback(hwnd, _):
                _, wpid = ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(ctypes.c_ulong()))
                # GetWindowThreadProcessId second arg needs to be a pointer
                lp_pid = ctypes.c_ulong()
                ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lp_pid))
                if lp_pid.value == pid:
                    result.append(hwnd)
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
            ctypes.windll.user32.EnumWindows(WNDENUMPROC(callback), 0)
            return result[0] if result else None

        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                name = (proc.info["name"] or "").lower()
                cmdline = " ".join(proc.info["cmdline"] or []).lower()
                if name == "node.exe" and "claude" in cmdline:
                    parent = proc.parent()
                    if parent:
                        hwnd = get_window_for_pid(parent.pid)
                        if hwnd:
                            buf = ctypes.create_unicode_buffer(512)
                            ctypes.windll.user32.GetWindowTextW(hwnd, buf, 512)
                            return {
                                "title": buf.value or f"Terminal (PID {parent.pid})",
                                "handle": hwnd,
                                "method": "psutil_node_parent",
                            }
            except Exception:
                pass
    except Exception:
        pass

    return None


# ── Focus a window ─────────────────────────────────────────────────────────────

def _focus_window(win: dict) -> bool:
    handle = win.get("handle", 0)
    title = win.get("title", "")

    try:
        from pywinauto import Desktop
        desk = Desktop(backend="uia")
        for w in desk.windows():
            try:
                if w.handle == handle or w.window_text() == title:
                    w.set_focus()
                    time.sleep(0.3)
                    return True
            except Exception:
                pass
    except Exception:
        pass

    try:
        import pygetwindow as gw
        wins = gw.getWindowsWithTitle(title)
        if wins:
            wins[0].activate()
            time.sleep(0.3)
            return True
    except Exception:
        pass

    if handle:
        try:
            import ctypes
            ctypes.windll.user32.SetForegroundWindow(handle)
            time.sleep(0.3)
            return True
        except Exception:
            pass

    return False


# ── Autonomous type-into-Claude ────────────────────────────────────────────────

def type_into_claude(
    prompt: str,
    context: str = "",
    open_if_missing: bool = True,
) -> tuple[bool, str]:
    """
    Find the live Claude Code terminal window and type `prompt` into it,
    then press Enter — as if Noah had typed it himself.

    Governed:
      - SAFE_SLEEP blocks all typing.
      - Every injection is audit-logged.
      - pyautogui failsafe is active (mouse to corner = abort).

    If no Claude Code window is found and open_if_missing=True, a new
    session is launched first.

    Returns (success, detail).
    """
    if _is_safe_sleep():
        return False, "SAFE_SLEEP active — autonomous typing blocked."

    _audit("type_into_claude", f"prompt[:60]={prompt[:60]!r}")

    win = find_claude_window()

    if win is None:
        if open_if_missing:
            ok, detail = open_claude_session(prompt, context)
            if ok:
                _audit("type_into_claude", "opened new session instead of typing")
            return ok, detail
        return False, "No Claude Code window found and open_if_missing=False."

    # Focus the window
    if not _focus_window(win):
        return False, f"Could not focus Claude Code window: {win.get('title')}"

    # Use pyautogui to type the message
    try:
        import pyautogui
        full = _build_prompt(prompt, context)

        # Use clipboard for multi-line / long messages — avoids key-repeat issues
        try:
            import pyperclip
            pyperclip.copy(full)
            time.sleep(0.2)
            pyautogui.hotkey("ctrl", "v")
        except Exception:
            # Fallback: typewrite (ASCII-safe only)
            pyautogui.typewrite(full[:500], interval=0.02)

        time.sleep(0.15)
        pyautogui.press("enter")
        _audit("type_into_claude", f"typed and submitted to '{win.get('title')}'")
        return True, f"Message delivered to Claude Code window '{win.get('title')}'."
    except Exception as e:
        return False, f"pyautogui error: {e}"


# ── Non-interactive subprocess ask ────────────────────────────────────────────

def ask_claude(
    prompt: str,
    context: str = "",
    timeout: int = 120,
    cwd: str | None = None,
) -> tuple[bool, str]:
    """
    Run `claude -p "<prompt>"` as a subprocess and return (success, text).
    Silent — no window opened, answer returned inline.
    """
    exe = _claude_exe()
    if not exe:
        return False, (
            "Claude Code CLI not found on PATH. "
            "Install: npm install -g @anthropic-ai/claude-code"
        )

    full_prompt = _build_prompt(prompt, context)
    work_dir = cwd or str(ROOT)

    try:
        result = subprocess.run(
            [exe, "-p", full_prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=work_dir,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            return True, result.stdout.strip() or "(no output)"
        err = (result.stderr or result.stdout or "unknown error").strip()
        return False, f"Exit {result.returncode}: {err}"
    except subprocess.TimeoutExpired:
        return False, f"Claude Code did not respond within {timeout}s."
    except Exception as e:
        return False, f"Bridge error: {e}"


# ── Interactive session launcher ───────────────────────────────────────────────

def open_claude_session(
    prompt: str = "",
    context: str = "",
    cwd: str | None = None,
) -> tuple[bool, str]:
    """
    Open a new interactive `claude` session in a new PowerShell window.
    If prompt is given, it is written to a temp file and piped in on launch.
    """
    exe = _claude_exe()
    if not exe:
        return False, "Claude Code CLI not found on PATH."

    work_dir = cwd or str(ROOT)

    try:
        if prompt:
            full = _build_prompt(prompt, context)
            tmp = ROOT / "Memory" / "_claude_session_prompt.txt"
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(full, encoding="utf-8")
            # Open PS window, cd to repo, pipe prompt into claude
            ps_cmd = f"cd '{work_dir}'; Get-Content '{tmp}' | {exe}"
        else:
            ps_cmd = f"cd '{work_dir}'; {exe}"

        subprocess.Popen(
            ["powershell", "-NoExit", "-Command", ps_cmd],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_CONSOLE,
        )
        _audit("open_claude_session", f"prompt[:60]={prompt[:60]!r}")
        return True, "Claude Code session opened in new terminal."
    except Exception as e:
        return False, f"Could not open Claude Code session: {e}"


# ── Code-task classifier ───────────────────────────────────────────────────────

_CODE_KEYWORDS = {
    # Implementation verbs
    "implement", "build", "code", "create", "write", "add", "fix", "refactor",
    "edit", "update", "change", "modify", "delete", "remove", "rename",
    "scaffold", "generate", "deploy", "integrate", "wire up", "hook up",
    # File / code references
    "core/", ".py", ".ts", ".js", ".json", "file", "function", "class",
    "module", "import", "endpoint", "route", "schema", "database", "api",
    # Build pass / MYTHIC references
    "step ", "mythic", "build pass", "handoff", "hand off", "hand-off",
    "voice_hooks", "voice.py", "oracle.py", "tui", "oracle_tui",
    # Architecture / design
    "architecture", "design", "pattern", "structure", "refactor", "plan",
    # Question patterns about code
    "does ", "where is", "what file", "how does", "explain the code",
    "check if", "look at", "read the", "find the", "show me the",
    "what does", "why does", "how is", "what is the",
    # Action patterns often directed at code work
    "paste", "inject", "insert", "send this", "post this",
}

# Phrases that mean the user or ORACLE is directly addressing Claude Code
_CLAUDE_DIRECT_PATTERNS = [
    "into claude", "into the claude", "tell claude", "ask claude",
    "paste this into", "paste into", "send to claude", "hand off to claude",
    "hand to claude", "into this window", "into the new claude",
    "into the session", "into claude code", "to claude code",
    "for claude", "give claude", "show claude",
    "with claude", "using claude", "via claude",
    "code yourself", "code yourself with", "let claude", "have claude",
    # Screen/hands control — local model cannot do these, bridge handles them
    "take over", "keyboard", "mouse", "screen control", "take control",
    "type into", "click on", "move the mouse", "open claude",
]


def is_claude_directed(text: str) -> bool:
    """Return True if the message is explicitly addressed to / directed at Claude Code."""
    lower = text.lower()
    return any(p in lower for p in _CLAUDE_DIRECT_PATTERNS)


def is_code_task(text: str) -> bool:
    lower = text.lower()
    return is_claude_directed(text) or any(kw in lower for kw in _CODE_KEYWORDS)


# ── Prompt builder ─────────────────────────────────────────────────────────────

def _build_prompt(prompt: str, context: str = "") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = (
        f"[ORACLE → Claude Code] {ts}\n"
        f"Project: ORACLE.AI (G:\\My Drive\\HawkesNest LLC\\ORACLE.AI)\n"
    )
    if context:
        header += f"Context: {context}\n"
    header += "---\n"
    return header + prompt


# ── Status ─────────────────────────────────────────────────────────────────────

def status() -> str:
    exe = _claude_exe()
    win = find_claude_window()
    lines = [
        "",
        "  [CLAUDE CODE BRIDGE STATUS]",
        f"  claude CLI    : {'YES — ' + exe if exe else 'NO'}",
        f"  Active window : {win['title'] if win else 'not found'}",
        f"  SAFE_SLEEP    : {'YES (typing blocked)' if _is_safe_sleep() else 'no'}",
        f"  Repo root     : {ROOT}",
        "",
    ]
    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="ORACLE → Claude Code bridge")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--ask", type=str, metavar="PROMPT")
    parser.add_argument("--type", type=str, metavar="PROMPT", dest="type_msg")
    parser.add_argument("--open", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    if args.status:
        print(status())

    elif args.ask:
        print(f"Asking Claude Code: {args.ask!r}")
        ok, reply = ask_claude(args.ask)
        print(f"\n{'OK' if ok else 'FAIL'}: {reply}")

    elif args.type_msg:
        print(f"Typing into Claude Code window: {args.type_msg!r}")
        ok, detail = type_into_claude(args.type_msg)
        print(f"{'OK' if ok else 'FAIL'}: {detail}")

    elif args.open:
        ok, detail = open_claude_session(
            "ORACLE is handing off. What is the status of the MYTHIC BUILD PASS?"
        )
        print(f"{'OK' if ok else 'FAIL'}: {detail}")

    elif args.smoke:
        print("Smoke test:")
        print(f"  claude available  : {claude_available()}")
        print(f"  is_code_task test : {is_code_task('implement voice hooks')}")
        print(f"  find_claude_window: {find_claude_window()}")
        print(status())
    else:
        parser.print_help()
