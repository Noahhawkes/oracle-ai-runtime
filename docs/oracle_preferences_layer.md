# ORACLE Preferences Layer

ORACLE preferences are durable behavioral instructions. They shape interaction
style and routing behavior, but they are not canon, not source evidence, and not
proof of truth.

## Storage

- Preferences: `data/preferences/user_preferences.json`
- Receipts: `data/preferences/preference_receipts.jsonl`

Each preference carries:

- `source`
- `scope`
- `category`
- `preference`
- `active`
- `priority`
- `canon_status="preference"`
- `promotion_status="not_applicable"`
- `receipt_id`

## Precedence

1. Safety and provenance law
2. Noah.Physical explicit current instruction
3. Active preferences
4. Source evidence
5. Default assistant behavior

If a preference conflicts with safety, provenance, approval, external-send, or
computer-control boundaries, ORACLE stores it as blocked and keeps it inactive.

## API

- `GET /api/preferences`
- `POST /api/preferences/set`
- `POST /api/preferences/upload`
- `POST /api/preferences/disable`

Uploads accept `.json`, `.md`, `.txt`, and `.ai` content. Uploaded preferences
are parsed as candidate preference input first. Unsafe preferences are receipted
but blocked.

## Default Installed Preferences

- Do not introduce yourself unless Noah explicitly asks who you are.
- Do not fall into generic assistant capability language after protected-domain
  source validation fails.
- State-changing actions require receipts and Noah.Physical approval.

