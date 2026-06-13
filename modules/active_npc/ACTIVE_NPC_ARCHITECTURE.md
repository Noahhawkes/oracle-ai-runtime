# Active NPC Intelligence — Architecture

**Status:** Standalone prototype. Not wired into oracle_server.py.
**Location:** `modules/active_npc/`
**Tests:** 18/18 passing — run with `python -m modules.active_npc.tests`
**Demo:** `python -m modules.active_npc.demo`

---

## Design Principles

NPCs behave like persistent individuals, not scripted dialogue dispensers.

| Principle | Implementation |
|---|---|
| Truth before fluency | Dialogue generated from actual NPC state; not theatrical filler |
| Observed facts outrank inference | Every belief carries `Provenance` label |
| Memory stores meaning, not raw logs | Episodic buffer → semantic consolidation |
| Actions bounded by authority and capability | `NPCActionPolicy` enforces constraints |
| Continuity across scenes | All state persists; no personality reset |
| No omniscience | NPCs only know what they perceived, were told, or inferred |

---

## Module Map

```
modules/active_npc/
  npc_models.py         Typed data models and enums (shared base)
  npc_identity.py       Immutable personality, traits, skills, origin facts
  npc_memory.py         Episodic buffer, semantic store, belief store, decay
  npc_world_model.py    NPC's partial, possibly wrong map of the world
  npc_needs.py          Physical/emotional/social/strategic needs + urgency
  npc_goals.py          Short/long term goals, conflicts, abandonment conditions
  npc_relationships.py  Per-entity trust, fear, affection, debt, familiarity
  npc_perception.py     Converts WorldEvents into NPC Observations
  npc_reasoning.py      Generates candidate actions from full NPC state
  npc_action_policy.py  Selects one bounded action; enforces hard constraints
  npc_dialogue.py       Generates dialogue from actual state (no fabrication)
  npc_runtime.py        Full perceive → decide → act → consolidate loop
  mock_npc.py           Mira Ashford — deterministic test NPC
  world_adapter.py      Simulated world event generator
  demo.py               CLI demonstration (11 events)
  tests.py              18 deterministic tests
```

---

## Cognitive Loop

```
WorldEvent
  → NPCPerception.perceive()        Was the NPC present or informed?
  → relevance_score()               Is this worth acting on?
  → NPCMemory.retrieve()            What does the NPC remember about this?
  → _update_beliefs_from_observation()  Update what the NPC now believes
  → NPCGoals.update_from_event()    Did this complete or invalidate a goal?
  → NPCReasoning.interpret_observation()  What does the NPC make of it?
  → NPCReasoning.generate_candidates()   What could the NPC do?
  → NPCActionPolicy.select()        What is the NPC actually able to do?
  → NPCDialogue.generate()          What does the NPC say (if speaking)?
  → NPCMemory.store_episode()       Store this experience
  → NPCNeeds tick, relationship delta
  → CycleResult returned
```

---

## Epistemic Provenance

Every belief and memory carries one of:

| Label | Meaning |
|---|---|
| `observed` | NPC directly witnessed the event |
| `reported` | Told by another character; may be false |
| `inferred` | Reasoned from other beliefs |
| `assumed` | Background default, never verified |
| `disputed` | Contradicts another held belief |
| `false` | NPC believes this; objective world says otherwise |
| `unknown` | NPC acknowledges the gap |

NPC beliefs are never confused with objective world truth. The world adapter
holds the authoritative state; the NPC's world model is its own interpretation.

---

## Memory Architecture

```
NPCMemory
  episodic_buffer   (max 50)   Raw recent events; decays by weight
  semantic_store    (max 200)  Compressed long-term knowledge
  beliefs           (dict)     Subject::predicate → Belief with provenance

Consolidation: emotional_weight >= 0.65 → copy to semantic_store
Pruning: episodic buffer sorted by recency × emotional_weight; tail dropped
Decay: belief.confidence -= decay_rate × elapsed_days; removed at < 0.05
```

---

## Relationship Model

Each known entity has a `Relationship` record:

```
trust        [-1.0, 1.0]   Core willingness to cooperate
affection    [-1.0, 1.0]   Emotional warmth
fear         [0.0, 1.0]    Overrides positive relationship when high
respect      [0.0, 1.0]    Separate from affection
resentment   [0.0, 1.0]    Persistent grievance; dampens cooperation
loyalty      [0.0, 1.0]    Acts against own interest to protect
familiarity  [0.0, 1.0]    Stranger → intimate; affects communication style
debt         float          Negative = NPC owes them; positive = they owe NPC
```

Disposition is derived, not stored: function of trust, affection, fear, resentment.
Changes are incremental — no sudden resets.

---

## Action Selection

1. `NPCReasoning.generate_candidates()` produces a ranked list.
2. Each `CandidateAction` has `need_score`, `goal_score`, `relationship_score`, `risk`, `feasibility`.
3. `total_score = (needs×0.3 + goals×0.35 + rel×0.2 - risk×0.15) × feasibility`
4. `NPCActionPolicy.select()` walks the sorted list and applies hard constraints:
   - Physical capability too low → block ATTACK/FLEE
   - Target not reachable → block targeted actions
   - Game rule violation → block
   - Feasibility < 0.1 → block
5. First passing action is selected. Always-valid WAIT is the fallback.

---

## Behavioral Properties

| Property | How enforced |
|---|---|
| Persistent identity | `NPCIdentity` is frozen (immutable dataclass) |
| Bounded memory | Episodic buffer capped at 50; pruned by weight |
| Partial knowledge | Perception check required; private events not received |
| Relationship continuity | Incremental deltas; no reset API |
| Goal-directed action | Top-priority goal used in candidate generation |
| No omniscience | `_can_hear_about()` gates public events; private events blocked |
| No teleporting knowledge | NPC location checked against event location |
| No personality reset | Identity is frozen; only needs/goals/relationships change |
| Can refuse | `ActionKind.REFUSE` is a valid candidate; disposition-gated |
| Can lie | `ActionKind.DECEIVE` generates hedged or false dialogue |
| Can change plans | `Goal.conditions_to_abandon` checked every cycle |
| Explainable decisions | `PolicyContext.explain()` traces every selected and rejected action |

---

## Wiring into ORACLE (future)

When ready, the integration path is:

1. Replace `SimulatedWorldAdapter` with a real game-engine bridge.
2. Instantiate `NPCRuntime` per NPC; persist state to SQLite (reuse ORACLE's memory schema).
3. Route player-NPC interactions through `process_event()` with `interacting_with=player_id`.
4. Optionally: pipe `CycleResult.dialogue` through an LLM for stylistic expansion — but
   the LLM must receive only what the NPC's `world_model` and `memory` contain.
   It must not expand beyond known facts. Pass `npc_runtime.state_summary()` as the system prompt.

---

## Not claimed

This is a persistent cognitive simulation architecture.
It does not claim consciousness, sentience, genuine emotion, or independent personhood.
