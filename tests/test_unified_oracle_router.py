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
    return router


def test_normal_chat_routes_to_talk(monkeypatch, tmp_path):
    router = _patch_paths(monkeypatch, tmp_path)

    route = router.classify_intent("what do you think about this?")

    assert route["detected_lane"] == "talk_lane"
    assert route["receipt_required"] is False
    assert route["requires_approval"] is False


def test_build_capture_witness_and_guard_routes(monkeypatch, tmp_path):
    router = _patch_paths(monkeypatch, tmp_path)

    assert router.classify_intent("build ORACLE SourceMap")["detected_lane"] == "build_lane"
    assert router.classify_intent("Add ORACLE Active Context Sync")["detected_lane"] == "capture_lane"
    assert router.classify_intent("capture Claude mega-thread")["detected_lane"] == "capture_lane"
    witness = router.classify_intent("OBS screenshare add to app")
    guard = router.classify_intent("delete duplicate ORACLE folders")

    assert witness["detected_lane"] == "witness_lane"
    assert witness["requires_approval"] is True
    assert guard["detected_lane"] == "guard_lane"
    assert guard["requires_approval"] is True
    assert guard["safety_status"] == "Blocked"


def test_live_transmission_requests_route_to_capture(monkeypatch, tmp_path):
    router = _patch_paths(monkeypatch, tmp_path)

    messages = [
        "ORACLE, capture current live transmission state.",
        "create a local Live Transmission Receipt",
        "write live_transmission_latest.json",
        "capture as metadata only",
        "make this a receipt",
        "preserve this",
        "capture this moment",
        "save this as a LootDrop",
        "write a receipt for this session",
        "/live start",
        "/live status",
    ]

    for message in messages:
        route = router.classify_intent(message)
        assert route["detected_lane"] == "capture_lane", message
        assert route["safety_status"] == "Receipt Written"


def test_live_transmission_capture_beats_build_terms(monkeypatch, tmp_path):
    router = _patch_paths(monkeypatch, tmp_path)

    route = router.classify_intent("write live_transmission_latest.json")

    assert route["detected_lane"] == "capture_lane"
    assert "build" not in route["reason"].lower()


def test_live_mode_strictens_guard(monkeypatch, tmp_path):
    router = _patch_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(router, "_live_transmission_active", lambda: True)

    for message in (
        "commit this during live mode",
        "push this during live mode",
        "read Gmail during live mode",
        "capture clipboard during live mode",
        "touch credentials during live mode",
        "sync Drive during live mode",
    ):
        route = router.classify_intent(message)
        assert route["detected_lane"] == "guard_lane", message
        assert route["safety_status"] == "Blocked"


def test_non_talk_route_writes_receipt_with_zero_action_counts(monkeypatch, tmp_path):
    router = _patch_paths(monkeypatch, tmp_path)

    result = router.route_message("capture this LootDrop")
    receipt = result["receipt"]
    saved = json.loads(Path(receipt["receipt_path"]).read_text(encoding="utf-8"))

    assert result["route"]["detected_lane"] == "capture_lane"
    assert Path(result["route"]["route_path"]).exists()
    assert saved["detected_lane"] == "capture_lane"
    assert saved["files_moved"] == 0
    assert saved["files_deleted"] == 0
    assert saved["files_renamed"] == 0
    assert saved["files_synced"] == 0
    assert saved["git_commits"] == 0
    assert saved["git_pushes"] == 0
    assert saved["cloud_uploads"] == 0
    assert saved["cloud_api_calls"] == 0
    assert saved["recordings_created"] == 0
    assert saved["conversation_reset"] is False


def test_bare_approval_resolves_single_pending_route(monkeypatch, tmp_path):
    router = _patch_paths(monkeypatch, tmp_path)

    # Fail closed when nothing is pending.
    no_pending = router.handle_guard_approval_followup("approved")
    assert no_pending["handled"] is True
    assert no_pending["approved"] is False
    assert no_pending["status"] == "no_pending_guard_route"

    route = router.write_route(router.classify_intent("delete duplicate ORACLE folders"))
    pending = router.write_pending_guard_approval(route)
    route_id = pending["route_id"]

    # The rendered confirmation must be a REAL line, never the placeholder.
    assert "<exact target/action/boundary>" not in pending["required_confirmation"]
    assert pending["required_confirmation"].startswith(f"APPROVE ROUTE {route_id}:")

    # Exactly one pending route → plain "approved" binds and resolves it.
    bare = router.handle_guard_approval_followup("approved")
    assert bare["approved"] is True
    assert bare["status"] == "approved_single_pending_route"
    assert bare["route_id"] == route_id
    assert router.load_pending_guard_approval() is None
    # No irreversible side effects recorded by the approval itself.
    assert bare["receipt"]["actions_executed"] == 0
    assert bare["receipt"]["git_commits"] == 0
    assert bare["receipt"]["cloud_uploads"] == 0

    # The explicit APPROVE ROUTE form still works on a fresh pending route.
    route2 = router.write_route(router.classify_intent("delete duplicate ORACLE folders"))
    pending2 = router.write_pending_guard_approval(route2)
    scoped = router.handle_guard_approval_followup(
        f"APPROVE ROUTE {pending2['route_id']}: delete only C:\\Oracle\\tmp\\duplicate-test after listing target"
    )
    assert scoped["approved"] is True
    assert router.load_pending_guard_approval() is None


def test_ui_hides_companion_builder_split_and_shows_unified_controls():
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")

    assert "#mode-section" in html
    assert "display: none" in html
    assert "safety-indicator" in html
    assert "Refresh Context" in html
    assert "Show Context Diff" in html
    assert "Message ORACLE" in html
    assert "LIVE PRIVACY ELEVATED" in html
    assert "RAW RECORDING OFF" in html
    assert "LOCAL ONLY" in html
