"""
core/claude_code_bridge.py — ORACLE → Claude Code Bridge

ORACLE routes code questions, build tasks, and implementation requests to
Claude Code (the `claude` CLI) rather than attempting them with the local
model. Claude Code has full codebase context; the local model does not.

Two modes:
  ask(prompt)    — non-interactive, returns answer as a string (claude -p)
  open(prompt)   — launches an interactive Claude Code session in a new terminal

Governed: ORACLE may ask freely; opening an interactive session shows a
confirmation chip unless `force=True` is passed.

Usage (from oracle_tui.py or oracle.py):
    from claude_code_bridge import ask_claude, open_claude_session

    answer = ask_claude("Does voice.py already have speak_prompt?")
    open_claude_session("Implement Step 10 of the MYTHIC BUILD PASS")
"""

import subprocess
import sys
import shutil
from pathlib import Path
from datetime import datetime, timezone

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

# ── Claude Code detection ──────────────────────────────────────────────────────

def _claude_exe() -> str | None:
    """Return the path to the `claude` CLI, or None if not found."""
    return shutil.which("claude")


def claude_available() -> bool:
    return _claude_exe() is not None


# ── Non-interactive ask ────────────────────────────────────────────────────────

def ask_claude(
    prompt: str,
    context: str = "",
    timeout: int = 120,
    cwd: str | None = None,
) -> tuple[bool, str]:
    """
    Run `claude -p "<prompt>"` and return (success, response_text).

    Adds ORACLE context header so Claude Code knows who is asking and why.
    Never opens a window — answer comes back as text inline.

    timeout: seconds to wait for a response (default 120)
    cwd: working directory for claude (defaults to ORACLE repo root)
    """
    exe = _claude_exe()
    if not exe:
        return False, (
            "Claude Code CLI (`claude`) not found on PATH. "
            "Install it with: npm install -g @anthropic-ai/claude-code"
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
            answer = result.stdout.strip()
            return True, answer or "(no output)"
        else:
            err = (result.stderr or result.stdout or "unknown error").strip()
            return False, f"Claude Code returned exit {result.returncode}: {err}"
    except subprocess.TimeoutExpired:
        return False, f"Claude Code did not respond within {timeout}s."
    except Exception as e:
        return False, f"Claude Code bridge error: {e}"


# ── Interactive session launcher ───────────────────────────────────────────────

def open_claude_session(
    prompt: str = "",
    context: str = "",
    cwd: str | None = None,
) -> tuple[bool, str]:
    """
    Open an interactive `claude` session in a new terminal window.
    Passes the prompt as the initial message via --resume or stdin pipe.

    Returns (success, detail_message).
    """
    exe = _claude_exe()
    if not exe:
        return False, "Claude Code CLI not found on PATH."

    work_dir = cwd or str(ROOT)
    initial = _build_prompt(prompt, context) if prompt else ""

    try:
        if sys.platform == "win32":
            # Windows: open a new PowerShell window
            if initial:
                # Write prompt to a temp file so we can pass it cleanly
                tmp = ROOT / "Memory" / "_claude_session_prompt.txt"
                tmp.parent.mkdir(parents=True, exist_ok=True)
                tmp.write_text(initial, encoding="utf-8")
                cmd = (
                    f'Start-Process powershell -ArgumentList '
                    f'"-NoExit", "-Command", '
                    f'"cd \'{work_dir}\'; '
                    f'Get-Content \'{tmp}\' | {exe}"'
                )
            else:
                cmd = (
                    f'Start-Process powershell -ArgumentList '
                    f'"-NoExit", "-Command", "cd \'{work_dir}\'; {exe}"'
                )
            subprocess.Popen(
                ["powershell", "-Command", cmd],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            # macOS/Linux fallback
            subprocess.Popen(
                ["bash", "-c", f"cd '{work_dir}' && {exe}"],
                start_new_session=True,
            )
        return True, "Claude Code session opened in new terminal."
    except Exception as e:
        return False, f"Could not open Claude Code session: {e}"


# ── Code-task classifier ───────────────────────────────────────────────────────

_CODE_KEYWORDS = {
    "implement", "build", "create", "write", "add", "fix", "refactor",
    "edit", "update", "change", "modify", "delete", "remove", "rename",
    "core/", ".py", "file", "function", "class", "module", "import",
    "step ", "mythic", "voice_hooks", "voice.py", "oracle.py", "tui",
    "does ", "where is", "what file", "how does", "explain the code",
    "check if", "look at", "read the", "find the",
}

def is_code_task(text: str) -> bool:
    """
    Heuristic: should this query go to Claude Code instead of the local model?
    Returns True if the message looks like a code/build question.
    """
    lower = text.lower()
    return any(kw in lower for kw in _CODE_KEYWORDS)


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


# ── Status ────────────────────────────────────────────────────────────────────

def status() -> str:
    exe = _claude_exe()
    lines = [
        "",
        "  [CLAUDE CODE BRIDGE STATUS]",
        f"  claude CLI found : {'YES — ' + exe if exe else 'NO'}",
        f"  Repo root        : {ROOT}",
        "",
    ]
    return "\n".join(lines)


# ── CLI smoke test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ORACLE → Claude Code bridge")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--ask", type=str, metavar="PROMPT")
    parser.add_argument("--open", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    if args.status:
        print(status())

    elif args.ask:
        print(f"Asking Claude Code: {args.ask!r}")
        ok, reply = ask_claude(args.ask)
        print(f"\n{'OK' if ok else 'FAIL'}: {reply}")

    elif args.open:
        ok, detail = open_claude_session("Hello — ORACLE is opening a session. What's the status of the MYTHIC BUILD PASS?")
        print(f"{'OK' if ok else 'FAIL'}: {detail}")

    elif args.smoke:
        print("Smoke test:")
        print(f"  claude available: {claude_available()}")
        print(f"  is_code_task('implement voice hooks'): {is_code_task('implement voice hooks')}")
        print(f"  is_code_task('hello how are you'): {is_code_task('hello how are you')}")
        ok, r = ask_claude("In one sentence, confirm you received this test ping from ORACLE.")
        print(f"  ask_claude smoke: {'PASS' if ok else 'FAIL'} — {r[:120]}")
    else:
        parser.print_help()
