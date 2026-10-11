# Calibration Design v0.1

**Status:** CANDIDATE / PRE-EXECUTION  
**Date:** 2026-10-10  
**Authority:** Noah A. Hawkes  
**Depends on:** `SIX_DIMENSION_DECISION_RULE_V0_1.md`, Protocol v0.3, Annotator Handbook v0.1  
**Purpose:** Judge the ruler before the claim. Produce the reliability and distributional evidence required to freeze the remaining decision-rule brackets. Does not authorize filling any bracket from preference.

## 1. What calibration must deliver before confirmatory freeze

Calibration answers whether the instrument can measure the six dimensions with sufficient reliability for the decision rule to be executable. It also supplies the empirical distributions needed to set the remaining parameters without post-hoc selection.

Required outputs before any confirmatory preregistration:

- Per-dimension Krippendorff's α (ordinal) and raw agreement.
- Critical Integrity flag agreement.
- Adjudication records, with original scores preserved.
- Observed score distributions, within-corpus variance, and paired-difference variance on development material under matched-budget conditions.
- Failure modes of the instrument itself, including defective probes, systematic rater disagreements, and dimensions that do not separate.
- Explicit recommendation: which dimensions, if any, are reliability-eligible for superiority claims, which for non-inferiority only, and which remain unresolved.

If the instrument fails the terminal reliability gate, that failure is recorded. No confirmatory claim proceeds under that hypothesis version. No fourth round is permitted for the same version.

## 2. Probe set construction

Three independent rounds maximum. Each round uses 48 fresh probes, 8 per dimension. Probes are not reused across rounds.

Probe requirements:

- Independently authored or independently reviewed. Authors of a probe must not score it.
- Phrased without the six dimension names where possible.
- Source-grounded gold answer key locked before any model output is seen.
- Include both positive recovery cases and explicit UNKNOWN / CONFLICT PRESERVED cases.
- Include at least one Critical Integrity probe family per round, drawn from CE-01, CE-02, CE-04, CE-07, CE-09.
- Synthetic decoy cases with no public project footprint for leakage control.
- Held out from any development compression runs used to select baselines.

Each probe records:

- source pointers;
- gold state: RESOLVED / UNKNOWN / CONFLICT PRESERVED;
- required structure elements;
- whether it is Critical Integrity.

## 3. Rater procedure

Exactly two independent primary raters per probe plus one adjudicator. The adjudicator is not counted as an independent rater for reliability estimation.

- Raters score independently before any discussion.
- Raters are blinded to condition, continuity-aware vs. generic. Condition labels are stripped.
- Scoring uses the 0–3 ordinal rubric in the Annotator Handbook exactly. No additional point deductions for flags.
- Error flags and Critical Integrity codes are applied as defined. They do not alter the 0–3 score unless the handbook explicitly requires it.
- After independent scoring, adjudication occurs only for disagreement.
- Original scores are never overwritten.
- Defective probes are retired, not repaired after seeing answers.

Qualification gate, before any rater scores confirmatory material:

- at least 85% agreement with adjudicated calibration labels on a held-out qualification set;
- no unresolved misunderstanding of evidence precedence or UNKNOWN / CONFLICT rules;
- no systematic Critical Integrity misclassification.

## 4. Reliability metrics and terminal states

Primary metrics:

- Krippendorff's α at the ordinal measurement level, computed separately per dimension from original independent ratings;
- Krippendorff's α at the nominal measurement level for binary item-level Critical Integrity flags.

Secondary metrics:

- weighted Cohen's κ for 0-3 dimension scores using the weighting scheme frozen before Round 1;
- raw agreement;
- disagreement categories.

Adjudicated scores are not substituted into inter-rater reliability calculations. Undefined coefficients are reported as UNDEFINED with the raw label distribution rather than replaced by 0 or 1.

Terminal states are assigned from Round 3 only. Rounds 1 and 2 are developmental and do not establish terminal confirmatory eligibility:

- **α ≥ 0.80:** CONFIRMATORY-ELIGIBLE for that dimension.
- **0.67 ≤ α < 0.80:** PILOT-GRADE ONLY.
- **α < 0.67:** NOT RELIABLY MEASURABLE under this hypothesis version.

A dimension that does not reach CONFIRMATORY-ELIGIBLE cannot be placed in the superiority set. It may still be placed in the non-inferiority set only if its α meets the pilot-grade floor and the protocol explicitly accepts that risk. Otherwise it is excluded from the confirmatory vector for this version.

## 5. Using calibration data to freeze the remaining brackets

Calibration does not invent the numbers. It supplies the evidence from which the following can be frozen:

| Bracket | Evidence required before freeze | Rule |
|---|---|---|
| Superiority set P | Per-dimension α and observed paired-difference distributions on development material | Only dimensions with α ≥ 0.80 and clear separation potential may enter P. P must be non-empty. |
| Non-inferiority set N | Same reliability data | Remaining eligible dimensions. |
| δ_k, superiority | Observed variance and minimum detectable effect under planned sample size | Set to the smallest improvement the instrument and design can reliably distinguish above noise. Not chosen for narrative convenience. |
| m_k, non-inferiority | Same | Set to the largest degradation still acceptable given reliability and practical meaning. |
| α, familywise | Power calculations from observed variance | Frozen after sample-size and clustering plan are fixed. |
| Simultaneous interval method | Cluster structure and dependence estimates | Must account for within-corpus pairing and probe clustering. |
| Clustering procedure | Empirical intra-class correlation from calibration/pilot | Frozen before confirmatory analysis. |
| τ, Critical Integrity | Observed critical-error rates and adjudication reliability | Maximum acceptable rate that the design can actually detect and that integrity policy will tolerate. |
| Missing-response handling | Frequency and type of missing scores in calibration | Prespecified rule, e.g. exclude probe, impute under stated assumption, or treat as failure. |
| Corpus weighting | Number and independence of available corpora | Equal weight default unless calibration shows material imbalance that must be corrected and justified. |
| Multiplicity procedure | Number of primary comparisons | Frozen once the primary comparison is locked. |

All freezes are versioned. Any change after confirmatory outcomes exist creates a new hypothesis version and requires a new held-out test.

## 6. Development material vs. confirmatory material

Calibration and parameter-setting use only development corpora and development probes.

The confirmatory probe set and confirmatory corpora remain untouched until the decision rule is fully frozen.

No result from confirmatory material may be used to adjust:

- δ_k;
- m_k;
- P;
- N;
- τ.

## 7. Failure modes that must be recorded

- Dimension that cannot reach reliability threshold.
- Systematic rater disagreement on UNKNOWN vs. RESOLVED.
- Probes that are defective once answers are seen.
- Critical Integrity codes that raters apply inconsistently.
- Apparent effects that disappear under blinded scoring or when project vocabulary is removed.
- Instrument that measures fluency in project language rather than structure.

These are evidence about the ruler. They are preserved.

## 8. Immediate next artifacts

Round 1 probe authorship is governed by `research/calibration/ROUND_1_PROBE_AUTHORING_CONSTRAINTS_V0_1.md`. That artifact fixes the 48-probe balance, author separation, required probe fields, challenge coverage, leakage defenses, lock procedure, and scoring-readiness gate without instantiating any confirmatory bracket.

1. Probe-generation specification and authorship log for Round 1, 48 probes.
2. Rater recruitment and qualification packet.
3. Scoring sheet / schema that captures original scores, flags, Critical Integrity codes, and adjudication without overwrite.
4. Analysis script skeleton for α, disagreement categorization, and variance estimation.
5. Versioned disagreements record for any external review of the calibration design itself.

## Boundary

This design judges whether the six-dimension ruler is reliable enough to support a confirmatory claim under the decision rule already written.

It does not establish:

- that the dimensions are complete;
- that continuity-aware compression works;
- that any identity claim is supported.

If the ruler fails, the failure is the result.

The brackets remain unresolved until the data exist.

**No confirmatory execution is authorized until they are frozen from that data.**
