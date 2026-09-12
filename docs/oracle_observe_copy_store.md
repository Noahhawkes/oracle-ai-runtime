# ORACLE Observe.Copy.Store Custody Sweep

Status: implemented as a metadata-only first pass.

This sweep indexes ORACLE-adjacent artifacts without moving, copying, uploading,
executing, or canon-promoting them.

## Purpose

ORACLE needs to know where its adjacent files and connector-discovered artifacts
are before it can decide what deserves deeper custody. The first pass is an
evidence index, not an archive copy.

Markers:

- ORACLE
- OracleAI
- ORACLE.AI
- oracle-ai-runtime
- SOV1
- UserPath
- Rendered Reality
- Legacy.GI

## Pipeline

```text
Observe
  -> discover path and marker match
  -> hash matched file with SHA-256
  -> classify source system and sensitivity

Copy
  -> not performed in first pass
  -> requires explicit Noah.Physical approval

Store
  -> write metadata-only manifest
  -> write sweep receipt
  -> keep canon_status=candidate
  -> keep promotion_status=not_promoted
```

## Storage

- Manifest: `data/oracle_custody/oracle_artifact_manifest.jsonl`
- Latest receipt: `data/oracle_custody/oracle_custody_sweep_receipt_latest.json`
- Timestamped receipts: `data/oracle_custody/oracle_custody_sweep_receipt_*.json`

## Manifest Fields

Each artifact row includes:

- `source_path`
- `source_system`
- `filename`
- `extension`
- `size_bytes`
- `created_at`
- `modified_at`
- `sha256`
- `matched_terms`
- `custody_status`
- `copy_status`
- `store_status`
- `canon_status`
- `promotion_status`
- `sensitivity`
- `notes`

Additional operational fields may include `source_root`, `duplicate_count`, and
`duplicate_group_id`.

## Boundaries

- No file moves.
- No deletes.
- No uploads.
- No execution.
- No raw content duplication in first pass.
- No canon promotion.
- Private family, financial, medical, legal, or identity-adjacent paths may be
  indexed only when ORACLE markers are present, and are labeled high sensitivity.

## Command

```powershell
python -m core.oracle_custody_sweep
```

Optional focused scan:

```powershell
python -m core.oracle_custody_sweep --root C:\Oracle --root C:\ORACLE.AI
```

## Copy Gate

Copy candidates in the receipt are recommendations only. They are not copied.
A later copy step must require explicit Noah.Physical approval and must write a
separate receipt for every copied artifact.
