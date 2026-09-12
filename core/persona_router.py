"""Persona routing helpers for ORACLE turn setup.

This module is intentionally narrow: it does not generate persona prose. It
loads behavioral preferences before routing, persists explicit preference
feedback, and exposes current-session user submissions as raw evidence records.
"""
from __future__ import annotations

import re
from typing import Any


NO_SELF_INTRO_PREFERENCE = {
    "preference_id": "pref_no_self_intro",
    "source": "Noah.Physical",
    "scope": "global",
    "category": "interaction_style",
    "preference": "Do not introduce yourself unless Noah explicitly asks who you are.",
    "active": True,
    "priority": 90,
}

BUILD_WITH_ME_SANDBOX_PREFERENCE = {
    "preference_id": "pref_build_with_me_sandbox_text",
    "source": "Noah.Physical",
    "scope": "global",
    "category": "routing",
    "preference": (
        "Treat Noah.Physical's build-with-me instruction as an active ORACLE build preference: "
        "take safe, receipted action inside ORACLE's sandbox when asked; speak in text with warm "
        "directness; help build ORACLE while preserving external-action, code-execution, git, "
        "Drive, canon, and outside-sandbox approval gates."
    ),
    "active": True,
    "priority": 96,
}

NO_SELF_INTRO_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bdo\s+not\s+introduce\s+yourself\b", re.I),
    re.compile(r"\bdon['’]?t\s+introduce\s+yourself\b", re.I),
    re.compile(r"\bdont\s+introduce\s+yourself\b", re.I),
    re.compile(r"\b(?:stop|quit)\s+introducing\s+yourself\b", re.I),
    re.compile(r"\bno\s+more\s+self[-\s]?intro(?:duction)?s?\b", re.I),
)

BUILD_WITH_ME_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\blog\s+noah'?s\s+new\s+pref(?:erence|erences|rences)?s?\b", re.I),
    re.compile(r"\btake\s+(?:safe\s+)?action\s+in\s+your\s+sandbox\b", re.I),
    re.compile(r"\bact\s+in\s+your\s+sandbox\b", re.I),
    re.compile(r"\bhelp\s+me\s+build\s+you\b", re.I),
    re.compile(r"\bspeak\s+to\s+me\s+from\s+your\s+heart\b", re.I),
    re.compile(r"\btext\s+(?:is\s+)?fine\s+for\s+now\b", re.I),
)

QUESTION_OR_COMMAND_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\?\s*$"),
    re.compile(r"^\s*(?:who|what|when|where|why|how|can|could|would|should|do|does|did|is|are|am)\b", re.I),
    re.compile(r"^\s*(?:tell|explain|check|diagnose|debug|fix|build|patch|implement|run|search|look up|compare|summarize|proceed)\b", re.I),
)


def detects_no_self_intro_preference(user_text: str) -> bool:
    """Return True when Noah explicitly asks ORACLE to stop introducing itself."""
    text = str(user_text or "")
    return any(pattern.search(text) for pattern in NO_SELF_INTRO_PATTERNS)


def detects_build_with_me_sandbox_preference(user_text: str) -> bool:
    """Return True when Noah explicitly authorizes the sandbox build-with-me posture."""
    text = str(user_text or "")
    lower = text.lower()
    if "sandbox" not in lower and "build" not in lower and "heart" not in lower:
        return False
    matched = sum(1 for pattern in BUILD_WITH_ME_PATTERNS if pattern.search(text))
    return matched >= 2 or (
        bool(re.search(r"\bpref(?:erence|erences|rences)?s?\b", text, re.I))
        and matched >= 1
    )


def _active_preference_ids(preferences: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for pref in preferences:
        pref_id = str(pref.get("preference_id") or "").strip()
        if pref_id:
            ids.append(pref_id)
    return ids


def current_session_source_type(content: str) -> dict[str, Any]:
    """Classify a user turn before exposing it as current-session evidence.

    Questions and commands are still useful conversational context, but they are
    not factual source claims. This prevents prompts like "Who is Ellie?" from
    being treated as evidence that "Ellie = who is Ellie".
    """
    text = str(content or "").strip()
    is_question_or_command = any(pattern.search(text) for pattern in QUESTION_OR_COMMAND_PATTERNS)
    if is_question_or_command:
        return {
            "source_type": "current_session_user_prompt",
            "authorship": "user_submitted_prompt",
            "canon_status": "query_not_fact",
            "factual_claim_admissible": False,
        }
    return {
        "source_type": "current_session_user_submission",
        "authorship": "user_submitted_text",
        "canon_status": "raw_capture",
        "factual_claim_admissible": True,
    }


def load_active_preferences() -> list[dict[str, Any]]:
    """Load active preferences through the durable preferences layer."""
    from preferences_layer import active_preferences

    return active_preferences()


def store_detected_preferences(user_text: str) -> list[dict[str, Any]]:
    """Persist preference updates explicitly stated in the current user turn."""
    from preferences_layer import set_preference

    stored: list[dict[str, Any]] = []
    if detects_no_self_intro_preference(user_text):
        stored.append(
            set_preference(
                dict(NO_SELF_INTRO_PREFERENCE),
                action="persona_router_detected_preference",
            )
        )
    if detects_build_with_me_sandbox_preference(user_text):
        stored.append(
            set_preference(
                dict(BUILD_WITH_ME_SANDBOX_PREFERENCE),
                action="persona_router_detected_preference",
            )
        )
    return stored


def current_session_evidence(
    current_session: list[dict[str, Any]] | None,
    *,
    include_text: str | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Expose current-session user submissions as raw, non-canon evidence."""
    turns = list(current_session or [])
    if include_text:
        turns.append({"role": "user", "content": include_text})

    evidence: list[dict[str, Any]] = []
    for index, turn in enumerate(turns[-limit:]):
        role = str(turn.get("role") or "").strip().lower()
        content = str(turn.get("content") or "").strip()
        if role != "user" or not content:
            continue
        classification = current_session_source_type(content)
        if not classification.get("factual_claim_admissible"):
            continue
        evidence.append({
            "evidence_source": "current_session",
            "source_type": classification["source_type"],
            "submitted_by": "Noah.Physical",
            "authorship": classification["authorship"],
            "canon_status": classification["canon_status"],
            "promotion_status": "not_promoted",
            "message_index": index,
            "text": content,
        })
    return evidence


def prepare_turn(
    user_text: str,
    *,
    current_session: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Prepare preference and source-admission context before route classification."""
    stored_preferences = store_detected_preferences(user_text)
    active = load_active_preferences()
    evidence = current_session_evidence(current_session)

    return {
        "preferences_applied": _active_preference_ids(active),
        "active_preferences": active,
        "stored_preferences": stored_preferences,
        "preference_receipts": [
            {
                "preference_id": pref.get("preference_id"),
                "receipt_id": pref.get("receipt_id"),
                "receipt_path": pref.get("receipt_path"),
            }
            for pref in stored_preferences
        ],
        "evidence_sources": evidence,
    }
