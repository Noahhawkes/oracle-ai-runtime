"""Tests for the ORACLE Context Bus (core/context_bus.py).

The context bus composes one canonical, provenance-tagged context pass from live
state so context stops being hand-relayed via clipboard. It composes content
only — it never sends/types into another AI (HANDS_OFF). Defensive: a failing
subsystem degrades a line to UNKNOWN, never crashes.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "core")):
    if p not in sys.path:
        sys.path.insert(0, p)

import context_bus as cb


def test_compose_has_all_sections_and_basis():
    data = cb.compose()
    assert data["kind"] == "oracle_context_pass"
    for sec in ("runtime", "cognition", "capabilities", "federation", "witness", "mindcoin", "hands"):
        assert sec in data["sections"]
        assert data["sections"][sec]["basis"] in {"RUNTIME_VERIFIED", "CANDIDATE", "UNKNOWN", "DOCTRINE"}


def test_doctrine_present():
    data = cb.compose()
    assert "AI may have hands; the human keeps the keys." in data["doctrine"]
    assert any("Reflection channel" in d for d in data["doctrine"])


def test_render_is_paste_ready_text():
    txt = cb.render(cb.compose())
    assert "ORACLE CONTEXT PASS" in txt
    for tag in ("[RUNTIME", "[CAPABILITIES", "[FEDERATION", "[MINDCOIN", "[HANDS", "[DOCTRINE]"):
        assert tag in txt
    # governance: the pass tells the receiver authority stays with Noah
    assert "Noah.Physical" in txt


def test_defensive_on_subsystem_failure(monkeypatch):
    # If a subsystem read throws, its line degrades to UNKNOWN, pass still composes.
    def boom():
        raise RuntimeError("simulated subsystem down")
    monkeypatch.setattr(cb, "_federation", boom)
    data = cb.compose()
    assert data["sections"]["federation"]["basis"] == "UNKNOWN"
    # other sections unaffected; render still works
    txt = cb.render(data)
    assert "ORACLE CONTEXT PASS" in txt


def test_compose_does_not_actuate():
    # The bus must never enable hands as a side effect of composing.
    import computer_control as cc
    before = cc._hands_off()
    cb.compose()
    assert cc._hands_off() == before  # composing changes no actuation posture
