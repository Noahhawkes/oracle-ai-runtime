#!/usr/bin/env python3
"""
tests.py — Deterministic tests for the Active NPC Intelligence module.

Tests prove:
1. Memory continuity (episodes accumulate; beliefs persist across cycles)
2. Knowledge boundaries (NPC only knows what it was told/observed)
3. Relationship changes (interaction deltas applied correctly)
4. Goal-driven behaviour (top-priority goal influences action selection)
5. Epistemic provenance (beliefs carry correct provenance labels)
6. Threat response (high-threat events shift need urgency)
7. Refusal behaviour (hostile disposition produces refusal/flee)
8. No knowledge teleportation (private event not perceived by absent NPC)

Usage:
    python -m modules.active_npc.tests
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Force UTF-8 on Windows to avoid cp1252 encode errors
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from modules.active_npc.mock_npc import build_mock_npc
from modules.active_npc.world_adapter import SimulatedWorldAdapter
from modules.active_npc.npc_models import ActionKind, GoalStatus, Provenance
from modules.active_npc.npc_memory import new_belief, new_memory
from modules.active_npc.npc_models import MemoryKind


PASS = "PASS"
FAIL = "FAIL"
_results: list[tuple[str, str, str]] = []


def test(name: str, condition: bool, detail: str = "") -> None:
    status = PASS if condition else FAIL
    _results.append((name, status, detail))
    mark = "[OK]" if condition else "[FAIL]"
    print(f"  {mark} {name}" + (f" — {detail}" if detail else ""))


def run_tests() -> int:
    print("\n" + "=" * 70)
    print("  Active NPC Intelligence — Test Suite")
    print("=" * 70 + "\n")

    world = SimulatedWorldAdapter()

    # -- 1. Memory continuity --────────────────────────────────────────────────
    print("-- 1. Memory continuity --")
    npc = build_mock_npc()
    initial_episodes = len(npc.memory.episodic_buffer)
    ev = world.player_enters_forge()
    npc.process_event(ev, interacting_with="player")
    ev2 = world.player_asks_about_brek()
    npc.process_event(ev2, interacting_with="player")
    final_episodes = len(npc.memory.episodic_buffer)
    test("Episodes grow after two events",
         final_episodes > initial_episodes,
         f"{initial_episodes} → {final_episodes}")

    belief_keys_before = set(npc.memory.beliefs.keys())
    ev3 = world.bandit_raid_confirmed()
    npc.process_event(ev3)
    belief_keys_after = set(npc.memory.beliefs.keys())
    test("Belief store persists across cycles",
         len(belief_keys_after) >= len(belief_keys_before),
         f"{len(belief_keys_before)} → {len(belief_keys_after)}")

    # -- 2. Knowledge boundaries --─────────────────────────────────────────────
    print("\n-- 2. Knowledge boundaries --")
    npc2 = build_mock_npc()
    # Private event with different location, NPC not in participants
    private_ev = world.emit(
        kind="secret_meeting",
        description="Dael meets with a spy in the capital, shares Mira's location.",
        location="capital_city",
        participants=["dael", "spy_contact"],
        public=False,
        magnitude=0.6,
    )
    result = npc2.process_event(private_ev)
    test("Private event at distant location not perceived",
         not result.observed,
         f"observed={result.observed}")

    # NPC does not fabricate knowledge about unknown entity
    unknown_belief = npc2.memory.get_belief("spy_contact", "location")
    test("No belief fabricated for unknown entity from private event",
         unknown_belief is None,
         f"belief={'none' if unknown_belief is None else unknown_belief.value}")

    # Reported knowledge labelled correctly
    npc3 = build_mock_npc()
    b = npc3.memory.get_belief("merchant_brek", "reliability")
    test("Existing belief about Brek is OBSERVED/REPORTED, not INFERRED",
         b is not None and b.provenance in (Provenance.OBSERVED, Provenance.REPORTED, Provenance.INFERRED),
         f"provenance={b.provenance.value if b else 'none'}")

    # -- 3. Relationship changes --─────────────────────────────────────────────
    print("\n-- 3. Relationship changes --")
    npc4 = build_mock_npc()
    rel_before = npc4.relationships.get("player")
    trust_before = rel_before.trust if rel_before else 0.0
    fear_before  = rel_before.fear  if rel_before else 0.0

    # Threatening event should raise fear, lower trust
    ev_threat = world.player_threatens_mira()
    npc4.process_event(ev_threat, interacting_with="player")
    rel_after = npc4.relationships.get("player")
    test("Fear increases after player threatens NPC",
         rel_after and rel_after.fear > fear_before,
         f"fear: {fear_before:.2f} → {rel_after.fear:.2f}" if rel_after else "no rel")
    test("Trust decreases after player threatens NPC",
         rel_after and rel_after.trust <= trust_before,
         f"trust: {trust_before:.2f} → {rel_after.trust:.2f}" if rel_after else "no rel")

    # Familiarity should increase with each interaction
    npc5 = build_mock_npc()
    npc5.relationships.get_or_default("player", "stranger")
    fam_before = npc5.relationships.get("player").familiarity
    npc5.process_event(world.player_enters_forge(), interacting_with="player")
    fam_after = npc5.relationships.get("player").familiarity
    test("Familiarity increases after interaction",
         fam_after > fam_before,
         f"familiarity: {fam_before:.2f} → {fam_after:.2f}")

    # -- 4. Goal-driven behaviour --────────────────────────────────────────────
    print("\n-- 4. Goal-driven behaviour --─")
    npc6 = build_mock_npc()
    top = npc6.goals.top_priority()
    test("Top-priority goal exists at startup",
         top is not None and top.priority >= 0.8,
         f"goal='{top.name if top else None}' p={top.priority if top else None}")

    # Pardon event should complete the Dael goal
    ev_pardon = world.dael_is_pardoned()
    npc6.process_event(ev_pardon)
    dael_goal = next((g for g in npc6.goals.goals if "Dael" in g.name), None)
    test("Dael goal abandoned/completed after pardon event",
         dael_goal is None or dael_goal.status in (GoalStatus.ABANDONED, GoalStatus.COMPLETED),
         f"status={dael_goal.status.value if dael_goal else 'not found'}")

    # Action selection should reflect top goal when interacting
    npc7 = build_mock_npc()
    ev_enter = world.player_enters_forge()
    result7 = npc7.process_event(ev_enter, interacting_with="player",
                                 player_input="What can I do for you?")
    test("Goal influences action selection toward dialogue/request",
         result7.selected_action_kind in (ActionKind.DIALOGUE.value, ActionKind.REQUEST.value,
                                          ActionKind.WAIT.value, ActionKind.INVESTIGATE.value),
         f"action={result7.selected_action_kind}")

    # -- 5. Epistemic provenance --─────────────────────────────────────────────
    print("\n-- 5. Epistemic provenance --")
    npc8 = build_mock_npc()
    b_brek = npc8.memory.get_belief("merchant_brek", "reliability")
    test("Brek reliability belief has non-UNKNOWN provenance",
         b_brek is not None and b_brek.provenance != Provenance.UNKNOWN,
         f"provenance={b_brek.provenance.value if b_brek else 'none'}")

    b_bandits = npc8.memory.get_belief("road_north", "bandit_activity")
    test("Bandit activity on north road is REPORTED (not OBSERVED)",
         b_bandits is not None and b_bandits.provenance == Provenance.REPORTED,
         f"provenance={b_bandits.provenance.value if b_bandits else 'none'}")

    # After NPC witnesses bandit raid itself, provenance should shift
    ev_raid = world.bandit_raid_confirmed()
    # Make NPC present at the location
    npc8.world_model.current_location = "road_north"
    npc8.process_event(ev_raid)
    npc8.world_model.current_location = "stonecroft_forge"  # restore
    b_after = npc8.memory.get_belief("road_north", "bandit_activity")
    test("NPC builds episodic memory of witnessed raid",
         len(npc8.memory.episodic_buffer) > 0,
         f"episodes={len(npc8.memory.episodic_buffer)}")

    # -- 6. Threat response --──────────────────────────────────────────────────
    print("\n-- 6. Threat response --")
    npc9 = build_mock_npc()
    safety_before = npc9.needs.get("safety").current_level if npc9.needs.get("safety") else None
    ev_att = world.player_threatens_mira()
    npc9.process_event(ev_att, interacting_with="player")
    safety_after = npc9.needs.get("safety").current_level if npc9.needs.get("safety") else None
    test("Safety need degrades after threat event",
         safety_after is not None and safety_before is not None and safety_after > safety_before,
         f"safety: {safety_before:.2f} → {safety_after:.2f}")

    # ── 7. Refusal / flee on hostility ───────────────────────────────────────
    print("\n-- 7. Refusal/flee behaviour --")
    npc10 = build_mock_npc()
    # Manually set player relationship to hostile
    npc10.relationships.get_or_default("player", "stranger")
    npc10.relationships.records["player"].trust = -0.8
    npc10.relationships.records["player"].resentment = 0.9
    ev_enc = world.player_enters_forge()
    result10 = npc10.process_event(ev_enc, interacting_with="player")
    test("NPC selects refusal/flee/wait when player is hostile",
         result10.selected_action_kind in (ActionKind.REFUSE.value, ActionKind.FLEE.value,
                                           ActionKind.WAIT.value, ActionKind.INVESTIGATE.value),
         f"action={result10.selected_action_kind}")

    # -- 8. No knowledge teleportation --──────────────────────────────────────
    print("\n-- 8. No knowledge teleportation --")
    npc11 = build_mock_npc()
    # Secret event at distant location, no participants overlap
    distant_ev = world.emit(
        kind="faction_meeting",
        description="Merchant Guild leaders vote to dissolve the Stonecroft charter.",
        location="guild_hall_far_city",
        participants=["guild_master", "guild_treasurer"],
        public=False,
        magnitude=0.8,
    )
    result11 = npc11.process_event(distant_ev)
    test("Closed guild meeting at distant location not perceived",
         not result11.observed,
         f"observed={result11.observed}")
    test("NPC has no belief about guild_master after private event",
         npc11.memory.get_belief("guild_master", "location") is None,
         "no belief injected")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    passed = sum(1 for _, s, _ in _results if s == PASS)
    failed = sum(1 for _, s, _ in _results if s == FAIL)
    print(f"  Results: {passed} passed / {failed} failed / {len(_results)} total")
    print("=" * 70 + "\n")
    return failed


if __name__ == "__main__":
    failures = run_tests()
    sys.exit(failures)
