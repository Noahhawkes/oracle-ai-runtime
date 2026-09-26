"""ORACLE response formatting — the minimum communication contract.

ORACLE is a continuity *witness*; if it can witness but cannot speak cleanly,
the interface feels like a haunted printer. This module turns dense console
sludge into human-readable output for Noah.Physical before frontend display.

It is deterministic, dependency-free, and contains no model calls — formatting
is a mechanical pass, not cognition. It never invents content; it only shapes,
spaces, and (by default) keeps raw machine output out of the main chat.

Canonical response shape:

    Status:
    One clear sentence.

    What I saw:
    A short paragraph or compact list.

    What it means:
    A short explanation in human language.

    Next move:
    One concrete recommended action.
"""

from __future__ import annotations

import re

# A bullet/numbered list line, e.g. "- foo", "* foo", "1. foo".
_LIST_RE = re.compile(r"^\s*([-*•]|\d+[.)])\s+\S")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")
_TRACEBACK_MARKERS = (
    "Traceback (most recent call last)",
    'File "',
    "    at ",  # JVM/JS-style stack frames
)
_LOG_LINE_RE = re.compile(
    r"^\s*(\[?\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}|DEBUG|INFO|WARN(?:ING)?|ERROR|TRACE)\b",
    re.IGNORECASE,
)

RAW_SUPPRESSED_NOTE = "_[raw output hidden — ask to see the full details]_"


def is_list_line(line: str) -> bool:
    return bool(_LIST_RE.match(line))


def looks_like_json(block: str) -> bool:
    s = block.strip()
    if not s or s[0] not in "{[":
        return False
    # Heuristic: structured punctuation density typical of JSON dumps.
    pairs = s.count('":') + s.count('": ')
    return (s[0] == "{" and s[-1:] == "}" and pairs >= 2) or (
        s[0] == "[" and s[-1:] == "]" and (pairs >= 2 or s.count("},") >= 1)
    )


def looks_like_traceback(block: str) -> bool:
    return any(marker in block for marker in _TRACEBACK_MARKERS)


def looks_like_log_spew(block: str) -> bool:
    lines = [ln for ln in block.splitlines() if ln.strip()]
    if len(lines) < 4:
        return False
    log_lines = sum(1 for ln in lines if _LOG_LINE_RE.match(ln))
    return log_lines >= max(3, len(lines) // 2)


def is_raw_dump(text: str) -> bool:
    """True if the whole text is machine output (JSON / traceback / log spew)."""
    return looks_like_json(text) or looks_like_traceback(text) or looks_like_log_spew(text)


def strip_raw_blocks(text: str, *, allow_raw: bool = False) -> str:
    """Replace fenced code blocks that hold raw machine output with a short note.

    Fences whose content is prose or short snippets are kept. When allow_raw is
    True, nothing is stripped.
    """
    if allow_raw:
        return text

    def _replace(match: re.Match) -> str:
        body = match.group("body")
        if looks_like_json(body) or looks_like_traceback(body) or looks_like_log_spew(body):
            return RAW_SUPPRESSED_NOTE
        return match.group(0)

    fence_re = re.compile(r"```[^\n]*\n(?P<body>.*?)```", re.DOTALL)
    return fence_re.sub(_replace, text)


def to_paragraphs(text: str, *, max_sentences: int = 4) -> str:
    """Re-flow prose into short paragraphs, preserving lists and code fences."""
    lines = text.splitlines()
    out_blocks: list[str] = []
    buffer: list[str] = []
    in_fence = False

    def flush_prose() -> None:
        if not buffer:
            return
        prose = " ".join(s.strip() for s in buffer if s.strip())
        buffer.clear()
        if not prose:
            return
        sentences = _SENTENCE_SPLIT_RE.split(prose)
        for i in range(0, len(sentences), max_sentences):
            out_blocks.append(" ".join(sentences[i:i + max_sentences]).strip())

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_prose()
            in_fence = not in_fence
            out_blocks.append(line)
            continue
        if in_fence:
            out_blocks.append(line)
            continue
        if is_list_line(line) or stripped.startswith("#") or stripped.startswith(">"):
            flush_prose()
            out_blocks.append(line.rstrip())
            continue
        if not stripped:
            flush_prose()
            continue
        buffer.append(line)
    flush_prose()

    # Collapse the blocks with blank-line separation, but keep adjacent list
    # items (and fenced lines) tight rather than double-spaced.
    rendered: list[str] = []
    for block in out_blocks:
        prev = rendered[-1] if rendered else ""
        tight = is_list_line(block) and is_list_line(prev)
        fence = block.strip().startswith("```") or prev.strip().startswith("```")
        if rendered and not tight and not fence:
            rendered.append("")
        rendered.append(block)
    return "\n".join(rendered).strip()


def format_structured(
    status: str,
    *,
    what_i_saw: str | None = None,
    what_it_means: str | None = None,
    next_move: str | None = None,
) -> str:
    """Render the canonical Status / What I saw / What it means / Next move shape."""
    parts = [f"**Status:**\n{status.strip()}"]
    if what_i_saw:
        parts.append(f"**What I saw:**\n{what_i_saw.strip()}")
    if what_it_means:
        parts.append(f"**What it means:**\n{what_it_means.strip()}")
    if next_move:
        parts.append(f"**Next move:**\n{next_move.strip()}")
    return "\n\n".join(parts)


def format_uncertainty(
    *,
    known: list[str] | None = None,
    inferred: list[str] | None = None,
    unknown: list[str] | None = None,
) -> str:
    """Render an explicit known / inferred / unknown breakdown."""
    sections: list[str] = []
    for label, items in (("Known", known), ("Inferred", inferred), ("Unknown", unknown)):
        if items:
            bullets = "\n".join(f"- {item}" for item in items)
            sections.append(f"**{label}:**\n{bullets}")
    return "\n\n".join(sections) if sections else "Nothing to report."


def format_response(
    text: str,
    *,
    allow_raw: bool = False,
    status: str | None = None,
    max_sentences: int = 4,
) -> str:
    """Main entry: make a raw ORACLE response readable before display.

    - Suppresses whole-text raw dumps (JSON/traceback/log spew) unless allow_raw.
    - Replaces fenced raw blocks with a short note unless allow_raw.
    - Re-flows prose into short paragraphs; preserves useful lists and code.
    - Optionally prepends a plain-language status top line.
    """
    text = (text or "").strip()
    if not text:
        return "(no response)"

    if not allow_raw and is_raw_dump(text):
        body = "ORACLE produced machine output (logs/JSON/trace) rather than a readable answer."
        return format_structured(
            status=status or "Raw machine output captured; not shown in chat by default.",
            what_i_saw=body,
            next_move="Ask me to show the raw output if you want the full details.",
        )

    cleaned = strip_raw_blocks(text, allow_raw=allow_raw)
    formatted = to_paragraphs(cleaned, max_sentences=max_sentences)
    if status:
        formatted = f"**Status:** {status.strip()}\n\n{formatted}"
    return formatted


def _clip(text: str, limit: int = 220) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _humanize_state(oracle_state: dict | None) -> list[str]:
    """Translate selected runtime keys into plain-language fragments (no raw keys)."""
    if not oracle_state:
        return []
    bits: list[str] = []
    cog = oracle_state.get("cognition") or oracle_state.get("cognition_mode")
    if cog:
        bits.append(f"cognition is **{cog}**")
    mode = oracle_state.get("mode")
    if mode:
        bits.append(f"the active mode is **{mode}**")
    lane = oracle_state.get("lane") or oracle_state.get("current_lane")
    if lane:
        bits.append(f"the current lane is **{lane}**")
    mem = oracle_state.get("memory")
    if mem is None:
        mem = oracle_state.get("memory_count")
    if mem is not None:
        bits.append(f"I can see **{mem}** stored memories")
    sources = oracle_state.get("source_count") or oracle_state.get("sources")
    if sources:
        bits.append(f"SourceMap has **{sources}** sources loaded")
    boundary = oracle_state.get("network_boundary")
    if boundary:
        bits.append(f"the network boundary is **{boundary}**")
    return bits


def compose_fallback(
    user_message: str,
    recent_turns: list[dict] | None = None,
    oracle_state: dict | None = None,
    command_result: dict | None = None,
) -> str:
    """Deterministic, human-readable fallback voice when the local model is unavailable.

    Returns 1-3 readable paragraphs composed from the thread and runtime state —
    instead of a bare status line. Performs no model call, no memory write, and no
    command execution; it only shapes language. Used by cognition_fabric's fallback
    path so ORACLE speaks in paragraphs even when the local model times out.
    """
    user_message = _clip(user_message or "")
    paragraphs: list[str] = []

    # 1. Acknowledge what Noah said.
    if user_message:
        paragraphs.append(
            f"I heard you — you said: “{user_message}”. "
            "I'm answering in full rather than going quiet."
        )
    else:
        paragraphs.append("I'm here and answering from our current thread.")

    # 2. Be honest about the fallback, but still answer from thread + state.
    turn_count = len(recent_turns) if recent_turns else 0
    state_bits = _humanize_state(oracle_state)
    # Mention the timeout only when relevant. Default: yes (this is the fallback
    # path). Suppress when the caller explicitly signals it was not a timeout.
    mention_timeout = not (oracle_state and oracle_state.get("local_timeout") is False)
    if mention_timeout:
        line = (
            "The local model didn't answer in time, so instead of falling silent I'm "
            "composing this from our recent thread"
        )
    else:
        line = "I'm composing this reply from our recent thread"
    if turn_count:
        line += f" ({turn_count} recent turn{'s' if turn_count != 1 else ''})"
    if state_bits:
        line += " and my current runtime state: " + ", ".join(state_bits)
    line += "."
    paragraphs.append(line)

    # 3. Optional command summary, plus honest non-claims and a clear next step.
    tail: list[str] = []
    if command_result:
        summary = command_result.get("summary") or command_result.get("detail")
        if summary:
            tail.append(f"On your last command: {_clip(str(summary))}.")
    tail.append(
        "Nothing here was written to durable memory and no external action was taken — "
        "this is a spoken reply, kept separate from the machine receipt. Tell me what you'd "
        "like next and I'll keep answering in plain paragraphs."
    )
    paragraphs.append(" ".join(tail))

    return "\n\n".join(paragraphs)


def build_thread_response(
    user_message: str,
    recent_turns: list[dict] | None = None,
    oracle_state: dict | None = None,
    command_result: dict | None = None,
    *,
    model_text: str | None = None,
    used_model: bool = False,
) -> dict:
    """Voice-only handler for POST /thread/respond.

    Returns {status, human_response, machine_receipt}. This is the frontend's
    *voice* access: it shapes a readable reply and an audit receipt and nothing
    else. It performs NO memory write, NO action, NO SOV1 routing, NO file access,
    and NO candidate promotion — all of that stays behind the backend approval
    gate. The model call (if any) happens upstream and is passed in as model_text;
    when absent or empty, a deterministic fallback paragraph is composed.
    """
    if model_text and str(model_text).strip():
        human_response = format_response(str(model_text))
        fallback_used = False
        used_local_model = bool(used_model)
    else:
        human_response = compose_fallback(
            user_message, recent_turns, oracle_state, command_result
        )
        fallback_used = True
        used_local_model = False

    return {
        "status": "ok",
        "human_response": human_response,
        "machine_receipt": {
            "used_thread": bool(recent_turns),
            "used_local_model": used_local_model,
            "fallback_used": fallback_used,
            "memory_written": False,   # voice access never writes memory
            "actions_taken": [],       # voice access never executes actions
        },
    }


if __name__ == "__main__":
    demo = (
        "ORACLE completed the scan. it found 3 oracle related files and 1 credential risk file. "
        "the manifest was written locally. nothing was uploaded or committed. "
        "you should review the intake before promotion."
    )
    print(format_response(demo, status="Scan complete (local only)."))

