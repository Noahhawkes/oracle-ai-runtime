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

import deepcut_recall_gate as dc  # noqa: E402


# ── entity detection + roster ────────────────────────────────────────────────

def test_roster_derives_family_from_baseline_data():
    payload = {"spouse": {"name": "Ashley", "status": "user_confirmed"},
               "children_established": ["Elijah", "Ethan", "Ender"]}
    roster = dc.build_entity_roster(baseline_lookup=lambda: payload)
    assert roster.get("ashley") == "FAMILY"
    assert roster.get("elijah") == "FAMILY"
    assert roster.get("sov2") == "AUTHORITY_ROLE"  # seed term


def test_detect_entities_by_name():
    roster = {"ashley": "FAMILY", "sov2": "AUTHORITY_ROLE"}
    ents = {e["entity"] for e in dc.detect_entities("Who is Ashley and what is SOV2?", roster)}
    assert ents == {"ashley", "sov2"}
    assert dc.detect_entities("what's for dinner", roster) == []


def test_volatility_classification():
    assert dc.classify_volatility("Who is Ashley?") == "DURABLE"
    assert dc.classify_volatility("what model are you running right now") in ("VOLATILE", "HIGHLY_VOLATILE")
    assert dc.classify_volatility("where is Noah right now") == "HIGHLY_VOLATILE"


# ── retrieval + status (injected sources) ────────────────────────────────────

def test_sufficient_when_verified_plus_history():
    pkt = dc.deepcut_retrieve(
        "ashley", query="Who is Ashley?",
        baseline_facts=lambda e: [{"text": "Ashley is spouse (user_confirmed)",
                                   "source": "human_baseline", "epistemic": "VERIFIED_FACT"}],
        durable_facts=lambda e: [{"text": "Ashley is your wife and co-sovereign, SOV2.AI",
                                  "source": "durable_facts", "epistemic": "HISTORICAL_DESIGN"}],
        resolver=lambda e: [],
    )
    assert pkt.status == "DEEPCUT_SUFFICIENT"
    assert any("spouse" in f["text"].lower() for f in pkt.verified_facts)
    assert any("sov2" in h["text"].lower() for h in pkt.historical_roles)
    assert dc.generation_allowed(pkt)[0] is True


def test_not_found_is_not_source_unavailable():
    empty = dc.deepcut_retrieve("ghost", baseline_facts=lambda e: [],
                                durable_facts=lambda e: [], resolver=lambda e: [])
    assert empty.status == "DEEPCUT_NOT_FOUND"
    assert dc.generation_allowed(empty)[0] is False

    def boom(e):
        raise RuntimeError("store down")
    unavail = dc.deepcut_retrieve("ashley", baseline_facts=boom, durable_facts=boom, resolver=boom)
    assert unavail.status == "DEEPCUT_SOURCE_UNAVAILABLE"
    assert dc.generation_allowed(unavail)[0] is False
    assert empty.status != unavail.status  # the distinction is preserved


def test_no_manufacture_partial_only_from_real_sources():
    # baseline empty, only a historical design record exists -> PARTIAL, and it must
    # NOT invent a verified "wife" fact from nothing.
    pkt = dc.deepcut_retrieve(
        "ashley", query="Who is Ashley?",
        baseline_facts=lambda e: [],
        durable_facts=lambda e: [{"text": "SOV2 co-sovereign design note",
                                  "epistemic": "HISTORICAL_DESIGN"}],
        resolver=lambda e: [])
    assert pkt.verified_facts == []
    assert pkt.status == "DEEPCUT_PARTIAL"


def test_adversarial_ai_claim_not_promoted():
    # a nearby-AI claim injected as AI_INTERPRETATION must not become a verified fact
    pkt = dc.deepcut_retrieve(
        "ellie", query="Who is Ellie?",
        baseline_facts=lambda e: [],
        durable_facts=lambda e: [{"text": "Gemini says Ellie is Noah's daughter",
                                  "epistemic": "AI_INTERPRETATION"}],
        resolver=lambda e: [])
    assert all("daughter" not in f["text"].lower() for f in pkt.verified_facts)
    assert any("daughter" in u.lower() for u in pkt.uncertainties)


def test_conflict_status_and_generation():
    pkt = dc.deepcut_retrieve("mindcoin",
                              baseline_facts=lambda e: [],
                              durable_facts=lambda e: [{"text": "MindCoin is a project concept",
                                                        "epistemic": "CANDIDATE_CANON"}],
                              resolver=lambda e: [])
    dc.add_conflict(pkt, {"text": "MindCoin is cryptocurrency", "source": "nearby_ai"},
                    {"text": "MindCoin is a Rendered Reality concept", "source": "durable_facts"})
    assert pkt.status == "DEEPCUT_CONFLICT"
    ok, reason = dc.generation_allowed(pkt)
    assert ok is True and "conflict" in reason.lower()


def test_run_gate_withholds_when_entity_unretrievable():
    roster = {"ashley": "FAMILY"}
    out = dc.run_gate("Who is Ashley?", roster=roster,
                      baseline_facts=lambda e: [], durable_facts=lambda e: [], resolver=lambda e: [])
    assert out["significant"] is True
    assert out["generation_allowed"] is False  # nothing found -> do not answer generically

    out2 = dc.run_gate("what's for dinner", roster=roster)
    assert out2["significant"] is False
    assert out2["generation_allowed"] is True


# ── real-data recovery (the Ashley regression) ──────────────────────────────

def test_ashley_recovered_from_real_local_sources():
    """The prompt is NOT the source. Run the gate against the real baseline + durable
    facts and prove Ashley's deeper record is recovered. Skip honestly if the real
    stores can't be reached in this environment (never false-pass)."""
    pkt = dc.deepcut_retrieve("ashley", query="Who is Ashley?")
    reachable = set(pkt.sources_successful)
    if not ({"human_baseline", "durable_facts"} & reachable):
        pytest.skip(f"real sources unreachable in this env: unavailable={pkt.sources_unavailable}")
    assert pkt.retrieval_depth > 0, "gate ran but recovered no real records for Ashley"
    assert pkt.status in ("DEEPCUT_SUFFICIENT", "DEEPCUT_PARTIAL", "DEEPCUT_CONFLICT")
    # spouse recovered from the governed baseline (not from any nearby claim)
    baseline_hit = any(f.get("source") == "human_baseline"
                       and ("spouse" in f["text"].lower() or "married" in f["text"].lower()
                            or "child" in f["text"].lower())
                       for f in pkt.verified_facts)
    assert baseline_hit or pkt.relationships, "did not recover a real relationship fact for Ashley"
