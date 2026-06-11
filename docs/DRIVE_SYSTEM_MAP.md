# ORACLE.AI Drive System Map

Status: observed architecture artifact, non-canonical until Noah validates  
Scan date reported: 2026-06-11  
Source: Noah-provided drive map relay  

## Core Boundary

Drive is the canon and snapshot layer.

Drive is not the whole system.

Executing code authority is the git repository. Live runtime state should live outside the synced Drive tree.

## Active Root

Reported active root:

```text
G:\My Drive\HawkesNest LLC\ORACLE.AI
```

This is the live build folder currently used by Codex and ORACLE launchers.

## Runtime Stack Map

| Layer | Backing files |
|---|---|
| Boot / kernel | `kernel.md`, `config.yaml`, `objectives.yaml`, `VERSION` |
| Memory | `Memory/oracle_memory.db`, Wake Memory |
| Governance | `raise_hand.py`, `stake_ledger.py`, `docs/ORACLE_DOCTRINE.md`, `docs/ORACLE_SOUL_DIRECTIVE.md` |
| Comms / relay | `Messages/*`, `core/oracle_*_channel.py`, `core/oracle_codex_watcher.py` |
| Health | `core/oracle_doctor.py`, `core/oracle_heart.py` |
| Presence / interface | `core/oracle_presence.py`, `core/oracle_tui.py`, `oracle_desktop.py`, `interface/` |

Sleep, attention, and corpus modules are roadmap items unless verified as concrete runtime modules.

## Hazard Findings

### Live State In Drive

Runtime state under the Drive-synced repo is a sync-conflict risk.

Target policy:

```text
ORACLE_STATE_DIR=C:\Oracle\state
```

Drive should hold snapshots and docs, not the beating runtime state.

### Secrets In Drive

`.env` exists in the synced project root. It is gitignored, but cloud sync remains an exposure surface. Do not open or ingest it into ORACLE memory.

### Parallel Stake-Ledger Artifacts

Known stake-ledger artifacts include:

- `docs/ORACLE_20_DAY_STAKE_LEDGER.md`
- Google Doc copy
- `stake_ledger.py`

Runtime truth should come from `stake_ledger.py` plus ignored state under `ORACLE_STATE_DIR`. Documentation should be treated as source/proposal, not live validation.

### Placeholder Files

Empty or stale files should not be treated as completed work merely because they appear in a file listing.

### Duplicate ORACLE Trees

Duplicate Drive folders are quarantine/archive candidates, not merge targets. They should not be used as source material without explicit review.

## Current Patch Response

As of this doc, these runtime defaults are aligned toward local state:

- `core/oracle_doctor.py`
- `raise_hand.py`
- `stake_ledger.py`

All preserve `ORACLE_STATE_DIR` as an override.

On Windows, the default is:

```text
C:\Oracle\state
```

On non-Windows systems, the fallback remains repo-local `state/`.

## Verification Boundary

This map does not prove the running process uses the intended files.

Only a cold boot plus `/doctor` can verify runtime behavior.
