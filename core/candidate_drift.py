"""
core/candidate_drift.py — shared anti-amplification machinery for candidate producers.

ORACLE has more than one thing that produces governed candidates:

  reflection_candidates.py   her own sandbox reflections  -> candidate
  prompt_learning_loop.py    Noah's prompts               -> candidate

Both need the same protection, and it must be defined once. The danger Noah named
in "When the Mirror Spoke Back" is ungoverned recursive amplification: a loop that
re-proposes its own last output with rising confidence until noise reads as
conviction. A producer without a drift check is that loop.

This module holds the shared primitives so the two producers cannot drift apart
from each other, which would be its own quiet failure.

Nothing here writes, approves, or promotes. It only measures similarity.
"""

from __future__ import annotations

import difflib
import re

# Similarity at or above this is treated as restatement, not new thought.
DRIFT_THRESHOLD = 0.88

# How many recent proposals to compare against.
DRIFT_LOOKBACK = 8

_SECRET_PATTERNS = (
    re.compile(r"\b(?:sk|pk|ghp|gho|ghs|xox[baprs])[-_][A-Za-z0-9_\-]{16,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b[A-Za-z0-9_\-]{0,10}(?:api[_-]?key|secret|password|passwd|token)"
               r"\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{16,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    # Seed phrases and wallet material stay out by construction.
    re.compile(r"\b(?:seed\s+phrase|mnemonic|private\s+key)\b\s*[:=]?\s*\S+", re.IGNORECASE),
)

REDACTION = "[REDACTED]"


def normalize(text: str) -> str:
    """Lowercase, collapse whitespace. Comparison form only, never stored as content."""
    return " ".join(str(text or "").lower().split())


def clip(text: str, limit: int) -> str:
    """Single-line, length-bounded. Candidates summarize; they do not archive."""
    body = " ".join(str(text or "").split())
    return body if len(body) <= limit else body[: limit - 1].rstrip() + "…"


def contains_secret(text: str) -> bool:
    return any(p.search(str(text or "")) for p in _SECRET_PATTERNS)


def redact(text: str) -> str:
    """Remove credential-shaped material before anything is persisted.

    Fails toward over-redaction. A candidate that lost a token is recoverable;
    a candidate that stored one is not."""
    body = str(text or "")
    for pattern in _SECRET_PATTERNS:
        body = pattern.sub(REDACTION, body)
    return body


def drift_score(text: str, prior_texts: list[str]) -> tuple[float, str]:
    """Highest similarity between this proposal and recent ones.

    Returns (score, closest_prior). Score 0.0 when there is nothing to compare."""
    needle = normalize(text)
    if not needle:
        return 0.0, ""
    best, matched = 0.0, ""
    for prior in prior_texts:
        candidate = normalize(prior)
        if not candidate:
            continue
        ratio = difflib.SequenceMatcher(None, needle, candidate).ratio()
        if ratio > best:
            best, matched = ratio, prior
    return best, matched


def is_amplification(score: float) -> bool:
    return score >= DRIFT_THRESHOLD
