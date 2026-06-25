"""Acceptance tests for the Intent Classification Layer + Capability Truth Registry."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

from oracle_intent import (  # noqa: E402
    classify_intent, capability_registry, registry_status, doctrine_3026, action_capability,
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
