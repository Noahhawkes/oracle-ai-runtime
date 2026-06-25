"""Acceptance tests for the Intent Classification Layer + Capability Truth Registry."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

from oracle_intent import (  # noqa: E402
    classify_intent, capability_registry, registry_status, doctrine_3026, action_capability,
    is_large_directive, safe_preview, build_lane_staging, BUILD_LANE_STAGING,
)


def test_1_casual_check_in():
    assert "casual_talk" in classify_intent("hey oracle are you with me")


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
    msg = "“smart”\n‘quotes’\nand newlines " + ("x" * 1000)
    p = safe_preview(msg)
    assert "“" not in p and "”" not in p and "‘" not in p and "’" not in p
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


def test_build_lane_message_is_honest():
    assert "large build directive" in BUILD_LANE_STAGING.lower()
    assert "build lane" in BUILD_LANE_STAGING.lower()
