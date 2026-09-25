# Governed continuity integration baseline

This change starts from `continuity/personal-journal-20260816` because it
contains the recent runtime integrations. The default `archive/runtime-lineage-2e6b0a3`
is a smaller historical line. Draft PR #15 proposes a large integration into
that archive line and must be reviewed independently; this branch does not
silently merge it. The provenance changes in PR #26 are already present on
the journal line. The missing `rendered_reality/memory` files and the root
`Memory/` ignore rule are drawn from PR #14.

## Boundaries enforced here

- Human statements are recorded as attributed testimony, staged for review.
  The speaker, author, submitter, and account owner stay distinct. An unknown
  actor remains `UNKNOWN`. Existing legacy facts without actor evidence are
  downgraded in place, retaining their former status in correction history.
- Canon promotion needs a receipt, an explicit approval record for its exact
  content hash and receipt ID, and `Noah.Physical` as the recorded approver.
  The service invoking `record_approval` must authenticate that actor; a
  caller supplied string by itself is not identity proof.
- Chat output and route names can mention actions and receipt paths but cannot
  establish execution. The packet records such paths as unverified mentions.
  Only upstream structured verification results with action ID and receipt hash
  populate `actions_executed`. That upstream verification must validate the
  underlying receipt before setting `verified=true`.
- Packet files are replaced atomically. The latest pointer advances after
  the index append is flushed. A crash between these writes can leave an
  indexed event newer than `latest.json`; reconciliation is future work.

## Verification and deployment

The focused Linux suite covers provenance, cold reload, approval and action
claims. It is not a Windows desktop or live ORACLE test. Before deploying to
`C:\Oracle\ORACLE.AI-runtime`, back up the durable memory database, review
legacy downgrades, authenticate canon approvals at the UI/service boundary,
and run the focused suite plus live port 7781 checks on that machine. Do not
promote candidate records to canon during integration.

## Public custody

This repository and pull requests are public. Keep private conversations,
names beyond necessary fixture identities, raw receipts, local database files,
secrets, and Windows runtime state out of commits. Existing public history
needs a separate custody review before any rewrite or archival decision.
