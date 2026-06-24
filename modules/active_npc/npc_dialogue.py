"""
npc_dialogue.py — Generate dialogue from actual NPC state.

Dialogue must not reveal knowledge the NPC does not possess.
Style is determined by vocabulary_level, verbosity, and current
emotional context — not by making the NPC sound theatrical.
"""
from __future__ import annotations

from typing import Optional

from .npc_models import ActionKind, CandidateAction, Provenance
from .npc_identity import NPCIdentity
from .npc_memory import NPCMemory
from .npc_relationships import NPCRelationships
from .npc_world_model import NPCWorldModel
from .npc_goals import NPCGoals
from .npc_needs import NPCNeeds


class NPCDialogue:

    def __init__(
        self,
        identity: NPCIdentity,
        memory: NPCMemory,
        relationships: NPCRelationships,
        world_model: NPCWorldModel,
        goals: NPCGoals,
        needs: NPCNeeds,
    ):
        self.identity = identity
        self.memory = memory
        self.relationships = relationships
        self.world_model = world_model
        self.goals = goals
        self.needs = needs

    def generate(
        self,
        action: CandidateAction,
        target_entity_id: Optional[str],
        player_input: Optional[str] = None,
    ) -> str:
        """
        Generate a single dialogue line or refusal appropriate to the
        NPC's actual state. Never invents knowledge not held in memory or beliefs.
        """
        target_name = self._target_name(target_entity_id)
        rel = self.relationships.get(target_entity_id) if target_entity_id else None
        disposition = self.relationships.disposition_toward(target_entity_id) if target_entity_id else "neutral"

        if action.kind == ActionKind.REFUSE:
            return self._refuse(target_name, rel, disposition)

        if action.kind == ActionKind.FLEE:
            return self._flee_line(target_name)

        if action.kind == ActionKind.WAIT:
            return self._idle_line()

        if action.kind == ActionKind.INVESTIGATE:
            return self._investigate_line(action.target)

        if action.kind == ActionKind.DIALOGUE:
            if self._is_arcane_action(action):
                return self._arcane_line(action, target_name, rel, disposition)
            return self._dialogue_line(action, target_name, rel, disposition, player_input)

        if action.kind == ActionKind.REQUEST:
            return self._request_line(target_name, rel)

        if action.kind == ActionKind.DECEIVE:
            return self._deceive_line(target_name)

        return f"{self.identity.name} says nothing and looks away."

    # ── Line generators ────────────────────────────────────────────────────────

    def _refuse(self, target_name: str, rel, disposition: str) -> str:
        if disposition == "hostile":
            return self._style(f"I have nothing to say to you{', ' + target_name if target_name else ''}.")
        if rel and rel.fear > 0.5:
            return self._style(f"I'd rather not get involved in this.")
        return self._style(f"That's not something I'm willing to do.")

    def _flee_line(self, target_name: str) -> str:
        return self._style("I need to go. Now.")

    def _idle_line(self) -> str:
        top_goal = self.goals.top_priority()
        if top_goal and self.identity.traits.extraversion < 0.3:
            return self._style(f"…")
        if top_goal:
            return self._style(f"I've got things to attend to.")
        return self._style(f".")

    def _investigate_line(self, target: Optional[str]) -> str:
        if target == "stonecroft_forge_ward":
            return self._style("The ward is wrong. Keep back unless I ask you to hold iron.")
        if target:
            known = self.world_model.get_entity(target)
            if known:
                return self._style(f"I've heard of {known.name}. What do you know about them?")
            return self._style(f"Who's this '{target}' you're talking about?")
        return self._style("What's going on here?")

    def _dialogue_line(self, action: CandidateAction, target_name: str, rel, disposition: str, player_input: Optional[str]) -> str:
        top_goal = self.goals.top_priority()
        urgent_need = self.needs.most_urgent(1)

        # If NPC doesn't know something relevant to what was asked, say so
        if player_input:
            # Check if player asked about something NPC doesn't know
            unknown_markers = ["where is", "who is", "what happened", "did you see"]
            for marker in unknown_markers:
                if marker in player_input.lower():
                    # Extract subject
                    subject = player_input.lower().replace(marker, "").strip().rstrip("?")
                    beliefs = self.memory.get_beliefs_about(subject)
                    if not beliefs:
                        return self._style(f"I don't know anything about that.")
                    # Find first observed/reported belief
                    for b in beliefs:
                        if b.provenance in (Provenance.OBSERVED, Provenance.REPORTED):
                            qualifier = "I heard that" if b.provenance == Provenance.REPORTED else "I saw"
                            return self._style(f"{qualifier} {b.value}.")
                    return self._style(f"I'm not sure. That's just what I assumed.")

        # Goal-pursuing dialogue
        if top_goal and disposition not in ("hostile",):
            committed = top_goal.committed_to
            if target_name in committed:
                return self._style(f"I still intend to {top_goal.description.lower()}. I haven't forgotten.")
            return self._style(f"I need to {top_goal.description.lower()}.")

        # Need-driven
        if urgent_need and urgent_need[0].urgency > 0.6:
            nd = urgent_need[0]
            return self._style(f"I need to deal with something. {nd.description}.")

        # Default: acknowledge and deflect if uncomfortable
        if disposition in ("suspicious", "hostile"):
            return self._style(f"What do you want from me?")

        return self._style(f"What is it?")

    def _arcane_line(self, action: CandidateAction, target_name: str, rel, disposition: str) -> str:
        if disposition == "hostile":
            return self._style("Do not put that charm on my anvil.")
        if rel and rel.trust < -0.2:
            return self._style("Set it down slowly. I will judge whether it is clean.")
        if rel and rel.trust > 0.25:
            return self._style(f"All right{', ' + target_name if target_name else ''}. Lay the charm by the tongs and keep your hand steady.")
        return self._style("Lay it by the tongs. If the rune bites, step away.")

    def _request_line(self, target_name: str, rel) -> str:
        if rel and rel.trust > 0.4:
            return self._style(f"I could use your help, {target_name}." if target_name else "I could use some help.")
        return self._style(f"I'm asking. Not demanding.")

    def _deceive_line(self, target_name: str) -> str:
        if self.identity.traits.honesty_base > 0.8:
            # High-honesty NPC will hedge rather than outright lie
            return self._style("I don't think that's any of your concern.")
        return self._style("Everything's fine. Nothing to worry about.")

    # ── Style ──────────────────────────────────────────────────────────────────

    def _target_name(self, entity_id: Optional[str]) -> str:
        if not entity_id: return ""
        e = self.world_model.get_entity(entity_id)
        return e.name if e else entity_id

    def _is_arcane_action(self, action: CandidateAction) -> bool:
        text = f"{action.target or ''} {action.content}".lower()
        return any(token in text for token in ("arcane", "ward", "rune", "charm", "magic"))

    def _style(self, text: str) -> str:
        """Apply vocabulary and verbosity style."""
        prefix = f"{self.identity.name}: "
        if self.identity.vocabulary_level == "simple":
            text = text.lower()
        elif self.identity.vocabulary_level == "noble":
            text = text[0].upper() + text[1:] if text else text
        if self.identity.verbosity == "terse" and len(text) > 60:
            text = text[:57].rstrip() + "…"
        return prefix + text
