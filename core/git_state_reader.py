"""File-only Git state reader for ORACLE hot paths.

This module intentionally never invokes git.exe. ORACLE's UI and chat routes
poll runtime state frequently; on Windows a broken Git process can raise a
modal application-error dialog and wedge the server. File reads keep branch and
HEAD visibility without shelling out.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def _resolve_git_dir(root: Path) -> Path | None:
    dot_git = root / ".git"
    try:
        if dot_git.is_dir():
            return dot_git
        if dot_git.is_file():
            text = dot_git.read_text(encoding="utf-8", errors="replace").strip()
            if text.lower().startswith("gitdir:"):
                target = text.split(":", 1)[1].strip()
                path = Path(target)
                if not path.is_absolute():
                    path = (root / path).resolve()
                return path
    except Exception:
        return None
    return None


def _read_packed_ref(git_dir: Path, ref_name: str) -> str | None:
    packed = git_dir / "packed-refs"
    try:
        if not packed.exists():
            return None
        for line in packed.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line or line.startswith("#") or line.startswith("^") or " " not in line:
                continue
            sha, name = line.split(" ", 1)
            if name.strip() == ref_name:
                return sha.strip()
    except Exception:
        return None
    return None


def _read_head(git_dir: Path) -> dict[str, Any]:
    try:
        head_text = (git_dir / "HEAD").read_text(encoding="utf-8", errors="replace").strip()
    except Exception as exc:
        return {
            "branch": "UNKNOWN",
            "commit": "UNKNOWN",
            "head_sha": "UNKNOWN",
            "ref": None,
            "error": f"{type(exc).__name__}: {exc}",
        }

    if head_text.startswith("ref:"):
        ref_name = head_text.split(":", 1)[1].strip()
        branch = ref_name[len("refs/heads/"):] if ref_name.startswith("refs/heads/") else ref_name
        sha: str | None = None
        try:
            ref_path = git_dir / ref_name
            if ref_path.exists():
                sha = ref_path.read_text(encoding="utf-8", errors="replace").strip()
            else:
                sha = _read_packed_ref(git_dir, ref_name)
        except Exception:
            sha = None
        return {
            "branch": branch or "UNKNOWN",
            "commit": sha[:7] if sha else "UNKNOWN",
            "head_sha": sha or "UNKNOWN",
            "ref": ref_name,
            "error": None if sha else "ref_not_found",
        }

    sha = head_text.strip()
    return {
        "branch": "(detached)",
        "commit": sha[:7] if sha else "UNKNOWN",
        "head_sha": sha or "UNKNOWN",
        "ref": None,
        "error": None if sha else "empty_head",
    }


def _read_recent_from_reflog(git_dir: Path, limit: int) -> list[str]:
    log_path = git_dir / "logs" / "HEAD"
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    recent: list[str] = []
    for line in reversed(lines[-max(limit * 3, limit):]):
        parts = line.split("\t", 1)
        prefix = parts[0].split()
        if len(prefix) < 2:
            continue
        sha = prefix[1]
        message = parts[1].strip() if len(parts) == 2 else ""
        if not sha or set(sha) == {"0"}:
            continue
        recent.append((sha[:7] + (" " + message if message else "")).strip())
        if len(recent) >= limit:
            break
    return recent


def read_git_snapshot(root: str | Path, *, recent_limit: int = 5) -> dict[str, Any]:
    """Return Git identity without running git.

    Dirty/changed-file status is deliberately unknown here. Computing it
    correctly requires Git index semantics, and shelling out is what caused the
    runtime loop. Build-lane tools can still run Git explicitly when approved.
    """
    root_path = Path(root)
    git_dir = _resolve_git_dir(root_path)
    if git_dir is None:
        return {
            "available": False,
            "source": "git_files_no_subprocess",
            "branch": "UNKNOWN",
            "commit": "UNKNOWN",
            "head_sha": "UNKNOWN",
            "working_tree": "unknown",
            "changed_files": [],
            "changed_file_count": None,
            "dirty": "UNKNOWN",
            "status_short": "UNKNOWN",
            "recent_commits": [],
            "error": ".git not found",
            "subprocess_used": False,
        }

    head = _read_head(git_dir)
    return {
        "available": head.get("commit") != "UNKNOWN",
        "source": "git_files_no_subprocess",
        "git_dir": str(git_dir),
        "branch": head.get("branch") or "UNKNOWN",
        "commit": head.get("commit") or "UNKNOWN",
        "head_sha": head.get("head_sha") or "UNKNOWN",
        "ref": head.get("ref"),
        "working_tree": "unknown",
        "changed_files": [],
        "changed_file_count": None,
        "dirty": "UNKNOWN",
        "status_short": "UNKNOWN",
        "recent_commits": _read_recent_from_reflog(git_dir, recent_limit),
        "error": head.get("error"),
        "subprocess_used": False,
    }
