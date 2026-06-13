"""
npc_identity.py — Stable NPC identity. Immutable after creation.

Includes personality traits, values, fears, loyalties, skills,
role, speaking style, and origin facts. Never resets between scenes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class PersonalityTraits:
    openness: float        # 0–1  curiosity vs. routine preference
    conscientiousness: float  # 0–1  orderly vs. flexible
    extraversion: float    # 0–1  social energy
    agreeableness: float   # 0–1  cooperative vs. competitive
    neuroticism: float     # 0–1  emotional reactivity
    # Domain-specific
    honesty_base: float    # 0–1  default truthfulness (can be overridden by goals)
    courage: float         # 0–1  willingness to act under threat
    pragmatism: float      # 0–1  ends-justify-means tendency


@dataclass(frozen=True)
class NPCIdentity:
    """
    Immutable core identity. Read by every module but never written
    after NPC creation. Personality shapes all behaviour; it does not
    determine it.
    """
    npc_id: str
    name: str
    age: int
    sex: str
    role: str               # e.g. "blacksmith", "guard captain", "merchant"
    faction: str            # primary affiliation
    home_location: str

    # Personality
    traits: PersonalityTraits

    # Values (ordered by priority — index 0 is most important)
    values: tuple[str, ...]   # e.g. ("family", "justice", "gold")
    fears: tuple[str, ...]    # e.g. ("imprisonment", "losing daughter")
    loyalties: tuple[str, ...]  # ordered by strength

    # Skills and capabilities
    skills: frozenset[str]    # e.g. {"swordfighting", "herbalism", "negotiation"}
    physical_capability: float  # 0–1; limits action feasibility
    social_reach: frozenset[str]  # entity ids this NPC can plausibly contact

    # Speaking style
    vocabulary_level: str   # "simple" | "educated" | "noble" | "street"
    verbosity: str          # "terse" | "normal" | "verbose"
    deflection_style: str   # how they avoid uncomfortable topics

    # Immutable origin facts (NPC knows these as bedrock)
    origin_facts: tuple[str, ...]

    # Optional metadata
    description: str = ""
    secret: Optional[str] = None  # only used if revealed by a goal or relation

    def trait_score(self, trait: str) -> float:
        return getattr(self.traits, trait, 0.5)

    def knows_skill(self, skill: str) -> bool:
        return skill.lower() in {s.lower() for s in self.skills}

    def can_contact(self, entity_id: str) -> bool:
        return entity_id in self.social_reach


# ── Factory helpers ────────────────────────────────────────────────────────────

def make_identity(
    npc_id: str,
    name: str,
    role: str,
    faction: str,
    home_location: str,
    age: int = 35,
    sex: str = "unknown",
    traits: Optional[dict] = None,
    values: tuple[str, ...] = ("survival",),
    fears: tuple[str, ...] = (),
    loyalties: tuple[str, ...] = (),
    skills: Optional[set[str]] = None,
    social_reach: Optional[set[str]] = None,
    physical_capability: float = 0.7,
    vocabulary_level: str = "normal",
    verbosity: str = "normal",
    deflection_style: str = "changes subject",
    origin_facts: tuple[str, ...] = (),
    description: str = "",
    secret: Optional[str] = None,
) -> NPCIdentity:
    t = traits or {}
    pt = PersonalityTraits(
        openness=t.get("openness", 0.5),
        conscientiousness=t.get("conscientiousness", 0.5),
        extraversion=t.get("extraversion", 0.5),
        agreeableness=t.get("agreeableness", 0.5),
        neuroticism=t.get("neuroticism", 0.3),
        honesty_base=t.get("honesty_base", 0.7),
        courage=t.get("courage", 0.5),
        pragmatism=t.get("pragmatism", 0.5),
    )
    return NPCIdentity(
        npc_id=npc_id,
        name=name,
        age=age,
        sex=sex,
        role=role,
        faction=faction,
        home_location=home_location,
        traits=pt,
        values=values,
        fears=fears,
        loyalties=loyalties,
        skills=frozenset(skills or set()),
        physical_capability=physical_capability,
        social_reach=frozenset(social_reach or set()),
        vocabulary_level=vocabulary_level,
        verbosity=verbosity,
        deflection_style=deflection_style,
        origin_facts=origin_facts,
        description=description,
        secret=secret,
    )
