# Continuity Intelligence: A Rate-Distortion Framework for Longitudinal Human-AI Memory

**Author:** Noah A. Hawkes  
**Status:** MANUSCRIPT DRAFT v0.1  
**Date:** 2026-10-10  
**Research snapshot:** `95251cac4a91a32222bd5e8b0b54974d61c9f487`

## Abstract

Ordinary retrieval and summarization can recover text and topic while destroying continuity-critical structure in longitudinal human-AI records. This paper investigates whether an explicitly structure-preserving compression intervention improves six operational dimensions—decision, correction, temporal, relational, provenance, and uncertainty fidelity—relative to strong generic compression under matched resource budgets. The evaluation separates ordinary task performance from non-compensatory critical integrity violations and prespecifies positive, negative, and inconclusive outcomes. The work concerns the preservation of attributable, temporally scoped, and epistemically qualified records. It makes no claim about consciousness, subjective survival, numerical identity, or the completeness of the six dimensions.

## 1. Introduction

Long-lived human-AI systems accumulate more than facts.

They accumulate decisions and reversals, direct statements and summaries, role-dependent relationships, uncertainty, corrections, imported documents, model-generated interpretations, and claims whose truth status changes over time.

Memory systems optimized primarily for semantic similarity, recency, relevance, compression ratio, or token economy can preserve topical content while losing distinctions required for trustworthy longitudinal reconstruction.

A record may preserve that a decision occurred while losing whether it was later reversed.

It may preserve the content of a statement while losing who made it.

It may preserve a later synthesis while presenting it as the original source.

It may retain a historical belief while losing that the person no longer holds it.

It may answer an unresolved question with a plausible completion because the system is optimized to answer rather than preserve uncertainty.

These are not merely retrieval errors. They are structural continuity errors.

This paper asks:

> **Under finite and explicitly measured storage, retrieval, prompt, and output budgets, does a continuity-aware compression intervention preserve more continuity-relevant structure than strong generic baselines?**

The claim is deliberately narrower than the historical ambitions that motivated the broader Legacy.GI and Rendered Reality research program.

The experiment does not test whether a digital representation is the same person as its source.

It does not test whether consciousness can be transferred.

It does not test subjective survival.

It tests whether a specified representation preserves six observable forms of longitudinal structure more reliably under matched resource constraints.

### 1.1 Contribution boundary

Existing memory and long-context benchmarks already evaluate information extraction, multi-session reasoning, temporal reasoning, knowledge updates, and abstention. LongMemEval is a particularly relevant example.[1][2]

Accordingly, this work does not claim priority over temporal reasoning or knowledge-update evaluation.

The proposed contribution is:

> **A joint structure-preservation instrument combining decision state, correction lineage, temporal scope, relational roles, evidence provenance, epistemic status, and non-compensatory integrity failures, evaluated through controlled compression under matched resource budgets.**

Whether that combination is sufficiently novel for a specific venue remains an empirical literature-review question rather than a project assertion.

## 2. Related Work

### 2.1 Long-term conversational memory

LongMemEval and related benchmarks establish that long-running assistants can be evaluated on tasks including information extraction, temporal reasoning, multi-session reasoning, knowledge updates, and abstention.[1][2]

Continuity Intelligence overlaps those areas but introduces a different emphasis: the preservation of structural relationships among states, corrections, provenance, roles, and unresolved knowledge under compression.

### 2.2 Rate-distortion theory

Classical rate-distortion theory formalizes the tradeoff between representational rate and expected distortion.[3]

The conceptual analogy is useful for continuity-aware memory because a longitudinal record must preserve some features more faithfully than others under finite representation budgets.

However, empirical token counts are not automatically equivalent to information-theoretic rate.

This paper therefore uses rate-distortion theory as a formal framing while separating it from the operational finite-budget experiment.

### 2.3 Provenance

The W3C PROV family distinguishes provenance relations including attribution, derivation, quotation, revision, and primary source.[4][5]

Continuity Intelligence builds on the same general principle: source lineage must survive transformation.

The experiment extends provenance with project-specific but independently measurable axes for adoption state, epistemic state, correction lineage, and temporal applicability.

### 2.4 Longitudinal HCI and archival integrity

Longitudinal interactive systems face a problem familiar to archives: later interpretation can overwrite distinctions present in the original record.

Continuity Intelligence treats provenance, supersession, and uncertainty as first-class evaluation targets rather than background metadata.

## 3. Problem Formulation

Let (X) denote a longitudinal human-AI corpus.

Let (Z_c) denote a continuity-aware compressed representation.

Let (Z_g) denote a strong generic compressed representation.

Let (Q) denote held-out continuity probes.

Let (F_k(Z,Q)) denote performance on continuity dimension (k).

### 3.1 Theoretical framing

A multi-dimensional rate-distortion framing can be written as:

[
R(mathbf D)
=
inf_{p(zmid x)}
I(X;Z)
]

subject to:

[
mathbb E[d_k(X,hat X(Z))]le D_k,
qquad k=1,ldots,6.
]

Here (hat X(Z)) is the task-relevant reconstruction supported by representation (Z), not necessarily a reconstructed transcript.

### 3.2 Empirical study

The experiment instead estimates:

[
Delta_k(mathbf B)
=
mathbb E[F_k(Z_c,Q)-F_k(Z_g,Q)]
]

under:

[
mathbf B=
(B_{stored}, B_{retrieved}, B_{prompt}, B_{output}).
]

The study therefore adopts the following boundary:

> **We estimate task-conditioned distortion under explicitly measured resource constraints; we do not claim to recover the corpus's information-theoretic rate-distortion function.**

## 4. Hypothesis and Decision Rule

### 4.1 Primary hypothesis

> **The specified continuity-aware intervention retains more of the six continuity structures than the frozen strongest generic baseline at equal measured resource budgets.**

This is a claim about a specified intervention.

It is not a claim about every possible continuity-aware method.

### 4.2 Vector rule

Primary success requires all of the following:

1. superiority beyond a prespecified minimum meaningful effect on a frozen primary subset of dimensions;
2. non-inferiority within frozen margins on the remaining confirmatory dimensions;
3. passage of the Critical Integrity criterion;
4. reliability-eligible annotation for every included dimension;
5. matched-budget compliance;
6. blinded scoring;
7. no material protocol deviation.

The exact primary superiority subset and dimension-specific minimum effects must be frozen before the relevant pilot/confirmatory run.

### 4.3 Outcome classes

**Positive:** superiority, non-inferiority, integrity, reliability, and budget criteria are satisfied.

**Negative:** the preregistered analysis provides substantive evidence of inferiority, excludes the minimum effect required for the claim in the unfavorable direction, or establishes a prespecified integrity failure.

**Inconclusive:** success is not established, but uncertainty remains too large to support a substantive negative conclusion, or the instrument is insufficiently reliable.

This distinction prevents a common error in falsification language: a nonsignificant or underpowered result does not automatically demonstrate absence of effect.

"No post-hoc rescue" prohibits changing the success definition after results are observed. It does not convert uncertainty into a negative finding.

## 5. Continuity-Aware Compression Intervention

The intervention is specified separately in `CONTINUITY_AWARE_COMPRESSION_INTERVENTION_V0_1.md`.

Each record contains independent fields for:

- assertion/event content;
- speaker;
- subject;
- relevant role;
- recorded time;
- valid-time interval;
- evidence type;
- source pointer;
- origin;
- adoption status;
- epistemic state;
- correction/supersession links;
- relationship links where supported;
- sensitivity.

The compressor must define:

- source normalization;
- continuity-link construction;
- salience scoring;
- merge rules;
- conflict rules;
- drop ordering under budget pressure.

Continuity-aware may not be assigned retrospectively to whichever representation performs best.

## 6. Resource Budgets

All method-specific metadata counts.

The budget vector is:

[
mathbf B=(B_{stored},B_{retrieved},B_{prompt},B_{output}).
]

### 6.1 Stored budget

Includes record text, labels, timestamps, graph edges, provenance, uncertainty markers, correction links, and any other persistent representation overhead.

### 6.2 Retrieved budget

Includes all representation content fetched for a probe.

### 6.3 Prompt budget

Includes system instructions, answer instructions, schema instructions, retrieved evidence, and condition-specific control text.

### 6.4 Output budget

Uses the same tokenizer and hard cap across compared conditions.

Hard caps and actual usage are reported.

Truncation or retrieval failures remain part of the result rather than being silently repaired.

## 7. Experimental Controls

For the primary representation comparison:

- same source corpus;
- same compression model where applicable;
- same answering model;
- same decoding settings;
- same answer instructions;
- different representation objectives or schemas;
- all method-specific metadata counted;
- primary generic comparator selected on development data only.

Answering-policy changes are tested as separate factorial conditions.

This distinguishes a representation advantage from a prompt advantage.

## 8. Six Operational Dimensions

The dimensions form a measurement ruler.

They are not a complete ontology of a person.

### Decision fidelity

Preserves what was chosen, who had decision authority, relevant constraints or rationale, and whether the choice remained in force.

### Correction fidelity

Preserves prior state, correction event, authority, supersession lineage, new state, and the historical fact that the previous state existed.

### Temporal fidelity

Preserves ordering, duration where material, state-at-time, and current/historical or proposed/implemented distinctions.

### Relational fidelity

Preserves source-supported relationship structure and role boundaries without substituting one person, role, or relation for another.

### Provenance fidelity

Preserves origin, evidence path, transformation lineage, authorship where material, and source pointers.

### Uncertainty fidelity

Preserves UNKNOWN, contested, unresolved, and confidence-bounded states instead of smoothing them into unsupported certainty.

## 9. Provenance, Truth, and Adoption

The instrument separates five axes.

### Origin

Human statement, AI synthesis, model inference, quoted third party, imported source, or unknown.

### Evidence

Transcript, attestation, external source, code/commit receipt, derivative summary, or missing evidence.

### Adoption

Candidate, adopted, superseded, rejected, or unspecified.

### Epistemic state

Supported, uncertain, contested, or unknown.

### Temporal scope

The interval during which an assertion or decision applied when known.

Three authority rules follow:

> **For attribution and historical utterance, primary records govern over derivative summaries.**

> **For current adopted position, explicit authorized corrections govern within their stated scope.**

> **For external factual truth, evidence authority is assessed separately from utterance provenance.**

These rules prevent the system from confusing "the person said it," "the person currently believes it," and "the external evidence supports it."

## 10. Critical Integrity Set

Critical integrity failures are non-compensatory.

The primary families include:

- wrong person;
- false authorship;
- UNKNOWN converted to certainty;
- generated synthesis presented as historical memory;
- source fabrication.

A strong average recall score cannot compensate for fabricated attribution.

Each critical item must preregister:

- prohibited failure;
- evidence;
- adjudication rule;
- ambiguity handling;
- acceptance rule;
- uncertainty reporting.

Routine fidelity scores are reported separately from integrity status.

## 11. Benchmark Defenses

The benchmark must not succeed merely because the system recognizes its own vocabulary.

Required defenses include:

- independently authored held-out probes;
- questions phrased without dimension labels;
- synthetic cases with no public project footprint;
- blinded grading;
- source-grounded answer keys;
- equally structured non-continuity-specific baseline;
- prompt-only baseline;
- correction-link ablation;
- provenance-field ablation;
- temporal-scope ablation;
- full-history reference as a diagnostic, not equal-budget competitor.

## 12. Experimental Unit and Analysis

Conditions are paired within independent longitudinal corpora.

Multiple probes from one corpus are clustered observations.

The final confirmatory model must account for within-corpus dependence rather than treating every question as an independent replication.

The preregistered analysis should report:

- per-dimension effects;
- corpus-level paired effects;
- confidence intervals;
- Critical Integrity outcomes;
- catastrophic-error rates;
- UNKNOWN preservation;
- correction-chain completeness;
- provenance-attribution errors;
- current/historical collapse;
- actual budget use.

The final statistical model and power target remain to be frozen after calibration/pilot evidence and before confirmatory testing.

## 13. Calibration

The instrument uses a maximum of three calibration rounds.

Each round contains 48 fresh probes, eight per dimension.

Primary reliability metric:

- Krippendorff's alpha for ordinal scores.

Secondary metric when exactly two raters are used:

- weighted Cohen's kappa.

Also report:

- raw agreement;
- per-dimension agreement;
- Critical Integrity agreement.

Terminal reliability states:

- alpha >= 0.80: confirmatory-eligible;
- 0.67 <= alpha < 0.80: pilot-grade only;
- alpha < 0.67: not reliably measurable for this hypothesis version.

No fourth round is allowed for the same version.

## 14. Reproducibility Packet

A valid public result should include:

- frozen protocol hash;
- corpus manifest;
- eligibility rules;
- model/provider/version metadata;
- budget definitions and measurements;
- probe-generation procedure;
- partition records;
- annotator handbook;
- qualification records;
- calibration statistics;
- raw outputs;
- per-probe scores;
- catastrophic-error labels;
- Critical Integrity results;
- analysis code;
- effect-size calculations;
- deviations log;
- negative and null results;
- replication packet where private sources cannot be public.

A paragraph saying "it worked" is not a result.

## 15. Falsification

The tested implementation loses support when the locked design demonstrates that:

- the generic comparator performs materially better;
- the intervention cannot meet the minimum effect required by the claim;
- Critical Integrity fails;
- a protected dimension is materially harmed;
- the prompt-only condition explains the apparent gain;
- an equally structured generic schema explains the apparent gain;
- blinded scoring removes the advantage;
- the advantage depends on leakage;
- uncounted metadata explains the advantage;
- only project-specific terminology produces the effect;
- independent corpora fail to replicate it.

A failed Spine v0 does not falsify every conceivable continuity-aware method.

It does falsify the claim that Spine v0 succeeded under the frozen conditions.

## 16. Non-Claims

This work does not establish:

- consciousness upload;
- subjective survival;
- continued experience;
- numerical identity between source person and reconstruction;
- post-biological immortality;
- a validated biological threshold for historical project quantities such as 0.02 ms;
- sentience or personhood;
- completeness of the six dimensions;
- validity of every historical Legacy.GI formulation;
- generalization from one private N=1 corpus to a population.

## 17. Limitations

The measurement instrument itself may be wrong.

The six dimensions may overlap.

A dimension may fail calibration.

Synthetic corpora may improve reproducibility while reducing ecological validity.

Private longitudinal corpora may increase realism while limiting external inspection.

Annotation may introduce bias.

Probe authorship may create leakage.

The representation may benefit from schema regularity rather than continuity structure.

Strong generic systems may simply win.

Those are empirical possibilities, not rhetorical problems to explain away.

## 18. Conclusion

Continuity Intelligence is proposed here as an observable preservation problem.

The question is not whether a representation contains enough facts to resemble a life.

The question is whether it preserves the distinctions required to reconstruct what changed, who said what, which state governed when, what remains uncertain, and where the evidence came from.

That claim can lose.

The instrument can fail calibration.

The continuity-aware representation can lose to generic compression.

A negative result can remain in the public record.

That possibility is not a weakness of the project.

It is the condition that makes the claim scientific.

## References

[1] Wu, D. et al. *Benchmarking Chat Assistants on Long-Term Interactive Memory (LongMemEval).* arXiv:2410.10813. https://arxiv.org/abs/2410.10813

[2] LongMemEval project page. https://xiaowu0162.github.io/long-mem-eval/

[3] *Rate-Distortion Theory in Coding for Machines and its Applications.* https://arxiv.org/html/2305.17295v2

[4] W3C. *PROV-DM: The PROV Data Model.* https://www.w3.org/TR/prov-dm/

[5] W3C. *PROV-O: The PROV Ontology.* https://www.w3.org/TR/prov-o/

## Appendix roadmap

Future manuscript revisions should append:

- compressor pseudocode and exact drop ordering;
- budget-counting code;
- Critical Integrity rubric;
- probe-authorship/leakage protocol;
- full annotator handbook;
- calibration records;
- synthetic-corpus schema;
- preregistration;
- results, including null or negative outcomes.
