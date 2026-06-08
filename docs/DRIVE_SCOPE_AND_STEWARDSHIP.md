# ORACLE Drive Scope & Workspace Stewardship

## Why this exists

ORACLE was treating `G:\My Drive` as the whole world. She cannot steward
Noah's PC without a governed map of what is on it and what she is allowed
to look at.

Drive Scope gives her the map. Workspace Steward gives her manners.

---

## Drive Scope (`core/drive_scope.py`)

Safe read-only discovery of all drives and approved candidate paths on
Noah's Windows machine.

### What it discovers

| Source | Examples |
|---|---|
| Drive letters | C:\\ D:\\ G:\\ H:\\ |
| User dirs | Desktop, Documents, Downloads, Pictures, Videos |
| Cloud sync | OneDrive, Google Drive (G:\\My Drive) |
| Dev roots | C:\\dev, C:\\repos, ~/dev, ~/repos |
| OBS recordings | ~/Videos/OBS if present |

### Safety rules (non-negotiable)

- **Read-only discovery only.** No file content read.
- **No recursive full-drive crawl** by default.
- **External/removable drives blocked** unless explicitly approved.
- **Blocked folder patterns** (never traversed):
  - System: `Windows`, `System32`, `ProgramData`, `$Recycle.Bin`
  - Browser/credentials: `Chrome`, `Firefox`, `Edge`, `1Password`, `LastPass`, `Bitwarden`
  - Sensitive: `tax`, `legal`, `medical`, `financial`, `insurance`, `hipaa`
  - OS credentials: `AppData\Local\Microsoft\Credentials`

### Output files

| File | Contents |
|---|---|
| `Memory/drive_scope.json` | Full discovery result including drives, candidate paths, safety config |
| `Memory/scoped_paths.json` | Flat list of approved paths for other modules to consume |

### CLI

```bash
python core/drive_scope.py --discover    # run discovery and print status
python core/drive_scope.py --status      # show last discovery
python core/drive_scope.py --smoke-test  # 20/20 tests
```

### API

```python
from drive_scope import discover, load_scope, approved_paths, is_in_scope

scope = discover()              # run and persist
paths = approved_paths()        # ["G:\\My Drive\\...", "C:\\Users\\..."]
is_in_scope("C:\\dev\\myapp")  # True/False
```

---

## Workspace Steward (`core/workspace_steward.py`)

Keeps Noah's PC orderly without reckless control. Uses Drive Scope for
path awareness and Window Janitor for window inspection.

### What it may do

- Detect messy windows, orphaned terminals, stale prompts
- Detect old daemon proposals and old continuity exports
- Detect pending approval backlogs
- Propose one safe next stewardship action
- Write a read-only report

### What it may NOT do

| Forbidden | Why |
|---|---|
| Close unknown windows | Too destructive without verification |
| Delete / move / rename files | Irreversible |
| Kill processes | Could lose unsaved work |
| Edit source | Requires approval |
| Act outside approved Drive Scope | Scope enforced |

### Output files

| File | Contents |
|---|---|
| `Memory/workspace_steward_report.json` | Full findings dict |
| `Memory/workspace_steward_report.md` | Human-readable summary |

### One Next Action

The steward always produces exactly one recommended next action.
Priority order:

1. Pending approvals → review them
2. Excess terminals (>4) → flag for manual close
3. Stale daemon proposals (>3 days) → archive
4. Old continuity exports (>7 days) → rotate
5. New scoped paths discovered → confirm scope
6. All clear → no action needed

### CLI

```bash
python core/workspace_steward.py --dry-run     # full inspection + report
python core/workspace_steward.py --status      # show last report summary
python core/workspace_steward.py --smoke-test  # 29/29 tests
```
