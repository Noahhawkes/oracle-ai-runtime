"""
rendered_reality/safety.py — required holes + public-safe language constants

These are first-class controls (NEW GROUND 8, 11, 12), not garnish. Tests assert
the required holes are present so silent-failure / overclaim can't slip through.
"""
from __future__ import annotations

# Every hole here MUST appear in HOLES.md (test_holes_display_required).
REQUIRED_HOLES: tuple[str, ...] = (
    "no live Google Drive connector",
    "no ChatGPT/Grok/Gemini import connector",
    "no secure-drive connector",
    "no production embeddings model",
    "no autonomous runtime loop",
    "no relational/person-like agent instantiated",
    "no Oracle.AI ownership claim",
    "no AI personhood claim",
    "no ownership language",
    "not production ready",
    "runtime truth requires local execution and receipts",
)

# Language that must NOT be used in public description (NEW GROUND 11).
UNSAFE_PUBLIC_TERMS: tuple[str, ...] = (
    "digital twin",
    "writes your autobiography",
    "Oracle.AI platform",
    "knows your mind",
    "autonomous memory system",
    "production connector",
    "AI person",
    "owns her",
)

PUBLIC_SAFE_DESCRIPTION = (
    "Rendered Reality is a local runtime that tracks where your words and ideas "
    "came from. It separates what you wrote from what AI wrote, labels gaps, "
    "preserves contradictions, and won't call something true unless you approve "
    "it. It does not watch you. It witnesses what you give it. It does not "
    "invent. It only renders from your approved record."
)
