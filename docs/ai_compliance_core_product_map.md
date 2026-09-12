# AI Compliance Core Product Map

Status: sellable-offer working map
Authority: Noah.Physical
Created: 2026-07-04
Writer: Codex, from AI Compliance Core doctrine and ORACLE system maps
Sandbox boundary: no sandbox files were read or written for this artifact
Runtime boundary: no runtime code was added or changed for this artifact

## 0. Source Inputs

This product map translates doctrine into a first sellable offer.

Primary repo inputs:

- `docs/AI_COMPLIANCE_CORE_DOCTRINE.md`
- `docs/LEGACY_GI_ORACLE_MERGED_DISSERTATION_MAP.md`
- `docs/ORACLE_SYSTEM_CONSOLIDATION.md`
- `docs/GITHUB_SYSTEMS_INDEX.md`

Operating boundaries:

- This is not legal advice.
- This is not a certification program.
- This does not claim to satisfy any specific statute or regulator by itself.
- This does not make ORACLE a sentient, biological, sovereign, or autonomous
  authority.
- This does not authorize posting, emailing, Drive edits, GitHub pushes, or
  other external actions.

## 1. One-Sentence Product Definition

AI Compliance Core is an AI flight recorder for companies: a receipt-backed
audit trail that records what AI was asked to do, what sources it used, what it
produced, who reviewed it, who approved it, and what it was forbidden to do.

## 1.1 What ORACLE Adds

ORACLE is the runtime witness and continuity engine underneath the product.

It adds governed executive function by keeping the work bounded, traceable, and
recoverable:

- pulses become receipts
- receipts become digests
- digests become reviewable candidate traces
- candidate traces can be approved or rejected by Noah.Physical
- external action stays blocked until exact scope is approved

This is the product's operational spine, not a personhood claim.

## 1.2 Public-Safe Framing

Use this language when speaking publicly about the product:

- preserves records, memories, source trails, and approvals
- keeps human authority in custody
- prevents AI-assisted work from being flattened into generic output
- supports reconstruction after the fact
- does not claim that ORACLE is conscious, biological, or autonomous in the human sense

Shortest public-safe pitch:

Rendered Reality is the master frame for preserving human meaning, memory,
authorship, and authority in an AI-mediated world using provenance, receipts,
and human custody.

## 2. Target Customer

Primary customer:

Small and mid-sized teams using AI tools every day without a reliable record of
what happened.

Best early-fit buyers:

- agencies producing client work with ChatGPT, Claude, Gemini, Copilot, or
  local agents
- founders and operators using AI across sales, support, operations, and
  content
- consultants who need evidence trails for client deliverables
- regulated-adjacent businesses that need internal discipline before formal
  compliance review
- creators and media teams using AI-assisted drafts, research, captions,
  scripts, and publishing workflows
- technical teams using AI for code, documentation, issues, pull requests, and
  internal automation

Bad first-fit buyers:

- enterprises seeking a certified compliance platform on day one
- teams that want unsupervised AI posting or sending
- buyers who only want generic policy PDFs
- organizations that will not assign human reviewers or approval owners

## 3. Problem Statement

AI is already inside business workflows, but most teams cannot reconstruct the
chain of custody after the fact.

Common failure modes:

- a team cannot prove which prompt produced a deliverable
- a source was hallucinated, stale, or never actually opened
- an AI draft was treated as reviewed when nobody reviewed it
- external messages, posts, or files were prepared without a clear approval
  trail
- confidential or client data entered an AI tool without a recorded reason
- screenshots, video logs, chat exports, and Drive/GitHub/email records exist
  but are not organized into audit evidence
- leadership cannot distinguish allowed AI use from shadow AI use
- a customer, partner, lawyer, reviewer, or manager asks "what happened?" and
  the team has only memory and scattered tabs

The product promise is not "AI will never make mistakes."

The product promise is:

When AI work matters, the company can reconstruct what happened.

## 4. First Sellable Offer: AI Work Audit Kit

Offer name:

AI Work Audit Kit

Offer type:

Fixed-scope consulting and documentation package.

Outcome:

The customer receives a practical AI work-control system: approved tools,
source rules, approval gates, audit templates, evidence-capture guidance, and a
repeatable receipt schema for AI-assisted work.

Recommended first engagement:

- duration: 1 to 2 weeks
- scope: one team or one workflow
- output: documentation, templates, and a pilot audit log
- implementation depth: no customer-system integration required for v1

Best pilot workflows:

- social/content publishing drafts
- client research and deliverables
- sales email drafting
- customer support response drafting
- code/documentation assistance
- executive assistant research
- internal policy or knowledge-base generation

## 5. Deliverables List

Core deliverables:

- AI tool inventory
- approved tools registry
- blocked/prohibited tools list
- prompt and data risk map
- source/provenance checklist
- human review and approval rules
- external action approval policy
- audit log template
- compliance record schema
- sample completed receipts
- OBS/video/screenshot evidence policy
- public posting and reputation guardrail
- incident reconstruction worksheet
- 30-day adoption checklist

Optional add-ons:

- role-based AI use policy
- department-specific prompt/data rules
- client-facing AI disclosure language
- internal training deck
- monthly audit review packet
- ORACLE-backed local prototype, when separately approved

## 6. Compliance Record Schema

Minimum fields for each AI work record:

| Field | Purpose |
|---|---|
| `action_id` | Stable unique identifier for the work event |
| `created_at` | Timestamp when the record was opened |
| `operation_type` | Draft, research, summarize, classify, code, post-draft, file-change proposal, etc. |
| `task_purpose` | Plain-language reason the AI was used |
| `requested_by` | Human or system that requested the work |
| `business_owner` | Person accountable for the workflow |
| `produced_with` | Tool/model/application used |
| `token_origin` | Whether text/code was human-written, AI-assisted, AI-generated, pasted, imported, or mixed |
| `authorial_authority` | Person or entity with final authorship authority |
| `source_refs` | Files, URLs, emails, docs, tickets, screenshots, logs, or testimony used |
| `source_status` | Verified, unavailable, pasted-only, screenshot-only, inferred, unknown, or post-event testimony |
| `connector_used` | Connector/tool actually used, if any |
| `connector_result_id` | Receipt, request id, document id, message id, issue id, or local path |
| `reviewed_by` | Human reviewer |
| `approved_by` | Human approver |
| `approval_status` | Draft, needs_review, approved, rejected, expired, revoked |
| `allowed_tools` | Tools permitted for this work |
| `blocked_tools` | Tools forbidden for this work |
| `external_action` | Whether anything left the local/customer environment |
| `external_target` | Destination if external action was approved |
| `risk_category` | Low, medium, high, or critical |
| `privacy_class` | Public, internal, confidential, client, regulated, unknown |
| `receipt_path` | Where the evidence receipt is stored |
| `content_hash` | Hash of final or important artifacts when practical |
| `final_disposition` | Used, not used, archived, superseded, corrected, or deleted by policy |

Authorship rule:

AI assistance does not demote the human author's authorship. `token_origin` and
`authorial_authority` must remain separate fields.

## 7. Risk Matrix

| Risk Level | Examples | Required Control | External Action |
|---|---|---|---|
| Low | Internal brainstorming, rough outline, non-sensitive formatting, grammar cleanup | Tool/source note and optional receipt | Not allowed by default |
| Medium | Customer-facing draft, internal policy draft, business research, non-sensitive code/doc assistance | Source checklist, human review, approval record | Requires explicit approval |
| High | Client deliverable, sales/legal/financial/medical-adjacent content, code that changes production behavior, confidential data use | Full receipt, source verification, named reviewer, named approver | Requires explicit approval and target record |
| Critical | Regulated data, legal position, financial decision, health/safety claim, credential/payment/admin action, deletion, public accusation, mass messaging | Stop-and-escalate; specialist/legal/compliance review as applicable | Blocked until separately approved outside the AI workflow |

Default rule:

If the source, privacy class, approver, or external target is unknown, classify
the work at least one risk level higher.

## 8. External Action Approval Policy

External actions are any actions that send, publish, commit, push, delete,
purchase, message, invite, modify shared files, contact third parties, or move
data outside the approved workspace.

Policy:

- AI may draft an external action.
- AI may prepare a proposal for an external action.
- AI may summarize risks and source status.
- AI may not execute the external action without explicit human approval.

Approval record must include:

- approving human
- exact action approved
- destination or target
- final content or artifact
- source references
- risk category
- timestamp
- receipt path

Non-negotiable distinctions:

- Drafting is not sending.
- Preparing a post is not publishing.
- Creating a proposal is not approval.
- Connector visibility is not permission.
- Tool availability is not authorization.

## 9. Connector Provenance Rules

Connector provenance answers: "Did the AI actually see the thing it says it
saw?"

Source classes:

- verified connector result
- local file read
- user-provided pasted content
- screenshot evidence
- OBS/video-log evidence
- exported archive
- human testimony
- inferred context
- unsupported model claim
- unknown

Rules:

- Do not claim a connector was used unless it was actually used.
- Do not claim a file, email, Drive doc, issue, calendar item, contact, or
  message was reviewed unless its content or metadata was actually inspected.
- Preserve connector failures as evidence.
- Preserve unknown fields as unknown.
- Preserve contradictions rather than smoothing them into one story.
- Label post-event testimony as post-event testimony.
- Keep source facts separate from assistant inference.

Minimum connector receipt:

- connector/tool name
- query or target
- timestamp
- result id or path
- success/failure status
- summary of data actually returned
- fields intentionally not available

## 10. OBS/Video-Log Evidence Policy

OBS, screen recordings, screenshots, and video logs can support AI work audits,
but they require careful handling.

Permitted uses:

- corroborate workflow timing
- show interface state
- show visible tool output
- show approval prompts or blocked actions
- reconstruct failure paths
- demonstrate process for internal review

Required controls:

- privacy review before sharing
- redaction of credentials, personal data, client data, and private messages
- timestamp and file-path receipt
- hash when practical
- notes on what the video does and does not prove
- explicit approval before external use

Boundary:

Raw video is not automatically compliance evidence. It becomes evidence only
when indexed, labeled, reviewed, and tied to a specific audit question.

## 11. What This Is Not

AI Compliance Core is not:

- legal advice
- a replacement for a lawyer, compliance officer, security officer, or executive
  decision-maker
- a regulator-recognized certification by itself
- a guarantee that AI output is true
- a guarantee that a company is compliant with any specific law
- a general-purpose policy PDF generator
- an autonomous posting, emailing, committing, or publishing agent
- a tool for bypassing human review
- a claim that ORACLE is sentient, biological, sovereign, or autonomous
- a creative-world bible
- the Legacy.GI dissertation

## 12. 30-Day MVP Build Plan

The MVP is a docs-and-template product first. Runtime automation comes later
only after the offer is clear.

### Week 1: Package The Offer

Deliverables:

- one-page offer sheet
- intake questionnaire
- AI tool inventory template
- approved/blocked tools registry template
- compliance record schema template

Acceptance check:

A customer can understand the offer in five minutes and identify one workflow
to audit.

### Week 2: Build The Audit Kit

Deliverables:

- prompt/data risk map template
- source/provenance checklist
- external action approval policy
- public posting and reputation guardrail
- OBS/video-log evidence policy
- incident reconstruction worksheet

Acceptance check:

The kit can classify a real AI-assisted task as low, medium, high, or critical
and produce a record that a manager can review.

### Week 3: Pilot On One Workflow

Deliverables:

- select one pilot workflow
- fill out the tool inventory
- create 5 to 10 sample AI work records
- test review and approval status fields
- capture at least one source verification example
- capture at least one blocked or not-approved external action example

Acceptance check:

A third party can reconstruct what happened from the receipts without needing
the original operator to explain the whole session from memory.

### Week 4: Turn It Into A Sellable Packet

Deliverables:

- product brief
- customer-facing checklist
- before/after workflow example
- sample audit packet
- pricing hypothesis
- implementation checklist
- FAQ and non-goals page

Acceptance check:

The offer is ready for a discovery call, a pilot customer, or a simple landing
page without requiring new ORACLE runtime code.

## 13. First Version Success Criteria

The first version succeeds if:

- the customer has an approved AI tools list
- risky AI actions require named human approval
- source use is visible instead of guessed
- AI-assisted authorship is labeled without demoting human authority
- external actions are separated from drafts
- at least one workflow has real sample receipts
- the team can reconstruct an AI decision later

The first version fails if:

- it becomes a broad, vague AI governance brand
- it depends on unsupported legal/certification claims
- it blurs draft vs external action
- it claims connector access without evidence
- it sells mythic or creative language as business proof
- it requires custom software before the offer is understandable

## 14. Suggested Next Document

After this product map, the next useful artifact is:

`docs/ai_compliance_core_work_audit_kit_template.md`

That file should contain the actual customer-ready templates:

- intake form
- AI tool inventory
- approved tools list
- risk map
- receipt template
- approval log
- incident reconstruction worksheet
