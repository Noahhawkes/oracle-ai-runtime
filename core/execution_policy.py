"""
execution_policy.py — Immutable request contract.

Parsed once at the routing gate. Passed to every downstream handler
including fallback and timeout paths. Never mutated after creation.

The contract survives local-model timeout, Claude fallback, and any
exception path. Fallback handlers use it to honor the original schema.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Optional


# ── Signals that force deterministic bypass (no local model, no LLM) ─────────

_BYPASS_PATTERNS: list[str] = [
    r"\bdo not use the local (model|llm|conversational model)\b",
    r"\bdo not route to claude\b",
    r"\bdo not route to codex\b",
    r"\bdeterministic( runtime)? only\b",
    r"\bself[-\s]?test\b",
    # "diagnostic" alone is a topic word, not a routing instruction. A prompt
    # asking to EXPLAIN a diagnostic must reach the synthesis lane; only an
    # explicit deterministic-diagnostic instruction bypasses the model.
    r"\bdiagnostic only\b",
    r"\bdeterministic diagnostic\b",
    r"\breturn exactly these sections\b",
    r"\bno llm\b",
    r"\bbypas[s]? (local|llm|model)\b",
    r"\bruntime[ -]only\b",
]

# Signals that forbid file writes
_NO_WRITE_PATTERNS: list[str] = [
    r"\bdo not modify files?\b",
    r"\bno file (writes?|changes?|edits?)\b",
    r"\bread[ -]only\b",
    r"\bfile_write_policy.*forbidden\b",
]

# Signals that forbid Claude routing
_NO_CLAUDE_PATTERNS: list[str] = [
    r"\bdo not (use|route to|call) claude\b",
    r"\bno claude\b",
    r"\bforbid.*claude\b",
]

# Signals that forbid Codex routing
_NO_CODEX_PATTERNS: list[str] = [
    r"\bdo not (use|route to|call) codex\b",
    r"\bno codex\b",
    r"\bforbid.*codex\b",
]

# Section header extraction for explicit schemas only:
#   Current mode:
#   [Current mode]
# Plain conversational lines like "any updates" are not schema headings.
_SECTION_RE = re.compile(
    r"^\s*(?:\[\s*([A-Za-z][A-Za-z_ ]{2,40})\s*\]|[#*-]?\s*([A-Za-z][A-Za-z_ ]{2,40})\s*:)\s*$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class ExecutionPolicy:
    """
    Immutable snapshot of what this request requires and forbids.
    frozen=True prevents any downstream mutation.
    """
    raw_text: str
    is_diagnostic: bool
    requested_sections: tuple[str, ...]
    forbidden_tools: tuple[str, ...]  # e.g. ("claude", "codex", "local_model")
    allowed_tools: tuple[str, ...]
    file_write_forbidden: bool
    routing_policy: str    # "deterministic_bypass" | "local_only" | "normal"
    model_policy: str      # "none" | "local_only" | "any"
    unknown_value_policy: str  # "UNKNOWN" always for now
    parsed_at: float = field(default_factory=time.time)

    def forbids(self, tool: str) -> bool:
        t = tool.lower()
        return any(t in f.lower() for f in self.forbidden_tools)

    def has_schema(self) -> bool:
        return len(self.requested_sections) > 0


def parse(text: str) -> ExecutionPolicy:
    """
    Parse a user message into an ExecutionPolicy.
    Cheap, deterministic, no LLM.
    """
    lower = text.lower()

    def matches_any(patterns: list[str]) -> bool:
        return any(re.search(p, lower) for p in patterns)

    is_diagnostic = matches_any(_BYPASS_PATTERNS)

    # Build forbidden tool list
    forbidden: list[str] = []
    if matches_any(_NO_CLAUDE_PATTERNS) or is_diagnostic:
        forbidden.append("claude")
    if matches_any(_NO_CODEX_PATTERNS) or is_diagnostic:
        forbidden.append("codex")
    if is_diagnostic:
        forbidden.append("local_model")

    file_write_forbidden = matches_any(_NO_WRITE_PATTERNS)

    # Extract requested section headings
    sections: list[str] = []
    for m in _SECTION_RE.finditer(text):
        candidate = (m.group(1) or m.group(2) or "").strip()
        if 3 <= len(candidate) <= 40 and candidate.lower() not in ("the", "and", "for", "with"):
            sections.append(candidate)
    sections = list(dict.fromkeys(sections))  # deduplicate preserving order

    routing_policy = "deterministic_bypass" if is_diagnostic else "normal"
    model_policy   = "none" if is_diagnostic else "any"

    return ExecutionPolicy(
        raw_text=text,
        is_diagnostic=is_diagnostic,
        requested_sections=tuple(sections),
        forbidden_tools=tuple(forbidden),
        allowed_tools=(),
        file_write_forbidden=file_write_forbidden,
        routing_policy=routing_policy,
        model_policy=model_policy,
        unknown_value_policy="UNKNOWN",
    )


# ── Deterministic runtime state reader ───────────────────────────────────────

def _read_runtime_state() -> dict:
    """
    Read current ORACLE runtime state without calling any LLM.
    Returns UNKNOWN for anything that cannot be determined.
    """
    import os
    from pathlib import Path

    ROOT = Path(__file__).parent.parent
    state: dict[str, str] = {}

    # Current mode
    try:
        from session_state import get_mode
        state["current_mode"] = get_mode()
    except Exception:
        state["current_mode"] = "UNKNOWN"

    # Pending approvals
    try:
        from approval_center import list_pending
        pending = list_pending()
        if pending:
            state["pending_approvals"] = "; ".join(
                f"{p.get('id', '?')}: {p.get('description', '?')[:60]}"
                for p in pending[:5]
            )
        else:
            state["pending_approvals"] = "none"
    except Exception:
        state["pending_approvals"] = "UNKNOWN"

    # Execution ledger (last few entries)
    try:
        from execution_receipt import get_recent
        receipts = get_recent(limit=3)
        state["execution_ledger"] = "; ".join(str(r)[:60] for r in receipts) or "empty"
    except Exception:
        state["execution_ledger"] = "UNKNOWN"

    # Learning ledger
    try:
        from learning import get_ui_hints
        hints = get_ui_hints()
        state["total_interactions"] = str(hints.get("total_interactions", "UNKNOWN"))
    except Exception:
        state["total_interactions"] = "UNKNOWN"

    # Server uptime / version
    try:
        version_file = ROOT / "VERSION"
        state["version"] = version_file.read_text(encoding="utf-8").strip() if version_file.exists() else "UNKNOWN"
    except Exception:
        state["version"] = "UNKNOWN"

    # Known context / session
    try:
        state["session_id"] = os.environ.get("ORACLE_SESSION_ID", "UNKNOWN")
    except Exception:
        state["session_id"] = "UNKNOWN"

    return state


def build_deterministic_response(policy: ExecutionPolicy) -> str:
    """
    Build a structured deterministic response honoring the requested
    sections from the policy. Never calls an LLM.
    Returns UNKNOWN for any field that cannot be read from runtime state.
    """
    state = _read_runtime_state()

    # Section → state key mapping
    section_map: dict[str, str] = {
        "current mode":          state.get("current_mode", "UNKNOWN"),
        "mode":                  state.get("current_mode", "UNKNOWN"),
        "pending":               state.get("pending_approvals", "UNKNOWN"),
        "pending approvals":     state.get("pending_approvals", "UNKNOWN"),
        "pending intents":       state.get("pending_approvals", "UNKNOWN"),
        "execution ledger":      state.get("execution_ledger", "UNKNOWN"),
        "ledger":                state.get("execution_ledger", "UNKNOWN"),
        "interactions":          state.get("total_interactions", "UNKNOWN"),
        "total interactions":    state.get("total_interactions", "UNKNOWN"),
        "version":               state.get("version", "UNKNOWN"),
        "session":               state.get("session_id", "UNKNOWN"),
        "session id":            state.get("session_id", "UNKNOWN"),
        "routing policy":        policy.routing_policy,
        "model policy":          policy.model_policy,
        "file write policy":     "FORBIDDEN" if policy.file_write_forbidden else "ALLOWED",
        "forbidden tools":       ", ".join(policy.forbidden_tools) or "none",
        "allowed tools":         ", ".join(policy.allowed_tools) or "any",
        "requested sections":    ", ".join(policy.requested_sections) or "none specified",
        "unknown value policy":  policy.unknown_value_policy,
    }

    lines: list[str] = ["[ORACLE DETERMINISTIC RESPONSE]", ""]

    if policy.requested_sections:
        mapped = [s for s in policy.requested_sections if s.lower().strip() in section_map]
        unmapped = [s for s in policy.requested_sections if s.lower().strip() not in section_map]
        if not mapped:
            # Zero coverage: none of the prompt's headings correspond to a
            # runtime state field. Echoing every heading back as UNKNOWN
            # replaces the user's question with noise — refuse the echo and
            # say which lookup failed instead (only-that-field-UNKNOWN rule).
            lines.append(
                "No requested heading maps to a runtime state field, so the "
                "prompt structure is not echoed back as UNKNOWN."
            )
            lines.append(f"failed_lookup: section_map has no source for: {', '.join(policy.requested_sections)}")
            lines.append(f"available_fields: {', '.join(sorted(set(section_map)))}")
            lines.append(
                "If you wanted diagnostic reasoning rather than a runtime field dump, "
                "re-ask without a deterministic-only marker so the synthesis lane can answer."
            )
            return "\n".join(lines)
        for section in mapped:
            key = section.lower().strip()
            lines.append(f"{section}:")
            lines.append(section_map[key])
            lines.append("")
        if unmapped:
            lines.append(f"unmapped_headings (no runtime source, reported once): {', '.join(unmapped)}")
            lines.append("")
    else:
        # No sections specified — return full state dump
        lines.append("Runtime State:")
        for k, v in state.items():
            lines.append(f"  {k}: {v}")
        lines.append("")
        lines.append("Policy:")
        lines.append(f"  routing_policy: {policy.routing_policy}")
        lines.append(f"  model_policy: {policy.model_policy}")
        lines.append(f"  file_write_forbidden: {policy.file_write_forbidden}")
        lines.append(f"  forbidden_tools: {', '.join(policy.forbidden_tools) or 'none'}")

    return "\n".join(lines)


def build_timeout_response(policy: ExecutionPolicy) -> str:
    """
    Schema-preserving fallback when the local model times out.
    Honors the requested sections; injects UNKNOWN for missing data.
    Never produces generic Companion Mode dialogue.
    """
    lines: list[str] = ["[ORACLE TIMEOUT — original schema preserved]", ""]
    lines.append("The local model did not respond in time.")
    lines.append("No LLM fallback is permitted by the active execution policy.")
    lines.append("")

    if policy.requested_sections:
        for section in policy.requested_sections:
            lines.append(f"{section}:")
            lines.append("UNKNOWN")
            lines.append("")
    else:
        lines.append("No sections were specified in the original request.")

    lines.append(f"routing_policy: {policy.routing_policy}")
    lines.append(f"model_policy: {policy.model_policy}")
    lines.append(f"forbidden_tools: {', '.join(policy.forbidden_tools) or 'none'}")
    lines.append(f"file_write_policy: {'FORBIDDEN' if policy.file_write_forbidden else 'ALLOWED'}")

    return "\n".join(lines)
