# Document Atlas Status

Status: built and reconciled 2026-07-17  
Authority: Noah.Physical  
Canon status: candidate_unreviewed  
Promotion status: not_promoted  
Sandbox status: not touched

The document atlas is a read-only, candidate-only index of Noah's document
surfaces for ORACLE recall and classification. It does not promote canon, write
to Drive, write to sandbox, send externally, or store raw document text.

## Latest Unified Atlas

The current runtime atlas is the unified Memory atlas, not the earlier smaller
`data/document_atlas` pass.

- Summary: `Memory/document_atlas/unified_document_atlas_latest.md`
- JSONL: `Memory/document_atlas/unified_document_atlas_latest.jsonl`
- Receipt: `Memory/document_atlas/unified_document_atlas_receipt_latest.json`
- Local-only first pass: `Memory/document_atlas/document_atlas_latest.jsonl`
- Nexus live surface: `/nexus` and `/api/nexus`
- API status route: `/api/document-atlas/status`
- API search route: `/api/document-atlas/search?q=thread+injection`

## Readback Counts

From `Memory/document_atlas/unified_document_atlas_receipt_latest.json`:

- Total candidate records: `18,924`
- Local / Drive-for-Desktop records: `9,211`
- Unique Google Drive connector records: `9,713`
- Cloud-sync filesystem records: `5,173`
- Local filesystem records: `4,038`
- Duplicate `.gdoc` pointers removed: `0`

## Candidate Categories

- `general_document_candidate`: 7,994
- `oracle_runtime_and_doctrine`: 4,151
- `personal_and_relationship`: 2,284
- `sov1_governance_and_compliance`: 2,157
- `thread_and_conversation`: 841
- `creative_writing`: 403
- `identity_and_legacy`: 314
- `patent_invention_and_research`: 263
- `administrative_and_legal`: 219
- `rendered_reality_and_worldbuilding`: 216
- `ecowater_and_professional`: 82

## Extensions / MIME Types

- `.txt`: 4,805
- `.docx`: 4,344
- `text/plain`: 3,865
- `application/vnd.openxmlformats-officedocument.wordprocessingml.document`: 3,682
- `application/vnd.google-apps.document`: 2,166
- `.doc`: 62

## Connector Coverage Note

Eight sub-minute Google Drive import intervals still returned the connector
maximum of 200 results. Drive-for-Desktop metadata is indexed separately and
may cover corresponding mirrors, but absolute connector completeness is not
claimed for those burst windows.

Intervals with unresolved connector saturation:

- `2026-06-30T23:55:04.687Z` to `2026-06-30T23:55:46.875Z`
- `2025-03-20T19:01:20.859Z` to `2025-03-20T19:01:57.773Z`
- `2025-04-02T00:20:33.984Z` to `2025-04-02T00:21:10.898Z`
- `2025-04-17T18:18:43.242Z` to `2025-04-17T18:19:20.156Z`
- `2025-04-17T18:19:20.156Z` to `2025-04-17T18:19:57.070Z`
- `2025-05-26T22:05:39.257Z` to `2025-05-26T22:06:16.171Z`
- `2026-01-08T18:08:57.890Z` to `2026-01-08T18:09:34.804Z`
- `2026-01-08T18:09:34.804Z` to `2026-01-08T18:10:11.718Z`

## Boundaries

- All records remain candidate-only.
- `canon_promotion=false`
- `drive_mutation=false`
- `external_send=false`
- `file_mutation=false`
- `raw_content_stored=false`
- No sandbox writes or reads are required for this atlas.
- Atlas results are evidence for recall and routing, not proof of canon.

## Older Local Pass

An earlier local/cloud-sync metadata pass remains under `data/document_atlas`.
It found `8,391` records and is useful as a smaller fallback, but it is no
longer the current atlas of record.

## Hashes

- Unified index SHA256:
  `db2f2c055cfb46d711c781d35dc7dddd91a3be4a7db06fb3eea1a39a8a06da80`
- Unified receipt SHA256:
  `d3a57545221d4e1aa76f69d9977c4939812b8e3afe9be41546e11322f098920b`
