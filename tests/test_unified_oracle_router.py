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


def test_ui_hides_companion_builder_split_and_shows_unified_controls():
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")

    assert "#mode-section" in html
    assert "display: none" in html
    assert "safety-indicator" in html
    assert "Refresh Context" in html
    assert "Show Context Diff" in html
    assert "Message ORACLE" in html
