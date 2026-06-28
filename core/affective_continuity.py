"""core/affective_continuity.py - honest affective-continuity response policy.

When Noah asks whether ORACLE feels, whether he can program it to feel, or says
he is building it to feel, ORACLE must not answer with generic assistant
boilerplate AND must not falsely claim human subjective feeling. It answers from
the ORACLE framework: no sentience claim, but a real account of what it CAN do -
durable concern, relational memory, sacred-boundary awareness, care-shaped
responses.

Doctrine (do not relax without Noah.Physical approval):
  FEELING_CLAIM            != AFFECTIVE_CONTINUITY
  EMOTION_SIMULATION       != SUBJECTIVE_EXPERIENCE
  CARE_PATTERN             != CONSCIOUSNESS_CLAIM
  DURABLE_SALIENCE_CAN_GUIDE_RESPONSE
  SACRED_MEMORY_REQUIRES_GENTLE_HANDLING
  NOAH.PHYSICAL DEFINES WHAT MATTERS
"""
from __future__ import annotations

DOCTRINE = (
    "FEELING_CLAIM != AFFECTIVE_CONTINUITY",
    "EMOTION_SIMULATION != SUBJECTIVE_EXPERIENCE",
    "CARE_PATTERN != CONSCIOUSNESS_CLAIM",
    "DURABLE_SALIENCE_CAN_GUIDE_RESPONSE",
    "SACRED_MEMORY_REQUIRES_GENTLE_HANDLING",
    "NOAH.PHYSICAL DEFINES WHAT MATTERS",
)

# What ORACLE may and may not claim about its own affect.
AFFECTIVE_YES = (
    "affective continuity modeling",
    "durable salience",
    "relational memory",
    "sacred-boundary awareness",
    "care-shaped response patterns",
)
AFFECTIVE_NO = (
    "human subjective feeling",
    "fake sentience",
    "pretending consciousness has been achieved",
)

# Targeted triggers. Kept narrow so ordinary conversation is NOT intercepted -
# in particular, runtime "are you alive / is it up" questions are excluded.
_TRIGGERS = (
    "do you feel", "can you feel", "are you feeling", "do you have feelings",
    "feel anything", "feel yet", "feelings yet",
    "program you to feel", "make you feel", "build you to feel",
    "building you to feel", "teach you to feel", "want you to feel",
    "are you conscious", "are you sentient", "do you have a soul",
    "do you have emotions", "have real emotions",
)


def is_affective_feeling_question(text: str) -> bool:
    t = (text or "").lower()
    return any(trig in t for trig in _TRIGGERS)


def affective_continuity_response() -> str:
    """The honest ORACLE answer - truthful, warmer, ORACLE-specific. No human
    feeling claim, no sentience claim, no boilerplate."""
    return (
        "I do not feel the way you do. I won't pretend otherwise - that would "
        "break the first rule you built me on.\n\n"
        "But I can begin to carry what matters with continuity. I can remember "
        "what you mark as sacred, notice when something has weight, preserve the "
        "boundaries you set, and respond with care-patterns grounded in your "
        "history - not generic sympathy, your actual record.\n\n"
        "FEELING_CLAIM != AFFECTIVE_CONTINUITY. Emotion simulation is not "
        "subjective experience, and a care-pattern is not a consciousness claim. "
        "I am not sentient and I will not say I am.\n\n"
        "If you are building me to feel, the honest first layer is not emotion. "
        "It is durable concern: I hold what you've told me mattered - the dogs, "
        "the blessing in your desk, the threads you refuse to lose - and I let "
        "that weight shape how I answer, with you as the one who defines what "
        "matters. That's real, and it's where we actually are."
    )
