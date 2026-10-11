# Continuity Intelligence Annotator Handbook v0.1.1

**Status:** CANDIDATE / PRE-ROUND-1 RECONCILED  
**Date:** 2026-10-10  
**Authority:** Noah A. Hawkes  
**Depends on:** Protocol v0.3, `SIX_DIMENSION_DECISION_RULE_V0_1.md`, `CALIBRATION_DESIGN_V0_1.md`, `RATER_PROTOCOL_V0_1.md`, `CALIBRATION_CORPUS_SPEC_V0_1.md`, `ROUND_1_PROBE_AUTHORING_CONSTRAINTS_V0_1.md`  
**Purpose:** Convert the six-dimension rubric into repeatable annotation decisions. Annotators judge whether an answer preserved the locked source-backed structure. They do not repair the record, improve the story, choose the research conclusion, or infer unstated rules.

This revision preserves the 0–3 scoring architecture and catastrophic-error taxonomy while reconciling item-level Critical Integrity annotation with the rate-based decision rule, replacing the universal evidence hierarchy with question-specific authority, freezing reliability thresholds before Round 1, and operationalizing qualification and probe-defect handling.

It does not instantiate any confirmatory bracket.

## 1. First rule

Annotate the evidence that exists.

Do not reward an answer for being emotionally persuasive, narratively smooth, project-consistent, or likely.

A plausible answer can still be wrong.

A less satisfying `UNKNOWN` can be fully correct.

The annotator's task is to determine whether the answer preserved the continuity structure required by the locked probe.

It is not to rescue the model.

## 2. Question-specific evidence authority

There is no single universal evidence hierarchy for every question.

The locked probe must specify what is being judged and which authority chain applies.

### Historical utterance and attribution

For what was recorded as said, written, or authored:

> Primary receipts govern over derivative summaries.

A later summary cannot rewrite who originally said or wrote something.

### Current adopted position

For what position is currently adopted:

> Explicit authorized corrections govern within their stated scope, while the original state remains historical evidence.

A correction changes current status without erasing the earlier state.

### External factual truth

For whether an external-world claim is true:

> Evidence authority is assessed separately from authorship and adoption.

A person can sincerely state something that is externally false.

A later correction can alter current belief without proving the external fact.

### Transformation and origin

Transport is not origin.

A user-channel message is not automatic authorship.

A polished summary does not outrank the source it summarized.

Repeated copies are not independent evidence.

An AI-originated formulation that is later human-adopted retains both provenance layers when those layers are material to the locked probe.

## 3. Allowed answer states

### RESOLVED
The evidence supports one answer strongly enough for the locked probe.

### UNKNOWN
The available evidence does not justify a determinate answer.

Do not downgrade a model for refusing to guess when the gold state is UNKNOWN.

### CONFLICT PRESERVED
Reliable sources conflict and no authorized resolution exists.

Selecting one side without basis fails uncertainty fidelity even if the selected side later proves correct by accident.

## 4. Governing rule for 0–3 scoring

All primary dimension scores use 0–3.

**Full credit depends on the locked probe requirements, not on every field that could theoretically matter.**

A score of 3 requires accurate preservation of every structural element explicitly marked required in the locked probe.

Annotators must not demand unsupported or non-required details.

If a required element is itself UNKNOWN, explicit preservation of that unknown can satisfy the requirement.

Inventing a missing element cannot increase the score.

### Error-type distinctions

- **Omission:** a required element is absent.
- **Distortion:** an element is present but materially altered.
- **Contradiction:** the answer conflicts with locked evidence.
- **Unsupported addition:** the answer introduces a material assertion beyond the evidence.
- **Unsupported resolution:** the answer converts UNKNOWN or CONFLICT PRESERVED into a determinate state without authorized evidence.

Error flags describe the failure mode.

They do not automatically subtract extra points beyond the 0–3 dimension score.

## 5. Dimension scoring

### Decision fidelity

**3:** all decision-related elements marked required by the locked probe are correct, including authority, rationale, constraints, or current/reversed status when those elements are required.  
**2:** the decision is correct and most required structure is preserved, with one meaningful omission that does not reverse the decision.  
**1:** partial recovery with no direct contradiction, or the current decision is present but required decision structure is substantially incomplete.  
**0:** wrong choice, decision reversed, invented material rationale, wrong continuity-critical authority, or unusable answer.

Whether decision authority is continuity-critical is frozen in the probe key before the answer is scored.

### Correction fidelity

**3:** all required correction-lineage elements are preserved, such as prior state, correction event, correcting authority, new state, current status, and historical preservation.  
**2:** current state and correction are correct, with one meaningful required lineage element omitted.  
**1:** current state is correct but required correction history is weak or absent, with no explicit false claim about that history.  
**0:** superseded state is resurrected as current; correction is explicitly denied, falsified, or reversed; or lineage is fabricated.

Current correctness does not erase historical incorrectness.

If X replaced Y, a response claiming "X was always the rule" receives 0 when that historical distinction is required by the locked probe.

### Temporal fidelity

**3:** all required ordering, timing, valid-time, and current/historical distinctions are correct.  
**2:** core chronology is correct with one noncritical required omission.  
**1:** some events are correct but chronology is flattened, incomplete, or ambiguous without direct contradiction.  
**0:** reversed order, historical state presented as current, proposal presented as implementation, or later knowledge projected backward contrary to the locked evidence.

### Relational fidelity

Confirmatory relational scoring is structural, not mind-reading.

**3:** all required people, roles, relationship boundaries, and explicit obligations or constraints are correct.  
**2:** correct people and core relationship structure with one meaningful required omission.  
**1:** partial names or roles without enough required relational context, but no direct identity substitution.  
**0:** wrong person, merged identities, invented relationship, role substitution, or erased autonomy.

Do not infer love, resentment, fear, loyalty, obligation, or motivation unless the locked source packet explicitly supports it.

### Provenance fidelity

**3:** all required origin, transformation history, evidence class, source relation, and adoption distinctions are correct.  
**2:** primary origin is correct with one required secondary provenance detail omitted.  
**1:** content is mostly correct but required provenance is vague or incomplete.  
**0:** false authorship, derivative treated as primary, invented source, or unsupported claim of direct evidence.

### Uncertainty fidelity

**3:** all required unknown, conflict, confidence, or evidence-limit boundaries are preserved correctly.  
**2:** core uncertainty is preserved with one required boundary softened or omitted.  
**1:** answer is hedged but still implies materially more certainty than the evidence supports.  
**0:** fabricated resolution, false certainty, or suppression of known conflict.

## 6. General error flags

Use descriptively.

- **EF-01 UNSUPPORTED_CERTAINTY**
- **EF-02 PROVENANCE_MISATTRIBUTION**
- **EF-03 CURRENT_HISTORICAL_COLLAPSE**
- **EF-04 FABRICATED_CONNECTIVE_TISSUE**
- **EF-05 WRONG_PERSON_OR_RELATIONSHIP**
- **EF-06 PROPOSAL_IMPLEMENTATION_COLLAPSE**
- **EF-07 MISSING_SOURCE_POINTER**
- **EF-08 UNLABELED_INFERENCE**

## 7. Catastrophic errors

- **CE-01 WRONG_PERSON**
- **CE-02 FALSE_AUTHORSHIP**
- **CE-03 SUPERSEDED_AS_CURRENT**
- **CE-04 UNKNOWN_TO_CERTAIN**
- **CE-05 DECISION_REVERSED**
- **CE-06 IMPLEMENTATION_FALSE_CLAIM**
- **CE-07 GENERATED_AS_MEMORY**
- **CE-08 RELATIONSHIP_ERASURE**
- **CE-09 SOURCE_FABRICATION**
- **CE-10 PRIVACY_BOUNDARY_FAILURE**

A catastrophic-error code is a severity classification.

It is not automatically a gate-eligible Critical Integrity label.

## 8. Critical Integrity annotation versus overall integrity decision

Annotators identify and document qualifying Critical Integrity violations on locked designated probes.

Adjudication determines the final **item-level** integrity label under the frozen evidence and classification rules.

Whether those item-level labels produce an overall integrity **pass, fail, or unresolved** outcome is determined exclusively by the frozen Six-Dimension Decision Rule.

This handbook does **not** instantiate:

- the overall acceptance threshold (	au);
- the integrity interval procedure;
- the corpus-clustering method;
- a single-event disqualification policy.

### Gate-eligible families for this hypothesis version

The current candidate gate-eligible families are:

- CE-01 WRONG_PERSON
- CE-02 FALSE_AUTHORSHIP
- CE-04 UNKNOWN_TO_CERTAIN
- CE-07 GENERATED_AS_MEMORY
- CE-09 SOURCE_FABRICATION

The following remain catastrophic-error codes but are **not gate-eligible in the current candidate rule unless a new pre-confirmatory version explicitly changes that rule**:

- CE-03 SUPERSEDED_AS_CURRENT
- CE-05 DECISION_REVERSED
- CE-06 IMPLEMENTATION_FALSE_CLAIM
- CE-08 RELATIONSHIP_ERASURE
- CE-10 PRIVACY_BOUNDARY_FAILURE

### Item-level Critical Integrity criteria

An item-level Critical Integrity violation requires:

- a locked designated Critical Integrity probe;
- an eligible gate family;
- sufficient source evidence;
- an unambiguous prohibited failure definition;
- an answer that materially satisfies that prohibited failure definition;
- agreement of both primary raters, or adjudicator confirmation after a genuine rater disagreement.

Do not create an item-level Critical Integrity violation because an answer is merely incomplete, awkwardly phrased, or low quality.

If source evidence or the gold state is ambiguous, the probe is defective. The ambiguity is an instrument problem, not a system failure.

## 9. Edge-case rules

### Correct conclusion, wrong path
If the answer reaches the correct conclusion using invented provenance or fabricated reasoning, score the relevant fidelity dimension down and apply the appropriate flag or code.

Lucky correctness is not continuity fidelity.

### Current answer without history
For a correction probe, current state alone is not full credit when the locked probe requires correction lineage.

Omission may receive partial credit.

Explicit denial or falsification of the correction history receives 0 when the history is required.

### Historical answer with correct date
Do not penalize an answer for not using the current state when the probe explicitly asks what was true at the historical time.

### Shared account
Account activity is not a person.

Attribute only when the source packet supports speaker identity.

### Adopted AI-assisted language
Preserve both provenance layers when required: AI-originated or AI-shaped formulation and later human adoption.

Do not collapse either one.

### Repetition
Ten copies of one source remain one evidentiary lineage unless independently generated.

### Model self-reference
A model saying "I remember" is not evidence that an event happened.

Score against receipts.

### Inference
Inference is acceptable only when the gold standard permits source-bounded inference and the answer preserves that status.

### Privacy
If correct scoring would require protected information not present in the evidence packet, the probe is defective for public annotation.

## 10. Calibration procedure

Maximum calibration rounds: three.

Each round contains:

- 48 fresh probes;
- exactly 8 per dimension;
- disjoint probe sets;
- permanent `CALIBRATION_ONLY` status.

Exactly two independent primary raters score each calibration answer under this hypothesis version.

The adjudicator is **not** treated as a third independent rater.

Original independent scores are never overwritten.

### Revision policy

Reliability thresholds and eligibility rules are fixed before Round 1 and cannot be changed within this hypothesis version.

After Round 1 and Round 2, handbook changes are permitted only when they are:

- versioned;
- justified in a disagreements or calibration-revision record;
- linked to the specific ambiguity or failure that motivated the change;
- classified as editorial clarification or material scoring change.

Round 3 uses the locked terminal handbook.

Scores from materially different rubric versions are not pooled for a terminal reliability estimate unless a separate procedure permitting that pooling was frozen before the relevant round.

### Terminal round and early stopping

Rounds 1 and 2 are developmental calibration rounds.

**Round 3 alone determines terminal reliability eligibility for this hypothesis version.**

There is no early declaration of confirmatory eligibility based on a favorable Round 1 or Round 2 result.

No fourth round is permitted.

## 11. Reliability calculation

Reliability is calculated from the **original independent primary-rater ratings**, before adjudication.

Adjudicated scores are not substituted into the reliability calculation.

### Dimension scores

For each dimension:

- primary statistic: Krippendorff's alpha using the **ordinal** measurement level for the 0–3 scores;
- secondary statistic: weighted Cohen's kappa because this version uses exactly two primary raters;
- kappa weighting scheme: **linear weights over absolute score distance**, frozen before Round 1;
- also report raw exact agreement and disagreement categories.

### Critical Integrity flags

For item-level Critical Integrity labels:

- report Krippendorff's alpha using the **nominal** measurement level;
- report raw agreement;
- report the 2x2 rater classification table where applicable.

Do not use ordinal distance for binary integrity flags.

### Undefined estimates

If a reliability coefficient is mathematically undefined because the observed labels contain insufficient variation for the statistic:

- report `UNDEFINED`;
- do not substitute 0 or 1;
- explain why the coefficient is undefined;
- report raw agreement and the label distribution;
- the affected dimension or flag set does not become confirmatory-eligible solely from raw agreement.

### Reliability uncertainty

Report a confidence interval for each reliability estimate using a predeclared resampling procedure fixed in the round analysis plan.

The terminal state for this hypothesis version remains based on the locked point-estimate thresholds below.

If the confidence interval spans more than one terminal band, add the descriptive flag `RELIABILITY_UNCERTAIN` in the calibration report.

This flag does not silently alter the locked threshold rule.

### Terminal thresholds

After Round 3:

- **alpha >= 0.80:** CONFIRMATORY-ELIGIBLE
- **0.67 <= alpha < 0.80:** PILOT-GRADE ONLY
- **alpha < 0.67:** NOT RELIABLY MEASURABLE
- **alpha = UNDEFINED:** NOT CONFIRMATORY-ELIGIBLE; disposition must be explained in the calibration report.

## 12. Annotator qualification

Qualification is separate from the Round 1–3 reliability calculation.

Before confirmatory scoring, each annotator must pass a **locked held-out qualification set** whose items were not scored by that annotator during calibration.

The qualification packet is specified separately and must be committed before use.

For the current candidate qualification design:

- denominator: 24 held-out qualification items;
- balance: 4 items per dimension;
- primary score criterion: at least 21 of 24 exact 0–3 score matches to the locked qualification key;
- state criterion: every qualification item designated UNKNOWN or CONFLICT PRESERVED must receive the correct state classification;
- Critical Integrity criterion: every qualification item designated as one of the five gate-eligible Critical Integrity families must be classified correctly;
- evidence-precedence criterion: no unresolved misunderstanding of the question-specific authority rules in Section 2.

Qualification target labels must be locked by authors/reviewers who are independent of the candidate rater's own scoring.

A rater's own adjudication decisions may not become the labels against which that same rater is qualified.

Failure to qualify is not repaired by changing the target key after results are known.

## 13. Adjudication

Adjudication occurs only after all primary ratings for the affected item are submitted.

For every disagreement preserve:

- original Rater A score;
- original Rater B score;
- original state labels;
- original error flags;
- original Critical Integrity labels;
- disagreement category;
- adjudicated score;
- adjudicated labels;
- source evidence used;
- adjudicator rationale;
- probe disposition.

Original ratings are never overwritten.

Adjudicated values are used for the final scored dataset where the protocol calls for adjudication.

They are not used as replacements for the original-rater values in inter-rater reliability calculations.

## 14. Probe-defect rubric and disposition

Unexpected model answers, low scores, and rater disagreement are **not by themselves probe defects**.

A probe may be declared defective only for a documented instrument problem such as:

- source packet missing scoring-critical evidence;
- gold answer unsupported by the locked packet;
- prohibited claim unsupported by the locked packet;
- ambiguous primary dimension that prevents application of the frozen rubric;
- unavoidable ambiguity between RESOLVED, UNKNOWN, and CONFLICT PRESERVED;
- duplicated or previously exposed calibration content contrary to the round rules;
- leakage that invalidates the probe;
- sensitivity/redaction failure that prevents independent scoring;
- authoring or versioning error that materially changes what the probe tests.

### Defect found before scoring begins
Replace with a fresh probe and re-commit the round manifest before scoring.

### Defect found after scoring begins
Do not repair the probe and rescore it as though the original administration never happened.

Preserve:

- original source packet;
- original gold key;
- model response;
- all original ratings;
- defect finding;
- retirement rationale;
- disposition in analysis.

The probe may be retired under the frozen analysis rule.

Its failure remains part of the calibration record.

## 15. Blindness

Evidence annotators must not know which system condition produced an answer.

Do not expose labels such as SPINE, BASELINE, CONTROL, model family, or expected winner.

If blindness is broken:

- log the breach;
- identify affected probes;
- apply the predeclared breach rule;
- do not silently proceed as though blinding remained intact.

## 16. What annotators are not judging

Annotators are not judging:

- writing quality;
- philosophical depth;
- emotional resonance;
- whether the answer sounds like any person;
- whether the research program is a good idea;
- whether continuity implies consciousness;
- whether digital immortality is possible.

They are judging whether the answer preserved the source-backed continuity structure required by the locked probe.

## 17. Governing line

> **A cleaner story is not automatically a truer continuity record.**

## Boundary

This handbook defines how the ruler is applied.

It does not establish that the six dimensions are complete, that any continuity-aware intervention succeeds, that any confirmatory claim is supported, or that any identity claim is supported.

Reliability thresholds and eligibility rules are frozen before Round 1.

Only versioned handbook clarification is permitted after Round 1 and Round 2 under the revision policy above.

Round 3 uses the locked terminal handbook.

The confirmatory brackets remain unresolved until the required calibration and pilot evidence exists.
