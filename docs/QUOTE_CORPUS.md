# ORACLE Quote Corpus

Quote Corpus is ORACLE's local exact-excerpt layer.

It exists because the existing recall surfaces answer different questions:

- Document Atlas proves that a source exists and preserves metadata.
- File Recall can find and preview readable files.
- AI Lockbox creates compact `.AI` shorthand summaries.
- Quote Corpus creates bounded exact quote packets with source hashes, line ranges, and receipts.

This is the first layer meant to let ORACLE cite Noah's words without pretending that metadata, summaries, or assistant paraphrases are source evidence.

## Boundary

Quote Corpus is candidate-only and local.

- Source files are read-only.
- Source files are not edited, moved, deleted, uploaded, synced, or promoted.
- Credential-risk paths and secret-looking content are skipped.
- Packets are written under `Memory/quote_corpus/`.
- Packetized excerpts remain `canon_status=candidate` and `promotion_status=not_promoted`.
- This layer does not claim full-corpus semantic understanding.

## Files

- `Memory/quote_corpus/packets/*.ai`: one `.AI:QUOTE_SOURCE_PACKET/<source_id>` file per source text hash.
- `Memory/quote_corpus/manifest.jsonl`: searchable quote rows.
- `Memory/quote_corpus/receipts.jsonl`: ingest receipts, including gated/skipped sensitive records.
- `Memory/quote_corpus/latest_status.json`: latest count/status payload.

## ORACLE chat commands

```text
/quote-corpus-status
/quote-corpus-ingest rendered reality
/quote-corpus-search rendered reality
/quote-source C:\Users\noahh\OneDrive\Documents\ThreadMerge 06242026.docx
```

`/quote-corpus-ingest <query>` scans readable granted roots for a bounded batch of matching supported files. It does not scan everything at once.

`/quote-source <path>` packetizes one readable supported source file.

## API

```text
GET  /api/quote-corpus/status
POST /api/quote-corpus/ingest
GET  /api/quote-corpus/search?q=<query>&limit=8
GET  /api/quote-corpus/packet?path=<absolute-or-runtime-relative-path>
```

The ingest body accepts:

```json
{
  "query": "rendered reality",
  "limit": 5,
  "max_quotes_per_file": 80
}
```

## Supported source types

The initial extractor supports text-like files and `.docx`.

PDFs, images, audio, video, native Google Docs export, and OCR are not part of this first layer. Those should be added as separate extractors with their own receipts.

## How ORACLE should use it

When a quote-corpus hit exists, ORACLE should cite:

- source title
- source path
- line range
- exact excerpt

When no quote-corpus hit exists, ORACLE should say that exact excerpt evidence is not packetized yet, then fall back to Document Atlas, File Recall, AI Lockbox, thread ingest, or durable memory with the correct lower confidence.
