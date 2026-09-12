"""
rendered_reality/mind.py — OracleMind: memory-first responder (v0.1)

The correction made concrete: ORACLE is a local continuity mind with tools, not
a tool router pretending to be a mind.

  Memory first. Tools when needed. No fake gates. No permission theater.

respond() answers from local memory unless the message is a genuine action
(read/write a file, ingest, connect, change state, run a command, send out).
For an action she cannot perform, she does NOT ask fake permission — she says
plainly what capability is missing. Approval is requested only for an action she
can actually take that changes state.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .memory.local_memory import LocalMemory
from .memory.context_state import ContextState
from .provenance_graph.query import ProvenanceQuery


# action phrase -> required capability (first substring match wins)
_ACTION_MAP: tuple[tuple[str, str], ...] = (
    ("read file", "local_file_read"), ("read the file", "local_file_read"),
    ("open the file", "local_file_read"), ("show me the file", "local_file_read"),
    ("write file", "local_file_write"), ("create file", "local_file_write"),
    ("write to disk", "local_file_write"), ("save to disk", "local_file_write"),
    ("delete", "local_file_write"), ("rename", "local_file_write"),
    ("move file", "local_file_write"),
    ("ingest", "file_ingest"), ("import this file", "file_ingest"),
    ("load this folder", "file_ingest"),
    ("connect to", "connector"), ("sync with", "connector"),
    ("google drive", "connector"), ("upload", "connector"), ("download", "connector"),
    ("commit", "git_write"), ("git push", "git_write"), ("push to github", "git_write"),
    ("search the web", "web_access"), ("search online", "web_access"),
    ("look it up online", "web_access"), ("browse to", "web_access"),
    ("fetch the url", "web_access"),
    ("run command", "command_exec"), ("run the script", "command_exec"),
    ("execute ", "command_exec"),
    ("send email", "external_send"), ("publish", "external_send"),
    ("post to", "external_send"), ("transmit", "external_send"),
)

# Capabilities that change state and therefore warrant approval when available.
MUTATING_CAPS = frozenset({
    "local_file_write", "file_ingest", "connector", "git_write",
    "external_send", "command_exec", "canon_write",
})

DEFAULT_CAPS = frozenset({"memory_read"})  # a pure memory mind has no action tools


@dataclass
class MindResponse:
    kind: str                       # "memory" | "action" | "unsupported_action"
    text: str
    from_memory: bool
    citations: list[str] = field(default_factory=list)
    needs_capability: str | None = None
    requires_approval: bool = False


class OracleMind:
    def __init__(self, memory: LocalMemory, capabilities=None) -> None:
        self.memory = memory
        self.capabilities = set(capabilities) if capabilities is not None else set(DEFAULT_CAPS)

    # ── classification ───────────────────────────────────────────────────────
    def _detect_action(self, message: str) -> str | None:
        low = (message or "").lower()
        for phrase, cap in _ACTION_MAP:
            if phrase in low:
                return cap
        return None

    def classify(self, message: str) -> str:
        return "action" if self._detect_action(message) else "memory"

    # ── the one entry point ──────────────────────────────────────────────────
    def respond(self, message: str) -> MindResponse:
        cap = self._detect_action(message)
        if cap is None:
            return self._answer_from_memory(message)

        # It's an action. Tools when needed — but never fake permission.
        if cap not in self.capabilities:
            return MindResponse(
                kind="unsupported_action",
                text=f"I cannot do that from this runtime yet. Required missing capability: {cap}.",
                from_memory=False,
                needs_capability=cap,
            )
        mutating = cap in MUTATING_CAPS
        note = ("It changes state, so it needs your approval."
                if mutating else "Read-only; no approval needed.")
        return MindResponse(
            kind="action",
            text=f"That's an action I can take via '{cap}'. {note}",
            from_memory=False,
            requires_approval=mutating,
        )

    # ── memory answers (local only, with citations) ──────────────────────────
    def _answer_from_memory(self, message: str) -> MindResponse:
        low = (message or "").lower()

        if any(k in low for k in ("hole", "missing", "gap", "not observed")):
            hs = self.memory.holes()
            if not hs:
                return MindResponse("memory", "I'm holding no open holes in local memory.", True)
            body = "\n".join(f"  - [{rid}] {h}" for rid, h in hs[:20])
            return MindResponse("memory", "Open holes I'm holding:\n" + body, True,
                                citations=[rid for rid, _ in hs[:20]])

        if any(k in low for k in ("approv", "pending", "canon", "current state",
                                  "runtime state", "what do you hold", "status")):
            return MindResponse("memory", ContextState.from_memory(self.memory).render(), True)

        if any(k in low for k in ("who wrote", "provenance", "where did", "authored", "source of")):
            bd = ProvenanceQuery(self.memory.all()).authorship_breakdown()
            line = ", ".join(f"{k}={v}" for k, v in bd.items()) or "nothing yet"
            return MindResponse("memory", "Authorship I can account for locally: " + line, True)

        # general recall: honest summary + most relevant held records
        hits = self.memory.remember_about(message, limit=3)
        parts = [self.memory.project_summary()]
        cites: list[str] = []
        if hits:
            parts.append("\nMost relevant records I'm holding:")
            for h in hits:
                r = h.record
                parts.append(f"  - {self.memory.cite(r)}")
                snippet = (r.content or "")[:120]
                if snippet:
                    parts.append(f'      "{snippet}"')
                cites.append(r.receipt_id)
        return MindResponse("memory", "\n".join(parts), True, citations=cites)
