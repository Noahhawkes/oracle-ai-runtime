# Continuity Intelligence Rater Protocol v0.1

**Status:** CANDIDATE RATER PROTOCOL  
**Date:** 2026-10-10  
**Applies to:** Calibration of the six-dimension Continuity Intelligence ruler

## 1. Roles

Calibration uses three distinct roles:

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

## 9. Calibration rounds

Use exactly:

- maximum 3 rounds;
- 48 probes per round;
- 8 probes per dimension per round.

### Round 1

Independent scoring.

Then calculate reliability and categorize disagreements.

Handbook clarification is allowed after Round 1.

### Round 2

Fresh 48-probe set.

Independent scoring under revised handbook.

Handbook clarification is allowed after Round 2.

### Round 3

Fresh locked 48-probe set.

No further rubric revision for the same hypothesis version.

Round 3 determines terminal reliability state.

## 10. Reliability statistics

Primary:

- Krippendorff's alpha for ordinal scores by dimension.

Secondary when exactly two raters:

- weighted Cohen's kappa.

Also report:

- raw agreement;
- confusion/disagreement patterns;
- Critical Integrity flag agreement;
- number of defective or retired probes.

## 11. Terminal reliability states

After Round 3:

- **alpha >= 0.80:** CONFIRMATORY-ELIGIBLE
- **0.67 <= alpha < 0.80:** PILOT-GRADE ONLY
- **alpha < 0.67:** NOT RELIABLY MEASURABLE

No fourth calibration round is permitted for the same hypothesis version.

A failed dimension is preserved as a failed measurement attempt.

## 12. Rater qualification

Before confirmatory scoring, each rater must achieve:

- at least 85% agreement with adjudicated calibration labels;
- no unresolved evidence-class misunderstanding;
- no severe Critical Integrity misunderstanding;
- demonstrated correct handling of UNKNOWN and CONFLICT PRESERVED.

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
