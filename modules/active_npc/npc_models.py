"""
npc_models.py — Typed data models and enums shared across the active_npc module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ── Epistemics ────────────────────────────────────────────────────────────────

class Provenance(str, Enum):
    OBSERVED  = "observed"   # NPC directly witnessed the event
    REPORTED  = "reported"   # told by another character; may be false
    INFERRED  = "inferred"   # reasoned from other beliefs
    ASSUMED   = "assumed"    # background default, never verified
    DISPUTED  = "disputed"   # contradicts another held belief
    FALSE     = "false"      # NPC believes this but objective world says otherwise
    UNKNOWN   = "unknown"    # NPC acknowledges the gap


class MemoryKind(str, Enum):
    EPISODIC   = "episodic"    # specific event the NPC experienced or witnessed
    SEMANTIC   = "semantic"    # general knowledge or fact
    RELATIONAL = "relational"  # something about a specific entity
    EMOTIONAL  = "emotional"   # significant emotional moment


class NeedCategory(str, Enum):
    PHYSICAL   = "physical"
    EMOTIONAL  = "emotional"
    SOCIAL     = "social"
    STRATEGIC  = "strategic"
    ROLE       = "role"


class GoalStatus(str, Enum):
    ACTIVE    = "active"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class ActionKind(str, Enum):
    DIALOGUE    = "dialogue"
    MOVE        = "move"
    GIVE        = "give"
    TAKE        = "take"
    ATTACK      = "attack"
    FLEE        = "flee"
    WAIT        = "wait"
    REQUEST     = "request"
    REFUSE      = "refuse"
    DECEIVE     = "deceive"
    INVESTIGATE = "investigate"
    REST        = "rest"


# ── Core data structures ──────────────────────────────────────────────────────

@dataclass
class Belief:
    subject: str            # entity or concept this belief is about
    predicate: str          # what the NPC believes about the subject
    value: Any              # the specific claim
    provenance: Provenance
    confidence: float       # 0.0–1.0
    source: str             # who/what informed this belief
    timestamp: float        # epoch seconds when belief was formed/updated
    decay_rate: float = 0.0 # per-day decay; 0 = no decay
    tags: list[str] = field(default_factory=list)
    disputed_by: list[str] = field(default_factory=list)  # belief IDs that conflict


@dataclass
class Memory:
    id: str
    kind: MemoryKind
    summary: str            # compressed meaning
    raw_detail: str         # original detail before compression
    provenance: Provenance
    emotional_weight: float # 0.0–1.0; high = consolidates strongly
    timestamp: float
    location: str = ""
    participants: list[str] = field(default_factory=list)
    related_goals: list[str] = field(default_factory=list)
    decay_rate: float = 0.001  # fraction lost per day
    consolidated: bool = False  # moved from episodic buffer to long-term


@dataclass
class Need:
    category: NeedCategory
    name: str
    urgency: float          # 0.0–1.0; recalculated each cycle
    current_level: float    # 0.0 = fully satisfied, 1.0 = critical
    description: str
    satisfiers: list[str] = field(default_factory=list)  # action kinds that help


@dataclass
class Goal:
    id: str
    name: str
    description: str
    status: GoalStatus
    priority: float         # 0.0–1.0
    horizon: str            # "immediate" | "short" | "long"
    conditions_to_complete: list[str] = field(default_factory=list)
    conditions_to_abandon: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)  # other goal IDs
    conflicts_with: list[str] = field(default_factory=list)
    committed_to: list[str] = field(default_factory=list)  # entity names owed this


@dataclass
class Relationship:
    entity_id: str
    name: str
    trust: float        # -1.0 (betrayer) to 1.0 (fully trusted)
    affection: float    # -1.0 to 1.0
    fear: float         # 0.0 to 1.0
    respect: float      # 0.0 to 1.0
    resentment: float   # 0.0 to 1.0
    loyalty: float      # 0.0 to 1.0
    familiarity: float  # 0.0 = stranger, 1.0 = intimate
    debt: float         # negative = owe them, positive = they owe NPC
    last_interaction_summary: str = ""
    interaction_count: int = 0


@dataclass
class Observation:
    event_id: str
    event_type: str
    description: str
    perceived_by: str       # NPC id who perceived this
    timestamp: float
    location: str
    participants: list[str] = field(default_factory=list)
    raw_data: dict = field(default_factory=dict)


@dataclass
class CandidateAction:
    kind: ActionKind
    target: Optional[str]   # entity or location
    content: str            # dialogue text or action description
    rationale: str          # why this action was generated
    need_score: float       # how well it addresses current needs
    goal_score: float       # how well it advances goals
    relationship_score: float
    risk: float             # 0.0–1.0
    feasibility: float      # 0.0–1.0

    @property
    def total_score(self) -> float:
        return (
            self.need_score * 0.3
            + self.goal_score * 0.35
            + self.relationship_score * 0.2
            - self.risk * 0.15
        ) * self.feasibility


@dataclass
class SelectedAction:
    action: CandidateAction
    dialogue: Optional[str]  # generated dialogue if kind == DIALOGUE
    world_effect: Optional[str]  # description of world state change
    memory_to_store: Optional[Memory]


@dataclass
class WorldEvent:
    id: str
    kind: str
    description: str
    timestamp: float
    location: str
    participants: list[str] = field(default_factory=list)
    public: bool = True     # False = only directly-involved parties know
    magnitude: float = 0.5  # 0.0 = trivial, 1.0 = world-changing
    data: dict = field(default_factory=dict)
