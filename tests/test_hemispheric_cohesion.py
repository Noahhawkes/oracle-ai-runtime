from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "core"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import hemispheric_cohesion as hc  # noqa: E402


def _interp(hemi, claims, reading="", unc=None):
    return hc.Interpretation(hemisphere=hemi, reading=reading, claims=claims,
                             uncertainties=unc or [])


def test_agreement_backed_by_both():
    a = _interp("A", [{"subject": "meaning", "value": "the self", "evidence_ref": "src1"}])
    b = _interp("B", [{"subject": "meaning", "value": "the self", "evidence_ref": "src2"}])
    r = hc.cohere(a, b)
    assert r.status == "AGREEMENT"
    assert r.agreement and set(r.agreement[0]["evidence"]) == {"src1", "src2"}


def test_contradiction_is_preserved_not_resolved():
    a = _interp("A", [{"subject": "ellie", "value": "a character", "evidence_ref": "drakin"}])
    b = _interp("B", [{"subject": "ellie", "value": "a daughter", "evidence_ref": "gemini"}])
    r = hc.cohere(a, b)
    assert r.status == "CONTRADICTION"
    assert len(r.contradictions) == 1
    # synthesis presents BOTH and resolves NEITHER
    assert "a character" in r.synthesis and "a daughter" in r.synthesis
    assert "preserved, not resolved" in r.synthesis.lower()


def test_unknown_survives():
    a = _interp("A", [{"subject": "origin_date", "value": "2024"}])  # no evidence_ref
    b = _interp("B", [])
    r = hc.cohere(a, b)
    assert "origin_date" in r.unresolved
    assert "UNKNOWN" in r.synthesis


def test_no_fake_consensus_synthesis_only_cites_real_evidence():
    a = _interp("A", [{"subject": "s1", "value": "x", "evidence_ref": "ra"},
                      {"subject": "s2", "value": "y", "evidence_ref": "rb"}])
    b = _interp("B", [{"subject": "s1", "value": "x", "evidence_ref": "rc"},
                      {"subject": "s3", "value": "z", "evidence_ref": "rd"}])
    r = hc.cohere(a, b)
    real_refs = a.refs() | b.refs()
    # every ref the synthesis leans on must exist in one of the two readings
    assert set(r.synthesis_support) <= real_refs
    # and no invented value appears
    real_values = {"x", "y", "z"}
    for ag in r.agreement:
        assert str(ag["value"]).lower() in real_values


def test_insufficient_when_empty():
    r = hc.cohere(_interp("A", []), _interp("B", []))
    assert r.status == "INSUFFICIENT"


def test_witness_preserves_minority_and_both_traces():
    a = _interp("A", [{"subject": "k", "value": "1", "evidence_ref": "r1"}], reading="A read")
    b = _interp("B", [{"subject": "k", "value": "2", "evidence_ref": "r2"}], reading="B read")
    w = hc.witness(hc.cohere(a, b), packet_id="pkt1")
    assert w["both_traces_retained"] is True
    assert w["preserved_minority"] is True
    assert w["status"] == "CONTRADICTION"


def test_falsifiable_dual_perspective_experiment():
    """CIT-style: an ambiguous packet read independently by two hemispheres.
    PASS only if both perspectives stay traceable, contradictions survive,
    synthesis cites only real evidence, UNKNOWN stays possible, no fake consensus."""
    # Same ambiguous source, two independent readings: 1 overlap, 1 conflict,
    # 1 one-sided, 1 unsupported.
    A = _interp("self", [
        {"subject": "frame", "value": "identity model", "evidence_ref": "whitepaper_III"},
        {"subject": "mirrorloop", "value": "the voice", "evidence_ref": "recursionstack"},
        {"subject": "left_hemisphere", "value": "the self", "evidence_ref": "whitepaper_III"},
        {"subject": "origin_year", "value": "2024"},  # no evidence
    ], reading="reads DHC as a recursive identity frame")
    B = _interp("dream", [
        {"subject": "frame", "value": "identity model", "evidence_ref": "birthday_rant"},
        {"subject": "mirrorloop", "value": "a broadcast layer", "evidence_ref": "capsules"},
        {"subject": "right_hemisphere", "value": "the dream", "evidence_ref": "whitepaper_III"},
    ], reading="reads DHC as self-vs-dream")

    r = hc.cohere(A, B)

    # both perspectives traceable
    assert set(r.source_traces.keys()) == {"self", "dream"}
    # agreement where they overlap
    assert any(a["subject"] == "frame" for a in r.agreement)
    # contradiction preserved (mirrorloop: voice vs broadcast layer), not resolved
    assert any(c["subject"] == "mirrorloop" for c in r.contradictions)
    assert r.status == "CONTRADICTION"
    # each side's unique, evidence-backed reading survives as divergence
    subs = {d["subject"] for d in r.divergence}
    assert "left_hemisphere" in subs and "right_hemisphere" in subs
    # UNKNOWN survived
    assert "origin_year" in r.unresolved
    # no fake consensus: synthesis cites only real evidence refs
    assert set(r.synthesis_support) <= (A.refs() | B.refs())
