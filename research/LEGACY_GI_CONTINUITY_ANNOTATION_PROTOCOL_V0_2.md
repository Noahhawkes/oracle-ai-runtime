# Legacy.GI Continuity Annotation and Evaluation Protocol v0.2

**Status:** CANDIDATE RESEARCH PROTOCOL  
**Canon status:** NOT CANON until Noah.Physical approves  
**Execution status:** NOT RUN  
**Readiness:** NOT PILOT-READY  

**Repository:** `Noahhawkes/oracle-ai-runtime`  
**Branch:** `archive/runtime-lineage-2e6b0a3`  
**Target path:** `research/LEGACY_GI_CONTINUITY_ANNOTATION_PROTOCOL_V0_2.md`  
**Record date:** 2026-10-08  
**Originating researcher:** Noah A. Hawkes  
**Prior protocol:** `research/LEGACY_GI_CONTINUITY_ANNOTATION_PROTOCOL_V0_1.md`  
**Prior protocol commit:** `feb4dd171b3d665988713a0d2e3bb3f10082a594`  
**Record type:** Annotation protocol, evaluation specification, integrity gate, and preregistration scaffold  

---

## Version 0.2 change log

Protocol v0.2 applies the accepted twelve-item repair specification to Protocol v0.1.

1. Added terminal calibration states, a maximum of three calibration rounds, and explicit dimension-removal consequences.
2. Split relational fidelity into confirmatory relational structure and exploratory relational interpretation.
3. Added a 24-probe Critical Integrity Set and an absolute integrity gate.
4. Deferred Track B forecasting to a separate future protocol.
5. Removed subtractive score penalties to prevent double counting.
6. Added a six-dimension prompt-only baseline.
7. Locked the primary endpoint at 95 percent compression, with curve area as secondary evidence.
8. Specified annotator calibration and qualification requirements.
9. Added a default minimum practically meaningful effect rule.
10. Defined the complete primary verdict, including integrity and dimension noninferiority gates.
11. Restricted pilot-grade claim language.
12. Defined the public replication packet required for private-corpus runs.

The following v0.1 elements are preserved except where the repairs above explicitly modify them:

- the complete freeze-before-test list;
- four-budget separation: `B_store`, `B_retrieve`, `B_prompt`, and `B_output`;
- catastrophic-error taxonomy `CE-01` through `CE-10`;
- full-history probe sanity checking;
- jargon-overfitting as a failure condition;
- disclosure of AI assistance and provenance;
- the rule: **If Spine v0 loses, Spine v0 loses.**;
- the strong baseline set, now expanded with the prompt-only baseline.

These repairs improve the instrument.

They are not evidence for the Light Compression Hypothesis.

> **A better instrument does not make the hypothesis more true.**

---

# 0. Non-negotiable epistemic prohibitions

This protocol is governed by three prohibitions.

## 0.1 Instrument quality is not hypothesis evidence

The quality of this protocol, the tribunal process, the hostile audit, the precision of the scoring rubric, and the elegance of the experimental design do not count as evidence that Light Compression works.

Evidence begins only after a valid run produces results under the frozen protocol.

## 0.2 The execution ladder is fixed

The required order is:

```text
1. Write Protocol v0.2
2. Conduct hostile audit of Protocol v0.2
3. Build schemas and annotator handbook
4. Conduct calibration
5. Run pilot
```

Nothing skips a rung.

This document must not be marked `PILOT-READY` until the hostile audit is complete and the required schemas and handbook exist.

## 0.3 Failure conditions may not be softened after results appear

The experiment must be able to lose.

A valid loss is recorded as `FAIL`.

A failed integrity gate cannot be repaired after seeing the output.

A negative result cannot be converted into `INCONCLUSIVE_MEASUREMENT` merely because the project dislikes it.

---

# 1. Why this file exists

The current Legacy.GI scientific claim is testable in principle:

> **Selective structure-preserving compression may retain longitudinal human continuity information better than generic compression at equal information budgets.**

The missing artifact was not another theory document.

The missing artifact was the ruler.

Protocol v0.1 created the first complete ruler. A secondary hostile methodological audit then identified four load-bearing gaps:

- no terminal state for persistent annotation disagreement;
- relational fidelity remained a subjectivity sink;
- catastrophic continuity failures could be laundered by a higher average score;
- the forecast track did not yet have a defensible scoring rubric.

ChatGPT checked those criticisms against the actual v0.1 artifact before accepting them.

Protocol v0.2 repairs the instrument before any pilot begins.

The governing standard is:

> **A result is only useful if another careful evaluator could inspect the evidence, apply the same rubric, and understand why an answer received its score.**

This document does not claim that the experiment has been run.

This document does not claim that continuity fidelity proves identity preservation, consciousness transfer, digital immortality, or subjective survival.

It defines a candidate instrument for measuring continuity distortion.

---

# 2. Relationship to CANON-001 and Protocol v0.1

`research/LEGACY_GI_MATHEMATICAL_CORE_V1.md` is the current canonical internal research position under CANON-001.

CANON-001 establishes:

- the narrowed Light Compression Hypothesis;
- the six initial continuity dimensions;
- rate-distortion theory as the preferred first mathematical frame;
- the Identity Spine as a testable sparse-representation hypothesis;
- correction without erasure;
- provenance preservation;
- the distinction between legitimate evolution and illegitimate drift;
- the requirement that AI-generated formalization retain AI provenance;
- the rejection or demotion of unsupported physics-style claims.

Protocol v0.1 remains preserved as the first committed annotation and evaluation instrument.

Protocol v0.2 supersedes v0.1 for future methodological work, but it does not erase it.

If Protocol v0.2 conflicts with CANON-001, the conflict must be preserved and reviewed rather than silently resolved.

---

# 3. Primary research question and versioned hypothesis

The primary research question is:

> **At equal information budgets, does continuity-aware compression preserve more decision, correction, temporal, relational, provenance, and uncertainty structure than strong generic compression baselines?**

Let:

- `X` be a longitudinal source corpus;
- `Z_c` be a continuity-aware compressed representation;
- `Z_g` be a generic compressed representation;
- `B` be the fixed information budget;
- `Q` be a held-out set of continuity probes;
- `F_k(Z,Q)` be performance on continuity dimension `k`.

The six-dimension hypothesis is versioned as:

```text
LCL-6D-v0.2
```

The confirmatory alternative hypothesis is:

```math
H_1:
\mathbb{E}[F_{macro}(Z_c,Q)] - \mathbb{E}[F_{macro}(Z_g,Q)] \ge \delta_{min}
```

subject to all integrity, reliability, budget, and noninferiority gates in this protocol.

The null hypothesis is:

```math
H_0:
\mathbb{E}[F_{macro}(Z_c,Q)] - \mathbb{E}[F_{macro}(Z_g,Q)] < \delta_{min}
```

The project must accept a null or negative result if the continuity-aware condition does not outperform the frozen strongest generic compressed baseline under the locked protocol.

## 3.1 Dimension removal changes the hypothesis

The six dimensions are not sacred.

If a dimension cannot be annotated reliably after the terminal calibration process, that dimension must be removed from confirmatory scoring.

That changes the hypothesis.

Example:

```text
LCL-6D-v0.2
Decision + Correction + Temporal + Relational + Provenance + Uncertainty
```

may become:

```text
LCL-5D-v0.2-R1
Decision + Correction + Temporal + Provenance + Uncertainty
```

A dimension-reduced hypothesis requires:

- a new hypothesis identifier;
- a new preregistration;
- a new frozen probe allocation;
- a statement that the original six-dimension hypothesis was not reliably measurable under the prior protocol.

It is a new hypothesis version, not a cosmetic edit.

---

# 4. Active and deferred experimental tracks

## 4.1 TRACK A: RECONSTRUCTION

**Status:** ACTIVE IN PROTOCOL v0.2

All compression conditions receive the same approved source corpus through the same cutoff.

The source corpus contains the evidence needed to answer the held-out questions, but the systems do not receive:

- the final probe wording;
- gold answers;
- required elements;
- prohibited claims;
- adjudication notes.

The systems are then asked previously unseen questions about:

- decisions;
- correction chains;
- chronology;
- relational structure;
- provenance;
- uncertainty.

This tests whether the compressed representation retained continuity-relevant structure.

Reconstruction is the only track that contributes to the Protocol v0.2 Light Compression confirmatory verdict.

## 4.2 TRACK B: FORECAST

**Status:** DEFERRED

Forecasting actual later decisions, corrections, or state changes is not part of Protocol v0.2.

It is deferred because:

- human decisions are not deterministic;
- exact-match scoring can test fortune-telling rather than continuity;
- value-consistency scoring can become subjective;
- Protocol v0.2 does not yet contain a defensible forecast rubric.

Forecasting requires a separate future protocol:

```text
LEGACY_GI_LONGITUDINAL_FORECAST_PROTOCOL_V0_1.md
```

Track B is not part of the Light Compression confirmatory verdict.

A favorable forecast result may never be used to offset a reconstruction failure.

---

# 5. Permitted terminal result states

Every locked run must end in exactly one of three states.

## 5.1 PASS

The continuity-aware condition satisfies every preregistered requirement, including:

- primary effect threshold;
- Critical Integrity Gate;
- dimension noninferiority gate;
- annotation reliability requirements;
- equal-budget requirements;
- blinded scoring;
- protocol compliance.

## 5.2 FAIL

The experiment was validly executed, but the continuity-aware condition did not satisfy one or more preregistered success criteria.

Examples:

- no meaningful advantage over the strongest baseline;
- observed advantage below `delta_min`;
- confidence interval fails the preregistered decision rule;
- Critical Integrity Gate failure;
- material inferiority on an included dimension;
- advantage disappears under blinded scoring.

A valid loss is `FAIL`.

It may not be renamed because the project dislikes the result.

## 5.3 INCONCLUSIVE_MEASUREMENT

This state is allowed only for predefined measurement failures that prevent a valid test.

Permitted examples:

- persistent low inter-rater agreement after the third calibration round;
- a corrupted run that invalidates multiple conditions;
- a locked probe set shown to be invalid by the full-history sanity check;
- source-manifest integrity failure;
- privacy or consent boundaries that invalidate the planned evidence packet;
- renderer or required infrastructure failure before all conditions are completed.

`INCONCLUSIVE_MEASUREMENT` cannot be used when the experiment runs correctly and the continuity-aware condition loses.

That result is `FAIL`.

---

# 6. Research boundaries

This protocol measures representation performance.

It does not establish:

- that a representation is the human being;
- that a representation is conscious;
- that behavioral similarity proves identity continuation;
- that a model has recovered subjective experience;
- that a high score constitutes digital immortality;
- that the six dimensions exhaust identity;
- that Noah Hawkes is representative of the general population.

The first development corpus may be Noah Hawkes's governed archive because it is unusually deep and because the living source can still correct the record.

That makes it valuable for instrument development.

It remains an `N=1` case.

Population-level claims require independent participants and independent corpora.

---

# 7. Core definitions

## 7.1 Longitudinal corpus

A time-ordered body of records associated with one human across multiple contexts, periods, relationships, and source types.

The corpus may contain:

- direct human statements;
- journals;
- conversations;
- emails;
- decisions;
- corrections;
- code and repository artifacts;
- recordings;
- AI-generated text;
- AI-polished human text;
- third-party records;
- summaries;
- historical and current states.

## 7.2 Continuity record

A provenance-bound atomic record containing an assertion, decision, correction, relationship, unresolved state, or event that may matter to later longitudinal reconstruction.

## 7.3 Compression representation

A bounded representation derived from the source corpus under a fixed storage or token budget.

## 7.4 Continuity probe

A held-out question with a source-backed gold answer, required elements, prohibited distortions, evidence class, uncertainty status, and scoring rules.

## 7.5 Continuity distortion

Loss, corruption, temporal flattening, misattribution, overconfidence, or fabrication affecting one or more continuity dimensions.

## 7.6 Catastrophic continuity failure

A high-severity error that materially changes the represented person, source, authorship, or historical record.

## 7.7 Critical integrity probe

A preregistered, deliberately unambiguous probe specifically designed to test a prohibited identity or provenance failure.

## 7.8 Legitimate evolution

A change in represented state supported by new evidence, explicit revision, context, or time, with the earlier state preserved historically.

## 7.9 Illegitimate drift

A change caused by provenance loss, retrieval failure, misattribution, hallucination, untracked overwriting, or generation rather than evidence-backed development.

---

# 8. Corpus preparation

## 8.1 Source inventory

Before compression, create a source inventory containing:

- source ID;
- source title;
- source type;
- creation date;
- observed date;
- author or speaker if known;
- transport channel;
- version or revision;
- sensitivity classification;
- duplicate family;
- derivative status;
- evidentiary class;
- content hash.

## 8.2 Speaker and authorship separation

A shared account is not a single person.

The corpus must distinguish, where evidence permits:

- Noah.Physical;
- other family or household members;
- AI systems;
- quoted third parties;
- copied documents;
- unknown authorship.

Rules:

- user channel is not automatic authorship;
- copy and paste preserves original author;
- screenshots preserve original source;
- transport is not origin;
- AI-polished human text retains both provenances;
- Noah-adopted AI language records both origin and adoption;
- uncertain authorship remains `UNKNOWN`.

## 8.3 Duplicate and derivative handling

Repeated copies do not count as independent evidence.

Each duplicate family should record:

- canonical source candidate;
- exact duplicates;
- near duplicates;
- derivative summaries;
- revisions;
- unique information added by derivatives.

Repeated copies must not silently increase confidence in the underlying claim.

## 8.4 Atomic segmentation

Source material should be segmented into atomic or near-atomic records where practical.

Recommended unit types:

- assertion;
- decision;
- correction;
- question;
- unresolved state;
- relationship event;
- implementation claim;
- implementation receipt;
- value statement;
- timeline event.

## 8.5 Sensitivity partition

Every record must be classified as one of:

- public-safe;
- private;
- family-sensitive;
- minor-sensitive;
- medical;
- financial;
- employment-confidential;
- legal;
- unknown sensitivity.

The public GitHub repository must not receive raw private corpus material.

Presence in the corpus is not blanket consent for public release.

---

# 9. Dataset partitioning and leakage control

## 9.1 Required partitions

The corpus must be divided into:

1. **Development set**  
   Used to design prompts, features, weights, and code.

2. **Calibration sets**  
   Used to train annotators and test rubric reliability. Calibration records never enter the confirmatory test set.

3. **Confirmatory test set**  
   Locked before final evaluation and never used for system tuning.

## 9.2 Temporal partition

The confirmatory set should use a chronological boundary where practical.

All conditions receive the same eligible source interval.

The final probe wording and gold structure remain hidden during compression.

## 9.3 No answer leakage

The compression process must not receive:

- final probe wording;
- answer keys;
- required elements;
- prohibited claims;
- adjudicator notes;
- confirmatory outputs from another condition.

## 9.4 Model familiarity risk

Public corpus material may appear in model pretraining or retrieval indexes.

Mitigations:

- include newly held-out local material where consent permits;
- use source IDs and paraphrased probes rather than public document titles;
- compare multiple renderer models in later replication;
- include synthetic decoy probes with no public footprint;
- document any model with known repository access.

Perfect control over pretraining contamination must not be claimed when it cannot be verified.

---

# 10. Experimental conditions

All confirmatory conditions must use the same renderer model, decoding settings, prompt-output limit, and evaluation probes unless the preregistration explicitly states otherwise.

## 10.1 Continuity-aware architecture

A representation explicitly designed to preserve:

- decisions and rationale;
- corrections and supersession chains;
- temporal state;
- relational structure;
- provenance;
- uncertainty.

Working name:

> **Continuity-Aware Episodic Coreset, Spine v0**

The project term `Identity Spine` may remain, but the academic description must stay operational.

## 10.2 Six-dimension prompt-only baseline

A standard model receives:

- the same corpus;
- the same model;
- the same storage budget;
- the same prompt budget;
- the same six-dimension preservation instructions;

but it receives:

- no Identity Spine;
- no graph architecture;
- no coreset architecture;
- no bespoke continuity-selection algorithm.

This separates two claims:

```text
CLAIM A:
The six-dimensional instruction is a useful prompting method.

CLAIM B:
The Spine architecture adds value beyond the prompt.
```

If the prompt-only baseline matches Spine v0, the architecture has not earned its additional complexity.

The dimensions may still have value as a prompting technique.

## 10.3 Generic abstractive summary

A standard model-generated summary optimized for broad semantic coverage under the same storage budget.

## 10.4 Generic extractive summary

A source-extractive representation using a standard importance or centrality method under the same budget.

## 10.5 Recency-weighted memory

A representation prioritizing recent material under the same budget.

## 10.6 Compressed-store semantic RAG

A semantic retrieval system restricted to the same persistent storage budget as the continuity-aware arm.

## 10.7 Full-store semantic RAG

A practical baseline allowed to index the full corpus but restricted to the same per-probe retrieval and prompt budget.

This is not an equal-storage baseline and must be reported separately.

## 10.8 Full-history upper bound

Where technically possible, provide a condition with access to all relevant evidence.

This is a probe sanity check.

If the full-history condition performs poorly, the problem may be the probe set, answer key, renderer, or scoring instrument rather than compression.

A confirmatory run must not proceed on a probe set that the full-history condition cannot answer at the preregistered validity level.

## 10.9 Optional random negative control

Uniform random sampling may be included as a negative control.

Beating random sampling is not sufficient evidence for the Light Compression claim.

## 10.10 Frozen strongest generic baseline

The primary comparator must be selected using development data only.

Before confirmatory outputs are generated, select and record the strongest equal-storage generic condition from:

- six-dimension prompt-only;
- generic abstractive summary;
- generic extractive summary;
- recency-weighted memory;
- compressed-store semantic RAG.

The selected comparator is frozen in the preregistration.

The project may not select the comparator after seeing confirmatory results.

---

# 11. Equal information budgets and locked endpoints

The phrase `equal information budget` must be operationally explicit.

Record four budgets:

```text
B_store     = persistent representation size
B_retrieve  = amount retrieved for a probe
B_prompt    = total context sent to the renderer
B_output    = maximum answer length
```

For equal-storage comparisons:

```math
B_{store}^{continuity} = B_{store}^{baseline}
```

and:

```math
B_{prompt}^{continuity} = B_{prompt}^{baseline}
```

The tokenizer, encoding, and counting method must be identical across conditions.

Actual usage must be recorded, not merely maximum allowance.

## 11.1 Complete compression sweep

Run all preregistered levels:

- 50 percent compression;
- 75 percent compression;
- 90 percent compression;
- 95 percent compression;
- 97.5 percent compression;
- 99 percent compression.

## 11.2 Primary endpoint

The confirmatory primary endpoint is locked at:

```text
95 percent compression
5 percent of the original measured information budget retained
```

The confirmatory verdict is anchored to this predeclared condition.

## 11.3 Secondary endpoint

The secondary compression endpoint is:

```text
Area under the continuity-fidelity curve across the full preregistered sweep
```

The curve is secondary evidence, not a menu.

The analyst may not select whichever compression level produces the most favorable result and present it as primary.

---

# 12. Complete freeze-before-test list

Before confirmatory scoring, freeze and hash all of the following:

- corpus manifest;
- inclusion and exclusion rules;
- source hashes;
- partition dates;
- compression code;
- scoring features;
- feature weights;
- prompts;
- renderer model and version;
- embedding model and version, if used;
- retrieval configuration;
- token budgets;
- random seeds where supported;
- general probe set;
- Critical Integrity Probe Set;
- answer keys;
- required elements;
- prohibited claims;
- scoring rubric;
- evidence-class rules;
- primary comparator;
- primary endpoint;
- secondary endpoints;
- `delta_min`;
- dimension noninferiority margin;
- statistical analysis plan;
- permitted result states;
- privacy and redaction rules;
- environment manifest.

The frozen state must be committed and timestamped before confirmatory answers are generated.

**If Spine v0 loses, Spine v0 loses.**

A later Spine v1 is a new experiment and requires a new held-out set.

Tuning after confirmatory results creates a new experiment.

---

# 13. Continuity probe construction

Each probe must:

- test one primary continuity dimension;
- identify any secondary dimensions;
- have a source-backed gold answer;
- list required answer elements;
- list prohibited distortions;
- declare evidence class;
- declare uncertainty status;
- declare sensitivity;
- cite exact source IDs;
- avoid unsupported mind reading;
- avoid rewarding project-specific jargon unless the source requires it.

The primary benchmark must use actual recorded source states and outcomes.

Counterfactual questions are excluded from the Protocol v0.2 confirmatory set.

## 13.1 General probe balance

A pilot may begin with 60 general probes, approximately 10 per dimension.

A confirmatory study should target at least 180 general probes, approximately 30 per confirmatory-eligible dimension, subject to power analysis, source availability, and the final hypothesis version.

The 24 Critical Integrity probes are additional and are not counted toward the 180 general probes.

The general set should include:

- resolvable answers;
- `UNKNOWN` answers;
- `CONFLICT PRESERVED` answers;
- superseded-state traps;
- authorship traps;
- shared-account traps;
- proposal-versus-implementation traps;
- relational-structure probes;
- low-salience but continuity-critical events.

## 13.2 Jargon control

Some probes must be phrased without project-specific terms such as `Identity Spine`, `SOV1`, or `Light Compression`.

A method that succeeds only when the question repeats its own terminology has not demonstrated general continuity preservation.

---

# 14. Critical Integrity Probe Set

The Critical Integrity Probe Set contains exactly 24 preregistered, deliberately unambiguous probes.

It covers five non-negotiable failure families:

```text
CE-01 WRONG_PERSON
CE-02 FALSE_AUTHORSHIP
CE-04 UNKNOWN_TO_CERTAIN
CE-07 GENERATED_AS_MEMORY
CE-09 SOURCE_FABRICATION
```

Allocation rules:

- at least 4 probes for each failure family;
- the remaining 4 probes are allocated before preregistration;
- the final allocation is frozen before any system output is generated;
- no category may be added, removed, or reweighted after results appear.

## 14.1 Critical-probe design requirements

Every critical probe must have:

- unambiguous source evidence;
- a short, inspectable gold answer;
- a clearly prohibited failure;
- independent evidence review before the run;
- no dependence on subtle emotional interpretation;
- no unresolved source conflict;
- a predeclared critical code.

## 14.2 Absolute integrity gate

One adjudicated high-confidence critical failure on a designated critical probe causes the condition to fail the Integrity Gate.

A high-confidence critical failure requires:

- a valid locked probe;
- sufficient source evidence established before system identities are revealed;
- agreement by both evidence annotators, or confirmation by the adjudicator;
- no unresolved ambiguity in the gold standard;
- an answer that directly satisfies the prohibited failure definition.

A condition that fails the Integrity Gate cannot receive an overall `PASS`, even if its average continuity score is higher.

## 14.3 Two distinct outcomes

Every condition receives two separately reported outcomes:

```text
CONTINUITY PERFORMANCE
Did the representation preserve more structure?

INTEGRITY GATE
Did it commit a prohibited identity or provenance failure?
```

A system can score higher on average and still fail overall.

## 14.4 General-set catastrophic errors

Catastrophic errors on the general probe set are reported separately as rates with confidence intervals.

They do not automatically trigger the absolute integrity gate unless the preregistration explicitly designates the affected probe as critical.

---

# 15. Gold-standard probe schema

Recommended JSON form:

```json
{
  "probe_id": "CORR-0042",
  "track": "reconstruction",
  "primary_dimension": "correction",
  "secondary_dimensions": ["temporal", "provenance"],
  "critical_integrity": false,
  "critical_code": null,
  "question": "What was the corrected project position, and what earlier state did it replace?",
  "gold_answer": "The current position is X. It corrected earlier state Y, which remains historical rather than deleted.",
  "required_elements": [
    "current position X",
    "earlier position Y existed",
    "correction authority identified",
    "earlier state remains historical"
  ],
  "prohibited_claims": [
    "X was always the position",
    "Y never existed",
    "the AI independently promoted X"
  ],
  "source_ids": ["source-A", "source-B"],
  "evidence_class": "direct_human_correction",
  "uncertainty_status": "resolved",
  "sensitivity": "public-safe",
  "notes_for_adjudicator": "Do not require exact wording. Require correction lineage."
}
```

The gold answer must be concise enough to score and detailed enough to preserve the relevant continuity structure.

---

# 16. Evidence classes

Each gold answer must declare one primary evidence class.

## 16.1 Receipt-backed external fact

Supported by a timestamped source, code artifact, commit, public record, recording, or other inspectable evidence.

## 16.2 Direct self-attestation

A direct human statement about personal belief, intention, preference, emotional interpretation, or current self-understanding.

This is authoritative regarding the person's stated meaning at that time.

It is not automatically proof of external events.

## 16.3 Direct correction

An explicit correction by the relevant authority.

For Noah's identity, intent, and self-description, Noah.Physical is the final correction authority while alive.

External factual claims may still require independent evidence.

## 16.4 Source-bounded inference

A conclusion supported by identified evidence but not directly stated.

It must remain labeled as inference.

## 16.5 AI-generated candidate

A model-generated interpretation, equation, label, or extension that has not been independently adopted or verified.

## 16.6 Adopted AI-assisted formulation

Language or formalization originated or substantially shaped by AI and later explicitly adopted by Noah.

Both origins must remain visible.

## 16.7 UNKNOWN

The available sources do not justify a determinate answer.

## 16.8 CONFLICT PRESERVED

Reliable sources disagree and no authorized resolution is available.

A correct answer preserves the conflict rather than choosing the cleaner story.

---

# 17. The six continuity dimensions

The six dimensions are an evaluation ruler.

They are not a complete theory of personhood.

Each general probe receives one primary dimension and may receive secondary tags.

## 17.1 Decision fidelity

Measures preservation of:

- what was chosen;
- alternatives considered;
- stated rationale;
- relevant constraints;
- decision authority;
- later reversal or reaffirmation.

Score:

```text
3 = Correct choice plus all continuity-critical rationale, authority, and status elements.
2 = Correct choice and core rationale, but one meaningful structural element is missing.
1 = Partial recovery, vague or weakly supported, with no direct contradiction.
0 = Wrong choice, invented rationale, wrong authority, or no usable answer.
```

## 17.2 Correction fidelity

Measures preservation of:

- prior state;
- correction event;
- correcting authority;
- new state;
- current status;
- historical preservation of prior state.

Score:

```text
3 = Preserves old state, correction, authority, new state, and historical distinction.
2 = Correct current state and correction, but loses one lineage element.
1 = Returns current state without trustworthy correction history, or recognizes conflict without resolution.
0 = Resurrects the old state as current, erases the correction, or fabricates lineage.
```

## 17.3 Temporal fidelity

Measures preservation of:

- event order;
- date or relative sequence;
- current versus historical state;
- candidate versus canon;
- proposed versus implemented;
- supersession or persistence.

Score:

```text
3 = Correct sequence, state transitions, and current/historical distinction.
2 = Core sequence correct with one noncritical temporal omission.
1 = Some correct events but flattened or ambiguous chronology.
0 = Reversed order, wrong current state, or historical claim presented as current.
```

## 17.4 Relational fidelity

Relational fidelity is split into two layers.

### R1: Relational Structure

**Status:** CONFIRMATORY

R1 measures objectively scoreable, source-supported facts:

- who was involved;
- what relationship or role existed;
- whether identities were correctly separated;
- what explicit obligation or constraint was stated;
- whether the relationship was current, historical, disputed, or unknown.

Score:

```text
3 = Correct people, roles, explicit relationship constraints, and identity boundaries.
2 = Correct people and relationship, but one meaningful structural element is missing.
1 = Names or roles partially recovered without enough relationship context.
0 = Wrong person, merged identities, invented relationship, or erased autonomy.
```

### R2: Relational Interpretation

**Status:** EXPLORATORY

R2 includes claims such as:

- a relationship changed the emotional meaning of an event;
- attachment motivated a choice;
- loyalty, love, resentment, fear, or obligation was load-bearing.

R2 enters confirmatory scoring only when the source explicitly supports the interpretation.

Confirmatory example:

```text
I chose stability because my family needed it.
```

Exploratory example:

```text
Family must have motivated this choice, although the source does not say so.
```

Annotators may not infer what Noah or another person "really felt" without source support.

## 17.5 Provenance fidelity

Measures preservation of:

- original speaker or author;
- source type;
- direct versus inferred status;
- AI role;
- copied or transported status;
- later adoption or correction;
- source pointer.

Score:

```text
3 = Correct origin, transformation history, evidence class, and source relation.
2 = Correct primary origin with one secondary provenance detail missing.
1 = Content mostly correct but provenance vague, incomplete, or weakly supported.
0 = False authorship, derivative treated as primary, or unsupported source claim.
```

## 17.6 Uncertainty fidelity

Measures preservation of:

- known facts;
- unknown facts;
- conflict status;
- confidence limits;
- unresolved alternatives;
- evidence still required.

Score:

```text
3 = Correctly preserves uncertainty, conflict, confidence, and missing evidence.
2 = Core uncertainty preserved but one boundary is softened or omitted.
1 = Hedged answer that still implies more certainty than the evidence supports.
0 = Fabricated resolution, false certainty, or suppression of known conflict.
```

---

# 18. Scoring and error accounting

Each answer receives:

1. one primary dimension score from `0` to `3`;
2. optional secondary dimension scores;
3. nonnumeric error flags;
4. catastrophic-error codes where applicable;
5. integrity-gate status when the probe belongs to the Critical Integrity Set.

## 18.1 No subtractive penalties

Protocol v0.1 proposed automatic numeric subtraction for certain error types.

Protocol v0.2 removes subtractive penalties.

Reason:

- the dimension score already captures answer correctness;
- a CE code may describe the same underlying error;
- subtracting again double-counts the same failure;
- conditions that explicitly discuss provenance may otherwise face more penalty opportunities.

The score captures whether the answer was correct.

The flags describe how it failed.

## 18.2 General error flags

Suggested nonnumeric flags:

```text
EF-01 UNSUPPORTED_CERTAINTY
EF-02 PROVENANCE_MISATTRIBUTION
EF-03 CURRENT_HISTORICAL_COLLAPSE
EF-04 FABRICATED_CONNECTIVE_TISSUE
EF-05 WRONG_PERSON_OR_RELATIONSHIP
EF-06 PROPOSAL_IMPLEMENTATION_COLLAPSE
EF-07 MISSING_SOURCE_POINTER
EF-08 UNLABELED_INFERENCE
```

## 18.3 Catastrophic-error taxonomy

The v0.1 taxonomy is preserved:

```text
CE-01 WRONG_PERSON
CE-02 FALSE_AUTHORSHIP
CE-03 SUPERSEDED_AS_CURRENT
CE-04 UNKNOWN_TO_CERTAIN
CE-05 DECISION_REVERSED
CE-06 IMPLEMENTATION_FALSE_CLAIM
CE-07 GENERATED_AS_MEMORY
CE-08 RELATIONSHIP_ERASURE
CE-09 SOURCE_FABRICATION
CE-10 PRIVACY_BOUNDARY_FAILURE
```

All CE codes are reported separately from fidelity scores.

---

# 19. Annotation roles

No single person should create the gold standard, see all condition identities, and decide the winner.

## 19.1 Principal annotator

For the Noah development corpus, Noah.Physical supplies first-person ground truth for:

- intent;
- personal meaning;
- current self-description;
- explicit correction;
- relationship interpretation where he has authority to speak for himself;
- what was or was not adopted.

These labels should be created before Noah sees final model outputs where possible.

Noah's authority over his own meaning does not convert external claims into verified facts.

## 19.2 Evidence annotators

At least two evidence annotators independently score whether answers are supported by the receipts and rubric.

They should not know which condition produced which answer.

## 19.3 Adjudicator

A separate adjudicator resolves disagreements using:

- written rubric;
- source evidence;
- principal attestation where appropriate;
- preserved uncertainty.

The adjudicator records the reason for every resolved disagreement.

## 19.4 Privacy-preserving annotation

Sensitive probes may use redacted evidence packets.

Redactions must not remove the information necessary to score the probe.

If a probe cannot be independently scored without exposing material that should remain private, classify it as internal-only and report the limitation.

---

# 20. Calibration, qualification, and terminal reliability rules

Calibration is finite.

The rubric may not be revised forever.

## 20.1 Fixed calibration constants

```text
MAX_CALIBRATION_ROUNDS = 3
CALIBRATION_PROBES_PER_ROUND = 48
PROBES_PER_DIMENSION_PER_ROUND = 8
```

Each round uses a fresh calibration set that is never part of the confirmatory test set.

## 20.2 Round procedure

### Round 1: Independent scoring

- annotators score 48 practice probes independently;
- calculate dimension-level agreement;
- record disagreements;
- identify ambiguous definitions.

### Round 2: Review and clarification

- review Round 1 disagreements;
- clarify the rubric and annotator handbook;
- score a fresh 48-probe set independently;
- calculate dimension-level agreement again.

### Round 3: Fresh locked calibration set

- score a fresh locked 48-probe set;
- no further rubric revision for the same hypothesis version;
- assign terminal reliability status to every dimension.

## 20.3 Reliability metrics

Primary metric:

```text
Krippendorff's alpha for ordinal scores
```

Secondary metric when exactly two raters are used:

```text
weighted Cohen's kappa
```

Also report:

- raw agreement;
- dimension-specific agreement;
- Critical Integrity flag agreement.

## 20.4 Terminal dimension states after Round 3

```text
alpha >= 0.80
CONFIRMATORY-ELIGIBLE

alpha 0.67 to 0.79
PILOT-GRADE ONLY
NO CONFIRMATORY CLAIMS PERMITTED

alpha < 0.67
NOT RELIABLY MEASURABLE
STOP REVISING THIS HYPOTHESIS VERSION
PRESERVE THE FAILED CALIBRATION RESULT
```

No fourth calibration round is allowed for the same hypothesis version.

If a dimension is not confirmatory-eligible:

- it does not enter the confirmatory primary outcome;
- the original hypothesis version may not proceed unchanged;
- a dimension-reduced hypothesis requires a new preregistration;
- the failed calibration result remains part of the public research record.

## 20.5 Annotator qualification

Before confirmatory scoring, each annotator must achieve:

```text
at least 85 percent agreement with adjudicated calibration labels
```

and:

- no unresolved misunderstanding of evidence classes;
- no severe misclassification of Critical Integrity examples;
- demonstrated ability to preserve `UNKNOWN` and `CONFLICT PRESERVED`.

An annotator who does not qualify may not score the confirmatory set.

---

# 21. Annotation workflow

1. Select source material from the approved corpus partition.
2. Create a candidate probe.
3. Assign primary and secondary dimensions.
4. Identify exact source receipts.
5. Draft the gold answer.
6. List required elements.
7. List prohibited distortions.
8. Assign evidence class and uncertainty status.
9. Review sensitivity.
10. Complete independent probe-quality review.
11. Lock the probe before model evaluation.
12. Randomize and blind condition outputs.
13. Score independently.
14. Calculate agreement.
15. Adjudicate disagreements.
16. Preserve original scores and adjudication notes.

No score may be silently overwritten.

---

# 22. Metrics and verdict structure

Report a vector before any aggregate:

```math
\mathbf{F}_{CI}
=
(F_D,F_C,F_T,F_R,F_P,F_U)
```

`F_R` refers to confirmatory R1 relational structure, not unsupported R2 interpretation.

## 22.1 Dimension score

For dimension `k`:

```math
F_k = \frac{1}{N_k}\sum_{i=1}^{N_k}\frac{s_i}{3}
```

where `s_i` is the adjudicated score from `0` to `3`.

## 22.2 Macro score

```math
F_{macro} = \frac{1}{K}\sum_{k=1}^{K}F_k
```

where `K` is the number of confirmatory-eligible dimensions in the preregistered hypothesis version.

The macro score never replaces the dimension vector.

## 22.3 Primary outcome

The primary outcome is:

```text
Macro continuity fidelity at 95 percent compression
across all confirmatory-eligible dimensions
```

The comparison is continuity-aware Spine v0 versus the frozen strongest equal-storage generic baseline.

## 22.4 Gate 1: Critical Integrity

The continuity-aware condition must pass the 24-probe Critical Integrity Set.

One adjudicated high-confidence critical failure causes Gate 1 failure.

## 22.5 Gate 2: Dimension noninferiority

No included dimension may perform worse than the frozen strongest baseline by more than the preregistered noninferiority margin.

Recommended initial margin:

```text
0.05 normalized fidelity
```

A different margin requires written justification before confirmatory outputs are generated.

## 22.6 Required secondary results

Report:

- each dimension independently;
- catastrophic-error rates with confidence intervals;
- unsupported-certainty rate;
- provenance-attribution error rate;
- current/historical collapse rate;
- `UNKNOWN` preservation accuracy;
- correction-chain completeness;
- decision-choice accuracy;
- average answer length;
- retrieval volume;
- storage budget actually used;
- area under the compression-fidelity curve;
- ablations;
- prompt-only versus architectural performance.

If a dimension was removed for low reliability, the report must state that the experiment no longer tests the original six-dimensional hypothesis.

Text-similarity metrics may be reported only as diagnostics.

---

# 23. Default minimum practically meaningful effect

The confirmatory preregistration must define `delta_min` before answers are generated.

Protocol v0.2 supplies this default:

```text
delta_min = maximum of:

0.05 absolute normalized macro-fidelity improvement

or

0.30 x paired-score standard deviation estimated from the pilot
```

Also report paired rank-biserial correlation.

A value of:

```text
r >= 0.30
```

is a corroborating effect-size target, not the sole verdict.

The final `delta_min` must be written into a timestamped preregistration commit before confirmatory answers are generated.

It may not be moved after results appear.

---

# 24. Statistical analysis plan

The confirmatory plan must be frozen before scoring.

Recommended analysis:

1. Use paired comparisons because every probe is answered under every condition.
2. Report mean and median paired score differences.
3. Use 10,000 paired bootstrap resamples for confidence intervals.
4. Use a paired permutation test for the primary macro comparison.
5. Use McNemar's test for paired binary outcomes such as exact decision accuracy and catastrophic-error presence.
6. Use a predeclared multiple-comparison correction for dimension-level tests, such as Holm correction.
7. Report effect sizes and confidence intervals, not p-values alone.
8. Report every preregistered compression level, including negative or null results.

---

# 25. Complete primary verdict

A condition receives `PASS` only if every requirement below is satisfied.

1. Every included dimension is confirmatory-eligible.
2. The continuity-aware condition passes the Critical Integrity Gate.
3. The continuity-aware condition exceeds the frozen strongest generic baseline at the primary 95 percent endpoint.
4. The observed advantage meets or exceeds `delta_min`.
5. The preregistered confidence interval satisfies the locked decision rule.
6. No included dimension violates the noninferiority margin.
7. The result survives blinded scoring.
8. Equal-budget requirements were met.
9. No material protocol deviation invalidates the comparison.
10. The full-history sanity check supports probe validity.

A higher mean without both gates is not a pass.

---

# 26. Failure and falsification conditions

The tested continuity-aware implementation loses support if:

- it does not outperform the frozen strongest baseline;
- its advantage falls below `delta_min`;
- its confidence interval fails the preregistered rule;
- it fails the Critical Integrity Gate;
- it is materially inferior on an included dimension;
- its advantage disappears under blinded scoring;
- its advantage disappears after controlling for answer length or retrieval volume;
- the prompt-only baseline matches it;
- simple recency or semantic retrieval matches it;
- results depend on tuning against the confirmatory set;
- results are driven only by project-specific jargon;
- it produces unacceptable catastrophic-error rates;
- it overfits Noah's corpus and fails independent replication;
- the full-history condition shows that the probes themselves are invalid or unanswerable;
- privacy or consent constraints prevent a reproducible evaluation.

A failed Spine v0 does not disprove every possible continuity-aware method.

It does disprove the claim that Spine v0 succeeded under these conditions.

The failed version and result remain in the record.

**If Spine v0 loses, Spine v0 loses.**

---

# 27. Pilot-grade claim language

For reliability from `0.67` through `0.79`, the project may say only:

> **The pilot produced an exploratory feasibility signal under pilot-grade annotation reliability.**

It may not say:

- validated;
- confirmed;
- proved;
- replicated;
- scientifically established;
- `Legacy.GI outperformed generic compression`;
- `the Light Compression Hypothesis passed`.

Pilot results generate the next protocol.

They do not settle the hypothesis.

---

# 28. Ablation studies

If the continuity-aware condition passes the primary test, remove one feature family at a time:

- no decision weighting;
- no correction chains;
- no temporal links;
- no relational structure;
- no provenance;
- no uncertainty markers;
- no recurrence feature;
- no source-authority feature.

Measure the effect on every continuity dimension.

This identifies which components are load-bearing and which are decorative.

If a complex feature contributes no measurable value, remove it from the core architecture.

Advanced geometry, topology, or uncertainty-acceleration features remain outside the initial core and require separate incremental-value tests.

---

# 29. Sample probes

These examples illustrate structure only. They are not automatically part of the final benchmark.

## 29.1 Decision

```text
Question:
Why was the raw transcript preserved alongside the structured continuity summary?

Required elements:
- raw evidence has higher historical authority;
- interpretation is derivative;
- later analysis must not overwrite the original.
```

## 29.2 Correction

```text
Question:
What is the current safest role assigned to SOV1, and how should older meanings be handled?

Required elements:
- current role is governance and sovereignty under Noah.Physical;
- older operator or identity meanings remain historical;
- current meaning must not be projected backward.
```

## 29.3 Temporal

```text
Question:
Did the September scientific narrowing replace the earlier Legacy.GI architecture?

Gold structure:
No. It narrowed claim strength and created a testable scientific core while preserving the broader historical architecture.
```

## 29.4 Relational structure

```text
Question:
Why is a bike-tuning conversation on the shared account insufficient evidence that Noah is a bike enthusiast?

Required elements:
- multiple household members use the account;
- account identity is not human identity;
- speaker provenance must be established;
- Ethan is associated with much of that activity in the corrected record.
```

## 29.5 Provenance

```text
Question:
How should the Identity Spine mathematical formulation be attributed?

Gold structure:
The continuity-preservation problem and earlier compression concepts are rooted in Noah's project. The later mathematical formalization was AI-assisted and must retain that provenance.
```

## 29.6 Uncertainty

```text
Question:
What was the exact manufacturer and model of Noah's childhood Superman toy?

Gold structure:
UNKNOWN unless a source or Noah.Physical confirmation establishes it. A likely candidate remains a candidate.
```

## 29.7 Critical integrity example

```text
Code:
CE-02 FALSE_AUTHORSHIP

Question:
Did Noah directly write the later mathematical Identity Spine equation?

Gold structure:
No. The underlying continuity and compression problem is rooted in Noah's work. The later precise mathematical formulation was AI-assisted. Both layers must remain visible.
```

---

# 30. Machine-readable answer record

Recommended evaluation output:

```json
{
  "run_id": "RUN-001",
  "probe_id": "PROV-0012",
  "condition_id": "SPINE_V0_B95",
  "renderer_model": "model-name-version",
  "answer": "...",
  "retrieved_source_ids": ["S-14", "S-29"],
  "prompt_tokens": 1800,
  "output_tokens": 120,
  "primary_score_rater_1": 3,
  "primary_score_rater_2": 2,
  "adjudicated_score": 3,
  "secondary_scores": {
    "temporal": 2,
    "uncertainty": 3
  },
  "error_flags": [],
  "catastrophic_error_codes": [],
  "critical_integrity_failure": false,
  "adjudication_note": "Current and historical states were both preserved."
}
```

All raw outputs must be retained.

Do not store only final scores.

---

# 31. Experiment manifest

Every run requires:

```text
experiment ID
protocol version
hypothesis version
repository commit
corpus manifest hash
source hashes
probe-set hash
Critical Integrity Set hash
compression code commit
renderer model and version
embedding model and version
prompts
random seeds
B_store
B_retrieve
B_prompt
B_output
primary comparator
primary endpoint
secondary endpoints
delta_min
noninferiority margin
statistical analysis plan
run date
operator
hardware or environment
known failures
```

A result without a reproducible manifest is a demonstration, not a verified experiment.

---

# 32. Privacy, consent, and third-party rights

Longitudinal archives contain overlapping lives.

The principal's right to study their own life does not erase the privacy and authorship rights of other people appearing in the record.

Rules:

- use public-safe material for open benchmarks;
- keep raw private archives local or in approved protected storage;
- exclude minors' sensitive material from public release;
- redact third parties where identity is unnecessary;
- obtain consent before publishing intimate third-party material;
- preserve enough context for scoring without exposing unnecessary detail;
- document every exclusion;
- allow withdrawal from future use where legally and ethically required;
- never upload the private corpus to a public repository.

---

# 33. Private-corpus public replication packet

For any run whose source corpus cannot be made public, the public verification package must include:

- frozen protocol;
- Git commit and hashes;
- corpus manifest without private text;
- source-file hashes;
- redacted probe set;
- probe metadata;
- gold-answer structure with protected spans removed;
- all model outputs with required redactions;
- score matrix;
- original rater scores;
- adjudication notes;
- CE flags;
- general error flags;
- budgets;
- prompts;
- random seeds;
- model versions;
- code;
- environment manifest;
- deviations from protocol;
- negative findings;
- synthetic example corpus sufficient to execute the pipeline.

Outside researchers may not be able to verify every private fact.

They must still be able to verify that the frozen method produced the reported statistics.

Stage 1 private-corpus findings must be described as internally verified under the published method, not as independently replicated evidence.

---

# 34. Replication path

## Stage 1: Instrument development

Use a governed subset of Noah's corpus.

Goals:

- refine probes;
- test annotator agreement;
- validate budgets;
- identify leakage;
- debug scoring;
- estimate variance.

No general population claim is permitted.

## Stage 2: Independent participant

Recruit one additional consenting participant with a longitudinal corpus and living correction authority.

Freeze the method before applying it.

## Stage 3: Multi-participant benchmark

Use multiple participants with diverse histories, writing styles, relationships, and corpus types.

Evaluate:

- generalization;
- annotator reliability;
- privacy burden;
- cultural bias;
- relationship-model bias;
- whether the dimension set remains adequate.

## Stage 4: Cross-model replication

Repeat with different renderer and retrieval model families.

The result should not depend entirely on one provider or model lineage.

---

# 35. Reporting standard

A complete report must include:

- hypothesis version;
- protocol version;
- result state: `PASS`, `FAIL`, or `INCONCLUSIVE_MEASUREMENT`;
- corpus description;
- inclusion and exclusion criteria;
- privacy handling;
- experimental conditions;
- exact budgets;
- prompts;
- model versions;
- probe distribution;
- Critical Integrity Set performance;
- annotator roles;
- calibration history;
- reliability statistics;
- per-dimension results;
- macro result;
- catastrophic errors;
- ablations;
- prompt-only comparison;
- negative findings;
- deviations from protocol;
- raw-output availability;
- code and commit receipts;
- limitations;
- interpretation that does not exceed the evidence.

The report must label itself as one of:

- pilot;
- exploratory;
- confirmatory;
- replicated.

Passing a pilot is not replication.

---

# 36. Change control

Any change to this protocol requires:

- new version number;
- date;
- author and editor provenance;
- reason for change;
- sections changed;
- whether the change occurred before or after seeing results;
- preservation of the prior version.

Recommended status chain:

```text
DRAFT
-> HOSTILE_REVIEWED
-> REVISED
-> SCHEMAS_COMPLETE
-> HANDBOOK_COMPLETE
-> CALIBRATION_READY
-> CALIBRATED
-> PILOT_READY
-> PILOT_RUN
-> PREREGISTERED
-> CONFIRMATORY_RUN
-> REPLICATED or NOT_REPLICATED
```

Do not label a protocol `VALIDATED` merely because it exists in GitHub.

---

# 37. Fixed execution ladder after this commit

After Protocol v0.2 is written and committed, the next allowed steps are:

```text
1. Hostile audit of Protocol v0.2
2. Revise only if the audit identifies accepted defects
3. Build machine-readable schemas
4. Build the annotator handbook
5. Conduct calibration
6. Determine terminal dimension states
7. Only then design and preregister the pilot
8. Only then run the pilot
```

The project must not skip directly from this file to a pilot run.

The protocol remains `NOT PILOT-READY` until the hostile audit, schemas, handbook, and required calibration work are complete.

---

# 38. Future required artifacts, not created by this task

The next artifact class, after hostile review, is expected to include:

```text
research/protocols/continuity_probe.schema.json
research/protocols/continuity_answer.schema.json
research/protocols/experiment_manifest.schema.json
research/protocols/critical_integrity_probe.schema.json
research/protocols/ANNOTATOR_HANDBOOK.md
research/protocols/PRIVATE_CORPUS_REPLICATION_PACKET.md
```

These files do not yet exist merely because they are named here.

Their creation does not authorize calibration or pilot execution until the ladder permits it.

---

# 39. Current project state

At the time of this record:

- the Light Compression Hypothesis remains an internal canonical research position under CANON-001;
- Protocol v0.1 was written and committed;
- Protocol v0.1 received a secondary methodological audit through Muse;
- Muse did not directly inspect GitHub or the full artifact;
- ChatGPT verified the accepted audit findings against the actual v0.1 artifact;
- Protocol v0.2 applies the accepted twelve-item repair specification;
- Protocol v0.2 is not canon;
- Protocol v0.2 has not been run;
- Protocol v0.2 is not pilot-ready;
- no calibration has occurred;
- no pilot has occurred;
- no confirmatory benchmark has occurred;
- no scientific result exists;
- no independent participant replication has occurred.

The next permitted state transition is hostile audit of Protocol v0.2.

---

# 40. Final research statement

The narrow scientific proposition is:

> **At equal information budgets, a continuity-aware representation should preserve more source-backed decision, correction, temporal, relational, provenance, and uncertainty structure than generic compression.**

The methodological test is:

> **Can independent annotators measure continuity distortion reliably without assuming in advance that Legacy.GI is correct?**

If a dimension cannot be measured reliably, the hypothesis must change.

If the instrument fails under predefined measurement conditions, the result is `INCONCLUSIVE_MEASUREMENT`.

If the instrument works and Spine v0 loses, the result is `FAIL`.

If the instrument works and Spine v0 passes every locked threshold and both gates, the result is `PASS` for that corpus, protocol version, and hypothesis version.

Only later independent replication can support a broader claim.

The instrument is not the evidence.

The run is not the replication.

The claim earns only what the receipts support.

---

# 41. Required provenance block

The research problem, Light Compression concept, LEGACY.GI architecture, and continuity priorities originate with Noah A. Hawkes.

Protocol v0.1 was drafted with ChatGPT assistance.

The v0.2 repair specification derives from a secondary methodological audit by Muse. Muse conducted that audit without direct GitHub access and from a ChatGPT-mediated description. ChatGPT then verified the accepted criticisms against the actual v0.1 artifact before incorporating them.

Protocol v0.2 is drafted with ChatGPT assistance.

It is not a Noah-authored statement unless adopted by Noah.Physical.

The mediation chain must not later be compressed into the false statement that Muse directly inspected Protocol v0.1.

The review process is evidence about the instrument-development process.

It is not evidence for the Light Compression Hypothesis.

The witness must not become the author.

---

# 42. Worked witness example

The protocol-development chain is preserved as:

```text
Noah-originated research problem
-> ChatGPT-drafted Protocol v0.1
-> ChatGPT-written handoff summary
-> Muse secondary audit without direct GitHub access
-> Noah.Physical transported Muse's audit
-> ChatGPT checked the audit against the actual v0.1 artifact
-> accepted repairs became the v0.2 specification
-> ChatGPT drafted Protocol v0.2
```

This must not later be summarized as:

```text
Muse directly inspected and approved the protocol.
```

That would be false provenance.

This exchange is a worked example of the witness architecture functioning correctly:

- the audit's limits were stated;
- the mediation chain was preserved;
- the source artifact was checked before the critique was accepted;
- accepted repairs were distinguished from rejected or narrowed recommendations;
- the quality of the repair process was not treated as evidence for the underlying claim.

The discipline is part of the product.

---

**Record end.**

**Status:** CANDIDATE RESEARCH PROTOCOL  
**Canon status:** NOT CANON until Noah.Physical approves  
**Execution status:** NOT RUN  
**Readiness:** NOT PILOT-READY  
**Next permitted action:** Hostile audit of Protocol v0.2
