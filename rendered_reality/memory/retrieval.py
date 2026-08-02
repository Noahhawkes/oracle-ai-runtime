"""Honest local keyword retrieval for Rendered Reality receipts."""

from __future__ import annotations

import re
from dataclasses import dataclass


_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "is", "are", "was",
    "what", "do", "you", "i", "me", "my", "we", "about", "for", "with", "that",
    "this", "it", "can", "your", "her", "she", "from", "have", "has", "tell",
    "know", "remember",
}


def _tokens(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(token) > 2 and token not in _STOP
    ]


@dataclass
class Hit:
    record: object
    score: int
    matched: list[str]


def keyword_search(records, query: str, limit: int = 10) -> list[Hit]:
    """Rank records by query-token overlap without pretending to use vectors."""
    query_tokens = set(_tokens(query))
    if not query_tokens:
        return []
    hits: list[Hit] = []
    for record in records:
        haystack = " ".join(
            [
                getattr(record, "content", "") or "",
                getattr(record, "source", "") or "",
                getattr(record, "event_label", "") or "",
                " ".join(getattr(record, "holes", []) or []),
            ]
        )
        overlap = query_tokens & set(_tokens(haystack))
        if overlap:
            hits.append(Hit(record=record, score=len(overlap), matched=sorted(overlap)))
    hits.sort(key=lambda hit: -hit.score)
    return hits[:limit]
