"""
npc_runtime.py — Perceive → Interpret → Remember → Decide → Act → Consolidate.

The full cognitive loop. One NPC per instance. Stateful across calls.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from .npc_models import (
    ActionKind, MemoryKind, Provenance, SelectedAction, WorldEvent,
)
from .npc_identity import NPCIdentity
from .npc_memory import NPCMemory, new_memory, new_belief
from .npc_needs import NPCNeeds
from .npc_goals import NPCGoals, make_goal
from .npc_relationships import NPCRelationships
from .npc_world_model import NPCWorldModel
from .npc_perception import NPCPerception
from .npc_reasoning import NPCReasoning
from .npc_action_policy import NPCActionPolicy, PolicyContext
from .npc_dialogue import NPCDialogue


@dataclass
class CycleResult:
    """Full output of one perceive-decide-act cycle."""
    npc_id: str
    event_id: str
    observed: bool
    observation_summary: str
    interpretations: list[str]
    selected_action_kind: str
    dialogue: Optional[str]
    world_effect: Optional[str]
    policy_explanation: str
    timestamp: float = field(default_factory=time.time)


class NPCRuntime:

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

        # Sub-systems
        self.perception  = NPCPerception(identity, world_model)
        self.reasoning   = NPCReasoning(identity, memory, needs, goals, relationships, world_model)
        self.policy      = NPCActionPolicy(identity, world_model)
        self.dialogue    = NPCDialogue(identity, memory, relationships, world_model, goals, needs)

        self._cycle_count = 0

    # ── Main loop entry point ──────────────────────────────────────────────────

    def process_event(
        self,
        event: WorldEvent,
        interacting_with: Optional[str] = None,
        player_input: Optional[str] = None,
        policy_ctx: Optional[PolicyContext] = None,
    ) -> CycleResult:
        self._cycle_count += 1
        npc = self.identity

        # 1. Perception
        observation = self.perception.perceive(event)
        if observation is None:
            return CycleResult(
                npc_id=npc.npc_id,
                event_id=event.id,
                observed=False,
                observation_summary="Event not perceived.",
                interpretations=[],
                selected_action_kind="none",
                dialogue=None,
                world_effect=None,
                policy_explanation="Event not in perceptual range.",
            )

        # 2. Relevance filter
        relevance = self.perception.relevance_score(observation)
        if relevance < 0.05:
            # Too low relevance — NPC notices but does not act
            return CycleResult(
                npc_id=npc.npc_id, event_id=event.id, observed=True,
                observation_summary=observation.description,
                interpretations=["Noted; not relevant enough to act on."],
                selected_action_kind="wait",
                dialogue=None, world_effect=None,
                policy_explanation="Relevance below threshold.",
            )

        # 3. Memory retrieval — recent relevant memories
        context_memories = self.memory.retrieve(
            participants=observation.participants, limit=5
        )

        # 4. Belief update from observation
        self._update_beliefs_from_observation(observation)

        # 5. Goal update from event
        self.goals.update_from_event(event.description)
        self._update_arcane_goal_from_event(event)

        # 6. Interpretation
        interpretations = self.reasoning.interpret_observation(observation)

        # 7. World model update
        self.world_model.record_event(observation.description)
        self._update_world_model_from_event(event, observation)

        # 8. Candidate actions
        candidates = self.reasoning.generate_candidates(observation, interacting_with)

        # 9. Policy selection
        ctx = policy_ctx or PolicyContext(
            current_location=self.world_model.current_location,
            target_reachable=interacting_with is not None or event.location == self.world_model.current_location,
        )
        selected, rejections = self.policy.select(candidates, ctx)
        explanation = self.policy.explain(selected, rejections)

        # 10. Dialogue / world effect
        generated_dialogue = None
        world_effect = None
        if selected.kind == ActionKind.DIALOGUE or player_input:
            generated_dialogue = self.dialogue.generate(selected, interacting_with, player_input)
        elif selected.kind == ActionKind.FLEE:
            world_effect = f"{npc.name} moves away from {self.world_model.current_location}."
        elif selected.kind == ActionKind.ATTACK:
            world_effect = f"{npc.name} attacks {selected.target}."
        elif selected.kind == ActionKind.MOVE:
            world_effect = f"{npc.name} moves toward {selected.target}."

        # 11. Memory consolidation — store this experience
        mem = new_memory(
            kind=MemoryKind.EPISODIC,
            summary=f"Event '{event.kind}' at {event.location}. Responded with {selected.kind.value}.",
            provenance=Provenance.OBSERVED,
            emotional_weight=min(1.0, event.magnitude + 0.1),
            location=event.location,
            participants=event.participants,
        )
        self.memory.store_episode(mem)

        # 12. Need updates from event type
        self._update_needs_from_event(event)

        # 13. Relationship update if interacting
        if interacting_with:
            rel_delta = self._compute_relationship_delta(selected, event)
            self.relationships.record_interaction(
                interacting_with,
                self.world_model.believed_location_of(interacting_with),
                summary=observation.description[:80],
                **rel_delta,
            )

        return CycleResult(
            npc_id=npc.npc_id,
            event_id=event.id,
            observed=True,
            observation_summary=observation.description,
            interpretations=interpretations,
            selected_action_kind=selected.kind.value,
            dialogue=generated_dialogue,
            world_effect=world_effect,
            policy_explanation=explanation,
        )

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _update_beliefs_from_observation(self, obs) -> None:
        for participant in obs.participants:
            if participant == self.identity.npc_id:
                continue
            existing_entity = self.world_model.get_entity(participant)
            if existing_entity:
                # Update known location
                b = new_belief(
                    subject=participant,
                    predicate="location",
                    value=obs.location,
                    provenance=obs.raw_data.get("provenance", Provenance.OBSERVED)
                              if isinstance(obs.raw_data.get("provenance"), Provenance)
                              else Provenance.OBSERVED,
                    confidence=0.9,
                    source="direct_observation",
                )
                self.memory.update_belief(b)
                # Update world model
                existing_entity.believed_location = obs.location
                existing_entity.last_known_timestamp = time.time()

        if _is_arcane_event(obs.event_type, obs.description):
            desc = obs.description.lower()
            if "stabilize" in desc or "quieting rune" in desc:
                ward_state = "stabilizing charm offered; could calm the forge ward"
                confidence = 0.72
            elif "flare" in desc or "hums" in desc:
                ward_state = "unstable; blue-white resonance above the anvil"
                confidence = 0.82
            else:
                ward_state = "arcane activity observed at the forge"
                confidence = 0.65

            self.memory.update_belief(new_belief(
                subject="stonecroft_forge_ward",
                predicate="state",
                value=ward_state,
                provenance=Provenance.OBSERVED,
                confidence=confidence,
                source="direct_observation",
                decay_rate=0.03,
                tags=["magic", "forge", "ward"],
            ))

    def _update_arcane_goal_from_event(self, event: WorldEvent) -> None:
        if not _is_arcane_event(event.kind, event.description):
            return

        desc = event.description.lower()
        active_ward_goal = next(
            (g for g in self.goals.active() if g.name == "Stabilize forge ward"),
            None,
        )
        if "stabilize" in desc or "quieting rune" in desc:
            if active_ward_goal:
                self.goals.complete(active_ward_goal.id)
            return

        if active_ward_goal:
            return

        self.goals.add(make_goal(
            name="Stabilize forge ward",
            description="keep the forge ward from cracking or drawing danger",
            priority=0.78,
            horizon="immediate",
            conditions_to_complete=["ward stabilized", "stabilizing charm", "quieting rune"],
            conditions_to_abandon=["forge ward breaks", "forge destroyed"],
            committed_to=["village of Stonecroft"],
        ))

    def _update_world_model_from_event(self, event: WorldEvent, observation) -> None:
        kind_lower = event.kind.lower()
        if "attack" in kind_lower or "threat" in kind_lower:
            self.world_model.add_threat(
                event.description,
                event.magnitude,
                event.participants[0] if event.participants else "unknown",
                provenance=observation and Provenance.OBSERVED or Provenance.REPORTED,
            )

        if not _is_arcane_event(event.kind, event.description):
            return

        desc = event.description.lower()
        if "stabilize" in desc or "quieting rune" in desc:
            self.world_model.add_opportunity(
                "A stabilizing charm may calm the forge ward",
                value=0.7,
                provenance=Provenance.OBSERVED,
            )
            self.world_model.resolve_threat("forge ward")
        else:
            self.world_model.add_threat(
                event.description,
                severity=min(0.9, event.magnitude + 0.1),
                source="stonecroft_forge_ward",
                provenance=Provenance.OBSERVED,
            )

    def _update_needs_from_event(self, event: WorldEvent) -> None:
        kind_lower = event.kind.lower()
        if "threat" in kind_lower or "attack" in kind_lower:
            self.needs.degrade("safety", 0.2 * event.magnitude)
        if _is_arcane_event(event.kind, event.description):
            desc = event.description.lower()
            if "stabilize" in desc or "quieting rune" in desc:
                self.needs.satisfy("safety", 0.12)
                self.needs.satisfy("information", 0.2)
                self.needs.satisfy("duty_fulfillment", 0.1)
            else:
                self.needs.degrade("safety", 0.12 * event.magnitude)
                self.needs.degrade("information", 0.18)
                self.needs.degrade("duty_fulfillment", 0.08)
        if "resolved" in kind_lower or "peace" in kind_lower:
            self.needs.satisfy("safety", 0.15)
        if "social" in kind_lower or "conversation" in kind_lower:
            self.needs.satisfy("connection", 0.1)

    def _compute_relationship_delta(self, action, event: WorldEvent) -> dict:
        delta: dict = {"trust_delta": 0.0, "familiarity_delta": 0.05}
        kind_lower = event.kind.lower()
        if "threat" in kind_lower or "attack" in kind_lower:
            delta["fear_delta"] = 0.15
            delta["trust_delta"] = -0.1
        if "help" in kind_lower or "assist" in kind_lower:
            delta["trust_delta"] = 0.1
            delta["affection_delta"] = 0.05
        if _is_arcane_event(event.kind, event.description):
            desc = event.description.lower()
            if "stabilize" in desc or "quieting rune" in desc:
                delta["trust_delta"] = delta.get("trust_delta", 0.0) + 0.08
                delta["respect_delta"] = 0.05
            else:
                delta["fear_delta"] = delta.get("fear_delta", 0.0) + 0.05
        if action.kind == ActionKind.REFUSE:
            delta["resentment_delta"] = 0.05
        return delta

    def state_summary(self) -> str:
        n = self.identity
        lines = [
            f"=== {n.name} ({n.role}, {n.faction}) ===",
            f"Location: {self.world_model.current_location}",
            self.needs.summary(),
            self.goals.summary(),
            f"Beliefs: {len(self.memory.beliefs)} stored",
            f"Episodes: {len(self.memory.episodic_buffer)} in buffer",
            f"Threats: {len(self.world_model.active_threats())} active",
            f"Cycles run: {self._cycle_count}",
        ]
        return "\n".join(lines)


def _is_arcane_event(kind: str, description: str) -> bool:
    text = f"{kind} {description}".lower()
    return any(token in text for token in ("arcane", "ward", "rune", "charm", "magic"))
