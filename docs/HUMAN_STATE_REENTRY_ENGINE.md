# Human State and Re-entry Engine

Purpose: preserve Noah.Physical's explicit life/work transitions and produce a concise re-entry brief when he returns.

This is not mood detection, surveillance, or psychological inference. It records only:

- explicit Noah statements
- verified local system events supplied by ORACLE runtime
- Noah.Physical correction events

## Modes

- `WORK_ECOWATER`
- `WORK_ORACLE`
- `WORK_WRITING`
- `FAMILY`
- `ERRAND`
- `TRAVEL`
- `RECREATION`
- `REST`
- `SLEEP`
- `UNKNOWN`

Ambiguous statements remain `UNKNOWN` and are not recorded as state changes.

## API

- `GET /api/human-state`
- `GET /api/reentry-brief`
- `POST /api/human-state/transition`

`POST /api/human-state/transition` is local-only and writes a SQLite transition receipt. It does not touch external systems.

## Chat Hooks

- `/reentry`
- `/reentry-brief`
- `Back at the workstation`

These return a read-only re-entry brief and do not trigger build work.

## Boundaries

- no camera, microphone, location, browser history, or ambient monitoring
- no inference from inactivity alone
- no external sends or system changes
- no memory/canon promotion
- no identity record modification
- no emotional-state claims

Receipts over vibes.
