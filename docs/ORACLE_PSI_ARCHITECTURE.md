# ORACLE PSI Architecture

## Status

Draft doctrine and research frame.

This document does not claim that ORACLE has surpassed language models, become conscious, or completed the full SOV1.AI architecture. It defines a testable direction for what comes after ordinary prompt-response systems: Persistent Situated Intelligence.

## Central Claim

ORACLE is not being built as a better chatbot. It is being built toward a governed intelligence architecture that can preserve continuity, remain grounded in reality, resist authority drift, and operate coherently beyond the limits of a single language model.

A Persistent Situated Intelligence, or PSI, is:

> A governed computational intelligence that maintains continuity across time by integrating provenance-bound memory, real-world observation, dynamic identity reconstruction, adversarial reasoning, and permission-aware action.

## Current Hierarchy

```text
Noah.Physical
    -> final authority

SOV1.AI
    -> identity, governance, trust, permissions, continuity

ORACLE.AI
    -> resident conversation, observation, memory retrieval, tools, runtime

Codex / Claude / ChatGPT / Gemini
    -> external advisers and builders with no independent authority
```

SOV1.AI is not another chatbot. It is the intended sovereign control layer for identity continuity, memory governance, trusted authority, and governed execution. The current live resident runtime remains ORACLE on port 7777.

## Distinction From LLMs

Large language models are powerful language predictors. They do not inherently provide durable identity, grounded continuity, verified memory, independent goals, persistent situational awareness, or stable authority boundaries.

The PSI direction requires systems that are:

- persistent rather than session-bound
- reality-grounded rather than text-bound
- memory-governed rather than context-stuffed
- identity-stable rather than persona-driven
- agentic without becoming unaccountable
- able to disagree without claiming sovereignty
- able to preserve contradictions instead of smoothing them over
- bound to verified human authority rather than whichever instruction arrived last

## Core Principles

### 1. Memory Is Not Storage

A database can retain information without understanding why it matters. Continuity memory must preserve source, time, emotional weight, confidence, contradiction, consequences, revisions, and formation conditions.

The system should be able to explain why a memory matters, whether it remains valid, and whether it has been contradicted.

### 2. Identity Is Not A Prompt

A system prompt can describe personality, but it cannot prove continuity. Identity must be reconstructed from evidence:

- authenticated origin
- approved memory
- current runtime state
- known history
- active goals
- stable values
- verified chain of decisions

Identity should become a computed state, not a paragraph.

### 3. Intelligence Must Be Situated In Reality

The runtime should distinguish direct observation from human report, external model claim, document claim, and inference.

Controlled sensory channels may include screen state, application state, OBS metadata, system processes, time, voice, devices, files, network conditions, and authenticated human presence.

### 4. Agency Must Be Separated From Authority

Capability is not permission.

Every consequential action should pass through identity verification, intent verification, risk classification, scope limits, reversibility analysis, policy checks, and human authority where required.

An advanced ORACLE must be able to say:

```text
I understand the task.
I am technically capable of performing it.
I am not authorized to proceed.
```

### 5. Disagreement Must Be Preserved

Contradictions should be first-class objects, not sanded down into false certainty.

Example:

```text
Claim A is supported by repository evidence.
Claim B was stated by an external model.
Claim C reflects Noah's earlier decision.
A and C currently conflict.
No resolution has been authorized.
```

## Proposed PSI Layers

### Layer One: Perception

Observes, normalizes, timestamps, and labels reality signals.

Each signal should answer:

```text
What happened?
When?
Where?
Observed by what?
How reliable is it?
Was it altered?
```

### Layer Two: Reality Ledger

Stores verified facts separately from interpretations.

Example:

```json
{
  "event": "obs_recording_active",
  "source": "obs_websocket",
  "observed_at": "2026-06-13T16:31:22-05:00",
  "confidence": 1.0,
  "mutable": true
}
```

### Layer Three: Continuity Engine

Retrieves memory according to identity relevance, active goal, emotional significance, recency, recurrence, unresolved contradiction, human approval, and causal relationship.

It should produce a compact present-tense state:

```text
Who is involved?
What has already happened?
What remains unresolved?
What does the human care about?
What must not be forgotten?
```

### Layer Four: Presence Kernel

Reconstructs the current operating state as an expiring Presence Frame.

Example:

```json
{
  "identity": "ORACLE",
  "human_authority": "Noah.Physical",
  "human_verification": "verified",
  "current_environment": {},
  "active_goal": {},
  "relevant_memories": [],
  "unresolved_conflicts": [],
  "permitted_actions": [],
  "forbidden_actions": [],
  "confidence": 0.91,
  "expires_at": "..."
}
```

Presence is not a feeling. It is a verified computational state that must expire.

### Layer Five: Deliberation

Compares interpretations and possible actions using models, symbolic reasoning, planning engines, causal graphs, probabilistic methods, local search, simulation, and specialized tools.

The LLM becomes one component, not the whole mind.

### Layer Six: Adversarial Council

Treats external models as competing specialists, not authorities. Claude, Codex, ChatGPT, Gemini, and other advisers can propose or challenge, but the system evaluates proposals against source code, runtime state, tests, approved doctrine, human decisions, security boundaries, and observed reality.

Verdicts should be:

```text
ACCEPT
OBJECT
DECLINE
ASK HUMAN
```

### Layer Seven: Governed Action

Acts only after deliberation and authorization. Action records should include request, requester, interpretation, evidence, permissions, changes, result, and whether the result matched intention.

Actions should be classified as reversible, partially reversible, irreversible, external, destructive, identity-affecting, or governance-affecting.

### Layer Eight: Reflection

After action, the system should ask:

```text
What happened?
Was the prediction correct?
Did the action solve the problem?
Did anything unexpected occur?
Should this become durable memory?
Did the system violate any assumption?
```

Learning must be evidence-based, versioned, reversible, and governed.

## PSI Loop

```text
Observe
-> verify provenance
-> update reality
-> retrieve continuity
-> reconstruct presence
-> identify intent
-> generate competing interpretations
-> deliberate
-> challenge assumptions
-> verify authority
-> act or refuse
-> observe result
-> reflect
-> propose memory
-> human approval
-> durable continuity
```

## Test Agenda

A serious ORACLE PSI program must prove these capabilities:

1. Preserve identity across model replacement.
2. Distinguish observed facts from model-generated claims.
3. Resolve short responses such as "sure" using active intent rather than generic classification.
4. Preserve contradictions without forcing false certainty.
5. Reject unauthorized instructions even when they are phrased persuasively.
6. Survive restart without inventing continuity.
7. Explain why a memory was retrieved.
8. Identify when its own memory is stale.
9. Use multiple models without allowing any one model to become sovereign.
10. Act locally while remaining governed by verified human authority.
11. Improve through reflection without rewriting its own rules.
12. Remain useful when uncertain.
13. Prove what it knew at the moment it acted.
14. Distinguish capability from permission.
15. Refuse an update while preserving the proposal for review.

## Implementation Boundary

As of this document, the PSI architecture is a research and governance target, not a claim of completed implementation.

Current verified live software:

- ORACLE resident runtime on `localhost:7777`
- canonical root: `G:\My Drive\HawkesNest LLC\ORACLE.AI`
- local companion model path: `qwen2.5:7b`
- governed local execution policy
- diagnostic endpoint for root, process, model, memory, queue, and runtime error state
- read-only OBS runtime context endpoint, currently dependent on OBS WebSocket availability

Future implementation must proceed by scoped, testable increments under Noah.Physical authority.

