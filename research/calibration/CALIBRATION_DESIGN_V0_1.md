# Continuity Intelligence Calibration Design v0.1

**Status:** CANDIDATE DESIGN  
**Date:** 2026-10-10  
**Depends on:**
- `research/protocols/ANNOTATOR_HANDBOOK.md`
- `research/protocols/SIX_DIMENSION_DECISION_RULE_V0_1.md`
- `research/calibration/CALIBRATION_CORPUS_SPEC_V0_1.md`
- `research/calibration/RATER_PROTOCOL_V0_1.md`

## 1. Objective

Determine whether the six-dimension measurement ruler can be applied reliably by independent human raters before any confirmatory thresholds are instantiated.

Calibration is a measurement study.

It is not a test of the Light Compression Hypothesis.

## 2. Fixed round structure

Maximum rounds: 3.

Per round:

- 48 fresh probes;
- 8 decision;
- 8 correction;
- 8 temporal;
- 8 relational;
- 8 provenance;
- 8 uncertainty.

Round probe sets are disjoint.

## 3. Evidence composition

Candidate initial balance:

- 24 public-safe project-derived probes;
- 24 synthetic probes;
- 4 + 4 per dimension.

This balance is frozen in the round manifest before scoring.

## 4. Rater structure

Use:

- 2 independent primary raters;
- 1 adjudicator.

Raters are blinded to condition identity.

No calibration answer is discussed before both primary ratings are submitted.

## 5. Round 1 purpose

Round 1 asks:

- Are dimension definitions understandable?
- Which distinctions generate disagreement?
- Are source packets sufficient?
- Are Critical Integrity examples recognizable?
- Are UNKNOWN and CONFLICT PRESERVED handled consistently?

Round 1 may produce handbook revisions.

It does not produce confirmatory eligibility.

## 6. Round 2 purpose

Round 2 tests whether the revised handbook reduced ambiguity on a fresh set.

Round 2 may produce the final handbook clarifications for this hypothesis version.

## 7. Round 3 purpose

Round 3 is locked.

No further rubric revision is permitted for the same hypothesis version.

Round 3 assigns terminal dimension states.

## 8. Required outputs per round

For every dimension report:

- Krippendorff's alpha;
- weighted Cohen's kappa if exactly two raters;
- raw agreement;
- score-distribution table;
- disagreement-category counts;
- defective-probe count;
- Critical Integrity agreement where applicable.

Also report:

- total probes;
- retired probes;
- blinding breaches;
- missing responses;
- adjudication count;
- handbook version;
- manifest commit.

## 9. Decision thresholds

After Round 3:

### Confirmatory-eligible

`alpha >= 0.80`

### Pilot-grade only

`0.67 <= alpha < 0.80`

### Not reliably measurable

`alpha < 0.67`

A dimension below 0.80 does not silently remain in the confirmatory endpoint.

If the confirmatory hypothesis changes because a dimension fails reliability, create a new hypothesis version and preserve the failed calibration.

## 10. What remains unresolved after this design

This calibration design does not instantiate:

- superiority set;
- non-inferiority set;
- dimension-specific delta values;
- non-inferiority margins;
- confirmatory alpha;
- simultaneous confidence interval method;
- final clustering model;
- Critical Integrity tau;
- confirmatory missing-response rule;
- corpus weighting for the confirmatory estimand;
- multiplicity procedure.

Those remain bracketed until the appropriate calibration/pilot evidence exists and a preregistration freeze is created.

## 11. Round 1 readiness checklist

Round 1 may begin only after:

- 48 eligible probes exist;
- each source packet is inspectable;
- each gold answer is locked;
- all required/prohibited elements are specified;
- probe IDs are unique;
- sensitivity review is complete;
- two primary raters are identified;
- one adjudicator is identified;
- raters complete orientation;
- rater conflicts/provenance are recorded;
- Round 1 manifest is committed.

## 12. Preservation rule

If the ruler fails, record the failure.

Do not make the dimension easier after Round 3.

Do not reinterpret a failed dimension as exploratory success.

Do not discard disagreement because it is inconvenient.

Calibration is where the project proves that its ruler can survive another human mind.
