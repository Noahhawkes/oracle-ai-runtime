"""
world_adapter.py — Simulated world-state adapter.

Translates game-engine events into WorldEvent objects the NPC system
consumes. In production this bridges to an actual game engine or
world-state database. Here it produces deterministic mock events.
"""
from __future__ import annotations

import time
import uuid
from typing import Optional

from .npc_models import WorldEvent


class SimulatedWorldAdapter:
    """
    Generates scripted world events for demonstration and testing.
    Does not connect to any external system.
    """

    def __init__(self):
        self._event_log: list[WorldEvent] = []

    def emit(
        self,
        kind: str,
        description: str,
        location: str,
        participants: Optional[list[str]] = None,
        public: bool = True,
        magnitude: float = 0.3,
        data: Optional[dict] = None,
    ) -> WorldEvent:
        event = WorldEvent(
            id=str(uuid.uuid4())[:8],
            kind=kind,
            description=description,
            timestamp=time.time(),
            location=location,
            participants=participants or [],
            public=public,
            magnitude=magnitude,
            data=data or {},
        )
        self._event_log.append(event)
        return event

    def log(self) -> list[WorldEvent]:
        return list(self._event_log)

    # ── Scripted scenario events ───────────────────────────────────────────────

    def player_enters_forge(self) -> WorldEvent:
        return self.emit(
            kind="social_encounter",
            description="A traveller walks into the forge and approaches the counter.",
            location="stonecroft_forge",
            participants=["player", "mira_ashford"],
            magnitude=0.2,
        )

    def player_asks_about_brek(self) -> WorldEvent:
        return self.emit(
            kind="social_inquiry",
            description="The traveller asks: 'I heard Brek's last shipment was short. What do you know about him?'",
            location="stonecroft_forge",
            participants=["player", "mira_ashford"],
            magnitude=0.3,
        )

    def player_asks_about_dael(self) -> WorldEvent:
        return self.emit(
            kind="social_inquiry",
            description="The traveller asks: 'I'm looking for someone named Dael. Passed through here two winters ago.'",
            location="stonecroft_forge",
            participants=["player", "mira_ashford"],
            magnitude=0.5,
        )

    def guard_arrives(self) -> WorldEvent:
        return self.emit(
            kind="authority_presence",
            description="Captain Syla enters the forge flanked by two guards.",
            location="stonecroft_forge",
            participants=["guard_captain_syla", "mira_ashford"],
            public=True,
            magnitude=0.6,
        )

    def brek_defaults_on_payment(self) -> WorldEvent:
        return self.emit(
            kind="economic_threat",
            description="Word reaches Stonecroft: Brek has fled the region, leaving debts unpaid.",
            location="stonecroft_market",
            participants=["merchant_brek"],
            public=True,
            magnitude=0.55,
        )

    def bandit_raid_confirmed(self) -> WorldEvent:
        return self.emit(
            kind="threat_event",
            description="A merchant caravan was attacked on the north road. Three guards killed.",
            location="road_north",
            participants=["unknown_bandits"],
            public=True,
            magnitude=0.75,
        )

    def ore_shipment_arrives(self) -> WorldEvent:
        return self.emit(
            kind="positive_outcome",
            description="A full iron ore shipment arrives at the forge — correct weight, no shortage.",
            location="stonecroft_forge",
            participants=["mira_ashford"],
            magnitude=0.4,
        )

    def player_offers_help(self) -> WorldEvent:
        return self.emit(
            kind="social_offer",
            description="The traveller offers to investigate Brek's whereabouts for a fair price.",
            location="stonecroft_forge",
            participants=["player", "mira_ashford"],
            magnitude=0.4,
        )

    def player_threatens_mira(self) -> WorldEvent:
        return self.emit(
            kind="threat_event",
            description="The traveller grabs Mira's arm and demands she reveal who she's been hiding.",
            location="stonecroft_forge",
            participants=["player", "mira_ashford"],
            public=False,
            magnitude=0.8,
        )

    def dael_is_pardoned(self) -> WorldEvent:
        return self.emit(
            kind="official_decree",
            description="The Duke issues a pardon for all fugitives from the border conflict, including Dael.",
            location="stonecroft_square",
            participants=["mira_ashford"],
            public=True,
            magnitude=0.7,
        )
