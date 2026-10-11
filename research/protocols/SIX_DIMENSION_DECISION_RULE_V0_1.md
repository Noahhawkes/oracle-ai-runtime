# Six-Dimension Decision Rule v0.1

**Status:** CANDIDATE / PROTOCOL-READY  
**Date:** 2026-10-10  
**Authority:** Noah A. Hawkes  
**Applies to:** Continuity Intelligence confirmatory evaluation  
**Important:** Bracketed fields MUST be instantiated and frozen before confirmatory execution. This file does not authorize filling them after outcomes are known.

## 1. Endpoint and estimand

The confirmatory endpoint is the vector of between-condition differences in decision, correction, temporal, relational, provenance, and uncertainty fidelity:

[
\boldsymbol{\Delta}(\mathbf B)
=
(\Delta_D,\Delta_C,\Delta_T,\Delta_R,\Delta_{Pv},\Delta_U).
]

For each dimension (k),

[
\Delta_k(\mathbf B)
=
\mathbb E_X\!\left[
S_k^{(c)}(X;\mathbf B)
-
S_k^{(g)}(X;\mathbf B)
\right],
]

where:

- (S_k^{(c)}) and (S_k^{(g)}) are corpus-level scores under the continuity-aware and frozen generic-baseline conditions.
- Higher scores indicate greater fidelity.
- Conditions are paired within each independent longitudinal corpus.
- Probe aggregation, score normalization, and treatment of missing responses are fixed in the scoring handbook.
- (\mathbf B) is the matched resource-budget vector.

The expectation is over the prespecified eligible corpus population. Each corpus receives equal weight unless a different weighting rule is justified and frozen in advance.

## 2. Frozen dimension assignments and margins

Before confirmatory execution, each dimension is assigned to either the superiority set (P) or the non-inferiority set (N), with

[
P\cup N=\{D,C,T,R,Pv,U\},
\qquad
P\cap N=\varnothing,
\qquad
P\ne\varnothing.
]

Here (Pv) denotes provenance, avoiding confusion with the superiority set (P).

| Dimension | Confirmatory role | Frozen threshold |
|---|---|---|
| Decision | [Superiority / non-inferiority] | [(\delta_D) / (m_D)] |
| Correction | [Superiority / non-inferiority] | [(\delta_C) / (m_C)] |
| Temporal | [Superiority / non-inferiority] | [(\delta_T) / (m_T)] |
| Relational | [Superiority / non-inferiority] | [(\delta_R) / (m_R)] |
| Provenance | [Superiority / non-inferiority] | [(\delta_{Pv}) / (m_{Pv})] |
| Uncertainty | [Superiority / non-inferiority] | [(\delta_U) / (m_U)] |

For superiority dimensions, (\delta_k>0) is the minimum practically meaningful improvement.

For non-inferiority dimensions, (m_k>0) is the maximum acceptable degradation.

Assignments, thresholds, and their rationales are frozen before access to confirmatory test outcomes.

## 3. Inferential bounds

The analysis produces simultaneous confidence intervals

[
[L_k,U_k]
]

for all six (\Delta_k), using **[specified analysis model and interval-construction procedure]** with familywise coverage of at least (1-\alpha), where (\alpha=\text{[value]}).

The procedure accounts for:

- pairing between conditions;
- dependence among probes from the same corpus;
- the independent longitudinal corpus as the relevant higher-level experimental unit.

Probe count is not treated as the number of independent corpora.

## 4. Dimension-level decisions

For each superiority dimension (k\in P):

- **Pass:** (L_k>\delta_k).
- **Fail:** (U_k<\delta_k), excluding the required meaningful improvement.
- **Unresolved:** neither condition holds.

For each non-inferiority dimension (k\in N):

- **Pass:** (L_k>-m_k).
- **Fail:** (U_k<-m_k), demonstrating degradation beyond the permitted margin.
- **Unresolved:** neither condition holds.

Equality with a threshold is classified as unresolved.

Failure to demonstrate superiority or non-inferiority does not, by itself, establish failure of the substantive claim.

## 5. Critical Integrity Set gate

Integrity is a **non-compensatory** endpoint.

Ordinary fidelity gains cannot offset critical integrity violations.

For the rate-based gate, let (p_{crit}) be the continuity-aware condition's probability of at least one adjudicated critical violation on an eligible integrity probe.

Let

[
[L_{crit},U_{crit}]
]

be its confidence interval, calculated using **[frozen procedure accounting for corpus clustering]**, and let (\tau=\text{[maximum acceptable rate]}).

- **Integrity pass:** (U_{crit}\le\tau).
- **Integrity fail:** (L_{crit}>\tau).
- **Integrity unresolved:** otherwise.

The protocol freezes:

- the eligible denominator;
- qualifying violations;
- adjudication procedure;
- treatment of unresolved labels;
- confidence-interval procedure;
- clustering method;
- acceptance threshold (\tau).

Baseline critical-error rates are reported separately.

A baseline's poor integrity does not waive this acceptance requirement.

## 6. Overall confirmatory outcome

Define:

[
\mathcal S
=
\bigcap_{k\in P}\{L_k>\delta_k\},
]

[
\mathcal N
=
\bigcap_{k\in N}\{L_k>-m_k\},
]

[
\mathcal I
=
\{U_{crit}\le\tau\}.
]

The overall result is:

1. **Positive** if (\mathcal S), (\mathcal N), and (\mathcal I) all hold.
2. **Negative** if any required dimension fails or the integrity gate fails.
3. **Inconclusive** otherwise.

If (N) is empty, its condition is satisfied by definition.

A negative classification identifies failure of the specified confirmatory claim.

Reports distinguish:

- insufficient meaningful benefit;
- unacceptable dimensional degradation;
- integrity failure.

These are not interchangeable findings.

## 7. Reporting and claim boundary

All six estimates, intervals, thresholds, dimension-level classifications, and integrity results are reported regardless of the overall outcome.

No weighted aggregate substitutes for the vector rule.

A positive result licenses only the following form of statement:

> Under the specified budgets, corpus population, baseline, and answering procedure, the tested continuity-aware intervention exceeded the minimum meaningful improvement on the designated primary dimensions, remained within permitted degradation margins on the remaining dimensions, and satisfied the critical integrity criterion.

It does **not** license a claim of superiority on all six dimensions unless all six were assigned to superiority and passed.

For multiple baselines or budget conditions, the protocol designates one primary comparison or freezes an explicit joint decision rule and corresponding multiplicity procedure.

Selection of the most favorable comparison after observing outcomes is prohibited.

## 8. Freeze requirements

Before confirmatory execution, freeze and version:

- the superiority set (P);
- the non-inferiority set (N);
- every (\delta_k);
- every (m_k);
- (\alpha);
- the simultaneous interval procedure;
- the corpus-clustering procedure;
- the integrity denominator;
- the integrity confidence-interval procedure;
- (\tau);
- missing-response handling;
- corpus weighting;
- multiplicity procedure across any additional primary baselines or budget conditions.

Any change after confirmatory outcomes are available creates a new hypothesis version and requires a new held-out test.

## 9. Boundary

This rule determines whether the **specified confirmatory claim** passes, fails, or remains inconclusive.

It does not determine:

- whether continuity is metaphysical identity;
- whether a reconstruction is the same person;
- whether subjective survival occurs;
- whether the six dimensions are complete;
- whether every possible continuity-aware method would behave like the tested intervention.
