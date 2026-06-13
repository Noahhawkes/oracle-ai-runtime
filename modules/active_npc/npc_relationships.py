"""
npc_relationships.py — Per-entity relationship state with remembered interactions.

Every known entity gets its own Relationship record. Changes are incremental
and bounded — no sudden resets, no emotional teleportation.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from .npc_models import Relationship


_CLAMP = lambda v, lo=-1.0, hi=1.0: max(lo, min(hi, v))


@dataclass
class NPCRelationships:
    npc_id: str
    records: dict[str, Relationship] = field(default_factory=dict)

    def get(self, entity_id: str) -> Optional[Relationship]:
        return self.records.get(entity_id)

    def get_or_default(self, entity_id: str, name: str = "unknown") -> Relationship:
        if entity_id not in self.records:
            self.records[entity_id] = Relationship(
                entity_id=entity_id, name=name,
                trust=0.0, affection=0.0, fear=0.0,
                respect=0.3, resentment=0.0, loyalty=0.0,
                familiarity=0.0, debt=0.0,
            )
        return self.records[entity_id]

    def record_interaction(
        self,
        entity_id: str,
        name: str,
        summary: str,
        trust_delta: float = 0.0,
        affection_delta: float = 0.0,
        fear_delta: float = 0.0,
        respect_delta: float = 0.0,
        resentment_delta: float = 0.0,
        familiarity_delta: float = 0.05,
        debt_delta: float = 0.0,
    ) -> None:
        rel = self.get_or_default(entity_id, name)
        rel.trust       = _CLAMP(rel.trust + trust_delta)
        rel.affection   = _CLAMP(rel.affection + affection_delta)
        rel.fear        = _CLAMP(rel.fear + fear_delta, 0.0, 1.0)
        rel.respect     = _CLAMP(rel.respect + respect_delta, 0.0, 1.0)
        rel.resentment  = _CLAMP(rel.resentment + resentment_delta, 0.0, 1.0)
        rel.familiarity = _CLAMP(rel.familiarity + familiarity_delta, 0.0, 1.0)
        rel.debt       += debt_delta
        rel.last_interaction_summary = summary
        rel.interaction_count += 1

    def disposition_toward(self, entity_id: str) -> str:
        rel = self.records.get(entity_id)
        if not rel: return "neutral (stranger)"
        score = rel.trust * 0.4 + rel.affection * 0.3 + rel.respect * 0.2 - rel.resentment * 0.1
        if rel.fear > 0.7: return "fearful"
        if score > 0.6: return "friendly"
        if score > 0.2: return "cautious-positive"
        if score > -0.2: return "neutral"
        if score > -0.5: return "suspicious"
        return "hostile"

    def trusts(self, entity_id: str, threshold: float = 0.3) -> bool:
        rel = self.records.get(entity_id)
        return rel is not None and rel.trust >= threshold

    def fears(self, entity_id: str, threshold: float = 0.5) -> bool:
        rel = self.records.get(entity_id)
        return rel is not None and rel.fear >= threshold

    def owes(self, entity_id: str) -> bool:
        rel = self.records.get(entity_id)
        return rel is not None and rel.debt < 0

    def summary(self, entity_id: str) -> str:
        rel = self.records.get(entity_id)
        if not rel: return f"No relationship with {entity_id}."
        return (
            f"{rel.name}: trust={rel.trust:+.2f} aff={rel.affection:+.2f} "
            f"fear={rel.fear:.2f} resp={rel.respect:.2f} "
            f"res={rel.resentment:.2f} fam={rel.familiarity:.2f} "
            f"debt={rel.debt:+.2f} — {self.disposition_toward(entity_id)}"
        )

    def all_summaries(self) -> list[str]:
        return [self.summary(eid) for eid in self.records]
