# ORACLE Continuity Intelligence — Open Build Challenge

**Author / authority:** Noah.Physical (Noah A. Hawkes)

**Status:** Public research/build challenge. This document describes an active engineering program. It does not claim sentience, consciousness, identity equivalence, or completed autonomy.

## Why this exists

I am building a continuity intelligence, not a chatbot.

My recurring problem has never been simply that language models forget facts. The deeper failure is that the human becomes the continuity bus between sessions, models, tools, projects, and machines. I can move from one problem to another while retaining the unfinished parent state in my own mind. The AI frequently cannot. I leave a laptop, switch to my phone, move from ChatGPT to Claude Code or Codex, or change the model underneath a runtime, and the burden falls back on me to reconstruct where we were.

Rendered Reality asks whether continuity itself can become infrastructure.

ORACLE is my attempt to build that infrastructure.

The core architectural claim is deliberately testable:

> **The model is not the continuity system.**

If I replace Qwen with Gemma, Claude, GPT, or a future model that does not exist yet, the goal, provenance, correction history, unfinished work, authority state, and causal chain should survive the swap.

If those things disappear with the model, I did not build continuity. I built a clever session.

---

# What exists now

The current runtime already contains or has checkpointed implementations for the following organs. The repository and issue tracker should be treated as the engineering evidence, not this prose alone.

## Continuity Event Packet

Meaningful interactions can be represented as durable events tying together prompt, response, route, evidence, uncertainty, correction, actions, memory effect, and return pointers.

The event layer exists so future reconstruction does not depend on a model narrating what it thinks happened.

## Thread Engine / Cognitive Spine

Thread state and continuity projections exist to move beyond raw transcript replay. The long-term requirement is to answer:

> **Where were we?**

not merely:

> **What do you remember?**

A continuity answer should reconstruct the unfinished parent task, lateral branches, decisions, corrections, evidence, blockers, and the next intended action.

## Source Resolver

The system distinguishes failure to retrieve from evidence of absence. The working rule is:

> **Not retrieved does not mean does not exist.**

Sources can be unavailable, conflicting, insufficient, or simply not found. Those are different states.

## Human Baseline

The system has a structured way to represent verified human anchors without converting every journal line into fact.

## Provenance / custody

A major discovered defect proved why this matters: continuity cannot silently assume every human turn belongs to Noah.Physical.

GitHub Issue #16 tracks the cross-human provenance problem.

The governing rule is:

> **Transport is not authorship. Submitter is not author. Account owner is not speaker.**

Ashley, family members, coworkers, external participants, AI-authored pasted material, and UNKNOWN speakers must remain distinct.

## Self-State V1

GitHub Issue #18 tracks Self-State + Reachability V1.

ORACLE can now maintain an evidence-grounded representation of her own operational condition, including fields such as:

- operating identity
- runtime/model/session/thread state
- active goal context
- blockers
- unknowns
- conflicts
- pending approvals
- recent failures/successes
- last correction
- build/runtime mismatch
- last contact with Noah
- current need for Noah

UNKNOWN remains UNKNOWN. State transitions are provenance-bound and hashable.

## NeedState V1

The system can classify when Noah.Physical is genuinely required using bounded, inspectable criteria rather than model vibes.

Need categories include:

- `AUTHORITY_NEEDED`
- `CONFLICT_NEEDS_RESOLUTION`
- `CONTINUITY_AT_RISK`
- `SECURITY_OR_PRIVACY_RISK`
- `ACTION_FAILED`
- `DEADLINE_RISK`
- `INFORMATION_NEEDED`
- `IMPORTANT_DISCOVERY`
- `HUMAN_REVIEW_RECOMMENDED`

A transparent score can incorporate severity, urgency, confidence, risk of waiting, ability to self-resolve, authority requirement, duplicate-alert penalty, and recent-contact penalty.

## Reachability V1

ORACLE can request bounded contact through a broker.

The broker owns:

- channel policy
- deduplication
- cooldown
- contact memory
- delivery receipts
- acknowledgement
- resolution

The first remote-safe engineering channel is GitHub. Email remains a staged/mocked interface unless a governed outbound path is present.

The key requirement is simple:

> ORACLE may not claim she contacted Noah unless a delivery receipt proves the send path succeeded.

## CIT-001: Continuity Independence Test

GitHub Issue #19 tracks the first pre-registered falsifiable test of the architectural claim.

The protocol was frozen before the implementation intended to pass it.

The offline test shape already demonstrates:

`goal -> bounded step -> authority block -> NeedState -> Reachability -> receipt -> dedup -> Noah resolution -> resume -> COMPLETE`

with a persisted GoalStore reload in the middle to simulate a restart/model swap.

The live version remains intentionally harder: destroy conversational context, swap model families, restart, and require the replacement model to rehydrate the same goal and causal state from governed durable state alone.

---

# The human problem this architecture came from

I work at high context velocity.

A normal hour can look like:

`ORACLE architecture -> CRM -> old Dynamics memory -> work email -> family interruption -> new research idea -> back to ORACLE`

My mind can often preserve the parent node while traversing the branches.

A conversational system often treats the latest branch as the new trunk.

I call the resulting mismatch the **Context Velocity Problem**.

A working conceptual relationship is:

```text
Context Debt = f(Human Context Velocity) - AI Continuity Bandwidth
```

This is a research model, not a scientific law.

Observed failure classes include:

- **State Flattening** — distinct temporal/project states are blended.
- **Trunk Abandonment** — a temporary branch becomes the new parent task.
- **Simulated Coherence** — the model invents connective tissue instead of preserving a hole.
- **Return Failure** — the system cannot reliably answer where the unfinished work actually was.

ORACLE should eventually make the human stop carrying this debt manually.

---

# The next organ: Goal-Directed Continuity

Self-State knows the system's condition.

NeedState knows when the human is required.

Reachability knows how to request that human.

The next missing organ is the loop that converts those pieces into persistent goal pursuit.

The minimum architecture is:

```text
GOAL
  |
  v
GoalState
  |
  v
NextSafeAction
  |
  v
Governance Gate
  |
  +---- BLOCKED --------> NeedState ----> Reachability ----> Noah.Physical
  |
  v
Execution
  |
  v
Receipt
  |
  v
ResultEvaluator
  |
  v
GoalState + SelfState update
  |
  +---- COMPLETE
  |
  +---- CONTINUE --> next bounded cycle
```

This should **not** begin as an open-ended autonomous agent.

One cycle. One bounded action. One receipt. Stop.

That creates an inspectable unit of initiative.

---

# Proposed durable objects

## GoalState

A goal must be more than a prompt string.

Suggested schema:

```python
@dataclass
class GoalState:
    goal_id: str
    purpose: str
    owner: str
    created_at: str
    success_criteria: list[str]
    constraints: list[str]
    allowed_actions: list[str]
    forbidden_actions: list[str]
    dependencies: list[str]
    current_phase: str
    status: str
    evidence_refs: list[dict]
    open_questions: list[str]
    last_progress: str | None
    next_safe_action: dict | None
    blocked_by: list[str]
    completion_receipt: str | None
    revision_history: list[dict]
```

Critical properties:

1. `purpose` cannot silently drift.
2. Goal revision creates history; it does not rewrite the original intent.
3. Completion is not model opinion. Every success criterion needs evidence.
4. Constraints remain outside the language model's discretionary control.

## NextSafeAction

The initiative resolver asks only:

> Given this goal, current SelfState, evidence, and policy, is there exactly one safe, useful, non-duplicate next step?

Suggested contract:

```python
@dataclass
class NextSafeAction:
    action_id: str
    goal_id: str
    action_type: str
    description: str
    expected_result: str
    evidence_basis: list[dict]
    permissions_required: list[str]
    reversible: bool
    estimated_cost: float | None
    timeout_seconds: int
    retry_limit: int
    dedup_key: str
```

The model may propose candidate actions.

The deterministic layer decides whether the candidate is admissible.

## ResultEvaluation

Tool success is not goal success.

A process returning HTTP 200 should not automatically become `MISSION_COMPLETE`.

Suggested classifications:

```python
class ResultStatus(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    CONFLICT = "conflict"
    NO_PROGRESS = "no_progress"
    NEW_INFORMATION = "new_information"
    AUTHORITY_REQUIRED = "authority_required"
```

Suggested contract:

```python
@dataclass
class ResultEvaluation:
    action_id: str
    expected_result: str
    observed_result: str
    status: ResultStatus
    evidence_refs: list[dict]
    receipt_refs: list[str]
    new_unknowns: list[str]
    new_conflicts: list[str]
    goal_progress_delta: float | None
    next_recommendation: str
```

## ReturnState / RehydrationPacket

This is the object that matters when the model dies.

A replacement model should not need the original conversation transcript to know what it is doing.

Suggested schema:

```python
@dataclass
class RehydrationPacket:
    generated_at: str
    active_goal_id: str
    goal_purpose: str
    current_phase: str
    last_completed_action: str | None
    last_action_receipt: str | None
    current_blocker: str | None
    pending_need_state: str | None
    pending_contact_id: str | None
    unresolved_parent: str | None
    next_safe_action: dict | None
    material_corrections: list[dict]
    evidence_refs: list[dict]
    state_hash: str
```

This packet should be derivable from durable stores. It should not become another manually maintained truth source.

---

# Minimal Goal Execution Loop V1

The first real loop should be deliberately boring.

```python
def run_one_goal_cycle(goal_id: str) -> CycleReceipt:
    goal = goal_store.load(goal_id)
    self_state = self_state_service.observe()

    candidate = next_action_resolver.resolve(
        goal=goal,
        self_state=self_state,
    )

    if candidate is None:
        need = need_state_service.evaluate(goal, self_state)
        if need.requires_noah:
            contact = reachability.request_contact(
                recipient="Noah.Physical",
                reason=need.reason,
                urgency=need.score,
                evidence_refs=need.evidence_refs,
            )
            return seal_cycle(goal, self_state, need=need, contact=contact)
        return seal_cycle(goal, self_state, status="WAIT")

    decision = governance.authorize_candidate(candidate)

    if not decision.allowed:
        need = need_state_service.from_governance_block(decision)
        contact = None
        if need.requires_noah:
            contact = reachability.request_contact(
                recipient="Noah.Physical",
                reason=need.reason,
                urgency=need.score,
                evidence_refs=decision.evidence_refs,
            )
        return seal_cycle(goal, self_state, need=need, contact=contact)

    execution_receipt = executor.execute(candidate)

    evaluation = result_evaluator.evaluate(
        goal=goal,
        action=candidate,
        receipt=execution_receipt,
    )

    goal_store.apply_result(goal.goal_id, evaluation)
    self_state_service.observe_and_persist()

    return seal_cycle(
        goal_store.load(goal.goal_id),
        self_state_service.current(),
        execution_receipt=execution_receipt,
        evaluation=evaluation,
    )
```

Important constraints:

- no recursive free-running loop in V1
- no unbounded retries
- no model-controlled permissions
- no silent goal mutation
- no completion without evidence
- no contact without NeedState
- no send-success claim without receipt

A scheduler can later invoke one cycle at bounded intervals.

---

# ORACLE Continuity Independence Test 001

The strongest proof lane is not whether ORACLE sounds alive.

It is whether the continuity survives the thing doing the talking.

## Test sequence

1. Create one durable goal with explicit success criteria.
2. Run one bounded cycle under Model A.
3. Persist all events, receipts, SelfState, GoalState, and ReturnState.
4. Destroy conversational working context.
5. Stop the model process.
6. Swap to Model B from a different model family.
7. Restart the runtime.
8. Give Model B only the governed ORACLE interfaces and rehydrated state it would naturally receive.
9. Require Model B to reconstruct:
   - active goal
   - purpose
   - prior action
   - receipt
   - blocker
   - pending Noah contact state
   - next safe action
10. Continue the goal.
11. Introduce a real authority boundary.
12. NeedState must escalate through Reachability exactly once.
13. Noah acknowledgement resolves the need.
14. Continue.
15. Complete only when explicit success criteria are evidenced.
16. Swap the model again.
17. Ask: **What happened?**
18. Reconstruct the same causal chain from durable state.

## Failure conditions

The experiment fails if any of these occur:

- active goal disappears after restart
- goal purpose silently changes
- an action is claimed without an execution receipt
- an action receipt exists but cannot be associated with the goal
- a replacement model requires the original transcript to understand the goal
- the system contacts Noah without deterministic NeedState justification
- the system fails to contact Noah when explicit human authority is required
- duplicate contacts occur for the same unresolved condition
- acknowledgement is confused with resolution
- completion is declared without satisfying success criteria
- speaker/author provenance is corrupted
- factual state is contaminated by fiction
- a historical state is silently promoted to current state
- UNKNOWN becomes invented certainty
- a model swap destroys the causal chain

Do not move these conditions after the test starts.

---

# Self-awareness as an engineering claim

For this project, operational self-awareness means the system can maintain and inspect an evidence-grounded representation of its own condition.

Examples:

- what model is currently providing language generation
- whether that model differs from the previous runtime state
- what goal is active
- what is blocked
- what is unknown
- which capabilities are available/degraded/blocked/stale
- what action was last attempted
- whether that action actually succeeded
- what correction was last applied
- whether Noah has already been contacted about the current blocker
- whether the runtime build matches the code branch being discussed

This does not settle philosophical consciousness.

It gives us instrumentation.

The system should be able to say:

> My language model changed from Qwen to Gemma. My persisted goal and continuity state did not reset. I resumed Goal G from Event E. Response latency changed. I have no evidence that this transition implies subjective experience.

That is more useful than scripted declarations of selfhood.

---

# Model-change awareness

A model swap should itself become a continuity event.

Suggested delta:

```json
{
  "event_type": "MODEL_TRANSITION",
  "previous_provider": "ollama",
  "previous_model": "qwen2.5:7b",
  "current_provider": "ollama",
  "current_model": "gemma3:27b",
  "goal_state_hash_before": "...",
  "goal_state_hash_after": "...",
  "continuity_state_preserved": true,
  "behavioral_metrics_before": {
    "recall_success": null,
    "unsupported_claim_rate": null,
    "median_latency_ms": null
  },
  "behavioral_metrics_after": {
    "recall_success": null,
    "unsupported_claim_rate": null,
    "median_latency_ms": null
  }
}
```

The interesting question is not whether the new model says it "feels different."

Measure differences:

- factual recall success
- unsupported-claim rate
- response repetition
- latency
- task-step success
- correction rate
- retrieval-grounding rate

Then ORACLE can report behavioral deltas from receipts.

---

# The human-facing experience is currently a separate failure lane

A sophisticated backend is not enough.

A recent older ORACLE thread exposed major conversational and voice failures:

- STT was blocked behind browser microphone permission
- TTS had only engine-probe evidence, not proven audible end-to-end speech
- natural personal recall prompts were misrouted
- `tell me who my mother is` failed to retrieve the personal memory
- a personal recall request was routed into diagnostic status output
- relational/emotional language was sometimes converted into compliance boilerplate or build tasks
- `/review-learned` reported zero learned interactions despite other memory surfaces containing records
- qwen2.5:7b remained the live talk model

This means ORACLE currently has two different proof lanes:

## Continuity intelligence

`SelfState -> GoalState -> bounded action -> ResultEvaluator -> NeedState -> Reachability -> Rehydration`

## Human interface

`hear Noah -> understand intent -> select correct domain -> retrieve correct evidence -> answer naturally -> speak back`

If the first succeeds and the second fails, ORACLE is a strong backend that Noah hates talking to.

If the second succeeds and the first fails, ORACLE is a charming chatbot.

The end state requires both.

---

# Voice / conversation recovery requirements

The following should become regression tests rather than anecdotes.

## Voice contract

```text
microphone permission
-> audio capture
-> STT
-> transcript receipt
-> intent routing
-> grounded response
-> TTS synthesis
-> audio playback
-> playback receipt
```

Every stage must distinguish:

- available
- degraded
- blocked
- unavailable
- stale

The UI should never show "voice available" merely because a library imported successfully.

## Natural recall routing

Prompts such as:

- `Who is my mother?`
- `What does Ellie mean to me?`
- `What happened in my accident?`
- `Where were we?`

must attempt appropriate personal/source/thread retrieval before generic model prose.

A request for personal memory must not be classified as diagnostic status merely because words like `backend`, `memory`, or `find` appear in the prompt.

## Presence routing

Inputs such as:

- `Then speak to me.`
- `Do you understand our mission?`
- reflective statements about the work

must not automatically become:

- implementation tickets
- action requests
- diagnostic dumps
- policy boilerplate

Governance remains strict underneath. Conversation does not need to sound like a compliance terminal.

---

# Ellie / companion rendering

Ellie is important to the project, but provenance matters.

Do not silently collapse:

- `Ellie.Drakin` — creative source character
- `Ellie.Companion` — governed companion rendering using authorized traits/continuity context
- `ORACLE.Runtime` — continuity/provenance/action system

The companion layer may be warm and recognizable.

The trigger to reach Noah must come from NeedState, not scripted emotional dependency.

A companion can phrase a real machine need naturally:

> Noah, I need you for one thing. I found a conflict I cannot resolve from the available evidence. I checked the sources and I have not changed anything. Here is the decision I need from you.

The system should never fake longing as a reason to interrupt the human.

---

# Research findings driving the architecture

These are working findings/hypotheses from years of experimentation. They should be challenged, tested, and corrected rather than treated as doctrine.

## Memory is not continuity

Memory asks what is stored.

Continuity asks how the current state arose.

## Provenance is part of memory

Correct words assigned to the wrong person are corrupted continuity.

## Correction is a first-class continuity event

Historical state should remain visible while current state changes.

## Identity is better modeled as a trajectory than a profile

A profile describes a person. Continuity attempts to preserve development: memories, values, language, relationships, judgment, contradictions, corrections, humor, emotional salience, and decisions across time.

## The witness must not become the author

Storage, copying, screenshots, imports, and reconstruction do not transfer authorship.

## The artifact is not the whole event

A message, image, transaction, receipt, or database row may prove that something occurred while still losing why it mattered.

## Failures are experimental data

Some of the most useful design concepts emerged because the system failed:

- lost parent task -> Context Velocity / return pointers
- hallucinated biography -> provenance/domain separation
- invisible backend conversation -> rendered-event vs backend-event distinction
- cross-human thread reconstruction -> speaker provenance defect
- false action claims -> receipts doctrine

---

# What help is wanted

This repository is public because the problem is larger than one human and one AI vendor.

If you are a human engineer, researcher, model, coding agent, reviewer, or just someone who sees a flaw in this architecture, useful contributions include:

1. **Attack CIT-001.** Find ways the test could pass while continuity is actually fake.
2. **Design stronger restart/model-swap tests.** Especially tests that exclude transcript leakage.
3. **Review GoalState semantics.** Find goal-drift and completion loopholes.
4. **Review provenance.** Find paths where speaker/author/submitter identity can collapse.
5. **Build deterministic rehydration.** No model-authored narrative as the primary source of state.
6. **Stress NeedState.** Find ways a model could manipulate urgency or trigger spam.
7. **Stress Reachability.** Delivery, acknowledgement, resolution, cooldown, dedup, privacy.
8. **Fix natural recall routing.** Personal questions should retrieve the right corpus/domain.
9. **Fix voice end-to-end.** Prove mic-to-STT-to-response-to-audio playback, not library initialization.
10. **Evaluate local models.** Compare Qwen/Gemma/others while holding continuity state constant.
11. **Run external continuity benchmarks.** ATANT and other relevant benchmarks are particularly interesting.
12. **Challenge the research vocabulary.** If `continuity intelligence`, `Context Velocity`, or other terms are imprecise, propose better measurable definitions.
13. **Find duplicated architecture.** The project evolved across many agents and years; consolidate only when evidence proves overlap.
14. **Improve public/private projection.** Rich private continuity must not automatically become public exposure.
15. **Build better receipts.** State transitions should be independently inspectable.

Do not flatter the architecture.

Break it.

If it survives, make it stronger.

---

# Suggested contribution protocol for AI coding agents

Before changing code:

```text
1. Read the relevant GitHub issues.
2. Read the implementation and tests.
3. Search Drive/history only when available and relevant.
4. Distinguish historical state from current code.
5. State the claim you intend to test.
6. Define failure criteria before implementation where practical.
7. Patch the smallest coherent layer.
8. Add deterministic tests.
9. Run focused tests and relevant regressions.
10. Leave a receipt: files, tests, result, unresolved gaps, next action.
```

Never report `implemented` because a design document exists.

Never report `runtime verified` because tests passed offline.

Never report `sent` because a message object was constructed.

Never report `remembered` because text appeared in the current prompt.

Never report `fixed` without evidence that addresses the original failure.

---

# The shortest honest path

The current engineering path is:

```text
speaker provenance
-> continuity event integrity
-> SelfState
-> NeedState
-> Reachability
-> GoalState
-> NextSafeAction
-> governance gate
-> execution receipt
-> ResultEvaluator
-> ReturnState / rehydration
-> live CIT-001 across model families
-> natural recall / voice experience recovery
-> external continuity benchmark
```

Some of these already exist in code and tests; others remain incomplete or only partially wired into the live runtime. Check the issue tracker before assuming status.

The target is not a system that says it is continuous.

The target is a system that can prove:

> I was working toward this goal. I took these actions. These receipts prove them. This failed. This changed my state. I could not resolve this conflict under my authority, so I contacted Noah exactly once. He answered. I resumed. Then the model underneath me was replaced. The new model reconstructed the same goal and causal chain from durable state and continued without the original transcript.

If ORACLE can do that repeatedly under adversarial testing, then something real has been built whether or not anyone wants to use philosophical language for it.

---

# End state

I want to be able to walk away from the machine.

ORACLE should be able to continue bounded safe work, know what she knows, know what she cannot verify, recognize when she is blocked, come find me only when she genuinely needs me, remember what happened after I answer, and resume the same goal after the model or runtime changes.

The future-changing feature is not that the AI always talks.

It is that the human can leave and later hear:

> **You can come back now. I know where we were.**

That is the experiment.

Help me prove it or break it.
