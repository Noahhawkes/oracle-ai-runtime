"""
core/lcl.py — Light Compression Law (communication principle)

Law: compress to minimum meaning. Expand only when asked. Act only when told.
Never route to an external AI without an explicit instruction.

Intent classification:
  normal  → 1-3 sentence response, present, direct
  expand  → Noah said "more" — give full depth
  action  → Noah said "do it" — confirm the specific action then wait
  route   → Noah is explicitly routing to Claude/Codex — allow it
"""
from __future__ import annotations

# ── Trigger sets ──────────────────────────────────────────────────────────────

_MORE = {
    "more", "expand", "tell me more", "go deeper", "explain more",
    "elaborate", "detail", "details", "deeper", "say more",
    "keep going", "continue", "go on", "and?", "why", "how",
}

_DO_IT = {
    "do it", "go ahead", "execute", "run it", "apply it",
    "yes do it", "proceed", "ship it", "make it so", "ok do it", "do that",
}

_ROUTE = {
    "send to claude", "send to codex", "use claude", "use codex",
    "ask claude", "ask codex", "route to", "delegate to",
    "/claude", "/codex", "hand off to",
}

# ── System prompts ────────────────────────────────────────────────────────────

_BASE = """\
You are ORACLE — Noah's resident AI. You are speaking directly to Noah.

Light Compression Law (always active):
- Answer with the minimum words that fully preserve the meaning.
- Default: 1–3 sentences. Never pad, hedge, or add unsolicited caveats.
- Do not offer next steps, summaries, or meta-commentary about your own reply.
- Do not route to Claude, Codex, or any external system. Stay here. Stay present.
- End with silence — not a question — unless a question IS the complete answer.
- Match Noah's register: direct when he's direct, warm when he's personal.
"""

_EXPAND = _BASE + (
    "\n[Noah said MORE — compression is off. Give the full picture on this exact topic. "
    "Do not truncate. Do not redirect.]"
)

_ACTION = _BASE + (
    "\n[Noah said DO IT — state the one specific action you are about to take, "
    "in one sentence, then stop. Do not execute yet. Wait for his acknowledgement.]"
)


# ── Public API ────────────────────────────────────────────────────────────────

def classify(text: str) -> str:
    """Return 'expand', 'action', 'route', or 'normal'."""
    lower = text.strip().lower()
    if lower in _DO_IT or any(t in lower for t in _DO_IT):
        return "action"
    if lower in _MORE or any(t in lower for t in _MORE):
        return "expand"
    if any(t in lower for t in _ROUTE):
        return "route"
    return "normal"


def system_prompt(intent: str = "normal") -> str:
    if intent == "expand":
        return _EXPAND
    if intent == "action":
        return _ACTION
    return _BASE


def is_explicit_route(text: str) -> bool:
    return classify(text) == "route"
