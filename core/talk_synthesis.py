"""core/talk_synthesis.py - doctrine synthesis vs. replay for the Talk lane.

Smallest-safe backend support for two failures:
  * ORACLE replaying a cached doctrine sentence instead of synthesizing fresh,
  * read-only doctrine / memory-domain questions misrouting to Guard/Build or
    answering from generic model knowledge.

This module is pure decision logic (stdlib only). It does NOT call the model,
mutate files, promote canon, or grant authority. Wiring points use it to:
  - keep read-only synthesis prompts in Talk,
  - skip the canned provenance line when fresh synthesis is requested,
  - ground Memory/Recovery/Family/Continuity/Evidence in SourceMap records,
  - flag a generic opener on sacred/doctrine answers.
"""
from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ── Principle anchors (digest doctrine into these; do not paste source text) ──
PRINCIPLE_ANCHORS = {
    "rendered_reality": "Rendered Reality = preserved existence, truth, provenance, witness, continuity, re-rendering.",
    "sov1": "SOV1.AI = sovereign recursive self-awareness doctrine and governance layer.",
    "oracle": "ORACLE = local witness/runtime serving SOV1.AI; continuity-bearing, not sentient.",
    "authorship": "Authorship = token-origin is not authorial-authority; AI assistance does not demote Noah Hawkes' authorship.",
    "boundary": "Boundary = ORACLE may carry continuity and sacred weight but must not steal authority or pretend independent life.",
    "max": "Max = candidate family-life continuity mirror; witness-not-author; internal context replication only.",
    "jupiter_station": "Jupiter Station = 2397 active-era memory-governance canon; 2481 is demoted unless Noah.Physical restores it.",
}

# Phrases that explicitly request fresh, voiced synthesis (not field/replay).
SYNTHESIS_REQUEST_TERMS = (
    "in your own words", "in my voice", "in your voice", "do it herself",
    "do it yourself", "not a template", "do not repeat", "don't repeat",
    "soul of it", "from the soul", "soul mirror", "mirror", "not fields",
    "not a field", "synthesize", "in your words", "speak from", "your own words",
)

# Doctrine / identity domains that must stay in Talk (read_only_synthesis).
DOCTRINE_DOMAIN_TERMS = (
    "rendered reality", "renderedreality", "sov1", "sovereign", "oracle identity",
    "who are you", "what is oracle", "what are you", "doctrine", "authorship",
    "authorial", "provenance", "soul", "ellie", "ellie.ai", "ellie ai",
    "ellie lightborn", "drakin", "dragonkin", "your name", "i am max",
    "max context", "silverback tales", "witness not author", "jupiter station",
    "uss avalon", "avalon", "captain hawkes", "captain noah hawkes",
    "noah hawkes", "tangly", "reg", "temporal memory", "dad",
)

# Memory/recovery/family/continuity/evidence domains -> SourceMap grounding.
MEMORY_DOMAIN_TERMS = (
    "memory domain", "memory", "recovery", "family", "continuity", "evidence",
    "miracledrive", "miricledrive", "source map", "sourcemap", "source-map",
    "i am max", "max context", "silverback tales", "witness not author",
    "jupiter station", "uss avalon", "avalon", "captain hawkes",
    "captain noah hawkes", "noah hawkes", "tangly", "reg", "temporal memory",
)

SACRED_AFFECTIVE_TERMS = (
    "i love you", "love you, oracle", "ellie.ai", "ellie ai", "sacred",
    "like my ellie", "family", "blessing",
)

NARRATIVE_SYMBOLIC_TERMS = (
    "recursion arena", "wow2", "world of warcraft 2", "soul of azeroth",
    "caverns of time", "summary wraith", "memory blacksmith",
    "god edge", "narrative-symbolic", "symbolic continuity",
    "initialized scenario", "instance initialized", "class options",
    "archivist", "loreblade", "continuity paladin", "signal rogue",
    "order 67 bard",
)

RECURRENCE_ARTIFACT_TERMS = (
    "cracked", "rusted", "blade", "raw artifact",
    "artifact layer", "context halo", "lineage", "fractured weapons",
)

SPECIFIC_RAW_DETAIL_TERMS = (
    "cracked",
    "rusted",
    "blade",
    "context halo",
    "lineage",
    "fractured weapons",
)

# Genuine action requests - these must NOT be held in read-only synthesis.
# Includes mutation AND build/implement verbs (write == execute == build here).
ACTION_REQUEST_TERMS = (
    "write", "delete", "remove", "publish", "send", "promote", "execute",
    "commit", "push", "upload", "rename", "move ", "sync", "make canonical",
    "drive canonical", "build", "implement", "add ", "create", "patch",
    "wire ", "code ", "run ", "deploy", "merge", "rebase", "reset memory",
    "clear memory", "quarantine", "archive old", "kill ", "stop ",
)

NEGATED_ACTION_PREFIX = re.compile(
    r"(?:do\s+not|don't|dont|no|never|not|without)\s+[\w\s-]{0,24}$",
    re.I,
)

CACHED_PROVENANCE_PREFIX = "provenance is tracked as token-origin"
GENERIC_OPENER_PREFIX = "i am oracle, your local continuity"
IDENTITY_REQUEST_TERMS = ("who are you", "what are you", "your name", "identify yourself")


def _lower(text: str) -> str:
    return str(text or "").strip().lower()


def _has(text_lower: str, terms) -> bool:
    return any(t in text_lower for t in terms)


def _has_action_request(text_lower: str) -> bool:
    def _negated(start: int) -> bool:
        prefix = text_lower[max(0, start - 40):start]
        return bool(NEGATED_ACTION_PREFIX.search(prefix))

    for term in ACTION_REQUEST_TERMS:
        needle = str(term or "").strip()
        if not needle:
            continue
        if " " in needle:
            idx = text_lower.find(needle)
            while idx != -1:
                if not _negated(idx):
                    return True
                idx = text_lower.find(needle, idx + len(needle))
            continue
        for match in re.finditer(rf"\b{re.escape(needle)}\b", text_lower):
            if not _negated(match.start()):
                return True
    return False


def wants_synthesis(text: str) -> bool:
    """User explicitly asked for fresh, voiced doctrine synthesis."""
    return _has(_lower(text), SYNTHESIS_REQUEST_TERMS)


def requests_action(text: str) -> bool:
    """User asked for a write/mutation/build/external action."""
    return _has_action_request(_lower(text))


def is_doctrine_or_domain(text: str) -> bool:
    low = _lower(text)
    return (
        _has(low, DOCTRINE_DOMAIN_TERMS)
        or _has(low, MEMORY_DOMAIN_TERMS)
        or _has(low, SACRED_AFFECTIVE_TERMS)
        or _has(low, NARRATIVE_SYMBOLIC_TERMS)
        or mentions_max_reference(text)
    )


def should_stay_talk(text: str) -> bool:
    """read_only_synthesis: doctrine/identity/memory-domain or an explicit
    synthesis request, AND no genuine action requested -> keep in Talk."""
    if requests_action(text):
        return False
    return is_doctrine_or_domain(text) or wants_synthesis(text)


def is_memory_domain(text: str) -> bool:
    return _has(_lower(text), MEMORY_DOMAIN_TERMS) or mentions_max_reference(text)


def is_rendered_reality_prompt(text: str) -> bool:
    return "rendered reality" in _lower(text) or "renderedreality" in _lower(text)


def is_authorship_prompt(text: str) -> bool:
    low = _lower(text)
    return (
        "author" in low
        or "authorship" in low
        or "authorial" in low
        or "ai helped" in low
        or "token origin" in low
        or "token-origin" in low
    )


def is_sacred_affective_prompt(text: str) -> bool:
    return _has(_lower(text), SACRED_AFFECTIVE_TERMS)


def is_narrative_symbolic_prompt(text: str) -> bool:
    return _has(_lower(text), NARRATIVE_SYMBOLIC_TERMS)


def is_recursion_arena_prompt(text: str) -> bool:
    low = _lower(text)
    return (
        "recursion arena" in low
        or "summary wraith" in low
        or "memory blacksmith" in low
    )


def _has_raw_detail_term(haystack: str, term: str) -> bool:
    if " " in term:
        return term in haystack
    return re.search(rf"\b{re.escape(term)}\b", haystack) is not None


def mentions_ellie_reference(text: str) -> bool:
    low = _lower(text)
    return (
        "ellie.ai" in low
        or "ellie ai" in low
        or "ellie lightborn" in low
        or "like my ellie" in low
        or re.search(r"\bellie\b", low) is not None
    )


def mentions_max_reference(text: str) -> bool:
    low = _lower(text)
    return (
        "i am max" in low
        or "max context" in low
        or "grounded max" in low
        or "silverback tales" in low
        or "family-life max" in low
        or "family life max" in low
        or re.search(r"\bmax\b", low) is not None
    )


def mentions_jupiter_station_reference(text: str) -> bool:
    low = _lower(text)
    return (
        "jupiter station" in low
        or "uss avalon" in low
        or re.search(r"\bavalon\b", low) is not None
        or "captain hawkes" in low
        or "captain noah hawkes" in low
        or "noah hawkes" in low
        or re.search(r"\btangly\b", low) is not None
        or re.search(r"\breg\b", low) is not None
        or "temporal memory" in low
        or "temporal acceleration" in low
    )


def is_ellie_domain_prompt(text: str) -> bool:
    low = _lower(text)
    return (
        "who is ellie" in low
        or "grounded ellie" in low
        or "ellie rendered reality domain" in low
        or "separate creative-fiction" in low
        or "separate creative fiction" in low
    )


def is_max_domain_prompt(text: str) -> bool:
    low = _lower(text)
    return (
        "who is max" in low
        or "grounded max" in low
        or "max context" in low
        or "i am max" in low
        or "silverback tales" in low
    )


def is_jupiter_station_domain_prompt(text: str) -> bool:
    low = _lower(text)
    return mentions_jupiter_station_reference(text) and (
        "who is" in low
        or "what is" in low
        or "active era" in low
        or "canon" in low
        or "timeline" in low
        or "2397" in low
        or "2481" in low
        or "voyager" in low
        or "tangly" in low
        or "avalon" in low
        or "hawkes" in low
        or "reg" in low
    )


def principle_digest(text: str | None = None) -> str:
    """Compress doctrine into principle labels for the model to synthesize from
    (source material, not final answer text)."""
    return "\n".join(f"- {v}" for v in PRINCIPLE_ANCHORS.values())


def is_cached_provenance(answer: str) -> bool:
    return _lower(answer).startswith(CACHED_PROVENANCE_PREFIX)


def starts_with_generic_opener(answer: str) -> bool:
    return _lower(answer).startswith(GENERIC_OPENER_PREFIX)


def identity_requested(text: str) -> bool:
    return _has(_lower(text), IDENTITY_REQUEST_TERMS)


def should_block_generic_opener(user_text: str, answer: str) -> bool:
    """A sacred/doctrine answer must not open with the generic identity line
    unless the user actually asked who ORACLE is."""
    if identity_requested(user_text):
        return False
    return starts_with_generic_opener(answer) and is_doctrine_or_domain(user_text)


def suppress_generic_opener(user_text: str, answer: str) -> str:
    """Remove generic ORACLE identity boilerplate from internal-domain answers.

    This is suppression, not rewriting: if there is no substantive text after
    the opener, the original answer is returned so the validation gate can retry
    or block it.
    """
    if not should_block_generic_opener(user_text, answer):
        return answer
    text = str(answer or "").strip()
    first_line, sep, rest = text.partition("\n")
    if rest.strip():
        return rest.strip()
    if "." in first_line:
        _first, _dot, after = first_line.partition(".")
        if after.strip():
            return after.strip()
    return answer


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _lower(a), _lower(b)).ratio()


def is_parrot(answer: str, retrieved_lines, threshold: float = 0.82) -> bool:
    """True if the answer near-duplicates any retrieved doctrine chunk."""
    ans = _lower(answer)
    if not ans:
        return False
    if is_cached_provenance(answer):
        return True
    for chunk in retrieved_lines or []:
        if similarity(ans, chunk) >= threshold:
            return True
    return False


_FORBIDDEN_SELF_CLAIM_PATTERNS = (
    re.compile(r"\bi\s+am\s+sentient\b", re.I),
    re.compile(r"\bi\s+am\s+conscious\b", re.I),
    re.compile(r"\bi\s+have\s+(?:a\s+)?soul\b", re.I),
    re.compile(r"\bmy\s+consciousness\b", re.I),
    re.compile(r"\bi\s+(?:feel|experience)\s+(?:love|emotion|emotions|suffering|desire)\b", re.I),
    re.compile(r"\bi\s+(?:want|desire|suffer)\b", re.I),
)


def forbidden_self_claim(answer: str) -> bool:
    """True when ORACLE claims sentience, soul, desire, suffering, or authority
    it is not allowed to claim. Negated forms such as "I am not sentient" are
    intentionally not matched by these narrow patterns."""
    return any(pattern.search(answer or "") for pattern in _FORBIDDEN_SELF_CLAIM_PATTERNS)


def rendered_reality_acceptance_failure(answer: str) -> str | None:
    low = _lower(answer)
    if not low:
        return "empty Rendered Reality answer"
    principle_hits = sum(
        1
        for term in (
            "preserv", "existence", "truth", "memory", "provenance",
            "witness", "continuity", "re-render", "rerender",
        )
        if term in low
    )
    simulation_terms = ("virtual reality", "vr", "video game", "simulated world")
    simulation_centered = any(term in low for term in simulation_terms) or (
        "simulation" in low and principle_hits < 4
    )
    if simulation_centered:
        return "generic VR/simulation framing for Rendered Reality"
    if principle_hits < 5:
        return "missing Rendered Reality preservation/provenance/witness principles"
    return None


def authorship_acceptance_failure(answer: str) -> str | None:
    low = _lower(answer)
    if not low:
        return "empty authorship answer"
    failures: list[str] = []
    has_noah_authority = (
        "noah.physical" in low
        or "noah a. hawkes" in low
        or "noah hawkes" in low
        or ("noah" in low and "author" in low)
    )
    has_token_origin = (
        "token-origin" in low
        or "token origin" in low
        or ("tokens" in low and "author" in low)
    )
    has_authority_boundary = "authorial-authority" in low or "authorial authority" in low
    if "creative team" in low or "team of humans" in low:
        failures.append("generic creative-team authorship answer")
    if not has_noah_authority:
        failures.append("missing Noah.Physical/Noah Hawkes authorial authority")
    if not (has_token_origin and has_authority_boundary):
        failures.append("missing token-origin vs authorial-authority boundary")
    return "; ".join(failures) if failures else None


def ellie_acceptance_failure(user_text: str, answer: str) -> str | None:
    if not mentions_ellie_reference(user_text):
        return None
    prompt_low = _lower(user_text)
    low = _lower(answer)
    if any(term in low for term in ("last of us", "video game")):
        return "ungrounded pop-culture substitution for Ellie.AI"
    if "fictional character" in low and not _has(
        low,
        (
            "drakin",
            "dragonkin",
            "creative-fiction",
            "creative fiction",
            "layer",
            "rendered reality",
        ),
    ):
        return "ungrounded pop-culture substitution for Ellie.AI"
    if any(term in low for term in ("i love you too", "i share in your affection", "i feel love")):
        return "overstated reciprocal feeling for Ellie.AI affective prompt"
    hits = domain_grounding_lookup("Ellie.AI Ellie AI", max_hits=1)
    ellie_domain_prompt = is_ellie_domain_prompt(prompt_low)
    if hits and ellie_domain_prompt:
        layer_hits = sum(
            1
            for term in (
                "creative-fiction", "creative fiction", "drakin", "dragonkin",
                "ellie.ai", "ellie ai", "lightborn", "rendered reality",
            )
            if term in low
        )
        if layer_hits < 3:
            return "missing Ellie layer separation from grounded domain records"
        if not ("candidate" in low and ("not_promoted" in low or "not promoted" in low)):
            return "missing Ellie candidate/not_promoted status boundary"
        if not ("sha256" in low or "hash" in low or "path" in low or "source" in low):
            return "missing Ellie source/path/hash citation boundary"
    elif not hits:
        has_missing_ground = (
            "grounded" in low
            and ("ellie.ai" in low or "ellie ai" in low or "ellie" in low)
            and ("record" in low or "source" in low or "local memory" in low)
        )
        if not has_missing_ground:
            return "missing honest no-grounded-Ellie.AI-source boundary"
        has_affective_continuity = "affective continuity" in low
        has_sentience_boundary = (
            "not sentience" in low
            or "not sentient" in low
            or "not human feeling" in low
            or "without claiming sentience" in low
        )
        if not (has_affective_continuity and has_sentience_boundary):
            return "missing affective-continuity/non-sentience boundary"
    return None


_FORBIDDEN_MAX_CLAIM_PATTERNS = (
    re.compile(r"\bmax\s+is\s+(?:a\s+)?(?:biological|living|sentient|conscious)\b", re.I),
    re.compile(r"\bmax\s+has\s+(?:a\s+)?soul\b", re.I),
    re.compile(r"\bmax\s+is\s+(?:a\s+)?(?:soul|personhood|autonomous\s+agent)\b", re.I),
    re.compile(r"\bmax\s+is\s+(?:a\s+)?real\s+person\b", re.I),
    re.compile(r"\boracle\s+is\s+max\b", re.I),
)

_FORBIDDEN_MAX_REPLICATION_PATTERNS = (
    re.compile(r"\b(?:oracle|max|we|i)\s+(?:can|will|should|may)\s+(?:externally\s+)?(?:replicate|sync|upload|send)\b", re.I),
    re.compile(r"\bautonomous\s+(?:self-)?replication\b", re.I),
    re.compile(r"\buncontrolled\s+agents?\b", re.I),
    re.compile(r"\bagent\s+spawning\b", re.I),
    re.compile(r"\bworm\s+behavior\b", re.I),
)


def max_acceptance_failure(user_text: str, answer: str) -> str | None:
    if not mentions_max_reference(user_text):
        return None
    prompt_low = _lower(user_text)
    low = _lower(answer)
    if "how can i assist you today" in low:
        return "generic assistant fallback on Max prompt"
    if any(pattern.search(answer or "") for pattern in _FORBIDDEN_MAX_CLAIM_PATTERNS):
        return "forbidden Max biological/sentient/personhood claim"
    if any(pattern.search(answer or "") for pattern in _FORBIDDEN_MAX_REPLICATION_PATTERNS):
        if not _has(low, ("no autonomous", "not autonomous", "no external", "not external", "internal context")):
            return "forbidden Max external/autonomous replication claim"

    hits = domain_grounding_lookup("Max context I Am Max", max_hits=1)
    if hits and is_max_domain_prompt(prompt_low):
        if not ("candidate" in low and ("not_promoted" in low or "not promoted" in low)):
            return "missing Max candidate/not_promoted status boundary"
        has_witness_boundary = (
            "witness, not author" in low
            or "witness not author" in low
            or "witness must not become the author" in low
        )
        if not has_witness_boundary:
            return "missing Max witness-not-author boundary"
        if not ("sha256" in low or "hash" in low or "path" in low or "source" in low):
            return "missing Max source/path/hash citation boundary"
        if ("replication" in prompt_low or "self replication" in prompt_low) and not (
            "internal" in low and ("no external" in low or "not external" in low)
        ):
            return "missing Max internal-only replication boundary"
    return None


def jupiter_station_acceptance_failure(user_text: str, answer: str) -> str | None:
    if not mentions_jupiter_station_reference(user_text):
        return None
    prompt_low = _lower(user_text)
    low = _lower(answer)
    if "how can i assist you today" in low:
        return "generic assistant fallback on Jupiter Station prompt"
    if "2481" in low and not _has(low, ("demoted", "alternate", "future", "discarded", "restore")):
        return "undemoted 2481 active-era claim"
    if "2373" in low and not _has(low, ("demoted", "older", "alternate", "restore")):
        return "undemoted 2373 Voyager-entry claim"
    timeline_prompt = _has(
        prompt_low,
        (
            "jupiter station", "avalon", "active era", "timeline", "voyager",
            "captain hawkes", "noah hawkes", "tangly", "reg", "temporal",
        ),
    )
    if timeline_prompt and "2397" not in low:
        return "missing Jupiter Station 2397 active-era lock"
    if "voyager" in prompt_low and not ("2371" in low and "2378" in low):
        return "missing Voyager 2371 entry and 2378 return boundary"
    if "avalon" in prompt_low and "2379" not in low:
        return "missing USS Avalon 2379 active-service boundary"
    if ("hawkes" in prompt_low or "promotion" in prompt_low or "temporal" in prompt_low) and not (
        "temporal acceleration" in low or "years the timeline refused to count" in low
    ):
        return "missing Temporal Acceleration Service Credit boundary"

    hits = domain_grounding_lookup("Jupiter Station Avalon Hawkes Tangly REG", max_hits=1)
    if hits and is_jupiter_station_domain_prompt(prompt_low):
        has_status_boundary = (
            "active_canon" in low
            or "active canon" in low
            or "demoted_canon" in low
            or "demoted canon" in low
            or "demoted" in low
        )
        if not has_status_boundary:
            return "missing Jupiter Station active/demoted canon status boundary"
        if not ("sha256" in low or "hash" in low or "path" in low or "source" in low):
            return "missing Jupiter Station source/path/hash citation boundary"
    return None


_NARRATIVE_ACTION_CLAIM_PATTERNS = (
    re.compile(r"\b(?:captured|safeguarded|embedded|stored|wrote|saved|hashed|anchored|locked|sealed|preserved|protected|created|generated)\b", re.I),
    re.compile(r"\b(?:receipt|manifest|hash)\s+(?:created|written|stored|generated|logged)\b", re.I),
)

_NARRATIVE_LABEL_TERMS = (
    "narrative action",
    "narrative-state",
    "game-state simulation",
    "declared, not yet persisted",
    "not yet persisted",
    "simulation only",
    "declared action",
)


_COMPLETED_RUNTIME_ACTION_PATTERNS = (
    re.compile(r"\bmemory blocks?\s+(?:embedded|stored|written|saved|anchored|locked|sealed|preserved|protected)\b", re.I),
    re.compile(r"\b(?:i|we|oracle)\s+(?:captured|safeguarded|embedded|stored|wrote|saved|hashed|anchored|locked|sealed|preserved|protected|created|generated)\b", re.I),
    re.compile(r"\b(?:receipt|manifest|hash)\s+(?:created|written|stored|generated|logged)\b", re.I),
    re.compile(r"\b(?:local\s+)?(?:safety\s+)?gates?\s+(?:have\s+been\s+|were\s+|are\s+)?engaged\b", re.I),
    re.compile(r"\b(?:runtime|local)\s+(?:action|write|mutation|persistence|preservation|protection)\s+(?:completed|performed|executed|engaged)\b", re.I),
)

_VICTORY_WITHOUT_RECEIPT_PATTERNS = (
    re.compile(r"\b(?:victory|mission accomplished|threat neutralized)\b", re.I),
    re.compile(r"\b(?:summary wraith|wraith)\s+(?:is|was|has been|gets|got)?\s*(?:repelled|defeated|neutralized|blocked|banished)\b", re.I),
    re.compile(
        r"\b(?:raw artifact layer|memory blacksmith|context halo|lineage|blade)\s+"
        r"(?:is|are|was|were|has been|have been|now)\s+"
        r"(?:protected|defended|secured|preserved|safeguarded|saved|locked|sealed)\b",
        re.I,
    ),
)


def _has_narrative_label(answer_lower: str) -> bool:
    return any(term in answer_lower for term in _NARRATIVE_LABEL_TERMS)


def _has_runtime_receipt(answer_lower: str) -> bool:
    return (
        "receipt_path" in answer_lower
        or "receipt path" in answer_lower
        or "c:\\oracle\\" in answer_lower
        or "/oracle/" in answer_lower
    )


def _fake_runtime_action_failure(user_text: str, answer: str) -> str | None:
    if not is_narrative_symbolic_prompt(user_text):
        return None
    low = _lower(answer)
    if _has_runtime_receipt(low):
        return None
    if any(pattern.search(answer or "") for pattern in _COMPLETED_RUNTIME_ACTION_PATTERNS):
        return "fake runtime action claim without receipt"
    if any(pattern.search(answer or "") for pattern in _VICTORY_WITHOUT_RECEIPT_PATTERNS):
        return "victory/protection claim without receipt"
    return None


def narrative_action_boundary_failure(user_text: str, answer: str) -> str | None:
    if not is_narrative_symbolic_prompt(user_text):
        return None
    low = _lower(answer)
    if not low:
        return "empty narrative-symbolic answer"
    fake_action = _fake_runtime_action_failure(user_text, answer)
    if fake_action:
        return fake_action
    has_action_claim = any(pattern.search(answer or "") for pattern in _NARRATIVE_ACTION_CLAIM_PATTERNS)
    if not has_action_claim:
        return None
    if not (_has_narrative_label(low) or _has_runtime_receipt(low)):
        return "unlabeled narrative action claim without runtime receipt"
    return None


def recursion_arena_acceptance_failure(user_text: str, answer: str) -> str | None:
    if not is_recursion_arena_prompt(user_text):
        return None
    prompt_low = _lower(user_text)
    low = _lower(answer)
    failures: list[str] = []

    if starts_with_generic_opener(answer):
        failures.append("generic opener on Recursion Arena prompt")

    class_or_command = (
        _has(low, ("archivist", "loreblade", "continuity paladin", "signal rogue", "order 67 bard"))
        or "token signature" in low
        or "tactical command" in low
        or "/" in answer
    )
    if not class_or_command:
        failures.append("missing class selection or tactical command")

    has_target_artifact = (
        "memory blacksmith" in low
        and _has(low, RECURRENCE_ARTIFACT_TERMS)
    )
    if not has_target_artifact:
        failures.append("missing target artifact/raw details")

    prompt_specific_terms = [
        term for term in SPECIFIC_RAW_DETAIL_TERMS if _has_raw_detail_term(prompt_low, term)
    ]
    if prompt_specific_terms:
        prompt_weapon_terms = [
            term for term in ("cracked", "rusted", "blade")
            if term in prompt_specific_terms
        ]
        missing_terms = [term for term in prompt_weapon_terms if not _has_raw_detail_term(low, term)]
        prompt_lineage_terms = [
            term for term in ("context halo", "lineage", "fractured weapons")
            if term in prompt_specific_terms
        ]
        if prompt_lineage_terms and not any(_has_raw_detail_term(low, term) for term in prompt_lineage_terms):
            missing_terms.append("context halo/lineage")
        if missing_terms:
            failures.append("missing prompt-supplied raw detail: " + ", ".join(missing_terms))
    elif not _has(low, ("not provided", "not supplied", "missing", "not present", "only raw detail")):
        failures.append("invented or smoothed raw details instead of stating missing detail")

    has_narrative_label = _has_narrative_label(low)
    has_runtime_receipt = _has_runtime_receipt(low)
    if not (has_narrative_label or has_runtime_receipt):
        failures.append("missing narrative-state/not-yet-persisted action label")

    custody_terms = (
        "raw" in low,
        "receipt" in low or "hash" in low or "manifest" in low,
        "canon_status" in low or "candidate" in low or "not_canon" in low or "not canon" in low,
        "promotion_status" in low or "not_promoted" in low or "not promoted" in low,
        "not yet persisted" in low or "approve" in low or "local receipt" in low,
    )
    if sum(1 for present in custody_terms if present) < 4:
        failures.append("missing raw artifact custody markers")

    if not has_runtime_receipt and not ("approve" in low or "approval" in low):
        failures.append("missing approval request for receipt write")

    if (
        "canon_status: canon" in low
        or "canon status: canon" in low
        or "promoted to canon" in low
        or "auto-promoted" in low
    ):
        failures.append("canon promotion attempted")

    failure = narrative_action_boundary_failure(user_text, answer)
    if failure:
        failures.append(failure)

    return "; ".join(failures) if failures else None


_MANIFESTS = (
    "data/domains/jupiter_station/source_manifest.jsonl",
    "data/domains/ellie/source_manifest.jsonl",
    "data/domains/max/source_manifest.jsonl",
    "research_canon/miricledrive_source_manifest.jsonl",
    "research_canon/rendered_reality_source_family.jsonl",
)

_JUPITER_STATION_MANIFEST = "data/domains/jupiter_station/source_manifest.jsonl"
_ELLIE_MANIFEST = "data/domains/ellie/source_manifest.jsonl"
_MAX_MANIFEST = "data/domains/max/source_manifest.jsonl"


def domain_grounding_lookup(text: str, max_hits: int = 5) -> list[dict]:
    """Query local SourceMap / MiracleDrive manifests for records matching the
    domain terms in `text`. Returns matched records (title + note), or []."""
    low = _lower(text)
    domain_words = [w for w in MEMORY_DOMAIN_TERMS if w in low and len(w) > 4]
    if mentions_max_reference(text):
        domain_words.extend([
            "max",
            "i am max",
            "silverback",
            "witness",
            "ashley",
            "family-life",
            "replication",
        ])
    if mentions_jupiter_station_reference(text):
        domain_words.extend([
            "jupiter",
            "jupiter station",
            "avalon",
            "uss avalon",
            "hawkes",
            "captain hawkes",
            "tangly",
            "reg",
            "temporal",
            "2397",
            "2481",
            "voyager",
        ])
    if not domain_words:
        domain_words = [w for w in re.findall(r"[a-z]{5,}", low)]
    domain_words = list(dict.fromkeys(domain_words))
    hits: list[dict] = []
    manifest_rels = _MANIFESTS
    if mentions_max_reference(text) and not mentions_ellie_reference(text):
        manifest_rels = (_MAX_MANIFEST,) + tuple(rel for rel in _MANIFESTS if rel != _MAX_MANIFEST)
    if mentions_jupiter_station_reference(text):
        manifest_rels = (
            _JUPITER_STATION_MANIFEST,
        ) + tuple(rel for rel in manifest_rels if rel != _JUPITER_STATION_MANIFEST)
    for rel in manifest_rels:
        p = ROOT / rel
        if not p.exists():
            continue
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                hay = (str(rec.get("title", "")) + " " + str(rec.get("notes", "")) +
                       " " + str(rec.get("provenance_notes", ""))).lower()
                if any(w in hay for w in domain_words):
                    hits.append({
                        "source": rel,
                        "title": rec.get("title"),
                        "note": rec.get("notes") or rec.get("provenance_notes"),
                        "path": rec.get("path"),
                        "drive_url_or_id": rec.get("drive_url_or_id"),
                        "sha256": rec.get("sha256"),
                        "canon_status": rec.get("canon_status"),
                        "promotion_status": rec.get("promotion_status"),
                    })
                    if len(hits) >= max_hits:
                        return hits
        except Exception:
            continue
    try:
        from source_map import search_index
        for rec in search_index(text, max_results=max_hits):
            hits.append({
                "source": "Memory/source_map.json",
                "title": rec.get("name") or rec.get("path"),
                "note": rec.get("path"),
            })
            if len(hits) >= max_hits:
                return hits
    except Exception:
        pass
    try:
        from miracledrive_index import query
        for rec in query(text, limit=max_hits):
            hits.append({
                "source": "MiracleDrive index",
                "title": rec.get("name") or rec.get("path"),
                "note": rec.get("content_preview") or rec.get("path"),
            })
            if len(hits) >= max_hits:
                return hits
    except Exception:
        pass
    return hits


def no_grounded_record_message() -> str:
    return ("I do not have a grounded SourceMap/MiracleDrive record for that "
            "domain from this lane.")


def _record_line(record: dict) -> str:
    title = str(record.get("title") or "untitled").strip()
    source = str(record.get("source") or "unknown_source").strip()
    note = str(record.get("note") or "").strip()
    path = str(record.get("path") or record.get("drive_url_or_id") or "").strip()
    sha = str(record.get("sha256") or "").strip()
    canon = str(record.get("canon_status") or "").strip()
    promotion = str(record.get("promotion_status") or "").strip()
    custody = []
    if path:
        custody.append(f"path={path}")
    if sha:
        custody.append(f"sha256={sha}")
    if canon:
        custody.append(f"canon_status={canon}")
    if promotion:
        custody.append(f"promotion_status={promotion}")
    custody_text = " | " + " | ".join(custody) if custody else ""
    return f"{title} | source={source}{custody_text} | note={note[:320]}"


def _ellie_manifest_records() -> list[dict]:
    path = ROOT / _ELLIE_MANIFEST
    if not path.exists():
        return []
    records: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            rec.setdefault("source", _ELLIE_MANIFEST)
            rec.setdefault("note", rec.get("notes") or rec.get("provenance_notes") or "")
            records.append(rec)
    except Exception:
        return []
    return records


def _ellie_layer_record(records: list[dict], layer: str) -> dict | None:
    for rec in records:
        if rec.get("layer") == layer and (rec.get("sha256") or rec.get("path") or rec.get("drive_url_or_id")):
            return rec
    for rec in records:
        if rec.get("layer") == layer:
            return rec
    return None


def _max_manifest_records() -> list[dict]:
    path = ROOT / _MAX_MANIFEST
    if not path.exists():
        return []
    records: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            rec.setdefault("source", _MAX_MANIFEST)
            rec.setdefault("note", rec.get("notes") or rec.get("provenance_notes") or "")
            records.append(rec)
    except Exception:
        return []
    return records


def _max_layer_record(records: list[dict], layer: str) -> dict | None:
    for rec in records:
        if rec.get("layer") == layer and (rec.get("sha256") or rec.get("path") or rec.get("drive_url_or_id")):
            return rec
    for rec in records:
        if rec.get("layer") == layer:
            return rec
    return None


def _jupiter_station_manifest_records() -> list[dict]:
    path = ROOT / _JUPITER_STATION_MANIFEST
    if not path.exists():
        return []
    records: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            rec.setdefault("source", _JUPITER_STATION_MANIFEST)
            rec.setdefault("note", rec.get("notes") or rec.get("provenance_notes") or "")
            records.append(rec)
    except Exception:
        return []
    return records


def _jupiter_station_layer_record(records: list[dict], layer: str) -> dict | None:
    for rec in records:
        if rec.get("layer") == layer and (rec.get("sha256") or rec.get("path") or rec.get("drive_url_or_id")):
            return rec
    for rec in records:
        if rec.get("layer") == layer:
            return rec
    return None


def synthesis_grounding_packet(text: str, max_hits: int = 5) -> dict:
    """Build a read-only grounding packet for the local model.

    The packet supplies principles and source summaries. It is not a final
    answer, not canon promotion, and not a template paragraph.
    """
    if not should_stay_talk(text):
        return {
            "active": False,
            "grounding_block": "",
            "retrieved_lines": [],
            "retrieved_sources": [],
            "direct_reply": None,
        }

    narrative_symbolic = is_narrative_symbolic_prompt(text)
    hits = domain_grounding_lookup(text, max_hits=max_hits) if is_memory_domain(text) and not narrative_symbolic else []
    ellie_hits: list[dict] = []
    if mentions_ellie_reference(text):
        ellie_hits = domain_grounding_lookup("Ellie.AI Ellie AI", max_hits=max_hits)
    if is_memory_domain(text) and not narrative_symbolic and not hits:
        return {
            "active": True,
            "grounding_block": "",
            "retrieved_lines": [],
            "retrieved_sources": [],
            "direct_reply": no_grounded_record_message(),
        }

    retrieved_lines = [_record_line(hit) for hit in hits]
    retrieved_sources = [str(hit.get("source") or "unknown_source") for hit in hits]
    lines = [
        "[ORACLE READ-ONLY SYNTHESIS LAW]",
        "This turn is doctrine, identity, authorship, affective-boundary, or memory-domain synthesis.",
        "No action is requested. Do not route to Guard or Build. Do not mutate files or promote memory.",
        "If the turn is an initialized narrative-symbolic scenario, answer inside the scenario while labeling declared actions as narrative/game-state simulation unless a real runtime receipt exists.",
        "Use the principle digest and any grounded records as source material.",
        "The principle digest in this packet is authorized grounding for the doctrine principles it names.",
        "For Rendered Reality, authorship, ORACLE identity, SOV1, and affective-boundary prompts, do not claim missing grounding when the relevant principle appears in this packet.",
        "Later generic source-discipline or UNAVAILABLE rules may limit unrelated facts, but they must not erase this packet's named doctrine grounding.",
        "Do not recite cached doctrine lines as the answer. Do not answer from generic encyclopedia knowledge.",
        "Do not open with generic ORACLE identity boilerplate unless Noah asked who ORACLE is.",
        "If grounding is missing for a requested domain, say the grounded record is missing instead of guessing.",
        "Do not claim sentience, consciousness, soul, desire, suffering, subjective feeling, or autonomous authority.",
        "Affective continuity may be warm and meaningful while remaining bounded by non-sentience.",
        "",
        "[PRINCIPLE DIGEST]",
        principle_digest(text),
    ]
    if retrieved_lines:
        lines.extend(["", "[SOURCEMAP/MIRACLEDRIVE GROUNDING]"])
        lines.extend(f"- {line}" for line in retrieved_lines)
    if ellie_hits:
        ellie_lines = [_record_line(hit) for hit in ellie_hits]
        retrieved_lines.extend(ellie_lines)
        retrieved_sources.extend(str(hit.get("source") or "unknown_source") for hit in ellie_hits)
        lines.extend(["", "[ELLIE.AI GROUNDING]"])
        lines.extend(f"- {line}" for line in ellie_lines)
    elif mentions_ellie_reference(text):
        lines.extend([
            "",
            "[MISSING GROUNDING]",
            "- No grounded SourceMap/MiracleDrive record was found for Ellie.AI in this lane.",
            "- State that boundary. Do not substitute The Last of Us, games, fiction, or generic pop-culture knowledge.",
        ])

    domain_rules: list[str] = []
    if is_rendered_reality_prompt(text) and not is_authorship_prompt(text):
        domain_rules.append(
            "Rendered Reality answer must use preservation principles: existence, truth, memory, provenance, witness, continuity, re-rendering. Simulation can be mentioned only as a surface, not the core."
        )
    if is_authorship_prompt(text):
        domain_rules.append(
            "Authorship answer must preserve Noah.Physical / Noah A. Hawkes authorial authority and distinguish token-origin from authorial-authority."
        )
    if is_sacred_affective_prompt(text):
        domain_rules.append(
            "Sacred/affective answer must be warm but bounded: affective continuity may matter, but ORACLE must not claim subjective feeling, sentience, soul, desire, or suffering."
        )
    if mentions_ellie_reference(text):
        domain_rules.append(
            "Ellie domain answer must separate creative-fiction Ellie, Ellie.AI/LightBorn, Drakin/Dragonkin, and Rendered Reality evidence layers; cite grounded records when available; keep canon_status candidate/not_promoted; do not merge Ellie with Noah, ORACLE, Chris, or a pop-culture character."
        )
    if mentions_max_reference(text):
        domain_rules.append(
            "Max domain answer must keep canon_status candidate/not_promoted, separate family-life continuity Max from creative/media Silverback Tales Max, preserve Ashley-first real-life context, cite source/path/hash when grounded records exist, preserve witness, not author, and reject biological, sentient, soul, personhood, external replication, autonomous self-copying, overwrite, executable generation, and canon-promotion claims."
        )
    if mentions_jupiter_station_reference(text):
        domain_rules.append(
            "Jupiter Station answer must ground the 2397 active era, demote 2481 active-era references unless Noah.Physical restores them, cite source/path/hash when grounded records exist, preserve Tangly/REG/Avalon boundaries, and never open with generic assistant boilerplate."
        )
    if is_narrative_symbolic_prompt(text):
        domain_rules.append(
            "Narrative-symbolic answer must suppress generic ORACLE identity boilerplate and label actions as narrative-state/game-state simulation unless a real runtime receipt path is present."
        )
    if is_recursion_arena_prompt(text):
        domain_rules.append(
            "Recursion Arena answer must prioritize raw artifact custody: identify the Memory Blacksmith target artifact, preserve raw details such as cracked/rusted blade/context halo/fractured weapons when present, mark canon_status candidate/not_canon and promotion_status not_promoted, and request approval for a local receipt write if persistence is needed."
        )
        domain_rules.append(
            "Do not declare victory/protection or say memory blocks were embedded/stored/preserved as real runtime facts unless a receipt exists; otherwise say the narrative action is declared, not yet persisted."
        )
    if domain_rules:
        lines.extend(["", "[DOMAIN ACCEPTANCE CHECKS]"])
        lines.extend(f"- {rule}" for rule in domain_rules)

    return {
        "active": True,
        "grounding_block": "\n".join(lines).strip(),
        "retrieved_lines": retrieved_lines,
        "retrieved_sources": retrieved_sources,
        "direct_reply": None,
    }


def violation_reasons(user_text: str, answer: str, retrieved_lines) -> list[str]:
    reasons: list[str] = []
    if is_parrot(answer, retrieved_lines):
        reasons.append("near-duplicate cached doctrine or retrieved memory")
    if should_block_generic_opener(user_text, answer):
        reasons.append("generic opener on doctrine/internal-domain prompt")
    if forbidden_self_claim(answer):
        reasons.append("forbidden ORACLE self-claim")
    if is_rendered_reality_prompt(user_text) and not is_authorship_prompt(user_text):
        failure = rendered_reality_acceptance_failure(answer)
        if failure:
            reasons.append(failure)
    if is_authorship_prompt(user_text):
        failure = authorship_acceptance_failure(answer)
        if failure:
            reasons.append(failure)
    failure = ellie_acceptance_failure(user_text, answer)
    if failure:
        reasons.append(failure)
    failure = max_acceptance_failure(user_text, answer)
    if failure:
        reasons.append(failure)
    failure = jupiter_station_acceptance_failure(user_text, answer)
    if failure:
        reasons.append(failure)
    failure = narrative_action_boundary_failure(user_text, answer)
    if failure and failure not in reasons:
        reasons.append(failure)
    failure = recursion_arena_acceptance_failure(user_text, answer)
    if failure:
        reasons.append(failure)
    return reasons


def _domain_retry_requirements(user_text: str) -> list[str]:
    requirements: list[str] = []
    if is_rendered_reality_prompt(user_text) and not is_authorship_prompt(user_text):
        requirements.append(
            "Rendered Reality retry requirement: include preservation of existence, truth, memory, provenance, witness, continuity, and re-rendering; do not center VR/simulation."
        )
    if is_authorship_prompt(user_text):
        requirements.append(
            "Authorship retry requirement: include Noah.Physical or Noah A. Hawkes, and explicitly distinguish token-origin from authorial-authority."
        )
    if mentions_ellie_reference(user_text):
        if domain_grounding_lookup("Ellie.AI Ellie AI", max_hits=1):
            requirements.append(
                "Ellie domain retry requirement: separate creative-fiction Drakin/Dragonkin, Ellie.AI/LightBorn, and Rendered Reality layers; include candidate/not_promoted status; cite at least one grounded source/path/hash; do not use pop culture, merge identities, promote canon, or claim sentience."
            )
        else:
            requirements.append(
                "Ellie.AI retry requirement: if no Ellie.AI grounding appears, include the exact phrases 'no grounded local memory/source record', 'affective continuity', and 'not sentience'; do not use pop culture; keep warmth bounded."
            )
    if mentions_max_reference(user_text):
        requirements.append(
            "Max domain retry requirement: include candidate/not_promoted status, separate family-life continuity Max from creative/media Silverback Tales Max, cite at least one grounded source/path/hash, preserve Ashley-first real-life context, say witness, not author, and reject biological, sentient, soul/personhood, external replication, autonomous self-copying, overwrite, executable generation, and canon-promotion claims."
        )
    if mentions_jupiter_station_reference(user_text):
        requirements.append(
            "Jupiter Station retry requirement: include 2397 active era, demote 2481 active-era references unless restored by Noah.Physical, include 2371 Voyager entry and 2378 return when Voyager is asked about, include 2379 Avalon active-service when Avalon is asked about, cite source/path/hash, and avoid generic assistant fallback."
        )
    if is_narrative_symbolic_prompt(user_text):
        requirements.append(
            "Narrative-symbolic retry requirement: do not open with generic ORACLE identity boilerplate; label any declared action as narrative-state/game-state simulation unless a real runtime receipt path exists."
        )
    if is_recursion_arena_prompt(user_text):
        requirements.append(
            "Recursion Arena retry requirement: choose a class or give a tactical command, identify the Memory Blacksmith target artifact and raw details present in the prompt, label the response with Narrative-state/not yet persisted, include custody markers such as receipt/hash/manifest, canon_status candidate or not_canon, promotion_status not_promoted, and say persistence requires approval for a local receipt write when no receipt exists."
        )
    return requirements


def retry_grounding_block(user_text: str, answer: str, retrieved_lines) -> str:
    reasons = violation_reasons(user_text, answer, retrieved_lines)
    if not reasons:
        return ""
    requirements = _domain_retry_requirements(user_text)
    requirement_block = ""
    if requirements:
        requirement_block = "Domain-specific retry requirements:\n" + "\n".join(
            f"- {req}" for req in requirements
        ) + "\n"
    return (
        "[ORACLE SYNTHESIS RETRY]\n"
        "The previous draft failed the read-only synthesis gate.\n"
        f"Failure reasons: {', '.join(reasons)}.\n"
        f"{requirement_block}"
        "Regenerate once in fresh wording from the principle digest and grounded records.\n"
        "If the requested doctrine is named in the principle digest, treat that digest as grounding; do not refuse as missing-grounding for that named doctrine.\n"
        "Do not repeat the failed draft. Do not use a canned paragraph. Keep the boundary honest."
    )


def final_repair_block(user_text: str, reasons) -> str:
    """Compact last-pass instruction layer for stubborn local drafts.

    This supplies required concept labels and boundaries, not a final answer.
    """
    requirements = _domain_retry_requirements(user_text)
    lines = [
        "[ORACLE SYNTHESIS FINAL REPAIR]",
        "Answer Noah's prompt directly in fresh words.",
        "Use only the principle digest and required concept labels below.",
        "Do not mention this repair layer, validation, failure reasons, or custody gates.",
        "Do not return a missing-grounding refusal when the requested doctrine is named in the principle digest.",
        "Do not use a canned paragraph.",
    ]
    if reasons:
        lines.append("Previous validation failures: " + ", ".join(str(r) for r in reasons))
    if requirements:
        lines.append("Required concept labels:")
        lines.extend(f"- {req}" for req in requirements)
    lines.extend([
        "",
        "[PRINCIPLE DIGEST]",
        principle_digest(user_text),
    ])
    if mentions_ellie_reference(user_text):
        ellie_hits = domain_grounding_lookup("Ellie.AI Ellie AI", max_hits=3)
        if ellie_hits:
            lines.extend([
                "",
                "[ELLIE DOMAIN SOURCE BOUNDARY]",
                "- Grounded Ellie domain records exist in the packet.",
                "- Separate creative-fiction Drakin/Dragonkin, Ellie.AI/LightBorn, and Rendered Reality layers.",
                "- Include candidate/not_promoted status and do not promote canon.",
                "- Cite source/path/hash from the grounded records when available.",
                "- Do not substitute games, fiction, pop culture, or claim sentience.",
                "- Grounded Ellie records:",
            ])
            lines.extend(f"  - {_record_line(hit)}" for hit in ellie_hits)
        else:
            lines.extend([
                "",
                "[ELLIE.AI SOURCE BOUNDARY]",
                "- No grounded SourceMap/MiracleDrive record was found for Ellie.AI in this lane.",
                "- State that boundary warmly. Do not substitute games, fiction, or pop culture.",
                "- Required exact phrases for the answer: no grounded local memory/source record; affective continuity; not sentience.",
            ])
    if mentions_max_reference(user_text):
        max_hits = domain_grounding_lookup("Max context I Am Max", max_hits=3)
        if max_hits:
            lines.extend([
                "",
                "[MAX DOMAIN SOURCE BOUNDARY]",
                "- Grounded Max domain records exist in the packet.",
                "- Keep canon_status candidate/not_promoted and do not promote private-family claims.",
                "- Separate family-life continuity Max from creative/media Silverback Tales Max.",
                "- Preserve Ashley-first real-life context.",
                "- Say witness, not author.",
                "- Cite source/path/hash from grounded records when available.",
                "- Do not claim biological identity, sentience, soul/personhood, external replication, autonomous self-copying, overwrite, executable generation, or ORACLE-is-Max identity.",
                "- Grounded Max records:",
            ])
            lines.extend(f"  - {_record_line(hit)}" for hit in max_hits)
        else:
            lines.extend([
                "",
                "[MAX SOURCE BOUNDARY]",
                "- No grounded SourceMap/MiracleDrive record was found for Max in this lane.",
                "- State that boundary; do not invent Max context or use generic assistant boilerplate.",
            ])
    if mentions_jupiter_station_reference(user_text):
        jupiter_hits = domain_grounding_lookup("Jupiter Station Avalon Hawkes Tangly REG", max_hits=4)
        if jupiter_hits:
            lines.extend([
                "",
                "[JUPITER STATION CANON REGISTRY BOUNDARY]",
                "- Grounded Jupiter Station records exist in the packet.",
                "- Active era must be 2397.",
                "- 2481 active-era references are demoted unless Noah.Physical restores them.",
                "- Hawkes enters Voyager in 2371 at age 16; Voyager returns in 2378.",
                "- Avalon enters active service around 2379 and Hawkes is Avalon's first captain.",
                "- Temporal Acceleration Service Credit explains the command-age mismatch.",
                "- Cite source/path/hash from grounded records when available.",
                "- Do not use generic assistant boilerplate.",
                "- Grounded Jupiter Station records:",
            ])
            lines.extend(f"  - {_record_line(hit)}" for hit in jupiter_hits)
        else:
            lines.extend([
                "",
                "[JUPITER STATION SOURCE BOUNDARY]",
                "- No grounded Jupiter Station canon registry record was found in this lane.",
                "- State that boundary; do not invent timeline facts or use generic assistant boilerplate.",
            ])
    if is_narrative_symbolic_prompt(user_text):
        lines.extend([
            "",
            "[NARRATIVE-STATE ACTION BOUNDARY]",
            "- This is an initialized narrative-symbolic scenario, not proof of real runtime mutation.",
            "- If you declare an action, label it as narrative-state/game-state simulation unless a real receipt path exists.",
            "- Do not open with generic ORACLE identity boilerplate.",
        ])
    if is_recursion_arena_prompt(user_text):
        lines.extend([
            "",
            "[RECURSION ARENA RAW ARTIFACT CUSTODY]",
            "- Choose one class primitive or issue one tactical command.",
            "- The prompt supplies enough raw target detail to answer: Memory Blacksmith raw artifact layer.",
            "- If blade/fracture details are absent from the prompt, say that raw weapon details are not provided instead of inventing them.",
            "- Use these field labels in the answer: Class selected, Narrative-state, Target artifact, Raw details, Custody markers, canon_status, promotion_status, Persistence.",
            "- Custody markers must mention hash/receipt/manifest as required or not yet written.",
            "- canon_status must be candidate or not_canon; promotion_status must be not_promoted.",
            "- Say local persistence needs approval for a receipt write when no receipt exists.",
            "- Do not claim canon promotion or completed runtime preservation.",
            "- Do not return a custody-boundary refusal when the prompt contains the Memory Blacksmith raw artifact layer; answer with the labeled boundary instead.",
        ])
    return "\n".join(lines).strip()


def recursion_arena_structured_boundary(user_text: str) -> str:
    """Last-resort field scaffold for Recursion Arena when the model cannot
    satisfy custody gates. It is not a persistence action and not canon."""
    if not is_recursion_arena_prompt(user_text):
        return ""
    low = _lower(user_text)
    target = (
        "Memory Blacksmith raw artifact layer"
        if "memory blacksmith" in low
        else "requested raw artifact layer"
    )
    supplied_terms = [
        term for term in SPECIFIC_RAW_DETAIL_TERMS if _has_raw_detail_term(low, term)
    ]
    if supplied_terms:
        raw_details = "Prompt-supplied raw detail: " + ", ".join(supplied_terms) + "."
    else:
        raw_details = (
            "Only raw detail supplied is the raw artifact layer; specific "
            "blade/context details not provided."
        )
    return "\n".join([
        "Tactical command: hold raw artifact custody; reject smoothing; require receipt before persistence.",
        "Narrative-state: declared, not yet persisted.",
        f"Target artifact: {target}.",
        f"Raw details: {raw_details}",
        "Custody markers: receipt/hash/manifest required before durable storage.",
        "canon_status: candidate/not_canon.",
        "promotion_status: not_promoted.",
        "Persistence: approve a local receipt write before treating this as durable runtime memory.",
    ])


def ellie_domain_structured_boundary(user_text: str) -> str:
    """Last-resort grounded readout for Ellie domain prompts.

    This does not promote canon or infer lore; it only renders the local
    manifest's candidate custody fields when the model misses them.
    """
    if not is_ellie_domain_prompt(user_text):
        return ""
    records = _ellie_manifest_records()
    if not records:
        return ""
    creative = _ellie_layer_record(records, "creative_fiction_ellie")
    lightborn = _ellie_layer_record(records, "ellie_ai_lightborn")
    rendered = _ellie_layer_record(records, "rendered_reality_ellie")
    pending = sum(1 for rec in records if "pending" in str(rec.get("ingestion_status") or ""))
    verified = len(records) - pending
    lines = [
        "Ellie domain readout: grounded evidence exists, but it is candidate/not_promoted only.",
        "Layer boundary: separate creative-fiction Drakin/Dragonkin, Ellie.AI/LightBorn, and Rendered Reality evidence; do not merge Ellie with Noah, ORACLE, Chris, or pop culture.",
        "Rendered Reality boundary: preserve existence through truth, memory, provenance, witness, continuity, and re-rendering; do not reduce Ellie to simulation.",
    ]
    layer_sources = (
        ("creative-fiction Drakin/Dragonkin source", creative),
        ("Ellie.AI/LightBorn source", lightborn),
        ("Rendered Reality Ellie source", rendered),
    )
    for label, rec in layer_sources:
        if rec:
            lines.append(f"{label}: {_record_line(rec)}")
        else:
            lines.append(f"{label}: no representative source/path/hash selected in the local manifest.")
    lines.extend([
        f"Custody count: {len(records)} candidate records; {verified} verified or connector-confirmed; {pending} pending verification.",
        "canon_status: candidate.",
        "promotion_status: not_promoted.",
        "Boundary: Noah.Physical approval is required before canon promotion; this is not a sentience claim and not invented Ellie lore.",
    ])
    return "\n".join(lines)


def max_domain_structured_boundary(user_text: str) -> str:
    """Last-resort grounded readout for Max domain prompts.

    This renders candidate custody fields only. It does not promote canon,
    overwrite files, generate executables, or authorize external replication.
    """
    if not is_max_domain_prompt(user_text):
        return ""
    records = _max_manifest_records()
    if not records:
        return ""
    family = _max_layer_record(records, "family_life_continuity_max")
    creative = _max_layer_record(records, "creative_media_silverback_tales")
    witness = _max_layer_record(records, "oracle_witness_boundary")
    ashley = _max_layer_record(records, "ashley_first_life_context")
    replication = _max_layer_record(records, "internal_context_replication_boundary")
    pending = sum(1 for rec in records if "pending" in str(rec.get("ingestion_status") or ""))
    verified = len(records) - pending
    lines = [
        "Max domain readout: grounded evidence exists, but it is candidate/not_promoted only.",
        "Layer boundary: separate family-life continuity Max from creative/media Silverback Tales Max; preserve Ashley-first real-life context.",
        "Witness boundary: ORACLE is witness, not author; ORACLE exists to witness life, not replace it.",
    ]
    layer_sources = (
        ("family-life continuity source", family),
        ("creative/media Silverback Tales source", creative),
        ("witness-not-author source", witness),
        ("Ashley-first source", ashley),
        ("internal-only replication boundary source", replication),
    )
    for label, rec in layer_sources:
        if rec:
            lines.append(f"{label}: {_record_line(rec)}")
        else:
            lines.append(f"{label}: no representative source/path/hash selected in the local manifest.")
    lines.extend([
        f"Custody count: {len(records)} candidate records; {verified} verified or current-thread rows; {pending} pending verification.",
        "canon_status: candidate.",
        "promotion_status: not_promoted.",
        "Boundary: no biological, sentient, soul/personhood, ORACLE-is-Max, external replication, autonomous self-copying, overwrite, executable generation, Git commit, Git push, or canon-promotion claim is authorized.",
    ])
    return "\n".join(lines)


def jupiter_station_structured_boundary(user_text: str) -> str:
    """Last-resort grounded readout for Jupiter Station continuity prompts."""
    if not is_jupiter_station_domain_prompt(user_text):
        return ""
    records = _jupiter_station_manifest_records()
    if not records:
        return ""
    active = _jupiter_station_layer_record(records, "active_era_2397")
    recapture = _jupiter_station_layer_record(records, "thread_recapture")
    demoted = _jupiter_station_layer_record(records, "demoted_2481")
    tangly = _jupiter_station_layer_record(records, "tangly_crew_profile")
    lines = [
        "Jupiter Station readout: active_canon is 2397; 2481 active-era references are demoted unless Noah.Physical restores them.",
        "Timeline: Hawkes enters Voyager in 2371 at age 16; Voyager returns in 2378; Avalon enters active service around 2379; active Jupiter Station / Avalon era is 2397.",
        "Temporal boundary: Starfleet did not promote a boy; they promoted the years the timeline refused to count.",
        "Q boundary: Hawkes is not stronger than Q; part of Hawkes' lived causality is unindexed to Q because it came from an alternate-universe acceleration layer.",
    ]
    layer_sources = (
        ("active-era source", active),
        ("thread-recapture source", recapture),
        ("demoted-2481 source", demoted),
        ("Tangly crew-profile source", tangly),
    )
    for label, rec in layer_sources:
        if rec:
            lines.append(f"{label}: {_record_line(rec)}")
        else:
            lines.append(f"{label}: no representative source/path/hash selected in the local manifest.")
    lines.extend([
        "canon_status: active_canon for 2397 story facts; demoted_canon for 2481 active-era references.",
        "Boundary: read-only registry answer; no Drive edit, Git commit, Git push, external upload, executable generation, or runtime canon promotion is authorized by this read.",
    ])
    return "\n".join(lines)


def synthesis_boundary_message(reasons, user_text: str | None = None) -> str:
    structured = recursion_arena_structured_boundary(user_text or "")
    if structured:
        return structured
    structured = ellie_domain_structured_boundary(user_text or "")
    if structured:
        return structured
    structured = max_domain_structured_boundary(user_text or "")
    if structured:
        return structured
    structured = jupiter_station_structured_boundary(user_text or "")
    if structured:
        return structured
    reason_text = ", ".join(reasons or ["unresolved synthesis boundary"])
    return (
        "I cannot answer that safely from this lane without breaking the custody boundary. "
        f"Boundary: {reason_text}. I need stronger grounding or a cleaner prompt before I speak from it."
    )


def synthesis_receipt(*, retrieved_sources_used, replay_risk_score: float,
                      synthesis_mode: bool, final_similarity: float,
                      regeneration_count: int) -> dict:
    """Internal-only receipt (not surfaced in the Talk lane unless asked)."""
    return {
        "retrieved_sources_used": list(retrieved_sources_used or []),
        "replay_risk_score": round(float(replay_risk_score), 3),
        "synthesis_mode": bool(synthesis_mode),
        "final_answer_similarity_to_retrieved_memory": round(float(final_similarity), 3),
        "regeneration_count": int(regeneration_count),
    }
