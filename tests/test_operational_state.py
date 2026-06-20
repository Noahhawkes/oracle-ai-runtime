"""
Tests for ORACLE's operational world-model (core/operational_state.py).

Proves the state is reconciled live from verified sources, that declared
narrative is labeled and staleness-checked (never presented as verified fact),
and that the conversation reads from it. No LLM, no external services.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import operational_state as ops  # noqa: E402


def test_verified_git_facts_are_live():
    s = ops.build_operational_state()
    v = s["verified"]
    assert v["branch"] and v["branch"] != "UNKNOWN"
    assert v["commit"] and v["commit"] != "UNKNOWN"
    assert v["working_tree"] in ("clean", "modified")
    assert isinstance(v["recent_commits"], list)
    # freshness: observed_at is recent (within a minute)
    obs = datetime.fromisoformat(s["observed_at"])
    assert (datetime.now(timezone.utc) - obs).total_seconds() < 60


def test_declared_is_labeled_and_staleness_checked():
    s = ops.build_operational_state()
    d = s["declared"]
    # The narrative carries its source and an explicit stale flag (bool).
    assert d["source"].endswith("project_states.json")
    assert isinstance(d.get("stale"), bool)
    if "error" not in d:
        # age is a number when the timestamp parsed
        assert d.get("age_hours") is None or isinstance(d["age_hours"], (int, float))


def test_summary_separates_verified_from_declared():
    text = ops.summarize_operational_state()
    assert "VERIFIED [OPERATIONAL_STATE]" in text
    assert "DECLARED" in text
    assert "BOUNDARY:" in text
    # verified section names live runtime facts
    assert "Branch/commit:" in text
    import runtime_config
    assert f"localhost:{runtime_config.runtime_port()}" in text
    assert "localhost:7777" not in text


def test_declared_narrative_never_shown_as_verified():
    """A declared next-step must appear only under DECLARED, marked not-activated."""
    s = ops.build_operational_state()
    s["declared"]["next_recommended_step"] = "Run /pending to review the 12 proposed scope paths."
    s["declared"]["stale"] = True
    s["declared"]["age_hours"] = 86.0
    text = ops.summarize_operational_state(s)
    verified_part, _, declared_part = text.partition("DECLARED")
    assert "12 proposed scope paths" not in verified_part      # not in the verified block
    assert "12 proposed scope paths" in declared_part           # only under declared
    assert "not activated" in declared_part
    assert "STALE" in declared_part


def test_no_network_required_for_build():
    # Even if Ollama is unreachable, build must not raise and must return a dict.
    s = ops.build_operational_state()
    assert isinstance(s, dict) and "verified" in s
    assert isinstance(s["verified"]["runtime"]["ollama_models_loaded"], list)


# ── conversation reads from the fresh state ────────────────────────────────────
import oracle_server as srv  # noqa: E402


def test_active_task_question_uses_operational_state():
    r = srv._deterministic_runtime_answer("What are you working on?")
    assert r is not None
    assert r.startswith("VERIFIED [OPERATIONAL_STATE]") or r.startswith("UNAVAILABLE [OPERATIONAL_STATE]")


def test_what_changed_question_uses_operational_state():
    r = srv._deterministic_runtime_answer("What changed in your build?")
    assert r is not None
    assert "[OPERATIONAL_STATE]" in r


def test_state_reconciliation_error_is_bounded(monkeypatch):
    import operational_state
    monkeypatch.setattr(operational_state, "build_operational_state",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("recon down")))
    r = srv._deterministic_runtime_answer("what is your current state")
    assert r is not None and r.startswith("UNAVAILABLE [OPERATIONAL_STATE]")
