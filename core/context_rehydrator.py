"""Return-to-Work Context Rehydrator (V1).

Answers "where were we?" deterministically from durable state so a new session or
a restarted server resumes instead of starting at turn zero. Reads the latest
continuity event + active goal, builds a bounded <return_to_work_state> capsule,
and (when wired) injects it into the prompt floor.

Work-state only: no private PII in the capsule. Injectable sources for tests;
real defaults read the actual local ledgers. Pure stdlib.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
EVENTS = ROOT / "data" / "ledger" / "events.jsonl"
GOALS_DIR = ROOT / "data" / "ledger"

UNKNOWN = "UNKNOWN"
MAX_CAPSULE_CHARS = 1200


def _sha(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()[:16]


def latest_event(events_path: str | Path = EVENTS) -> dict[str, Any] | None:
    p = Path(events_path)
    if not p.exists():
        return None
    try:
        lines = [ln for ln in p.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
        return json.loads(lines[-1]) if lines else None
    except (OSError, ValueError):
        return None


def active_goal(goal_store_dir: str | Path = GOALS_DIR) -> dict[str, Any] | None:
    try:
        import goal_state as gs
        store = gs.GoalStore(store_dir=goal_store_dir)
        actives = store.active()
        if not actives:
            return None
        g = actives[-1]
        return {"goal_id": g.goal_id, "purpose": g.purpose, "status": g.status,
                "next_safe_action": g.next_safe_action, "blocked_by": g.blocked_by,
                "last_progress": g.last_progress}
    except Exception:
        return None


def build_capsule(*, latest_event_fn: Callable[[], dict | None] | None = None,
                  active_goal_fn: Callable[[], dict | None] | None = None,
                  extra: dict[str, Any] | None = None) -> dict[str, Any]:
    ev = (latest_event_fn or latest_event)() or {}
    goal = (active_goal_fn or active_goal)() or {}
    x = dict(extra or {})

    capsule = {
        "thread": x.get("thread") or ev.get("thread_id") or ev.get("session_id") or UNKNOWN,
        "project": x.get("project") or goal.get("purpose") or UNKNOWN,
        "goal": goal.get("purpose") or x.get("goal") or UNKNOWN,
        "goal_status": goal.get("status") or UNKNOWN,
        "last_step": goal.get("last_progress") or x.get("last_step") or UNKNOWN,
        "last_event": ev.get("event_id") or UNKNOWN,
        "blockers": goal.get("blocked_by") or x.get("blockers") or UNKNOWN,
        "unknowns": x.get("unknowns") or UNKNOWN,
        "next_step": goal.get("next_safe_action") or x.get("next_step") or UNKNOWN,
    }
    capsule["provenance"] = _sha(json.dumps(capsule, sort_keys=True, default=str))
    capsule["has_state"] = any(v not in (UNKNOWN, None, "") for k, v in capsule.items()
                               if k in ("project", "goal", "last_event", "next_step"))
    return capsule


def render_capsule(capsule: dict[str, Any]) -> str:
    """Bounded <return_to_work_state> block. Empty string when there is no real state."""
    if not capsule.get("has_state"):
        return ""
    fields = ("thread", "project", "goal", "goal_status", "last_step", "last_event",
              "blockers", "unknowns", "next_step", "provenance")
    lines = [f"  {f}: {str(capsule.get(f, UNKNOWN))[:160]}" for f in fields]
    block = "<return_to_work_state>\n" + "\n".join(lines) + "\n</return_to_work_state>\n"
    return block[:MAX_CAPSULE_CHARS]


def return_to_work_block(**kwargs) -> str:
    """Convenience: build + render in one call, failing closed to empty."""
    try:
        return render_capsule(build_capsule(**kwargs))
    except Exception:
        return ""
