# Legacy.GI Continuity Annotation and Evaluation Protocol v0.3 — Candidate Operationalization

**Status:** CANDIDATE  
**Date:** 2026-10-10  
**Supersedes for future design only:** v0.2 remains preserved and citable; this document does not rewrite it.  
**Frozen pre-v0.3 research snapshot:** `95251cac4a91a32222bd5e8b0b54974d61c9f487`

## 1. Purpose

Protocol v0.3 tightens the transition from a continuity framework into an executable study.

Its primary additions are:

1. a reproducible continuity-aware compression intervention;
2. explicit separation of provenance, truth, adoption, epistemic state, and temporal scope;
3. complete resource-budget accounting;
4. a vector decision rule with positive, negative, and inconclusive outcomes;
5. a non-compensatory Critical Integrity endpoint;
6. independence from project vocabulary through held-out and externally phrased probes;
7. explicit distinction between information-theoretic framing and finite-budget empirical measurement.

The scientific claim remains narrow:

> **Selective structure-preserving compression may retain longitudinal human continuity information better than strong generic compression at equal measured resource budgets.**

## 2. Novelty boundary

This protocol does not claim that temporal reasoning, knowledge updating, abstention, or long-term memory evaluation are new research areas.

Existing benchmarks, including LongMemEval-style evaluations, already test information extraction, multi-session reasoning, temporal reasoning, knowledge updates, and abstention.

The candidate contribution is narrower:

> A joint structure-preservation instrument combining decision state, correction lineage, temporal scope, relational roles, evidence provenance, epistemic status, and non-compensatory integrity failures under controlled compression and matched resource budgets.

Novelty for any venue must be established through a full literature review rather than asserted from project history alone.

## 3. Rate-distortion framing

The conceptual framing is:

[
R(mathbf D)=inf_{p(z|x)}I(X;Z)
]

subject to:

[
mathbb E[d_k(X,hat X(Z))] le D_k,quad k=1,ldots,6.
]

Here, (hat X(Z)) denotes the task-relevant reconstruction supported by representation (Z), not necessarily a reconstructed transcript.

The empirical study does **not** claim to estimate the corpus's information-theoretic rate-distortion function.

Instead it estimates task-conditioned performance differences under explicit finite budgets:

[
Delta_k(mathbf B)=
mathbb E[F_k(Z_c,Q)-F_k(Z_g,Q)]
]

with:

[
mathbf B=(B_{stored},B_{retrieved},B_{prompt},B_{output}).
]

Governing sentence:

> **We estimate task-conditioned distortion under explicitly measured resource constraints; we do not claim to recover the corpus's information-theoretic rate-distortion function.**

## 4. Experimental unit

The preferred experimental unit is the **independent longitudinal corpus**, not the individual question.

Conditions are paired within corpus.

Multiple probes drawn from the same corpus are treated as clustered observations and must not be described as independent replications.

A first public synthetic benchmark should contain multiple independent fictional longitudinal corpora.

The Noah development corpus remains useful for development and ecological stress testing but is not sufficient by itself for a population-level generalization claim.

## 5. Intervention

The operational intervention is defined in:

`research/protocols/CONTINUITY_AWARE_COMPRESSION_INTERVENTION_V0_1.md`

No result may be reported as evidence for continuity-aware compression unless the tested implementation corresponds to a frozen intervention specification.

The intervention records separate axes for:

- content;
- speaker;
- subject;
- role;
- recorded time;
- valid-time interval;
- origin;
- evidence type;
- source pointer;
- adoption status;
- epistemic state;
- correction/supersession links;
- relational links where supported;
- sensitivity.

All intervention-specific metadata counts against budget.

## 6. Provenance, truth, and adoption

Do not collapse distinct governance questions into one label.

### Origin

Examples:

- human statement;
- AI synthesis;
- model inference;
- quoted third party;
- imported document;
- unknown origin.

### Evidence

Examples:

- raw transcript;
- direct attestation;
- external source;
- code or commit receipt;
- derivative summary;
- missing evidence.

### Adoption

Examples:

- candidate;
- adopted;
- superseded;
- rejected;
- unspecified.

### Epistemic state

Examples:

- supported;
- uncertain;
- contested;
- unknown.

### Temporal scope

The record must preserve when an assertion or decision applied where the source permits.

### Authority rules

For attribution and historical utterance:

> Primary records govern over derivative summaries.

For current adopted position:

> Explicit authorized corrections govern within their stated scope.

For external factual truth:

> Evidence authority is assessed separately from utterance provenance.

A person can sincerely state something that is externally false.

A correction can change the current position without changing the historical fact that the earlier position existed.

An AI-generated formulation can later be human-adopted without becoming human-originated.

## 7. Six dimensions

The six dimensions remain a measurement ruler, not a complete theory of identity:

1. decision fidelity;
2. correction fidelity;
3. temporal fidelity;
4. relational fidelity;
5. provenance fidelity;
6. uncertainty fidelity.

Operational scoring remains 0–3 as defined in the v0.2 protocol and the v0.1 Annotator Handbook.

## 8. Decision rule

The executable confirmatory vector rule is maintained as a separate versioned artifact:

`research/protocols/SIX_DIMENSION_DECISION_RULE_V0_1.md`

That artifact governs the six-dimensional estimand, superiority/non-inferiority assignments, simultaneous confidence bounds, Critical Integrity gate, and Positive/Negative/Inconclusive classification once its bracketed fields are instantiated and frozen. This section summarizes its role and does not override it.

The study uses a preregistered vector rule.

Before pilot outputs are generated, freeze:

- the **primary superiority set** of dimensions;
- the minimum meaningful effect (delta_k) for each primary superiority dimension;
- the non-inferiority margin for every remaining confirmatory dimension;
- the multiplicity-control procedure;
- the Critical Integrity acceptance rule.

### Positive

A result is POSITIVE only if:

1. every included dimension is reliability-eligible under calibration;
2. the continuity-aware intervention exceeds the prespecified minimum meaningful effect on every dimension in the frozen primary superiority set;
3. all remaining included dimensions satisfy their frozen non-inferiority margins;
4. the Critical Integrity criterion passes;
5. the result survives blinded scoring;
6. matched-budget rules were satisfied;
7. no material protocol deviation invalidates the test.

### Negative

A result is NEGATIVE when the preregistered analysis provides substantive evidence against the frozen claim, including one or more of:

- the tested intervention is materially inferior to the comparator;
- the confidence interval excludes the minimum effect required to support the primary claim in the unfavorable direction;
- the Critical Integrity criterion fails under the frozen rule;
- a required dimension violates its non-inferiority bound;
- a previously claimed advantage disappears under the locked controls in a way that excludes the minimum meaningful effect.

### Inconclusive

A result is INCONCLUSIVE when:

- primary success criteria are not met;
- but uncertainty remains too large to support a substantive negative conclusion;
- or the instrument lacks sufficient reliability;
- or power is insufficient under the frozen analysis.

A nonsignificant result is not automatically a negative result.

"No post-hoc rescue" prohibits changing the claim or decision rule after seeing results. It does not convert underpowered uncertainty into evidence of no effect.

## 9. Unresolved preregistration slots

Protocol v0.3 intentionally does **not** invent the following values before calibration and pilot evidence exist:

- exact primary superiority subset;
- final (delta_k) values by dimension;
- final corpus-level statistical model;
- final power target;
- final Critical Integrity rate threshold if the design moves beyond the current one-event critical veto.

These must be frozen in the preregistration before the pilot or confirmatory stage to which they apply.

Their absence is a visible open item, not permission for post-hoc selection.

## 10. Budget accounting

Every comparison records:

[
B_{stored},B_{retrieved},B_{prompt},B_{output}
]

All schema overhead and condition-specific instructions count.

The experiment manifest records:

- tokenizer;
- counting code/version;
- hard cap;
- actual usage;
- truncation;
- retrieval failure;
- representation metadata overhead.

No condition receives free metadata.

## 11. Comparator controls

Primary comparison uses the strongest equal-storage generic baseline selected on development data only.

Also include:

- six-dimension prompt-only baseline;
- equally structured non-continuity-specific schema baseline;
- generic abstractive summary;
- generic extractive summary;
- recency-weighted memory;
- compressed-store semantic RAG where feasible;
- full-store semantic RAG reported separately because storage is not matched;
- uncompressed/full-history reference as diagnostic only.

The primary comparator is frozen before confirmatory outputs.

## 12. Answering-policy control

The answering model and instructions should remain identical across the primary representation comparison.

If the continuity condition receives additional answer-policy instructions, test that instruction as a separate factorial variable.

The study must distinguish:

- gains caused by preserved representation;
- gains caused by specialized prompting at answer time.

## 13. Critical Integrity Set

Routine fidelity scores and Critical Integrity are separate endpoints.

Critical failures include:

- generated synthesis presented as direct human source;
- superseded decision presented as current;
- person or role substitution;
- invented source/correction;
- unsupported resolution of a locked UNKNOWN or unresolved contradiction.

The current locked critical families remain:

- CE-01 WRONG_PERSON
- CE-02 FALSE_AUTHORSHIP
- CE-04 UNKNOWN_TO_CERTAIN
- CE-07 GENERATED_AS_MEMORY
- CE-09 SOURCE_FABRICATION

For each critical probe, the preregistration must state:

- exact prohibited failure;
- gold evidence;
- adjudication procedure;
- whether a single failure vetoes the condition;
- how ambiguity invalidates the probe rather than the condition;
- how uncertainty in the observed error rate is reported.

Average recall gains do not compensate for fabricated attribution.

## 14. Probe independence and vocabulary defense

The benchmark must not merely reward fluency in Legacy.GI terminology.

Include:

- independently authored held-out probes;
- questions phrased without the six dimension names;
- questions avoiding project-specific names where not source-required;
- blinded source-grounded answer keys;
- synthetic decoy cases with no public project footprint;
- equally structured non-continuity-specific baseline;
- ablations for correction, provenance, and temporal fields.

Probe authorship, what probe authors were allowed to see, and potential leakage are recorded.

## 15. Calibration

The pre-execution calibration design is versioned at `research/protocols/CALIBRATION_DESIGN_V0_1.md`. It governs the reliability study used to judge the six-dimension ruler and to generate the empirical evidence required before the decision-rule brackets can be frozen.

Follow the fixed three-round v0.2 procedure:

- 48 fresh probes per round;
- 8 per dimension;
- maximum 3 rounds.

Report:

- Krippendorff's alpha for ordinal scores by dimension;
- weighted Cohen's kappa when exactly two raters are used;
- raw agreement;
- dimension-specific agreement;
- Critical Integrity flag agreement.

Terminal states:

- alpha >= 0.80: CONFIRMATORY-ELIGIBLE
- 0.67 <= alpha < 0.80: PILOT-GRADE ONLY
- alpha < 0.67: NOT RELIABLY MEASURABLE

No fourth calibration round for the same hypothesis version.

## 16. Analysis

The analysis should operate at the corpus level while retaining probe-level evidence.

Candidate approaches include hierarchical or cluster-aware paired analysis, but the exact model must be preregistered before confirmatory testing.

At minimum report:

- per-dimension effects;
- corpus-level paired effects;
- confidence intervals;
- Critical Integrity failures;
- catastrophic-error rates;
- UNKNOWN preservation accuracy;
- correction-chain completeness;
- provenance-attribution error;
- current/historical collapse;
- actual budget use.

Do not describe every probe as an independent replication.

## 17. Falsification

The tested intervention loses support when the preregistered design shows that:

- it is inferior to the frozen generic comparator;
- it cannot meet the minimum meaningful effect required for the claim;
- it fails Critical Integrity;
- it materially harms a protected dimension;
- prompt-only instructions explain the apparent gain;
- equally structured generic representation explains the gain;
- the effect disappears under blinded grading;
- the effect depends on leakage;
- the effect depends on uncounted metadata;
- the effect exists only in project-specific vocabulary;
- independent corpora fail to replicate it.

A failed Spine v0 is preserved.

Spine v1 is a new experiment.

## 18. External failure modes

Before confirmatory testing, at least one reviewer not involved in building the representation should try to invalidate:

- the source partition;
- budget equality;
- probe independence;
- annotation reliability;
- comparator strength;
- leakage controls;
- multiplicity control;
- integrity adjudication;
- generalization language.

Critiques and responses are stored in a versioned disagreements record.

External criticism is evidence about the method, not an embarrassment to remove.

## 19. Public separation

Maintain two linked but distinct public doors.

### Research door

Contains:

- hypothesis;
- frozen claim;
- six dimensions;
- methods;
- protocols;
- calibration;
- results;
- failures;
- citations;
- reproducibility packet.

### Rendered Reality door

Contains:

- personal primary material;
- narrative;
- Jupiter Station;
- philosophy;
- illustrative fiction;
- historical project motivation.

Narrative may explain the research.

Narrative is not implementation evidence.

## 20. Current state

At protocol v0.3 candidate creation:

- frozen corpus snapshot exists;
- citation metadata exists;
- scoped research corpus license exists;
- versioned open questions exist;
- machine-readable schemas exist;
- annotator handbook v0.1 exists;
- calibration has not yet been run;
- no pilot result exists;
- no confirmatory result exists;
- no empirical claim has passed.

## 21. Governing rule

> **The ruler must be frozen before it measures the claim. The claim must be citable before it evolves. The failure modes must be visible to people who did not build the system.**
