"""Smoke tests for the Scoped Capability Broker (core/pending_actions.py).

Proves durable pending-action tokens, real (non-placeholder) approval lines,
bare-approval-resolves-single-route, multi-route disambiguation, path
containment, risk blocks, audit receipts, and fail-closed behavior.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import pending_actions as pa  # noqa: E402
import trusted_build as tb  # noqa: E402


def _isolate(tmp_path):
    pa.PENDING_ACTIONS_PATH = tmp_path / "pending_actions.jsonl"
    pa.RUN_LOG_PATH = tmp_path / "run_log.jsonl"
    tb._STATE_FILE = tmp_path / "tb_state.json"


def test_module_smoke_runner_passes():
    assert pa.run_smoke_tests() == 0


def test_acknowledge_only_does_not_route_to_guard(tmp_path):
    _isolate(tmp_path)
    tb.set_trusted_build(True)
    assert pa.submit_action(action_type="acknowledge", intent_summary="ack")["decision"] == "auto_approved"


def test_low_risk_local_auto_when_authorized(tmp_path):
    _isolate(tmp_path)
    tb.set_trusted_build(True)
    p = str(pa.RUNTIME_ROOT / "core" / "x.py")
    assert pa.submit_action(action_type="create_code_file", intent_summary="new", paths=[p])["decision"] == "auto_approved"


def test_dangerous_actions_block(tmp_path):
    _isolate(tmp_path)
    tb.set_trusted_build(True)
    p = str(pa.RUNTIME_ROOT / "core" / "x.py")
    assert pa.submit_action(action_type="delete", intent_summary="d", paths=[p])["decision"] == "guard_pending"
    assert pa.submit_action(action_type="edit_code_file", intent_summary="e", paths=[str(pa.RUNTIME_ROOT / ".env")])["decision"] == "guard_pending"
    assert pa.submit_action(action_type="network", intent_summary="n")["decision"] == "guard_pending"
    assert pa.submit_action(action_type="git_push", intent_summary="g")["decision"] == "guard_pending"
    assert pa.submit_action(action_type="edit_code_file", intent_summary="o", paths=["C:\\Users\\noahh\\x.py"])["decision"] == "guard_pending"


def test_no_placeholder_in_approval_line(tmp_path):
    _isolate(tmp_path)
    tok = pa.create_pending_action(action_type="delete", intent_summary="rm temp", boundary="not reversible")
    assert "<exact target/action/boundary>" not in tok.approval_text_rendered
    assert tok.approval_text_rendered.startswith(f"APPROVE ROUTE {tok.route_id}:")


def test_bare_approval_resolves_single_route(tmp_path):
    _isolate(tmp_path)
    tok = pa.create_pending_action(action_type="delete", intent_summary="one", boundary="b")
    res = pa.resolve_approval("approved")
    assert res["approved"] is True and res["route_id"] == tok.route_id
    assert pa.list_pending() == []


def test_multiple_pending_require_explicit_route(tmp_path):
    _isolate(tmp_path)
    pa.create_pending_action(action_type="delete", intent_summary="a", boundary="b")
    pa.create_pending_action(action_type="move", intent_summary="c", boundary="b")
    res = pa.resolve_approval("approved")
    assert res["status"] == "needs_disambiguation"
    assert len(res["pending_route_ids"]) == 2


def test_no_pending_fails_closed(tmp_path):
    _isolate(tmp_path)
    res = pa.resolve_approval("approved")
    assert res["approved"] is False and res["status"] == "no_pending"


def test_audit_receipt_written(tmp_path):
    _isolate(tmp_path)
    tb.set_trusted_build(True)
    pa.submit_action(action_type="create_code_file", intent_summary="x", paths=[str(pa.RUNTIME_ROOT / "core" / "x.py")])
    assert pa.RUN_LOG_PATH.exists()
    assert len(pa._read_jsonl(pa.RUN_LOG_PATH)) >= 1


def test_path_containment(tmp_path):
    _isolate(tmp_path)
    assert pa.contained_path(str(pa.RUNTIME_ROOT / "core" / "x.py")) is not None
    assert pa.contained_path(str(pa.RUNTIME_ROOT / ".." / "escape.py")) is None
    assert pa.contained_path("G:\\My Drive\\x.txt") is None
