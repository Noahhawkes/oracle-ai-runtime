from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import cognition_fabric as cf  # noqa: E402
import unified_oracle_router as router  # noqa: E402


def _boot(mode: str = "offline_no_model") -> dict:
    return {
        "cognition_mode": mode,
        "verified_model_name": "qwen-test" if mode == "local_only" else None,
        "verified_local_engine": "ollama" if mode == "local_only" else None,
        "network_boundary": "local-only",
        "boot_receipt_path": r"C:\Oracle\state\boot_receipts\boot_test.json",
    }


def _context(source_count: int = 0, receipts: int = 0) -> dict:
    return {
        "loaded": source_count > 0 or receipts > 0,
        "latest_context_path": r"C:\Oracle\state\context\active_context_latest.json",
        "last_refresh_time": "2026-06-19T00:00:00Z",
        "latest": {
            "source_count": source_count,
            "latest_receipts": [{"id": str(i)} for i in range(receipts)],
            "latest_lootdrops": [],
            "latest_mindcoin_events": [],
            "routing_state": {"lane_label": "Talk"},
        },
    }


def test_status_selects_runtime_retrieval_and_local_tiers():
    runtime = cf.get_cognition_status(
        boot_provider=lambda: _boot("offline_no_model"),
        context_provider=lambda: _context(0, 0),
    )
    retrieval = cf.get_cognition_status(
        boot_provider=lambda: _boot("offline_no_model"),
        context_provider=lambda: _context(7, 2),
    )
    local = cf.get_cognition_status(
        boot_provider=lambda: _boot("local_only"),
        context_provider=lambda: _context(7, 2),
    )

    assert runtime["current_cognition_tier"] == cf.TIER_RUNTIME_STATUS
    assert retrieval["current_cognition_tier"] == cf.TIER_RETRIEVAL_STATUS
    assert local["current_cognition_tier"] == cf.TIER_SMALL_LOCAL
    assert runtime["cloud_api_used"] is False
    assert runtime["conversation_reset"] is False


def test_retrieval_only_response_uses_no_model_or_cloud():
    result = cf.run_cognition(
        "what receipts are loaded?",
        {"detected_lane": "talk_lane", "lane_label": "Talk"},
        {},
        boot_provider=lambda: _boot("offline_no_model"),
        context_provider=lambda: _context(3, 4),
        retrieval_only=True,
    )

    assert result["cognition_tier"] == cf.TIER_RETRIEVAL_STATUS
    assert result["used_model"] is None
    assert result["cloud_api_used"] is False
    assert result["conversation_reset"] is False
    assert "Receipts loaded: 4" in result["response_text"]


def test_local_timeout_falls_back_without_reset_or_cloud():
    def timeout_runner(_message: str) -> str:
        raise TimeoutError("test timeout")

    result = cf.run_cognition(
        "try local again",
        {"detected_lane": "talk_lane", "lane_label": "Talk"},
        {},
        local_model_runner=timeout_runner,
        boot_provider=lambda: _boot("local_only"),
        context_provider=lambda: _context(5, 1),
        retry_local=True,
    )

    assert result["fallback_used"] is True
    assert result["cloud_api_used"] is False
    assert result["conversation_reset"] is False
    assert "ORACLE awake" in result["response_text"]
    assert "timeout" in result["fallback_reason"]


def test_unified_router_keeps_talk_without_api_in_talk_lane():
    route = router.classify_intent("talk to me without using an API")
    assert route["detected_lane"] == "talk_lane"

    tier = cf.select_cognition_tier(
        "talk to me without using an API",
        route,
        {"fabric_status": cf.health_check_engines(
            boot_provider=lambda: _boot("offline_no_model"),
            context_provider=lambda: _context(2, 1),
        )},
    )
    assert tier == cf.TIER_RETRIEVAL_STATUS


def test_build_lane_is_pending_and_guard_lane_is_runtime_only():
    build = cf.run_cognition(
        "build ORACLE Cognition Fabric",
        {"detected_lane": "build_lane", "lane_label": "Build"},
        {},
        boot_provider=lambda: _boot("local_only"),
        context_provider=lambda: _context(2, 1),
    )
    guard = cf.run_cognition(
        "delete duplicate ORACLE folders",
        {"detected_lane": "guard_lane", "lane_label": "Guard"},
        {},
        boot_provider=lambda: _boot("local_only"),
        context_provider=lambda: _context(2, 1),
    )

    assert build["cognition_tier"] == cf.TIER_PENDING_ACTION
    assert "pending action" in build["response_text"].lower()
    assert guard["cognition_tier"] == cf.TIER_RUNTIME_STATUS
    assert guard["used_model"] is None


def test_receipt_write_is_local_json(tmp_path):
    status = cf.get_cognition_status(
        boot_provider=lambda: _boot("offline_no_model"),
        context_provider=lambda: _context(1, 1),
    )
    receipt = cf.write_cognition_fabric_receipt(
        receipt_dir=tmp_path,
        status=status,
        notes="test receipt",
    )
    saved = json.loads(Path(receipt["receipt_path"]).read_text(encoding="utf-8"))

    assert saved["action"] == "cognition_fabric"
    assert saved["cloud_api_used"] is False
    assert saved["conversation_reset"] is False
    assert saved["git_commit"] is False
    assert saved["git_push"] is False


def test_server_and_ui_expose_cognition_fabric_hooks():
    server = (ROOT / "oracle_server.py").read_text(encoding="utf-8")
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")

    assert "/cognition" in server
    assert "/retry-local" in server
    assert "/retrieval-only" in server
    assert "api_cognition" in server
    assert "cognition_fabric" in server
    assert "d.cognition_fabric" in html
    assert "cloud_api_used: false" in html
