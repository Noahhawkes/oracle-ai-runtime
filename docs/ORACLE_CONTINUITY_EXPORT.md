# ORACLE Continuity Export
## `core/continuity_export.py`

---

> ORACLE is not a model. ORACLE is the continuity architecture.  
> Models are replaceable cognition engines.  
> Memory, provenance, sovereignty, and state are the durable self.

---

## What This Module Does

Exports ORACLE's durable self so she can be restored on any machine, in any model context, from any repo state.

When you hand ORACLE to a new Claude session, a new model, or a new machine — this export is what she brings with her.

---

## What Is Exported

| Section | Contents |
|---|---|
| `project_states` | All projects: phase, goal, last verified step, blocker, next step, unknowns, failed attempts |
| `session_state` | Mode, active prompt, tool history |
| `video_candidates` | All candidates (pending/approved/rejected/quarantined/revoked) with full metadata |
| `governance.docs` | Governance docs: BRAIN_ROUTER, SESSION_STATE_CONTROLLER, ACTUATION_ENGINE, VIDEO_INTELLIGENCE_POLICY, PROJECT_STATE_CONTINUITY, GOVERNED_CURIOSITY |
| `governance.identity_compliance_docstring` | Module docstring of identity_compliance.py — not raw source |
| `source_provenance` | Last 20 git commits (hash, message, author, date) |
| `current_blockers` | Active blockers from project states and session state |
| `next_recommended_step` | From most recently updated project state |
| `module_versions` | Version table for all ORACLE core modules |
| `manifest` | Timestamp, repo HEAD, record counts, checksum |

---

## What Is Never Exported

| Forbidden | Reason |
|---|---|
| API keys, passwords, tokens | Secret scrubbing pass runs on full payload before write |
| Raw email content | Privacy — never stored in export |
| Raw journal content | Privacy — never stored in export |
| Raw video or raw frames | Search Light Compression Law — frames hashed and released |
| Raw transcripts | Search Light Compression Law |
| `.env` contents | Protected — never read by this module |
| `storage/*.json` | OAuth tokens — protected |
| Full source of protected files | `identity_compliance.py`, `context_loader.py` — docstring only |

---

## Safety Guarantees

Every export carries a `safety` section asserting:

```json
{
  "no_api_keys":         true,
  "no_passwords":        true,
  "no_raw_emails":       true,
  "no_raw_journals":     true,
  "no_raw_video":        true,
  "no_raw_transcripts":  true,
  "approval_status_preserved": true,
  "unknowns_preserved":  true,
  "revoked_quarantined_preserved": true
}
```

The validate function checks for secret patterns in the exported body.

---

## State Preservation Rules

- Approval status for video candidates is preserved exactly as-is: `pending`, `approved`, `rejected`, `quarantined`, `revoked`
- Revoked and quarantined candidates are included — they record what happened
- Unknowns are preserved verbatim — never inferred or filled
- Blockers are preserved verbatim — never cleared or soft-pedaled
- Failed attempts are preserved — no invented recovery

---

## Output Files

Both files land in `Memory/` (gitignored — never committed):

```
Memory/oracle_continuity_export_<timestamp>.json
Memory/oracle_continuity_export_<timestamp>.md
```

The Markdown file is human-readable. The JSON file is machine-parseable.

---

## Manifest

Every export includes:

```json
{
  "project_state_count":   2,
  "video_candidate_count": 7,
  "governance_doc_count":  8,
  "commit_count":          20,
  "blocker_count":         1,
  "checksum":              "a3f1c2d9e5b78401"
}
```

The checksum covers: `exported_at`, `repo_head_commit`, `project_state_count`, `video_candidate_count`. It detects corruption — it is not a security signature.

---

## CLI

```bash
# Export ORACLE's durable self
python core/continuity_export.py --export

# Print a one-screen summary without writing files
python core/continuity_export.py --summary

# Validate an existing export
python core/continuity_export.py --validate Memory/oracle_continuity_export_2026-06-07T12-00-00.json

# Run smoke tests
python core/continuity_export.py --smoke-test
```

---

## API

```python
from continuity_export import (
    build_export,
    write_json_export,
    write_md_export,
    validate_export,
    print_summary,
    scrub,
)

# Build export payload (does not write to disk)
payload, ts_str = build_export()

# Write both files
json_path = write_json_export(payload, ts_str)
md_path   = write_md_export(payload, ts_str)

# Validate an export on disk
report = validate_export("Memory/oracle_continuity_export_2026-06-07T12-00-00.json")
print(report["valid"])      # True
print(report["missing"])    # []

# Print live summary to stdout
print_summary()

# Scrub secrets from any dict/list/value before persisting
clean = scrub({"api_key": "sk-xxx", "name": "oracle"})
# -> {"api_key": "[REDACTED — secret field]", "name": "oracle"}
```

---

## Secret Scrubbing

The `scrub()` function is recursive and covers:

| Pattern | Example | Result |
|---|---|---|
| Field name is a secret | `{"password": "..."}` | `[REDACTED — secret field]` |
| OpenAI key pattern | `sk-abc123...` | `[REDACTED — secret pattern detected]` |
| Google API key pattern | `AIzaSy...` | `[REDACTED — secret pattern detected]` |
| GitHub PAT pattern | `ghp_...` | `[REDACTED — secret pattern detected]` |
| Long base64 string | 40+ char base64 | `[REDACTED — secret pattern detected]` |

Safe values pass through unchanged.

---

## Smoke Tests

43/43 — all passing.

Covers:
- Secret scrubbing: key pattern, field name, safe value, dict, nested dict, list
- Checksum: deterministic, different input → different hash, length 16
- Git log: returns list, non-empty, has hash and message fields
- Git head: non-empty string
- `build_export`: all 13 sections present, no raw API keys, safety flags set
- `validate_export`: valid on fresh export, catches bad path, catches corrupt JSON
- `print_summary`: no crash, correct output sections

---

## Persistence

Export files write to `Memory/` which is gitignored. They are local-only, portable by hand — copy to USB, email to self, paste into a new Claude session.

The export does not push to GitHub. The export does not call any API. It reads only local disk and `git log`.

---

## Integration Points

This module is standalone — it reads from the same files other modules write to:

| Source | File read |
|---|---|
| `project_state.py` | `Memory/project_states.json` |
| `session_state.py` | `Memory/session_state.json` |
| `video_intelligence.py` | `Memory/video_observation_candidates.json` |
| Governance docs | `docs/*.md` |
| Git | `git log` via subprocess |

It does not import other ORACLE modules at runtime — safe to call standalone.

---

*Last updated: 2026-06-07 | ORACLE.AI — Continuity Export Policy v0.1*
