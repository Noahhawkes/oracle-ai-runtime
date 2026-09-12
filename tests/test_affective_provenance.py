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


def test_love_under_constraint_is_love_with_action_and_cost():
    e = ap.extract_affective_events(
        "If I can't give my family financial stability, then I will give them love.",
        source_id="t1")
    assert e, "should harvest at least one event"
    ev = e[0]
    assert ev.virtue_family == "LOVE"
    assert ev.has_action and ev.has_cost           # value-to-action + cost captured
    assert "family" in ev.target.lower()
    assert ev.exact_text                            # raw receipt preserved


def test_pity_never_conflated_with_selfless_charity():
    e = ap.extract_affective_events(
        "I am not asking for pity. I trade flame for flame, not charity for crumbs.",
        source_id="t2")
    fams = {x.virtue_family for x in e}
    assert "CHARITY_PITY" in fams
    assert "CHARITY_SELFLESS_LOVE" not in fams      # the two must never merge


def test_faith_is_recognized_at_the_edge_of_proof():
    e = ap.extract_affective_events(
        "For the first time I answered yes. 100% yes, eternal life is real. I believe in God.",
        source_id="t3")
    assert any(x.virtue_family == "FAITH" for x in e)


def test_holes_are_preserved_not_invented():
    e = ap.extract_affective_events("Someone gave without needing credit that day.",
                                    source_id="t4", noah_authored=False)
    ev = next(x for x in e if x.virtue_family.startswith("CHARITY"))
    assert "authorship not confirmed as Noah's own words" in ev.holes
    assert ev.target == "UNKNOWN" and any("target" in h for h in ev.holes)


def test_no_sentiment_float_anywhere_in_the_schema():
    ev = ap.AffectiveEvent(source_id="s", exact_text="x", virtue_family="LOVE")
    for v in ev.to_dict().values():
        assert not isinstance(v, float), "affective events must carry NO sentiment floats"


def test_summary_is_counts_not_magnitudes():
    e = ap.extract_affective_events(
        "I love Ashley. I will protect my sons. I hope for a better future.", source_id="t6")
    s = ap.summarize(e)
    assert s["total"] == len(e)
    assert "NOT sentiment" in s["note"]
