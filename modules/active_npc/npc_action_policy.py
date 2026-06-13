"""
npc_action_policy.py — Choose one bounded action from candidates.

Enforces: game rules, authority limits, physical capability,
location constraints, resource availability. No capability inflation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .npc_models import ActionKind, CandidateAction
from .npc_identity import NPCIdentity
from .npc_world_model import NPCWorldModel


@dataclass
class PolicyContext:
    """Everything the policy checker needs that is not already in the NPC."""
    current_location: str
    target_reachable: bool = True
    resources_available: dict[str, float] = None  # resource_name → quantity
    game_rules: list[str] = None                  # forbidden action strings

    def __post_init__(self):
        if self.resources_available is None:
            self.resources_available = {}
        if self.game_rules is None:
            self.game_rules = []


class NPCActionPolicy:

    def __init__(self, identity: NPCIdentity, world_model: NPCWorldModel):
        self.identity = identity
        self.world_model = world_model

    def select(
        self,
        candidates: list[CandidateAction],
        ctx: PolicyContext,
    ) -> tuple[CandidateAction, list[str]]:
        """
        Return the best feasible action and a list of rejection reasons
        for the actions that were blocked.
        """
        rejections: list[str] = []

        for candidate in candidates:
            block = self._check_constraints(candidate, ctx)
            if block:
                rejections.append(f"[{candidate.kind.value}] blocked: {block}")
                continue
            return candidate, rejections

        # Fallback: always-valid WAIT
        wait = CandidateAction(
            kind=ActionKind.WAIT, target=None,
            content="Wait — all candidate actions were blocked by policy.",
            rationale="Policy fallback",
            need_score=0.0, goal_score=0.0, relationship_score=0.0,
            risk=0.0, feasibility=1.0,
        )
        return wait, rejections

    def _check_constraints(self, c: CandidateAction, ctx: PolicyContext) -> Optional[str]:
        """Return a blocking reason string, or None if action is permitted."""

        # Physical capability
        if c.kind in (ActionKind.ATTACK, ActionKind.FLEE) and \
                self.identity.physical_capability < 0.2:
            return f"physical capability too low ({self.identity.physical_capability:.2f})"

        # Target reachability
        if c.target and not ctx.target_reachable:
            return f"target '{c.target}' not reachable from {ctx.current_location}"

        # Game rule violations
        for rule in ctx.game_rules:
            if c.kind.value in rule.lower():
                return f"game rule forbids '{c.kind.value}': {rule}"

        # Resource requirements
        if c.kind == ActionKind.GIVE:
            if ctx.resources_available.get("item", 0) <= 0:
                return "no items available to give"

        # Skills required
        if c.kind == ActionKind.INVESTIGATE and \
                not self.identity.knows_skill("investigation") and \
                not self.identity.knows_skill("perception"):
            pass  # Not blocking — anyone can investigate; just less effective

        # Feasibility threshold
        if c.feasibility < 0.1:
            return f"feasibility too low ({c.feasibility:.2f})"

        return None

    def explain(self, selected: CandidateAction, rejections: list[str]) -> str:
        lines = [f"Selected: {selected.kind.value} — {selected.content}"]
        lines.append(f"  Rationale: {selected.rationale}")
        lines.append(f"  Score: {selected.total_score:.3f}")
        if rejections:
            lines.append("  Blocked alternatives:")
            for r in rejections:
                lines.append(f"    {r}")
        return "\n".join(lines)
