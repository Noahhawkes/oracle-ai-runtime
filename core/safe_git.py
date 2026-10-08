"""
core/safe_git.py — the only way this runtime should ever invoke git.

On 2026-07-19 ORACLE went down and Noah's screen filled with terminal windows
that flashed open and closed. Two faults combined:

1. Every git call in the runtime spawned a Windows console. Ten modules shell
   out to git, several on timers, and none passed CREATE_NO_WINDOW. Each console
   consumes interactive desktop heap, which is a fixed 20 MB allocation and has
   nothing to do with available RAM. Enough consoles and the heap runs dry.

2. Once the heap was exhausted, git.exe could no longer initialize and died with
   0xc0000142 behind a modal dialog. oracle_server._run_git had no timeout, so
   the server blocked forever on a child that would never exit, while still
   holding port 7781. Every endpoint timed out. The UI polled that endpoint
   every 30 seconds, so it re-armed itself continuously.

The fix is not "add a timeout to the one that broke." It is to make it
impossible for any git call in this runtime to open a window or hang.

Rules enforced here:
  - CREATE_NO_WINDOW on Windows, always. No git call may allocate a console.
  - A timeout, always. A hung git can never block a request thread.
  - Failure returns UNKNOWN, never a confident wrong value. A read that did not
    happen is not evidence of absence.

Prefer read_head() over run() where possible. Reading .git directly cannot hang,
cannot spawn a console, and cannot fail to initialize.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any, Optional

UNKNOWN = "UNKNOWN"
DEFAULT_TIMEOUT = 5.0


def _no_window_kwargs() -> dict[str, Any]:
    """Windows: never allocate a console for a git child."""
    import os

    if os.name != "nt":
        return {}
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return {"creationflags": flags} if flags else {}


def run(args: list[str], *, cwd: Optional[Path] = None,
        timeout: float = DEFAULT_TIMEOUT) -> str:
    """Run a git command safely. Returns stripped stdout, or UNKNOWN.

    Never raises. Never opens a window. Never blocks past `timeout`."""
    kwargs: dict[str, Any] = {
        "text": True,
        "stderr": subprocess.DEVNULL,
        "timeout": timeout,
        **_no_window_kwargs(),
    }
    if cwd is not None:
        kwargs["cwd"] = str(cwd)
    try:
        return subprocess.check_output(["git", *args], **kwargs).strip()
    except Exception:
        return UNKNOWN


def read_head(repo_root: Path) -> tuple[str, str]:
    """Branch and short commit, read straight from .git. No subprocess.

    This is the preferred path for status displays and polls. Plain file reads
    cannot hang, cannot spawn a console, and cannot fail to initialize.
    Returns (UNKNOWN, UNKNOWN) if anything is unreadable."""
    branch, commit = UNKNOWN, UNKNOWN
    try:
        git_dir = Path(repo_root) / ".git"
        head_text = (git_dir / "HEAD").read_text(encoding="utf-8").strip()

        if not head_text.startswith("ref:"):
            # Detached HEAD holds the sha directly.
            return "(detached)", head_text[:7]

        ref = head_text.split(" ", 1)[1].strip()
        # Strip only the refs/heads/ prefix; branch names contain slashes.
        branch = ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref

        ref_path = git_dir / ref
        if ref_path.exists():
            commit = ref_path.read_text(encoding="utf-8").strip()[:7]
        else:
            packed = git_dir / "packed-refs"
            if packed.exists():
                for line in packed.read_text(encoding="utf-8", errors="replace").splitlines():
                    if line.startswith("#") or " " not in line:
                        continue
                    sha, name = line.split(" ", 1)
                    if name.strip() == ref:
                        commit = sha.strip()[:7]
                        break
    except Exception:
        pass
    return branch, commit


class CachedGitValue:
    """A git read that refreshes at most once per ttl seconds.

    For values that genuinely need git (dirty status, log) and are read by
    pollers. Degrades to UNKNOWN rather than hammering a failing git."""

    def __init__(self, args: list[str], *, cwd: Optional[Path] = None,
                 ttl: float = 120.0, timeout: float = DEFAULT_TIMEOUT):
        self._args = list(args)
        self._cwd = cwd
        self._ttl = ttl
        self._timeout = timeout
        self._at = 0.0
        self._value: str = UNKNOWN

    def get(self) -> str:
        now = time.time()
        if now - self._at > self._ttl:
            self._value = run(self._args, cwd=self._cwd, timeout=self._timeout)
            self._at = now
        return self._value

    @property
    def age_seconds(self) -> float:
        return time.time() - self._at if self._at else float("inf")
