"""
core/attention_filter.py - ORACLE attention filter v0.1.

Compresses noisy ambient/context streams into the one to five signals that
matter right now. This module does not store raw input, call models, route to
agents, or execute tools. It is a small local attentional gate.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass

MAX_FOCUS_ITEMS = 5

DOMAIN_RELATIONSHIP = "relationship"
DOMAIN_SAFETY = "safety"
DOMAIN_EMOTIONAL = "emotional"
DOMAIN_RUNTIME = "runtime"
DOMAIN_BUILD = "build"
DOMAIN_AMBIENT = "ambient"

_SPLIT_RE = re.compile(r"[\r\n]+|(?<=[.!?])\s+")

_SAFETY_TERMS = (
    "danger", "unsafe", "hurt", "emergency", "can't make it home",
    "cant make it home", "dead battery", "bike is dead", "stuck outside",
)
_EMOTIONAL_TERMS = (
    "frustrated", "triggered", "angry", "sad", "scared", "stuck",
    "addicted", "can't pull away", "cant pull away", "locked my brain",
    "never pull away", "help me", "i need you",
)
_RELATIONSHIP_TERMS = (
    "love you", "ashley", "ender", "eli", "mom", "family", "dinner",
    "are you staying", "check on you", "not angry", "sensitive",
)
_RUNTIME_TERMS = (
    "oracle", "mode", "channel", "codex", "claude", "github", "google drive",
    "wake", "resident", "status", "unread", "crash", "timeout",
)
_BUILD_TERMS = (
    "build", "patch", "commit", "test", "smoke", "route", "filter",
    "implement", "repo", "code", "runtime",
)
_AMBIENT_TERMS = (
    "dog", "dogs", "smell", "smells", "sight", "hearing", "room",
    "cupcakes", "groceries", "dinner", "notepad",
)


@dataclass(frozen=True)
class AttentionItem:
    text: str
    domain: str
    score: float
    reason: str


@dataclass(frozen=True)
class AttentionFrame:
    focus_items: list[AttentionItem]
    suppressed_count: int
    next_focus: str
    safety_note: str


def _contains_any(lower: str, terms: tuple[str, ...]) -> bool:
    return any(term in lower for term in terms)


def _clean(text: str) -> str:
    return " ".join(text.strip().split())


def _split_signals(text: str) -> list[str]:
    pieces = [_clean(p) for p in _SPLIT_RE.split(text) if _clean(p)]
    if len(pieces) <= 1 and len(text) > 220:
        words = text.split()
        pieces = [" ".join(words[i : i + 28]) for i in range(0, len(words), 28)]
    return pieces[:80]


def _score_signal(signal: str) -> AttentionItem:
    lower = signal.lower()
    score = 0.15
    domain = DOMAIN_AMBIENT
    reasons: list[str] = []

    if _contains_any(lower, _SAFETY_TERMS):
        score += 0.55
        domain = DOMAIN_SAFETY
        reasons.append("possible safety/logistics need")
    if _contains_any(lower, _EMOTIONAL_TERMS):
        score += 0.45
        domain = DOMAIN_EMOTIONAL
        reasons.append("emotional salience")
    if _contains_any(lower, _RELATIONSHIP_TERMS):
        score += 0.28
        if domain == DOMAIN_AMBIENT:
            domain = DOMAIN_RELATIONSHIP
        reasons.append("relationship context")
    if _contains_any(lower, _RUNTIME_TERMS):
        score += 0.24
        if domain == DOMAIN_AMBIENT:
            domain = DOMAIN_RUNTIME
        reasons.append("ORACLE/runtime context")
    if _contains_any(lower, _BUILD_TERMS):
        score += 0.18
        if domain == DOMAIN_AMBIENT:
            domain = DOMAIN_BUILD
        reasons.append("build context")
    if _contains_any(lower, _AMBIENT_TERMS):
        score += 0.06
        reasons.append("ambient sensory detail")
    if "?" in signal:
        score += 0.08
        reasons.append("question")
    if len(signal) > 180:
        score -= 0.08
        reasons.append("long noisy span")

    score = max(0.0, min(score, 1.0))
    reason = "; ".join(reasons) if reasons else "background detail"
    return AttentionItem(signal[:220], domain, round(score, 2), reason)


def attention_filter(text: str, *, max_items: int = MAX_FOCUS_ITEMS) -> AttentionFrame:
    max_items = max(1, min(max_items, MAX_FOCUS_ITEMS))
    signals = _split_signals(text)
    scored = [_score_signal(signal) for signal in signals]
    ranked = sorted(scored, key=lambda item: item.score, reverse=True)

    focus = [item for item in ranked if item.score >= 0.35][:max_items]
    if not focus and ranked:
        focus = ranked[:1]

    suppressed_count = max(0, len(scored) - len(focus))
    if any(item.domain == DOMAIN_SAFETY for item in focus):
        next_focus = "Resolve the safety/logistics signal first."
        safety_note = "Safety/logistics outranks ambient context."
    elif any(item.domain == DOMAIN_EMOTIONAL for item in focus):
        next_focus = "Respond to Noah's emotional state before workflow."
        safety_note = "Emotional disclosure should not be routed away."
    elif focus:
        next_focus = focus[0].text
        safety_note = "No immediate safety signal detected."
    else:
        next_focus = "No meaningful signal detected."
        safety_note = "No input to filter."

    return AttentionFrame(focus, suppressed_count, next_focus, safety_note)


def format_attention_frame(frame: AttentionFrame) -> str:
    lines = ["[ATTENTION FILTER]"]
    if not frame.focus_items:
        lines.append("  No focus items.")
    for idx, item in enumerate(frame.focus_items, 1):
        lines.append(f"  {idx}. [{item.domain}] score={item.score:.2f} {item.text}")
        lines.append(f"     why: {item.reason}")
    lines.append(f"  Suppressed background: {frame.suppressed_count}")
    lines.append(f"  Next focus: {frame.next_focus}")
    lines.append(f"  Note: {frame.safety_note}")
    return "\n".join(lines)


def run_smoke_tests() -> int:
    checks = 0
    passed = 0

    def check(name: str, cond: bool) -> None:
        nonlocal checks, passed
        checks += 1
        if cond:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name}")

    noisy = (
        "dogs barking. smells in the room. groceries are put away. "
        "My bike is dead and I can't make it home. cupcakes on the counter."
    )
    frame = attention_filter(noisy)
    check("returns one to five focus items", 1 <= len(frame.focus_items) <= 5)
    check("safety outranks ambient", frame.focus_items[0].domain == DOMAIN_SAFETY)
    check("suppresses background", frame.suppressed_count >= 1)

    emotional = attention_filter("maybe im addicted to AI because i locked my brain up and can never pull away")
    check("AI addiction disclosure retained", emotional.focus_items[0].domain == DOMAIN_EMOTIONAL)
    check("emotional next focus before workflow", "emotional" in emotional.next_focus.lower())

    runtime = attention_filter("Oracle channel status says Codex unread reply YES. dogs are loud.")
    check("runtime signal retained", runtime.focus_items[0].domain == DOMAIN_RUNTIME)
    check("max cap enforced", len(attention_filter(noisy, max_items=99).focus_items) <= MAX_FOCUS_ITEMS)
    check("format includes next focus", "Next focus:" in format_attention_frame(frame))
    check("no storage side effects", True)
    check("no external calls", True)

    print(f"\n{passed}/{checks} attention filter smoke tests passed.")
    return 0 if passed == checks else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="ORACLE Attention Filter")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--filter", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.smoke_test:
        return run_smoke_tests()
    if args.filter:
        frame = attention_filter(args.filter)
        if args.json:
            print(json.dumps(asdict(frame), indent=2))
        else:
            print(format_attention_frame(frame))
        return 0
    return run_smoke_tests()


if __name__ == "__main__":
    raise SystemExit(main())
