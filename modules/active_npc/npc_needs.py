"""
npc_needs.py — NPC needs with changing urgency.

Needs are not emotions. They are persistent states with measurable
urgency that influence goal selection and action candidates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .npc_models import Need, NeedCategory


@dataclass
class NPCNeeds:
    npc_id: str
    needs: list[Need] = field(default_factory=list)

    def add(self, need: Need) -> None:
        self.needs.append(need)

    def most_urgent(self, n: int = 3) -> list[Need]:
        return sorted(self.needs, key=lambda x: x.urgency, reverse=True)[:n]

    def get(self, name: str) -> Optional[Need]:
        return next((nd for nd in self.needs if nd.name == name), None)

    def satisfy(self, name: str, amount: float = 0.3) -> None:
        nd = self.get(name)
        if nd:
            nd.current_level = max(0.0, nd.current_level - amount)
            nd.urgency = _compute_urgency(nd)

    def degrade(self, name: str, amount: float = 0.1) -> None:
        nd = self.get(name)
        if nd:
            nd.current_level = min(1.0, nd.current_level + amount)
            nd.urgency = _compute_urgency(nd)

    def tick(self, elapsed_hours: float = 1.0) -> None:
        """Natural degradation over time."""
        for nd in self.needs:
            if nd.category == NeedCategory.PHYSICAL:
                nd.current_level = min(1.0, nd.current_level + 0.02 * elapsed_hours)
            elif nd.category == NeedCategory.SOCIAL:
                nd.current_level = min(1.0, nd.current_level + 0.01 * elapsed_hours)
            nd.urgency = _compute_urgency(nd)

    def summary(self) -> str:
        urgent = self.most_urgent(3)
        parts = [f"{nd.name}({nd.urgency:.2f})" for nd in urgent]
        return "Needs: " + ", ".join(parts)


def _compute_urgency(nd: Need) -> float:
    # Non-linear: urgency spikes as current_level approaches 1.0
    return nd.current_level ** 2


# ── Default need profiles ──────────────────────────────────────────────────────

def default_needs(npc_id: str) -> NPCNeeds:
    store = NPCNeeds(npc_id=npc_id)
    defs = [
        Need(NeedCategory.PHYSICAL,  "safety",          urgency=0.1, current_level=0.1, description="Freedom from immediate harm", satisfiers=["flee", "move", "attack"]),
        Need(NeedCategory.PHYSICAL,  "sustenance",      urgency=0.1, current_level=0.2, description="Food and water", satisfiers=["rest", "give", "request"]),
        Need(NeedCategory.EMOTIONAL, "respect",         urgency=0.1, current_level=0.2, description="Being treated with dignity", satisfiers=["dialogue", "refuse"]),
        Need(NeedCategory.SOCIAL,    "connection",      urgency=0.1, current_level=0.3, description="Meaningful contact with others", satisfiers=["dialogue", "request"]),
        Need(NeedCategory.STRATEGIC, "information",     urgency=0.1, current_level=0.5, description="Understanding of current situation", satisfiers=["investigate", "dialogue"]),
        Need(NeedCategory.ROLE,      "duty_fulfillment",urgency=0.1, current_level=0.2, description="Meeting role obligations", satisfiers=["give", "request", "move"]),
    ]
    for nd in defs:
        nd.urgency = _compute_urgency(nd)
        store.add(nd)
    return store
