"""
core/live_context.py — ORACLE LiveContext Service

Maintains ORACLE's current operational context as a volatile, sovereign-controlled
state buffer. This is NOT durable memory. It is the live working picture of what
is happening right now.

Architecture position:
    Approved Signals -> [LiveContext] -> Candidate Meaning -> SOV1 Approval -> Memory

LiveContext:
- Is always loaded at ORACLE startup
- Reflects the current session state
- Clears volatile fields (pending_candidates) on privacy mode
- Never writes directly to oracle_memory.db
- Persists state to Memory/live_context.json between sessions (gitignored)
- Can be paused — context updates are suspended during pause

Privacy guarantee:
- Privacy mode OFF by default
- When privacy mode is ON: sensor_mode all OFF, pending_candidates cleared,
  context updates suspended
- Purge buffer: clears pending_candidates without approving them
- No camera, microphone, or keystroke data is ever stored here

Sovereignty:
- sovereign field is immutable at runtime
- memory_policy defaults to APPROVAL_REQUIRED and cannot be lowered via code
- Only Noah can change memory_policy to a less restrictive value
"""

import json
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from root import ROOT

_STATE_FILE = ROOT / "Memory" / "live_context.json"

_DEFAULT_STATE = {
    "sovereign":           "Noah Hawkes / SOV1.AI",
    "active_project":      "ORACLE.AI",
    "active_tool":         "Claude Code",
    "active_repo":         "oracle-ai-core",
    "current_task":        "",
    "sensor_mode": {
        "camera":          "OFF",
        "microphone":      "OFF",
    },
    "memory_policy":       "APPROVAL_REQUIRED",
    "pending_candidates":  [],
    "privacy_mode":        False,
    "paused":              False,
    "last_updated":        "",
}

# Fields that may never be changed via update() — only Noah can change them
_IMMUTABLE_FIELDS = {"sovereign", "memory_policy"}


class LiveContext:
    """
    Volatile operational context buffer for ORACLE.

    Load once at startup via LiveContext(). Use get() to read state,
    update() to change mutable fields, set_privacy_mode() for privacy,
    pause()/resume() to suspend context updates, purge_buffer() to
    clear pending candidates without approving them.

    State is persisted to Memory/live_context.json (gitignored).
    """

    def __init__(self):
        self._state = dict(_DEFAULT_STATE)
        self._load()
        # Always stamp last_updated on load
        self._state["last_updated"] = datetime.now().isoformat()
        self._save()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Load state from disk if it exists, merging with defaults."""
        if not _STATE_FILE.exists():
            return
        try:
            saved = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
            # Merge saved values over defaults — never override immutable fields
            for k, v in saved.items():
                if k not in _IMMUTABLE_FIELDS:
                    self._state[k] = v
        except Exception:
            pass  # corrupt file → use defaults

    def _save(self) -> None:
        """Persist current state to disk."""
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(
            json.dumps(self._state, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ── Read ──────────────────────────────────────────────────────────────────

    def get(self) -> dict:
        """Return a copy of the current state."""
        return dict(self._state)

    def show(self) -> str:
        """Return a human-readable summary of the current context state."""
        s = self._state
        privacy_label = "ON  [context updates suspended]" if s["privacy_mode"] else "OFF"
        paused_label  = "YES" if s["paused"] else "NO"
        sensor_cam    = s["sensor_mode"].get("camera", "OFF")
        sensor_mic    = s["sensor_mode"].get("microphone", "OFF")
        pending_count = len(s.get("pending_candidates", []))

        lines = [
            "",
            "--- ORACLE Live Context ---",
            f"  Sovereign       : {s['sovereign']}",
            f"  Active project  : {s['active_project']}",
            f"  Active tool     : {s['active_tool']}",
            f"  Active repo     : {s['active_repo']}",
            f"  Current task    : {s['current_task'] or '(none set)'}",
            f"  Memory policy   : {s['memory_policy']}",
            f"  Privacy mode    : {privacy_label}",
            f"  Context paused  : {paused_label}",
            f"  Camera          : {sensor_cam}",
            f"  Microphone      : {sensor_mic}",
            f"  Pending approval: {pending_count} candidate(s)",
            f"  Last updated    : {s['last_updated'][:19]}",
            "---------------------------",
            "",
        ]
        return "\n".join(lines)

    # ── Write ─────────────────────────────────────────────────────────────────

    def update(self, **kwargs) -> None:
        """
        Update mutable context fields. Raises ValueError for immutable fields.
        Does nothing if context is paused (except for pause/privacy/task fields).
        """
        passthrough = {"paused", "privacy_mode", "current_task", "pending_candidates"}
        for key, value in kwargs.items():
            if key in _IMMUTABLE_FIELDS:
                raise ValueError(
                    f"'{key}' is immutable. Only Noah can change this value."
                )
            if self._state.get("paused") and key not in passthrough:
                continue  # silently drop updates while paused
            self._state[key] = value

        self._state["last_updated"] = datetime.now().isoformat()
        self._save()

    def set_task(self, task: str) -> None:
        """Set the current active task description."""
        self._state["current_task"] = task
        self._state["last_updated"] = datetime.now().isoformat()
        self._save()

    # ── Privacy ───────────────────────────────────────────────────────────────

    def set_privacy_mode(self, on: bool) -> str:
        """
        Toggle privacy mode.

        When ON:
          - sensor_mode: camera=OFF, microphone=OFF
          - pending_candidates cleared (not approved — discarded)
          - context updates paused

        When OFF:
          - sensors remain OFF (must be explicitly enabled per connector)
          - context updates resume
        """
        self._state["privacy_mode"] = on
        if on:
            self._state["sensor_mode"] = {"camera": "OFF", "microphone": "OFF"}
            self._state["pending_candidates"] = []
            self._state["paused"] = True
            msg = "Privacy mode ON. Sensors OFF. Live buffer cleared. Context paused."
        else:
            self._state["paused"] = False
            msg = "Privacy mode OFF. Context updates resumed. Sensors remain OFF until explicitly enabled."

        self._state["last_updated"] = datetime.now().isoformat()
        self._save()
        return msg

    def pause(self) -> str:
        """Pause context updates without entering full privacy mode."""
        self._state["paused"] = True
        self._state["last_updated"] = datetime.now().isoformat()
        self._save()
        return "Context updates paused. Memory policy unchanged. Use /resume-context to resume."

    def resume(self) -> str:
        """Resume context updates."""
        self._state["paused"] = False
        self._state["last_updated"] = datetime.now().isoformat()
        self._save()
        return "Context updates resumed."

    def purge_buffer(self) -> str:
        """
        Clear all pending candidates from the live buffer without approving them.
        This does NOT affect the ApprovalGate pending store on disk.
        Use ApprovalGate.reject() to formally reject disk-persisted candidates.
        """
        count = len(self._state.get("pending_candidates", []))
        self._state["pending_candidates"] = []
        self._state["last_updated"] = datetime.now().isoformat()
        self._save()
        return f"Live buffer cleared. {count} pending candidate(s) discarded (not approved, not stored)."

    # ── Candidate tracking (volatile — not the ApprovalGate) ─────────────────

    def add_pending(self, label: str) -> None:
        """
        Track a candidate label in the live buffer (display only).
        Not the same as ApprovalGate.submit() — this is the volatile UI indicator.
        """
        if self._state.get("paused") or self._state.get("privacy_mode"):
            return
        pending = self._state.get("pending_candidates", [])
        if label not in pending:
            pending.append(label)
        self._state["pending_candidates"] = pending
        self._state["last_updated"] = datetime.now().isoformat()
        self._save()


# ── Module-level singleton ────────────────────────────────────────────────────

_instance: LiveContext | None = None


def get_live_context() -> LiveContext:
    """Return the module-level LiveContext singleton. Creates on first call."""
    global _instance
    if _instance is None:
        _instance = LiveContext()
    return _instance
