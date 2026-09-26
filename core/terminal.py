"""
core/terminal.py — ORACLE Persistent Terminal Session

ORACLE gets her own persistent PowerShell process she can type commands into.
State carries between commands: cd, env vars, activated venvs, all of it.

Usage:
    from terminal import get_terminal
    term = get_terminal()
    output = term.run("cd C:\\Users\\noahh && dir")
    output = term.run("python --version")

The session stays alive for the duration of the ORACLE process.
Call term.close() on shutdown, or it cleans up automatically on exit.
"""

import subprocess
import threading
import queue
import time
import os
import sys
import atexit
from pathlib import Path

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent


# Sentinel that marks end-of-output in the pipe
_END_MARKER = "__ORACLE_CMD_DONE_9f3a__"

_instance = None
_lock = threading.Lock()


def _creationflags() -> int:
    if os.name != "nt":
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _record_spawn(pid: int, command: str, visible_window: bool) -> None:
    try:
        from terminal_census import record_spawn

        record_spawn(
            kind="persistent_terminal",
            pid=pid,
            command=command,
            cwd=str(ROOT),
            visible_window=visible_window,
            cleanup_policy="close on ORACLE process exit",
        )
    except Exception:
        pass


def _record_exit(pid: int, reason: str) -> None:
    try:
        from terminal_census import record_exit

        record_exit(kind="persistent_terminal", pid=pid, reason=reason)
    except Exception:
        pass


def get_terminal() -> "PersistentTerminal":
    """Return the shared terminal session, creating it if needed."""
    global _instance
    with _lock:
        if _instance is None or not _instance.alive:
            _instance = PersistentTerminal()
    return _instance


class PersistentTerminal:
    """
    A persistent PowerShell subprocess ORACLE can send commands to.
    Each run() call sends a command and reads all output until done.
    """

    def __init__(self):
        env = os.environ.copy()
        env["ORACLE_TERMINAL_OWNER"] = "terminal_run"
        env["ORACLE_TERMINAL_VISIBLE"] = "false"
        command = "powershell -NoLogo -NoExit -ExecutionPolicy Bypass -Command -"
        self._proc = subprocess.Popen(
            ["powershell", "-NoLogo", "-NoExit", "-ExecutionPolicy", "Bypass",
             "-Command", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,   # merge stderr into stdout
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(ROOT),
            env=env,
            creationflags=_creationflags(),
        )
        _record_spawn(self._proc.pid, command, visible_window=False)
        self._out_q: queue.Queue = queue.Queue()
        self._reader = threading.Thread(
            target=self._read_stdout, daemon=True, name="oracle-terminal-reader"
        )
        self._reader.start()
        self.alive = True
        # Drain any startup banner
        self._drain_startup()

    def _read_stdout(self):
        """Background thread: push every line from stdout into the queue."""
        try:
            for line in self._proc.stdout:
                self._out_q.put(line)
        except Exception:
            pass
        finally:
            self._out_q.put(None)   # EOF sentinel

    def _drain_startup(self):
        """Consume PowerShell's startup output."""
        self._send_raw(f'Write-Host "{_END_MARKER}"')
        self._collect(timeout=5.0)

    def _send_raw(self, cmd: str):
        try:
            self._proc.stdin.write(cmd + "\n")
            self._proc.stdin.flush()
        except Exception:
            self.alive = False

    def _collect(self, timeout: float = 30.0) -> str:
        """Read lines from the queue until the end marker appears or timeout."""
        lines = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                line = self._out_q.get(timeout=0.2)
            except queue.Empty:
                continue
            if line is None:
                self.alive = False
                break
            stripped = line.rstrip()
            if _END_MARKER in stripped:
                break
            lines.append(stripped)
        return "\n".join(lines).strip()

    def run(self, command: str, timeout: float = 60.0) -> str:
        """
        Run a command in the persistent shell. Returns combined stdout+stderr.
        State (cwd, env vars, activated venvs) persists between calls.
        """
        if not self.alive:
            return "Terminal session is closed. Restart ORACLE to get a new one."

        # Wrap command so we can detect when it finishes
        # Use try/finally so the marker always prints even if command errors
        wrapped = (
            f'try {{ {command} }} catch {{ Write-Host "ERROR: $_" }}; '
            f'Write-Host "{_END_MARKER}"'
        )
        self._send_raw(wrapped)
        output = self._collect(timeout=timeout)
        return output or "(command completed, no output)"

    def get_cwd(self) -> str:
        """Return the terminal's current working directory."""
        return self.run("(Get-Location).Path", timeout=5.0)

    def close(self):
        """Cleanly shut down the terminal process."""
        pid = getattr(self._proc, "pid", 0) if self._proc else 0
        try:
            self._proc.stdin.write("exit\n")
            self._proc.stdin.flush()
            self._proc.wait(timeout=3)
        except Exception:
            pass
        finally:
            self.alive = False
            try:
                self._proc.kill()
            except Exception:
                pass
            if pid:
                _record_exit(pid, "close")


def close_terminal():
    global _instance
    if _instance is not None and _instance.alive:
        _instance.close()


atexit.register(close_terminal)
