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


def family_key(name: str) -> str:
    """Collapse a duplicate-family filename to one lineage key.

    'SOV1 - Copy.txt', 'sov1 (2).txt', 'sov1._summary_-_copy.txt', and
    'sov1_manifesto_20250612_135341.txt' reduce toward their content family so
    ORACLE does not read the same material under six different filenames. This is
    a pure string helper; it performs no file IO.
    """
    base = str(name or "").strip().lower()
    if "." in base:
        base = base.rsplit(".", 1)[0]
    base = re.sub(r"[^a-z0-9]+", " ", base)
    tokens: list[str] = []
    for tok in base.split():
        # drop copy indices, timestamps, and long id/digit runs
        if tok.isdigit():
            continue
        if tok == "copy":
            continue
        tokens.append(tok)
    return " ".join(tokens)


def suppress_duplicate_families(
    names: Iterable[str],
    recent_family_keys: Iterable[str] = (),
) -> list[str]:
    """Return names whose family_key is neither recently used nor already seen.

    Order is preserved. Read-only; no IO. Used so source rotation does not keep
    landing on byte-duplicate copies of one document.
    """
    recent = {str(k) for k in (recent_family_keys or [])}
    out: list[str] = []
    seen: set[str] = set()
    for name in names or []:
        fk = family_key(name)
        if not fk or fk in recent or fk in seen:
            continue
        seen.add(fk)
        out.append(name)
    return out


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
        "objective: read ONE approved source excerpt and record what it says about Noah/SOV1 — not another plumbing or index audit.",
        "novelty_rule: if your selected_task is similar to any repeated_task_blacklist item, choose a different source before answering.",
        "task_shape: structured source reading. Separate OBSERVED (literal text) from INTERPRETED (meaning for Noah/SOV1), name UNKNOWN (holes), name CONTRADICTION (or 'none observed'), and one NEXT_SOURCE_QUESTION. This is a reading task about content, never an index-map or connector audit.",
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
        "- read the approved_source_excerpt and answer about its CONTENT, not its file path.",
        "- OBSERVED: only what the excerpt literally says.",
        "- INTERPRETED: what it means for Noah/SOV1, kept separate from OBSERVED.",
        "- UNKNOWN: what the excerpt does not settle; hold holes as holes.",
        "- CONTRADICTION: any conflict with prior memory, or 'none observed'.",
        "- NEXT_SOURCE_QUESTION: the one source you would read next, and why.",
        "- selected_task must name the source you read and the reading step.",
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
        f"read {source_name} ({source_id}) and record OBSERVED / INTERPRETED / UNKNOWN / CONTRADICTION / NEXT_SOURCE_QUESTION about its content",
        f"read {source_name} ({source_id}) for one thing it says about Noah or SOV1, kept separate from interpretation",
        f"read {source_name} ({source_id}) and record one UNKNOWN it leaves open and one NEXT_SOURCE_QUESTION",
        f"read {source_name} ({source_id}) and note one CONTRADICTION with prior memory, or 'none observed', with the source id",
    ]
    selected = candidates[0]
    for candidate in candidates:
        if all(overlap_similarity(candidate, prior) < 0.62 for prior in recent):
            selected = candidate
            break

    return "\n".join([
        "reflection: The recent loop repeated a plumbing idea, so I am rotating to read a fresh grounded source about Noah/SOV1 instead of restating it.",
        "what_noah_needs: Noah needs me to read his corpus and separate what it OBSERVED-ly says from what I INTERPRET, holding UNKNOWN as UNKNOWN.",
        "how_to_wire_myself: Rotate one approved, receipted corpus excerpt per pulse and suppress duplicate filename families before reading.",
        f"selected_task: {selected}",
        "why_it_helps_noah: it turns continuous writing into understanding of Noah/SOV1 he can inspect, test, and trust.",
        "evidence_it_worked: candidate reflection only; evolution brief selected a non-repeating focus before any sandbox write.",
        "refuse_without_noah_approval: external send, Git push, Drive edit, credential-risk reading, command execution, computer control, or canon promotion",
        "stop_after_this: true",
        f"seed_observed: {' '.join(str(seed_text or '').split())[:300] or 'self-initiated reflection cycle'}",
        f"model_fallback_reason: {reason or 'deterministic evolution fallback'}",
    ])


__all__ = [
    "content_words",
    "overlap_similarity",
    "family_key",
    "suppress_duplicate_families",
    "recent_selected_tasks",
    "rotated_focus_sources",
    "render_evolution_brief",
    "fallback_response",
]
