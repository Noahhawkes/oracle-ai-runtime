# ORACLE Thread Capture Architecture

Goal: every AI-system thread can be transported into ORACLE as custody-bound
evidence without becoming canon.

Core law:

```text
Transport everything.
Trust nothing until classified.
```

## Sources

Supported as explicit user-supplied artifacts:

- ChatGPT
- Claude
- Claude Code
- Codex
- Gemini
- Grok
- GitHub Copilot
- ORACLE local exports
- Google Drive exports
- screenshots
- PDF exports
- HTML exports
- copy/paste text

This system does not scrape accounts, watch browsers, capture keystrokes, upload
files, delete source files, mutate source exports, or auto-promote anything.

## Storage Paths

```text
Memory/thread_ingest/
Memory/thread_ingest/raw_transcripts/
Memory/thread_ingest/parsed_transcripts/
Memory/thread_ingest/source_manifests/
Memory/thread_ingest/custody_receipts/
Memory/thread_ingest/search_index.jsonl
thread_exports/
```

## Pipeline

```text
AI Thread Source
-> Capture
-> Normalize
-> Speaker Provenance
-> Thread ID
-> Timestamp
-> Source System
-> Message Order
-> Token Origin
-> Authorial Authority
-> Claim Type
-> Receipt Hash
-> Store Raw
-> Store Parsed
-> Searchable Index
-> Canon Candidate Only
```

## Schema

Transcript metadata:

```text
source_system
source_thread_id
captured_by
capture_method
captured_at
original_source_path
raw_file_path
raw_sha256
message_count
participants
known_authors
unknown_authors
contains_ai_generated_text
contains_user_submitted_text
parse_status
canon_status: candidate
promotion_status: not_promoted
```

Message rows:

```text
speaker
message_text
message_index
timestamp_if_known
token_origin
authorial_authority
claim_type
canon_status: candidate
promotion_status: not_promoted
```

Custody receipts:

```text
receipt_kind
operation
recorded_at
source_system
source_thread_id
captured_by
capture_method
raw_file_path
raw_sha256
parsed_transcript_path
source_manifest_jsonl
search_index_jsonl
receipt_hash_sha256
account_scrape_performed: false
source_file_mutated: false
cloud_upload: false
git_commit: false
git_push: false
```

## Provenance Rules

- User-channel text is transport, not proof of Noah authorship.
- `User:` and `Human:` become `authorial_authority: unknown`.
- `Noah.Physical:` becomes `authorial_authority: Noah.Physical`.
- AI speakers become `token_origin: ai_generated_text` and
  `authorial_authority: unknown`.
- Copy/paste preserves original speaker when known.
- Unknown authorship remains unknown.
- Captured thread means evidence candidate, not canon.
- Canon promotion requires explicit Noah.Physical approval outside this module.

## Commands

CLI:

```powershell
python core/thread_capture.py --status
python core/thread_capture.py --ingest-file path\to\thread.html --source-system ChatGPT --source-thread-id thread-123
python core/thread_capture.py --ingest-dir thread_exports\sqlite_sessions --source-system ORACLE --capture-method sqlite_session_export
Get-Content thread.txt | python core/thread_capture.py --ingest-stdin --source-system Claude --source-thread-id claude-123
python core/thread_capture.py --search "Rendered Reality"
```

ORACLE chat:

```text
/thread-ingest-status
/thread-ingest-file <source-system> | <path> | <optional-thread-id> | <optional-capture-method>
/thread-ingest-dir <source-system> | <directory> | <optional-pattern> | <optional-capture-method> | <recursive:true|false>
/thread-ingest-paste <source-system> | <source-thread-id> | <transcript text>
/thread-capture-evidence <source-system> | <source-thread-id> | <transcript text>
/thread-capture-search <query>
```

HTML files are normalized with local text extraction. PDF files are always
stored raw; if a local `pypdf` runtime is available, text is extracted into the
parsed transcript as well. Screenshots and image files are stored as raw visual
evidence until an explicit OCR step is added.
