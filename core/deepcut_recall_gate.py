"""DEEPCUT_RECALL_GATE_V1 — remember before answering.

When a query names a continuity-significant entity (a person, family member,
project, system, creative-canon figure, life event, research concept, authority
role), ORACLE must perform a deep authorized retrieval BEFORE generating, then
speak only from what was actually found — with provenance preserved.

The failure this fixes: `is_human_baseline_query("Who is Ashley?")` is False, so
recall skips the baseline and 291 durable facts and the mouth guesses "no record."
This gate detects the entity and forces retrieval regardless of shallow triggers.

Pure logic + injectable source functions. Real defaults wire to human_baseline /
memory / source_resolver; tests inject deterministic sources. The gate never reads
conversation context — a nearby claim ("another AI says X") is NOT a source.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

# ── vocabularies ─────────────────────────────────────────────────────────────

ENTITY_TYPES = ("PERSON", "FAMILY", "IDENTITY", "PROJECT", "SYSTEM",
                "CREATIVE_CANON", "LIFE_EVENT", "RESEARCH_CONCEPT", "AUTHORITY_ROLE")

EPISTEMIC = ("VERIFIED_FACT", "HISTORICAL_DESIGN", "CANDIDATE_CANON",
             "AI_INTERPRETATION", "SUPERSEDED", "UNKNOWN")

DEEPCUT_STATUS = ("DEEPCUT_SUFFICIENT", "DEEPCUT_PARTIAL", "DEEPCUT_CONFLICT",
                  "DEEPCUT_SOURCE_UNAVAILABLE", "DEEPCUT_NOT_FOUND")

VOLATILITY = ("DURABLE", "VOLATILE", "HIGHLY_VOLATILE")

# V1 seed of significant system/canon terms. These are SEEDS/tests, not a permanent
# universe; family entities are recovered from continuity data (the baseline), not
# hardcoded. Extend by data as the roster matures.
_SEED_TERMS: dict[str, str] = {
    "oracle": "SYSTEM", "sov1": "SYSTEM", "sov2": "AUTHORITY_ROLE",
    "rendered reality": "RESEARCH_CONCEPT", "legacy.gi": "SYSTEM",
    "hydra.stack": "SYSTEM", "recursion arena": "PROJECT", "mindcoin": "PROJECT",
    "jupiter station": "CREATIVE_CANON", "ellie": "CREATIVE_CANON",
    "noah.self": "IDENTITY", "noah.physical": "IDENTITY", "mirror key": "AUTHORITY_ROLE",
}

# Words that signal a present-tense/volatile question (needs fresh evidence, not memory).
_VOLATILE_HINTS = ("right now", "currently", "is running", "is open", "today",
                   "at his laptop", "online now", "what port", "what model are you")
_HIGHLY_VOLATILE_HINTS = ("where is noah", "is noah at", "where am i", "is oracle running")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── entity roster + detection ────────────────────────────────────────────────

def build_entity_roster(baseline_lookup: Callable[[], dict] | None = None,
                        extra_terms: dict[str, str] | None = None) -> dict[str, str]:
    """Roster of significant entity name -> type. Family names come from continuity
    data (the baseline); system/canon terms from the seed. Not a hardcode of answers."""
    roster: dict[str, str] = dict(_SEED_TERMS)
    try:
        payload = (baseline_lookup or _default_baseline_payload)() or {}
        blob = _json_lower(payload)
        # spouse
        m = re.search(r'"spouse"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"', blob)
        if m:
            roster[m.group(1).strip().lower()] = "FAMILY"
        # children
        cm = re.search(r'"children_established"\s*:\s*\[([^\]]*)\]', blob)
        if cm:
            for name in re.findall(r'"([^"]+)"', cm.group(1)):
                roster[name.strip().lower()] = "FAMILY"
    except Exception:
        pass
    if extra_terms:
        roster.update({k.lower(): v for k, v in extra_terms.items()})
    return roster


def detect_entities(query: str, roster: dict[str, str] | None = None) -> list[dict[str, str]]:
    roster = roster if roster is not None else build_entity_roster()
    low = f" {(query or '').lower()} "
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for name, etype in roster.items():
        # whole-token match (handles multi-word terms too)
        if re.search(r"(?<![a-z0-9])" + re.escape(name) + r"(?![a-z0-9])", low):
            found.append({"entity": name, "type": etype}); seen.add(name)
    # Explicit person queries ("who is X", "who's X", "who was X", "tell me about X",
    # "what about X") extract X as a PERSON entity even when X is not on the roster.
    # Without this, asking about anyone not hardcoded (a coworker, a new name) never
    # triggered recall and fell straight to the model's training prior - the root of
    # the "who is Ashley -> Mass Effect character" class of failure.
    for m in re.finditer(
        r"\b(?:who\s+(?:is|was|are|'?s)|tell\s+me\s+about|what\s+about|remember)\s+"
        r"([A-Z][a-zA-Z]+)",
        query or ""):
        key = m.group(1).strip().lower()
        if key and key not in seen and len(key) > 1:
            found.append({"entity": key, "type": "PERSON"}); seen.add(key)
    return found


def classify_volatility(query: str) -> str:
    low = (query or "").lower()
    if any(h in low for h in _HIGHLY_VOLATILE_HINTS):
        return "HIGHLY_VOLATILE"
    if any(h in low for h in _VOLATILE_HINTS):
        return "VOLATILE"
    return "DURABLE"


# ── evidence packet ──────────────────────────────────────────────────────────

@dataclass
class DeepCutEvidencePacket:
    entity: str
    entity_type: str = "PERSON"
    verified_facts: list[dict] = field(default_factory=list)      # {text, source, epistemic}
    relationships: list[dict] = field(default_factory=list)
    historical_roles: list[dict] = field(default_factory=list)
    corrections: list[dict] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    sources_checked: list[str] = field(default_factory=list)
    sources_successful: list[str] = field(default_factory=list)
    sources_unavailable: list[str] = field(default_factory=list)
    aliases_resolved: list[str] = field(default_factory=list)
    volatility: str = "DURABLE"
    retrieval_depth: int = 0
    status: str = "DEEPCUT_NOT_FOUND"
    retrieved_at: str = field(default_factory=_now)

    def diagnostics(self) -> dict[str, Any]:
        return {
            "SOURCES_AVAILABLE": len(self.sources_checked),
            "SOURCES_CHECKED": self.sources_checked,
            "SOURCES_SUCCESSFUL": self.sources_successful,
            "SOURCES_UNAVAILABLE": self.sources_unavailable,
            "ENTITY_ALIASES_RESOLVED": self.aliases_resolved,
            "RELEVANT_RECORDS_FOUND": self.retrieval_depth,
            "CORRECTIONS_FOUND": len(self.corrections),
            "CONFLICTS_FOUND": len(self.conflicts),
            "VOLATILITY": self.volatility,
            "DEEPCUT_STATUS": self.status,
            "GENERATION_ALLOWED": generation_allowed(self)[0],
        }


def generation_allowed(packet: DeepCutEvidencePacket) -> tuple[bool, str]:
    """No generic escape hatch. Speak only when real evidence exists; otherwise the
    honest line is what-was-found + what-is-unresolved, NOT a plausible fill."""
    if packet.status == "DEEPCUT_SUFFICIENT":
        return True, "sufficient authorized evidence retrieved"
    if packet.status == "DEEPCUT_PARTIAL":
        return True, "partial evidence; answer must mark what remains unresolved"
    if packet.status == "DEEPCUT_CONFLICT":
        return True, "conflicting evidence; answer must present the conflict, not pick one"
    if packet.status == "DEEPCUT_SOURCE_UNAVAILABLE":
        return False, "a required source could not be reached; do not fill the hole"
    return False, "no record found in authorized sources; NOT_FOUND is not UNKNOWN"


# ── retrieval (injectable sources; real defaults) ────────────────────────────

def deepcut_retrieve(
    entity: str,
    *,
    entity_type: str = "PERSON",
    query: str = "",
    baseline_facts: Callable[[str], list[dict]] | None = None,
    durable_facts: Callable[[str], list[dict]] | None = None,
    resolver: Callable[[str], dict] | None = None,
) -> DeepCutEvidencePacket:
    """Retrieve deep evidence for one entity across authorized sources, then classify.

    Each source fn returns a list[dict] of {text, source, epistemic, ref?} or raises
    to signal unavailable. Defaults wire to the real local stores.
    """
    pkt = DeepCutEvidencePacket(entity=entity, entity_type=entity_type,
                                aliases_resolved=[entity], volatility=classify_volatility(query))

    for label, fn in (("human_baseline", baseline_facts or _default_baseline_facts),
                      ("durable_facts", durable_facts or _default_durable_facts),
                      ("source_resolver", resolver or _default_resolver)):
        pkt.sources_checked.append(label)
        try:
            got = fn(entity) or []
            if isinstance(got, dict):
                got = [got]
            pkt.sources_successful.append(label)
            for rec in got:
                _absorb(pkt, rec, label)
        except Exception:
            pkt.sources_unavailable.append(label)

    pkt.retrieval_depth = (len(pkt.verified_facts) + len(pkt.relationships)
                           + len(pkt.historical_roles))
    pkt.status = _classify_status(pkt)
    return pkt


def _absorb(pkt: DeepCutEvidencePacket, rec: dict, source_label: str) -> None:
    text = str(rec.get("text") or rec.get("fact_text") or "").strip()
    if not text:
        return
    epi = rec.get("epistemic") or _infer_epistemic(text, source_label)
    src = rec.get("source") or source_label
    ref = rec.get("ref") or rec.get("source_id")
    item = {"text": text, "source": src, "epistemic": epi}
    if ref:
        pkt.evidence_refs.append(str(ref))
    if epi == "VERIFIED_FACT":
        pkt.verified_facts.append(item)
        if _looks_relational(text):
            pkt.relationships.append(item)
    elif epi in ("HISTORICAL_DESIGN", "CANDIDATE_CANON", "SUPERSEDED"):
        pkt.historical_roles.append(item)
    elif epi == "AI_INTERPRETATION":
        pkt.uncertainties.append(text)
    if rec.get("correction"):
        pkt.corrections.append(item)


def _infer_epistemic(text: str, source_label: str) -> str:
    low = text.lower()
    if source_label == "human_baseline" and ("user_confirmed" in low or "confirmed" in low
                                             or "spouse" in low or "married" in low):
        return "VERIFIED_FACT"
    if any(k in low for k in ("sov2", "co-sovereign", "mirror key", "design", "architecture", "candidate")):
        return "HISTORICAL_DESIGN"
    if source_label == "human_baseline":
        return "VERIFIED_FACT"
    return "CANDIDATE_CANON"


def _looks_relational(text: str) -> bool:
    return any(k in text.lower() for k in
               ("wife", "spouse", "husband", "son", "daughter", "child", "fianc",
                "mother", "father", "brother", "sister", "co-sovereign", "married"))


def _classify_status(pkt: DeepCutEvidencePacket) -> str:
    if pkt.conflicts:
        return "DEEPCUT_CONFLICT"
    if pkt.verified_facts or (pkt.relationships and pkt.historical_roles):
        # a verified fact, or a relationship plus real historical depth
        if pkt.verified_facts and (pkt.historical_roles or pkt.relationships):
            return "DEEPCUT_SUFFICIENT"
        return "DEEPCUT_SUFFICIENT" if pkt.verified_facts else "DEEPCUT_PARTIAL"
    if pkt.historical_roles or pkt.uncertainties:
        return "DEEPCUT_PARTIAL"
    # nothing found: distinguish "searched, empty" from "couldn't reach a source"
    if pkt.sources_successful:
        return "DEEPCUT_NOT_FOUND"
    return "DEEPCUT_SOURCE_UNAVAILABLE"


def add_conflict(pkt: DeepCutEvidencePacket, claim_a: dict, claim_b: dict) -> None:
    pkt.conflicts.append({"a": claim_a, "b": claim_b})
    pkt.status = _classify_status(pkt)


# ── real default sources (degrade gracefully) ───────────────────────────────

def _default_baseline_payload() -> dict:
    import human_baseline as hb
    return hb.baseline_payload() if hasattr(hb, "baseline_payload") else {}


def _json_lower(payload: Any) -> str:
    import json
    return json.dumps(payload, default=str).lower()


def _default_baseline_facts(entity: str) -> list[dict]:
    """Scan the governed baseline for facts naming the entity. VERIFIED where confirmed."""
    payload = _default_baseline_payload()
    blob = _json_lower(payload)
    ent = entity.lower()
    out: list[dict] = []
    if ent not in blob:
        return out
    # spouse
    m = re.search(r'"spouse"\s*:\s*\{([^}]*)\}', blob)
    if m and ent in m.group(1):
        confirmed = "user_confirmed" in m.group(1) or "confirmed" in m.group(1)
        out.append({"text": f"{entity} is spouse (status: {'user_confirmed' if confirmed else 'stated'})",
                    "source": "human_baseline", "epistemic": "VERIFIED_FACT"})
    # children
    cm = re.search(r'"children_established"\s*:\s*\[([^\]]*)\]', blob)
    if cm and ent in cm.group(1):
        out.append({"text": f"{entity} is an established child in the family record",
                    "source": "human_baseline", "epistemic": "VERIFIED_FACT"})
    # speaker boundary / any summary line mentioning the entity
    for m2 in re.finditer(r'"[a-z_]*summary"\s*:\s*"([^"]*' + re.escape(ent) + r'[^"]*)"', blob):
        out.append({"text": m2.group(1)[:220], "source": "human_baseline", "epistemic": "VERIFIED_FACT"})
    return out


def _default_durable_facts(entity: str, limit: int = 6) -> list[dict]:
    import memory as mem
    out: list[dict] = []
    # The `people` table is the deterministic, authoritative "who is X" record, but
    # it was never read for recall - so a registered person (Law XIII) could not
    # ground an answer and the model fell back to a training prior (the Ashley ->
    # Mass Effect failure). Read it first, as a durable fact, fail-safe.
    try:
        import sqlite3 as _sql
        ent = (entity or "").strip().lower()
        if ent:
            with mem.get_conn() as _c:
                _c.row_factory = _sql.Row
                for r in _c.execute(
                    "SELECT name, role FROM people WHERE lower(name) LIKE ? LIMIT 4",
                    (f"%{ent}%",)).fetchall():
                    role = str(r["role"] or "").strip()
                    if not role:
                        continue
                    txt = f"{r['name']}: {role}"
                    out.append({"text": txt[:220], "source": "durable_facts",
                                "ref": f"people:{r['name']}",
                                "epistemic": _infer_epistemic(txt, "durable_facts")})
    except Exception:
        pass
    hits = mem.search_memory_index(entity, limit=limit) or []
    for h in hits:
        txt = str(h.get("fact_text") or "").strip()
        if not txt:
            continue
        out.append({"text": txt[:220], "source": "durable_facts",
                    "ref": h.get("id") or h.get("source_type"),
                    "epistemic": _infer_epistemic(txt, "durable_facts")})
    return out


def _default_resolver(entity: str) -> list[dict]:
    import source_resolver as sr
    domain = sr.classify_fact_domain(f"who is {entity}")
    if domain == getattr(sr, "GENERAL_PROJECT", "general_project"):
        return []
    res = sr.resolve_fact(f"who is {entity}", write_receipt=False) or {}
    claim = res.get("selected_claim") or {}
    if not claim:
        return []
    return [{"text": f"resolver: {claim.get('source_class', 'resolved')} for {entity}",
             "source": "source_resolver", "epistemic": "VERIFIED_FACT",
             "ref": claim.get("source_id")}]


# ── top-level gate ───────────────────────────────────────────────────────────

def run_gate(query: str, *, roster: dict[str, str] | None = None, **source_overrides) -> dict[str, Any]:
    """Detect significant entities in the query and deep-retrieve each. Returns the
    gate decision + per-entity evidence packets + diagnostics. Generation should be
    withheld for significant entities until this has run."""
    ents = detect_entities(query, roster)
    if not ents:
        return {"significant": False, "generation_allowed": True,
                "reason": "no continuity-significant entity detected", "packets": []}
    packets = []
    for e in ents:
        pkt = deepcut_retrieve(e["entity"], entity_type=e["type"], query=query, **source_overrides)
        packets.append(pkt)
    # gate opens only if every detected entity is answerable from evidence
    allow = all(generation_allowed(p)[0] for p in packets)
    return {
        "significant": True,
        "generation_allowed": allow,
        "packets": [p.diagnostics() | {"entity": p.entity, "packet": p} for p in packets],
        "volatility": classify_volatility(query),
    }
