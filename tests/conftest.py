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
def isolate_action_candidate_store(tmp_path, monkeypatch):
    """Redirect the action-candidate store to a per-test temp file.

    Without this, any test that runs a self-prompt cycle submits a real
    candidate into Memory/action_candidates.json and it surfaces in Noah's
    live approval queue. Tests that need their own path simply monkeypatch
    CANDIDATES_FILE again -- this only sets a safe default.
    """
    try:
        import action_candidates as _ac
    except Exception:
        return
    monkeypatch.setattr(
        _ac, "CANDIDATES_FILE", tmp_path / "action_candidates.json", raising=False
    )
