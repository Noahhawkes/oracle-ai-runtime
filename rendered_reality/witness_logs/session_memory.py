"""
rendered_reality/witness_logs/session_memory.py — session log (v0.1)

Append-only log of what happened this session, so ORACLE can answer "what have
we done" from local state instead of guessing. Lightweight events, not receipts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class SessionEvent:
    kind: str          # e.g. "ingest", "approval", "answer", "note"
    detail: str
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SessionMemory:
    def __init__(self) -> None:
        self._events: list[SessionEvent] = []

    def log(self, kind: str, detail: str) -> SessionEvent:
        ev = SessionEvent(kind=kind, detail=detail)
        self._events.append(ev)
        return ev

    def recent(self, n: int = 10) -> list[SessionEvent]:
        return self._events[-n:]

    def render(self, n: int = 10) -> str:
        if not self._events:
            return "No session events recorded yet."
        rows = [f"  {e.at[11:19]} [{e.kind}] {e.detail}" for e in self.recent(n)]
        return "SESSION LOG (recent)\n" + "\n".join(rows)

    def __len__(self) -> int:
        return len(self._events)
