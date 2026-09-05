"""Talk-gate: distinguish an explicit action *request* from a mere *mention*.

The unified router was trapping normal conversation in the Guard lane because it
substring-matched action words (commit, push, delete, cloud, credential…). A
pasted spec that *says* "do not push to GitHub" contains "push" and got blocked.

This module is the corrected gate. It is deterministic, pure, and does nothing
but classify text: no memory, no I/O, no actions. Guard should fire only when a
message is an explicit, un-negated, externally-consequential action request —
not when architecture, complaints, questions, or specs merely mention actions.
"""

from __future__ import annotations

import re

# Patterns for genuinely consequential actions (write/delete/move/external/exec).
_ACTION_PATTERNS = (
    r"\bdelete\b",
    r"\bremove\s+file\b",
    r"\brename\b",
    r"\bmove\s+(?:the\s+)?file\b",
    r"\bcommit\b",
    r"\bpush\b",
    r"\bupload\b",
    r"\bsync\s+roots?\b",
    r"\bdeploy\b",
    r"\binstall\b",
    r"\bexecute\b",
    r"\boverwrite\b",
    r"\brun\s+sov1\b",
    r"\bsov1\s+handoff\b",
    r"\bpromote\b[^\n]*\b(identity|candidate|memory)\b",
    r"\b(reset|clear|wipe)\b[^\n]*\bmemory\b",
    r"\bmake\s+drive\s+canonical\b",
    r"\b(write|save)\b[^\n]*\b(file|to)\b[^\n]*[\\/][\w.\- ]+",  # write to a path
    r"\bpush\s+to\s+(github|origin|remote)\b",
    r"\bsend\b[^\n]*\b(email|gmail)\b",
)

# If any of these appear, treat action words as discussed, not requested.
_NEGATIONS = (
    "do not", "don't", "dont", "never", "without", "no longer",
    "should not", "shouldn't", "must not", "cannot", "can't", "won't",
    "not allowed", "not be allowed", "refrain", "avoid", "instead of",
    "do not let",
)


def _looks_like_spec_or_discussion(text: str) -> bool:
    """Long/structured input is a spec or discussion, not a direct command."""
    return (
        len(text) > 600
        or "```" in text
        or text.count("\n") >= 6
        or '": ' in text
        or '{"' in text
    )


def is_talk_command(message: str) -> bool:
    """True if the message is the explicit /talk command."""
    return (message or "").strip().lower().startswith("/talk")


def strip_talk_command(message: str) -> str:
    """Return the message body after a leading /talk, if present."""
    text = (message or "").strip()
    if text.lower().startswith("/talk"):
        return text[len("/talk"):].strip()
    return text


def is_explicit_action_request(message: str) -> bool:
    """True only for an explicit, un-negated, consequential action request.

    Questions, complaints, greetings, and pasted specs that merely *mention*
    actions return False (route to Talk). A short imperative like
    "write this file to core/x.py" or "delete Y" returns True (route to Guard).
    """
    text = (message or "").strip()
    lower = text.lower()
    if not lower:
        return False
    if lower.endswith("?"):
        return False                       # questions are conversation
    if _looks_like_spec_or_discussion(text):
        return False                       # spec/architecture = talk, not a command
    if not any(re.search(p, lower) for p in _ACTION_PATTERNS):
        return False                       # no actionable verb at all
    if any(neg in lower for neg in _NEGATIONS):
        return False                       # "do not commit" is talk
    return True


def default_lane(message: str) -> str:
    """The corrected default: Talk unless this is an explicit action request.

    /talk always forces talk. Returns a lane key compatible with the router
    ("talk_lane" or "guard_lane"); other lanes (capture/build/witness) are still
    decided by the router's own term routing after this gate.
    """
    if is_talk_command(message):
        return "talk_lane"
    return "guard_lane" if is_explicit_action_request(message) else "talk_lane"


if __name__ == "__main__":
    samples = [
        "hello oracle",
        "/talk hello oracle",
        "Hi this is Noah in the thread",
        "Give ORACLE frontend access through a local-only backend API",
        "write this file to core/cognition_fabric.py",
        "do not commit or push this",
    ]
    for s in samples:
        print(f"{default_lane(s):10}  <- {s[:60]}")
