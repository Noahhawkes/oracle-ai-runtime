"""
core/working_memory.py — ORACLE L1 working memory (hot, in-RAM, bounded).

This is the fast tier of the Continuity Fabric: the small, immediate state ORACLE
holds about *right now* — active task, current project/repo, recent verified
facts, recent entities/files, pending tool tasks, current focus, runtime state.

Design rules (enforced here):
  * In-memory only. No disk, no network — this is the hot path.
  * Bounded. Rolling collections are capped; nothing grows without limit.
  * Explicit expiration. Rolling items carry a TTL and are purged on access.
  * Sourced + timestamped. Every value records who set it and when.
  * Epistemic honesty. Authoritative state values are labeled one of
    verified | reported | inferred | unknown — never blended.
  * Versioned. state_version increments only when authoritative state changes,
    so observers can cheaply detect "did anything real change?".
  * No raw surveillance. This stores structured facts/state given to it; it does
    not capture or retain raw audio/video/screen streams.
"""
from __future__ import annotations

import copy
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

VALID_STATUS = frozenset({"verified", "reported", "inferred", "unknown"})
DEFAULT_MAX_ITEMS = 50
DEFAULT_TTL_SECONDS = 1800  # 30 min for rolling items


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class StateValue:
    """An authoritative current-state value with its epistemic status."""
    value: Any
    status: str          # verified | reported | inferred | unknown
    source: str
    updated_at: str

    def as_dict(self) -> dict:
        return {"value": self.value, "status": self.status,
                "source": self.source, "updated_at": self.updated_at}


@dataclass(frozen=True)
class _Item:
    content: Any
    source: str
    at: str
    _deadline: float | None  # monotonic clock deadline, or None = no expiry

    def as_dict(self) -> dict:
        return {"content": self.content, "source": self.source, "at": self.at}


class WorkingMemory:
    def __init__(self, *, max_items: int = DEFAULT_MAX_ITEMS,
                 default_ttl: float = DEFAULT_TTL_SECONDS) -> None:
        if max_items < 1:
            raise ValueError("max_items must be >= 1")
        self._lock = threading.RLock()
        self._max_items = max_items
        self._default_ttl = default_ttl
        self._version = 0
        self._updated_at = _now_iso()
        # Authoritative singletons (active_task, current_project, repo_state,
        # current_focus, runtime_state, current_mode, ...).
        self._state: dict[str, StateValue] = {}
        # Rolling, bounded, expiring collections.
        self._recent_facts: deque[_Item] = deque(maxlen=max_items)
        self._recent_entities: deque[_Item] = deque(maxlen=max_items)
        self._recent_files: deque[_Item] = deque(maxlen=max_items)
        self._pending_tasks: deque[_Item] = deque(maxlen=max_items)
        self._conversation: deque[_Item] = deque(maxlen=max_items)

    # ── authoritative state ────────────────────────────────────────────────
    def set_state(self, key: str, value: Any, *, source: str,
                  status: str = "reported") -> int:
        """Set an authoritative current-state value. Returns the state version."""
        if status not in VALID_STATUS:
            raise ValueError(f"status must be one of {sorted(VALID_STATUS)}, got {status!r}")
        if not source:
            raise ValueError("source is required")
        with self._lock:
            prev = self._state.get(key)
            self._state[key] = StateValue(value, status, source, _now_iso())
            # Bump version only on a real change in value or epistemic status.
            if prev is None or prev.value != value or prev.status != status:
                self._version += 1
            self._updated_at = _now_iso()
            return self._version

    def get_state(self, key: str) -> StateValue | None:
        with self._lock:
            return self._state.get(key)

    # ── rolling collections ────────────────────────────────────────────────
    def _deadline(self, ttl: float | None) -> float | None:
        ttl = self._default_ttl if ttl is None else ttl
        return None if ttl <= 0 else time.monotonic() + ttl

    def _add(self, dq: deque, content: Any, source: str, ttl: float | None) -> None:
        if not source:
            raise ValueError("source is required")
        with self._lock:
            dq.append(_Item(content, source, _now_iso(), self._deadline(ttl)))
            self._updated_at = _now_iso()

    def add_fact(self, text: str, *, source: str, ttl: float | None = None) -> None:
        self._add(self._recent_facts, text, source, ttl)

    def add_entity(self, name: str, *, source: str, ttl: float | None = None) -> None:
        self._add(self._recent_entities, name, source, ttl)

    def add_file(self, path: str, *, source: str, ttl: float | None = None) -> None:
        self._add(self._recent_files, path, source, ttl)

    def add_pending_task(self, task: Any, *, source: str, ttl: float | None = None) -> None:
        self._add(self._pending_tasks, task, source, ttl)

    def add_conversation_turn(self, role: str, content: str, *, source: str = "conversation",
                              ttl: float | None = None) -> None:
        self._add(self._conversation, {"role": role, "content": content}, source, ttl)

    # ── expiration ─────────────────────────────────────────────────────────
    def _purge_expired(self) -> None:
        now = time.monotonic()
        for dq in (self._recent_facts, self._recent_entities, self._recent_files,
                   self._pending_tasks, self._conversation):
            kept = [it for it in dq if it._deadline is None or it._deadline > now]
            if len(kept) != len(dq):
                dq.clear()
                dq.extend(kept)

    # ── read ───────────────────────────────────────────────────────────────
    @property
    def version(self) -> int:
        with self._lock:
            return self._version

    def snapshot(self) -> dict[str, Any]:
        """Return an immutable deep-copied view of current working memory."""
        with self._lock:
            self._purge_expired()
            return copy.deepcopy({
                "state_version": self._version,
                "updated_at": self._updated_at,
                "state": {k: v.as_dict() for k, v in self._state.items()},
                "recent_facts": [it.as_dict() for it in self._recent_facts],
                "recent_entities": [it.as_dict() for it in self._recent_entities],
                "recent_files": [it.as_dict() for it in self._recent_files],
                "pending_tasks": [it.as_dict() for it in self._pending_tasks],
                "conversation": [it.as_dict() for it in self._conversation],
            })


# Process-wide singleton for the live runtime.
_WM: WorkingMemory | None = None
_WM_LOCK = threading.Lock()


def get_working_memory() -> WorkingMemory:
    global _WM
    if _WM is None:
        with _WM_LOCK:
            if _WM is None:
                _WM = WorkingMemory()
    return _WM


if __name__ == "__main__":
    wm = get_working_memory()
    wm.set_state("active_task", "none — idle", source="runtime", status="verified")
    wm.add_fact("FTS5 is available", source="phase0")
    import json
    print(json.dumps(wm.snapshot(), indent=2))
