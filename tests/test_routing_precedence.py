from __future__ import annotations

import os
import sys
import json
import asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "core"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import oracle_server as srv  # noqa: E402
from oracle_intent import build_lane_staging  # noqa: E402
from unified_oracle_router import classify_intent  # noqa: E402


def _long(text: str) -> str:
    return "\n".join([text] * 80)


async def _collect_stream_payloads(prompt: str) -> list[dict]:
    payloads: list[dict] = []
    async for chunk in srv._stream_reply(prompt):
        if not chunk.startswith("data: "):
            continue
        payloads.append(json.loads(chunk[len("data: "):].strip()))
    return payloads


def test_large_read_only_doctrine_reaches_talk_before_legacy_staging():
    prompt = _long("What is Rendered Reality in your own words?")

    assert build_lane_staging(prompt) is None
    route = classify_intent(prompt)
    assert route["detected_lane"] == "talk_lane"
    assert "read_only_synthesis" in route["reason"]
    assert srv._oracle_intent_dispatch(prompt) is None


def test_large_talk_request_reaches_talk_before_legacy_staging():
    prompt = _long("Can you talk to me normally?")

    assert build_lane_staging(prompt) is None
    route = classify_intent(prompt)
    assert route["detected_lane"] == "talk_lane"
    assert srv._oracle_intent_dispatch(prompt) is None
    assert srv._noah_direct_should_handle("Can you talk to me normally?") is False


def test_large_marker_directive_uses_legacy_preservation():
    prompt = _long("BACKEND_PATCH_REQUEST patch oracle_server.py")

    assert build_lane_staging(prompt) is not None
    route = classify_intent(prompt)
    assert route["detected_lane"] == "build_lane"
    dispatch = srv._oracle_intent_dispatch(prompt)
    assert dispatch is not None
    text, route_name = dispatch
    assert route_name == "build_lane_staged"
    assert "large build directive" in text.lower()


def test_talk_escape_hatch_beats_marker_directive():
    prompt = _long("/talk BACKEND_PATCH_REQUEST explain what this means")

    assert build_lane_staging(prompt) is None
    route = classify_intent(prompt)
    assert route["detected_lane"] == "talk_lane"
    assert "forced_talk" in route["reason"]


def test_existing_approval_receipt_status_request_does_not_reenter_guard():
    prompt = """
ROUTING LOOP FIX:

You already recorded Noah.Physical approval for this bounded local routing patch.

Use the existing approval receipt:
- route_e4cf4092bd0f
- route_a12cb8b905a1

Next action:
Either execute the approved reversible local build handler for the routing patch, or report that no executable local handler exists.

Do not route this back to Guard.
Do not preserve as a new build directive.
Do not ask for approval again.
Do not touch GitHub, Google Drive, Gmail, Calendar, external send, OBS, canon promotion, or private memory promotion.

Return only:

approval_receipt_used:
handler_exists:
handler_name:
can_execute_locally:
if_not_executable_reason:
next_command_for_noah:
"""

    route = classify_intent(prompt)
    response = srv._approval_receipt_status_response(prompt)

    assert srv._is_existing_approval_receipt_status_request(prompt) is True
    assert route["detected_lane"] == "talk_lane"
    assert route["requires_approval"] is False
    assert "existing_approval_receipt_status" in route["reason"]
    assert "approval_receipt_used: route_e4cf4092bd0f, route_a12cb8b905a1" in response
    assert "handler_exists: false" in response
    assert "can_execute_locally: false" in response
    assert "no action was executed" in response


def test_smoke_test_receipt_only_routes_read_only_status_before_guard():
    prompt = """
SMOKE TEST RECEIPT ONLY
Report current route state and whether server was restarted.
Do not execute.
Do not touch external systems.
Do not ask for approval.
Do not commit, push, send, publish, delete, upload, or promote canon.
"""

    route = classify_intent(prompt)

    assert route["route_type"] == "diagnostic_status"
    assert route["action_type"] == "read_only_status"
    assert route["detected_lane"] == "talk_lane"
    assert route["requires_approval"] is False


def test_smoke_test_receipt_only_stream_returns_deterministic_status():
    prompt = """
SMOKE TEST RECEIPT ONLY
Report current route state and whether server was restarted.
Do not execute.
Do not touch external systems.
Do not ask for approval.
Do not commit, push, send, publish, delete, upload, or promote canon.
"""

    payloads = asyncio.run(_collect_stream_payloads(prompt))
    route = next(p for p in payloads if p.get("type") == "route")
    token = next(p for p in payloads if p.get("type") == "token")
    done = next(p for p in payloads if p.get("type") == "done")

    assert route["route_type"] == "diagnostic_status"
    assert route["lane"] == "talk_lane"
    assert route["fallback_used"] is False
    assert "actions_executed: 0" in token["text"]
    assert "server_restarted_by_this_request: false" in token["text"]
    assert "computer_operator" not in token["text"]
    assert done["effective_route"] == "diagnostic_status"


def test_restart_server_still_routes_guard():
    route = classify_intent("Restart the server.")

    assert route["detected_lane"] == "guard_lane"
    assert route["requires_approval"] is True
