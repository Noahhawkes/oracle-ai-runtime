"""
core/context_commands.py — ORACLE Sovereign Context Command Functions

Clean importable interface for all LiveContext operations.
These are the 49% functions — ORACLE renders and suggests.
The 51% belongs to Noah: approve, reject, correct, revoke.

Used by oracle.py slash commands and any future UI layer (Overlay, API).

Human Sovereignty Rule:
    Candidate meaning may be generated automatically.
    Durable memory requires SOV1 / Noah approval.
    No function here writes directly to oracle_memory.db.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from live_context import LiveContext


def show_current_context(ctx: "LiveContext") -> dict:
    """Return the current live context state as a dict."""
    return ctx.get()


def show_context_formatted(ctx: "LiveContext") -> str:
    """Return a human-readable formatted context display."""
    return ctx.show()


def privacy_mode(ctx: "LiveContext", enabled: bool = True) -> str:
    """
    Toggle privacy mode.
    ON  — clears live buffer, sets all sensors OFF, pauses context updates.
    OFF — resumes context updates; sensors remain OFF until explicitly enabled.
    """
    return ctx.set_privacy_mode(enabled)


def pause_context(ctx: "LiveContext") -> str:
    """Pause context updates without entering full privacy mode."""
    return ctx.pause()


def resume_context(ctx: "LiveContext") -> str:
    """Resume context updates after pause."""
    return ctx.resume()


def stop_listening(ctx: "LiveContext") -> str:
    """
    Set microphone sensor to OFF.
    Sensors are OFF by default — this is a hard reset if a connector
    has enabled the microphone.
    """
    state = ctx.get()
    sensor = dict(state.get("sensor_mode", {}))
    sensor["microphone"] = "OFF"
    ctx.update(sensor_mode=sensor)
    return "Microphone: OFF. No audio capture active."


def stop_watching(ctx: "LiveContext") -> str:
    """
    Set camera sensor to OFF.
    Sensors are OFF by default — this is a hard reset if a connector
    has enabled the camera.
    """
    state = ctx.get()
    sensor = dict(state.get("sensor_mode", {}))
    sensor["camera"] = "OFF"
    ctx.update(sensor_mode=sensor)
    return "Camera: OFF. No visual capture active."


def purge_live_buffer(ctx: "LiveContext") -> str:
    """
    Clear all pending candidates from the live volatile buffer.
    Does NOT affect the ApprovalGate disk store.
    Discards without approving — nothing reaches memory.
    """
    return ctx.purge_buffer()


def show_pending_candidates(ctx: "LiveContext") -> list:
    """
    Return the list of pending candidate labels in the live buffer.
    For full ApprovalGate disk candidates, use ApprovalGate.list_pending().
    """
    return ctx.get().get("pending_candidates", [])


def show_pending_gate() -> list:
    """
    Return all candidates in the ApprovalGate disk store awaiting Noah's decision.
    These are structured CandidateEvent dicts with full metadata.

    Human Sovereignty Rule enforced here:
        This function only reads. No write occurs.
        Writes require ApprovalGate.approve() or .correct() — explicit human action.
    """
    from integration_gate import ApprovalGate
    return ApprovalGate().list_pending()


def set_active_task(ctx: "LiveContext", task: str) -> str:
    """Update the current_task field in live context."""
    ctx.set_task(task)
    return f"Active task set: {task}"
