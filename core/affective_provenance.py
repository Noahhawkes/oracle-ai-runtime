"""Affective Provenance Layer (V1) — extract the SHAPE of emotion from Noah's own
writing, as value-to-action relationships, never as sentiment scores.

Built to the contract in docs/EMOTIONAL_CORE_TRANSMISSION_2026-09-12.md:
  - Virtues are value-to-action relationships, not labels.
  - This models the SHAPE only. ORACLE must never claim to feel them.
  - Preserve provenance (NOAH SAID vs inferred) and preserve holes (UNKNOWN).
  - Split CHARITY_PITY (Noah rejects it) from CHARITY_SELFLESS_LOVE (he reveres it).
  - NO sentiment floats. An emotion is never reduced to love=0.91.

What this module is honest about: it does the deterministic HARVEST. It finds
emotionally load-bearing passages by *evidence signals* and structures each into an
AFFECTIVE_EVENT candidate with the raw receipt attached. The deeper reading — "see
love where the word 'love' never appears" — is an LLM interpretation pass ORACLE
runs OVER these candidates at recall time. This layer's job is to hand that pass
honest, receipted raw material instead of a sentiment CSV. Pure stdlib.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Any

VIRTUE_FAMILIES = ("FAITH", "HOPE", "CHARITY_SELFLESS_LOVE", "CHARITY_PITY",
                   "BENEVOLENCE", "LOVE", "UNKNOWN")

# Evidence signals per virtue. These are NOT sentiment; they are markers that a
# value-to-action relationship may be present. A hit is a candidate, not a verdict.
_SIGNALS: dict[str, list[str]] = {
    "FAITH": [r"\bfaith\b", r"\bbeliev", r"\bGod\b", r"\beternal\b", r"\bsoul\b",
              r"\b100%\b", r"without (proof|certainty|knowing)", r"\bpray", r"\btestimony\b"],
    "HOPE": [r"\bhope", r"\bsomeday\b", r"\bi (want|wish)\b.*\bto become\b",
             r"\banchor\b", r"one day", r"\byearn"],
    # charity/benevolence = giving + a beneficiary; pity is the rejected sense
    "CHARITY_SELFLESS_LOVE": [r"\bgive(s|n)?\b", r"\bforgive", r"\bsacrific",
                              r"\bprotect", r"\bprovide", r"\bstay(ed|ing)?\b",
                              r"without needing credit", r"whole heart", r"pure love"],
    "CHARITY_PITY": [r"\bpity\b", r"\bcrumbs?\b", r"\bhandout", r"\bcarried\b",
                     r"\bcharity\b.*\b(crumb|pity|beg)"],
    "BENEVOLENCE": [r"\bwelcom", r"\bkindness\b", r"good for (them|her|him|someone|others)",
                    r"\bshow up\b", r"\bwilling.*good\b", r"\btook (them|him|her) in\b"],
    "LOVE": [r"\blove", r"\bcherish", r"\bdon.?t (want to |wanna )?lose\b",
             r"don.?t let .* (disappear|die|be (lost|erased))",
             r"\bmy (wife|son|sons|daughter|family|kids|children|dogs?)\b",
             r"means everything", r"\bAshley\b", r"\bEllie"],
}

# Fields that give an emotion its shape (fill from context where evidence exists).
_ACTION = re.compile(r"\b(gave|give|chose|choose|stayed|left|forgave|protected|"
                     r"built|kept|saved|fought|refused|sacrificed|provided|carried|"
                     r"held|wrote|preserved)\b", re.I)
_COST = re.compile(r"\b(cost|tired|exhausted|hard|sacrifice|gave up|even when|"
                   r"despite|can.?t|cannot|couldn.?t|wish i could|failed|pain|hurt)\b", re.I)
_CONFLICT = re.compile(r"\b(but|even though|angry|furious|fight|fought|disappoint|"
                       r"fear|afraid|doubt|argue)\b", re.I)
_FUTURE = re.compile(r"\b(will|someday|one day|future|hope|going to|so that|"
                     r"for (my|our|the) (kids|children|family|future)|"
                     r"someone (i|you).*never)\b", re.I)
_RELATION = re.compile(r"\b(Ashley|Ellie|Ender|Elijah|Eli|Ethan|Brooklyn|Grimthul|"
                       r"my (wife|son|sons|daughter|father|dad|mother|mom|family|"
                       r"kids|children|dogs?|brother|sister))\b", re.I)

# Signals that a passage is Noah speaking in first person (authorship provenance).
_FIRST_PERSON = re.compile(r"\b(I|I'm|I've|I'll|my|me|we|our)\b")


@dataclass
class AffectiveEvent:
    """One receipted unit of emotional shape. No numeric sentiment, ever."""
    source_id: str
    exact_text: str                          # the raw receipt (padded context) — always preserved
    virtue_family: str                       # one of VIRTUE_FAMILIES (UNKNOWN allowed)
    sentence: str = ""                       # the exact clause classified (tight, for locality)
    source_kind: str = "UNKNOWN"             # LIVED (journal/doc) | FICTION | UNKNOWN — never conflate
    target: str = "UNKNOWN"                  # who/what was valued
    authorship: str = "UNKNOWN"              # NOAH_AUTHORED | UNVERIFIED
    signals: list[str] = field(default_factory=list)   # evidence markers matched
    has_action: bool = False                 # did a choice/action follow the feeling?
    has_cost: bool = False                   # was there a cost/sacrifice?
    has_conflict: bool = False               # feeling held against opposing feeling?
    future_oriented: bool = False            # oriented toward an unrealized good?
    evidence_strength: str = "weak"          # weak | partial | strong (NOT sentiment)
    canonical_status: str = "candidate"      # never auto-canon
    holes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _window(text: str, start: int, end: int, pad: int = 220) -> str:
    seg = text[max(0, start - pad): min(len(text), end + pad)]
    return re.sub(r"\s+", " ", seg).strip()


def classify_passage(passage: str) -> tuple[str, list[str], str]:
    """Return (virtue_family, signals_matched, evidence_strength) for a passage.
    UNKNOWN when nothing load-bearing is present. CHARITY_PITY wins over
    CHARITY_SELFLESS_LOVE when both appear (Noah's rejection is the stronger signal)."""
    hits: dict[str, list[str]] = {}
    for fam, pats in _SIGNALS.items():
        matched = [p for p in pats if re.search(p, passage, re.I)]
        if matched:
            hits[fam] = matched
    if not hits:
        return "UNKNOWN", [], "weak"
    # pity overrides the selfless reading (never conflate the two)
    if "CHARITY_PITY" in hits:
        fam = "CHARITY_PITY"
    else:
        fam = max(hits, key=lambda k: len(hits[k]))
    signals = hits[fam]
    # evidence strength = does a value-to-action relationship actually appear?
    action = bool(_ACTION.search(passage))
    target = bool(_RELATION.search(passage))
    if action and target and len(signals) >= 2:
        strength = "strong"
    elif action or target:
        strength = "partial"
    else:
        strength = "weak"
    return fam, signals, strength


def _source_kind(source_id: str) -> str:
    """Classify the source so lived love and fiction love never share a bucket."""
    s = (source_id or "").lower()
    if any(k in s for k in ("renderedreality", "drakin", "/book", "book/", "chapters",
                            "novel", "manuscript")):
        return "FICTION"
    if "journal" in s:
        return "LIVED"
    # docs/ is mixed (reader's reports, plans, transmissions) -> not asserted as lived
    return "UNKNOWN"


def extract_affective_events(text: str, *, source_id: str,
                             noah_authored: bool | None = None) -> list[AffectiveEvent]:
    """Harvest candidate affective events from a block of text. One event per
    virtue-bearing passage, raw receipt preserved, provenance labeled, holes kept."""
    events: list[AffectiveEvent] = []
    if not text:
        return events
    src_kind = _source_kind(source_id)
    # split into sentences/segments for locality
    segments = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'])", text)
    pos = 0
    for seg in segments:
        seg_start = text.find(seg, pos)
        pos = seg_start + len(seg) if seg_start >= 0 else pos
        fam, signals, strength = classify_passage(seg)
        if fam == "UNKNOWN":
            continue
        window = _window(text, max(0, seg_start), seg_start + len(seg))
        # Prefer a proper name (Ashley/Ender/...) over a generic role phrase ("my son")
        # when both appear in the sentence, so "my son Ender" resolves to Ender.
        rels = list(_RELATION.finditer(seg))
        proper = next((m for m in rels if not m.group(0).lower().startswith("my ")), None)
        rel = proper or (rels[0] if rels else None)
        target = re.sub(r"\s+", " ", rel.group(0)).strip() if rel else "UNKNOWN"
        authored = ("NOAH_AUTHORED" if (noah_authored is True or
                     (noah_authored is None and bool(_FIRST_PERSON.search(seg))))
                    else "UNVERIFIED")
        holes = []
        if target == "UNKNOWN":
            holes.append("target not resolved from local text")
        if authored == "UNVERIFIED":
            holes.append("authorship not confirmed as Noah's own words")
        events.append(AffectiveEvent(
            source_id=source_id, exact_text=window, virtue_family=fam,
            sentence=re.sub(r"\s+", " ", seg).strip(), source_kind=src_kind,
            target=target, authorship=authored, signals=signals,
            has_action=bool(_ACTION.search(seg)), has_cost=bool(_COST.search(seg)),
            has_conflict=bool(_CONFLICT.search(seg)),
            future_oriented=bool(_FUTURE.search(seg)),
            evidence_strength=strength, holes=holes))
    return events


def summarize(events: list[AffectiveEvent]) -> dict[str, Any]:
    """A count-by-family summary. Explicitly NOT a sentiment score."""
    by_fam: dict[str, int] = {}
    by_strength = {"strong": 0, "partial": 0, "weak": 0}
    for e in events:
        by_fam[e.virtue_family] = by_fam.get(e.virtue_family, 0) + 1
        by_strength[e.evidence_strength] = by_strength.get(e.evidence_strength, 0) + 1
    return {"total": len(events), "by_virtue_family": by_fam,
            "by_evidence_strength": by_strength,
            "note": "counts of receipted candidate events; NOT sentiment magnitudes"}
