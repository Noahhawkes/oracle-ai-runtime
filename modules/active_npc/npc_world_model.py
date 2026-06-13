"""
npc_world_model.py — The NPC's incomplete, possibly mistaken map of the world.

Deliberately separate from objective world state. An NPC believes
what they observed, were told, inferred, or assumed — not what is
actually true. This model may contain false information.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from .npc_models import Belief, Provenance
from .npc_memory import new_belief


@dataclass
class LocationBelief:
    name: str
    known: bool = True
    description: str = ""
    safety_estimate: float = 0.5   # 0=very dangerous, 1=very safe (NPC's view)
    last_visited: Optional[float] = None


@dataclass
class EntityBelief:
    entity_id: str
    name: str
    known_role: str = "unknown"
    faction: str = "unknown"
    believed_location: str = "unknown"
    believed_disposition: str = "neutral"  # toward the NPC
    last_known_timestamp: Optional[float] = None
    provenance: Provenance = Provenance.ASSUMED


@dataclass
class FactionBelief:
    name: str
    disposition_toward_npc: float = 0.0  # -1 hostile, +1 allied
    believed_goals: list[str] = field(default_factory=list)
    known_members: list[str] = field(default_factory=list)
    provenance: Provenance = Provenance.ASSUMED


@dataclass
class ThreatBelief:
    description: str
    severity: float          # 0–1
    source: str
    provenance: Provenance
    timestamp: float
    resolved: bool = False


@dataclass
class OpportunityBelief:
    description: str
    value: float             # 0–1 estimated value
    provenance: Provenance
    timestamp: float
    expired: bool = False


@dataclass
class NPCWorldModel:
    """The world as this NPC understands it — partial and fallible."""
    npc_id: str

    locations: dict[str, LocationBelief] = field(default_factory=dict)
    entities: dict[str, EntityBelief] = field(default_factory=dict)
    factions: dict[str, FactionBelief] = field(default_factory=dict)
    threats: list[ThreatBelief] = field(default_factory=list)
    opportunities: list[OpportunityBelief] = field(default_factory=list)
    recent_events: list[str] = field(default_factory=list)  # plain summaries, NPC's version

    # Current situational awareness
    current_location: str = "unknown"
    time_of_day: str = "unknown"
    general_threat_level: float = 0.2

    # ── Queries ───────────────────────────────────────────────────────────────

    def knows_entity(self, entity_id: str) -> bool:
        return entity_id in self.entities

    def get_entity(self, entity_id: str) -> Optional[EntityBelief]:
        return self.entities.get(entity_id)

    def believed_location_of(self, entity_id: str) -> str:
        e = self.entities.get(entity_id)
        return e.believed_location if e else "unknown"

    def active_threats(self) -> list[ThreatBelief]:
        return [t for t in self.threats if not t.resolved]

    def active_opportunities(self) -> list[OpportunityBelief]:
        return [o for o in self.opportunities if not o.expired]

    def knows_location(self, name: str) -> bool:
        return name in self.locations and self.locations[name].known

    # ── Updates ───────────────────────────────────────────────────────────────

    def observe_entity(
        self, entity_id: str, name: str, role: str, location: str,
        disposition: str = "neutral", provenance: Provenance = Provenance.OBSERVED,
    ) -> None:
        self.entities[entity_id] = EntityBelief(
            entity_id=entity_id,
            name=name,
            known_role=role,
            believed_location=location,
            believed_disposition=disposition,
            last_known_timestamp=time.time(),
            provenance=provenance,
        )

    def hear_about_entity(
        self, entity_id: str, name: str, role: str,
        location: str = "unknown", source: str = "unknown",
    ) -> None:
        if entity_id not in self.entities:
            self.entities[entity_id] = EntityBelief(
                entity_id=entity_id,
                name=name,
                known_role=role,
                believed_location=location,
                provenance=Provenance.REPORTED,
                last_known_timestamp=time.time(),
            )
        else:
            existing = self.entities[entity_id]
            if existing.provenance not in (Provenance.OBSERVED,):
                existing.believed_location = location
                existing.provenance = Provenance.REPORTED
                existing.last_known_timestamp = time.time()

    def add_threat(
        self, description: str, severity: float, source: str,
        provenance: Provenance = Provenance.OBSERVED,
    ) -> None:
        self.threats.append(ThreatBelief(
            description=description, severity=severity,
            source=source, provenance=provenance, timestamp=time.time(),
        ))
        self.general_threat_level = min(1.0, self.general_threat_level + severity * 0.2)

    def add_opportunity(
        self, description: str, value: float,
        provenance: Provenance = Provenance.INFERRED,
    ) -> None:
        self.opportunities.append(OpportunityBelief(
            description=description, value=value,
            provenance=provenance, timestamp=time.time(),
        ))

    def record_event(self, summary: str) -> None:
        self.recent_events.append(summary)
        if len(self.recent_events) > 20:
            self.recent_events = self.recent_events[-20:]

    def resolve_threat(self, description_fragment: str) -> None:
        for t in self.threats:
            if description_fragment.lower() in t.description.lower():
                t.resolved = True
