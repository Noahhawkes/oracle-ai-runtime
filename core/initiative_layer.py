"""Bounded prompt-back rules for ORACLE.

The initiative layer is deliberately small: it may suggest the next question
ORACLE should ask Noah, but it never executes work, writes memory, promotes
canon, sends externally, or controls the computer.
"""

from __future__ import annotations

import re
from typing import Any


SUPPRESSION_PATTERNS = (
    re.compile(r"\bdo not ask\b", re.I),
    re.compile(r"\bno follow[-\s]?up\b", re.I),
    re.compile(r"\breport only\b", re.I),
    re.compile(r"\bstatus only\b", re.I),
    re.compile(r"\breturn only\b", re.I),
)

THREAD_LOAD_PATTERNS = (
    re.compile(r"\bthread(?:s)?\b.*\b(?:too much|carry|blend|lost|dump|landed|uploaded|pasted)\b", re.I | re.S),
    re.compile(r"\b(?:too much to carry|all blend together|thread dump|pasted text)\b", re.I),
)

EXPLICIT_INITIATIVE_PATTERNS = (
    re.compile(r"\bprompt(?:ing)?\s+back\b", re.I),
    re.compile(r"\bbounded initiative\b", re.I),
    re.compile(r"\binitiative layer\b", re.I),
)

SOURCE_FAILURE_PATTERNS = (
    re.compile(r"^\s*UNAVAILABLE\b", re.I),
    re.compile(r"\bmissing\b.*\b(?:source|grounding|receipt|evidence)\b", re.I),
    re.compile(r"\bcurrent[-_\s]?session\b.*\b(?:source|evidence|submission)\b", re.I),
)

SELF_INTRO_FAILURE_PATTERNS = (
    re.compile(r"\b(?:dont|don't|do not|wouldn't|wouldnt)\s+introduce\s+yourself\b", re.I),
    re.compile(r"\byou said you wouldn['’]?t introduce\b", re.I),
)

CAPTURE_ROUTE_TYPES = {
    "thread_capture_status",
    "thread_burden_report",
    "thread_ingest_file",
    "thread_ingest_dir",
    "thread_ingest_paste",
    "thread_capture",
}


def _matches_any(patterns: tuple[re.Pattern[str], ...], text: str) -> bool:
    return any(pattern.search(text or "") for pattern in patterns)


def _suppressed(user_text: str) -> bool:
    return _matches_any(SUPPRESSION_PATTERNS, user_text)


def maybe_prompt_back(
    user_text: str,
    reply_text: str = "",
    *,
    route_type: str = "",
    lane: str = "",
    preferences_applied: list[str] | None = None,
) -> dict[str, Any] | None:
    """Return a suggestion-only prompt-back candidate for clear decision points."""
    user = str(user_text or "")
    reply = str(reply_text or "")
    route = str(route_type or "")
    if not user.strip() or _suppressed(user):
        return None
    if "Prompt-back candidate:" in reply:
        return None

    reason = ""
    question = ""
    options: list[str] = []

    if _matches_any(EXPLICIT_INITIATIVE_PATTERNS, user):
        reason = "explicit_bounded_initiative_request"
        question = "Do you want me to stage the prompt-back rules, inspect the self-intro preference failure, or hold this as raw evidence?"
        options = ["stage_prompt_back_rules", "inspect_preference_failure", "hold_raw_only"]
    elif _matches_any(THREAD_LOAD_PATTERNS, user) or route in CAPTURE_ROUTE_TYPES:
        reason = "thread_burden_decision_point"
        question = "Do you want me to classify the landed thread material, index/search it, or hold it raw for now?"
        options = ["classify_candidate", "index_or_search", "hold_raw_only"]
    elif reply and _matches_any(SOURCE_FAILURE_PATTERNS, reply):
        reason = "source_validation_boundary"
        question = "Do you want me to use current-session text as raw evidence, search indexed custody, or keep this answer unavailable?"
        options = ["use_current_session_raw_capture", "search_indexed_custody", "keep_unavailable"]
    elif _matches_any(SELF_INTRO_FAILURE_PATTERNS, user):
        reason = "preference_repair_boundary"
        question = "Do you want me to re-save the no-self-intro preference, inspect why it was bypassed, or continue without changing state?"
        options = ["save_preference", "inspect_preference_route", "continue_no_state_change"]

    if not reason:
        return None

    return {
        "initiative_status": "suggestion_only",
        "prompt_back_type": "bounded_question",
        "reason": reason,
        "question": question,
        "options": options,
        "lane": lane or "talk_lane",
        "action_taken": "none",
        "writes_performed": False,
        "external_action_performed": False,
        "approval_required_for_state_change": True,
        "preferences_applied": list(preferences_applied or []),
    }


def format_prompt_back(suggestion: dict[str, Any]) -> str:
    options = suggestion.get("options") or []
    lines = [
        "Prompt-back candidate:",
        str(suggestion.get("question") or "").strip(),
        f"initiative_status: {suggestion.get('initiative_status', 'suggestion_only')}",
        f"action_taken: {suggestion.get('action_taken', 'none')}",
        "approval_required_for_state_change: true",
    ]
    if options:
        lines.append("options: " + ", ".join(str(option) for option in options))
    return "\n".join(lines).strip()


def append_prompt_back(reply_text: str, suggestion: dict[str, Any] | None) -> str:
    text = str(reply_text or "")
    if not suggestion:
        return text
    prompt_back = format_prompt_back(suggestion)
    if not text.strip():
        return prompt_back
    return text.rstrip() + "\n\n" + prompt_back

