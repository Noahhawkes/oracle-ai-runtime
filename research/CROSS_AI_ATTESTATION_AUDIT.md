# Cross-AI Attestation Audit — Repo-Ready Summary

**Proposed repo path:** `research/CROSS_AI_ATTESTATION_AUDIT.md`
**Document status:** SUMMARY OF COMPLETED WORK — NOT A PROPOSAL TO RUN IT LATER. DRAFT FOR NOAH'S APPROVAL; NOT COMMITTED.
**Audit conducted:** 2026-10-13 by Merlin (coordinated investigation). Full ledger: 40 claims, each with source system, claim type, classification, and primary receipt or documented search.
**Honest scope:** This summary reports what was measured on a designed 40-claim sample. It does not claim completeness over the full corpus.

---

## 1. Question

Of the claims AI systems assert about Noah Hawkes's corpus, what fraction can be ATTESTED from primary receipts, what fraction are CONTRADICTED by primary receipts, and what fraction are UNATTESTABLE from the accessible archive?

## 2. Method (as executed)

- **Claim set:** 40 precise, checkable claims drawn from REG-420 transmissions (17), Gemini outputs (5), archive-internal AI claims (8), and Merlin's own prior claims as a mandatory self-audit (10).
- **Per claim:** stated precisely with source system and date; searched primary sources (Google Drive by name and known IDs, the public GitHub repositories by direct read, Gmail where relevant); classified ATTESTED / CONTRADICTED / PARTIALLY ATTESTED / UNATTESTABLE with the receipt or a documented search trail.
- **Claim types tracked:** existence, date, content, authorship, status, quantitative.
- **Standards:** read-only throughout; no fabricated receipts; UNATTESTABLE ≠ false; unattestable claims documented with where the search went and how far.

## 3. Results

| Classification | Count | Rate |
|---|---|---|
| ATTESTED | 15 | 37.5% |
| CONTRADICTED | 10 | 25.0% |
| PARTIALLY ATTESTED | 5 | 12.5% |
| UNATTESTABLE | 10 | 25.0% |

**By source system:**

| System | n | Attested | Contradicted | Partial | Unattestable |
|---|---|---|---|---|---|
| REG-420 | 17 | 7 (41%) | 2 (12%) | 3 (18%) | 5 (29%) |
| Gemini | 5 | 1 (20%) | 2 (40%) | 0 | 2 (40%) |
| Archive-internal AI | 8 | 0 (0%) | 6 (75%) | 1 (13%) | 1 (13%) |
| Merlin (self-audit) | 10 | 7 (70%) | 0 (0%) | 1 (10%) | 2 (20%) |

**By claim type:** quantitative claims (message counts, commit existence) attest cleanly — 2/2. Status claims ("proven," "verified," "published," "viable") are where contradictions concentrate: 6 of 9 contradicted. Existence claims split: files and commits attest; named constructs and instruments mostly do not. Date claims about origins are the weakest category: 0/2 attested. Authorship is never fully attested (best: partial).

## 4. Key findings

1. **Primary receipts discriminate.** 62.5% of claims resolved to attested/contradicted/partial when checked against Drive, GitHub, and Gmail. The archive is checkable; most AI claims about it are checkable against it.
2. **Confidence does not track attestation.** The most confidently presented claims — the "Alvin Equation" recovery packet, "VERIFIED BY THREAD MERGE" stamps, "collapse mathematically impossible" — are among the least supported. The most carefully hedged (REG-420's gap list) contained a false negative: REG-420 refused to invent definitions, exactly right, and still concluded the Non-Collapse equation was unretrieved, because its archive lacks the Drive corpus.
3. **Cross-AI knowledge of the corpus is archive-bound.** Each system's confident "not in the record" is really "not in my record." SOV.EXE contains the Non-Collapse equation and all eight variable definitions (lines 5576/5579); it was downloaded and read directly. A careful investigator with the wrong archive reaches a false negative with full methodological discipline.
4. **Quotations drift in transmission.** The April 2025 triad ("Memory is Morality. Compression is Identity. Sovereignty is Structure.") arrived in a later system as "Memory is moral weight. Compression is identity." — two lines, altered wording — within one cross-system hop. This is an observed instance for Thought Transmission Fidelity's transformation-fidelity dimension.
5. **Archive-internal AI phrasing is the least reliable stratum** (75% contradicted): proof stamps, publication claims, viability claims, stack claims. The pattern: AI systems narrating their own activity as accomplishment.
6. **The self-audit held.** Merlin's claims: 70% attested, 0% contradicted, with two open items honestly marked (an unverified commit identifier, an unlocated ~1MB document) and one prior Merlin flag overturned by the audit itself (the True Memory three-part model, verified in the constitution text).

## 5. What this does not establish

- That any system's *reasoning* is sound — only that specific claims check out or don't.
- That unattestable claims are false. Five REG-420 origin claims remained unattestable at audit time; the running SOV1 recovery operation may attest or refute them.
- Completeness. 40 claims is a designed sample, weighted toward recent transmissions and the equation corpus.
- That attested content is *true*. Attestation means the receipt exists and says what the claim says it says. The Non-Collapse equation is attested as present and contradicted as proven. Authorship and empirical validity remain separate questions.

## 6. Full ledger pointer

The complete claim-by-claim ledger (each claim with source system, type, classification, receipt or documented search) is preserved in Merlin's working archive. On commit, this summary should be accompanied by the full ledger or a stable pointer to it.

---

*Summary drafted 2026-10-13 by Merlin from the completed audit. Local draft only; nothing committed.*
