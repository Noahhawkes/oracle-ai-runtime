"""Tests for the HANDS_OFF safety gate in core/computer_control.py.

Honors Noah's 'no computer control' boundary: physical input is OFF by default
and a kill-switch flag always wins. These tests only exercise the OFF path and
the precedence logic — they never enable hands and never inject a keystroke.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "core")):
    if p not in sys.path:
        sys.path.insert(0, p)

import computer_control as cc

pytestmark = pytest.mark.skipif(not cc.HANDS_AVAILABLE, reason="pyautogui not installed")


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    # Point the flag lookups at a clean temp dir and clear the enable env.
    (tmp_path / "Memory").mkdir()
    monkeypatch.setattr(cc, "ROOT", tmp_path)
    monkeypatch.delenv("ORACLE_HANDS_ON", raising=False)
    return tmp_path


def test_default_is_hands_off(isolated):
    assert cc._hands_off() is True


def test_output_actions_refused_when_off(isolated):
    for result in (cc.type_text("hello"), cc.press("enter"), cc.hotkey("ctrl", "v")):
        assert "[HANDS OFF]" in result            # refused, nothing injected


def test_env_enables_hands(isolated, monkeypatch):
    monkeypatch.setenv("ORACLE_HANDS_ON", "1")
    assert cc._hands_off() is False               # do NOT call output fns here


def test_on_flag_enables_hands(isolated):
    (isolated / "Memory" / "hands_on.flag").write_text("ok", encoding="utf-8")
    assert cc._hands_off() is False


def test_kill_switch_overrides_env(isolated, monkeypatch):
    monkeypatch.setenv("ORACLE_HANDS_ON", "1")
    (isolated / "Memory" / "hands_off.flag").write_text("stop", encoding="utf-8")
    assert cc._hands_off() is True
    assert "[HANDS OFF]" in cc.press("enter")     # kill switch refuses output


def test_reads_not_gated_by_hands_off(isolated):
    # Read-only path (output=False) must stay open even when hands are off.
    assert cc._hands_off() is True
    assert cc._require_hands(output=False) is None
