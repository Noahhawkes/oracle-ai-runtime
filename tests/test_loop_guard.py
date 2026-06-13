"""
Integration test for the console flood / self-route guard.

Reproduces the conditions of the runtime incident where a multi-line paste of
technical text routed to Claude dozens of times, and proves the guard now:

  - suppresses duplicate inputs within the dedup window
  - caps consecutive auto-routes to Claude
  - lets one human command route exactly once
  - resets the streak after a genuine conversational turn
"""
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))

from loop_guard import is_duplicate_input, input_hash, route_streak_exceeded  # noqa: E402


DUP_WINDOW = 8.0
STREAK_CAP = 3


def test_duplicate_input_suppressed_within_window():
    dq = deque(maxlen=12)
    t = 1000.0
    assert is_duplicate_input(dq, "the coffee is cold", t, DUP_WINDOW) is False
    dq.append((input_hash("the coffee is cold"), t))
    # Same line 2s later — paste flood — must be flagged duplicate
    assert is_duplicate_input(dq, "the coffee is cold", t + 2.0, DUP_WINDOW) is True


def test_duplicate_allowed_after_window():
    dq = deque(maxlen=12)
    t = 1000.0
    dq.append((input_hash("status"), t))
    # Deliberate human repeat well after the window is NOT suppressed
    assert is_duplicate_input(dq, "status", t + 30.0, DUP_WINDOW) is False


def test_one_human_command_routes_once():
    # A single route attempt (streak 1) is under the cap — it proceeds.
    streak = 0
    streak += 1
    assert route_streak_exceeded(streak, STREAK_CAP) is False


def test_paste_flood_is_capped():
    # Simulate many technical lines auto-routing with no human turn between them.
    streak = 0
    routed = 0
    blocked = 0
    for _ in range(20):
        streak += 1
        if route_streak_exceeded(streak, STREAK_CAP):
            blocked += 1
        else:
            routed += 1
    # Only the first STREAK_CAP routes proceed; the rest are blocked.
    assert routed == STREAK_CAP
    assert blocked == 20 - STREAK_CAP


def test_human_turn_resets_streak():
    # After hitting the cap, a real conversational turn resets the streak,
    # so the next legitimate route is allowed again.
    streak = STREAK_CAP + 5
    assert route_streak_exceeded(streak + 1, STREAK_CAP) is True
    # human conversational turn happens -> reset
    streak = 0
    streak += 1
    assert route_streak_exceeded(streak, STREAK_CAP) is False


def test_oracle_output_lines_do_not_each_route_uniquely():
    # ORACLE's own repeated "Routing to Claude Code." style output, if it were
    # ever fed back, hashes identically and is suppressed as duplicate.
    dq = deque(maxlen=12)
    t = 500.0
    line = "Routing to Claude Code."
    assert is_duplicate_input(dq, line, t, DUP_WINDOW) is False
    dq.append((input_hash(line), t))
    for i in range(1, 5):
        assert is_duplicate_input(dq, line, t + i, DUP_WINDOW) is True
