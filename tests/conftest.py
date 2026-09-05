"""Shared test guards.

Noah's durable memory is not a test fixture. Tests exercise real code paths --
including the self-prompt cycle, which now produces action candidates -- and
those paths must never write into the live runtime's memory store.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for _p in (ROOT, CORE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


@pytest.fixture(autouse=True)
def isolate_candidate_stores(tmp_path, monkeypatch):
    """Redirect every candidate store to per-test temp files.

    Without this, any test that runs a self-prompt cycle or ingests a prompt
    writes a real candidate into Memory/ and it surfaces in Noah's live
    approval queue. Tests that need their own path simply monkeypatch the
    path again; this only sets a safe default.

    Every new candidate producer must be added here. The failure is silent:
    tests pass while quietly polluting durable memory.
    """
    try:
        import action_candidates as _ac
        monkeypatch.setattr(
            _ac, "CANDIDATES_FILE", tmp_path / "action_candidates.json", raising=False
        )
    except Exception:
        pass

    try:
        import prompt_learning_loop as _pll
        monkeypatch.setattr(
            _pll, "CANDIDATES_FILE", tmp_path / "prompt_learning_candidates.json",
            raising=False,
        )
        monkeypatch.setattr(
            _pll, "EVENTS_FILE", tmp_path / "prompt_learning_events.jsonl",
            raising=False,
        )
    except Exception:
        pass
