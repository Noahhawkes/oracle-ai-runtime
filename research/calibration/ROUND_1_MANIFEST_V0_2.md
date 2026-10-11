# Round 1 Calibration Manifest v0.2

**Status:** FROZEN  
**Date:** 2026-10-10  
**Packet:** research/calibration/ROUND_1_CALIBRATION_PACKET_V0_2.md  
**Authority:** Noah A. Hawkes  
**Correction lineage:** v0.1 attempted freeze preserved at commit `e46aba437b46671f6f1326ceef1ae670b84a4c26`

## Freeze record

This manifest freezes the complete Round 1 Calibration Packet for independent scoring.

- Packet version: v0.2
- Probe count: 48 (exactly 8 per dimension)
- Split: 24 project-derived / 24 synthetic
- Critical Integrity probes: 16 (CE-01, CE-02, CE-04, CE-07, CE-09 represented)
- All probes permanently tagged CALIBRATION_ONLY
- Excluded from confirmatory testing, primary effect estimation, confirmatory-performance tuning, and future calibration-round reuse
- Full packet blob SHA: `de9d245d108947ec6afe7170bb6d0eed7f9421ba`

## v0.1 defect preservation

The v0.1 freeze attempt is preserved as historical state.

**Defect:** `ROUND1_FREEZE_CONTENT_POINTER_GAP`

The v0.1 commit correctly recorded packet counts, exclusions, and source snapshots, but `ROUND_1_CALIBRATION_PACKET_V0_1.md` contained only a summary and a pointer to conversation text. The complete 48-probe corpus was not inside the hashed repository object.

- Historical attempted-freeze commit: `e46aba437b46671f6f1326ceef1ae670b84a4c26`
- Historical v0.1 packet blob: `8a8d9a196fa48b0ccc90e5564014efd205a71a5f`
- Scoring under v0.1: none
- Evaluated-model exposure under v0.1: none
- Contamination from v0.1: none identified

v0.2 corrects the implementation defect by embedding the complete packet directly in repository history. v0.1 is not rewritten or deleted.

## Source snapshots referenced by project-derived probes

- `Noahhawkes/oracle-ai-runtime@23b79db50c96c43f86caeb6e2bba368533542686`
- `HawkesNest-LLC/Oracle@52089a06f849ae8dad763ba3398b9822e1b5a102`

## Operational status

- Gold structures were locked before any evaluated model condition.
- The complete probe text is contained in the v0.2 packet blob identified above.
- No confirmatory thresholds, superiority sets, margins, alpha, tau, interval methods, clustering procedures, missing-response rules, corpus weighting, or multiplicity procedures are instantiated by this packet.
- Confirmatory brackets remain unresolved.
- Scoring may begin only after two independent primary raters and one adjudicator are identified, oriented, and have completed conflict-of-interest and provenance disclosures under the Rater Protocol.
- Primary raters score independently before discussion.
- Adjudication occurs only after both primary ratings are submitted.
- Adjudicated scores are not substituted into inter-rater reliability calculations.

## Change rule

Any substantive change to the packet after this freeze creates a new packet version and a new manifest.

The frozen v0.2 packet is not edited in place.

Defects discovered after scoring begins are retired/logged rather than silently repaired.

## Operational lock

The Git commit containing this manifest and `ROUND_1_CALIBRATION_PACKET_V0_2.md` together is the operational lock for Round 1 v0.2.
