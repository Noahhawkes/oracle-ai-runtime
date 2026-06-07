# External Integration Sovereignty Design

Version: 1.0
Authority: Noah A. Hawkes
Status: Active design — ApprovalGate implemented, connectors not yet built.

---

## The Rule in One Sentence

If ORACLE sees it, that does not mean ORACLE owns it.
If ORACLE renders it, that does not mean ORACLE remembers it.
Only the sovereign human decides what becomes memory.

---

## 51/49 Human Sovereignty Rule

| Role | Who | What |
|---|---|---|
| Renderer (49%) | ORACLE | Fetch, parse, filter, structure, suggest, render candidates |
| Sovereign (51%) | Noah | Approve, reject, correct, delete, revoke, quarantine |

ORACLE performs the 49% without exception. Noah controls the 51% without override.

---

## Mandatory Integration Flow

```
External Source (Gmail / Calendar / Drive / Browser / File / API)
    ↓
ExternalConnector.fetch_raw()
    ↓  [raw bytes / JSON / HTML — never touches memory]
ExternalConnector.render_candidates()
    ↓  [structured CandidateEvent list — noise filtered, meaning suggested]
ApprovalGate.submit(candidates)
    ↓  [written to Projects/pending_candidates/ as JSON — status: PENDING]
    ↓  [Noah is notified — displayed in ORACLE console or Overlay]
Noah reviews → approves / rejects / corrects each candidate
    ↓
ApprovalGate.commit_approved(candidate_id)
    ↓  [calls memory.upsert_fact() — the ONLY path to permanent memory]
Memory Ledger (oracle_memory.db)
```

No step may be skipped. No connector may shortcut directly to `memory.upsert_fact()`.

---

## Core Components

### 1. `CandidateEvent` (data structure)

A structured, pending memory proposal. Fields:

| Field | Type | Description |
|---|---|---|
| `id` | str | Unique ID (UUID) |
| `source` | str | Origin system: `gmail`, `calendar`, `drive`, `file`, `browser` |
| `source_ref` | str | Reference in source system (email ID, event ID, file path) |
| `raw_excerpt` | str | Short excerpt of source text (max 500 chars) — never full raw content |
| `rendered_category` | str | Suggested memory category (from ORACLE Soul Directive list) |
| `rendered_key` | str | Suggested fact key |
| `rendered_value` | str | Suggested fact value — what ORACLE thinks this means |
| `confidence` | str | `high` / `medium` / `low` — ORACLE's confidence in the rendering |
| `status` | str | `PENDING_HUMAN_APPROVAL` / `APPROVED` / `REJECTED` / `CORRECTED` |
| `submitted_at` | str | ISO timestamp |
| `decided_at` | str | ISO timestamp — set when Noah approves/rejects |
| `correction` | str | Noah's corrected value if status is `CORRECTED` |
| `sensitive_flag` | bool | True if secret pattern was detected — must not be ingested |

### 2. `ApprovalGate` (core/integration_gate.py)

The mandatory intermediary between all external connectors and the memory ledger.

Methods:

| Method | Description |
|---|---|
| `submit(candidates)` | Accept a list of CandidateEvents, write to pending store, return IDs |
| `list_pending()` | Return all candidates with status PENDING_HUMAN_APPROVAL |
| `approve(candidate_id)` | Mark approved, call memory.upsert_fact(), set status APPROVED |
| `reject(candidate_id)` | Mark rejected, set status REJECTED — never written to memory |
| `correct(candidate_id, new_value)` | Noah corrects the rendered value — write corrected version to memory |
| `purge_old_pending(days)` | Remove pending candidates older than N days without approving |

### 3. `ExternalConnector` (base interface — not yet implemented per source)

Every connector must implement:

```python
class ExternalConnector:
    def fetch_raw(self) -> list[dict]:
        """Fetch raw data from source. Never touches memory."""
        ...

    def render_candidates(self, raw: list[dict]) -> list[CandidateEvent]:
        """Parse raw into structured candidates. Apply noise filter.
        Apply sensitive data filter. Return candidate list."""
        ...
```

Connectors may NOT implement a `write_memory()` method.
Connectors may NOT import `memory` directly.
Connectors call `ApprovalGate.submit()` — nothing else.

---

## Pending Store

Pending candidates are written to disk before Noah reviews them.
This ensures candidates survive a session restart.

Location: `Projects/pending_candidates/`

File per batch: `YYYY-MM-DD_HHMM_<source>.json`

Format:
```json
{
  "batch_id": "uuid",
  "source": "gmail",
  "submitted_at": "2026-06-06T16:00:00",
  "candidates": [
    {
      "id": "uuid",
      "source": "gmail",
      "source_ref": "email_id_abc123",
      "raw_excerpt": "Noah, your proposal is due Friday...",
      "rendered_category": "work",
      "rendered_key": "proposal_deadline_client_x",
      "rendered_value": "Proposal due to client X by Friday 2026-06-09",
      "confidence": "high",
      "status": "PENDING_HUMAN_APPROVAL",
      "submitted_at": "2026-06-06T16:00:00",
      "decided_at": null,
      "correction": null,
      "sensitive_flag": false
    }
  ]
}
```

---

## Google Workspace — Specific Rules

### Gmail

| Allowed | Forbidden |
|---|---|
| Read message subjects, sender names, first 200 chars of body | Read full message body into memory |
| Render deadline / commitment candidates | Auto-ingest any email content |
| Identify repeated senders | Store email addresses without approval |
| Flag action items for approval | Store OAuth tokens anywhere except `.env` |

### Calendar

| Allowed | Forbidden |
|---|---|
| Read event titles, dates, times, attendee count | Read attendee email addresses into memory |
| Render upcoming commitment candidates | Auto-ingest meeting notes |
| Flag recurring meetings for pattern detection | Store calendar API credentials in memory |

### Drive

| Allowed | Forbidden |
|---|---|
| Read document titles, last modified date, owner | Read full document content into memory |
| Render project-related document candidates | Store Drive OAuth tokens in memory |
| Flag documents matching active project names | Auto-summarise documents without approval |

### Contacts / People

| Allowed | Forbidden |
|---|---|
| Read contact names | Read phone numbers, addresses, or emails into memory without approval |
| Suggest person entries for Noah's people table | Auto-add contacts to memory |

---

## Token and Secret Handling

OAuth tokens, refresh tokens, client secrets, and API keys:

1. **Storage:** `.env` file only. Never in `Memory/oracle_memory.db`. Never in any JSON candidate file. Never in any log file.
2. **Prompts:** Never passed to the LLM as part of any prompt or context.
3. **Logs:** The `sensitive_flag` on `CandidateEvent` is set to `True` if any secret pattern is detected. Flagged candidates are never approved — they are quarantined automatically.
4. **Debug output:** `audit_log.py` must never write token values. Log event types only.

Secret patterns that trigger `sensitive_flag = True`:
- `sk-...` (OpenAI-style keys)
- `AKIA...` (AWS keys)
- `ya29.` (Google OAuth access tokens)
- `1/...` (Google refresh tokens)
- `Bearer ...` in any value field
- `-----BEGIN ...-----` (private keys)
- Credit card patterns (13-16 digit sequences)
- SSN patterns (`\d{3}-\d{2}-\d{4}`)
- Passwords in key-value form (`password:`, `passwd:`, `secret:`)

---

## ORACLE Slash Commands (Future)

These commands will be added when connectors are implemented:

| Command | Description |
|---|---|
| `/pending` | List all PENDING_HUMAN_APPROVAL candidates |
| `/approve <id>` | Approve one candidate — writes to memory |
| `/reject <id>` | Reject one candidate — never stored |
| `/correct <id> <new_value>` | Correct ORACLE's rendering and approve |
| `/approve-all <source>` | Approve all pending from one source (requires confirmation) |
| `/reject-all <source>` | Reject all pending from one source |

---

## Implementation Order

### Phase 0 — Gate only (current — implemented)
`core/integration_gate.py` exists with `CandidateEvent`, `ApprovalGate`.
No connectors exist. No external data flows yet.
The gate can be tested with manually constructed candidates.

### Phase 1 — File connector
Read local files from approved paths.
Render text excerpts as candidates.
Lowest risk — no OAuth, no external network.

### Phase 2 — Gmail connector
OAuth 2.0 via `google-auth` library.
Read-only Gmail scope: `gmail.readonly`.
Subject + sender + first 200 chars only.
All candidates pending until approved.

### Phase 3 — Calendar connector
OAuth 2.0 read-only Calendar scope.
Upcoming events (next 7 days) only.
No attendee email addresses in candidates.

### Phase 4 — Drive connector
OAuth 2.0 read-only Drive scope.
Metadata only (title, modified date, owner name).
No document body content without explicit Noah request.

### Phase 5 — `/pending` review UI in Overlay
Display pending candidates in the Overlay panel.
One-click approve / reject / correct.
Most important phase for usability.

---

## Acceptance Criteria for Any New Connector

A connector is safe to ship when:

1. `fetch_raw()` touches no memory imports
2. `render_candidates()` applies the sensitive pattern filter — `sensitive_flag` is set
3. No token or credential appears in any `CandidateEvent` field
4. All candidates arrive with `status: PENDING_HUMAN_APPROVAL`
5. `ApprovalGate.submit()` is the only write call the connector makes
6. A manual test of approve / reject / correct works end-to-end
7. Noah has reviewed and approved the connector's scope before it is wired to a scheduled poll
