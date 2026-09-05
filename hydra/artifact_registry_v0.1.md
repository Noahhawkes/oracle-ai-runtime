# HYDRA Artifact Registry v0.1

Status: candidate spec
Authority: Noah.Physical
Mode: local-only
Durable memory: false

## Problem

People use AI to create meaningful artifacts, then those artifacts vanish into clipboard fog.

Emails, novels, posts, proposals, letters, research drafts, and messages often carry intent, memory, context, and human judgment. The final text alone is not enough. The system needs to preserve what the artifact was for, where it came from, what version was used, and whether it should be forgotten, parked, or remembered.

## Artifact Schema

artifact_id:
artifact_type: email | novel | post | proposal | memory | message | research | legal_draft | personal_letter
created_at:
created_by: Noah.Physical
tool_used:
prompt_context:
source_material:
generated_versions:
human_final:
destination: Gmail | LinkedIn | Docs | manuscript | CRM | nowhere | other
approval_status: candidate | approved | durable | discard
sensitivity: public | personal | private | sacred | regulated
provenance:
meaning_summary:
retention_rule:
canon_link:
source_hashes:

## Lane Rules

1. Candidate by default.
2. Human final is more important than generated drafts.
3. Preserve why it mattered, not every token of noise.
4. Sensitive artifacts require explicit approval before durable memory.
5. Public artifacts may be indexed, but still require provenance.
6. Sacred artifacts may be witnessed without being summarized.
7. Regulated artifacts require stricter containment.
8. No artifact becomes canon without Noah.Physical approval.

## Civilian Product Framing

Meaningful AI-generated work should not vanish after the send button.
Important artifacts need a home, a receipt, and human approval over what they become.
