"""
TARGET 2 regression tests:
  - deferred action requests ("...log that in memory") enroll as pending intent
  - a subsequent "proceed"/"yes" resolves the pending intent (no fall-through)
  - the routing fallback is mode-aware (never says "switch to Builder" in Builder)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import cognitive_kernel as ck  # noqa: E402
import oracle_server as srv  # noqa: E402


def test_detect_deferred_action_positive():
    assert ck.detect_deferred_action("we need to fix the camera, log that in memory")
    assert ck.detect_deferred_action("integrate this into doctrine")
    assert ck.detect_deferred_action("remember to wire the voice backend")
    assert ck.detect_deferred_action("save this to memory")


def test_detect_deferred_action_negative():
    assert ck.detect_deferred_action("how are you doing today") is None
    assert ck.detect_deferred_action("yes") is None
    assert ck.detect_deferred_action("what's on my screen") is None


def test_enroll_then_resolve(tmp_path, monkeypatch):
    monkeypatch.setattr(ck, "STATE_FILE", tmp_path / "kernel_state.json")

    # Turn 1: a deferred action request enrolls a pending intent.
    d1 = ck.decide_next("we need to fix your camera, log that in memory")
    assert d1.intent == ck.INTENT_CONVERSATION
    state = ck.load_kernel_state()
    assert state.get("pending_intent") is not None
    assert "camera" in state["pending_intent"]["text"].lower()

    # Turn 2: "proceed" resolves it instead of falling through.
    d2 = ck.decide_next("proceed")
    assert d2.intent == ck.INTENT_PROCEED_PENDING
    assert d2.decision == ck.KERNEL_ACT
    # Pending intent is cleared after resolution.
    assert ck.load_kernel_state().get("pending_intent") is None


def test_bare_proceed_without_pending_still_defers(tmp_path, monkeypatch):
    monkeypatch.setattr(ck, "STATE_FILE", tmp_path / "kernel_state2.json")
    d = ck.decide_next("proceed")
    assert d.intent == ck.INTENT_CONVERSATION  # nothing to resolve


def test_fallback_mode_aware_builder():
    out = srv._strip_routing_artifacts("Routing to Claude Code.", "builder")
    assert "already in builder" in out.lower()
    assert "switch to builder" not in out.lower()


def test_fallback_companion_offers_switch():
    out = srv._strip_routing_artifacts("Routing to Claude Code.", "companion")
    assert "switch to builder" in out.lower()
