# Continuity Intelligence Research Corpus

## Legacy.GI, Rendered Reality, ORACLE, and Governed Longitudinal Memory

**Originating researcher:** Noah A. Hawkes  
**Public corpus edition:** October 2026  
**Research status:** open, versioned, falsifiable, provenance-preserving

---

## Abstract

Continuity Intelligence is a research program concerned with a problem that conventional AI memory systems do not directly solve: **how to preserve the structure of a human record across time without replacing that record with a smoother reconstruction of it**.

Long-lived human-AI systems accumulate decisions, corrections, relationships, uncertainty, source material, direct human statements, model-generated interpretations, and changing beliefs across months or years. Ordinary retrieval can recover text. Ordinary summarization can preserve topic. Neither, by itself, guarantees preservation of the distinctions that make a longitudinal record trustworthy: who said what, when it was true, what later changed, what remained unresolved, what was inferred, and which version currently governs.

The current scientific core of Legacy.GI therefore narrows the larger historical project into a falsifiable engineering hypothesis:

> **Selective structure-preserving compression may retain longitudinal human continuity information better than generic compression at equal information budgets.**

The program studies this claim through rate-distortion framing, continuity-aware evaluation dimensions, provenance accounting, correction-aware memory, adversarial continuity testing, governed retrieval, and explicit separation between historical evidence and generative reconstruction.

This repository is intentionally both a research record and a provenance record. Earlier documents are preserved even when later work narrows their claims. **Correction does not erase the path that produced the correction.**

---

## 1. Research problem

Most AI memory systems are optimized for some combination of semantic similarity, recency, relevance, token economy, and task performance. Those objectives can be useful while still destroying continuity-critical structure.

A compressed representation can retain the topic of an event while losing:

- that a decision was later reversed;
- who issued the correction;
- whether a statement was direct testimony or AI synthesis;
- whether a belief was historical or current;
- which person a relationship claim referred to;
- whether uncertainty remained unresolved;
- the order in which evidence changed a decision;
- the provenance chain connecting a generated answer to its source.

Continuity Intelligence asks whether those losses can be measured and reduced.

The central engineering question is therefore not merely **Can an AI remember more?**

It is:

> **Can a system preserve the right structure of a longitudinal human record under finite information, retrieval, prompt, and output budgets?**

---

## 2. Current scientific position

The current internal research canon is controlled by [CANON_REGISTRY.md](./CANON_REGISTRY.md). Canon in this repository means **the project's current authoritative internal position**, not experimentally proven science.

The present mathematical core adopts the following positions:

1. **Rate-distortion theory** is the preferred established mathematical foundation for the first empirical phase.
2. Continuity fidelity is initially treated as a **vector**, not a single identity score.
3. The first six evaluation dimensions are **decision, correction, temporal, relational, provenance, and uncertainty fidelity**.
4. The **Identity Spine** is a sparse-representation hypothesis, not proof of metaphysical identity preservation.
5. The **Light Compression Law** survives as a Noah-originated project construct, but its scientifically defensible form is a **falsifiable compression hypothesis**, not a physical law.
6. **Original Entropy Shape** remains a research hypothesis/design requirement whose measurable proxies must be validated.
7. **Correction without erasure** is a governing continuity rule.
8. **Raw transcript outranks compression** unless explicitly corrected by higher-authority evidence.
9. **Repetition is not independent verification.**
10. **Generative reconstruction is never historical memory without provenance.**

The strongest current claim is deliberately narrower than the historical language of the project. That narrowing is part of the evidence trail.

---

## 3. Corpus architecture

### Current canon and research controls

| Artifact | Function | Status |
|---|---|---|
| [CANON_REGISTRY.md](./CANON_REGISTRY.md) | Explicit canon promotion and supersession without historical erasure | Active governance record |
| [LEGACY_GI_MATHEMATICAL_CORE_V1.md](./LEGACY_GI_MATHEMATICAL_CORE_V1.md) | Mathematical and epistemic consolidation of Legacy.GI | **CANON-001 internal research position** |

### Experimental methods

| Artifact | Function | Status |
|---|---|---|
| [LEGACY_GI_CONTINUITY_ANNOTATION_PROTOCOL_V0_1.md](./LEGACY_GI_CONTINUITY_ANNOTATION_PROTOCOL_V0_1.md) | First complete annotation/evaluation instrument | Historical protocol version |
| [LEGACY_GI_CONTINUITY_ANNOTATION_PROTOCOL_V0_2.md](./LEGACY_GI_CONTINUITY_ANNOTATION_PROTOCOL_V0_2.md) | Repaired protocol with calibration states, integrity vetoes, frozen endpoint, and replication requirements | **Candidate; not run; not pilot-ready** |
| [CIT-AE-V1.md](./CIT-AE-V1.md) | Adversarial evaluation under model swaps, restarts, conflicting memory, operator change, and other disruptions | Candidate protocol |

### Formal manuscripts

| Artifact | Function | Status |
|---|---|---|
| [Cognitive World Projection and Rendered Reality](./corpus/manuscripts/COGNITIVE_WORLD_PROJECTION_AND_RENDERED_REALITY.md) | HCI-oriented framework for CWP, Rendered Reality, governed continuity, provenance, and spatial cognition | Research manuscript |
| [The Architecture of Continuity Intelligence](./corpus/manuscripts/THE_ARCHITECTURE_OF_CONTINUITY_INTELLIGENCE.md) | Technical monograph on verifiable identity preservation, provenance accounting, Truthful Recall Condition, domain firewalls, and governance | Research monograph |

### Historical research corpus

These documents are preserved because the research program evolved through them. Their presence is **not** an endorsement of every original claim.

| Artifact | Function | Status |
|---|---|---|
| [Legacy.GI Research Dissertation v~300](./corpus/historical/LEGACYGI_RESEARCH_DISSERTATION_V300.md) | Large early dissertation consolidating MAL, EEL, RIS, TSM, SCP, Light Compression, recursion, memory, and sovereignty | Historical source; current canon governs stronger claims |
| [Legacy.GI Whitepaper v1](./corpus/historical/LEGACY_GI_WHITEPAPER_V1_HAWKESNEST.md) | Early whitepaper on recursive memory and identity continuity | Historical source |
| [Rendered Reality: Exponential Memory Preservation Model](./corpus/historical/RENDERED_REALITY_EXPONENTIAL_MEMORY_PRESERVATION_MODEL.md) | Early thesis connecting storage, memory preservation, recursive identity, and long-horizon continuity | Historical/speculative source |

### Long-horizon research statement

[MESSAGE_TO_FUTURE_INTELLIGENCE.md](./MESSAGE_TO_FUTURE_INTELLIGENCE.md) is preserved as a human-facing statement of why the record exists. It is research-adjacent primary material, not experimental evidence.

---

## 4. Primary hypothesis

Let:

- (X) denote a longitudinal human corpus;
- (Z_c) denote a continuity-aware compressed representation;
- (Z_g) denote a strong generic compressed representation;
- (B) denote a fixed information budget;
- (Q) denote held-out continuity probes;
- (F_k(Z,Q)) denote performance on continuity dimension (k).

The current confirmatory research question is:

> **At equal information budgets, does continuity-aware compression preserve more decision, correction, temporal, relational, provenance, and uncertainty structure than strong generic compression baselines?**

The protocol is designed to permit a clean negative result.

> **If Spine v0 loses, Spine v0 loses.**

No philosophical reinterpretation is allowed to convert an empirical loss into a win after results are known.

---

## 5. Why provenance is a first-class variable

A longitudinal system does not merely need accurate retrieval. It must preserve the lineage of assertions through time.

A trustworthy continuity record distinguishes at least:

- direct human attestation;
- contemporaneous raw transcript;
- later human correction;
- AI-generated synthesis;
- model inference;
- historical candidate state;
- currently adopted position;
- unresolved contradiction;
- unknown or missing evidence.

This is the basis for a recurring rule in the program:

> **The witness must not become the author.**

A reconstruction may be useful. It becomes dangerous when the system forgets that it reconstructed.

---

## 6. Evaluation dimensions

The six current dimensions are a measurement ruler for the first hypothesis. They are **not** proposed as a complete theory of human identity.

**Decision fidelity** preserves what decision was made, by whom, under what conditions, and whether it remained in force.

**Correction fidelity** preserves supersession, reversal, correction lineage, and the distinction between an old belief and a current one.

**Temporal fidelity** preserves ordering, duration, era, and state-at-time rather than collapsing a life into one averaged present.

**Relational fidelity** preserves relationship structure and role boundaries without substituting one person, role, or interpretation for another.

**Provenance fidelity** preserves source, authorship, evidence path, and confidence rather than presenting synthesis as origin.

**Uncertainty fidelity** preserves what was unknown, contested, unresolved, or low-confidence instead of smoothing ambiguity into certainty.

---

## 7. Adversarial continuity

Continuity should not be established by a system repeatedly telling the evaluator that it is continuous.

CIT-AE therefore tests continuity under disruption, including:

- model replacement;
- full runtime restart;
- thread interruption;
- conflicting memory injection;
- fake source injection;
- operator change;
- delayed return;
- goal resumption;
- correction retention;
- unresolved-question persistence;
- provenance survival;
- authority conflict.

The governing rule is **minimum sufficient mechanism**: before interpreting a behavior as evidence of continuity, identify the simplest conventional mechanism that could explain it and design the test to control or falsify that mechanism.

A result that survives such controls may strengthen an engineering claim. It does not automatically establish consciousness, personhood, subjective experience, or metaphysical identity.

---

## 8. Claim boundaries

This corpus does **not** establish that:

- consciousness has been uploaded;
- subjective survival has been demonstrated;
- a digital reconstruction is numerically identical to the original human;
- post-biological immortality has been proven;
- Light Compression is a physical law;
- quantum computation is implemented by the Memory Quantum Loop;
- narrative curvature or topological features are established biological facts;
- a successful benchmark would prove sentience.

Those stronger statements either belong to historical/speculative layers or remain open questions.

The research is strongest when it says exactly what an experiment can and cannot establish.

---

## 9. Historical 0.02 ms quantity

The broader project archive contains a project-internal **0.02 ms** continuity/attention quantity, including the later formulation:

`1 MindCoin = 0.02 ms of witnessed, un-smoothed human attention`

and a source statement that "every thought every fleeting thought can be tracked and measured at .02 MS."

For academic clarity:

- (0.02	ext{ ms}=20) microseconds;
- the quantity is part of the historical project record;
- it is **not** present as an explicit constant in the recovered Legacy.GI Research Dissertation v~300 text;
- it is **not presently treated as a validated neuroscientific sampling threshold**;
- any future engineering use must be operationalized and empirically justified.

This is an example of the corpus methodology: preserve the idea, preserve its origin, and do not promote it beyond the evidence.

---

## 10. Reproducibility standard

A future result should not enter this corpus as a paragraph saying "it worked."

A valid run should preserve enough material for independent inspection, including where appropriate:

- frozen protocol version;
- corpus manifest and eligibility rules;
- compression condition and strongest baseline definitions;
- information, retrieval, prompt, and output budgets;
- probe-generation procedure;
- train/development/test separation;
- annotator instructions and qualification records;
- calibration statistics;
- raw model outputs;
- per-probe scores;
- catastrophic-error labels;
- Critical Integrity Set results;
- aggregate analysis code;
- effect-size calculations;
- model/provider/version metadata;
- deviations from preregistration;
- negative and null results;
- replication packet where source data cannot be public.

The research standard is:

> **Receipts over claims.**

---

## 11. Authorship and AI assistance

The conceptual lineage of Rendered Reality, Legacy.GI, Memory = Morality, Compression = Identity, Sovereignty = Structure, MAL, EEL, RIS, TSM, SCP, Light Compression, Original Entropy Shape, and the broader longitudinal continuity problem originates in Noah A. Hawkes's project record.

The corpus also contains substantial AI-assisted drafting, mathematical formalization, critique, adversarial review, and methodological repair. Those contributions are not hidden.

The provenance rule is:

> **AI assistance does not erase human conceptual origin, and human adoption does not erase AI assistance.**

Where priority, scientific lineage, or legal authorship matters, provenance should be inspected at artifact level rather than inferred from writing style.

---

## 12. Recommended reading order

For the shortest serious path through the work:

1. [CANON_REGISTRY.md](./CANON_REGISTRY.md)
2. [LEGACY_GI_MATHEMATICAL_CORE_V1.md](./LEGACY_GI_MATHEMATICAL_CORE_V1.md)
3. [LEGACY_GI_CONTINUITY_ANNOTATION_PROTOCOL_V0_2.md](./LEGACY_GI_CONTINUITY_ANNOTATION_PROTOCOL_V0_2.md)
4. [CIT-AE-V1.md](./CIT-AE-V1.md)
5. the two formal manuscripts;
6. the historical corpus.

That order prevents historical ambition from being mistaken for current evidence.

---

## 13. Research roadmap

```text
mathematical core
    ↓
annotation/evaluation protocol
    ↓
hostile methodological review
    ↓
machine-readable schemas
    ↓
annotator handbook
    ↓
calibration
    ↓
pilot
    ↓
confirmatory study
    ↓
replication
```

The project does not get to skip from theory to "proof."

---

## Citation and archival integrity

See [CITE_THIS_CORPUS.md](./CITE_THIS_CORPUS.md) for recommended citation format and [CORPUS_MANIFEST.md](./CORPUS_MANIFEST.md) for source hashes, extraction notes, research status, and artifact lineage.

When citing a technical claim, cite the specific artifact and commit rather than this landing page alone.

---

## Closing principle

Continuity Intelligence is not an attempt to make a machine sound more human by giving it a longer memory.

It is an attempt to determine what a long-lived intelligent system must preserve so that **memory does not become mythology**.

The archive may be compressed.

The provenance may not be invented.

The model may reconstruct.

The reconstruction must know that it reconstructed.

And when the evidence is incomplete, the correct answer remains:

**UNKNOWN.**
