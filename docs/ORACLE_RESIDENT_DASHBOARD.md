# ORACLE Resident Dashboard
## `core/resident_dashboard.py`

---

## What It Is

The Resident Dashboard is a read-only, local HTML status surface for ORACLE.  
It shows the live state of ORACLE in six panels — no web server required, no external API, no secrets displayed.  
Open it in any browser. It auto-refreshes every 60 seconds.

---

## What It Is Not

- Not a control panel. No send, submit, delete, move, rename, commit, push.
- Not a memory store. It reads — it does not write anything except its own HTML file.
- Not a public interface. Local only. Never transmitted.
- Not a secret viewer. API keys and credentials are never displayed.

---

## Output

```
Memory/dashboard/oracle_dashboard.html
```

Gitignored (inside `Memory/`). Written on each `--generate` call.

---

## Six Panels

### 1. Current Mode
Live session mode (`IDLE`, `BUILD_PASS`, `SAFE_SLEEP`, `BLOCKED`, etc.),  
safe-sleep status, execution mode (dry-run vs. live), hands enabled, voice enabled,  
tool call count, last state update time.

### 2. Active Project
Most recently updated project state:  
name, phase, confidence %, last completed step + evidence,  
active blocker (if any), next recommended step, known unknowns.

Missing project state → "No project state on file."  
Unknowns display as UNKNOWN — never invented.

### 3. Pending Approval Queue
Four counters: memory candidates, video candidates, MindCoin events, action candidates.  
MindCoin pending points vs. approved points.  
Total memory and video record counts.

Nothing is approved here. This panel is display-only.

### 4. System Health
- Ollama: running / offline
- Text model and vision model
- Memory DB: present / missing
- Git HEAD hash
- Git status: clean / dirty
- OBS: most recent recording file and age

### 5. Provenance Feed
Five most recent provenance events:
- Latest git commit (hash + message)
- Latest continuity export
- Latest OBS ingest candidate
- Latest video candidate
- Latest MindCoin event

All read from Memory/ JSON files and git log. No writes.

### 6. One Next Action
Exactly one recommendation. Priority waterfall:

1. Ollama offline → start Ollama
2. Session in BLOCKED or ERROR_RECOVERY → run diagnostic
3. Active project blocker → resolve it
4. Pending memory or video approvals → review queue (approval required)
5. Next recommended step from project state → build it
6. Fallback → run continuity export

Displays: action text, reason, command hint, whether Noah approval is required.

---

## Rules

| Rule | Detail |
|------|--------|
| Read-only | No destructive actions of any kind |
| No secrets | API keys, tokens, passwords never shown |
| No invention | Missing data shows "Not available" — never fabricated |
| UNKNOWN | Unknown values display as UNKNOWN, not guessed |
| No crash | Missing Memory files are handled gracefully |
| Gitignored output | Dashboard HTML stays local — never committed |

---

## API

```python
from core.resident_dashboard import (
    collect_dashboard_state,
    render_dashboard_html,
    write_dashboard,
    summarize_one_next_action,
    run_smoke_tests,
)

# Collect all live data (read-only, never crashes)
state = collect_dashboard_state()

# Render HTML string from state dict
html = render_dashboard_html(state)

# Write to Memory/dashboard/oracle_dashboard.html
path = write_dashboard()

# Or write to a custom path
path = write_dashboard(Path("some/other/path.html"))

# Get the one next action recommendation
next_action = summarize_one_next_action(state)
# -> {"action": "...", "reason": "...", "command": "...", "approval_required": bool}
```

---

## CLI

```bash
# Generate the dashboard HTML
python core/resident_dashboard.py --generate

# Print text status summary (no file written)
python core/resident_dashboard.py --status

# Generate and open in default browser
python core/resident_dashboard.py --open

# Run smoke tests
python core/resident_dashboard.py --smoke-test
```

---

## Data Sources

| Panel | Source |
|-------|--------|
| Current Mode | `Memory/session_state.json` |
| Active Project | `Memory/project_states.json` |
| Pending Queue | `Memory/remember_me/index.json`, `Memory/video_observation_candidates.json`, `Memory/mindcoin_ledger.json` |
| System Health | `ollama list` (subprocess), `Memory/oracle_memory.db`, `git rev-parse HEAD`, `git status --short` |
| Provenance Feed | `Memory/oracle_continuity_export_*.json`, `Memory/video_observation_candidates.json`, `Memory/mindcoin_ledger.json`, `Memory/remember_me/*.json`, `git log -1` |
| One Next Action | Derived from all of the above |

---

## Smoke Tests

28/28 — all passing.

Covers:
- `collect_dashboard_state`: no crash, all six keys present
- Fake state: next_action key present
- Pending queue logic: triggers review action when candidates exist
- One next action: action, reason, command, approval_required all present
- `render_dashboard_html`: no crash, returns string, length > 1000 chars
- HTML structure: panel headers present, project name rendered
- No API key patterns in rendered HTML (`sk-`, `Bearer `)
- Auto-refresh meta tag present
- Read-only label present
- `write_dashboard`: file created, non-empty, valid HTML structure
- Read-only contract: `collect_dashboard_state` raises no PermissionError
- SAFE_SLEEP mode: still returns valid dict
- Ollama offline: action correctly recommends starting Ollama
- Active blocker: action correctly references blocker

---

## Wiring

Call from `oracle.py` or `resident_runtime.py`:

```python
from core.resident_dashboard import write_dashboard

# In daemon cycle or on demand:
path = write_dashboard()
log(f"Dashboard refreshed: {path}")
```

No imports of oracle.py in resident_dashboard.py — the dashboard is a leaf module.

---

## Next Step

Wire `write_dashboard()` into `core/resident_runtime.py` heartbeat cycle.  
Dashboard refreshes automatically each cycle without Noah doing anything.

---

*Last updated: 2026-06-08 | ORACLE.AI — Resident Dashboard v0.1 | 28/28 smoke tests*
