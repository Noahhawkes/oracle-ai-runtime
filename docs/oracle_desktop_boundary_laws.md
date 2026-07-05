# ORACLE Desktop - Boundary Laws

Authority: Noah.Physical
Established: 2026-06-28 (TP_031)

These laws govern the ORACLE desktop experience and thread persistence. They are
referenced by `ORACLE.ps1` and enforced/tested where noted.

## Laws

- **REFRESH_MUST_NOT_DESTROY_THREAD**
  A browser/app refresh must reload the current thread, never blank it. Enforced
  by: server writes every turn to `Memory/oracle_memory.db` (`save_message`);
  `GET /api/history` falls back to the durable store on empty in-memory history;
  the UI `init()` calls `restoreHistory()` on load. Proven by
  `tests/test_thread_persistence.py`.

- **LOCAL_CHAT_STATE != DURABLE_MEMORY**
  In-browser chat state (the rendered messages, the in-memory `_history`) is a
  view, not the system of record. The durable record is the SQLite store. Losing
  the tab must not lose the thread.

- **DESKTOP_APP_EXPECTATION != BROWSER_TAB_EXPERIMENT**
  ORACLE is meant to be opened like an app (one icon, one home), not assembled by
  the operator from remembered localhost ports. `ORACLE.ps1` + the Desktop
  "ORACLE" shortcut provide the one face.

- **NOAH_SHOULD_NOT_HAVE_TO_REMEMBER_PORTS**
  The launcher detects 7777 / 7778 / 7781 / 11434, labels current vs stale, and
  routes to the canonical runtime (7781). The operator never hand-picks a port,
  and is never silently dropped onto the stale 7777 copy.

## Notes

- Canonical runtime port is 7781 (`core/runtime_config.py`). 7777 is legacy and
  has historically been a stale Google Drive mirror copy (see TP_017) - the
  launcher labels it `stale` and refuses to treat it as ORACLE.
- Starting/restarting the elevated web server remains Noah.Physical's action; the
  launcher reports the exact command rather than silently spawning duplicates.
