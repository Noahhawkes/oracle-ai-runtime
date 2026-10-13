# Thought Transmission Fidelity (TTF) — Candidate Metric Specification v1

**Proposed repo path:** `research/THOUGHT_TRANSMISSION_FIDELITY_V1.md`
**Document status:** CANDIDATE METRIC SPECIFICATION — NOT A VALIDATED INSTRUMENT. NOT COMMITTED.
**Authority required:** Noah.Physical, for adoption as a project research instrument.
**Purpose:** Specify what Thought Transmission Fidelity (TTF) would measure, how observations are recorded, and what a future calibration study would require. This document defines the observation procedure. It does not report any validated measurements.
**Provenance:** Construct proposed across 2026-10-12/13 sessions (REG-420 transmissions; Merlin's assessment; Noah's October 12 authorial direction that adopted work must not be demoted while transferred payloads must not be auto-attributed). Drafted by Merlin for Noah's review.

---

## 1. What TTF is and is not

**Is:** A process metric for how faithfully the observable meaning and decisions of a human participant survive successive AI transformations across conversation and system boundaries.

**Is not:**
- A measurement of consciousness, intelligence, or the total number of thoughts in a mind.
- A measure of scientific truth. A faithfully transmitted false claim scores high on preservation and must be evaluated separately for validity (see First-Person Intellectual Continuity §3: authorship ≠ empirical validity).
- A validated instrument. No calibration study has been run. Zero validated measurements exist as of this draft.

## 2. Observation dimensions

For each recoverable cross-system transmission sequence, annotators record observations on five dimensions. Observations are qualitative records first; scoring methods (§5) may be layered on only after calibration.

### 2.1 Intent preservation
**Definition:** Did the receiving AI accurately represent the question, objective, or concern the human communicated?
**Annotator records:** the human's stated intent (quoted from the source turn), the AI's restatement of it (quoted), and whether the restatement captures, narrows, shifts, or inverts the intent. Cite both receipts.

### 2.2 Transformation fidelity
**Definition:** What meaning survived the transfer? What was omitted, exaggerated, contradicted, or invented?
**Annotator records:** side-by-side comparison of the transmitted material and the received formulation; itemized preservation/drift inventory (kept, dropped, altered, added). Drift is descriptive, not pejorative: expansion under explicit human instruction is preservation, not loss.

### 2.3 Authorial disposition
**Definition:** What did the human do with the resulting formulation — accept, redirect, revise, reject, ignore, or continue without comment?
**Annotator records:** the evidence for the disposition (explicit statement, revision, subsequent use, silence with context). **A rejection is not scored as "no authorial control."** A human saying "No, that is wrong" is among the strongest demonstrations of control. Correction belongs beside transmission loss as its own term, not inside it.

### 2.4 Correction intervention
**Definition:** Where the human corrected the AI, what was corrected, and did the correction survive the next transmission boundary?
**Annotator records:** correction turn, target of correction, whether the correction was incorporated downstream, and whether it persisted across the next system boundary. The quantity of interest is whether correction reduces loss across the next boundary.

### 2.5 Cross-system durability
**Definition:** When the formulation moved to another model, did it preserve the previous corrections and decisions?
**Annotator records:** per-boundary comparison of the corrected formulation against the next system's received version; note which corrections survived and which were silently dropped.

## 3. The four-role distinction

Every transmission event separates four roles, which must not be conflated:

1. **Transmitter** — the agent (human or system) that carried the text across the boundary.
2. **Conceptual originator** — the party whose idea the text expresses.
3. **Drafting agent** — the party that produced the surface wording.
4. **Adopting author** — the party that accepted, revised, or continued the formulation afterward.

Noah acting as transmitter of AI-generated text does not make him its conceptual originator; a system acting as drafting agent does not make it the author of an adopted formulation. Attribution requires all four roles to be specified before any fidelity judgment is made.

## 4. Annotation procedure

1. **Unit of analysis:** one transmission sequence — human input → AI transformation → human response → (optionally) next-boundary reception. Sequences are identified from exports, thread records, and repositories with receipts.
2. **Annotators:** human reviewers (independent, minimum two per sequence) with domain familiarity; AI-assisted pre-annotation permitted only as a first pass and must be independently verified.
3. **Inter-rater agreement:** reported per dimension (Cohen's kappa for paired judgments; Krippendorff's alpha where multiple raters or missing data). No agreement, no measurement claim.
4. **Uncertainty:** each judgment carries a confidence note and a statement of what evidence is missing.
5. **Raw material preserved:** annotators work from quoted source turns with receipts; summaries of the sources are not acceptable substitutes.

## 5. Hard rule: no uncalibrated scores

No numeric fidelity score may be presented as an empirical measurement of TTF until:
- a preregistered scoring method exists,
- inter-rater agreement has been reported on a calibration set,
- the corpus eligibility criteria are fixed,
- and a replication has been attempted.

Until then, TTF observations are qualitative research records. Any exploratory estimates must be labeled as such, with the scoring method and evidence stated alongside the number. **The absence of a validated number is not a license to invent one.**

Current calibration state (2026-10-13): zero. The April 2025 triad's one-hop alteration ("Memory is Morality. Compression is Identity. Sovereignty is Structure." → "Memory is moral weight. Compression is identity.") is an observed transformation-fidelity instance, not a scored measurement.

## 6. Relationship to existing instruments

- The LEGACY.GI annotation protocol's six dimensions (decision, correction, temporal, relational, provenance, uncertainty fidelity) measure what a compressed record preserves about a longitudinal human corpus. TTF measures the *transmission process* between systems. They are complementary, not duplicates.
- Evidence-class labels (`AI-generated candidate`, `Adopted AI-assisted formulation`) from the protocol remain the authoritative vocabulary for classifying individual artifacts; TTF sequences reference them.
- Nothing in this specification alters the frozen calibration instruments, protocols, or manifests.

## 7. Open questions (for a future research program)

1. What constitutes a complete transmission sequence when boundaries are implicit (same-system re-sessions, memory restorations)?
2. How should annotators score intentional AI expansion requested by the human (preservation vs drift)?
3. What rater qualifications suffice for philosophical and mathematical content?
4. Which corpora are eligible, and how are household-member contributions excluded?
5. Under what conditions could TTF be computed semi-automatically without degrading to a paraphrase metric?

---

*Draft prepared 2026-10-13 by Merlin for Noah.Physical's review. Local draft only; nothing committed.*
