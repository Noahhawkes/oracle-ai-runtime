# Executor Scope Gate v0.1

**Module:** `tools/executor.py` — scope gate wired into file-affecting tool handlers

---

## Purpose

Every file-affecting tool call from the LLM travels through `tools/executor.py`.
Before this build, the executor had no awareness of Drive Scope or Freedom to Ask —
it could read or write any path the LLM named.

The Executor Scope Gate closes that gap. It fires before any file handler executes
and enforces the same governance rules that protect the rest of the stack.

---

## Gate function

```python
_scope_gate(path: str, tool_name: str, approved_for_write: bool = False)
    -> tuple[bool, str]
```

Returns `(allowed, message)`. If blocked, `message` is a Freedom to Ask phrase
that includes the request_id, smallest scope, and will_not_do list so Noah knows
exactly what to approve.

**Fails open** — if `drive_scope` or `freedom_to_ask` are unavailable, the gate
returns `(True, "")` and the tool continues normally. This preserves existing
behaviour in degraded environments.

---

## Access policy

| Condition | Result |
|---|---|
| Destructive tool (`delete_file`, `move_file`, `rename_file`) | Always blocked — ask phrase |
| System path (`C:\Windows`, `C:\Program Files`, etc.) | Always blocked — ask phrase |
| Path not in `scoped_paths.json` | Blocked — ask phrase |
| Write to ORACLE home (`G:\My Drive\HawkesNest LLC\ORACLE.AI`) | Allowed — she writes her own Memory/ |
| Write to cloud-sync path (OneDrive, G:\My Drive) outside ORACLE home | Blocked — ask phrase |
| Write to in-scope non-cloud path without `approved_for_write=True` | Blocked — ask phrase |
| Read / discovery in approved scope | Allowed |

---

## Gated tools

| Tool | Mode | Gate fires |
|---|---|---|
| `read_file` | `READ_CONTENT` | Always |
| `write_file` | `WRITE_ACTIVE` | Always (passes `approved_for_write=True` — `_confirm()` handles approval) |
| `list_directory` | `READ_DISCOVERY` | Always |
| `source_map_ingest` | `READ_CONTENT` | Always |
| `filesystem_scan` | `READ_DISCOVERY` | When paths provided |

Non-file tools (`recall_facts`, `run_shell`, `open_app`, `browser_*`, `git_op`, etc.)
are not in `_FILE_GATED_TOOLS` and never call the gate.

---

## Write approval flow

For `write_file`, the gate is called with `approved_for_write=True`. This means:
- Out-of-scope paths → blocked with ask phrase (no `_confirm()` shown)
- Cloud-sync paths outside ORACLE home → blocked with ask phrase
- In-scope non-cloud paths → gate allows, `_confirm()` handles interactive approval

Future improvement: replace `_confirm()` with the structured Freedom to Ask approval
flow so the request_id can be approved via the approval center.

---

## Ask phrase format

When blocked, ORACLE returns:

```
I need access to `<path>` because <reason>. I only need <mode>. I will not: <list>.
Safeguards: No destructive actions, No external/cloud uploads. Approve? [request_id: <id>]
```

The request is written to `Memory/machine_profiles/access_requests.json` as PENDING.
Noah approves or denies via the approval center — ORACLE never self-approves.

---

## Smoke tests

```
python tools/executor.py --smoke-test   # 12/12
```

| # | Test |
|---|---|
| 1 | Approved read path allowed |
| 2 | Unknown path blocked with ask phrase |
| 3 | Proposed-only path (AppData, not in scoped_paths) blocked |
| 4 | System path blocked |
| 5 | Write without write approval blocked |
| 6 | Cloud-sync write blocked even with `approved_for_write=True` |
| 7 | Destructive action blocked inside approved scope |
| 8 | Non-file tool not in gated set |
| 9 | Blocked response includes request_id |
| 10 | Blocked response includes path (smallest scope) |
| 11 | Blocked response includes will_not_do constraint |
| 12 | No destructive or external actions — only PENDING requests in temp |

---

## First smoke test run (2026-06-09)

```
12/12 smoke tests passed.
```
