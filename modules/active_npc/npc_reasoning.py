"""
npc_reasoning.py — Produces candidate interpretations and actions.

Reasoning is deterministic given the NPC's state. It does not
hallucinate knowledge the NPC does not possess.
"""
from __future__ import annotations

from typing import Optional

from .npc_models import (
    ActionKind, CandidateAction, Observation,
    Provenance,
)
from .npc_identity import NPCIdentity
from .npc_memory import NPCMemory
from .npc_needs import NPCNeeds
from .npc_goals import NPCGoals
from .npc_relationships import NPCRelationships
from .npc_world_model import NPCWorldModel


class NPCReasoning:

    def __init__(
        self,
        identity: NPCIdentity,
        memory: NPCMemory,
        needs: NPCNeeds,
        goals: NPCGoals,
        relationships: NPCRelationships,
        world_model: NPCWorldModel,
    ):
        self.identity = identity
        self.memory = memory
        self.needs = needs
        self.goals = goals
        self.relationships = relationships
        self.world_model = world_model

    def generate_candidates(
        self,
        observation: Optional[Observation],
        interacting_with: Optional[str] = None,
    ) -> list[CandidateAction]:
        """
        Produce a ranked list of candidate actions from current state.
        Every candidate includes a rationale traceable to NPC state.
        """
        candidates: list[CandidateAction] = []

        urgent_needs = self.needs.most_urgent(3)
        top_goal = self.goals.top_priority()
        threats = self.world_model.active_threats()
        rel = self.relationships.get(interacting_with) if interacting_with else None
        disposition = self.relationships.disposition_toward(interacting_with) if interacting_with else "neutral"

        # ── Threat response ────────────────────────────────────────────────────
        for threat in threats:
            if threat.severity > 0.7:
                if self.identity.traits.courage < 0.4:
                    candidates.append(CandidateAction(
                        kind=ActionKind.FLEE,
                        target=None,
                        content="Flee from immediate danger",
                        rationale=f"High threat '{threat.description}'; low courage ({self.identity.traits.courage:.1f})",
                        need_score=0.9,
                        goal_score=0.1,
                        relationship_score=0.0,
                        risk=0.3,
                        feasibility=self.identity.physical_capability,
                    ))
                else:
                    candidates.append(CandidateAction(
                        kind=ActionKind.INVESTIGATE,
                        target=threat.source,
                        content=f"Assess the threat from {threat.source}",
                        rationale=f"Threat '{threat.description}'; courage ({self.identity.traits.courage:.1f}) supports investigation",
                        need_score=0.7,
                        goal_score=0.3,
                        relationship_score=0.0,
                        risk=0.5,
                        feasibility=self.identity.physical_capability * 0.8,
                    ))

        # ── Goal-directed action ───────────────────────────────────────────────
        if top_goal:
            if interacting_with and disposition not in ("hostile", "suspicious"):
                trust = rel.trust if rel else 0.0
                candidates.append(CandidateAction(
                    kind=ActionKind.DIALOGUE,
                    target=interacting_with,
                    content=f"[pursuing goal: {top_goal.name}]",
                    rationale=f"Top goal '{top_goal.name}' (p={top_goal.priority:.1f}); "
                               f"interacting with entity",
                    need_score=0.3,
                    goal_score=top_goal.priority,
                    relationship_score=max(0.0, trust),
                    risk=0.1 if trust > 0 else 0.3,
                    feasibility=0.9,
                ))

        # ── Need-driven action ────────────────────────────────────────────────
        for need in urgent_needs:
            if need.urgency > 0.5 and need.satisfiers:
                kind_str = need.satisfiers[0]
                try:
                    kind = ActionKind(kind_str)
                except ValueError:
                    kind = ActionKind.WAIT
                candidates.append(CandidateAction(
                    kind=kind,
                    target=interacting_with,
                    content=f"Address need: {need.name}",
                    rationale=f"Need '{need.name}' urgency={need.urgency:.2f}",
                    need_score=need.urgency,
                    goal_score=0.1,
                    relationship_score=0.0,
                    risk=0.2,
                    feasibility=0.8,
                ))

        # ── Relationship-influenced action ─────────────────────────────────────
        if rel and interacting_with:
            if rel.fear > 0.6:
                candidates.append(CandidateAction(
                    kind=ActionKind.FLEE,
                    target=None,
                    content=f"Avoid {rel.name} due to fear",
                    rationale=f"Fear of {rel.name} = {rel.fear:.2f}",
                    need_score=0.6,
                    goal_score=0.0,
                    relationship_score=0.0,
                    risk=0.2,
                    feasibility=self.identity.physical_capability,
                ))
            elif rel.trust < -0.3:
                candidates.append(CandidateAction(
                    kind=ActionKind.REFUSE,
                    target=interacting_with,
                    content=f"Refuse to engage with {rel.name}",
                    rationale=f"Trust of {rel.name} = {rel.trust:.2f}; negative",
                    need_score=0.2,
                    goal_score=0.2,
                    relationship_score=0.4,
                    risk=0.1,
                    feasibility=1.0,
                ))

        # ── Default: wait / observe ────────────────────────────────────────────
        candidates.append(CandidateAction(
            kind=ActionKind.WAIT,
            target=None,
            content="Observe and wait",
            rationale="No urgent action required",
            need_score=0.0,
            goal_score=0.0,
            relationship_score=0.0,
            risk=0.0,
            feasibility=1.0,
        ))

        return sorted(candidates, key=lambda c: c.total_score, reverse=True)

    def interpret_observation(self, obs: Observation) -> list[str]:
        """
        Produce a list of interpretations the NPC might draw from an observation.
        Each interpretation is bounded by what the NPC already knows.
        """
        interpretations = []
        desc = obs.description.lower()

        for participant in obs.participants:
            if participant == self.identity.npc_id:
                continue
            entity = self.world_model.get_entity(participant)
            if entity:
                interpretations.append(
                    f"{entity.name} was present — known as {entity.known_role} of {entity.faction}"
                )
            else:
                interpretations.append(
                    f"Unknown participant: '{participant}' — no prior knowledge"
                )

        if "attack" in desc or "killed" in desc or "murder" in desc:
            interpretations.append("This event involved violence — threat level should increase")

        if "gold" in desc or "reward" in desc or "payment" in desc:
            if self.identity.traits.pragmatism > 0.5:
                interpretations.append("Potential financial opportunity detected")

        if not interpretations:
            interpretations.append("Event noted; insufficient context to draw specific conclusions")

        return interpretations
