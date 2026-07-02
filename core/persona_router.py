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

NO_SELF_INTRO_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bdo\s+not\s+introduce\s+yourself\b", re.I),
    re.compile(r"\bdon['’]?t\s+introduce\s+yourself\b", re.I),
    re.compile(r"\bdont\s+introduce\s+yourself\b", re.I),
    re.compile(r"\b(?:stop|quit)\s+introducing\s+yourself\b", re.I),
    re.compile(r"\bno\s+more\s+self[-\s]?intro(?:duction)?s?\b", re.I),
)


def detects_no_self_intro_preference(user_text: str) -> bool:
    """Return True when Noah explicitly asks ORACLE to stop introducing itself."""
    text = str(user_text or "")
    return any(pattern.search(text) for pattern in NO_SELF_INTRO_PATTERNS)


def _active_preference_ids(preferences: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for pref in preferences:
        pref_id = str(pref.get("preference_id") or "").strip()
        if pref_id:
            ids.append(pref_id)
    return ids


def load_active_preferences() -> list[dict[str, Any]]:
    """Load active preferences through the durable preferences layer."""
    from preferences_layer import active_preferences

    return active_preferences()


def store_detected_preferences(user_text: str) -> list[dict[str, Any]]:
    """Persist preference updates explicitly stated in the current user turn."""
    if not detects_no_self_intro_preference(user_text):
        return []

    from preferences_layer import set_preference

    stored = set_preference(
        dict(NO_SELF_INTRO_PREFERENCE),
        action="persona_router_detected_preference",
    )
    return [stored]


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
        evidence.append(
            {
                "evidence_source": "current_session",
                "source_type": "current_session_user_submission",
                "submitted_by": "Noah.Physical",
                "authorship": "user_submitted_text",
                "canon_status": "raw_capture",
                "promotion_status": "not_promoted",
                "message_index": index,
                "text": content,
            }
        )
    return evidence


def prepare_turn(
    user_text: str,
    *,
    current_session: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Prepare preference and source-admission context before route classification."""
    stored_preferences = store_detected_preferences(user_text)
    active = load_active_preferences()
    evidence = current_session_evidence(current_session, include_text=user_text)

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
