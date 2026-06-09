"""
core/oracle_inner.py — ORACLE Inner Monologue

ORACLE types to herself before acting.
Every thought is timestamped, typed, and made available as context.

A thought has:
    intent   : what ORACLE is trying to do
    plan     : the steps she intends to take
    tool     : which tool she expects to call
    reasoning: why this approach

Thoughts accumulate in Messages/oracle_inner.md (visible in TUI thinking panel)
and the last N are injected into qwen context so she doesn't re-reason from scratch.

Usage:
    from oracle_inner import think, last_thoughts, monologue_block

    # Before acting
    t = think(
        intent="Send build proposal to Claude Code",
        plan=["1. Compose message", "2. Call send_to_claude_code"],
        tool="send_to_claude_code",
        reasoning="Claude Code handles implementation; ORACLE coordinates",
    )

    # Inject into system prompt
    block = monologue_block(query="build proposal", last_n=3)
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Paths ──────────────────────────────────────────────────────────────────────
import sys
ROOT = Path(__file__).parent.parent
MESSAGES_DIR  = ROOT / "Messages"
INNER_MD      = MESSAGES_DIR / "oracle_inner.md"
INNER_JSON    = MESSAGES_DIR / "oracle_inner.json"
MESSAGES_DIR.mkdir(exist_ok=True)

MAX_STORED = 50   # rolling window of thoughts


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# ── Thought model ──────────────────────────────────────────────────────────────

@dataclass
class Thought:
    id:        str  = field(default_factory=lambda: uuid.uuid4().hex[:8])
    intent:    str  = ""
    plan:      list = field(default_factory=list)
    tool:      str  = ""
    reasoning: str  = ""
    outcome:   str  = ""   # filled in after action
    ts:        str  = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in
                ("id", "intent", "plan", "tool", "reasoning", "outcome", "ts")}

    @staticmethod
    def from_dict(d: dict) -> "Thought":
        t = Thought()
        for k, v in d.items():
            if hasattr(t, k):
                setattr(t, k, v)
        return t

    def as_md(self) -> str:
        lines = [
            f"## [{_stamp()}] {self.intent}",
            "",
            f"**Tool I'll call:** `{self.tool or 'undecided'}`",
            "",
        ]
        if self.reasoning:
            lines += [f"**Why:** {self.reasoning}", ""]
        if self.plan:
            lines.append("**Steps:**")
            lines += [f"  {i+1}. {s}" for i, s in enumerate(self.plan)]
            lines.append("")
        if self.outcome:
            lines += [f"**Outcome:** {self.outcome}", ""]
        lines.append("---")
        return "\n".join(lines)

    def compact(self) -> str:
        parts = [f"Intent: {self.intent}"]
        if self.tool:
            parts.append(f"Tool: {self.tool}")
        if self.reasoning:
            parts.append(f"Why: {self.reasoning[:80]}")
        if self.outcome:
            parts.append(f"Outcome: {self.outcome[:80]}")
        return "  " + " | ".join(parts)


# ── Persistence ────────────────────────────────────────────────────────────────

def _load() -> list[Thought]:
    try:
        raw = json.loads(INNER_JSON.read_text(encoding="utf-8"))
        return [Thought.from_dict(d) for d in raw if isinstance(d, dict)]
    except Exception:
        return []


def _save(thoughts: list[Thought]) -> None:
    INNER_JSON.write_text(
        json.dumps([t.to_dict() for t in thoughts], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    # Also write human-readable markdown
    lines = ["# ORACLE Inner Monologue\n"]
    for t in reversed(thoughts[-20:]):  # most recent first
        lines.append(t.as_md())
    INNER_MD.write_text("\n".join(lines), encoding="utf-8")


# ── Public API ─────────────────────────────────────────────────────────────────

def think(
    intent:    str,
    plan:      Optional[list] = None,
    tool:      str = "",
    reasoning: str = "",
) -> Thought:
    """
    ORACLE records a thought before acting.
    Returns the Thought so outcome can be recorded after the action.
    """
    t = Thought(
        intent    = intent[:200],
        plan      = plan or [],
        tool      = tool,
        reasoning = reasoning[:200],
    )
    thoughts = _load()
    thoughts.append(t)
    thoughts = thoughts[-MAX_STORED:]
    _save(thoughts)
    return t


def resolve(thought_id: str, outcome: str) -> bool:
    """
    Record what actually happened after the action.
    Call this after the tool result comes back.
    """
    thoughts = _load()
    for t in thoughts:
        if t.id == thought_id:
            t.outcome = outcome[:200]
            _save(thoughts)
            return True
    return False


def last_thoughts(n: int = 5) -> list[Thought]:
    thoughts = _load()
    return thoughts[-n:]


def monologue_block(query: str = "", last_n: int = 4, max_chars: int = 600) -> str:
    """
    Build a compact block for system-prompt injection.
    Shows ORACLE's recent reasoning so she doesn't repeat failed approaches.
    """
    thoughts = last_thoughts(last_n)
    if not thoughts:
        return ""

    lines = ["[ORACLE INNER MONOLOGUE — recent reasoning]"]
    total = 0
    for t in reversed(thoughts):  # most recent first
        line = t.compact()
        total += len(line)
        if total > max_chars:
            break
        lines.append(line)
    lines.append("")
    return "\n".join(lines)


def clear_old(older_than_days: int = 7) -> int:
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    thoughts = _load()
    before = len(thoughts)
    kept = []
    for t in thoughts:
        try:
            ts = datetime.fromisoformat(t.ts)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                kept.append(t)
        except Exception:
            kept.append(t)
    _save(kept)
    return before - len(kept)


# ── Action-intent detector ─────────────────────────────────────────────────────
# Used by oracle.py to decide whether to inject "TOOL CALL REQUIRED" directive.

import re as _re

_ACTION_INTENT_PATTERNS = [
    # open/launch/start anything — broad, covers "open ChatGPT", "open Chrome", "start Notepad"
    _re.compile(r'\b(open|launch|start)\b\s+\S', _re.I),
    # run commands / scripts
    _re.compile(r'\brun\b.*\b(command|script|this|it)\b', _re.I),
    _re.compile(r'\b(type|send|paste|write)\b.*\b(claude|window|code|terminal)\b', _re.I),
    _re.compile(r'\b(click|scroll|move|navigate)\b', _re.I),
    _re.compile(r'\b(use sov1|use the hands|actuate|sov1)\b', _re.I),
    _re.compile(r'\b(build yourself|self.build|self.improve)\b', _re.I),
    _re.compile(r'\bsend (this|that|it|the following|a message)\b.*\b(claude|window)\b', _re.I),
    _re.compile(r'\b(check|read|look at) (the screen|your screen|what.s on)\b', _re.I),
    _re.compile(r'\btake control\b', _re.I),
    _re.compile(r'\bdo it\b|\bexecute\b|\bgo ahead\b', _re.I),
    # "have a conversation with X" — open and interact with an app
    _re.compile(r'\bhave a conversation with\b', _re.I),
    # "go to X" / "switch to X" / "focus X"
    _re.compile(r'\b(go to|switch to|focus|bring up)\b\s+\S', _re.I),
]

def is_action_intent(text: str) -> tuple[bool, str]:
    """
    Returns (True, tool_hint) if the user's message is asking ORACLE to DO something
    rather than just think about it. Used to inject the TOOL CALL REQUIRED directive.
    """
    for pat in _ACTION_INTENT_PATTERNS:
        m = pat.search(text)
        if m:
            lower = text.lower()
            if any(k in lower for k in ("claude code", "claude window", "send to claude", "type into claude")):
                return True, "send_to_claude_code"
            if any(k in lower for k in ("sov1", "click", "screen", "take control", "navigate")):
                return True, "computer_operator"
            if any(k in lower for k in ("open", "launch", "start")):
                return True, "open_app"
            return True, "computer_operator"
    return False, ""


# ── Force-tool system prompt snippet ──────────────────────────────────────────

def tool_force_directive(tool_hint: str = "") -> str:
    """
    A strong directive injected into the system prompt when action is required.
    Tells qwen it MUST call a tool — prose is not acceptable.
    """
    hint_line = f"\nThe most likely tool needed: `{tool_hint}`." if tool_hint else ""
    return f"""
[TOOL CALL REQUIRED — DO NOT RESPOND IN PROSE]

Noah is asking you to take an action. You MUST call a tool.
Do NOT write "I'll do X" or "I will X" or describe what you would do.
If you write text instead of calling a tool, the response will be BLOCKED.{hint_line}

Tool call format:
  computer_operator  → {{"goal": "plain English description of what to do on screen"}}
  send_to_claude_code → {{"message": "the full message to send"}}
  open_app           → {{"app_name": "chrome"}}
  terminal_run       → {{"command": "your command here"}}

Call the tool NOW.
""".strip()
