"""
core/oracle_loop.py — ORACLE Autonomous Build Loop

ORACLE ↔ Claude Code continuous loop:
  1. ORACLE runs a governance cycle to pick the next task
  2. Writes the task to Messages/oracle_to_claude.md
  3. Claude Code (this session) reads it, implements, writes response
  4. ORACLE reads the response, speaks it, picks next task
  5. Repeat

Start:  loop_start()
Stop:   loop_stop()
Status: loop_status()

The loop runs in a daemon background thread so the REPL stays responsive.
Noah can type at any time — 'loop off' or 'stop loop' halts it.
"""

from __future__ import annotations

import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

# ── Paths ──────────────────────────────────────────────────────────────────────
import sys
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "core"))

from oracle_claude_channel import (
    ORACLE_TO_CLAUDE, CLAUDE_TO_ORACLE, CHANNEL_LOG,
    send_to_claude, clear_channel,
)

# ── Config ─────────────────────────────────────────────────────────────────────
POLL_INTERVAL      = 3.0    # seconds between inbox checks
CYCLE_INTERVAL     = 45.0   # seconds between autonomous cycles when idle
MAX_CONSECUTIVE    = 50     # hard cap — stop loop after this many tasks
RESPONSE_TIMEOUT   = 300.0  # seconds to wait for Claude before cycling again

# ── State ──────────────────────────────────────────────────────────────────────
_loop_thread:   Optional[threading.Thread] = None
_loop_running   = threading.Event()
_loop_lock      = threading.Lock()

_stats = {
    "tasks_sent":     0,
    "responses_read": 0,
    "cycles_run":     0,
    "started_at":     None,
    "last_task":      "",
    "last_response":  "",
    "last_error":     "",
}

# Callback set by oracle.py so the loop can print to the REPL
_print_cb: Optional[Callable[[str], None]] = None
_speak_cb: Optional[Callable[[str], None]] = None


def set_callbacks(print_fn: Callable, speak_fn: Callable):
    global _print_cb, _speak_cb
    _print_cb = print_fn
    _speak_cb = speak_fn


def _out(msg: str):
    if _print_cb:
        _print_cb(msg)
    else:
        print(msg, flush=True)


def _speak(msg: str):
    if _speak_cb:
        try:
            _speak_cb(msg)
        except Exception:
            pass


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M UTC")


# ── Task generation ────────────────────────────────────────────────────────────

def _next_task_from_response(response: str) -> str:
    """
    Parse Claude's response to find the next task.
    Claude often ends with 'Next:' or 'What next?' — extract that.
    Otherwise return empty string to let the cycle engine decide.
    """
    lines = response.strip().splitlines()
    for line in reversed(lines):
        l = line.strip()
        if l.lower().startswith(("next:", "next step:", "next task:")):
            return l.split(":", 1)[-1].strip()
        if l.lower().startswith("what") and "?" in l:
            return ""   # question back to Noah — let cycle decide
    return ""


def _governance_task() -> str:
    """
    Ask oracle_runtime for the next highest-priority task.
    Returns a plain-English task string for Claude Code.
    """
    try:
        from oracle_runtime import run_cycle, MODE_DAEMON_SAFE
        result = run_cycle(mode=MODE_DAEMON_SAFE)
        step = result.next_recommended_step or ""
        priority = result.selected_priority or "maintenance"
        action = result.action_taken or ""

        if not step and not action:
            return ""

        task = step or action
        return f"[ORACLE GOVERNANCE — {priority}]\n\n{task}"
    except Exception as e:
        _stats["last_error"] = str(e)
        return ""


def _project_state_task() -> str:
    """Fallback: read project state and propose the next step."""
    try:
        from project_state import load_state
        ps = load_state("ORACLE.AI")
        if ps and ps.next_recommended_step:
            return (
                f"[ORACLE PROJECT STATE — {ps.current_phase}]\n\n"
                f"{ps.next_recommended_step}"
            )
    except Exception:
        pass
    return ""


# ── Core loop ──────────────────────────────────────────────────────────────────

def _loop_body():
    global _stats
    _stats["started_at"] = datetime.now(timezone.utc).isoformat()
    last_cycle_time = 0.0
    last_sent_time  = 0.0
    waiting_for_response = False

    _out(f"\n  \033[92m[LOOP START]\033[0m ORACLE autonomous loop active. "
         f"Cycling every {int(CYCLE_INTERVAL)}s. Say 'loop off' to stop.\n")
    _speak("Autonomous loop active.")

    while _loop_running.is_set() and _stats["tasks_sent"] < MAX_CONSECUTIVE:
        try:
            now = time.time()

            # ── 1. Check for Claude's response ────────────────────────────────
            if CLAUDE_TO_ORACLE.exists():
                try:
                    response = CLAUDE_TO_ORACLE.read_text(encoding="utf-8").strip()
                    if response:
                        CLAUDE_TO_ORACLE.unlink()
                        _stats["responses_read"] += 1
                        _stats["last_response"] = response[:120]
                        waiting_for_response = False

                        # Display in REPL
                        _out(f"\n  \033[92m[CLAUDE → ORACLE  {_stamp()}]\033[0m")
                        for line in response.splitlines()[:20]:
                            _out(f"  {line}")
                        _out("")
                        _speak("Claude responded.")

                        # Log it
                        try:
                            with open(CHANNEL_LOG, "a", encoding="utf-8") as f:
                                f.write(f"\n## [{_stamp()}] Claude → ORACLE\n\n{response[:600]}\n")
                        except Exception:
                            pass

                        # Determine next task from response
                        follow_up = _next_task_from_response(response)
                        if follow_up:
                            time.sleep(1.0)
                            _send_task(follow_up)
                            last_sent_time = time.time()
                            last_cycle_time = time.time()
                        else:
                            # No explicit follow-up — let cycle engine decide shortly
                            last_cycle_time = time.time() - CYCLE_INTERVAL + 10

                except Exception as e:
                    _stats["last_error"] = str(e)

            # ── 2. Response timeout — don't wait forever ──────────────────────
            elif waiting_for_response and (now - last_sent_time) > RESPONSE_TIMEOUT:
                _out(f"\n  \033[93m[LOOP]\033[0m No response in {int(RESPONSE_TIMEOUT)}s — cycling.\n")
                waiting_for_response = False
                last_cycle_time = 0   # force cycle

            # ── 3. Periodic governance cycle ──────────────────────────────────
            elif not waiting_for_response and (now - last_cycle_time) >= CYCLE_INTERVAL:
                _stats["cycles_run"] += 1
                last_cycle_time = now

                task = _governance_task() or _project_state_task()
                if task:
                    _send_task(task)
                    last_sent_time = now
                    waiting_for_response = True
                else:
                    _out(f"  \033[90m[LOOP] Cycle {_stats['cycles_run']} — no task generated. Waiting.\033[0m")

        except Exception as e:
            _stats["last_error"] = traceback.format_exc()[:200]

        time.sleep(POLL_INTERVAL)

    if _stats["tasks_sent"] >= MAX_CONSECUTIVE:
        _out(f"\n  \033[93m[LOOP HALT]\033[0m Reached {MAX_CONSECUTIVE} task limit. "
             f"Say 'loop on' to restart.\n")
    else:
        _out(f"\n  \033[90m[LOOP STOPPED]\033[0m\n")

    _loop_running.clear()
    _speak("Loop stopped.")


def _send_task(task: str):
    _stats["tasks_sent"] += 1
    _stats["last_task"] = task[:120]

    # Clear stale response first
    if CLAUDE_TO_ORACLE.exists():
        CLAUDE_TO_ORACLE.unlink()

    ok = send_to_claude(task)
    if ok:
        _out(f"\n  \033[93m[ORACLE → CLAUDE  {_stamp()}]\033[0m  task #{_stats['tasks_sent']}")
        preview = task.splitlines()[0][:80] if task else ""
        _out(f"  {preview}\n")

        try:
            with open(CHANNEL_LOG, "a", encoding="utf-8") as f:
                f.write(f"\n## [{_stamp()}] ORACLE → Claude  (task #{_stats['tasks_sent']})\n\n{task[:400]}\n")
        except Exception:
            pass
    else:
        _out(f"  \033[91m[LOOP ERROR]\033[0m Failed to write task to channel.\n")


# ── Public API ─────────────────────────────────────────────────────────────────

def loop_start():
    global _loop_thread, _stats
    with _loop_lock:
        if _loop_running.is_set():
            _out("  [LOOP] Already running.\n")
            return
        # Reset stats
        _stats = {
            "tasks_sent": 0, "responses_read": 0, "cycles_run": 0,
            "started_at": None, "last_task": "", "last_response": "", "last_error": "",
        }
        _loop_running.set()
        _loop_thread = threading.Thread(target=_loop_body, daemon=True, name="oracle-loop")
        _loop_thread.start()


def loop_stop():
    _loop_running.clear()
    _out("  [LOOP] Stopping after current poll…\n")


def loop_status() -> str:
    running = _loop_running.is_set()
    lines = [
        f"  Loop      : {'RUNNING' if running else 'STOPPED'}",
        f"  Tasks sent: {_stats['tasks_sent']}",
        f"  Responses : {_stats['responses_read']}",
        f"  Cycles    : {_stats['cycles_run']}",
        f"  Started   : {_stats['started_at'] or 'never'}",
    ]
    if _stats["last_task"]:
        lines.append(f"  Last task : {_stats['last_task'][:80]}")
    if _stats["last_error"]:
        lines.append(f"  Last error: {_stats['last_error'][:80]}")
    return "\n".join(lines)


def is_running() -> bool:
    return _loop_running.is_set()
