from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "core"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import affective_provenance as ap  # noqa: E402
import relationship_state as rs  # noqa: E402


def _events(text: str, source_id: str = "t", authored: bool = True):
    return ap.extract_affective_events(text, source_id=source_id, noah_authored=authored)


def test_relationship_is_history_not_a_name():
    # love + cost + commitment across turns -> accumulated structure, not one label
    evs = _events("I love Ashley. I will protect Ashley even when it costs me. "
                  "I promise I will stay with Ashley forever.")
    r = rs.build_relationship("Ashley", evs, role="WIFE (SOV2)")
    assert r.shared_event_count >= 1
    assert r.attachment in ("present", "established", "deep")
    assert r.attachment_receipts, "must keep the raw receipts that built attachment"
    assert r.role == "WIFE (SOV2)"


def test_no_sentiment_float_in_relationship_schema():
    r = rs.build_relationship("X", [])
    for v in r.to_dict().values():
        assert not isinstance(v, float), "relationships carry NO sentiment floats"


def test_holes_preserved_when_evidence_absent():
    r = rs.build_relationship("Nobody", [])
    assert r.shared_event_count == 0
    assert any("no affective events" in h for h in r.holes)
    assert any("candidate" in h for h in r.holes)   # never auto-canon


def test_sacrifice_requires_love_with_cost():
    evs = _events("If I can't give my family financial stability, then I will give them love.")
    r = rs.build_relationship("family", evs)
    assert r.sacrifices, "love-under-constraint must register as a sacrifice for that target"


def test_pity_does_not_build_attachment():
    # CHARITY_PITY is rejected by Noah; it must not count as attachment/love
    evs = _events("I gave Marcus pity and crumbs, nothing more.", authored=True)
    r = rs.build_relationship("Marcus", evs)
    # pity events exist but attachment (love/selfless/benevolence) should not be inflated by them
    assert r.attachment == "none" or not any("pity" in x.lower() for x in r.attachment_receipts)


def test_lived_and_fiction_attachment_never_conflate():
    lived = _events("I love Ashley more than my own life.",
                    source_id="journals_repo/entry.txt")
    fic = _events("Ellie loved her Scala with her whole heart.",
                  source_id="renderedreality/drakin/ch1.txt")
    rl = rs.build_relationship("Ashley", lived, role="WIFE")
    rf = rs.build_relationship("Ellie", fic, role="heroine", aliases=["Ellie.AI"])
    assert rl.lived_attachment != "none" and rl.fiction_attachment == "none"
    assert rf.fiction_attachment != "none" and rf.lived_attachment == "none"
    assert "fiction" in rf.current_state and "lived" in rl.current_state


def test_current_state_is_qualitative_never_a_score():
    evs = _events("I love my son Ender. We fought but I forgave him and stayed.")
    r = rs.build_relationship("Ender", evs, role="SON")
    assert isinstance(r.current_state, str) and r.current_state != "UNKNOWN"
    assert r.current_state != "insufficient evidence"
