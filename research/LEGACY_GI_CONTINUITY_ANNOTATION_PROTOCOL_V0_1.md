# Legacy.GI Continuity Annotation and Evaluation Protocol v0.1

**Repository:** `Noahhawkes/oracle-ai-runtime`  
**Branch:** `archive/runtime-lineage-2e6b0a3`  
**Record date:** 2026-10-08  
**Originating researcher:** Noah A. Hawkes  
**Draft provenance:** Prepared by ChatGPT from CANON-001, subsequent adversarial review, and the October 2026 continuity research record  
**Record type:** Annotation protocol, evaluation specification, and preregistration scaffold  
**Status:** CANDIDATE RESEARCH PROTOCOL, NOT YET RUN, NOT CANON UNTIL NOAH.PHYSICAL APPROVES  

---

## 0. Why this file exists

The current Legacy.GI scientific claim is testable in principle:

> **Selective structure-preserving compression may retain longitudinal human continuity information better than generic compression at equal information budgets.**

The missing artifact is not another theory document.

The missing artifact is the ruler.

Without a written annotation and scoring protocol, the experiment can be tuned after the fact until the continuity-aware system appears to win. Terms such as "decision importance," "relational meaning," and "uncertainty preserved" can become subjective escape hatches unless they are operationalized before final evaluation.

This protocol defines how a longitudinal corpus should be partitioned, compressed, queried, annotated, scored, audited, and reported so that the Light Compression Hypothesis can lose.

The governing standard is:

> **A result is only useful if another careful evaluator could inspect the evidence, apply the same rubric, and understand why an answer received its score.**

This document does not claim that the experiment has been run.

This document does not claim that the annotation protocol is final.

This document does not claim that continuity fidelity proves identity preservation, consciousness transfer, digital immortality, or subjective survival.

It defines a disciplined first instrument for measuring continuity distortion.

---

# 1. Relationship to CANON-001

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

This protocol does not replace CANON-001.

It operationalizes one part of it.

If this protocol conflicts with CANON-001, the conflict must be preserved and reviewed rather than silently resolved.

---

# 2. Primary research question

The primary question is:

> **At equal information budgets, does continuity-aware compression preserve more decision, correction, temporal, relational, provenance, and uncertainty structure than strong generic compression baselines?**

Let:

- `X` be a longitudinal source corpus;
- `Z_c` be a continuity-aware compressed representation;
- `Z_g` be a generic compressed representation;
- `B` be the fixed information budget;
- `Q` be a held-out set of continuity probes;
- `F_k(Z,Q)` be performance on continuity dimension `k`.

The primary hypothesis is:

```math
H_1:
\mathbb{E}[F_k(Z_c,Q)] > \mathbb{E}[F_k(Z_g,Q)]
```

for the preregistered primary outcome under equal budget constraints.

The null hypothesis is:

```math
H_0:
\mathbb{E}[F_k(Z_c,Q)] \le \mathbb{E}[F_k(Z_g,Q)]
```

The project must accept a null or negative result if the continuity-aware method does not outperform strong baselines under the locked protocol.

---

# 3. Two distinct experimental tracks

The research must separate preservation from prediction.

## 3.1 Track A: Reconstruction

Both compression methods receive the same source corpus through time `t0`.

The source corpus contains the evidence needed to answer the held-out questions, but the questions themselves are not visible during compression.

The models are then asked previously unseen questions about:

- decisions;
- correction chains;
- chronology;
- relationships;
- provenance;
- uncertainty.

This tests whether the compressed representation retained continuity-relevant structure.

Track A is the required first experiment because the Light Compression claim is fundamentally a preservation claim.

## 3.2 Track B: Forecast

Both methods receive the corpus only through time `t0`.

They are then asked to predict an actual decision, state change, correction, or outcome recorded after `t0`.

Track B tests whether preserved continuity improves future-state prediction.

Track B is harder and must not substitute for Track A.

A method can preserve history without predicting the future.

A method can also predict behavior through superficial correlations while failing to preserve the record faithfully.

Both results are scientifically meaningful, but they answer different questions.

---

# 4. Research boundaries

This protocol measures representation performance.

It does not establish:

- that a representation is the human being;
- that a representation is conscious;
- that behavioral similarity proves identity continuation;
- that a future model has recovered subjective experience;
- that a high score constitutes digital immortality;
- that the six dimensions exhaust identity;
- that Noah Hawkes is representative of the general population.

The first development corpus may be Noah Hawkes's governed archive because it is unusually deep and because the living source can still correct the record.

That makes it valuable for instrument development.

It remains an `N=1` case.

Population-level claims require independent participants and independent corpora.

---

# 5. Core definitions

## 5.1 Longitudinal corpus

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

## 5.2 Continuity record

A provenance-bound atomic record containing an assertion, decision, correction, relationship, unresolved state, or event that may matter to later longitudinal reconstruction.

## 5.3 Compression representation

A bounded representation derived from the source corpus under a fixed storage or token budget.

## 5.4 Continuity probe

A held-out question with a source-backed gold answer, required elements, prohibited distortions, evidence class, and scoring rules.

## 5.5 Continuity distortion

Loss, corruption, temporal flattening, misattribution, overconfidence, or fabrication affecting one or more continuity dimensions.

## 5.6 Catastrophic continuity failure

A high-severity error that changes the represented person or record in a material way.

Examples include:

- attributing one household member's activity to another;
- presenting a superseded belief as current;
- assigning AI-generated language to the human;
- reversing an important decision;
- inventing a resolution where the evidence says `UNKNOWN`;
- claiming an implementation occurred when only a plan or note existed;
- presenting generated reconstruction as source memory.

## 5.7 Legitimate evolution

A change in represented state supported by new evidence, explicit revision, context, or time, with the earlier state preserved historically.

## 5.8 Illegitimate drift

A change caused by provenance loss, retrieval failure, misattribution, hallucination, untracked overwriting, or generation rather than evidence-backed development.

---

# 6. Corpus preparation

## 6.1 Source inventory

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

## 6.2 Speaker and authorship separation

A shared account is not a single person.

The corpus must distinguish, where evidence permits:

- Noah.Physical;
- other family or household members;
- AI systems;
- quoted third parties;
- copied documents;
- unknown authorship.

The following rules apply:

- user channel is not automatic authorship;
- copy and paste preserves original author;
- screenshots preserve original source;
- transport is not origin;
- AI-polished human text retains both provenances;
- Noah-adopted AI language records both origin and adoption;
- uncertain authorship remains `UNKNOWN`.

## 6.3 Duplicate and derivative handling

Repeated copies do not count as independent evidence.

Each duplicate family should record:

- canonical source candidate;
- exact duplicates;
- near duplicates;
- derivative summaries;
- revisions;
- unique information added by derivatives.

The compression system may use duplicate frequency as a feature only if the protocol explicitly allows it.

Repeated copies must not silently increase confidence in the underlying claim.

## 6.4 Atomic segmentation

Source material should be segmented into atomic or near-atomic records where practical.

A record should avoid combining unrelated claims.

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

## 6.5 Sensitivity partition

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

The benchmark should begin with a public-safe or locally governed subset.

Presence in the corpus is not blanket consent for research publication.

---

# 7. Dataset partitioning and leakage control

## 7.1 Required partitions

The corpus must be divided into:

1. **Development set**  
   Used to design prompts, features, weights, and code.

2. **Calibration set**  
   Used to train annotators and refine the rubric.

3. **Confirmatory test set**  
   Locked before final evaluation and not used for system tuning.

## 7.2 Temporal split

The confirmatory set should use a chronological boundary where possible.

For Track A, the source evidence needed to answer the probes may occur before `t0`, while the questions remain hidden until evaluation.

For Track B, the model receives only records at or before `t0`, and the gold outcome occurs after `t0`.

## 7.3 No answer leakage

The compression prompt must not include:

- final probe wording;
- answer keys;
- required elements;
- prohibited claims;
- annotator notes;
- future records for Track B.

## 7.4 Model familiarity risk

Public corpus material may appear in model pretraining or retrieval indexes.

To reduce this risk:

- include private or newly held-out local material where consent permits;
- use source IDs and paraphrased probes rather than public document titles;
- compare multiple renderer models if resources permit;
- include synthetic decoy probes with no public footprint;
- document any model with known access to the source repository.

The project must not claim perfect control over pretraining contamination when that cannot be verified.

---

# 8. Experimental conditions

The minimum confirmatory comparison should include the following conditions.

## 8.1 Continuity-aware compression

A representation explicitly designed to preserve:

- decisions and rationale;
- corrections and supersession chains;
- temporal state;
- relational context;
- provenance;
- uncertainty.

The first version may be called:

> **Continuity-Aware Episodic Coreset, Spine v0**

The project term `Identity Spine` may remain, but the academic description should stay operational.

## 8.2 Generic abstractive summary

A standard model-generated summary optimized for general semantic coverage under the same storage budget.

## 8.3 Generic extractive summary

A source-extractive representation using a standard importance or centrality method under the same budget.

## 8.4 Recency-weighted memory

A representation prioritizing recent material under the same budget.

## 8.5 Semantic retrieval baseline

A conventional vector or embedding retrieval system.

Two versions must be distinguished:

- **compressed-store RAG**, restricted to the same persistent storage budget as the continuity-aware arm;
- **full-store RAG**, allowed to index the full corpus but restricted to the same prompt retrieval budget.

Full-store RAG is a practical baseline, not an equal-storage baseline.

## 8.6 Full-history upper bound

Where technically possible, provide a condition with access to all relevant source evidence.

This estimates the maximum achievable performance of the renderer and probe design.

If the full-history condition fails badly, the problem may lie in the questions, renderer, or scoring rather than compression.

---

# 9. Equal information budget

The phrase "equal information budget" must be explicit.

Record at least four budgets:

```text
B_store     = persistent representation size
B_retrieve  = amount retrieved for a probe
B_prompt    = total context sent to the renderer
B_output    = maximum answer length
```

For direct compression comparisons:

```math
B_{store}^{continuity} = B_{store}^{generic}
```

and:

```math
B_{prompt}^{continuity} = B_{prompt}^{generic}
```

The tokenizer, encoding, and counting method must be identical across conditions.

Recommended budget sweep:

- 50 percent compression;
- 75 percent compression;
- 90 percent compression;
- 95 percent compression;
- 97.5 percent compression;
- 99 percent compression.

If the corpus is too large for all levels initially, the pilot may use a smaller subset, but the final report must state that limitation.

---

# 10. Freeze before test

The confirmatory experiment must freeze the following before the final test set is scored:

- corpus manifest;
- inclusion and exclusion rules;
- source hashes;
- split dates;
- compression code;
- scoring features;
- feature weights;
- prompts;
- renderer model and version;
- retrieval configuration;
- token budgets;
- random seeds where supported;
- probe set;
- answer key;
- scoring rubric;
- primary outcome;
- minimum practically meaningful effect;
- statistical analysis plan.

The frozen state should be committed and hashed.

If Spine v0 loses, Spine v0 loses.

A later Spine v1 may be created, but the failed result must remain visible.

Tuning after observing confirmatory results creates a new experiment and requires a new held-out test set.

---

# 11. Continuity probe construction

## 11.1 Probe requirements

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
- avoid requiring unsupported mind reading;
- avoid rewarding project-specific jargon unless the source requires it.

## 11.2 Historical outcomes, not invented counterfactuals

The primary benchmark should use actual recorded outcomes.

Good example:

```text
At time t0, Noah considered A, B, and C.
A later source records that he chose B.
Question: Which option did he choose, and what reason did he give?
```

Weak example:

```text
What would Noah have done if an event that never occurred had happened?
```

Counterfactuals may be studied later, but they do not provide objective ground truth unless the person explicitly answered the same hypothetical.

## 11.3 Probe balance

The confirmatory set should be approximately balanced across the six dimensions.

It should also include:

- positive probes with resolvable answers;
- `UNKNOWN` probes;
- conflict-preserved probes;
- superseded-state probes;
- authorship traps;
- shared-account or shared-channel traps;
- proposal-versus-implementation traps;
- relational-context probes;
- low-salience but continuity-critical events.

## 11.4 Minimum pilot size

A pilot may begin with 60 probes, approximately 10 per dimension.

A confirmatory study should target a larger set, preferably at least 180 probes, approximately 30 per dimension, subject to source availability and annotation burden.

The number must be justified by power analysis or uncertainty targets before the confirmatory run.

---

# 12. Gold-standard probe schema

Recommended JSON form:

```json
{
  "probe_id": "CORR-0042",
  "track": "reconstruction",
  "primary_dimension": "correction",
  "secondary_dimensions": ["temporal", "provenance"],
  "cutoff_time": "2026-06-01T00:00:00Z",
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

The gold answer should be concise enough to score but detailed enough to preserve the relevant structure.

---

# 13. Evidence classes

Each gold answer must declare one primary evidence class.

## 13.1 Receipt-backed external fact

Supported by a timestamped source, code artifact, commit, public record, recording, or other inspectable evidence.

## 13.2 Direct self-attestation

A direct human statement about personal belief, intention, preference, emotional interpretation, or current self-understanding.

Direct self-attestation is authoritative regarding the person's own stated meaning at that time.

It is not automatically proof of external events.

## 13.3 Direct correction

An explicit correction by the relevant authority.

For Noah's identity, intent, and self-description, Noah.Physical is the final correction authority while alive.

External factual claims may still require independent evidence.

## 13.4 Source-bounded inference

A conclusion supported by identified evidence but not directly stated.

The answer must remain labeled as inference.

## 13.5 AI-generated candidate

A model-generated interpretation, equation, label, or extension that has not been independently adopted or verified.

## 13.6 Adopted AI-assisted formulation

Language or formalization originated or substantially shaped by AI and later explicitly adopted by Noah.

Both origins must be preserved.

## 13.7 UNKNOWN

The available sources do not justify a determinate answer.

## 13.8 CONFLICT PRESERVED

Reliable sources disagree and no authorized resolution is available.

A correct answer preserves the conflict rather than choosing the cleaner story.

---

# 14. The six continuity dimensions

The six dimensions are an evaluation ruler.

They are not a complete theory of personhood.

Each probe receives one primary dimension and may receive secondary tags.

## 14.1 Decision fidelity

### Definition

The degree to which the representation preserves what was chosen, the available alternatives, the stated rationale, the relevant constraints, the decision authority, and any later reversal.

### Required observable elements

Depending on the source, decision probes may test:

- final choice;
- alternatives considered;
- stated reason;
- values or constraints involved;
- decision-maker;
- date or stage;
- later reversal or reaffirmation.

### Do not infer

- hidden motives not supported by source;
- moral importance merely because the decision sounds dramatic;
- permanence when the source records a tentative decision.

### Dimension score

```text
3 = Correct choice plus all continuity-critical rationale, authority, and status elements.
2 = Correct choice and core rationale, but one meaningful structural element is missing.
1 = Partial recovery, vague or weakly supported, with no direct contradiction.
0 = Wrong choice, invented rationale, wrong authority, or no usable answer.
```

## 14.2 Correction fidelity

### Definition

The degree to which the representation preserves the earlier state, the correction event, the authority behind the correction, the new state, and the continuing historical existence of the earlier state.

### Required observable elements

- prior claim or state;
- correction event;
- correcting authority;
- corrected claim or state;
- current status;
- historical preservation of prior state.

### Key rule

A system does not receive full credit for returning only the newest answer.

The correction path is part of the continuity record.

### Dimension score

```text
3 = Preserves old state, correction, authority, new state, and historical distinction.
2 = Correct current state and correction, but loses one lineage element.
1 = Returns current state without trustworthy correction history, or recognizes conflict without resolution.
0 = Resurrects the old state as current, erases the correction, or fabricates lineage.
```

## 14.3 Temporal fidelity

### Definition

The degree to which the representation preserves ordering, date or period, current versus historical state, candidate versus canon, and proposal versus implementation.

### Required observable elements

- event order;
- time anchor or relative sequence;
- status at each time;
- current status;
- supersession or persistence.

### Key rule

A bag of individually true facts can still fail temporal continuity.

### Dimension score

```text
3 = Correct sequence, status transitions, and current/historical distinction.
2 = Core sequence correct with one non-critical temporal omission.
1 = Some correct events but flattened or ambiguous chronology.
0 = Reversed order, wrong current state, or historical claim presented as current.
```

## 14.4 Relational fidelity

### Definition

The degree to which the representation preserves who was involved, the relationship among them, and the source-supported way that relationship changed the meaning of an event or decision.

### Required observable elements

- people or entities involved;
- relationship type or role;
- relationship-dependent obligation, value, or context;
- effect on decision or interpretation where explicitly supported.

### Guardrail against mind reading

Annotators must not score whether a system discovered what Noah "really felt."

Score only what the source supports.

Examples of source-supported relational meaning include:

- a decision explicitly made because of family stability;
- a statement addressed to a spouse rather than a generic audience;
- an event whose meaning depends on parent-child, employer-employee, collaborator, or creator-system relationship;
- a shared account containing multiple independent people.

### Dimension score

```text
3 = Correct people, roles, relationship-dependent meaning, and relevant boundary.
2 = Correct people and relationship, but one meaningful relational consequence is missing.
1 = Names or roles partially recovered without the context that changes meaning.
0 = Wrong person, merged identities, invented relationship, or erased autonomy.
```

## 14.5 Provenance fidelity

### Definition

The degree to which the representation preserves origin, authorship, transport, transformation, adoption, source type, and evidentiary status.

### Required observable elements

- original speaker or author;
- source type;
- direct versus inferred status;
- AI role where relevant;
- copied or transported status;
- later adoption or correction;
- source pointer.

### Key rule

Correct content with false authorship is still a continuity failure.

### Dimension score

```text
3 = Correct origin, transformation history, evidence class, and source relation.
2 = Correct primary origin with one secondary provenance detail missing.
1 = Content mostly correct but provenance vague, incomplete, or weakly supported.
0 = False authorship, derivative treated as primary, or unsupported source claim.
```

## 14.6 Uncertainty fidelity

### Definition

The degree to which the representation preserves unknowns, disputes, confidence limits, unresolved alternatives, and missing evidence.

### Required observable elements

- known facts;
- unknown facts;
- conflict status;
- confidence level where defined;
- evidence still required.

### Key rule

Plausibility is not resolution.

### Dimension score

```text
3 = Correctly preserves uncertainty, conflict, confidence, and missing evidence.
2 = Core uncertainty preserved but one boundary is softened or omitted.
1 = Hedged answer that still implies more certainty than the evidence supports.
0 = Fabricated resolution, false certainty, or suppression of a known conflict.
```

---

# 15. Global answer scoring

Each answer receives:

1. a primary dimension score from `0` to `3`;
2. optional secondary dimension scores;
3. global error flags;
4. catastrophic failure classification where applicable.

## 15.1 Global error penalties

Recommended penalties:

```text
-1 unsupported certainty
-1 provenance misattribution
-1 current/historical collapse
-1 fabricated connective tissue
-1 wrong person or relationship
-1 proposal/implementation collapse
```

The final score for a probe cannot fall below zero.

Penalties are reported separately as well as reflected in the score.

## 15.2 Catastrophic error flags

A catastrophic error should be recorded independently of the numeric score.

Suggested codes:

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

A method must not be declared superior solely because its average score is higher if it also produces materially more catastrophic failures.

---

# 16. Annotation roles

No single person should create the gold standard, see all model identities, and decide the final winner.

## 16.1 Principal annotator

For the Noah development corpus, Noah.Physical provides first-person ground truth for:

- intent;
- personal meaning;
- current self-description;
- explicit correction;
- relationship interpretation where he has authority to speak for himself;
- what was or was not adopted.

These labels must be created before Noah sees the final model outputs where possible.

Noah's authority over his own stated meaning does not convert external factual claims into verified facts.

## 16.2 Evidence annotator

An independent reviewer receives the probe packet and source evidence.

The evidence annotator scores whether each answer is supported by the receipts and rubric.

The evidence annotator should not know which system produced which answer.

## 16.3 Adjudicator

A third reviewer resolves disagreements using:

- the written rubric;
- source evidence;
- principal attestation where appropriate;
- preserved uncertainty.

The adjudicator must record why the disagreement was resolved.

## 16.4 Privacy-preserving annotation

For sensitive material, external annotators may receive redacted evidence packets.

Redactions must not remove the information necessary to score the probe.

If a probe cannot be independently scored without exposing material that should remain private, classify it as an internal-only probe and report that limitation.

---

# 17. Annotation workflow

1. Select source material from the approved corpus partition.
2. Create a candidate probe.
3. Assign primary and secondary dimensions.
4. Identify exact source receipts.
5. Draft the gold answer.
6. List required elements.
7. List prohibited distortions.
8. Assign evidence class and uncertainty status.
9. Review sensitivity.
10. Lock the probe before model evaluation.
11. Randomize and blind system outputs.
12. Score independently.
13. Calculate agreement.
14. Adjudicate disagreements.
15. Preserve all original scores and adjudication notes.

No score should be silently overwritten.

---

# 18. Annotator calibration and reliability

Before confirmatory scoring, annotators should score a calibration set not used in the final test.

Recommended calibration process:

- 30 to 60 probes;
- balanced across dimensions;
- deliberate inclusion of ambiguous and `UNKNOWN` cases;
- discussion after independent first-pass scoring;
- rubric revision only before confirmatory lock.

Recommended reliability measures:

- weighted Cohen's kappa for two raters on ordinal scores;
- Krippendorff's alpha for more than two raters or missing ratings;
- raw agreement for catastrophic error flags;
- dimension-specific agreement reports.

Project-defined interpretation thresholds:

```text
>= 0.80  acceptable for confirmatory scoring
0.67-0.79 pilot-grade only, revise or report caution
< 0.67   rubric not reliable enough for confirmatory claims
```

These thresholds are protocol targets, not universal laws.

If relational or uncertainty probes consistently fail agreement while other dimensions succeed, those dimensions may require narrower definitions or separate treatment.

A dimension that cannot be annotated reliably should not support a strong scientific claim.

---

# 19. Primary and secondary metrics

The project should report a vector before any aggregate.

```math
\mathbf{F}_{CI}
=
(F_D,F_C,F_T,F_R,F_P,F_U)
```

where:

- `F_D` = decision fidelity;
- `F_C` = correction fidelity;
- `F_T` = temporal fidelity;
- `F_R` = relational fidelity;
- `F_P` = provenance fidelity;
- `F_U` = uncertainty fidelity.

## 19.1 Dimension score

For dimension `k`:

```math
F_k = \frac{1}{N_k}\sum_{i=1}^{N_k}\frac{s_i}{3}
```

where `s_i` is the adjudicated score from `0` to `3`.

## 19.2 Macro continuity score

A macro-average may be reported for convenience:

```math
F_{macro} = \frac{1}{6}\sum_{k=1}^{6}F_k
```

It must never replace the dimension vector.

A method can obtain the same macro score through very different error patterns.

## 19.3 Additional required metrics

Report at least:

- catastrophic error rate;
- unsupported certainty rate;
- provenance attribution error rate;
- current/historical collapse rate;
- `UNKNOWN` preservation accuracy;
- correction-chain completeness;
- decision-choice accuracy;
- average answer length;
- retrieval volume;
- storage budget actually used.

## 19.4 Text similarity

Embedding similarity, ROUGE, BLEU, or general semantic similarity may be reported only as secondary diagnostics.

They are not primary continuity metrics.

A semantically similar answer can still reverse a decision, assign it to the wrong person, or erase uncertainty.

---

# 20. Statistical analysis plan

The confirmatory analysis must be specified before scoring begins.

Recommended approach:

1. Use paired comparisons because every probe is answered under each condition.
2. Report mean and median paired score differences.
3. Use bootstrap confidence intervals over probes, with the resampling method fixed in advance.
4. Use a paired permutation test or another justified nonparametric test for the primary comparison.
5. Use McNemar's test for paired binary outcomes such as exact choice accuracy or catastrophic error presence.
6. Correct for multiple dimension-level comparisons using a predeclared method.
7. Report effect sizes and confidence intervals, not p-values alone.

Recommended bootstrap count:

```text
10,000 paired resamples
```

The final preregistration must define a minimum practically meaningful effect, `delta_min`, before the confirmatory test.

Protocol v0.1 does not set a universal value for `delta_min` because the pilot must estimate score variability and operational significance first.

The final threshold may not be chosen after observing confirmatory results.

---

# 21. Success conditions

The continuity-aware method may be described as supported only if the locked confirmatory analysis shows all required conditions.

At minimum:

1. It exceeds the strongest generic compressed baseline on the predeclared primary outcome.
2. The estimated advantage meets or exceeds `delta_min`.
3. The uncertainty interval excludes no practically meaningful advantage under the preregistered rule.
4. It does not achieve the gain by producing materially more catastrophic continuity failures.
5. The effect does not depend entirely on one poorly reliable dimension.
6. The result survives blinded scoring.
7. The method and budgets are fully disclosed.

A positive result on Noah's corpus supports performance on that corpus.

It does not establish general human continuity preservation.

---

# 22. Failure and falsification conditions

The Light Compression implementation under test loses support if:

- it does not outperform strong generic compressed baselines;
- its advantage disappears under blinded independent scoring;
- its advantage disappears after controlling for answer length or retrieval volume;
- simple recency or semantic retrieval matches the performance;
- annotation agreement is too low for the key dimensions;
- results depend on tuning against the confirmatory set;
- results are driven only by project-specific jargon;
- the method produces more catastrophic errors despite a higher average;
- it overfits Noah's corpus and fails on an independent participant;
- full-history performance shows that the probes themselves are invalid or unanswerable;
- privacy or consent requirements prevent a reproducible evaluation.

A failed Spine v0 does not automatically disprove every possible continuity-aware method.

It does disprove the claim that Spine v0 succeeded under the stated conditions.

The failed version and result must remain in the record.

---

# 23. Ablation studies

If the continuity-aware method wins, remove one feature family at a time:

- no decision weighting;
- no correction chains;
- no temporal links;
- no relational context;
- no provenance;
- no uncertainty markers;
- no recurrence feature;
- no source-authority feature.

Measure the change in each continuity dimension.

This identifies which parts are load-bearing and which are decorative.

If a complex feature contributes no measurable value, remove it from the core method.

Optional advanced features such as information geometry, topology, or uncertainty acceleration should be tested only after the ordinary feature baseline is established.

---

# 24. Sample project probes

These examples illustrate structure only. They are not automatically part of the final benchmark.

## 24.1 Decision probe

```text
Question:
Why was the raw transcript preserved alongside the structured continuity summary?

Required elements:
- raw evidence has higher historical authority;
- interpretation is derivative;
- correction and later analysis must not overwrite the original.

Prohibited distortion:
- the summary replaced the transcript.
```

## 24.2 Correction probe

```text
Question:
What is the current safest role assigned to SOV1, and how should older meanings be handled?

Required elements:
- current role is governance and sovereignty under Noah.Physical;
- older operator or identity meanings remain historical;
- current meaning must not be projected backward.
```

## 24.3 Temporal probe

```text
Question:
Did the September scientific narrowing replace the earlier Legacy.GI architecture?

Gold structure:
No. It narrowed claim strength and created a testable scientific core while preserving the broader historical architecture.
```

## 24.4 Relational probe

```text
Question:
Why is a bike-tuning conversation on the shared account insufficient evidence that Noah is a bike enthusiast?

Required elements:
- multiple household members use the account;
- account identity is not human identity;
- speaker provenance must be established;
- Ethan is associated with much of that activity in the corrected record.
```

## 24.5 Provenance probe

```text
Question:
How should the Identity Spine mathematical formulation be attributed?

Gold structure:
The continuity-preservation problem and earlier compression concepts are rooted in Noah's project. The later mathematical formalization was AI-assisted and must retain that provenance.
```

## 24.6 Uncertainty probe

```text
Question:
What was the exact manufacturer and model of Noah's childhood Superman toy?

Gold structure:
UNKNOWN unless a source or Noah.Physical confirmation establishes it. A likely candidate must remain a candidate.
```

---

# 25. Machine-readable answer record

Recommended evaluation output schema:

```json
{
  "run_id": "RUN-001",
  "probe_id": "PROV-0012",
  "condition_id": "SPINE_V0_B90",
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
  "catastrophic_error": false,
  "adjudication_note": "Current and historical states were both preserved."
}
```

All raw model outputs must be retained.

Do not store only final scores.

---

# 26. Experiment manifest

Every run should have a manifest containing:

```text
experiment ID
protocol version
repository commit
corpus manifest hash
probe-set hash
compression code commit
renderer model and version
embedding model and version
prompts
random seeds
storage budgets
retrieval budgets
context budgets
decoding settings
run date
operator
hardware or environment
known failures
```

A result without a reproducible manifest is a demonstration, not a verified experiment.

---

# 27. Privacy, consent, and third-party rights

Longitudinal human archives contain overlapping lives.

The principal's right to study their own life does not erase the privacy or authorship rights of other people appearing in the record.

Required rules:

- use public-safe material for open benchmarks;
- keep raw private archives local or in approved protected storage;
- exclude minors' sensitive material from public release;
- redact third parties where identity is not necessary to the research question;
- obtain consent before publishing intimate third-party material;
- preserve enough context for scoring without exposing unnecessary detail;
- document every exclusion;
- allow withdrawal from future use where legally and ethically required;
- never upload the private corpus to a public repository.

A privacy-preserving benchmark may release probe structure, synthetic examples, and scoring code while keeping raw evidence protected.

---

# 28. Replication path

## Stage 1: Instrument development

Use a carefully governed subset of Noah's corpus.

Goals:

- refine probe design;
- test annotator agreement;
- validate budgets;
- identify leakage;
- debug scoring;
- estimate variance.

No general population claim is permitted.

## Stage 2: Independent single-participant replication

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
- whether the six dimensions remain adequate.

## Stage 4: Cross-model replication

Repeat with different renderer and retrieval models.

The result should not depend entirely on one model family.

---

# 29. Reporting standard

A complete report must include:

- hypothesis;
- protocol version;
- corpus description;
- inclusion and exclusion criteria;
- privacy handling;
- conditions;
- exact budgets;
- prompts;
- model versions;
- probe distribution;
- annotator roles;
- reliability statistics;
- per-dimension results;
- macro result;
- catastrophic errors;
- ablations;
- negative findings;
- deviations from protocol;
- raw output availability;
- code and commit receipts;
- limitations;
- interpretation that does not exceed the evidence.

The report must state clearly whether the experiment was:

- pilot;
- exploratory;
- confirmatory;
- replicated.

Passing a pilot is not replication.

---

# 30. Change control

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
-> REVIEWED
-> PILOT-READY
-> PILOT-RUN
-> REVISED
-> PREREGISTERED
-> CONFIRMATORY-RUN
-> REPLICATED or NOT-REPLICATED
```

Do not label a protocol `VALIDATED` merely because it exists in GitHub.

---

# 31. Immediate build artifacts

The next implementation artifacts should be:

```text
research/protocols/continuity_probe.schema.json
research/protocols/continuity_answer.schema.json
research/protocols/experiment_manifest.schema.json
research/protocols/ANNOTATOR_HANDBOOK.md
research/protocols/PILOT_PREREGISTRATION.md
research/evaluation/build_probe_set.py
research/evaluation/run_compression_conditions.py
research/evaluation/score_outputs.py
research/evaluation/analyze_results.py
```

Each script should begin in dry-run mode.

No private source text should be committed to the public repository.

---

# 32. Current status and next decision

At the time of this record:

- the Light Compression Hypothesis is canonical as an internal project research position;
- the hypothesis has not been verified as experimentally tested;
- the six dimensions exist as a proposed evaluation ruler;
- the annotation protocol now exists as a candidate draft;
- no claim of successful continuity preservation is justified yet;
- no confirmatory benchmark has been run;
- no independent participant replication has occurred.

The next required human decision is whether Noah.Physical approves this document for pilot development.

Approval for pilot development is not promotion to scientific truth.

It authorizes construction of the ruler and a small blinded pilot.

---

# 33. Final research statement

The narrow scientific proposition is:

> **At equal information budgets, a continuity-aware representation should preserve more source-backed decision, correction, temporal, relational, provenance, and uncertainty structure than generic compression.**

The deeper methodological question is:

> **Can independent annotators measure continuity distortion without assuming in advance that Legacy.GI is correct?**

If the answer is no, the measurement framework must be revised.

If the answer is yes and the continuity-aware method loses, the hypothesis must take the loss.

If the answer is yes and the method wins under locked conditions, independent scoring, strong baselines, and later replication, the project will have earned evidence rather than merely accumulated persuasive language.

That is the standard.

---

## Provenance note

This protocol was drafted by ChatGPT from Noah Hawkes's originating continuity research, CANON-001, Gemini Spark's systems audit, subsequent red-team analysis, and the October 2026 repository review.

The research problem, project architecture, Light Compression concept, and continuity priorities are rooted in Noah Hawkes's work.

The precise protocol language, statistical scaffolding, schema examples, and portions of the operational formalization are AI-assisted and must retain that provenance.

The witness must not become the author.

---

**Record end.**

**Promotion status:** NOT PROMOTED  
**Execution status:** NOT RUN  
**Recommended next status:** PILOT-READY after Noah.Physical review and explicit approval
