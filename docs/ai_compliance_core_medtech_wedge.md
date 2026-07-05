# AI Compliance Core — MedTech Wedge (Candidate Vertical Note)

Status: candidate, not canon
Authority: Noah.Physical
Created: 2026-07-05
Writer: Claude Code, from Noah.Physical live insight 2026-07-05 ("regulated
medtech startups face heavy documentation burden") plus the existing doctrine
and product map
Sandbox boundary: no sandbox files were read or written for this artifact
Runtime boundary: no runtime code was added or changed for this artifact
Promotion status: not_promoted — pass to a new thread for development

## 0. Source Inputs & Claim Boundary

Parents of this note:

- `docs/AI_COMPLIANCE_CORE_DOCTRINE.md`
- `docs/ai_compliance_core_product_map.md`
- Noah.Physical live business insight, captured 2026-07-05

This note extends the product map with one vertical. It does not replace or
rewrite the horizontal offer.

Forbidden claims (verbatim, non-negotiable):

- No FDA certification claim.
- No legal compliance guarantee.
- No replacement for regulatory counsel.
- No autonomous approval.
- No sentience, personhood, or metaphysical continuity claim.

Allowed language register:

audit-readiness · provenance · approval traceability · documentation control ·
source-backed AI work records · quality documentation support ·
human-in-the-loop governance · compliance-readiness.

## 1. Wedge Thesis

Regulated medtech startups may be the sharpest first vertical for the AI
flight recorder, because they are the one customer class that is already
*forced* to produce what the product makes:

- documentation with named reviewers and named approvers
- traceability from requirement to output to evidence
- records that survive third-party audit
- proof of who decided what, when, from which source

Every other buyer treats receipt discipline as optional hygiene. A medtech
startup treats it as a condition of existing. AI Compliance Core does not have
to convince them documentation matters — it only has to make their AI-assisted
work produce the records they already owe.

Status: HYPOTHESIS. Not validated with any buyer. Unknown remains UNKNOWN.

## 2. Documentation Burden Map

The nine burdens from the live insight, each mapped honestly:

| Burden | Existing offer supports today | Needs building | Status |
|---|---|---|---|
| IP audit | source_refs / authorship fields separate human vs AI-assisted origin | IP-specific record view | candidate |
| FDA readiness | approval traceability + receipts support *readiness posture*, never clearance itself | mapping guide written with counsel | candidate |
| Quality systems | record schema (24 fields) is a quality-record pattern | alignment pass against customer's QMS | candidate |
| Design inputs/outputs | requested_by / source_refs / final_disposition give input→output traceability | design-control-shaped template | candidate |
| Manufacturing handoff | external_action + external_target record what left the building | handoff packet template | candidate |
| Contract manufacturer docs | connector provenance rules prove what was actually sent/reviewed | CM-facing record view | candidate |
| QMS records | audit log template + receipts | none for pilot scope | candidate |
| Audit readiness | the whole product; reconstruction-after-the-fact is the core promise | vertical vocabulary only | candidate |
| Investor diligence | receipt-backed work records answer "how was this built and who approved it" | diligence packet framing | candidate |
| Human approval traceability | reviewed_by / approved_by / approval_status — already the spine | nothing | strongest fit |

## 3. Schema Fit

The existing Compliance Record Schema (product map §6) already carries the
load-bearing fields for this vertical:

- `requested_by` / `reviewed_by` / `approved_by` / `approval_status` →
  human approval traceability
- `source_refs` / `source_status` / `content_hash` → documentation provenance
- `external_action` / `external_target` → manufacturing/CM handoff custody
- `token_origin` / `authorial_authority` → IP and authorship separation

Known gaps (build list, not blockers):

- no requirement-ID linkage field (design input ↔ output pairing)
- no document-revision lineage field
- no customer-QMS record-number cross-reference field

## 4. Buyer Hypothesis

Candidate buyers at a pre-clearance medtech startup:

- founder/CEO (owns investor diligence pain)
- quality lead / first quality hire (owns QMS pain)
- fractional RA/QA consultant (channel partner, not end buyer)

All HYPOTHESIS. Zero discovery calls completed. Validation status: UNKNOWN.

## 5. Offer Adaptation

MedTech variant of the AI Work Audit Kit (product map §4), same fixed scope:

- pilot workflow = ONE design-documentation or CM-handoff workflow
- deliverables = the standard kit plus the design-control-shaped record
  template from §3 gaps
- risk matrix inheritance: regulated data and health/safety claims remain
  **Critical → stop-and-escalate**. The wedge does not soften the matrix;
  it is the matrix's best showcase.

## 6. What This Is Not

Inherits product map §11 in full, plus vertical-specific:

- does not produce FDA submissions or any part of a 510(k)/De Novo/PMA
- does not substitute for a quality management system
- does not certify ISO 13485 or any standard
- requires the customer's regulatory counsel in the loop for any
  regulatory-facing use of its records

## 7. Risks & Disqualifiers

Walk away when:

- the buyer wants the kit to *be* their QMS
- the buyer wants AI to approve records autonomously
- the buyer resists naming human reviewers/approvers
- any claim of regulatory sufficiency is requested as a deliverable

Counsel review is mandatory before any customer-facing language in this
vertical ships.

## 8. Validation Next Steps (proposal-only)

1. Read the existing AICC collateral at
   `OneDrive - sov1.ai\Noah.AI Tech Documents\AI Compliance Core\`
   (contents currently UNKNOWN — never referenced in repo docs beyond the
   systems index pointer) before drafting any customer-facing language.
2. Draft five discovery-call questions for a medtech founder or quality lead.
3. Define pilot acceptance criteria: a third party can reconstruct one
   AI-assisted design-documentation decision from receipts alone.
4. No outreach, no posting, no external action without explicit
   Noah.Physical approval per the External Action Approval Policy.

## 9. Promotion Path

candidate → reviewed by Noah.Physical → canon, per intake rules.

Evidence that would justify promotion:

- at least three discovery conversations confirming the burden map
- one pilot customer letter of intent, or one completed pilot
- counsel-reviewed customer-facing language

Until then this file remains a candidate vertical note. Raw insight outranks
this summary; this summary outranks nothing.
