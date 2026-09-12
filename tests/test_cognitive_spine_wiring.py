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

import audit_log  # noqa: E402
import cognitive_spine  # noqa: E402
import oracle_server as srv  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_duplicate_turn_guard():
    """The duplicate-turn guard is deliberately module-level, in-process
    state (see oracle_server._integrate_cognitive_turn) -- reset it between
    tests so one test's turn keys can't mask another's assertions."""
    srv._INTEGRATED_TURN_KEYS.clear()
    srv._INTEGRATED_TURN_KEYS_SET.clear()
    yield
    srv._INTEGRATED_TURN_KEYS.clear()
    srv._INTEGRATED_TURN_KEYS_SET.clear()


def test_integrate_cognitive_turn_calls_spine_with_session_and_reply(monkeypatch):
    calls = []

    def fake_integrate_chat_turn(**kwargs):
        calls.append(kwargs)
        return object(), {"transition_id": "cogxn_test"}

    monkeypatch.setattr(cognitive_spine, "integrate_chat_turn", fake_integrate_chat_turn)
    monkeypatch.setattr(srv, "_session_id", 42)

    srv._integrate_cognitive_turn("What are we building?", "The Cognitive Spine.")

    assert len(calls) == 1
    assert calls[0]["session_id"] == "42"
    assert calls[0]["user_text"] == "What are we building?"
    assert calls[0]["reply_text"] == "The Cognitive Spine."


def test_integrate_cognitive_turn_resolves_model_id_when_not_supplied(monkeypatch):
    calls = []

    def fake_integrate_chat_turn(**kwargs):
        calls.append(kwargs)
        return object(), {}

    monkeypatch.setattr(cognitive_spine, "integrate_chat_turn", fake_integrate_chat_turn)
    monkeypatch.setattr(srv, "_session_id", 1)

    import llm
    monkeypatch.setattr(llm, "get_model", lambda *a, **k: "qwen2.5:7b-test")

    srv._integrate_cognitive_turn("hello", "hi there")

    assert calls[0]["model_id"] == "qwen2.5:7b-test"


def test_integrate_cognitive_turn_never_raises_when_spine_fails(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("state store unavailable")

    monkeypatch.setattr(cognitive_spine, "integrate_chat_turn", boom)
    monkeypatch.setattr(srv, "_session_id", 1)
    # Failure handling now audit-logs (see the dedicated test below) --
    # stub it here too so this test can't write to the real Logs/ dir.
    monkeypatch.setattr(audit_log, "log", lambda *a, **k: None)

    # must not raise -- this call sits on the hot chat path and is
    # explicitly best-effort, matching every other grounding call nearby.
    srv._integrate_cognitive_turn("hello", "hi there")


def test_integrate_cognitive_turn_logs_failure_instead_of_swallowing_silently(monkeypatch):
    """Replaces the old bare `except Exception: pass`. A spine failure must
    still not raise into the chat path, but it must no longer be invisible:
    it has to reach the same audit log every other subsystem (HANDS,
    DAEMON, ...) uses, tagged so it's greppable, with no raw traceback."""
    logged = []

    def boom(**kwargs):
        raise RuntimeError("state store unavailable")

    def fake_log(event_type, content, approved=None):
        logged.append((event_type, content))

    monkeypatch.setattr(cognitive_spine, "integrate_chat_turn", boom)
    monkeypatch.setattr(audit_log, "log", fake_log)
    monkeypatch.setattr(srv, "_session_id", 7)

    srv._integrate_cognitive_turn("hello", "hi there")

    assert len(logged) == 1
    event_type, content = logged[0]
    assert event_type == "COGNITIVE_SPINE"
    assert "integration_failed" in content
    assert "RuntimeError" in content
    # no raw multi-line traceback dumped into the log line
    assert "Traceback" not in content


def test_integrate_cognitive_turn_duplicate_call_creates_only_one_transition(monkeypatch):
    """One response must not be able to create two state transitions. Calling
    _integrate_cognitive_turn twice with the same session/user_text/reply_text
    (e.g. a future bug that calls it from two branches for one turn, or an
    SSE-reconnect replay) must only advance the spine once."""
    calls = []

    def fake_integrate_chat_turn(**kwargs):
        calls.append(kwargs)
        return object(), {"transition_id": f"cogxn_{len(calls)}"}

    monkeypatch.setattr(cognitive_spine, "integrate_chat_turn", fake_integrate_chat_turn)
    monkeypatch.setattr(srv, "_session_id", 99)

    srv._integrate_cognitive_turn("same question", "same answer")
    srv._integrate_cognitive_turn("same question", "same answer")

    assert len(calls) == 1


def test_integrate_cognitive_turn_different_turns_are_not_deduplicated(monkeypatch):
    """The duplicate guard must key on content, not just session -- two
    genuinely different turns in the same session must both integrate."""
    calls = []

    def fake_integrate_chat_turn(**kwargs):
        calls.append(kwargs)
        return object(), {"transition_id": f"cogxn_{len(calls)}"}

    monkeypatch.setattr(cognitive_spine, "integrate_chat_turn", fake_integrate_chat_turn)
    monkeypatch.setattr(srv, "_session_id", 99)

    srv._integrate_cognitive_turn("first question", "first answer")
    srv._integrate_cognitive_turn("second question", "second answer")

    assert len(calls) == 2
