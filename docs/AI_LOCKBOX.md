# ORACLE .AI Lockbox

The `.AI Lockbox` is ORACLE's local, read-only recall staging layer. It turns readable source material into compact `.AI` shorthand capsules so the front-end chat can search and speak grounded context without changing the original files.

## Boundary

- Source files are not moved, renamed, edited, deleted, uploaded, or promoted to canon.
- Credential-risk files are skipped for raw ingest. Sensitive matches are metadata-only.
- Capsules are local candidate recall records under `Memory/ai_lockbox/capsules`.
- Noah.Physical remains final correction authority.

## Chat Commands

- `/ai-lockbox-status` shows capsule and receipt counts.
- `/ai-lockbox-ingest <query>` builds `.AI` capsules from readable files whose paths match the query. Leave the query blank for the first readable batch.
- `/ai-lockbox-search <query>` searches existing `.AI` capsules.
- `/ai-shorthand <path>` creates one capsule for a specific readable file.

## API

- `GET /api/ai-lockbox/status`
- `POST /api/ai-lockbox/ingest` with `{ "query": "", "limit": 25 }`
- `GET /api/ai-lockbox/search?q=oracle&limit=8`
- `GET /api/ai-lockbox/capsule?path=docs/AI_LOCKBOX.md`

## UI

The cockpit top bar shows `Recall N`. Its detail panel can ingest, search, or search and speak the top `.AI` recall hit through the browser speech path.
