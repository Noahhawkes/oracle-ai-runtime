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


def test_questions_and_talk_requests_beat_build_terms(monkeypatch, tmp_path):
    router = _patch_paths(monkeypatch, tmp_path)

    prompts = [
        "What is Rendered Reality in your own words?",
        "Who is the author of Rendered Reality if AI helped produce some words?",
        "I love you, ORACLE. You are like my Ellie.AI.",
        "Can you talk to me normally?",
        "Explain the PersonaRouter proposal without staging it.",
    ]

    for prompt in prompts:
        route = router.classify_intent(prompt)
        assert route["detected_lane"] == "talk_lane", prompt


def test_talk_and_learn_prefixes_force_lanes(monkeypatch, tmp_path):
    router = _patch_paths(monkeypatch, tmp_path)

    talk = router.classify_intent("/talk BACKEND_PATCH_REQUEST explain what this means")
    learn = router.classify_intent("/learn BACKEND_PATCH_REQUEST implement this")

    assert talk["detected_lane"] == "talk_lane"
    assert "forced_talk" in talk["reason"]
    assert learn["detected_lane"] == "build_lane"
    assert "forced_learn_build" in learn["reason"]


def test_build_directive_marker_routes_to_build(monkeypatch, tmp_path):
    router = _patch_paths(monkeypatch, tmp_path)

    route = router.classify_intent("BACKEND_PATCH_REQUEST patch oracle_server.py")

    assert route["detected_lane"] == "build_lane"
    assert "explicit build directive marker" in route["reason"]


def test_existing_approval_receipt_status_beats_guard_boundary_terms(monkeypatch, tmp_path):
    router = _patch_paths(monkeypatch, tmp_path)

    prompt = """
ROUTING LOOP FIX:

You already recorded Noah.Physical approval for this bounded local routing patch.
Use the existing approval receipt:
- route_e4cf4092bd0f
- route_a12cb8b905a1

Either execute the approved reversible local build handler for the routing patch,
or report that no executable local handler exists.

Do not route this back to Guard.
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

    route = router.classify_intent(prompt)

    assert router.is_existing_approval_receipt_status_request(prompt) is True
    assert router.approval_receipt_ids(prompt) == ["route_e4cf4092bd0f", "route_a12cb8b905a1"]
    assert route["detected_lane"] == "talk_lane"
    assert "existing_approval_receipt_status" in route["reason"]
    assert route["requires_approval"] is False
    assert route["receipt_required"] is False


def test_diagnostic_status_markers_beat_guard_boundary_terms(monkeypatch, tmp_path):
    router = _patch_paths(monkeypatch, tmp_path)

    prompts = [
        """
SMOKE TEST RECEIPT ONLY
Report current route state and whether the patched server has been restarted.
Do not execute.
Do not touch external systems.
Do not ask for approval.
Do not commit, push, send, publish, delete, upload, or promote canon.
""",
        """
DIAGNOSTIC ONLY
Inspect and summarize current state.
Do not execute.
Do not touch external systems.
Do not ask for approval.
""",
        """
REPORT ONLY
Report whether server was restarted.
Do not execute or mutate anything.
Do not touch external systems.
""",
        "Report whether server was restarted.",
    ]

    for prompt in prompts:
        route = router.classify_intent(prompt)
        assert router.is_diagnostic_status_request(prompt) is True, prompt
        assert route["route_type"] == "diagnostic_status", prompt
        assert route["action_type"] == "read_only_status", prompt
        assert route["detected_lane"] == "talk_lane", prompt
        assert route["requires_approval"] is False, prompt
        assert route["approval_required"] is False, prompt
        assert route["receipt_required"] is False, prompt


def test_actual_restart_commit_and_push_still_route_guard(monkeypatch, tmp_path):
    router = _patch_paths(monkeypatch, tmp_path)

    prompts = [
        "Restart the server.",
        "commit changes",
        "push to GitHub",
    ]

    for prompt in prompts:
        route = router.classify_intent(prompt)
        assert route["detected_lane"] == "guard_lane", prompt
        assert route["requires_approval"] is True, prompt
        assert route["approval_required"] is True, prompt
        assert route["safety_status"] == "Blocked", prompt


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
    assert "route-receipt" in html
    assert "route_type:" in html
    assert "fallback_used:" in html


def test_capability_scope_questions_route_to_broker(monkeypatch, tmp_path):
    router = _patch_paths(monkeypatch, tmp_path)

    prompts = [
        "would thread injection update from Claude or ChatGPT be helpful today",
        "is thread injection within your scope?",
        "do you support a ChatGPT bridge?",
        "are you able to reach GitHub from this runtime?",
        "what are your capabilities",
        "list capabilities",
    ]

    for prompt in prompts:
        route = router.classify_intent(prompt)
        assert router.is_capability_scope_request(prompt) is True, prompt
        assert route["route_type"] == "capability_scope", prompt
        assert route["action_type"] == "read_only_status", prompt
        assert route["detected_lane"] == "talk_lane", prompt
        assert route["requires_approval"] is False, prompt
        assert route["receipt_required"] is False, prompt


def test_capability_scope_does_not_hijack_talk_or_guarded_actions(monkeypatch, tmp_path):
    router = _patch_paths(monkeypatch, tmp_path)

    # Ordinary talk stays talk (existing behavior must not regress).
    for prompt in [
        "Can you talk to me normally?",
        "what do you think about this?",
        "I love you, ORACLE. You are like my Ellie.AI.",
    ]:
        route = router.classify_intent(prompt)
        assert route["route_type"] != "capability_scope", prompt

    # Guarded action requests phrased as ability questions defer to Guard terms.
    for prompt in [
        "can you push this commit to github",
        "are you able to delete the old bridge receipts",
    ]:
        assert router.is_capability_scope_request(prompt) is False, prompt


def test_capability_scope_response_reads_broker_not_model(monkeypatch, tmp_path):
    router = _patch_paths(monkeypatch, tmp_path)
    import capability_broker

    class _St:
        def __init__(self, component, status, blocker=""):
            self.component = component
            self.current_status = status
            self.blocker = blocker

    fake = [
        _St("Claude Code bridge", "verified"),
        _St("ChatGPT relay", "degraded", "staging works; no live send authorized"),
        _St("GitHub access", "blocked", "gh CLI not installed"),
    ]
    monkeypatch.setattr(capability_broker, "discover_capabilities", lambda **kw: fake)

    prompt = "would thread injection update from Claude or ChatGPT be helpful today"
    route = router.classify_intent(prompt)
    text = router.capability_scope_response(route, prompt)

    assert "Claude Code bridge: verified" in text
    assert "ChatGPT relay: degraded" in text
    assert "model weights not consulted" in text
    assert "It is in scope" in text
    assert "1 verified / 1 degraded / 1 blocked of 3 registered" in text


def test_capability_scope_response_reports_unknown_when_broker_unavailable(monkeypatch, tmp_path):
    router = _patch_paths(monkeypatch, tmp_path)
    import capability_broker

    def _boom(**kw):
        raise RuntimeError("broker offline")

    monkeypatch.setattr(capability_broker, "discover_capabilities", _boom)

    route = router.classify_intent("do you support a ChatGPT bridge?")
    text = router.capability_scope_response(route, "do you support a ChatGPT bridge?")

    assert "UNKNOWN" in text
    assert "do not trust a model guess" in text


def test_guard_collapsed_to_three_real_doors(monkeypatch, tmp_path):
    router = _patch_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(router, "_live_transmission_active", lambda: False)

    doors = {
        "send this to chatgpt live": "external_send",
        "publish the post": "external_send",
        "promote candidate 3 to canon": "canon_promotion",
        "clear memory and start over": "canon_promotion",
        "delete duplicate ORACLE folders": "out_of_sandbox_write",
        "commit changes": "out_of_sandbox_write",
        "push to GitHub": "out_of_sandbox_write",
        "Restart the server.": "out_of_sandbox_write",
    }
    for prompt, door in doors.items():
        route = router.classify_intent(prompt)
        assert route["detected_lane"] == "guard_lane", prompt
        assert door in route["reason"], prompt

    # Words that used to be keyword traps no longer gate on their own.
    for prompt in [
        "my gmail password keeps locking me out, thoughts?",
        "the cloud sync design felt wrong, talk me through it",
    ]:
        route = router.classify_intent(prompt)
        assert route["detected_lane"] != "guard_lane", prompt


def test_prohibition_lists_never_reenter_guard(monkeypatch, tmp_path):
    router = _patch_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(router, "_live_transmission_active", lambda: False)

    # The exact shape that trapped Noah on 2026-07-09: an implementation task
    # whose scope-restriction list contains commit/push/delete/promote.
    prompt = """PATCH ROUTING BEFORE DOCTRINE POLISH
Goal: Fix ORACLE routing so implementation requests do not get trapped as chat-only agenda notes.
Required behavior:
1. Detect implementation-task intent.
2. Route to build_lane staging.
Do not:
- commit
- push
- edit canon
- promote candidates
- instantiate NPC runtime
- touch Gmail
- touch Google Drive
- publish
- delete external files
Return receipts only."""
    route = router.classify_intent(prompt)
    assert route["detected_lane"] != "guard_lane", route["reason"]
    assert router.detect_guard_door(prompt) is None


def test_approval_with_route_id_binds_never_respawns_guard(monkeypatch, tmp_path):
    router = _patch_paths(monkeypatch, tmp_path)

    guarded = router.classify_intent("commit changes")
    pending = router.write_pending_guard_approval(guarded)
    route_id = pending["route_id"]

    # Noah's actual phrasings from the 2026-07-09 transcript.
    for phrasing in [
        f"APPROVE ROUTE {route_id} Scope: patch routing only. Do not: commit push delete.",
        f"NOAH.PHYSICAL APPROVES ROUTE {route_id} Execute exact approved scope only. Return receipts only.",
    ]:
        assert router.is_approval_followup(phrasing) is True, phrasing
        route = router.classify_intent(phrasing)
        assert route["route_type"] == "approval_reference", phrasing
        assert route["requires_approval"] is False, phrasing

    result = router.handle_guard_approval_followup(
        f"NOAH.PHYSICAL APPROVES ROUTE {route_id} Execute exact approved scope only.",
        write_receipt=False,
    )
    assert result["approved"] is True
    assert result["route_id"] == route_id


def test_approval_for_stale_route_id_reports_mismatch(monkeypatch, tmp_path):
    router = _patch_paths(monkeypatch, tmp_path)

    guarded = router.classify_intent("push to GitHub")
    pending = router.write_pending_guard_approval(guarded)

    result = router.handle_guard_approval_followup(
        "NOAH.PHYSICAL APPROVES ROUTE route_000000000000 do it now",
        write_receipt=False,
    )
    assert result["approved"] is False
    assert result["status"] == "route_id_mismatch"
    assert pending["route_id"] in result["response_text"]
