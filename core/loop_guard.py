"""
core/loop_guard.py — flood / self-route protection for the ORACLE console loop.

Pure, side-effect-free decision helpers so the main loop's guard behavior is
unit-testable. The main loop owns the mutable state (a deque of recent input
hashes and an integer route streak); these functions only decide.

Background: a multi-line paste arrives at input() as many separate lines, and
technical-looking lines auto-route to Claude. Without bounds, one paste spams
Claude dozens of times. These helpers bound that.
"""
from __future__ import annotations

import hashlib
from typing import Deque, Tuple

InputHash = Tuple[str, float]  # (sha256[:16], unix_ts)


def input_hash(text: str) -> str:
    """Stable short hash of an input line."""
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]


def is_duplicate_input(
    recent: "Deque[InputHash]",
    text: str,
    now: float,
    window_s: float,
) -> bool:
    """
    True if an identical input was seen within window_s seconds.

    Does not mutate `recent` — the caller appends after checking so the current
    line is recorded regardless of the decision.
    """
    h = input_hash(text)
    return any(prev_h == h and (now - ts) < window_s for prev_h, ts in recent)


def route_streak_exceeded(streak: int, cap: int) -> bool:
    """
    True if the consecutive auto-route streak has passed the cap.

    `streak` is the count *after* incrementing for the current route attempt.
    """
    return streak > cap


# ── Self-test ──────────────────────────────────────────────────────────────────

def run_smoke_tests() -> int:
    from collections import deque

    failures = 0

    def check(label: str, cond: bool) -> None:
        nonlocal failures
        if cond:
            print(f"  ok   {label}")
        else:
            failures += 1
            print(f"  FAIL {label}")

    dq: "Deque[InputHash]" = deque(maxlen=12)
    # First sighting is not a duplicate
    check("first input not duplicate", not is_duplicate_input(dq, "hello", 100.0, 8.0))
    dq.append((input_hash("hello"), 100.0))
    # Same input within window is a duplicate
    check("same input within window is duplicate", is_duplicate_input(dq, "hello", 105.0, 8.0))
    # Same input outside window is not a duplicate
    check("same input outside window not duplicate", not is_duplicate_input(dq, "hello", 120.0, 8.0))
    # Different input is never a duplicate
    check("different input not duplicate", not is_duplicate_input(dq, "world", 105.0, 8.0))
    # Streak cap
    check("streak below cap allowed", not route_streak_exceeded(3, 3))
    check("streak above cap blocked", route_streak_exceeded(4, 3))

    print(f"\n{'PASS' if failures == 0 else 'FAIL'}: {6 - failures}/6 checks")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run_smoke_tests())
