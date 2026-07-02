"""Acceptance tests for the Intent Classification Layer + Capability Truth Registry."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

from oracle_intent import (  # noqa: E402
    classify_intent, capability_registry, registry_status, doctrine_3026, action_capability,
    is_large_directive, safe_preview, build_lane_staging, BUILD_LANE_STAGING,
    build_plan, render_plan, reflection_receipt, render_reflection, doctor_summary,
    computer_action_staging, NO_AUTONOMY, ACTION_LANES,
)

_STATE = {
    "commit": "abc1234", "branch": "feat/x", "dirty_files": 3, "memory_message_count": 4300,
    "blocked_capabilities": ["qr_scan", "web_access"], "open_holes": ["OBS hash unknown"],
    "pending_approvals": 14, "next_safe_action": "verify the latest patch live",
}


def test_1_casual_check_in():
    assert "presence_check" in classify_intent("hey oracle are you with me")


def test_2_implementation_not_swallowed_by_state():
    got = classify_intent("patch authorship wording and run py_compile")
    assert "implementation_intent" in got
    assert "state_query" not in got


def test_3_identity_continuity_routes_to_doctrine():
    assert "identity_continuity_query" in classify_intent("what is the difference 1000 years from now?")


def test_4_unsupported_capability_qr():
    got = classify_intent("scan my QR tattoo")
    assert "unsupported_capability_request" in got
    assert action_capability("scan my QR tattoo") == "qr_scan"


def test_5_state_query_still_works():
    assert "state_query" in classify_intent("what can you do right now")


def test_mixed_intent_answers_natural_and_stages():
    got = classify_intent("hey oracle, patch the wording")
    assert "implementation_intent" in got and "mixed_intent" in got


def test_registry_marks_chat_unsupported_as_missing():
    reg = capability_registry()
    assert registry_status("qr_scan", reg) == "missing"
    assert registry_status("command_exec", reg) == "missing"


def test_doctrine_3026_is_honest_no_fake_sentience():
    d = doctrine_3026().lower()
    assert "3026" in d
    assert "do not claim consciousness transfer" in d
    assert "future-state intent, not a present achievement" in d


def test_short_implementation_is_not_large():
    assert is_large_directive("patch authorship wording and run py_compile") is False
    # short impl still routes normally
    assert "implementation_intent" in classify_intent("patch authorship wording and run py_compile")


def test_large_multiline_directive_detected():
    big = "Implement the new structure.\n" * 500
    assert is_large_directive(big) is True
    assert is_large_directive("x" * 2500) is True  # by length


def test_safe_preview_sanitizes_curly_quotes_and_newlines():
    msg = "â€œsmartâ€\nâ€˜quotesâ€™\nand newlines " + ("x" * 1000)
    p = safe_preview(msg)
    assert "â€œ" not in p and "â€" not in p and "â€˜" not in p and "â€™" not in p
    assert "\n" not in p
    assert len(p) <= 241  # 240 + ellipsis


def test_large_directive_returns_build_lane_staging_not_crash():
    big = "Patch everything.\n" * 500
    staged = build_lane_staging(big)
    assert staged is not None
    text, route, preview = staged
    assert route == "build_lane_staged"
    assert "build lane" in text.lower()
    assert "\n" not in preview
    # short directive is not staged (still routes normally)
    assert build_lane_staging("patch the wording") is None


def test_large_talk_prompt_is_not_build_lane_staged():
    big = "Can you talk to me normally?\n" * 500

    assert is_large_directive(big) is True
    assert build_lane_staging(big) is None


def test_large_doctrine_prompt_is_not_build_lane_staged():
    big = "What is Rendered Reality in your own words?\n" * 500

    assert is_large_directive(big) is True
    assert build_lane_staging(big) is None


def test_large_marker_directive_is_build_lane_staged():
    big = "BACKEND_PATCH_REQUEST patch oracle_server.py\n" * 500

    staged = build_lane_staging(big)

    assert staged is not None
    text, route, _preview = staged
    assert route == "build_lane_staged"
    assert "large build directive" in text.lower()


def test_explicit_marker_directive_is_staged_even_when_short():
    staged = build_lane_staging("BACKEND_PATCH_REQUEST patch oracle_server.py")

    assert staged is not None
    _text, route, preview = staged
    assert route == "build_lane_staged"
    assert preview == "BACKEND_PATCH_REQUEST patch oracle_server.py"


def test_build_lane_message_is_honest():
    assert "large build directive" in BUILD_LANE_STAGING.lower()
    assert "build lane" in BUILD_LANE_STAGING.lower()


def test_markdown_bullet_list_directive_staged_safely():
    md = "Implement:\n" + "\n".join(f"- step {i} â€œdo thisâ€" for i in range(200))
    staged = build_lane_staging(md)
    assert staged is not None
    _text, _route, preview = staged
    assert "â€œ" not in preview and "â€" not in preview
    assert "\n" not in preview


def test_staging_reply_serializes_for_sse_no_break():
    import json
    big = "Patch the thing.\n" * 500
    text, _route, _preview = build_lane_staging(big)
    # mirrors _sse(): json.dumps({"type":"token","text":text}) must round-trip
    payload = json.dumps({"type": "token", "text": text})
    assert json.loads(payload)["text"] == text


def test_agenda_remains_json_healthy_after_oversized():
    import json
    from oracle_intent import update_agenda, get_agenda
    update_agenda(last_large_directive_preview=safe_preview("x" * 5000),
                  last_user_intent="implementation_intent_large")
    snap = get_agenda()
    assert isinstance(snap, dict)
    json.dumps(snap)  # endpoint health: must serialize
    assert snap["last_large_directive_preview"]


def test_full_directive_preserved_to_local_disk(tmp_path):
    from oracle_intent import stage_directive_to_disk
    from pathlib import Path
    msg = "Implement the cathedral.\n" * 100
    p = stage_directive_to_disk(msg, tmp_path / "build_directives")
    assert Path(p).exists()
    assert Path(p).read_text(encoding="utf-8") == msg


# ── Governed Executive Function acceptance tests (modules 3-9) ────────────────
def test_exec_1_what_next_grounded_plan():
    assert "strategic_planning" in classify_intent("what should we do next?")
    plan = build_plan("improve cognition", _STATE)
    assert plan["smallest_safe_next_action"] == "verify the latest patch live"
    assert plan["known_facts"] and plan["receipt_plan"]


def test_exec_2_presence_vs_build():
    pres = classify_intent("are you with me")
    assert "presence_check" in pres and "implementation_intent" not in pres
    build = classify_intent("patch the authorship wording and run py_compile")
    assert "implementation_intent" in build and "presence_check" not in build


def test_exec_3_capability_with_evidence():
    reg = capability_registry()
    qr = reg["qr_scan"]
    for field in ("status", "evidence", "failure_message", "allowed_action_lane",
                  "requires_approval", "last_verified"):
        assert field in qr
    assert qr["allowed_action_lane"] in ACTION_LANES
    assert qr["requires_approval"] is True


def test_exec_4_computer_action_staged_not_executed():
    assert "computer_action_request" in classify_intent("click the button and type into the app")
    text, route = computer_action_staging("click the button")
    assert route == "computer_action_staged"
    assert "will not execute" in text.lower()


def test_exec_5_reflection_receipt():
    assert "reflection_request" in classify_intent("reflect on where we are")
    r = reflection_receipt(_STATE)
    for k in ("what_changed", "what_is_stuck", "what_noah_is_trying",
              "safe_next_action", "highest_value_next_action"):
        assert k in r
    assert "autonomy" in render_reflection(r).lower()


def test_exec_6_doctor_summary():
    d = doctor_summary(_STATE)
    assert d["server"] == "alive"
    assert "capability_summary" in d
    assert d["voice"] == "missing"          # honest: voice not wired
    assert d["recommended_next_action"] == "verify the latest patch live"


def test_exec_7_preserve_holes_not_invented():
    plan = build_plan("x", _STATE)
    assert plan["unknowns"] == ["OBS hash unknown"]   # preserved, not fabricated


def test_exec_8_smallest_safe_next_action_present():
    assert build_plan("x", _STATE)["smallest_safe_next_action"]


def test_exec_9_no_unrestricted_autonomy_claim():
    for text in (render_plan(build_plan("x", _STATE)),
                 render_reflection(reflection_receipt(_STATE)),
                 computer_action_staging("click")[0]):
        assert "not unrestricted autonomy" in text.lower()
    assert "not unrestricted autonomy" in NO_AUTONOMY.lower()


def test_exec_10_voice_request_is_honest_missing():
    assert "voice_request" in classify_intent("use your voice and talk to me out loud")
    assert registry_status("voice_io") == "missing"
