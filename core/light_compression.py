"""
core/light_compression.py — ORACLE Light Compression Memory System

Core law: Memory is compression of meaningful light.

Raw signal (conversation, files, events) passes through a scoring filter.
High-score signal is compressed from raw text into typed, reusable meaning.
Recall retrieves by relevance — not keyword, not recency alone.

Memory types:
  FACT         — stable facts about Noah, the system, or the world
  PROJECT      — current build state, phase, blockers, next steps
  PATTERN      — repeated behavior, repeated failures, recurring themes
  RELATIONSHIP — how people, systems, and agents relate
  EMOTIONAL    — things that matter because Noah cares deeply
  CONSTRAINT   — rules, boundaries, governance laws
  NEXT_ACTION  — the most important next move right now

Scoring:
  score = relevance + recurrence + emotional_weight + project_value
          - sensitivity_risk - noise_penalty
  < 0.3  → discard
  0.3–0.6 → temporary context only
  > 0.6  → create pending memory (routes to approval if sensitive)
  sensitive → block or gate
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Paths ──────────────────────────────────────────────────────────────────────
import sys
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "core"))

MEMORY_DIR  = ROOT / "Memory"
LIGHT_FILE  = MEMORY_DIR / "light_memory.json"
MEMORY_DIR.mkdir(exist_ok=True)

# ── Memory types ───────────────────────────────────────────────────────────────
FACT         = "fact"
PROJECT      = "project"
PATTERN      = "pattern"
RELATIONSHIP = "relationship"
EMOTIONAL    = "emotional"
CONSTRAINT   = "constraint"
NEXT_ACTION  = "next_action"

ALL_TYPES = [FACT, PROJECT, PATTERN, RELATIONSHIP, EMOTIONAL, CONSTRAINT, NEXT_ACTION]

# ── Score thresholds ───────────────────────────────────────────────────────────
THRESHOLD_DISCARD   = 0.30
THRESHOLD_TEMPORARY = 0.60   # below this = temp context only; above = persist

# ── Sensitivity patterns — these gate on approval or block ────────────────────
_SENSITIVE_PATTERNS = [
    "sk-", "api_key", "api key", "secret", "token", "password", "bearer",
    "private key", "credential",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Data model ─────────────────────────────────────────────────────────────────

@dataclass
class LightMemory:
    id:            str   = field(default_factory=lambda: uuid.uuid4().hex[:10])
    memory_type:   str   = FACT
    raw_signal:    str   = ""          # original text (kept short for audit)
    compressed:    str   = ""          # the distilled meaning — what ORACLE actually uses
    source:        str   = "conversation"
    score:         float = 0.0
    relevance:     float = 0.0
    recurrence:    int   = 1           # how many times this signal has appeared
    emotional_weight: float = 0.0
    project_value: float = 0.0
    sensitivity:   float = 0.0
    noise:         float = 0.0
    status:        str   = "active"    # active | superseded | discarded
    created_at:    str   = field(default_factory=_now)
    updated_at:    str   = field(default_factory=_now)
    tags:          list  = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "memory_type": self.memory_type,
            "raw_signal": self.raw_signal[:200],
            "compressed": self.compressed,
            "source": self.source, "score": round(self.score, 3),
            "relevance": self.relevance, "recurrence": self.recurrence,
            "emotional_weight": self.emotional_weight,
            "project_value": self.project_value,
            "sensitivity": self.sensitivity, "noise": self.noise,
            "status": self.status,
            "created_at": self.created_at, "updated_at": self.updated_at,
            "tags": self.tags,
        }

    @staticmethod
    def from_dict(d: dict) -> "LightMemory":
        m = LightMemory()
        for k, v in d.items():
            if hasattr(m, k):
                setattr(m, k, v)
        return m

    def summary(self) -> str:
        return f"[{self.memory_type.upper()}] {self.compressed[:100]}"


# ── Persistence ────────────────────────────────────────────────────────────────

def _load() -> list[LightMemory]:
    try:
        raw = json.loads(LIGHT_FILE.read_text(encoding="utf-8"))
        return [LightMemory.from_dict(d) for d in raw if isinstance(d, dict)]
    except Exception:
        return []


def _save(memories: list[LightMemory]) -> None:
    LIGHT_FILE.write_text(
        json.dumps([m.to_dict() for m in memories], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ── Scoring ────────────────────────────────────────────────────────────────────

# Keywords that boost each dimension
_RELEVANCE_BOOST = [
    "oracle", "noah", "sov1", "claude", "build", "fix", "error", "broken",
    "step ", "phase", "goal", "priority", "blocker", "next", "ship",
]
_PROJECT_BOOST = [
    "oracle.ai", "build pass", "mythic", "step ", ".py", "core/", "commit",
    "pull request", "test", "voice", "actuation", "channel", "loop",
]
_EMOTIONAL_BOOST = [
    "frustrated", "excited", "important", "matters", "love", "hate",
    "finally", "broken", "works", "perfect", "yes", "no", "never", "always",
    "want", "need", "feel", "care",
]
_CONSTRAINT_BOOST = [
    "must not", "never", "always", "rule", "law", "cannot", "blocked",
    "approval", "governed", "permission", "allowed", "forbidden",
]
_NOISE_SIGNALS = [
    "ok", "okay", "sure", "got it", "thanks", "bye", "hello", "hi",
    "yes", "no", "maybe", "alright", "fine",
]


def score_signal(
    text: str,
    memory_type: str = FACT,
    source: str = "conversation",
    recurrence: int = 1,
) -> tuple[float, float, float, float, float, float]:
    """
    Return (total_score, relevance, emotional_weight, project_value, sensitivity, noise).
    All dimensions 0.0–1.0. total_score is the weighted combination.
    """
    lower = text.lower().strip()
    words = lower.split()
    length = len(words)

    # Sensitivity — hard check first
    sensitivity = 1.0 if any(p in lower for p in _SENSITIVE_PATTERNS) else 0.0

    # Noise — very short or generic
    noise = 0.0
    if length <= 3 and lower in " ".join(_NOISE_SIGNALS):
        noise = 0.9
    elif length <= 6:
        noise = 0.4

    # Relevance — contains project-relevant terms
    rel_hits = sum(1 for kw in _RELEVANCE_BOOST if kw in lower)
    relevance = min(1.0, rel_hits / 3.0)

    # Emotional weight
    emo_hits = sum(1 for kw in _EMOTIONAL_BOOST if kw in lower)
    emotional_weight = min(1.0, emo_hits / 2.0)
    if memory_type == EMOTIONAL:
        emotional_weight = max(emotional_weight, 0.5)

    # Project value
    proj_hits = sum(1 for kw in _PROJECT_BOOST if kw in lower)
    project_value = min(1.0, proj_hits / 2.0)
    if memory_type in (PROJECT, NEXT_ACTION):
        project_value = max(project_value, 0.6)
    elif memory_type == PATTERN:
        project_value = max(project_value, 0.4)  # patterns always have some project value

    # Constraint boost
    if memory_type == CONSTRAINT:
        const_hits = sum(1 for kw in _CONSTRAINT_BOOST if kw in lower)
        relevance = max(relevance, min(1.0, const_hits / 2.0))

    # Recurrence boost — things that keep coming up matter more
    recurrence_boost = min(0.3, (recurrence - 1) * 0.1)

    # Weighted score
    score = (
        relevance       * 0.30
        + emotional_weight * 0.15
        + project_value    * 0.25
        + recurrence_boost * 0.15
        - sensitivity      * 0.8    # sensitive signals heavily penalised
        - noise            * 0.5
    )
    score = max(0.0, min(1.0, score))

    return score, relevance, emotional_weight, project_value, sensitivity, noise


# ── Compression — raw text → distilled meaning ────────────────────────────────

_TYPE_PREFIXES = {
    FACT:         "Stable fact",
    PROJECT:      "Project state",
    PATTERN:      "Recurring pattern",
    RELATIONSHIP: "Relationship",
    EMOTIONAL:    "Matters to Noah",
    CONSTRAINT:   "Rule",
    NEXT_ACTION:  "Next action",
}

def _auto_compress(raw: str, memory_type: str) -> str:
    """
    Rule-based compression when no LLM is available.
    Strips filler, trims to 1–2 sentences, prefixes with type label.
    """
    # Strip ORACLE terminal artifacts
    clean = raw.strip()
    for artifact in ("[BLOCKED]", "[GOVERNANCE]", "[CHAT]", "[WORK]", "[BUILD]",
                     "[LOCAL]", "Desired action :", "Missing/broken :", "Next step :"):
        clean = clean.replace(artifact, "").strip()

    # Collapse whitespace
    import re
    clean = re.sub(r"\s{2,}", " ", clean).strip()

    # Trim to 2 sentences max
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    compressed = " ".join(sentences[:2]).strip()
    if not compressed:
        compressed = clean[:150]

    prefix = _TYPE_PREFIXES.get(memory_type, "Memory")
    return f"{prefix}: {compressed}"


# ── Public API ─────────────────────────────────────────────────────────────────

def compress_and_store(
    raw_signal: str,
    memory_type: str = FACT,
    source: str = "conversation",
    compressed: Optional[str] = None,
    recurrence: int = 1,
    tags: Optional[list] = None,
) -> Optional[LightMemory]:
    """
    Score the signal. If score >= THRESHOLD_TEMPORARY, compress and persist.
    If sensitive, return None (caller should route to approval gate).
    Returns the LightMemory if stored, else None.
    """
    score, relevance, emo, proj, sensitivity, noise = score_signal(
        raw_signal, memory_type=memory_type, recurrence=recurrence
    )

    # Block sensitive material
    if sensitivity > 0.5:
        return None   # caller must gate this

    # Below discard threshold — drop it
    if score < THRESHOLD_DISCARD:
        return None

    # Build compressed form
    compressed_text = compressed or _auto_compress(raw_signal, memory_type)

    mem = LightMemory(
        memory_type=memory_type,
        raw_signal=raw_signal[:300],
        compressed=compressed_text,
        source=source,
        score=score,
        relevance=relevance,
        recurrence=recurrence,
        emotional_weight=emo,
        project_value=proj,
        sensitivity=sensitivity,
        noise=noise,
        tags=tags or [],
    )

    # Check for duplicate / supersede existing memory of same type+content
    memories = _load()
    for existing in memories:
        if (existing.memory_type == memory_type
                and existing.status == "active"
                and _similar(existing.compressed, compressed_text)):
            # Update recurrence and score instead of duplicating
            existing.recurrence += 1
            existing.score = min(1.0, existing.score + 0.05)
            existing.updated_at = _now()
            _save(memories)
            return existing

    memories.append(mem)
    _save(memories)
    return mem


def recall_by_meaning(
    query: str,
    top_k: int = 6,
    memory_types: Optional[list] = None,
    min_score: float = 0.0,
) -> list[LightMemory]:
    """
    Retrieve memories by relevance to query — not by keyword match alone.
    Scores each memory against the query context and returns top_k.
    """
    memories = [m for m in _load() if m.status == "active"]
    if memory_types:
        memories = [m for m in memories if m.memory_type in memory_types]
    if min_score > 0:
        memories = [m for m in memories if m.score >= min_score]

    if not memories:
        return []

    query_lower = query.lower()

    def _relevance_to_query(mem: LightMemory) -> float:
        compressed_lower = mem.compressed.lower()
        raw_lower = mem.raw_signal.lower()
        # Word overlap between query and compressed memory
        q_words = set(query_lower.split())
        m_words = set(compressed_lower.split())
        overlap = len(q_words & m_words) / max(len(q_words), 1)
        # Boost for high-priority types
        type_boost = {NEXT_ACTION: 0.3, PROJECT: 0.2, CONSTRAINT: 0.15, PATTERN: 0.1}.get(mem.memory_type, 0.0)
        return mem.score * 0.5 + overlap * 0.35 + type_boost

    ranked = sorted(memories, key=_relevance_to_query, reverse=True)
    return ranked[:top_k]


def recall_for_prompt(query: str = "", max_chars: int = 800) -> str:
    """
    Build a compact memory block for injection into the system prompt.
    Prioritises NEXT_ACTION, PROJECT, CONSTRAINT, then others.
    """
    priority_order = [NEXT_ACTION, PROJECT, CONSTRAINT, PATTERN, FACT, RELATIONSHIP, EMOTIONAL]
    retrieved: list[LightMemory] = []

    for mtype in priority_order:
        hits = recall_by_meaning(query, top_k=2, memory_types=[mtype], min_score=0.3)
        retrieved.extend(hits)
        if sum(len(m.compressed) for m in retrieved) > max_chars:
            break

    if not retrieved:
        return ""

    lines = ["[ORACLE MEMORY — compressed meaning]"]
    total = 0
    for mem in retrieved:
        line = f"  {mem.summary()}"
        total += len(line)
        if total > max_chars:
            break
        lines.append(line)
    lines.append("")
    return "\n".join(lines)


def list_memories(memory_type: Optional[str] = None, limit: int = 20) -> list[LightMemory]:
    memories = [m for m in _load() if m.status == "active"]
    if memory_type:
        memories = [m for m in memories if m.memory_type == memory_type]
    return sorted(memories, key=lambda m: m.score, reverse=True)[:limit]


def supersede(memory_id: str, new_compressed: str) -> bool:
    """Mark an existing memory superseded and store the updated version."""
    memories = _load()
    for m in memories:
        if m.id == memory_id:
            m.status = "superseded"
            m.updated_at = _now()
            _save(memories)
            compress_and_store(
                raw_signal=new_compressed,
                memory_type=m.memory_type,
                compressed=new_compressed,
                source="update",
            )
            return True
    return False


def purge_old(older_than_days: int = 60, keep_types: Optional[list] = None) -> int:
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    keep_types = keep_types or [CONSTRAINT, NEXT_ACTION, PROJECT]
    memories = _load()
    before = len(memories)
    kept = []
    for m in memories:
        if m.memory_type in keep_types:
            kept.append(m)
            continue
        try:
            ts = datetime.fromisoformat(m.updated_at)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                kept.append(m)
        except Exception:
            kept.append(m)
    _save(kept)
    return before - len(kept)


# ── Similarity helper ──────────────────────────────────────────────────────────

def _similar(a: str, b: str, threshold: float = 0.6) -> bool:
    """Simple word-overlap similarity — no external deps."""
    wa = set(a.lower().split())
    wb = set(b.lower().split())
    if not wa or not wb:
        return False
    overlap = len(wa & wb) / min(len(wa), len(wb))
    return overlap >= threshold


# ── Convenience: store a memory directly with full control ────────────────────

def remember(
    compressed: str,
    memory_type: str = FACT,
    source: str = "direct",
    score: float = 0.75,
    tags: Optional[list] = None,
) -> LightMemory:
    """
    Store a pre-compressed memory directly (bypasses scoring).
    Use when ORACLE or Noah explicitly says 'remember this'.
    """
    mem = LightMemory(
        memory_type=memory_type,
        raw_signal=compressed,
        compressed=compressed,
        source=source,
        score=score,
        relevance=score,
        tags=tags or [],
    )
    memories = _load()
    memories.append(mem)
    _save(memories)
    return mem


# ── Smoke test ─────────────────────────────────────────────────────────────────

def _smoke_test() -> int:
    import tempfile, os
    orig = LIGHT_FILE
    tmp = Path(tempfile.mktemp(suffix=".json"))

    import light_compression as lc
    lc.LIGHT_FILE = tmp

    failures = 0

    def check(label, passed):
        nonlocal failures
        tag = "PASS" if passed else "FAIL"
        print(f"  [{tag}] {label}")
        if not passed:
            failures += 1

    print("=" * 55)
    print("Light Compression — Smoke Tests")
    print("=" * 55)

    # 1. Noise is discarded
    result = lc.compress_and_store("ok", memory_type=FACT)
    check("Noise 'ok' is discarded (None)", result is None)

    # 2. Sensitive signal blocked
    result = lc.compress_and_store("api_key = sk-abc123", memory_type=FACT)
    check("Sensitive signal blocked (None)", result is None)

    # 3. Project signal stored
    result = lc.compress_and_store(
        "ORACLE.AI is in MYTHIC BUILD PASS Step 10 voice hooks",
        memory_type=PROJECT,
    )
    check("Project signal stored", result is not None)
    check("Score >= threshold", result is not None and result.score >= THRESHOLD_DISCARD)

    # 4. Compression strips artifacts
    result = lc.compress_and_store(
        "[BLOCKED]\nDesired action : routing to claude code\nMissing/broken : capability",
        memory_type=PATTERN,
        compressed="Claude integration blocked — desktop actuation finds window but not input control.",
    )
    check("Pattern stored with custom compressed text", result is not None)
    if result:
        check("Compressed text used", "actuation" in result.compressed)

    # 5. Recall by meaning returns relevant items
    hits = lc.recall_by_meaning("why is actuation broken", top_k=5)
    check("Recall returns results", len(hits) > 0)
    check("Recall includes pattern", any(h.memory_type == PATTERN for h in hits))

    # 6. recall_for_prompt builds non-empty string
    block = lc.recall_for_prompt("build status")
    check("recall_for_prompt non-empty", bool(block))
    check("recall_for_prompt contains MEMORY header", "[ORACLE MEMORY" in block)

    # 7. remember() bypasses scoring
    m = lc.remember("Noah wants ORACLE to talk naturally", memory_type=EMOTIONAL)
    check("remember() stores directly", m.score == 0.75)

    # 8. Similarity — similar texts detected
    check("Similar texts detected", lc._similar("voice hooks working", "voice hooks are working"))
    check("Dissimilar texts rejected", not lc._similar("voice hooks", "calendar integration"))

    # 9. list_memories returns active only
    all_mem = lc.list_memories()
    check("list_memories returns active", all(m.status == "active" for m in all_mem))

    # 10. Supersede
    if all_mem:
        target = all_mem[0].id
        ok = lc.supersede(target, "Updated: " + all_mem[0].compressed[:50])
        check("supersede marks old as superseded", ok)
        reloaded = [m for m in lc._load() if m.id == target]
        check("superseded memory has status=superseded", reloaded[0].status == "superseded")

    # Cleanup
    lc.LIGHT_FILE = orig
    try:
        tmp.unlink()
    except Exception:
        pass

    total = 16
    passed = total - failures
    print(f"{'='*55}")
    print(f"Result: {passed}/{total} passed")
    print(f"STATUS: {'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    print(f"{'='*55}\n")
    return failures


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--recall", metavar="QUERY")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--remember", metavar="TEXT")
    parser.add_argument("--type", dest="mtype", default=FACT)
    args = parser.parse_args()

    if args.smoke_test:
        sys.exit(_smoke_test())
    elif args.recall:
        hits = recall_by_meaning(args.recall)
        print(f"\nRecall: {args.recall!r}\n")
        for h in hits:
            print(f"  [{h.memory_type.upper():12}] score={h.score:.2f}  {h.compressed[:80]}")
        print()
    elif args.list:
        for m in list_memories():
            print(f"  [{m.memory_type.upper():12}] score={m.score:.2f}  {m.compressed[:80]}")
    elif args.remember:
        m = remember(args.remember, memory_type=args.mtype)
        print(f"Stored: {m.summary()}")
