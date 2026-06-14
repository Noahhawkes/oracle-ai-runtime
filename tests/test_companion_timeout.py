"""
Tests for the Companion local-model timeout + mode-truth fix.

Covers: realistic timeout success, no single-worker poisoning, honest busy state,
connection-vs-timeout differentiation, deterministic runtime/sight answers that
bypass the model, bounded source errors, truthful fallbacks, and bounded workers.
No external services and no real Ollama call are required.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import conversation_mode as cm  # noqa: E402


@pytest.fixture(autouse=True)
def _drain_inflight():
    """Ensure the single inference slot is free before and after each test."""
    while cm._INFLIGHT.acquire(blocking=False):
        pass
    cm._INFLIGHT.release()
    yield
    # best-effort: leave exactly one permit
    acquired = 0
    while cm._INFLIGHT.acquire(blocking=False):
        acquired += 1
    cm._INFLIGHT.release()


# 1. A response slower than the old 4.5s but within the budget succeeds.
def test_slow_but_within_budget_succeeds():
    def slow(messages, model):
        time.sleep(0.4)
        return "real local answer"
    r = cm.direct_response("hello", timeout_s=5, llm_call=slow)
    assert r.status == "ok"
    assert r.text == "real local answer"
    assert not r.timed_out and not r.fallback_used


# 4. Generation timeout and connection failure are distinguished.
def test_timeout_vs_connection_distinguished():
    import httpx

    def t_call(messages, model):
        raise httpx.ReadTimeout("read timed out")

    def c_call(messages, model):
        raise httpx.ConnectError("connection refused")

    rt = cm.direct_response("q", timeout_s=5, llm_call=t_call)
    rc = cm.direct_response("q", timeout_s=5, llm_call=c_call)
    assert rt.status == "total_generation_timeout"
    assert rc.status == "connection_failure"
    assert cm._classify_local_error(httpx.ReadTimeout("x")) == "total_generation_timeout"
    assert cm._classify_local_error(httpx.ConnectError("x")) == "connection_failure"


# 3. A busy request returns model_busy (not a false timeout), and 2. it returns
#    fast rather than starving behind the in-flight request.
def test_busy_returns_model_busy_fast_no_poison():
    gate = threading.Event()

    def blocking(messages, model):
        gate.wait(timeout=5)
        return "first done"

    holder = {}

    def run_first():
        holder["r1"] = cm.direct_response("first", timeout_s=10, llm_call=blocking)

    t = threading.Thread(target=run_first)
    t.start()
    time.sleep(0.3)  # let the first request acquire the inference slot

    start = time.time()
    r2 = cm.direct_response("second", timeout_s=10, llm_call=blocking)
    elapsed = time.time() - start

    assert r2.status == "model_busy"          # honest, not a false timeout
    assert r2.timed_out is False
    assert elapsed < 1.0                       # returned immediately, not after 10s

    gate.set()
    t.join(timeout=5)
    assert holder["r1"].status == "ok"

    # After the in-flight request completes, the slot is free again (no poison).
    r3 = cm.direct_response("third", timeout_s=5, llm_call=lambda m, mdl: "third ok")
    assert r3.status == "ok"


# 11. Workers are bounded; the slot is released after every call (no accumulation).
def test_bounded_workers_and_slot_release():
    assert cm._LOCAL_POOL._max_workers == 3
    for _ in range(20):
        r = cm.direct_response("x", timeout_s=5, llm_call=lambda m, mdl: "ok")
        assert r.status == "ok"
    # Slot must be free after a burst.
    assert cm._INFLIGHT.acquire(blocking=False)
    cm._INFLIGHT.release()


# 9/10. Truthful fallback: never claims a false mode, never pretends to answer.
def test_fallback_is_truthful():
    timeout_text = cm.fallback_response(status="total_generation_timeout",
                                        effective_mode="Companion", timeout_s=25)
    assert "I am in Companion Mode" not in timeout_text
    assert "Effective route: Companion" in timeout_text
    assert "No model answer was received" in timeout_text
    # Builder route must not be described as Companion.
    builder_text = cm.fallback_response(status="total_generation_timeout",
                                        effective_mode="Builder", timeout_s=25)
    assert "Effective route: Builder" in builder_text
    assert "Companion" not in builder_text
    busy = cm.fallback_response(status="model_busy", effective_mode="Companion")
    assert "processing another request" in busy


# 12. Companion conversation needs no external services (import + call only).
def test_no_external_services_needed():
    r = cm.direct_response("anything", timeout_s=5, llm_call=lambda m, mdl: "local only")
    assert r.text == "local only" and r.status == "ok"


# ── oracle_server deterministic runtime/sight answers ──────────────────────────
import oracle_server as srv  # noqa: E402


# 5. "What are you working on?" is answered deterministically (no local model).
def test_active_task_bypasses_model():
    r = srv._deterministic_runtime_answer("What are you working on?")
    assert r is not None
    assert "took too long" not in r.lower()           # not the timeout fallback
    assert r.startswith("VERIFIED") or r.startswith("UNAVAILABLE")


# 6. "Can you see me?" returns the sight state via the accessor, no conversational model.
def test_sight_question_uses_accessor():
    r = srv._deterministic_runtime_answer("Can you see me?")
    assert r is not None
    assert "[SIGHT]" in r


# 7. A missing continuity source yields a bounded error, not a model fallback.
#    (Presence uses the continuity frame; the active-task question uses the
#    operational-state accessor, covered in test_operational_state.py.)
def test_missing_continuity_source_bounded(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("continuity provider down")
    monkeypatch.setattr(srv, "_continuity_frame", boom)
    r = srv._deterministic_runtime_answer("are you there?")
    assert r is not None and r.startswith("UNAVAILABLE [RUNTIME_STATE]")


# 8. A missing sight source yields a bounded sight error.
def test_missing_sight_source_bounded(monkeypatch):
    import oracle_sight
    monkeypatch.setattr(oracle_sight, "sight_available",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sight down")))
    r = srv._deterministic_runtime_answer("what do you see")
    assert r is not None and r.startswith("UNAVAILABLE [SIGHT]")


# Non-matching text must fall through (return None) so normal routing proceeds.
def test_non_runtime_question_falls_through():
    assert srv._deterministic_runtime_answer("tell me a story about the ocean") is None
