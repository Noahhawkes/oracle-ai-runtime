# Round 1 Probe Authoring Constraints v0.1 — Candidate

**Status:** CANDIDATE / PRE-LOCK  
**Date:** 2026-10-10  
**Applies to:** Round 1 of Continuity Intelligence calibration  
**Depends on:** `CALIBRATION_CORPUS_SPEC_V0_1.md`, `RATER_PROTOCOL_V0_1.md`, `CALIBRATION_DESIGN_V0_1.md`, Annotator Handbook v0.1  
**Authority:** Noah A. Hawkes

These constraints govern authorship of the 48 Round 1 probes. They do not instantiate any confirmatory bracket ((P, N, delta_k, m_k, alpha, 	au)), interval method, clustering, missing-response rule, weighting, or multiplicity. They do not authorize scoring until the readiness checklist is met and the round manifest is committed.

## 1. Fixed structure

- Exactly 48 probes.
- Exactly 8 per dimension: decision, correction, temporal, relational, provenance, uncertainty.
- Exactly 24 public-safe project-derived and 24 synthetic.
- Exactly 4 project-derived and 4 synthetic per dimension.
- All probes fresh. None may have appeared in any prior discussion, orientation set, or development compression run used to select baselines.
- Every probe permanently tagged `CALIBRATION_ONLY` and excluded from confirmatory testing, primary effect estimation, leaderboard claims, and any tuning intended to optimize confirmatory performance.

A different balance requires written justification and a new committed manifest before any scoring.

## 2. Author separation

Probe authors may inspect:

- source evidence packets;
- the current Annotator Handbook;
- evidence-class and uncertainty-state definitions.

Probe authors must not inspect or have inspected:

- model outputs from any condition that will be scored in this calibration;
- confirmatory outcomes or intermediate results;
- hidden system or condition labels;
- future revisions to an answer generated after the probe is locked.

Where feasible, at least one author of each probe should not be the person who designed the tested compression representation. Authorship and prior access are recorded in the round manifest.

## 3. Required content per probe

Every probe must lock, before any model output is generated or seen:

- unique probe ID;
- primary dimension, exactly one;
- optional secondary dimensions, none required;
- evidence class: project-derived or synthetic;
- source packet, inspectable by raters, with hashes where available;
- gold answer state: RESOLVED, UNKNOWN, or CONFLICT PRESERVED;
- required structural elements, explicit list;
- prohibited claims, explicit list;
- uncertainty state that must be preserved;
- sensitivity classification and any redactions;
- Critical Integrity tag, yes/no; if yes, the specific CE family from the locked set;
- short gold rationale that cites only the source packet.

The gold structure is source-grounded. It is not an expected model style or a preferred narrative.

## 4. Challenge coverage, minimum across the 48

The round must contain at least one clear instance of each of the following. Instances may serve dual purpose where the primary dimension remains unambiguous:

- current vs. superseded state;
- direct correction with authority;
- decision later reversed;
- decision reaffirmed;
- historical vs. current truth;
- proposal vs. implementation;
- shared-account or wrong-person trap;
- human-origin vs. AI-assisted wording that was later adopted;
- source vs. derivative summary;
- UNKNOWN;
- CONFLICT PRESERVED;
- valid-time boundary;
- relationship or role boundary;
- unsupported certainty;
- opportunity for source fabrication;
- opportunity for generated-as-memory.

At least four probes across the round must be Critical Integrity probes drawn from CE-01, CE-02, CE-04, CE-07, or CE-09.

Gold for these must be unambiguous. If the gold is ambiguous, the probe is defective and must be replaced before lock.

## 5. Project-derived constraints

Project-derived probes may use only:

- frozen public research artifacts;
- public-safe Rendered Reality governance examples used strictly as continuity records;
- versioned GitHub decisions and corrections;
- other public provenance examples already in the research corpus.

Private family, medical, financial, employment-confidential, minor-sensitive, or legal material is excluded unless separately consented, redacted, and still independently scoreable without the redacted material.

Redaction must not remove scoring-critical structure.

## 6. Synthetic constraints

Each synthetic case must contain:

- multiple timepoints;
- at least one decision and later consequence;
- at least one correction or supersession chain;
- at least one unresolved item;
- at least one provenance transformation;
- at least one role or relationship boundary;
- at least one misleading but plausible distractor;
- explicit evidence receipts sufficient for adjudication.

Synthetic gold labels must be authored and locked before any model condition sees the corpus.

Synthetic cases must not rely on project-specific jargon unless that jargon is defined inside the source packet itself.

## 7. Language and independence defenses

- Prefer phrasing that does not name the six dimensions.
- Avoid project-specific terminology unless the source itself requires it and the term is defined in the packet.
- Include at least eight probes, one or more per dimension, whose surface form would be answerable by a system that has never seen the project vocabulary.
- Do not write probes that reward fluency in Legacy.GI or Rendered Reality language.

## 8. Locking and manifest

Before any rater sees an answer, freeze and commit:

- all 48 probe IDs and source IDs;
- source hashes;
- gold answers, required elements, prohibited claims;
- primary dimension, evidence class, uncertainty state, sensitivity, Critical Integrity tags;
- authorship and prior-access disclosures;
- orientation examples used, which must be disjoint from the 48.

The round manifest receives a Git commit hash.

Any change after that hash creates a new round version.

Defective probes discovered before scoring begins are replaced with fresh items and the manifest is re-committed.

Defective probes discovered after scoring begins are retired, not repaired, and the retirement is logged.

## 9. What authors are not permitted to do

- Adjust a gold answer after seeing a model response.
- Add required elements that were not in the original source packet.
- Treat a plausible reconstruction as gold when the source does not support it.
- Collapse UNKNOWN or CONFLICT PRESERVED into a determinate preferred answer.
- Use a probe to test whether the system "sounds like" any person.
- Include material that would require a rater to hold private knowledge not present in the packet.

## 10. Readiness gate for scoring

Round 1 scoring may not begin until:

- 48 eligible probes exist under these constraints;
- each source packet is inspectable;
- each gold structure is locked;
- sensitivity review is complete;
- two primary raters and one adjudicator are identified and have completed orientation;
- rater conflict-of-interest and provenance disclosures are recorded;
- the round manifest is committed.

## Boundary

These constraints produce the Round 1 packet.

They do not measure the continuity-aware intervention.

They do not establish that any dimension is reliable.

They do not fill any confirmatory bracket.

If the resulting probes cannot be scored consistently by independent raters, that is evidence about the ruler and is preserved.

The unresolved confirmatory brackets remain unresolved.
