"""
npc_memory.py — NPC memory: episodic, semantic, relational.

Properties:
- Bounded: older low-weight memories decay and are pruned
- Provenance-tagged: every stored belief knows how it was acquired
- Consolidation: high-weight episodic memories move to semantic store
- Retrieval: relevance-ranked, not unlimited replay of raw logs
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from .npc_models import Belief, Memory, MemoryKind, Provenance


MAX_EPISODIC_BUFFER = 50   # prune oldest when exceeded
MAX_SEMANTIC_STORE  = 200
CONSOLIDATION_THRESHOLD = 0.65  # emotional_weight above this → consolidate


@dataclass
class NPCMemory:
    npc_id: str

    # Episodic buffer (recent events, uncompressed)
    episodic_buffer: list[Memory] = field(default_factory=list)

    # Long-term semantic store (compressed, consolidated)
    semantic_store: list[Memory] = field(default_factory=list)

    # Belief store (indexed by subject+predicate key)
    beliefs: dict[str, Belief] = field(default_factory=dict)

    # ── Write ──────────────────────────────────────────────────────────────────

    def store_episode(self, memory: Memory) -> None:
        self.episodic_buffer.append(memory)
        if len(self.episodic_buffer) > MAX_EPISODIC_BUFFER:
            self._prune_episodic()
        if memory.emotional_weight >= CONSOLIDATION_THRESHOLD:
            self._consolidate(memory)

    def update_belief(self, belief: Belief) -> None:
        key = f"{belief.subject}::{belief.predicate}"
        existing = self.beliefs.get(key)
        if existing:
            # Flag as disputed if new belief contradicts
            if existing.value != belief.value:
                belief.disputed_by.append(key)
                existing.disputed_by.append(key)
                existing.provenance = Provenance.DISPUTED
        self.beliefs[key] = belief

    # ── Read ───────────────────────────────────────────────────────────────────

    def retrieve(
        self,
        query_tags: Optional[list[str]] = None,
        participants: Optional[list[str]] = None,
        kind: Optional[MemoryKind] = None,
        limit: int = 10,
    ) -> list[Memory]:
        """Return relevant memories, ranked by recency × emotional weight."""
        now = time.time()
        candidates: list[Memory] = self.episodic_buffer + self.semantic_store

        def score(m: Memory) -> float:
            age_days = (now - m.timestamp) / 86400
            recency = 1.0 / (1.0 + age_days * m.decay_rate)
            tag_match = 0.0
            if query_tags:
                hits = len(set(query_tags) & set(m.tags if hasattr(m, "tags") else []))
                tag_match = hits / max(len(query_tags), 1)
            participant_match = 0.0
            if participants:
                hits = len(set(participants) & set(m.participants))
                participant_match = hits / max(len(participants), 1)
            return recency * 0.4 + m.emotional_weight * 0.3 + tag_match * 0.2 + participant_match * 0.1

        filtered = [m for m in candidates if (kind is None or m.kind == kind)]
        return sorted(filtered, key=score, reverse=True)[:limit]

    def get_beliefs_about(self, subject: str) -> list[Belief]:
        return [b for k, b in self.beliefs.items() if k.startswith(f"{subject}::")]

    def get_belief(self, subject: str, predicate: str) -> Optional[Belief]:
        return self.beliefs.get(f"{subject}::{predicate}")

    def knows_fact(self, subject: str, predicate: str) -> bool:
        b = self.get_belief(subject, predicate)
        return b is not None and b.confidence > 0.3

    # ── Maintenance ────────────────────────────────────────────────────────────

    def tick_decay(self, elapsed_days: float = 1.0) -> None:
        """Reduce confidence on time-sensitive beliefs; prune near-zero."""
        to_remove = []
        for key, belief in self.beliefs.items():
            if belief.decay_rate > 0:
                belief.confidence -= belief.decay_rate * elapsed_days
                if belief.confidence <= 0.05:
                    to_remove.append(key)
        for k in to_remove:
            del self.beliefs[k]

    def _consolidate(self, m: Memory) -> None:
        consolidated = Memory(
            id=m.id + "_consolidated",
            kind=MemoryKind.SEMANTIC,
            summary=m.summary,
            raw_detail="",  # raw detail dropped in long-term
            provenance=m.provenance,
            emotional_weight=m.emotional_weight * 0.9,  # slight attenuation
            timestamp=m.timestamp,
            location=m.location,
            participants=m.participants,
            related_goals=m.related_goals,
            decay_rate=m.decay_rate * 0.5,  # slows further
            consolidated=True,
        )
        self.semantic_store.append(consolidated)
        if len(self.semantic_store) > MAX_SEMANTIC_STORE:
            # Drop the lowest-weight semantic memories
            self.semantic_store.sort(key=lambda x: x.emotional_weight, reverse=True)
            self.semantic_store = self.semantic_store[:MAX_SEMANTIC_STORE]

    def _prune_episodic(self) -> None:
        # Sort by recency × emotional weight; drop the tail
        self.episodic_buffer.sort(
            key=lambda m: m.emotional_weight + (1.0 / (1.0 + (time.time() - m.timestamp) / 3600)),
            reverse=True,
        )
        self.episodic_buffer = self.episodic_buffer[:MAX_EPISODIC_BUFFER]


# ── Factory ────────────────────────────────────────────────────────────────────

def new_memory(
    kind: MemoryKind,
    summary: str,
    provenance: Provenance,
    emotional_weight: float = 0.3,
    raw_detail: str = "",
    location: str = "",
    participants: Optional[list[str]] = None,
    related_goals: Optional[list[str]] = None,
    decay_rate: float = 0.001,
) -> Memory:
    return Memory(
        id=str(uuid.uuid4())[:8],
        kind=kind,
        summary=summary,
        raw_detail=raw_detail or summary,
        provenance=provenance,
        emotional_weight=emotional_weight,
        timestamp=time.time(),
        location=location,
        participants=participants or [],
        related_goals=related_goals or [],
        decay_rate=decay_rate,
    )


def new_belief(
    subject: str,
    predicate: str,
    value,
    provenance: Provenance,
    confidence: float,
    source: str,
    decay_rate: float = 0.0,
    tags: Optional[list[str]] = None,
) -> Belief:
    return Belief(
        subject=subject,
        predicate=predicate,
        value=value,
        provenance=provenance,
        confidence=confidence,
        source=source,
        timestamp=time.time(),
        decay_rate=decay_rate,
        tags=tags or [],
        disputed_by=[],
    )
