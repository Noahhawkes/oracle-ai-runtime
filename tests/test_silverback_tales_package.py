from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "docs" / "rendered_reality_silverback_tales"


REQUIRED_FILES = {
    "SERIES_BIBLE.md",
    "CHARACTER_BIBLE.md",
    "SEASON_1_MAP.md",
    "PILOT_SCRIPT.md",
    "PRODUCTION_PLAN.md",
    "CREATIVE_CONTINUITY_LEDGER.md",
    "ORACLE_SHOWRUNNER_PROMPT.md",
    "RECEIPT.md",
}


def _text(name: str) -> str:
    return (PACKAGE / name).read_text(encoding="utf-8")


def test_silverback_candidate_package_has_required_files():
    assert PACKAGE.exists()
    assert {path.name for path in PACKAGE.glob("*.md")} >= REQUIRED_FILES


def test_all_package_files_preserve_candidate_governance():
    for name in REQUIRED_FILES:
        text = _text(name).lower()
        assert "status: candidate" in text
        assert "canon status: candidate" in text
        assert "promotion status: not_promoted" in text
        assert "approval authority: noah.physical" in text


def test_series_bible_contains_self_rendering_engine_and_boundaries():
    text = _text("SERIES_BIBLE.md")

    assert "Max is directing the story of himself while life keeps refusing to take direction" in text
    assert "biographical source material must remain separate" in text
    assert "Oracle is not a magical truth machine" in text
    assert "Ashley is not a one-note corrective device" in text


def test_pilot_preserves_laundry_scene_and_oracle_competing_accounts():
    text = _text("PILOT_SCRIPT.md")

    assert "Can you come fold laundry with me?" in text
    assert "Max did a good job" in text
    assert "COMPETING ACCOUNTS" in text
    assert "The towel remains folded" in text


def test_showrunner_prompt_blocks_canon_promotion_and_sentience_claims():
    text = _text("ORACLE_SHOWRUNNER_PROMPT.md").lower()

    assert "never imply that fictional max is literally noah.physical" in text
    assert "never imply that oracle is conscious" in text
    assert "promote candidate material to canon without noah.physical approval" in text
    assert "invent family memories" in text


def test_production_plan_favors_small_pilot_before_platform():
    text = _text("PRODUCTION_PLAN.md").lower()

    assert "finish one 8 to 12 minute pilot" in text
    assert "one microphone" in text
    assert "do not start here" in text
    assert "noah.physical approval recorded" in text
