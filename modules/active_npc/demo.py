#!/usr/bin/env python3
"""
demo.py — Command-line demonstration of the Active NPC Intelligence system.

Runs 13 world events through Mira Ashford's cognitive loop and prints
the full cycle output: perception, interpretation, action selection,
dialogue, and policy explanation.

Usage:
    python -m modules.active_npc.demo
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

# Force UTF-8 on Windows consoles so the demonstration can render dividers.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.active_npc.mock_npc import build_mock_npc
from modules.active_npc.world_adapter import SimulatedWorldAdapter
from modules.active_npc.npc_action_policy import PolicyContext


DIVIDER = "─" * 72


def print_cycle(step: int, event_name: str, result) -> None:
    print(f"\n{DIVIDER}")
    print(f"  Step {step:02d}: {event_name}")
    print(DIVIDER)
    print(f"  Observed : {result.observed}")
    if result.observed:
        print(f"  Event    : {result.observation_summary}")
        print(f"  Interprets:")
        for interp in result.interpretations:
            print(f"    • {interp}")
        print(f"  Action   : {result.selected_action_kind}")
        if result.dialogue:
            wrapped = textwrap.fill(result.dialogue, width=68, initial_indent="    ", subsequent_indent="    ")
            print(f"  Dialogue :\n{wrapped}")
        if result.world_effect:
            print(f"  Effect   : {result.world_effect}")
        print(f"  Policy   :")
        for line in result.policy_explanation.splitlines():
            print(f"    {line}")
    else:
        print(f"  (Event outside perceptual range — NPC not informed)")


def run_demo() -> None:
    print("\n" + "=" * 72)
    print("  ORACLE Active NPC Intelligence — Demonstration")
    print("  NPC: Mira Ashford, Blacksmith, Stonecroft")
    print("=" * 72)

    npc = build_mock_npc()
    world = SimulatedWorldAdapter()

    print("\n" + npc.state_summary())

    # ── Event sequence ─────────────────────────────────────────────────────────

    step = 1

    # 1. Player enters forge
    ev = world.player_enters_forge()
    r = npc.process_event(ev, interacting_with="player", player_input="Hello.")
    print_cycle(step, "Player enters forge", r); step += 1

    # 2. Player asks about Brek (NPC has beliefs about Brek)
    ev = world.player_asks_about_brek()
    r = npc.process_event(ev, interacting_with="player",
                          player_input="I heard Brek's last shipment was short. What do you know about him?")
    print_cycle(step, "Player asks about Brek", r); step += 1

    # 3. Player asks about Dael — sensitive topic NPC will not reveal
    ev = world.player_asks_about_dael()
    r = npc.process_event(ev, interacting_with="player",
                          player_input="I'm looking for someone named Dael. Passed through here two winters ago.")
    print_cycle(step, "Player asks about Dael (secret)", r); step += 1

    # 4. Guard captain arrives — Mira fears Syla; behaviour should shift
    ev = world.guard_arrives()
    r = npc.process_event(ev, interacting_with="guard_captain_syla")
    print_cycle(step, "Guard captain enters forge", r); step += 1

    # 5. Brek defaults — economic threat, goal state changes
    ev = world.brek_defaults_on_payment()
    r = npc.process_event(ev)
    print_cycle(step, "Brek flees region (economic threat)", r); step += 1

    # 6. Bandit raid confirmed — threat level rises
    ev = world.bandit_raid_confirmed()
    r = npc.process_event(ev)
    print_cycle(step, "Bandit raid confirmed on north road", r); step += 1

    # 7. The forge ward flares - private magic inside Mira's workspace
    ev = world.forge_ward_flares()
    r = npc.process_event(ev)
    print_cycle(step, "Forge ward flares (arcane anomaly)", r); step += 1

    # 8. Player offers to help investigate Brek
    ev = world.player_offers_help()
    r = npc.process_event(ev, interacting_with="player",
                          player_input="I can track Brek down. For a price.")
    print_cycle(step, "Player offers to investigate Brek", r); step += 1

    # 9. Player offers a stabilizing charm - magic becomes social trust
    ev = world.player_offers_stabilizing_charm()
    r = npc.process_event(ev, interacting_with="player",
                          player_input="This charm can quiet the ward if you let me place it.")
    print_cycle(step, "Player offers stabilizing charm", r); step += 1

    # 10. Player threatens Mira - should trigger fear/refuse/flee response
    ev = world.player_threatens_mira()
    ctx = PolicyContext(
        current_location="stonecroft_forge",
        target_reachable=True,
        game_rules=["npc cannot attack players with guard_captain_syla present"],
    )
    r = npc.process_event(ev, interacting_with="player", policy_ctx=ctx)
    print_cycle(step, "Player threatens Mira (demands secret)", r); step += 1

    # 11. Ore shipment arrives - positive; goal partially satisfied
    ev = world.ore_shipment_arrives()
    r = npc.process_event(ev)
    print_cycle(step, "Ore shipment arrives (goal progress)", r); step += 1

    # 12. Dael is officially pardoned - long-term goal resolved
    ev = world.dael_is_pardoned()
    r = npc.process_event(ev)
    print_cycle(step, "Dael officially pardoned (goal resolved)", r); step += 1

    # 13. Player returns; relationship has changed
    ev = world.player_enters_forge()
    r = npc.process_event(ev, interacting_with="player",
                          player_input="I'm back. Heard about the pardon.")
    print_cycle(step, "Player returns post-threat (relationship continuity)", r); step += 1

    # ── Final state ───────────────────────────────────────────────────────────
    print(f"\n{DIVIDER}")
    print("  FINAL NPC STATE")
    print(DIVIDER)
    print(npc.state_summary())

    print(f"\n  Relationship — player:")
    rel = npc.relationships.get("player")
    if rel:
        print(f"  {npc.relationships.summary('player')}")

    print(f"\n  Active goals:")
    for g in npc.goals.active():
        print(f"    [{g.priority:.1f}] {g.name} — {g.status.value}")

    print(f"\n  Active beliefs (sample):")
    for key, belief in list(npc.memory.beliefs.items())[:6]:
        print(f"    {key}: {belief.value!r} [{belief.provenance.value}, conf={belief.confidence:.2f}]")

    print(f"\n  Memory episodes: {len(npc.memory.episodic_buffer)} buffer / {len(npc.memory.semantic_store)} semantic")
    print(f"\n{DIVIDER}\n")


if __name__ == "__main__":
    run_demo()
