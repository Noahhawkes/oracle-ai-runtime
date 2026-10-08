from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "core"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import reachability as rb  # noqa: E402
import self_state as ss  # noqa: E402


def _req(broker, **kw):
    base = dict(need_type="AUTHORITY_NEEDED", summary="decision needed",
                why="requires Noah authority", channel="github")
    base.update(kw)
    return broker.request_contact(**base)


def test_github_mock_send_stores_receipt(tmp_path):
    broker = rb.ReachabilityBroker(store_dir=tmp_path)
    res = _req(broker)
    assert res["status"] == "sent"
    assert res["delivery"]["delivery_status"] == "delivered_mock"
    assert len(broker.list_open()) == 1
    rec = broker._records[res["contact_id"]]
    assert rec["receipt_ref"] is not None
    assert rec["send_status"] == "sent"


def test_email_channel_is_staged_mock(tmp_path):
    broker = rb.ReachabilityBroker(store_dir=tmp_path)
    res = _req(broker, channel="email")
    assert res["status"] == "sent"
    assert res["delivery"]["delivery_status"] == "staged_mock"


def test_unsupported_channel_returns_unavailable(tmp_path):
    broker = rb.ReachabilityBroker(store_dir=tmp_path)
    res = _req(broker, channel="carrier_pigeon")
    assert res["status"] == "unavailable"


def test_delivery_receipt_persisted_across_reload(tmp_path):
    broker = rb.ReachabilityBroker(store_dir=tmp_path)
    res = _req(broker)
    cid = res["contact_id"]
    broker2 = rb.ReachabilityBroker(store_dir=tmp_path)
    assert cid in broker2._records
    assert broker2._records[cid]["receipt_ref"] is not None


def test_failed_send_does_not_claim_success(tmp_path):
    broker = rb.ReachabilityBroker(store_dir=tmp_path)
    broker.register_channel("github", rb.GitHubAttentionChannel(
        sender=lambda body: {"ok": False, "error": "network down"}))
    res = _req(broker)
    assert res["status"] == "failed"
    assert res["delivery"]["delivery_status"] == "failed"
    assert broker._records[res["contact_id"]]["send_status"] == "failed"


def test_duplicate_need_is_suppressed(tmp_path):
    broker = rb.ReachabilityBroker(store_dir=tmp_path)
    first = _req(broker, summary="same condition")
    second = _req(broker, summary="same condition")
    assert first["status"] == "sent"
    assert second["status"] == "suppressed_duplicate"
    assert second["contact_id"] == first["contact_id"]
    assert len(broker.list_open()) == 1


def test_resolved_need_allows_new_contact(tmp_path):
    broker = rb.ReachabilityBroker(store_dir=tmp_path)
    first = _req(broker, summary="same condition")
    assert broker.resolve(first["contact_id"], resolution_event="noah_fixed_it") is True
    third = _req(broker, summary="same condition")
    assert third["status"] == "sent"       # resolving cleared the open attention
    assert third["contact_id"] != first["contact_id"]


def test_public_channel_refuses_secret(tmp_path):
    broker = rb.ReachabilityBroker(store_dir=tmp_path)
    res = _req(broker, summary="token is sk-ant-SECRETSECRETSECRET123 do not send")
    assert res["status"] == "blocked_secret"
    # nothing was delivered
    assert "delivery" not in res


def test_end_to_end_self_state_need_reach_demo(tmp_path):
    # 1. ORACLE observes an unresolved P0 provenance issue requiring Noah authority.
    state = ss.build_self_state({
        "active_goal": "resolve #16 cross-human provenance",
        "pending_approvals": ["merge/authority decision on provenance sites B and C"],
        "runtime_status": "online",
    })
    assert state["classification"] == "NOAH_REQUIRED"

    # 2-3. She checks and determines she cannot self-resolve without Noah authority.
    need = ss.evaluate_need(state, {"authority_required": True, "severity": 90})
    assert need.need_type == "AUTHORITY_NEEDED"
    assert need.requires_noah is True

    # 4-7. Reachability broker selects the approved channel, mock-contacts, receipts.
    broker = rb.ReachabilityBroker(store_dir=tmp_path)
    res = broker.request_contact(
        need_type=need.need_type,
        summary="Unresolved P0 provenance (#16) needs a Noah.Physical decision",
        why="sites B and C require authority; ORACLE cannot self-approve",
        urgency=need.tier,
        tried="fixed site A (commit c29671e), tests green",
        recommended_action=need.recommended_action,
        evidence_refs=["issue-16", "commit-c29671e"],
        need_state_id=state["self_state_id"],
        channel="github",
    )
    assert res["status"] == "sent"
    contact_id = res["contact_id"]
    assert broker._records[contact_id]["receipt_ref"] is not None

    # 8. SelfState can now record that Noah was contacted (next observation).
    state2 = ss.build_self_state({
        "active_goal": "resolve #16 cross-human provenance",
        "pending_approvals": ["merge/authority decision on provenance sites B and C"],
        "runtime_status": "online",
        "last_noah_interaction": f"contact {contact_id} (attention queue)",
    }, previous=state)
    assert ss.has_meaningful_change(state, state2) is True

    # 9. A duplicate cycle does not contact him again.
    dup = broker.request_contact(
        need_type=need.need_type,
        summary="Unresolved P0 provenance (#16) needs a Noah.Physical decision",
        why="sites B and C require authority; ORACLE cannot self-approve",
        channel="github",
    )
    assert dup["status"] == "suppressed_duplicate"

    # 10. Noah acknowledgement + resolution clears the need.
    assert broker.acknowledge(contact_id) is True
    assert broker.resolve(contact_id, resolution_event="noah_decided") is True
    assert broker.list_open() == []
