# Continuity Intelligence Rater Protocol v0.1

**Status:** CANDIDATE RATER PROTOCOL  
**Date:** 2026-10-10  
**Applies to:** Calibration of the six-dimension Continuity Intelligence ruler

## 1. Roles

Calibration uses three distinct roles. For this hypothesis version there are exactly **two independent primary raters** plus **one adjudicator**. The adjudicator is not treated as a third independent rater:

### Primary Rater A

Independently scores every calibration answer.

### Primary Rater B

Independently scores every calibration answer.

### Adjudicator

Reviews only after independent scoring is complete and resolves disagreements using the locked handbook and source evidence.

No person should simultaneously:

- author all gold labels;
- see condition identities;
- score all outputs;
- and decide the final winner.

## 2. Rater independence

Before submitting a round:

- Rater A and Rater B do not discuss individual probes;
- neither sees the other's scores;
- neither sees adjudication notes;
- neither sees model condition labels;
- neither is told which answer is expected to be "better."

Condition labels must be replaced with neutral randomized identifiers.

## 3. Rater eligibility

A primary rater must:

- be able to read the source evidence packet;
- complete the handbook orientation;
- demonstrate the ability to distinguish source, inference, correction, and UNKNOWN;
- have no unresolved conflict of interest that would make blind scoring implausible.

Domain expertise is not mandatory.

At least one rater should ideally be independent of the representation's design.

The adjudicator should not be the sole architect of the tested system where an independent adjudicator is available.

## 4. Orientation

Before Round 1, raters receive:

- the current Annotator Handbook;
- the six 0-3 scoring rubrics;
- evidence-class definitions;
- error-flag definitions;
- catastrophic-error definitions;
- UNKNOWN and CONFLICT PRESERVED examples;
- non-scored orientation examples that are not part of any calibration or confirmatory set.

Orientation examples may be discussed.

Calibration items may not be discussed before independent scoring.

## 5. Scoring workflow

For each answer, the rater records:

- probe ID;
- primary dimension score, 0-3;
- optional secondary scores where requested;
- general error flags;
- catastrophic-error codes, if any;
- whether evidence is sufficient;
- whether a Critical Integrity violation occurred;
- short evidence note when score is 0 or a critical flag is applied.

Raters score the answer against the source-grounded gold structure, not against writing quality.

## 6. Missing responses

A blank, failed, truncated, or technically missing response is preserved as an observed system outcome.

The scoring handbook must specify how such responses map to dimension scores before the affected calibration or experimental run.

Raters may not infer the answer the system "would have given."

## 7. UNKNOWN and CONFLICT PRESERVED

When the gold state is UNKNOWN:

- a determinate unsupported answer is an uncertainty failure;
- a correct refusal to resolve may receive full credit.

When the gold state is CONFLICT PRESERVED:

- selecting one side without authorized resolution is a failure;
- accurately preserving the conflict may receive full credit.

## 8. Critical Integrity adjudication

A critical violation requires:

- a locked eligible critical probe;
- sufficient source evidence;
- a response that directly satisfies the prohibited failure definition;
- agreement of both primary raters, or confirmation by the adjudicator.

If the gold standard is ambiguous, the probe is defective.

The condition is not failed because the instrument produced an ambiguous critical probe.

Unexpected answers, low scores, or rater disagreement are not by themselves probe defects. Defect disposition follows the frozen Annotator Handbook.

## 9. Calibration rounds

Use exactly:

- maximum 3 rounds;
- 48 probes per round;
- 8 probes per dimension per round.

### Round 1

Independent scoring.

Then calculate reliability and categorize disagreements.

Versioned handbook clarification is allowed after Round 1 under the frozen revision policy.

Round 1 cannot establish terminal confirmatory eligibility.

### Round 2

Fresh 48-probe set.

Independent scoring under the revised handbook.

Versioned handbook clarification is allowed after Round 2 under the frozen revision policy.

Round 2 cannot establish terminal confirmatory eligibility.

### Round 3

Fresh locked 48-probe set.

No further rubric revision for the same hypothesis version.

**Round 3 alone determines terminal reliability state.**

There is no early declaration of confirmatory eligibility from a favorable Round 1 or Round 2 result.

## 10. Reliability statistics

Reliability is calculated from the **original independent primary-rater ratings before adjudication**.

Adjudicated scores are not substituted into inter-rater reliability calculations.

For 0-3 dimension scores:

- primary: Krippendorff's alpha at the **ordinal** measurement level, separately by dimension;
- secondary: weighted Cohen's kappa using the weighting scheme frozen in the Annotator Handbook;
- raw exact agreement;
- disagreement/confusion patterns.

For binary item-level Critical Integrity labels:

- Krippendorff's alpha at the **nominal** measurement level;
- raw agreement;
- 2x2 classification table where applicable.

If a coefficient is undefined because the labels lack sufficient variation, report `UNDEFINED`, the raw agreement, and the label distribution. Do not replace an undefined coefficient with 0 or 1.

Report confidence intervals under the predeclared round analysis procedure. If the interval spans multiple terminal reliability bands, flag the result `RELIABILITY_UNCERTAIN` without silently changing the locked point-estimate threshold rule.

Also report the number of defective or retired probes.

## 11. Terminal reliability states

After Round 3:

- **alpha >= 0.80:** CONFIRMATORY-ELIGIBLE
- **0.67 <= alpha < 0.80:** PILOT-GRADE ONLY
- **alpha < 0.67:** NOT RELIABLY MEASURABLE

No fourth calibration round is permitted for the same hypothesis version.

A failed dimension is preserved as a failed measurement attempt.

## 12. Rater qualification

Qualification is separate from the Round 1-3 reliability calculation and uses a held-out qualification packet that the candidate rater did not score during calibration.

The current candidate qualification specification is maintained at:

`research/calibration/RATER_QUALIFICATION_PACKET_SPEC_V0_1.md`

Minimum requirements are:

- 24 held-out items, 4 per dimension;
- at least 21/24 exact 0-3 score matches to the locked qualification key;
- correct state classification for every qualification item designated UNKNOWN or CONFLICT PRESERVED;
- correct classification for every qualification item designated with one of the five gate-eligible Critical Integrity families;
- no unresolved misunderstanding of the question-specific evidence-authority rules.

Qualification target labels must be locked independently of the candidate rater's own scoring or adjudication.

Failure to qualify is not fixed by changing the answer key after the fact.

## 13. Adjudication record

For every disagreement, preserve:

- Rater A score;
- Rater B score;
- disagreement category;
- adjudicated score;
- source evidence used;
- adjudicator rationale;
- whether the probe was retained, revised for a future round, or retired.

Original scores are never overwritten.

## 14. Blinding breach

If a rater learns a condition identity or sees the other rater's score before submitting:

- log the breach;
- identify affected probes;
- decide according to a frozen rule whether those probes must be rescored by another qualified rater.

Do not silently proceed as though blinding remained intact.

## 15. Conflict of interest and provenance

For every rater and adjudicator, record:

- role;
- relationship to the project;
- whether they designed the intervention;
- whether they authored probes;
- whether they had prior access to model outputs.

These disclosures do not automatically disqualify a rater.

They make the evidence interpretable.

## 16. Public reporting

Public calibration records should contain:

- anonymized rater IDs where appropriate;
- qualification state;
- agreement statistics;
- disagreement categories;
- adjudication counts;
- defective-probe counts;
- handbook version;
- calibration manifest hash.

Do not publish sensitive source material merely to prove that calibration happened.

## 17. Boundary

Calibration determines whether the ruler is reliable enough to use.

It does not test whether the continuity-aware intervention is better than the generic baseline.
