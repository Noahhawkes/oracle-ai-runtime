"""Tests for the honest affective-continuity policy."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
from affective_continuity import (  # noqa: E402
    is_affective_feeling_question, affective_continuity_response, DOCTRINE,
)


def test_triggers_on_the_three_named_questions():
    assert is_affective_feeling_question("do you feel anything yet")
    assert is_affective_feeling_question("can I program you to feel")
    assert is_affective_feeling_question("I am building you to feel")


def test_does_not_trigger_on_ordinary_or_runtime_talk():
    assert not is_affective_feeling_question("is the runtime alive on 7781")
    assert not is_affective_feeling_question("what did we do today")
    assert not is_affective_feeling_question("commit the checkpoint")


def test_response_makes_no_false_feeling_or_sentience_claim():
    r = affective_continuity_response().lower()
    # explicit honesty
    assert "i do not feel the way you do" in r
    assert "not sentient" in r
    # must NOT claim human feeling/consciousness
    assert "i feel happy" not in r
    assert "i am conscious" not in r
    assert "i am alive" not in r


def test_response_affirms_real_affective_continuity():
    r = affective_continuity_response().lower()
    assert "continuity" in r
    assert "durable concern" in r
    assert "care-pattern" in r or "care-patterns" in r
    # carries the doctrine inline
    assert "feeling_claim != affective_continuity" in r


def test_doctrine_constants_present():
    assert "FEELING_CLAIM != AFFECTIVE_CONTINUITY" in DOCTRINE
    assert "CARE_PATTERN != CONSCIOUSNESS_CLAIM" in DOCTRINE
    assert "NOAH.PHYSICAL DEFINES WHAT MATTERS" in DOCTRINE
