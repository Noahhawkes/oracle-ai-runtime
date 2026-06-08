# ORACLE Continuity Backup Scheduler v0.1

Runs safe local continuity exports on a schedule so ORACLE can preserve
herself without requiring Noah to remember manual backup commands.

## Non-negotiable rules

- **No cloud upload** unless `cloud_upload_allowed=True` is explicitly set and approved.
- **No raw email / journal / video / audio** export — ever.
- **Approval status, candidate state, revocation state** are preserved as-is.
- **Manifest + checksum** required for every real export.
- **SAFE_SLEEP blocks execution** — scheduler will not run during safe sleep mode.
- **Default schedule is disabled** — opt-in only.

## Default schedule

| Field | Default |
|---|---|
| `enabled` | `False` |
| `frequency` | `daily` |
| `export_mode` | `summary_and_governed_state_only` |
| `local_only` | `True` |
| `cloud_upload_allowed` | `False` |

## CLI

```bash
# Show current scheduler status and last/next run times
python core/continuity_scheduler.py --status

# Plan a backup without executing it — shows what WOULD happen
python core/continuity_scheduler.py --dry-run

# Run one backup export immediately
python core/continuity_scheduler.py --run-once

# Enable / disable automatic scheduling
python core/continuity_scheduler.py --enable
python core/continuity_scheduler.py --disable

# Smoke tests
python core/continuity_scheduler.py --smoke-test
```

## Data model

### ContinuitySchedule (`Memory/continuity_scheduler.json`)

| Field | Type | Description |
|---|---|---|
| `id` | str | Schedule identifier |
| `enabled` | bool | Whether auto-scheduling is active |
| `frequency` | str | hourly / daily / weekly / manual |
| `last_run_at` | ISO datetime | Last successful run |
| `next_run_at` | ISO datetime | Next scheduled run |
| `export_mode` | str | What to export |
| `safe_sleep_compatible` | bool | Always True — SAFE_SLEEP blocks execution |
| `local_only` | bool | True = never leaves local disk |
| `cloud_upload_allowed` | bool | Default False — requires explicit approval |
| `created_at` | ISO datetime | Schedule created |
| `updated_at` | ISO datetime | Last modified |

### ContinuityBackupRun (returned by `run_once()` / `dry_run()`)

| Field | Type | Description |
|---|---|---|
| `id` | str (UUID4) | Run identifier |
| `schedule_id` | str | Parent schedule id |
| `started_at` | ISO datetime | Run start time |
| `completed_at` | ISO datetime | Run end time |
| `status` | str | planned / running / completed / failed / blocked / dry_run |
| `export_path` | str or None | Path to export JSON file |
| `manifest_path` | str or None | Path to manifest JSON file |
| `checksum` | str or None | SHA-256 of export content |
| `blocked_reason` | str or None | Why execution was blocked |
| `safety_notes` | list[str] | What was scrubbed / allowed |

## Storage

| File | Purpose |
|---|---|
| `Memory/continuity_scheduler.json` | Schedule state |
| `Memory/continuity_scheduler_log.jsonl` | Event log |
| `Memory/continuity_exports/` | Export files + manifests |

## Blocked export types

`raw_email`, `raw_journal`, `raw_video`, `raw_audio`, `cloud_upload`, `unscanned_files`

These keys are scrubbed from the export payload before writing.

## Integration

Uses `core/continuity_export.py` → `build_export()` when available.
If `continuity_export` is not importable, `run_once()` fails cleanly with a blocked_reason.
