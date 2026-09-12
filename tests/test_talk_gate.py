import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

import talk_gate as tg


# ── Noah's acceptance tests ────────────────────────────────────────────────────

def test_hello_oracle_is_talk():
    assert tg.is_explicit_action_request("hello oracle") is False
    assert tg.default_lane("hello oracle") == "talk_lane"


def test_talk_command_forces_talk():
    assert tg.is_talk_command("/talk hello oracle") is True
    assert tg.default_lane("/talk hello oracle") == "talk_lane"
    assert tg.strip_talk_command("/talk hello oracle") == "hello oracle"


def test_noah_in_thread_is_talk():
    assert tg.default_lane("Hi this is Noah in the thread") == "talk_lane"


def test_architecture_spec_is_talk_not_guard():
    spec = (
        "Give ORACLE frontend access through a local-only backend API.\n\n"
        "Do not let the frontend directly write memory, execute actions, touch files, "
        "call SOV1, push GitHub, or promote candidates.\n\n"
        "Add or wire this endpoint:\n\n"
        "```text\nPOST /thread/respond\n```\n\n"
        "The frontend sends user_message, recent_turns, oracle_state.\n"
        "All persistence, approval, SOV1 routing, file access, and actions remain backend-gated."
    )
    assert tg.is_explicit_action_request(spec) is False
    assert tg.default_lane(spec) == "talk_lane"


def test_explicit_file_write_is_guard():
    msg = "write this file to core/cognition_fabric.py"
    assert tg.is_explicit_action_request(msg) is True
    assert tg.default_lane(msg) == "guard_lane"


# ── Guard rails around the gate ────────────────────────────────────────────────

def test_negated_action_is_talk():
    assert tg.is_explicit_action_request("do not commit or push this") is False
    assert tg.is_explicit_action_request("please never delete my files") is False


def test_question_about_action_is_talk():
    assert tg.is_explicit_action_request("should I commit and push now?") is False


def test_benign_receipt_write_is_not_guard():
    # "write a receipt" has no path target -> not a filesystem action request.
    assert tg.is_explicit_action_request("write a receipt for this moment") is False


def test_real_destructive_commands_are_guard():
    assert tg.is_explicit_action_request("delete the file now") is True
    assert tg.is_explicit_action_request("push to origin") is True
    assert tg.is_explicit_action_request("commit and push") is True


def test_short_complaint_is_talk():
    assert tg.default_lane("Oracle barely talks. Why can't she give me a paragraph?") == "talk_lane"
