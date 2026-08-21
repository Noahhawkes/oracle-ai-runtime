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


def test_operator_bridge_uses_api_helper_and_auto_primes():
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")

    assert "function rrBridgeFetchJson(path)" in html
    assert "apiUrl(path)" in html
    assert "fetch(url,{cache:'no-store'})" in html
    assert "rrBridgeFetchJson('/api/status')" in html
    assert "rrBridgeFetchJson('/api/capabilities'" in html
    assert "function rrBridgePrime()" in html
    assert "addEventListener('DOMContentLoaded',rrBridgePrime)" in html


def test_ui_exposes_self_prompt_writer_controls():
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")

    assert 'id="self-prompt-btn"' in html
    assert "function refreshSelfPromptStatus()" in html
    assert "function toggleSelfPromptMode()" in html
    assert "api/self-prompt/status" in html
    assert "api/self-prompt/enable" in html
    assert "api/self-prompt/disable" in html


def test_daily_driver_ui_collapses_advanced_controls():
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")

    assert 'id="ui-advanced-btn"' in html
    assert 'id="advanced-controls"' in html
    assert "function toggleAdvancedControls()" in html
    assert "oracle_ui_advanced_open" in html
    assert "body:not(.ui-advanced-open) .route-receipt { display: none; }" in html
    assert 'class="pr-item pr-extra"' in html
    assert 'durability-chip pending dur-extra' in html
    assert 'class="chip chip-extra"' in html
    assert "body.sidebar-collapsed #ce-bar" in html
    assert "body.sidebar-collapsed #af-fab" in html
    assert "body.sidebar-collapsed #af-panel" in html
    assert "function initSidebarState()" in html
    assert "window.matchMedia('(max-width: 760px)')" in html


def test_daily_driver_keeps_core_controls_visible():
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    topbar = html.split('<div id="topbar">', 1)[1].split('<div id="advanced-controls"', 1)[0]
    advanced = html.split('<div id="advanced-controls"', 1)[1].split('<!-- Camera / vision panel', 1)[0]

    for token in ('id="mode-indicator"', 'id="safety-indicator"', 'id="ai-lockbox-btn"', 'id="self-prompt-btn"'):
        assert token in topbar
    for token in ('id="read-access-btn"', 'id="self-notes-btn"', 'id="tuneup-btn"', 'id="human-state-btn"', 'id="operator-dashboard-btn"', 'id="preferences-btn"', 'id="sourcemap-btn"'):
        assert token in advanced
        assert token not in topbar


def test_chat_send_has_visible_timeout_recovery():
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")

    assert "const CHAT_REQUEST_TIMEOUT_MS = 45000;" in html
    assert "new AbortController()" in html
    assert "signal: chatController.signal" in html
    assert "ORACLE backend did not answer /chat" in html
    assert "setDurabilityChip('dur-save-state', 'chat blocked', 'warn')" in html
    assert "clearTimeout(chatTimeout)" in html


def test_ui_has_confirmation_gated_sandbox_edit_flow():
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")

    assert 'id="sandbox-edit-btn"' in html
    assert "function parseSandboxEditCommand(text)" in html
    assert "sandboxApiJson('/api/sandbox/read'" in html
    assert "sandboxApiJson('/api/sandbox/edit'" in html
    assert "expected_sha256: initialRead.sha256" in html
    assert "Confirm sandbox write" in html
    assert "Awaiting explicit confirmation; no mutation has occurred." in html
    assert "post-write re-read did not match the confirmed proposal" in html
    assert "Hard boundary: C:\\\\Oracle\\\\ORACLE.AI-runtime\\\\sandbox\\\\ only." in html


def test_cards_are_pure_reads(tmp_path):
    _isolate(tmp_path)
    # project_states.json must be unchanged by reading cards.
    ps = ROOT / "Memory" / "project_states.json"
    before = ps.stat().st_mtime if ps.exists() else None
    ux.evidence_vault()
    ux.context_recall()
    after = ps.stat().st_mtime if ps.exists() else None
    assert before == after
