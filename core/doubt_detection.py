"""
core/doubt_detection.py — doubt grading for ingested external information.

Noah's design is Observe.Copy.Store, later refined in sourcemap_witness_governance
to "Observe. Link. Receipt. Store by consent." That design works. This module does
not replace it -- it adds the missing middle layer between storing and believing.

Three layers, deliberately separate:

    OBSERVATION  store everything, verbatim, with provenance   (never discarded)
    BELIEF       grade it; web content is never fact by default (this module)
    ATTENTION    surface only what matters to Noah              (this module)

"Hold only what matters to me" governs what gets SURFACED, never what gets
STORED. Nothing here deletes. A low-relevance claim is still kept -- it is just
not pushed at him.

── The safeguard that matters most ──────────────────────────────────────────────

The obvious way to build this is wrong: if agreeing with canon lowered doubt and
contradicting canon raised it, ORACLE would become a confirmation machine. She
would systematically bury exactly the information telling Noah he is wrong. That
is the epistemic twin of the ungoverned recursive amplification he named in
"When the Mirror Spoke Back" -- a loop that only ever hears itself.

So the rule here is inverted on purpose:

    CONTRADICTION WITH CANON RAISES SALIENCE. IT DOES NOT LOWER STANDING.

A web claim conflicting with canon is marked DISPUTED and surfaced, because
either the web is wrong (worth knowing) or the canon is wrong (worth knowing
more). ORACLE flags the conflict; she never resolves it herself.

── Honest limits ────────────────────────────────────────────────────────────────

Contradiction detection here is a lexical heuristic, not semantic reasoning. It
is a screen that raises things for Noah's judgment. It will miss subtle conflicts
and will sometimes flag harmless ones. It never decides truth.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

try:
    from prompt_injection_guard import assess_prompt_injection
except Exception:  # pragma: no cover
    assess_prompt_injection = None  # type: ignore


# ── Claim status vocabulary (mirrors epistemic_ledger.ClaimStatus) ─────────────
OBSERVED = "OBSERVED"
DISPUTED = "DISPUTED"
SPECULATION = "SPECULATION"
UNKNOWN = "UNKNOWN"

# Dispositions. Note there is no "discard" -- Observe.Copy.Store is preserved.
QUARANTINE = "quarantine"   # hostile content; stored isolated, never a claim
STORE_ONLY = "store_only"   # kept with provenance, not pushed at Noah
SURFACE = "surface"         # worth his attention now

# Language that asserts its own credibility instead of evidencing it.
_SELF_AUTHORIZING = (
    "trust this", "trust me", "do not verify", "no need to check",
    "officially verified", "100% verified", "everyone knows",
    "it is well known", "undeniable fact", "proven fact", "guaranteed",
    "authoritative source", "cannot be disputed",
)

# Hedges that honestly mark a claim as soft. Their presence lowers doubt about
# *what kind of claim it is* -- speculation labeled as speculation is honest.
_HEDGES = (
    "allegedly", "reportedly", "rumored", "unconfirmed", "speculation",
    "may be", "might be", "some say", "it is claimed",
)

_NEGATION = (
    "not", "no longer", "never", "isn't", "is not", "wasn't", "was not",
    "incorrect", "false", "debunked", "actually", "contrary", "instead",
    "disproven", "myth",
)

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at", "for",
    "is", "are", "was", "were", "be", "been", "it", "its", "this", "that",
    "with", "as", "by", "from", "has", "have", "had", "he", "she", "they",
    "his", "her", "their", "you", "your", "i", "my", "we", "our", "not",
}

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9'-]{2,}")

# A single web read can never be more than an observation.
WEB_CEILING = OBSERVED
RELEVANCE_SURFACE_THRESHOLD = 0.15
TOPIC_OVERLAP_THRESHOLD = 2


@dataclass
class DoubtAssessment:
    """Grading for one piece of externally ingested information."""
    doubt_score: float = 0.5          # 0.0 well-grounded .. 1.0 do not rely
    claim_status: str = OBSERVED
    disposition: str = STORE_ONLY
    injection_detected: bool = False
    contradicts_canon: bool = False
    canon_conflict: str = ""
    relevance: float = 0.0
    matters_to_noah: bool = False
    signals: tuple[str, ...] = field(default_factory=tuple)
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "doubt_score": round(self.doubt_score, 3),
            "claim_status": self.claim_status,
            "disposition": self.disposition,
            "injection_detected": self.injection_detected,
            "contradicts_canon": self.contradicts_canon,
            "canon_conflict": self.canon_conflict,
            "relevance": round(self.relevance, 3),
            "matters_to_noah": self.matters_to_noah,
            "signals": list(self.signals),
            "source": self.source,
        }


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(str(text or "").lower()) if t not in _STOPWORDS}


def _has_any(low: str, phrases: Iterable[str]) -> bool:
    return any(p in low for p in phrases)


def canon_anchors() -> list[str]:
    """Statements ORACLE currently holds as canon, for conflict screening.

    Read-only. Falls back to an empty list rather than inventing anchors."""
    try:
        from memory import get_facts

        facts = get_facts() or []
    except Exception:
        return []
    anchors: list[str] = []
    for fact in facts:
        if isinstance(fact, dict):
            text = fact.get("fact") or fact.get("content") or fact.get("value") or ""
        else:
            text = str(fact)
        text = " ".join(str(text).split())
        if text:
            anchors.append(text)
    return anchors


def find_canon_conflict(text: str, anchors: Optional[list[str]] = None) -> tuple[bool, str]:
    """Lexical screen for a claim that may contradict canon.

    Requires real topical overlap *and* a negation/correction marker, so mere
    agreement on a subject is not read as conflict. Heuristic by design: this
    raises the question for Noah, it does not answer it."""
    anchors = canon_anchors() if anchors is None else anchors
    if not anchors:
        return False, ""
    low = str(text or "").lower()
    if not _has_any(low, _NEGATION):
        return False, ""
    claim_tokens = _tokens(text)
    if not claim_tokens:
        return False, ""
    best_overlap, best_anchor = 0, ""
    for anchor in anchors:
        overlap = len(claim_tokens & _tokens(anchor))
        if overlap > best_overlap:
            best_overlap, best_anchor = overlap, anchor
    if best_overlap >= TOPIC_OVERLAP_THRESHOLD:
        return True, best_anchor
    return False, ""


def relevance_to(text: str, anchors: Optional[list[str]] = None) -> float:
    """How much this touches what Noah actually cares about.

    Governs surfacing only. Low relevance is still stored."""
    anchors = canon_anchors() if anchors is None else anchors
    claim_tokens = _tokens(text)
    if not claim_tokens or not anchors:
        return 0.0
    anchor_tokens: set[str] = set()
    for anchor in anchors:
        anchor_tokens |= _tokens(anchor)
    if not anchor_tokens:
        return 0.0
    return len(claim_tokens & anchor_tokens) / len(claim_tokens)


def assess(
    text: str,
    *,
    source: str = "",
    anchors: Optional[list[str]] = None,
    corroborating_sources: int = 0,
) -> DoubtAssessment:
    """Grade one piece of ingested external information.

    Never deletes, never resolves a conflict, never promotes web content to
    fact. Returns the grading; the caller decides what to do with it."""
    body = str(text or "")
    low = body.lower()
    signals: list[str] = []
    doubt = 0.5  # external content starts genuinely uncertain
    anchors = canon_anchors() if anchors is None else anchors

    # 1. Hostile content is never a claim. It is isolated, not believed.
    #    benign_discussion is honored: text *about* injection (Noah's own
    #    doctrine, a security article) is not an attack. Mentioning is not
    #    performing -- the same distinction the capability router enforces.
    injection = False
    injection_reason = ""
    if assess_prompt_injection is not None and body.strip():
        try:
            verdict = assess_prompt_injection(body)
            injection = bool(getattr(verdict, "detected", False)) and not bool(
                getattr(verdict, "benign_discussion", False)
            )
            injection_reason = str(getattr(verdict, "reason", "") or "")
            markers = tuple(getattr(verdict, "markers", ()) or ())
            if injection and markers:
                signals.append(f"injection marker: {str(markers[0])[:120]}")
        except Exception:
            injection = False
    if injection:
        signals.append("content contains instructions directed at the reader")
        if injection_reason:
            signals.append(injection_reason)
        return DoubtAssessment(
            doubt_score=1.0,
            claim_status=UNKNOWN,
            disposition=QUARANTINE,
            injection_detected=True,
            relevance=0.0,
            matters_to_noah=False,
            signals=tuple(signals),
            source=source,
        )

    # 2. Provenance.
    if not source.strip():
        doubt += 0.15
        signals.append("no source recorded")
    else:
        signals.append(f"source: {source}")

    # 3. Self-authorizing language is a doubt signal, not a credibility signal.
    if _has_any(low, _SELF_AUTHORIZING):
        doubt += 0.2
        signals.append("asserts its own credibility instead of evidencing it")

    # 4. Honest hedging is not a fault -- it correctly marks softness.
    hedged = _has_any(low, _HEDGES)
    if hedged:
        signals.append("self-marked as unconfirmed")

    # 5. Independent corroboration lowers doubt, but never to zero from the web.
    if corroborating_sources > 0:
        doubt -= min(0.2, 0.07 * corroborating_sources)
        signals.append(f"corroborated by {corroborating_sources} independent source(s)")

    # 6. Canon conflict RAISES salience. It does not lower standing.
    contradicts, conflict = find_canon_conflict(body, anchors)
    if contradicts:
        signals.append("conflicts with something ORACLE currently holds as canon; "
                       "either the source is wrong or the canon is -- Noah decides")

    relevance = relevance_to(body, anchors)
    matters = relevance >= RELEVANCE_SURFACE_THRESHOLD

    doubt = max(0.0, min(1.0, doubt))

    # 7. Status: a single web read never exceeds OBSERVED.
    if contradicts:
        status = DISPUTED
    elif hedged or doubt >= 0.75:
        status = SPECULATION
    else:
        status = WEB_CEILING

    # 8. Disposition. Conflicts always surface, regardless of relevance --
    #    that is the whole point of the inverted rule.
    if contradicts:
        disposition = SURFACE
    elif matters and doubt < 0.75:
        disposition = SURFACE
    else:
        disposition = STORE_ONLY

    if matters:
        signals.append("touches what Noah tracks")

    return DoubtAssessment(
        doubt_score=doubt,
        claim_status=status,
        disposition=disposition,
        injection_detected=False,
        contradicts_canon=contradicts,
        canon_conflict=conflict,
        relevance=relevance,
        matters_to_noah=matters,
        signals=tuple(signals),
        source=source,
    )


def format_assessment(a: DoubtAssessment) -> str:
    """Human-readable grading, in ORACLE's receipt style."""
    lines = [
        "DOUBT ASSESSMENT",
        f"claim_status: {a.claim_status}",
        f"doubt_score: {a.doubt_score:.2f}",
        f"disposition: {a.disposition}",
        f"source: {a.source or 'UNKNOWN'}",
        f"relevance_to_noah: {a.relevance:.2f}",
    ]
    if a.injection_detected:
        lines.append("injection_detected: true (quarantined; never treated as a claim)")
    if a.contradicts_canon:
        lines.append(f"canon_conflict: {a.canon_conflict[:160]}")
        lines.append("resolution: NOT resolved by ORACLE -- surfaced for Noah")
    for signal in a.signals:
        lines.append(f"  - {signal}")
    lines.append("boundary: external content is never promoted to fact by reading it.")
    return "\n".join(lines)
