# ORACLE Operational Continuity Spine

Owner: `core.continuity_spine`

Purpose: compose existing ledgers into one operational view so Noah can return to work without reconstructing context.

The spine does not replace source ledgers. It reads:

- `core.human_state`
- `core.project_state`
- `approval_center`
- local receipt directories

It produces:

- current human state
- active project
- normalized open loops
- continuity timeline
- evidence density
- measurable health metrics
- operator dashboard
- daily continuity digest

## Open Loop Statuses

Every surfaced loop is normalized to one of:

- `completed`
- `active`
- `blocked`
- `waiting`
- `abandoned`

Each loop carries:

- timestamp
- originating session when known
- originating witness
- latest modification
- confidence
- owner
- evidence sources

## API

- `GET /api/continuity/spine`
- `GET /api/continuity/open-loops`
- `GET /api/continuity/timeline`
- `GET /api/continuity/health`
- `GET /api/continuity/operator-dashboard`
- `GET /api/continuity/daily-digest`

All endpoints are read-only. They do not send externally, mutate Drive, commit, push, promote canon, or trigger build work.

## Principle

Build the operating system for continuity, not another collection of features.
