# Rendered Reality - Source Family Map v0.1

Status: candidate source map (preserve-first, no ingestion)
Authority: Noah.Physical
Recall: Noah.Physical live OBS recall + Google Drive search confirmation, 2026-06-28
Continues: TP_018 (MiricleDrive connector restore), TP_019 (machine_scan_inventory)

## What this is

Rendered Reality is **not a single document**. It is a *source family* - a fossil
bed of related-but-distinct artifacts from a large archive effort to make Noah's
full human/project record readable by AI: every thread, every moment, every file,
every log, zipped material, AI-readable source archives, and workspace-era
(VS Code / Copilot / GitHub) experimentation.

This map records what was found and how it must be treated. It does **not** ingest,
merge, smooth, or rewrite anything. Map first, then thread families, then timeline,
then doctrine, then code artifacts, then receipts.

## Source categories (do not collapse across these)

- `philosophical_thesis` - "Rendered Reality: A Logical Exploration" type doctrine
- `personal_archive` - categorized journals, insights
- `personality_profile_extraction` - profile/values models derived from Noah's material
- `personal_evolution_extraction` - evolution/change models derived from Noah's material
- `thread_export` - exported AI conversations (Grok, ChatGPT, etc.)
- `filtered_data` - spreadsheets of filtered thread rows ("You said:" lines)
- `creative_media_branch` - fiction/satire (e.g. The Silverback Tales)
- `ai_readable_continuity_corpus` - the umbrella intent across the above

## Boundary laws (enforced as constants in the manifest + receipt)

- `RENDERED_REALITY_ARCHIVE != SINGLE_DOCUMENT`
- `THREAD_EXPORT != CANONICAL_FACT`
- `AI_SUMMARY != PRIMARY_SOURCE`
- `FILTERED_CONTENT != FULL_CONTEXT`
- `CREATIVE_BRANCH != TECHNICAL_SPEC`
- `SOURCE_FAMILY_MAP_PRECEDES_INGESTION`

## Rules

- Preserve provenance per source. Never merge authorship categories.
- A manuscript Noah authored, an AI categorization of his material, an exported
  multi-agent thread, a filtered spreadsheet, and a creative branch are FIVE
  different authorship situations. Keep them separable.
- `authorship_status` is never inferred from first-person wording or from a file
  living on Noah's drive. `LOCAL_FILE_PRESENCE != AUTHORSHIP`.
- Nothing here is approved or canonical. Indexing in this map is discovery only.
- Drive IDs / URLs / timestamps are populated only when connector-verified; until
  then they are `null` with an explicit hole, never fabricated.

## Relationship to ORACLE / MiricleDrive

- **Rendered Reality** = upstream doctrine + archive source family (the corpus).
- **MiricleDrive** = the scanner/inventory tool that discovers and groups these
  files (the map-maker) - see `machine_scan_inventory`.
- **ORACLE.AI** = the runtime witness that indexes, preserves provenance, and
  refuses to promote discovery into authorship or canon without Noah.Physical.

## Excavation order (proposed)

1. Source map (this file) ->
2. thread families ->
3. timeline ->
4. doctrine extraction ->
5. code artifacts ->
6. receipts / canon review.

Index data: `research_canon/rendered_reality_source_family.jsonl`
