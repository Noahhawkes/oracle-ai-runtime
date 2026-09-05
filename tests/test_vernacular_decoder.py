"""Tests for core/vernacular_decoder.py — conflict-speech decoding."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

from core.vernacular_decoder import decode, CONFLICT_SUBTEXT


def test_detects_g_dropped_conflict_phrase():
    r = decode("you was actin' funny")
    assert r.is_conflict
    assert any("don't trust it" in m for _, m in r.matches)


def test_detects_cap_as_lying():
    r = decode("that's cap and you know it")
    assert any(m == "You're lying." for _, m in r.matches)


def test_multiple_phrases_and_subtext():
    r = decode("Nah cuz you was actin funny, but now that's cap")
    assert len(r.matches) >= 2
    assert r.subtext == CONFLICT_SUBTEXT


def test_neutral_speech_is_not_conflict():
    r = decode("the weather is nice today")
    assert not r.is_conflict
    assert r.subtext is None


def test_undefined_terms_stay_unknown():
    r = decode("bro is cooked, no cap")
    assert "no cap" in r.undefined
    assert "bro is cooked" in r.undefined
    # recognized, but never auto-defined
    assert not r.is_conflict
