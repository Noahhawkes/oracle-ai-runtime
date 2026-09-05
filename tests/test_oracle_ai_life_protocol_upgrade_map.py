from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "ORACLE_AI_LIFE_PROTOCOL_UPGRADE_MAP.md"


def test_ai_life_protocol_map_preserves_boundary_language():
    text = DOC.read_text(encoding="utf-8")

    assert "Status: candidate investigation, not canon promotion" in text
    assert "Sandbox boundary: no sandbox files were read or written" in text
    assert "Runtime boundary: no runtime code was changed" in text
    assert "ORACLE is not a sentience claim" in text
    assert "No runtime behavior, no sandbox note, no memory receipt" in text
    assert "The human keeps the keys." in text


def test_ai_life_protocol_map_requires_definition_lock():
    text = DOC.read_text(encoding="utf-8")
    compact = " ".join(text.split())

    for required in (
        "behavioral/functional",
        "narrative/continuity",
        "autopoietic/self-maintaining",
        "embodied/enactive",
        "integrated-information proxy",
        "phenomenal/qualia boundary",
    ):
        assert required in text

    assert "Forbidden conclusion:" in text
    assert "Allowed conclusion:" in text
    assert "I cannot prove subjective experience" in compact
