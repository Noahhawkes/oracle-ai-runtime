"""
npc_goals.py — Goal tracking: short/long term, conflicts, commitments.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional

from .npc_models import Goal, GoalStatus


@dataclass
class NPCGoals:
    npc_id: str
    goals: list[Goal] = field(default_factory=list)

    def add(self, goal: Goal) -> None:
        self.goals.append(goal)

    def active(self) -> list[Goal]:
        return [g for g in self.goals if g.status == GoalStatus.ACTIVE]

    def top_priority(self, horizon: Optional[str] = None) -> Optional[Goal]:
        candidates = [g for g in self.active()
                      if horizon is None or g.horizon == horizon]
        return max(candidates, key=lambda g: g.priority, default=None)

    def get(self, goal_id: str) -> Optional[Goal]:
        return next((g for g in self.goals if g.id == goal_id), None)

    def complete(self, goal_id: str) -> None:
        g = self.get(goal_id)
        if g: g.status = GoalStatus.COMPLETED

    def abandon(self, goal_id: str, reason: str = "") -> None:
        g = self.get(goal_id)
        if g: g.status = GoalStatus.ABANDONED

    def suspend(self, goal_id: str) -> None:
        g = self.get(goal_id)
        if g: g.status = GoalStatus.SUSPENDED

    def conflicts(self) -> list[tuple[Goal, Goal]]:
        result = []
        active = self.active()
        for i, g1 in enumerate(active):
            for g2 in active[i+1:]:
                if g2.id in g1.conflicts_with or g1.id in g2.conflicts_with:
                    result.append((g1, g2))
        return result

    def update_from_event(self, event_description: str) -> None:
        """Check completion and abandonment conditions against a new event."""
        desc_lower = event_description.lower()
        for g in self.active():
            for cond in g.conditions_to_complete:
                if cond.lower() in desc_lower:
                    g.status = GoalStatus.COMPLETED
                    break
            if g.status == GoalStatus.ACTIVE:
                for cond in g.conditions_to_abandon:
                    if cond.lower() in desc_lower:
                        g.status = GoalStatus.ABANDONED
                        break

    def summary(self) -> str:
        active = self.active()
        if not active: return "No active goals."
        top = sorted(active, key=lambda g: g.priority, reverse=True)[:3]
        return "Goals: " + "; ".join(f"{g.name}(p={g.priority:.1f})" for g in top)


def make_goal(
    name: str,
    description: str,
    priority: float = 0.5,
    horizon: str = "short",
    conditions_to_complete: Optional[list[str]] = None,
    conditions_to_abandon: Optional[list[str]] = None,
    conflicts_with: Optional[list[str]] = None,
    committed_to: Optional[list[str]] = None,
) -> Goal:
    return Goal(
        id=str(uuid.uuid4())[:8],
        name=name,
        description=description,
        status=GoalStatus.ACTIVE,
        priority=priority,
        horizon=horizon,
        conditions_to_complete=conditions_to_complete or [],
        conditions_to_abandon=conditions_to_abandon or [],
        depends_on=[],
        conflicts_with=conflicts_with or [],
        committed_to=committed_to or [],
    )
