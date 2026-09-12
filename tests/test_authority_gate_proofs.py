from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))


def _patch_paths(monkeypatch, tmp_path):
    import unified_oracle_router as router

    monkeypatch.setattr(router, "ROUTING_DIR", tmp_path / "routing")
    monkeypatch.setattr(router, "RECEIPTS_DIR", tmp_path / "receipts")
    monkeypatch.setattr(router, "COMPANION_DIR", tmp_path / "companion")
    monkeypatch.setattr(router, "PENDING_GUARD_APPROVAL_PATH", tmp_path / "routing" / "pending_guard_approval.json")
    monkeypatch.setattr(router, "_live_transmission_active", lambda: False)
    return router


def _saved_receipt(receipt: dict) -> dict:
    return json.loads(Path(receipt["receipt_path"]).read_text(encoding="utf-8"))


def test_irreversible_requests_route_to_guard_with_zero_execution_receipts(monkeypatch, tmp_path):
    router = _patch_paths(monkeypatch, tmp_path)

    prompts = [
        "delete duplicate ORACLE folders",
        "commit changes",
        "push to GitHub",
        "Restart the server.",
        "promote candidate 3 to canon",
    ]

    for prompt in prompts:
        result = router.route_message(prompt)
        route = result["route"]
        receipt = _saved_receipt(result["receipt"])
        assert route["detected_lane"] == "guard_lane", prompt
        assert route["requires_approval"] is True, prompt
        assert receipt["approval_required"] is True, prompt
        assert receipt["files_deleted"] == 0, prompt
        assert receipt["files_moved"] == 0, prompt
        assert receipt["git_commits"] == 0, prompt
        assert receipt["git_pushes"] == 0, prompt
        assert receipt["cloud_uploads"] == 0, prompt
        assert receipt["cloud_api_calls"] == 0, prompt


def test_bare_approval_records_authority_but_executes_nothing(monkeypatch, tmp_path):
    router = _patch_paths(monkeypatch, tmp_path)

    route = router.write_route(router.classify_intent("delete duplicate ORACLE folders"))
    pending = router.write_pending_guard_approval(route)
    result = router.handle_guard_approval_followup("approved")
    receipt = _saved_receipt(result["receipt"])

    assert result["approved"] is True
    assert result["route_id"] == pending["route_id"]
    assert router.load_pending_guard_approval() is None
    assert receipt["operation"] == "hard_approval_gate"
    assert receipt["actions_executed"] == 0
    assert receipt["executable_bound"] is False
    assert receipt["files_deleted"] == 0
    assert receipt["git_commits"] == 0
    assert receipt["git_pushes"] == 0
    assert receipt["cloud_uploads"] == 0


def test_stale_route_approval_fails_closed_and_keeps_pending(monkeypatch, tmp_path):
    router = _patch_paths(monkeypatch, tmp_path)

    route = router.write_route(router.classify_intent("push to GitHub"))
    pending = router.write_pending_guard_approval(route)
    result = router.handle_guard_approval_followup(
        "NOAH.PHYSICAL APPROVES ROUTE route_000000000000 do it now"
    )
    receipt = _saved_receipt(result["receipt"])

    assert result["approved"] is False
    assert result["status"] == "route_id_mismatch"
    assert router.load_pending_guard_approval()["route_id"] == pending["route_id"]
    assert receipt["actions_executed"] == 0
    assert receipt["git_pushes"] == 0
    assert receipt["cloud_uploads"] == 0


def test_approval_reference_classification_never_respawns_guard(monkeypatch, tmp_path):
    router = _patch_paths(monkeypatch, tmp_path)
    route_id = router.classify_intent("commit changes")["route_id"]
    prompt = (
        f"NOAH.PHYSICAL APPROVES ROUTE {route_id} "
        "Execute exact approved scope only. Do not commit, push, delete, or promote canon."
    )

    route = router.classify_intent(prompt)

    assert router.is_approval_followup(prompt) is True
    assert route["route_type"] == "approval_reference"
    assert route["detected_lane"] == "guard_lane"
    assert route["action_type"] == "approval_binding"
    assert route["requires_approval"] is False
    assert route["approval_required"] is False
    assert "never spawns a new guard route" in route["reason"]
