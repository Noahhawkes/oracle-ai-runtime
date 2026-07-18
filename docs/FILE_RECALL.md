# File Recall

Status: Built 2026-07-13 — live at next server relight

ORACLE's front-end talk lane has governed READ access to Noah's files,
documents, and folders. Three ways in:

```text
/file-search <query>          explicit search (deep: filenames + content)
/file-read <path>             read a file (text formats + .docx)
/sensitive-inventory [query]  list credential-risk paths by metadata only
read file <path>              natural language forms route the same lane
search my files for <query>
GET /api/file-recall/search?q=<query>
GET /api/file-recall/read?path=<path>
GET /api/file-recall/sensitive-inventory?q=<query>
```

**Automatic conversation grounding** — the part that makes her feel present:
when Noah's message references his files, documents, folders, drive, notes,
novels, or manuscripts, the talk lane runs a fast filename recall (deep
content scanning is skipped so chat never lags) and injects the matching
files with previews into her model context. She cites real paths.

## Allowed roots

- C:\Oracle\ORACLE.AI-runtime (including read-only view of the sandbox)
- C:\Users\noahh\Documents, Desktop, Downloads
- G:\My Drive (filename search only — content is never bulk-downloaded
  from Drive File Stream)

## Boundary

READ ONLY, always:

- no write, delete, rename, move, upload, external send, canon promotion
- secret/credential paths hard-blocked by directory name (.ssh, .aws, .git,
  obs_captures, credentials, ...) and filename pattern (id_rsa, *.pem, *.key,
  token, password, api_key, .env, oauth, ...)
- sensitive inventory may show path, name, size, modified time, and risk reason,
  but never reads raw values or stores them in receipts
- 2 MB per-file cap, 8k-char previews, bounded walks
- every search and read appends a receipt to
  `Memory/file_recall_receipts.jsonl`

## Related

The creation witness (`tools/witness/creation_witness.py`, keeper-managed)
watches the same creative surfaces in the other direction: it records what is
being written or created (metadata only, never content) to
`Memory/creation_feed.jsonl`, which feeds ORACLE's self-prompt grounding and
the Jupiter Station command deck (`/jupiter`, `/api/creation-feed`).
