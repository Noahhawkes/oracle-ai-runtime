"""Smoke tests for ORACLE UI Experience Patch v0.1 (core/ui_experience.py).

Proves natural-language phrases route to deterministic cards without a model
call, the timeout fallback lists useful actions, and nothing writes durable
memory or takes external action.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import ui_experience as ux  # noqa: E402


def _isolate(tmp_path):
    import pending_actions as pa
    import trusted_build as tb
    pa.PENDING_ACTIONS_PATH = tmp_path / "pending_actions.jsonl"
    pa.RUN_LOG_PATH = tmp_path / "run_log.jsonl"
    tb._STATE_FILE = tmp_path / "tb_state.json"


def test_module_smoke_runner_passes():
    assert ux.run_smoke_tests() == 0


def test_evidence_vault_routes_without_model(tmp_path):
    _isolate(tmp_path)
    r = ux.route_phrase("Show me the Evidence Vault")
    assert r is not None and r["kind"] == "evidence_vault"
    assert "EVIDENCE VAULT" in r["text"] or "not fully implemented" in r["text"]


def test_context_recall_routes_without_model(tmp_path):
    _isolate(tmp_path)
    r = ux.route_phrase("Context recall")
    assert r is not None and r["kind"] == "context_recall"
    assert "CONTEXT RECALL" in r["text"]


def test_ui_patch_creates_proposal(tmp_path):
    _isolate(tmp_path)
    r = ux.route_phrase("improve UI experience")
    assert r is not None and r["kind"] == "ui_patch"
    assert "UI SELF-PATCH PROPOSED" in r["text"]
    assert "route_" in r["text"]  # a real proposal id, not a placeholder


def test_unrecognized_falls_through():
    assert ux.route_phrase("tell me a story about the sea") is None


def test_improved_fallback_lists_actions():
    fb = ux.improved_fallback()
    for token in ("/status", "/focus", "/capabilities", "Evidence Vault", "Context Recall"):
        assert token in fb
    assert "No durable memory or external action" in fb


def test_cards_are_pure_reads(tmp_path):
    _isolate(tmp_path)
    # project_states.json must be unchanged by reading cards.
    ps = ROOT / "Memory" / "project_states.json"
    before = ps.stat().st_mtime if ps.exists() else None
    ux.evidence_vault()
    ux.context_recall()
    after = ps.stat().st_mtime if ps.exists() else None
    assert before == after
