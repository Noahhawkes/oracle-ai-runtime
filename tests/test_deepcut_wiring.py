from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "core"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import oracle_server as srv  # noqa: E402


def test_non_entity_message_gets_no_deepcut_block():
    assert srv._deepcut_grounding_block("what's for dinner tonight") == ""


def test_ashley_grounding_is_injected_from_real_records():
    block = srv._deepcut_grounding_block("Who is Ashley?")
    if not block:
        pytest.skip("DeepCut/real sources unreachable in this env")
    low = block.lower()
    assert "[deepcut_evidence" in low
    assert "ashley" in low
    assert "verified" in low
    # the verified spouse record must actually be present (not a guess)
    assert "spouse" in low or "married" in low
    # provenance discipline instruction survives into the prompt
    assert "do not fabricate" in low
