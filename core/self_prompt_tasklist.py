"""Read-only tasklist context for ORACLE sandbox self-prompting.

The self-prompt journal is a stream; action_candidates is a proposal queue.
This module renders those surfaces as a compact tasklist so the next
self-prompt cycle can see what is already open, repeated, approved, or dead
before choosing another selected_task.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

try:  # pragma: no cover - import shape differs between test and runtime callers
    from self_prompt_evolution import recent_selected_tasks
except Exception:  # pragma: no cover
    from .self_prompt_evolution import recent_selected_tasks  # type: ignore


MAX_CONTEXT_CHARS = 2600
DEFAULT_LIMIT = 6
ACTIVE_STATUSES = frozenset({"pending", "approved"})
DEAD_STATUSES = frozenset({"rejected", "revoked", "quarantined"})


def _clip(value: Any, limit: int = 180) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _load_candidates(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _recent_by_status(
    candidates: Iterable[dict[str, Any]],
    statuses: frozenset[str],
    *,
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    rows = [c for c in candidates if str(c.get("status") or "").lower() in statuses]
    rows.sort(key=lambda c: str(c.get("updated_at") or c.get("created_at") or ""), reverse=True)
    return rows[: max(1, int(limit or DEFAULT_LIMIT))]


def _candidate_line(candidate: dict[str, Any]) -> str:
    cid = str(candidate.get("id") or "")[:8] or "unknown"
    status = _clip(candidate.get("status"), 14)
    title = _clip(candidate.get("title"), 150)
    risk = _clip(candidate.get("risk_level"), 10)
    return f"{status} | {risk} | {cid} | {title}"


def render_tasklist_context(
    *,
    journal_text: str = "",
    candidates_path: Path | str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> str:
    """Render ORACLE's self-writing task memory as prompt context.

    Read-only. No sandbox write, action-candidate mutation, approval, or
    execution happens here.
    """
    path = Path(candidates_path) if candidates_path else None
    candidates = _load_candidates(path)
    recent_tasks = recent_selected_tasks(journal_text, limit=limit)
    active = _recent_by_status(candidates, ACTIVE_STATUSES, limit=limit)
    dead = _recent_by_status(candidates, DEAD_STATUSES, limit=limit)

    lines = [
        ".AI:SELF_PROMPT_TASKLIST",
        "read_only=true",
        "sandbox_write=false",
        "external_send=false",
        "git_push=false",
        "canon_promotion=false",
        "purpose: choose the next self-prompt task without duplicating recent work.",
        "",
        "recent_selected_tasks_do_not_repeat:",
    ]
    if recent_tasks:
        lines.extend(f"- {_clip(task, 220)}" for task in recent_tasks)
    else:
        lines.append("- none_found")

    lines += ["", "active_candidates_in_play:"]
    if active:
        lines.extend(f"- {_candidate_line(candidate)}" for candidate in active)
    else:
        lines.append("- none_found")

    lines += ["", "dead_or_quarantined_candidates_do_not_resubmit:"]
    if dead:
        lines.extend(f"- {_candidate_line(candidate)}" for candidate in dead)
    else:
        lines.append("- none_found")

    lines += [
        "",
        "task_selection_rules:",
        "- If your selected_task matches recent_selected_tasks_do_not_repeat, choose another task.",
        "- If your selected_task matches active_candidates_in_play, refine or defer it instead of resubmitting.",
        "- If your selected_task matches dead_or_quarantined_candidates_do_not_resubmit, do not resurrect it.",
        "- If no genuinely new grounded task exists, answer quality_gate: discard_no_write and stop.",
    ]

    text = "\n".join(lines)
    if len(text) > MAX_CONTEXT_CHARS:
        return text[:MAX_CONTEXT_CHARS].rstrip() + "\n[tasklist_context_truncated]"
    return text


__all__ = ["render_tasklist_context"]
