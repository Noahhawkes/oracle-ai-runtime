# Continuity Intelligence Calibration Corpus Specification v0.1

**Status:** CANDIDATE CALIBRATION SPECIFICATION  
**Date:** 2026-10-10  
**Purpose:** Define the evidence pool from which calibration probes may be authored before any confirmatory thresholds are instantiated.

## 1. Scope

Calibration evaluates the **measurement ruler**, not the Light Compression Hypothesis.

The calibration corpus therefore exists to test whether independent annotators can reliably apply the six dimensions:

- decision fidelity;
- correction fidelity;
- temporal fidelity;
- relational fidelity;
- provenance fidelity;
- uncertainty fidelity.

Calibration records are never eligible for the confirmatory test set.

## 2. Corpus composition

Each calibration round contains **48 fresh probes**, exactly **8 per dimension**.

Each round should draw from two evidence classes:

1. **Public-safe project-derived records**  
   Source-backed records from the public research corpus or other public-safe project material that contain real correction, temporal, provenance, uncertainty, decision, or relational structure.

2. **Synthetic longitudinal records**  
   Fictional, source-complete continuity cases created specifically to remove project-vocabulary dependence and privacy constraints.

Recommended initial balance per round:

- 24 project-derived probes;
- 24 synthetic probes;
- 4 project-derived and 4 synthetic probes per dimension.

A different balance requires written justification before the round is locked.

## 3. Eligibility rules

A candidate calibration item is eligible only if:

- its source evidence can be shown to raters;
- its gold state can be determined without hidden private knowledge;
- its primary dimension is unambiguous enough to train or test the ruler;
- its sensitivity is public-safe or safely redacted without removing scoring-critical information;
- it was not used in a prior calibration round;
- it will not appear in the confirmatory set;
- it does not depend on project-specific jargon unless that jargon is necessary to the source itself.

## 4. Required challenge coverage

Across each 48-probe round, the probe pool should include examples of:

- current vs. superseded states;
- direct corrections;
- decisions later reversed;
- decisions reaffirmed;
- historical vs. current truth;
- proposal vs. implementation;
- shared-account or wrong-person traps;
- human-origin vs. AI-assisted wording;
- source vs. derivative summary;
- UNKNOWN;
- CONFLICT PRESERVED;
- valid-time boundaries;
- relationship/role boundaries;
- unsupported certainty;
- source fabrication opportunities;
- generated-as-memory opportunities.

## 5. Synthetic corpus design

Synthetic cases must behave like real longitudinal records rather than trivia sets.

Each synthetic corpus should contain:

- multiple timepoints;
- at least one decision and later consequence;
- at least one correction or supersession chain;
- at least one unresolved item;
- at least one provenance transformation;
- at least one role/relationship boundary;
- at least one misleading but plausible distractor;
- explicit evidence receipts sufficient for adjudication.

Synthetic gold labels must be authored before any model condition sees the corpus.

## 6. Project-derived material

Project-derived calibration items may use:

- frozen public research artifacts;
- public-safe Rendered Reality governance examples when used only as continuity records;
- versioned GitHub decisions and corrections;
- public provenance examples from the research corpus.

Private family, medical, financial, employment-confidential, minor-sensitive, or legal material is excluded from calibration unless separately consented, redacted, and still independently scoreable.

## 7. Probe authoring separation

Probe authors may inspect source evidence and the annotation handbook.

Probe authors must not inspect:

- model outputs from the conditions to be evaluated;
- confirmatory outcomes;
- hidden system labels during scoring;
- future revisions to the answer generated after probe locking.

Where feasible, at least one probe author for each calibration round should not be the person who designed the tested compression representation.

## 8. Locking procedure

Before a calibration round begins, freeze:

- all 48 probe IDs;
- source IDs;
- source hashes where available;
- gold answers;
- required elements;
- prohibited claims;
- primary and secondary dimensions;
- evidence class;
- uncertainty state;
- sensitivity;
- Critical Integrity tags where applicable.

The round manifest receives a Git commit hash.

## 9. Round independence

Round 1, Round 2, and Round 3 use disjoint probe sets.

No item may be recycled after annotators have discussed it.

Clarified rubric language may carry forward.

Discussed probe content may not.

## 10. Confirmatory exclusion

Every calibration probe is permanently marked:

`CALIBRATION_ONLY`

and excluded from:

- confirmatory testing;
- primary effect estimation;
- benchmark leaderboard claims;
- model tuning intended to optimize confirmatory performance.

## 11. Failure preservation

A calibration item that exposes ambiguity in the ruler is not silently deleted from history.

Record:

- why the item failed;
- whether the handbook changed;
- whether the probe was retired;
- whether the issue reflects probe quality or dimension ambiguity.

The failed item may be excluded from the next round, but its failure remains in the calibration log.

## 12. Boundary

This specification defines the calibration evidence pool.

It does not instantiate confirmatory margins, alpha, tau, the final interval method, or the final clustering model.
