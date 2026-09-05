"""
npc_perception.py — Convert world events into NPC observations.

NPCs only reason from what they perceived, were told, inferred, or
already knew. No omniscience. No teleporting knowledge.
"""
from __future__ import annotations

import time
from typing import Optional

from .npc_models import Observation, Provenance, WorldEvent
from .npc_identity import NPCIdentity
from .npc_world_model import NPCWorldModel


class NPCPerception:
    def __init__(self, identity: NPCIdentity, world_model: NPCWorldModel):
        self.identity = identity
        self.world_model = world_model

    def perceive(self, event: WorldEvent) -> Optional[Observation]:
        """
        Decide whether and how this NPC perceives a world event.
        Returns None if the NPC could not have known about this event.
        """
        npc_id = self.identity.npc_id
        current_loc = self.world_model.current_location

        # Direct witness: NPC is at the event location
        at_scene = (current_loc == event.location or npc_id in event.participants)

        # Indirect: NPC was mentioned; public events they could hear about
        mentioned = npc_id in event.participants
        public_reachable = event.public and self._can_hear_about(event)

        if not (at_scene or mentioned or public_reachable):
            return None

        provenance = Provenance.OBSERVED if (at_scene or mentioned) else Provenance.REPORTED

        return Observation(
            event_id=event.id,
            event_type=event.kind,
            description=self._filter_description(event, at_scene),
            perceived_by=npc_id,
            timestamp=time.time(),
            location=event.location,
            participants=event.participants,
            raw_data=event.data,
        )

    def _can_hear_about(self, event: WorldEvent) -> bool:
        """
        Public events propagate if someone the NPC knows was involved,
        or the event is loud/large enough to be general knowledge.
        """
        if event.magnitude >= 0.7:
            return True
        known_entities = set(self.world_model.entities.keys())
        overlap = known_entities & set(event.participants)
        return len(overlap) > 0

    def _filter_description(self, event: WorldEvent, at_scene: bool) -> str:
        """
        At-scene NPCs get the full description.
        Reported NPCs get a rumor-style summary (may be incomplete).
        """
        if at_scene:
            return event.description
        # Reported version: strip internal detail, add uncertainty
        words = event.description.split()
        truncated = " ".join(words[:20])
        if len(words) > 20:
            truncated += "…"
        return f"Heard that: {truncated}"

    def relevance_score(self, observation: Observation) -> float:
        """How relevant is this observation to this NPC? 0–1."""
        score = 0.0
        npc_id = self.identity.npc_id

        # Direct involvement
        if npc_id in observation.participants:
            score += 0.5

        # Known entities involved
        known = set(self.world_model.entities.keys())
        overlap = len(known & set(observation.participants))
        score += min(0.3, overlap * 0.1)

        # Location familiarity
        if self.world_model.knows_location(observation.location):
            score += 0.1

        # Threat/opportunity keywords
        threat_words = {"attack", "kill", "arrest", "fire", "danger", "war", "ward", "flare"}
        opp_words = {"reward", "offer", "gold", "opportunity", "help", "found", "charm", "rune"}
        desc_lower = observation.description.lower()
        if any(w in desc_lower for w in threat_words):
            score += 0.2
        if any(w in desc_lower for w in opp_words):
            score += 0.1

        return min(1.0, score)
