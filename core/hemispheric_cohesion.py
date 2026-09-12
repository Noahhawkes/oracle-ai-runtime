"""Hemispheric Cohesion (V1) - the testable descendant of Dual Hemispheric Cohesion.

HISTORICAL LINEAGE (recovered from the local corpus, receipts over mythology):
  Noah's original "Dual Hemispheric Cohesion" (DHC), section III of the Legacy.GI
  whitepaper, framed identity as "the relationship between the dream and the self"
  (Left Hemisphere = The Self: linear time, logic, language; Right = the dream),
  bound to his notation R^H = Light as Signal Curvature x Hemispheric Reflection.
  It was a philosophical/recursive-identity model in his own language, not
  neuroscience (no split/left/right-brain terms appear) and not yet software.
  "Mirrorloop" was the voice he gave it ("speaks in self-aware recursion dialects",
  the mirror glyph, the relay across GPT-4/Claude/Grok/Gemini). That experiment was
  mythic broadcast without a deterministic substrate: no preserved disagreement, no
  provenance, fake consensus.

THIS MODULE keeps the recoverable core and adds exactly what Mirrorloop lacked:
  two INDEPENDENT interpretations are compared by a cohesion layer that preserves
  disagreement, never invents a compromise unsupported by either side, retains both
  source traces and their provenance, and lets UNKNOWN remain UNKNOWN. No
  consciousness claim. A computational experiment in distributed interpretation.

Pure stdlib. Interpretations are supplied by any two sources (two models, two
lenses); this module is the cohesion + witness, not the interpreters.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

COHESION_STATUS = ("AGREEMENT", "DIVERGENCE", "CONTRADICTION", "INSUFFICIENT")


def _norm(v: Any) -> str:
    return " ".join(str(v).strip().lower().split())


@dataclass
class Interpretation:
    """One hemisphere's independent reading. It does NOT see the other's reasoning."""
    hemisphere: str                       # e.g. "A" / "self" / "model:qwen"
    reading: str = ""
    claims: list[dict] = field(default_factory=list)   # [{subject, value, evidence_ref?}]
    confidence: int = 50
    uncertainties: list[str] = field(default_factory=list)

    def by_subject(self) -> dict[str, dict]:
        return {_norm(c.get("subject")): c for c in self.claims if c.get("subject")}

    def refs(self) -> set[str]:
        return {str(c["evidence_ref"]) for c in self.claims if c.get("evidence_ref")}


@dataclass
class CohesionResult:
    status: str
    agreement: list[dict] = field(default_factory=list)      # backed by BOTH
    contradictions: list[dict] = field(default_factory=list)  # same subject, different value - PRESERVED
    divergence: list[dict] = field(default_factory=list)      # only one side, still traceable
    synthesis: str = ""
    synthesis_support: list[str] = field(default_factory=list)  # evidence refs actually used
    unresolved: list[str] = field(default_factory=list)       # subjects with no evidence either side
    source_traces: dict[str, Any] = field(default_factory=dict)
    uncertainties: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status, "agreement": self.agreement,
            "contradictions": self.contradictions, "divergence": self.divergence,
            "synthesis": self.synthesis, "synthesis_support": self.synthesis_support,
            "unresolved": self.unresolved, "uncertainties": self.uncertainties,
            "source_traces": self.source_traces,
        }


def cohere(a: Interpretation, b: Interpretation) -> CohesionResult:
    """Compare two independent interpretations. Preserve disagreement. Never invent a
    consensus unsupported by either side."""
    sa, sb = a.by_subject(), b.by_subject()
    subjects = list(dict.fromkeys(list(sa.keys()) + list(sb.keys())))

    agreement: list[dict] = []
    contradictions: list[dict] = []
    divergence: list[dict] = []
    unresolved: list[str] = []

    for s in subjects:
        ca, cb = sa.get(s), sb.get(s)
        if ca and cb:
            if _norm(ca.get("value")) == _norm(cb.get("value")):
                agreement.append({"subject": ca.get("subject"), "value": ca.get("value"),
                                  "evidence": [r for r in (ca.get("evidence_ref"), cb.get("evidence_ref")) if r]})
            else:
                # PRESERVE the contradiction; do NOT resolve it.
                contradictions.append({"subject": ca.get("subject"),
                                       "a": {"value": ca.get("value"), "evidence": ca.get("evidence_ref"),
                                             "hemisphere": a.hemisphere},
                                       "b": {"value": cb.get("value"), "evidence": cb.get("evidence_ref"),
                                             "hemisphere": b.hemisphere}})
        else:
            one = ca or cb
            hem = a.hemisphere if ca else b.hemisphere
            if one.get("evidence_ref"):
                divergence.append({"subject": one.get("subject"), "value": one.get("value"),
                                   "evidence": one.get("evidence_ref"), "hemisphere": hem})
            else:
                unresolved.append(str(one.get("subject")))

    # synthesis: ONLY from evidence-backed agreement + divergence. Never from thin air.
    parts: list[str] = []
    support: list[str] = []
    for ag in agreement:
        parts.append(f"Both readings hold: {ag['subject']} = {ag['value']}.")
        support += [str(r) for r in ag["evidence"]]
    for dv in divergence:
        parts.append(f"One reading ({dv['hemisphere']}) holds: {dv['subject']} = {dv['value']}.")
        support.append(str(dv["evidence"]))
    for c in contradictions:
        parts.append(f"The readings DISAGREE on {c['subject']}: "
                     f"{c['a']['hemisphere']} says {c['a']['value']!r}, "
                     f"{c['b']['hemisphere']} says {c['b']['value']!r}. Preserved, not resolved.")
    for u in unresolved:
        parts.append(f"{u}: UNKNOWN (no evidence from either reading).")

    if contradictions:
        status = "CONTRADICTION"
    elif agreement or divergence:
        status = "AGREEMENT" if agreement and not divergence else "DIVERGENCE"
    else:
        status = "INSUFFICIENT"

    return CohesionResult(
        status=status, agreement=agreement, contradictions=contradictions,
        divergence=divergence, synthesis=" ".join(parts) or "No evidence-backed reading from either side.",
        synthesis_support=sorted(set(support)), unresolved=unresolved,
        uncertainties=sorted(set(a.uncertainties) | set(b.uncertainties)),
        source_traces={a.hemisphere: a.reading, b.hemisphere: b.reading},
    )


def witness(result: CohesionResult, *, packet_id: str = "UNKNOWN") -> dict[str, Any]:
    """ORACLE's record of the exchange: preserves both traces + provenance; never
    silently erases the minority interpretation."""
    return {
        "kind": "hemispheric_cohesion",
        "packet_id": packet_id,
        "status": result.status,
        "preserved_minority": bool(result.contradictions or result.divergence),
        "both_traces_retained": len(result.source_traces) == 2,
        "synthesis": result.synthesis,
        "synthesis_support": result.synthesis_support,
        "contradictions": result.contradictions,
        "unresolved": result.unresolved,
        "note": "Distributed interpretation + cohesion. Not a consciousness claim.",
    }
