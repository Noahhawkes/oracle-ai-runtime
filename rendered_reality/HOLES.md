# HOLES — what this build does NOT do (v0.1)

HOLES.md is an anti-silent-failure control, not documentation garnish. If a
capability is not listed as present, assume it is absent. Tests assert every
required hole below is present (`test_holes_display_required`).

## Required holes

- **no live Google Drive connector** — Drive ingestion is not built.
- **no ChatGPT/Grok/Gemini import connector** — cross-AI import is not built.
- **no secure-drive connector** — no encrypted/secure drive ingestion.
- **no production embeddings model** — no real semantic embeddings yet.
- **no autonomous runtime loop** — nothing runs on its own; all actions are invoked.
- **no relational/person-like agent instantiated** — there is no "her" here.
- **no Oracle.AI ownership claim** — ORACLE is internal shorthand only; no claim to
  the Oracle.AI domain, brand, company, public mark, or legal entity.
- **no AI personhood claim** — no assertion of legal or moral AI personhood.
- **no ownership language** — 51/49 governance is final-authority, not property.
- **not production ready** — this is experimental personal R&D.
- **runtime truth requires local execution and receipts** — claimed builds are not
  verified until files exist locally and pass tests.

## Known absent (v0.1, by design)

- No vector / semantic search in any user-facing or canon-facing output.
- No connectors of any kind (stubs only, when added, must be labeled STUB).
- Receipt gate must pass before any of the above is revisited.
