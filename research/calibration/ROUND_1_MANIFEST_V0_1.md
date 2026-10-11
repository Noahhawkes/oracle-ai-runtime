# Round 1 Calibration Manifest v0.1

**Status:** FROZEN
**Date:** 2026-10-10
**Packet:** research/calibration/ROUND_1_CALIBRATION_PACKET_V0_1.md
**Authority:** Noah A. Hawkes

## Freeze record

This manifest freezes the Round 1 Calibration Packet for independent scoring.

- Packet version: v0.1
- Probe count: 48 (exactly 8 per dimension)
- Split: 24 project-derived / 24 synthetic
- Critical Integrity probes: 16 (CE-01, CE-02, CE-04, CE-07, CE-09 represented)
- All probes permanently tagged CALIBRATION_ONLY
- Excluded from confirmatory testing, primary effect estimation, and confirmatory-performance tuning

## Source snapshots referenced by project-derived probes

- Noahhawkes/oracle-ai-runtime@23b79db50c96c43f86caeb6e2bba368533542686
- HawkesNest-LLC/Oracle@52089a06f849ae8dad763ba3398b9822e1b5a102

## Operational status

- Gold structures locked before any evaluated model condition.
- No confirmatory thresholds, superiority sets, margins, alpha, tau, interval methods, clustering procedures, missing-response rules, corpus weighting, or multiplicity procedures are instantiated by this packet.
- Scoring may begin only after two independent primary raters and one adjudicator are identified, oriented, and have completed conflict-of-interest and provenance disclosures under the Rater Protocol.

## Change rule

Any substantive change to the packet after this manifest commit creates a new packet version and a new manifest. The frozen v0.1 packet is not edited in place.

## Commit

This manifest is committed together with the packet. The commit hash of this freeze is the operational lock for Round 1.
