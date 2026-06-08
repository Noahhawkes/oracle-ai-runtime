"""
core/oracle_claude_channel.py — ORACLE ↔ Claude Code bidirectional channel

How it works:
  ORACLE writes a task to Messages/oracle_to_claude.md
  Claude Code (this session) reads it, writes a response to Messages/claude_to_oracle.md
  ORACLE polls for the response, reads it, and acts on it

This is the file-based bridge that enables a continuous work loop between
ORACLE (local operator) and Claude Code (implementation engine).

ORACLE side:  send_to_claude(task)  →  wait_for_response()  →  act()
Claude side:  read Messages/oracle_to_claude.md  →  write Messages/claude_to_oracle.md
"""

import os
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
MESSAGES_DIR = ROOT / "Messages"
ORACLE_TO_CLAUDE = MESSAGES_DIR / "oracle_to_claude.md"
CLAUDE_TO_ORACLE = MESSAGES_DIR / "claude_to_oracle.md"
CHANNEL_LOG     = MESSAGES_DIR / "channel_log.md"

MESSAGES_DIR.mkdir(exist_ok=True)

_POLL_INTERVAL = 2.0   # seconds between response checks
_TIMEOUT       = 300   # 5 minutes max wait


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def send_to_claude(task: str, context: str = "") -> bool:
    """
    Write a task to the outbox for Claude Code to pick up.
    Returns True if written successfully.
    """
    try:
        # Clear any stale response first
        if CLAUDE_TO_ORACLE.exists():
            CLAUDE_TO_ORACLE.unlink()

        content = f"# Task from ORACLE — {_stamp()}\n\n{task}\n"
        if context:
            content += f"\n## Context\n\n{context}\n"
        content += "\n---\n_ORACLE is waiting for your response in `Messages/claude_to_oracle.md`_\n"

        ORACLE_TO_CLAUDE.write_text(content, encoding="utf-8")

        # Append to channel log
        try:
            with open(CHANNEL_LOG, "a", encoding="utf-8") as f:
                f.write(f"\n## [{_stamp()}] ORACLE → Claude\n\n{task[:200]}\n")
        except Exception:
            pass

        return True
    except Exception as e:
        return False


def wait_for_response(timeout: float = _TIMEOUT, poll: float = _POLL_INTERVAL) -> str | None:
    """
    Poll for Claude's response file. Returns the response text or None on timeout.
    Progress dots printed every 10 seconds so the terminal shows life.
    """
    deadline = time.time() + timeout
    last_dot = time.time()

    while time.time() < deadline:
        if CLAUDE_TO_ORACLE.exists():
            try:
                response = CLAUDE_TO_ORACLE.read_text(encoding="utf-8").strip()
                if response:
                    # Log it
                    try:
                        with open(CHANNEL_LOG, "a", encoding="utf-8") as f:
                            f.write(f"\n## [{_stamp()}] Claude → ORACLE\n\n{response[:400]}\n")
                    except Exception:
                        pass
                    return response
            except Exception:
                pass

        if time.time() - last_dot >= 10:
            print("  [channel] Waiting for Claude response…", flush=True)
            last_dot = time.time()

        time.sleep(poll)

    return None


def ask_claude(task: str, context: str = "", timeout: float = _TIMEOUT) -> str:
    """
    Full round-trip: write task → wait → return response.
    Returns response text or an error string.
    """
    if not send_to_claude(task, context=context):
        return "[CHANNEL ERROR] Could not write task to Messages/oracle_to_claude.md"

    response = wait_for_response(timeout=timeout)
    if response is None:
        return f"[CHANNEL TIMEOUT] No response in {int(timeout)}s. Check Messages/oracle_to_claude.md."

    return response


def pending_task() -> str | None:
    """
    Called by Claude Code to check if ORACLE has a pending task.
    Returns the task text or None.
    """
    if ORACLE_TO_CLAUDE.exists():
        try:
            return ORACLE_TO_CLAUDE.read_text(encoding="utf-8").strip() or None
        except Exception:
            return None
    return None


def reply_from_claude(response: str) -> bool:
    """
    Called by Claude Code (or by me in this session) to write a response back to ORACLE.
    """
    try:
        content = f"# Claude Response — {_stamp()}\n\n{response}\n"
        CLAUDE_TO_ORACLE.write_text(content, encoding="utf-8")
        return True
    except Exception:
        return False


def clear_channel():
    """Reset both message files."""
    for f in (ORACLE_TO_CLAUDE, CLAUDE_TO_ORACLE):
        try:
            if f.exists():
                f.unlink()
        except Exception:
            pass
