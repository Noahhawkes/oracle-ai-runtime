from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))


def _spine_text() -> str:
    return (ROOT / "docs" / "NOAH_ORACLE_100_PROMPT_TRAINING_SPINE.md").read_text(
        encoding="utf-8"
    )


def test_noah_oracle_training_spine_has_exactly_100_unique_questions():
    text = _spine_text()
    ids = re.findall(r"\bQ(\d{3}):", text)

    assert len(ids) == 100
    assert len(set(ids)) == 100
    assert ids[0] == "001"
    assert ids[-1] == "100"


def test_noah_oracle_training_spine_covers_required_domains():
    text = _spine_text().lower()
    required_terms = (
        "noah.physical",
        "authorial_authority",
        "token_origin",
        "sandbox",
        "receipts",
        "unknown",
        "ai compliance core",
        "jupiter station",
        "approval-gated",
        "true before smooth",
    )

    for term in required_terms:
        assert term in text


def test_noah_oracle_profile_block_is_compact_and_bounded():
    from noah_oracle_profile import noah_oracle_profile_block

    block = noah_oracle_profile_block()

    assert "NOAH_ORACLE_CONVERSATION_PROFILE" in block
    assert "Noah.Physical" in block
    assert "not_canon_not_source_evidence" in block
    assert "Do not claim ORACLE is biological, sentient, sovereign" in block
    assert len(block) < 3000

