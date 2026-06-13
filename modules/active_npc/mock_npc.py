"""
mock_npc.py — A deterministic mock NPC for testing and demonstration.

Mira Ashford: blacksmith, village of Stonecroft, Merchant Guild.
Personality: conscientious, moderately trusting, pragmatic, low neuroticism.
Fears: imprisonment, losing her forge.
Goal: secure a supply of iron ore before the winter.
Secret: she sheltered a fugitive named Dael two years ago; trusts no guards.
"""
from __future__ import annotations

import time

from .npc_identity import make_identity
from .npc_memory import NPCMemory, new_belief, new_memory
from .npc_models import MemoryKind, Provenance
from .npc_needs import default_needs
from .npc_goals import NPCGoals, make_goal
from .npc_relationships import NPCRelationships
from .npc_world_model import NPCWorldModel, LocationBelief
from .npc_runtime import NPCRuntime


def build_mock_npc() -> NPCRuntime:
    identity = make_identity(
        npc_id="mira_ashford",
        name="Mira Ashford",
        role="blacksmith",
        faction="Merchant Guild",
        home_location="stonecroft_forge",
        age=41,
        sex="female",
        traits={
            "openness": 0.4,
            "conscientiousness": 0.8,
            "extraversion": 0.35,
            "agreeableness": 0.55,
            "neuroticism": 0.2,
            "honesty_base": 0.75,
            "courage": 0.5,
            "pragmatism": 0.65,
        },
        values=("duty", "family", "independence", "gold"),
        fears=("imprisonment", "losing forge", "starvation"),
        loyalties=("Merchant Guild", "village of Stonecroft", "Dael"),
        skills={"blacksmithing", "negotiation", "basic_combat", "appraisal"},
        social_reach={"player", "alderman_vorn", "merchant_brek", "guard_captain_syla"},
        physical_capability=0.7,
        vocabulary_level="educated",
        verbosity="normal",
        deflection_style="redirects to business",
        origin_facts=(
            "Born in Stonecroft, apprenticed to her father at age 12.",
            "Took over the forge after her father died of fever.",
            "Has been sole proprietor for 19 years.",
            "Sheltered a fugitive named Dael two winters ago; no one in authority knows.",
        ),
        description="A sturdy, pragmatic woman who speaks plainly and trusts slowly.",
        secret="sheltered Dael; will deny it if guards ask",
    )

    # Memory with seeded history
    memory = NPCMemory(npc_id="mira_ashford")

    past_ts = time.time() - 86400 * 5  # 5 days ago

    memory.store_episode(new_memory(
        kind=MemoryKind.EPISODIC,
        summary="Brek's last ore shipment was short by 20%. He claimed road bandits.",
        provenance=Provenance.REPORTED,
        emotional_weight=0.55,
        location="stonecroft_forge",
        participants=["merchant_brek"],
    ))

    memory.store_episode(new_memory(
        kind=MemoryKind.EPISODIC,
        summary="Guard captain Syla came asking about strangers passing through two winters ago.",
        provenance=Provenance.OBSERVED,
        emotional_weight=0.8,
        location="stonecroft_forge",
        participants=["guard_captain_syla"],
    ))

    memory.update_belief(new_belief(
        subject="merchant_brek",
        predicate="reliability",
        value="questionable — last shipment short",
        provenance=Provenance.OBSERVED,
        confidence=0.75,
        source="direct_experience",
    ))

    memory.update_belief(new_belief(
        subject="guard_captain_syla",
        predicate="intent",
        value="investigating fugitives; could threaten Mira's secret",
        provenance=Provenance.INFERRED,
        confidence=0.6,
        source="past_interaction",
    ))

    memory.update_belief(new_belief(
        subject="road_north",
        predicate="bandit_activity",
        value="reported by Brek; unconfirmed",
        provenance=Provenance.REPORTED,
        confidence=0.4,
        source="merchant_brek",
        decay_rate=0.05,
    ))

    # Needs
    needs = default_needs("mira_ashford")
    needs.degrade("duty_fulfillment", 0.3)  # ore supply at risk
    needs.degrade("information", 0.4)       # uncertain about supply chain

    # Goals
    goals = NPCGoals(npc_id="mira_ashford")
    goals.add(make_goal(
        name="Secure iron ore supply",
        description="arrange reliable iron ore delivery before first frost",
        priority=0.85,
        horizon="short",
        conditions_to_complete=["ore contract signed", "shipment confirmed"],
        conditions_to_abandon=["forge destroyed", "forced to leave stonecroft"],
        committed_to=["Merchant Guild"],
    ))
    goals.add(make_goal(
        name="Protect Dael's secret",
        description="ensure no one in authority learns she sheltered Dael",
        priority=0.9,
        horizon="long",
        conditions_to_complete=["pardon", "pardoned"],
        conditions_to_abandon=["Dael himself reveals it"],
        conflicts_with=[],
    ))
    goals.add(make_goal(
        name="Assess Brek's trustworthiness",
        description="determine if Brek's short shipment was theft or genuine misfortune",
        priority=0.5,
        horizon="short",
        conditions_to_complete=["spoke to Brek directly", "inspected his warehouse"],
        conditions_to_abandon=["Brek leaves the region"],
    ))

    # Relationships
    relationships = NPCRelationships(npc_id="mira_ashford")
    relationships.record_interaction(
        "merchant_brek", "Brek",
        summary="Short shipment; gave weak excuse",
        trust_delta=-0.15, respect_delta=-0.1, familiarity_delta=0.2,
    )
    relationships.record_interaction(
        "guard_captain_syla", "Captain Syla",
        summary="Asked about strangers; made Mira nervous",
        trust_delta=-0.2, fear_delta=0.25, familiarity_delta=0.1,
    )
    relationships.get_or_default("player", "stranger")

    # World model
    world = NPCWorldModel(npc_id="mira_ashford")
    world.current_location = "stonecroft_forge"
    world.time_of_day = "morning"
    world.general_threat_level = 0.25

    world.observe_entity("merchant_brek", "Brek", "merchant", "stonecroft_market")
    world.observe_entity("guard_captain_syla", "Captain Syla", "guard captain", "stonecroft_garrison")
    world.hear_about_entity("player", "traveller", "unknown", "stonecroft_inn", source="rumor")

    world.locations["stonecroft_forge"]  = LocationBelief("stonecroft_forge", known=True, safety_estimate=0.8, last_visited=time.time())
    world.locations["stonecroft_market"] = LocationBelief("stonecroft_market", known=True, safety_estimate=0.6)
    world.locations["road_north"]        = LocationBelief("road_north", known=True, safety_estimate=0.35, description="Bandit reports -- unconfirmed")

    world.add_threat("Possible bandit activity on north road", severity=0.4, source="merchant_brek", provenance=Provenance.REPORTED)

    return NPCRuntime(
        identity=identity,
        memory=memory,
        needs=needs,
        goals=goals,
        relationships=relationships,
        world_model=world,
    )
