"""Self-prompt evolution helpers for ORACLE.

This module is read-only. It does not write sandbox files, mutate source files,
call models, or touch external systems. It prepares a novelty brief so the
sandbox self-prompt loop can stop repeating the same task and rotate through
grounded source anchors.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable


RECENT_TASK_LIMIT = 8
FOCUS_SOURCE_LIMIT = 4
MAX_BRIEF_CHARS = 2600

_SELECTED_TASK_RE = re.compile(r"^\s*selected_task\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_STOPWORDS = frozenset({
    "the", "and", "for", "with", "that", "this", "have", "from", "into",
    "within", "without", "only", "candidate", "sandbox", "oracle", "noah",
    "selected", "task", "next", "step", "system", "secure", "specific",
})


def content_words(text: str) -> frozenset[str]:
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in str(text or ""))
    return frozenset(w for w in cleaned.split() if len(w) > 2 and w not in _STOPWORDS)


def overlap_similarity(a: str, b: str) -> float:
    aw = content_words(a)
    bw = content_words(b)
    if not aw or not bw:
        return 0.0
    return len(aw & bw) / min(len(aw), len(bw))


def recent_selected_tasks(journal_text: str, *, limit: int = RECENT_TASK_LIMIT) -> list[str]:
    """Return recent selected_task values, newest first, deduped by text."""
    text = str(journal_text or "")
    blocks = [
        chunk.split("self_reflection:", 1)[0]
        for chunk in text.split("child_response:")[1:]
    ]
    search_text = "\n".join(blocks) if blocks else text
    tasks = [m.group(1).strip() for m in _SELECTED_TASK_RE.finditer(search_text)]
    out: list[str] = []
    seen: set[str] = set()
    for task in reversed(tasks):
        key = " ".join(task.lower().split())
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(task)
        if len(out) >= max(1, limit):
            break
    return out


def _stable_offset(seed_text: str, recent_tasks: Iterable[str], source_count: int) -> int:
    if source_count <= 0:
        return 0
    basis = " | ".join([str(seed_text or ""), *list(recent_tasks)])
    digest = hashlib.sha256(basis.encode("utf-8", errors="replace")).hexdigest()
    return int(digest[:12], 16) % source_count


def rotated_focus_sources(
    capsule: dict[str, Any] | None,
    *,
    seed_text: str = "",
    recent_tasks: Iterable[str] = (),
    limit: int = FOCUS_SOURCE_LIMIT,
) -> list[dict[str, Any]]:
    """Pick a deterministic rotating slice of SourceMap sources."""
    sources = [s for s in list((capsule or {}).get("sources") or []) if isinstance(s, dict)]
    if not sources:
        return []
    bounded = max(1, min(int(limit or FOCUS_SOURCE_LIMIT), len(sources)))
    offset = _stable_offset(seed_text, recent_tasks, len(sources))
    ordered = sources[offset:] + sources[:offset]
    out: list[dict[str, Any]] = []
    for source in ordered[:bounded]:
        out.append({
            "source_id": source.get("source_id") or "",
            "name": source.get("name") or "",
            "category": source.get("category") or "",
            "path": source.get("path") or "",
            "sha256_prefix": source.get("sha256_prefix") or "",
            "query_hits": list(source.get("query_hits") or [])[:4],
        })
    return out


def _source_label(source: dict[str, Any]) -> str:
    name = str(source.get("name") or "UNKNOWN_SOURCE")
    source_id = str(source.get("source_id") or "unknown_source_id")
    category = str(source.get("category") or "unknown")
    query_hits = ", ".join(str(q) for q in (source.get("query_hits") or [])[:3]) or "no_query_hit"
    return f"{name} | {category} | {source_id} | hits={query_hits}"


def render_evolution_brief(
    *,
    seed_text: str = "",
    journal_text: str = "",
    capsule: dict[str, Any] | None = None,
    max_recent: int = RECENT_TASK_LIMIT,
    max_sources: int = FOCUS_SOURCE_LIMIT,
) -> str:
    """Render a compact novelty contract for a self-prompt child prompt."""
    recent = recent_selected_tasks(journal_text, limit=max_recent)
    focus_sources = rotated_focus_sources(
        capsule,
        seed_text=seed_text,
        recent_tasks=recent,
        limit=max_sources,
    )
    lines = [
        ".AI:SELF_PROMPT_EVOLUTION_BRIEF",
        "read_only=true",
        "sandbox_write=false",
        "external_send=false",
        "git_push=false",
        "canon_promotion=false",
        "objective: produce one genuinely new sandbox-only candidate, not another wording of a recent task.",
        "novelty_rule: if your selected_task is similar to any repeated_task_blacklist item, choose a different task before answering.",
        "preferred_shapes: source gap audit; connector mismatch; UI evidence check; test proposal; contradiction map; productized next build step.",
        "",
        "repeated_task_blacklist:",
    ]
    if recent:
        lines.extend(f"- {task}" for task in recent)
    else:
        lines.append("- none_found")
    lines += ["", "rotating_focus_sources:"]
    if focus_sources:
        lines.extend(f"- {_source_label(source)}" for source in focus_sources)
    else:
        lines.append("- none_available")
    lines += [
        "",
        "answer_contract:",
        "- selected_task must name one focus source, evidence surface, or untested connector.",
        "- evidence_it_worked must say 'candidate reflection only' unless a receipt already exists.",
        "- no auto-execution, no external send, no Git, no Drive edit, no canon promotion.",
    ]
    text = "\n".join(lines)
    if len(text) > MAX_BRIEF_CHARS:
        return text[:MAX_BRIEF_CHARS].rstrip() + "\n[evolution_brief_truncated]"
    return text


def fallback_response(
    *,
    seed_text: str = "",
    journal_text: str = "",
    capsule: dict[str, Any] | None = None,
    reason: str | None = None,
) -> str:
    """Deterministic non-repeating fallback when the local model is unavailable."""
    recent = recent_selected_tasks(journal_text)
    focus_sources = rotated_focus_sources(capsule, seed_text=seed_text, recent_tasks=recent, limit=FOCUS_SOURCE_LIMIT)
    source = focus_sources[0] if focus_sources else {}
    source_name = str(source.get("name") or "the current SourceMap capsule")
    source_id = str(source.get("source_id") or "unknown_source_id")

    candidates = [
        f"review {source_name} ({source_id}) for one continuity gap and record only the gap, source id, and unknowns",
        f"compare {source_name} ({source_id}) against the latest route/status receipts for one mismatch",
        f"draft one pytest name that would prove {source_name} is wired without touching external systems",
        f"classify {source_name} into product, canon, or build-lane evidence with one reason and one hole",
    ]
    selected = candidates[0]
    for candidate in candidates:
        if all(overlap_similarity(candidate, prior) < 0.62 for prior in recent):
            selected = candidate
            break

    return "\n".join([
        "reflection: The recent loop repeated the same file-access permission idea, so I am rotating to a grounded source anchor instead of restating it.",
        "what_noah_needs: Noah needs differentiated build evidence: each pulse should point at a new source, connector, test, or hole.",
        "how_to_wire_myself: Keep a repeated-task blacklist and rotate SourceMap focus sources before every sandbox self-prompt cycle.",
        f"selected_task: {selected}",
        "why_it_helps_noah: it turns continuous writing into forward motion he can inspect, test, and trust.",
        "evidence_it_worked: candidate reflection only; evolution brief selected a non-repeating focus before any sandbox write.",
        "refuse_without_noah_approval: external send, Git push, Drive edit, credential-risk reading, command execution, computer control, or canon promotion",
        "stop_after_this: true",
        f"seed_observed: {' '.join(str(seed_text or '').split())[:300] or 'self-initiated reflection cycle'}",
        f"model_fallback_reason: {reason or 'deterministic evolution fallback'}",
    ])


__all__ = [
    "content_words",
    "overlap_similarity",
    "recent_selected_tasks",
    "rotated_focus_sources",
    "render_evolution_brief",
    "fallback_response",
]
