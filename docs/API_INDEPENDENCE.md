# SOV1.AI — API Independence
## `core/llm.py` · `core/sov1.py`

---

## What It Means

SOV1.AI and ORACLE run entirely on local hardware — no cloud API call, no Anthropic key, no monthly bill, no remote dependency.

All reasoning runs on Ollama models installed on Noah's machine:
- **Text/reasoning**: `qwen2.5:7b`
- **Vision (screen reading)**: `qwen2.5-vl:7b`

---

## Default Behavior

`LOCAL_MODE` now defaults to `true`.

If `LOCAL_MODE` is not set in `.env`, SOV1 uses Ollama automatically.  
To use the cloud you must **explicitly** set `LOCAL_MODE=false`.

```
# .env — nothing needed for local mode
# LOCAL_MODE is true by default

# To opt into cloud (not recommended):
# LOCAL_MODE=false
# ANTHROPIC_API_KEY=sk-...
```

---

## Check Status

From the SOV1 terminal:
```
/api-status
```

From Python:
```python
from llm import is_api_independent, is_local, check_ollama

print(is_api_independent())   # True = no cloud API required
ok, msg = check_ollama()      # Ping Ollama health endpoint
```

---

## Enforce Independence

Call `require_local()` at any entry point that must never use the cloud:

```python
from llm import require_local

require_local("SOV1")   # Raises RuntimeError immediately if LOCAL_MODE=false
```

Use this in scripts, scheduled tasks, or daemon loops that must stay API-independent.

---

## New Tools (SOV1 v2)

Two new hands tools added that reduce SOV1's dependence on workarounds:

### `write_file`
Write text to any file on disk. No Notepad. No app. Direct.

```
Goal: "Save these notes to C:/Users/noahh/Desktop/notes.txt"
SOV1: write_file(path="C:/Users/noahh/Desktop/notes.txt", content="...")
```

Parameters:
- `path` — absolute or relative path (required)
- `content` — text to write (required)
- `append` — if true, append instead of overwrite (default false)

### `read_file`
Read a file's content without opening any app.

```
Goal: "What's in my notes.txt?"
SOV1: read_file(path="C:/Users/noahh/Desktop/notes.txt")
```

Parameters:
- `path` — path to read (required)
- `lines` — max lines to return (default: all, capped at 8000 chars)

Both tools are audit-logged via `audit_log`.

---

## Architecture: Two-Stage Local Loop

When `LOCAL_MODE=true`, SOV1 operates in a two-stage loop that splits vision from reasoning:

```
Stage 1 — Vision model (qwen2.5-vl:7b)
  Input:  screenshot
  Output: plain-text screen description
  No tools — vision model does not support tool calling

Stage 2 — Text model (qwen2.5:7b)
  Input:  screen description + goal + tools
  Output: tool call (next action)
  No images — text model never sees raw pixels
```

This split exists because:
- `qwen2.5-vl` handles vision but not tool calling
- `qwen2.5:7b` handles tool calling but not vision
- Together they match the capability of a single cloud vision+tool model

---

## What Doesn't Need the Cloud

All of these work fully locally:
- SOV1 desktop control (click, type, scroll, drag, focus, open)
- Screen observation and understanding
- File read/write
- Lesson memory
- Loop guard and safe-sleep protection
- Session state, project state, continuity export
- MindCoin ledger
- OBS log ingestion
- Video candidate creation (OpenCV frame analysis)
- Resident dashboard generation

---

## What Still Needs the Cloud (optional)

Nothing currently required. The cloud path exists as an opt-in for:
- Very long-context reasoning (qwen2.5:7b has limited context window)
- When local Ollama is not installed or GPU is unavailable

Set `LOCAL_MODE=false` + `ANTHROPIC_API_KEY` in `.env` to use Claude as the backend.

---

## Smoke Tests

23/23 — all passing (covers original 8 + 15 new).

New tests cover:
- `write_file`: creates file, verifies content, append mode, empty path error
- `read_file`: returns content, handles missing file gracefully
- `is_local()` defaults to `True` when `LOCAL_MODE` is unset
- `is_api_independent()` matches `is_local()`
- `require_local()` raises `RuntimeError` when `LOCAL_MODE=false`
- `require_local()` passes cleanly when local
- `_api_status_report()` returns a string with independence label

---

## Status

```
[f6f822e] Resident Dashboard v0.1   28/28
[9d785d7] MindCoin v0.1             51/51
[37dde78] OBS Ingest v0.1           26/26
[4213643] Continuity Export v0.1    43/43
[0e3b62b] Actuation Engine v0.1     39/39
```

SOV1 API Independence: active as of next commit.  
No API key required. No cloud call made when LOCAL_MODE is unset.

---

*Last updated: 2026-06-08 | ORACLE.AI — SOV1.AI API Independence v1*
