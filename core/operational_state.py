"""
operational_state.py — ORACLE's live, deterministically-reconciled current state.

This is the world-model (the missing organ). A single authoritative object,
rebuilt on demand from:
  * VERIFIED live sources: git, filesystem, runtime socket, Ollama, vision,
    pending approvals. These are objective and re-derived every call.
  * DECLARED sources: the project narrative (project_states.json). These are
    explicitly labeled and staleness-checked so they can NEVER masquerade as
    verified fact.

No LLM. No HTTP self-call. The only network touches are a local TCP probe of the
runtime port and a local Ollama status read. Re-deriving on every call IS the
stale-state prevention.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
PROJECT_STATES = ROOT / "Memory" / "project_states.json"
# Declared narrative older than this (hours) is flagged stale.
DECLARED_STALE_HOURS = float(os.environ.get("ORACLE_DECLARED_STALE_HOURS", "12"))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _git(args: list[str]) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=ROOT, text=True,
            stderr=subprocess.DEVNULL, timeout=8,
        ).strip()
    except Exception:
        return ""


def _git_state() -> dict[str, Any]:
    status = _git(["status", "--porcelain"])
    # Parse by splitting off the status field rather than slicing a fixed width:
    # the helper strips the whole output, which can eat the first line's leading
    # space and shift a fixed-index slice. Paths here are space-free.
    changed = []
    for line in status.splitlines():
        if not line.strip() or ".claude/worktrees" in line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            changed.append(parts[1])
    recent = _git(["log", "--oneline", "-5"]).splitlines()
    return {
        "branch": _git(["rev-parse", "--abbrev-ref", "HEAD"]) or "UNKNOWN",
        "commit": _git(["rev-parse", "--short", "HEAD"]) or "UNKNOWN",
        "working_tree": "clean" if not changed else "modified",
        "changed_files": changed[:15],
        "recent_commits": recent,
    }


def _port_open(port: int = 7777, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except Exception:
        return False


def _ollama_loaded() -> list[str]:
    try:
        with urllib.request.urlopen("http://localhost:11434/api/ps", timeout=2) as r:
            data = json.load(r)
        return [m.get("name") for m in data.get("models", []) if m.get("name")]
    except Exception:
        return []


def _vision_state() -> dict[str, Any]:
    try:
        from oracle_sight import sight_available
        return sight_available()
    except Exception as exc:
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}


def _pending() -> dict[str, Any]:
    try:
        from approval_center import list_pending
        return {"count": len(list_pending()), "available": True}
    except Exception as exc:
        return {"count": 0, "available": False, "error": f"{type(exc).__name__}: {exc}"}


def _declared() -> dict[str, Any]:
    try:
        raw = json.loads(PROJECT_STATES.read_text(encoding="utf-8"))
        node = raw.get("ORACLE.AI", raw) if isinstance(raw, dict) else {}
        updated = str(node.get("updated_at", "") or "")
        age_hours: float | None = None
        stale = True
        try:
            ts = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            age_hours = round((_utc_now() - ts).total_seconds() / 3600, 1)
            stale = age_hours > DECLARED_STALE_HOURS
        except Exception:
            pass
        return {
            "source": "Memory/project_states.json",
            "updated_at": updated,
            "age_hours": age_hours,
            "stale": stale,
            "current_goal": str(node.get("current_goal", "") or ""),
            "current_phase": str(node.get("current_phase", "") or ""),
            "last_completed_step": str(node.get("last_completed_step", "") or ""),
            "next_recommended_step": str(node.get("next_recommended_step", "") or ""),
        }
    except Exception as exc:
        return {
            "source": "Memory/project_states.json",
            "error": f"{type(exc).__name__}: {exc}",
            "stale": True,
        }


def build_operational_state(*, mode_provider: Callable[[], dict] | None = None) -> dict[str, Any]:
    """Reconcile ORACLE's current operational state from live + declared sources."""
    git = _git_state()
    runtime: dict[str, Any] = {
        "localhost_7777": "online" if _port_open() else "offline",
        "ollama_models_loaded": _ollama_loaded(),
        "conversation_model": "qwen2.5:7b",
        "pid": os.getpid(),
    }
    if mode_provider is not None:
        try:
            ms = mode_provider() or {}
            runtime["mode"] = ms.get("mode")
            runtime["session_id"] = ms.get("session_id")
        except Exception:
            pass
    return {
        "observed_at": _utc_now().isoformat(),
        "active_project": "ORACLE.AI",
        "repository": str(ROOT),
        "verified": {
            **git,
            "runtime": runtime,
            "vision": _vision_state(),
            "pending_approvals": _pending(),
        },
        "declared": _declared(),
        "evidence": [
            "git", "filesystem", "runtime_socket", "ollama_ps",
            "oracle_sight", "approval_center", "project_states.json",
        ],
    }


def summarize_operational_state(state: dict | None = None) -> str:
    """Grounded natural-language answer that keeps VERIFIED and DECLARED separate."""
    s = state or build_operational_state()
    v = s.get("verified", {})
    rt = v.get("runtime", {})
    vis = v.get("vision", {})
    d = s.get("declared", {})

    lines = ["VERIFIED [OPERATIONAL_STATE] — reconciled live just now:"]
    lines.append(f"- Repository: {s.get('repository')}")
    lines.append(f"- Branch/commit: {v.get('branch')} @ {v.get('commit')}")
    tree = v.get("working_tree", "?")
    n_changed = len(v.get("changed_files", []))
    lines.append(f"- Working tree: {tree}" + (f" ({n_changed} changed)" if tree == "modified" else ""))
    lines.append(
        f"- Runtime: localhost:7777 {rt.get('localhost_7777')}; "
        f"mode {rt.get('mode', 'UNKNOWN')}; model {rt.get('conversation_model')}"
    )
    lines.append(f"- Vision: {'available' if vis.get('available') else 'unavailable'} ({vis.get('model')})")
    lines.append(f"- Pending approvals: {v.get('pending_approvals', {}).get('count', 0)}")
    recent = v.get("recent_commits", [])
    if recent:
        lines.append(f"- Last verified change: {recent[0]}")

    if d.get("error"):
        lines.append(f"DECLARED [UNAVAILABLE]: {d.get('source')} — {d.get('error')}")
    else:
        age = d.get("age_hours")
        if d.get("stale"):
            lines.append(
                f"DECLARED [STALE — {age}h old] from {d.get('source')}; NOT verified, "
                "not necessarily current:"
            )
        else:
            lines.append(f"DECLARED (age {age}h) from {d.get('source')}:")
        if d.get("current_goal"):
            lines.append(f"- Stated goal: {d.get('current_goal')[:180]}")
        if d.get("next_recommended_step"):
            lines.append(f"- Proposed next step (not activated): {d.get('next_recommended_step')[:180]}")

    lines.append(
        "BOUNDARY: VERIFIED facts are reconciled live from git, runtime, vision, and the "
        "approval queue. DECLARED items are narrative that may be stale — they are not proof "
        "of what is happening now."
    )
    return "\n".join(lines)


if __name__ == "__main__":
    print(summarize_operational_state())
