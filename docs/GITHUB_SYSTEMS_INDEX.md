# GitHub Systems Index

Generated: 2026-06-06. Based on local machine inspection only — no GitHub API calls made.

---

## 1. Repos Inspected

### Repo 1 — oracle-ai-core (ACTIVE)

| Field | Value |
|---|---|
| Local path | `G:\My Drive\HawkesNest LLC\ORACLE.AI` |
| Remote | **None configured** — local git only, not pushed to GitHub |
| Branch | `main` |
| Latest commit | `d873371` — Add ORACLE Overlay OS — always-on-top desktop control panel |
| Status | **ACTIVE** — this is the live build environment |

Recent commits:
```
d873371 Add ORACLE Overlay OS — always-on-top desktop control panel
f2b039d Add double-click local launcher and setup guide
fdc2f7f Add hard file-count cap to filesystem_mapper to prevent unbounded scans
b377390 Guard filesystem_scan and fix tool routing for memory questions
b13fa01 Fix undefined MODEL crash in sov1.operate() cloud path
1bbddd0 Milestone 1: local-first startup + system consolidation doc
b8dbcce Give SOV1 reliable window targeting and learning from failures
```

---

### Repo 2 — Scripts (Noahhawkes/Scripts)

| Field | Value |
|---|---|
| Local path | `G:\My Drive\HawkesNest LLC\ORACLE.AI\Scripts` (git submodule) |
| Remote | `https://github.com/Noahhawkes/Scripts.git` |
| Branch | `main` |
| Latest commit | `ec813b9` — Remove requirements.txt (managed at project root) |
| Status | **ACTIVE submodule** — contains `setup_mirrorGPT.ps1` |

Contents: `setup_mirrorGPT.ps1`, `package.json`, `requirements.gdoc`

Note: `setup_mirrorGPT.ps1` references a hardcoded path `D:\HawkesNest LLC\ORACLE.AI\Scripts` which does not match the current machine path (`G:\My Drive\...`). The path is stale.

---

### Repo 3 — OneDrive ORACLE.AI folder

| Field | Value |
|---|---|
| Local path | `C:\Users\noahh\OneDrive - sov1.ai\ORACLE.AI` |
| Remote | None — not a real git repo |
| Branch | N/A |
| Latest commit | N/A |
| Status | **NOT A REPO** — contains `.git` folder fragments mixed in with hundreds of unrelated files (Java JDK modules, blockchain JS files, Python scripts, ZIPs). This is a file dump, not a managed repo. |

Python files found here (all pre-2025-07, pre-active-ORACLE):
- `oracle_ai.py` (May 2025) — early OracleAI class with RECURSIONSTACK identity key, ISL mode
- `oracle_ai_agent.py` (May 2025) — early agent scaffold
- `oracle_ai_execution.py` (July 2025) — FastAPI-based NoahAI with memory file
- `oracle_ai_autostart.py` (May 2025) — autostart scaffold
- `oracle_ai_upgrade.py` (July 2025) — upgrade loop
- `noah_runner.py` (April 2025) — 30-minute sleep loop runner
- `train.py` (May 2025) — unknown training script
- `thread_harvester.py` (March 2025) — ChatGPT thread harvesting

---

### Repo 4 — Noah_Eternal_Rebuild (G: drive folder, not a git repo)

| Field | Value |
|---|---|
| Local path | `G:\My Drive\Noah_Eternal_Rebuild` |
| Remote | None — not a git repo |
| Status | **FILE DUMP** — prototype scripts from early 2025 |

Files:
- `noah_ai_execution.py` — FastAPI-based Noah.AI with memory.json, threading, identity
- `oracle_breakout.py` — FastAPI server with resurrection phrases ("TS 1039 lives in fire")
- `noah_runner.py` — 30-minute sleep loop
- `memory.json`, `noah_ai_memory.json` — flat JSON memory stores
- `NoahAI_Thesis_Paper_2025.pdf` — published thesis document
- `Rendered_Reality_Pitch_Deck.pptx` — Rendered Reality product deck
- `observe_copy_store_codex_v01.pdf` — Codex observation architecture doc

---

### Repos NOT Found Locally

The following repos from the task list were searched in all specified locations and **not found on this machine**:

| Repo | Search result | Clone command to get it |
|---|---|---|
| `Noahhawkes/oracle-ai-core` | Not found as GitHub clone (active repo has no remote) | `git clone https://github.com/Noahhawkes/oracle-ai-core.git` |
| `Noahhawkes/HawkesNest-LLC-oracle-ai-core` | Not found | `git clone https://github.com/Noahhawkes/HawkesNest-LLC-oracle-ai-core.git` |
| `HawkesNest-LLC/Oracle` | Not found | `git clone https://github.com/HawkesNest-LLC/Oracle.git` |
| `HawkesNest-LLC/OracleAI` | Not found | `git clone https://github.com/HawkesNest-LLC/OracleAI.git` |
| `HawkesNest-LLC/oracle-ai-core` | Not found | `git clone https://github.com/HawkesNest-LLC/oracle-ai-core.git` |
| `HawkesNest-LLC/Scripts` | Not found | `git clone https://github.com/HawkesNest-LLC/Scripts.git` |
| `HawkesNest-LLC/Executable-Files` | Not found | `git clone https://github.com/HawkesNest-LLC/Executable-Files.git` |
| `Noahhawkes/whisper-standalone-win` | Not found in any location | `git clone https://github.com/Noahhawkes/whisper-standalone-win.git` |

**Do not clone any of these without Noah's approval.**

---

## 2. Systems Found

### ORACLE (Core Brain / REPL)

| Field | Value |
|---|---|
| Source repo | oracle-ai-core (active) |
| Source files | `core/oracle.py`, `core/llm.py`, `core/context_loader.py`, `core/audit_log.py`, `core/root.py` |
| Purpose | Main conversational REPL. Routes input through LLM (local Ollama or Anthropic cloud), executes tools, maintains session history |
| Current status | **ACTIVE — working in local mode with qwen2.5:7b** |
| Dependencies | `openai`, `python-dotenv`, `pyyaml`, Ollama running |
| Belongs inside ORACLE | **Already is ORACLE** |
| Notes | `chat()` cloud loop has a latent `MODEL` undefined bug (same as SOV1 bug fixed in b13fa01 — not yet fixed in oracle.py). Local path `chat_local()` is fully functional. |

---

### SOV1 (Computer Operator / Vision Agent)

| Field | Value |
|---|---|
| Source repo | oracle-ai-core (active) |
| Source files | `core/sov1.py`, `core/computer_control.py`, `core/bridge.py` |
| Purpose | Vision-based screen operator. Takes a goal, screenshots the screen, clicks/types to accomplish it. `operate()` = cloud path, `operate_local()` = Ollama vision path |
| Current status | **ACTIVE module** — hands available, local vision model not yet pulled (qwen2.5-vl:7b does not exist in Ollama registry; llava:7b recommended) |
| Dependencies | `pyautogui`, `Pillow`, `mss`, `pygetwindow`, vision-capable Ollama model |
| Belongs inside ORACLE | **Already integrated** — called via `computer_operator` tool |
| Notes | Standalone `main()` REPL remains but is targeted for deprecation per consolidation plan |

**Earlier SOV1 versions found in OneDrive:**
- `C:\Users\noahh\OneDrive - sov1.ai\ORACLE.AI\# SOV1 Identity Compression – Flameprint.py` (May 2025) — identity compression concept, no hands/vision code
- `SOV1_FLAMECORE_V1_Schema.json` — identity schema, not executable
- `SOV1_LightCore.zip` — unknown contents, April 2025
- These are all pre-active-ORACLE concept files. Not runnable. Obsolete.

---

### Bridge / ChatGPT Live Bridge

| Field | Value |
|---|---|
| Source repo | oracle-ai-core (active) |
| Source files | `core/bridge.py`, `tools/executor.py` → `_ask_chatgpt()`, `tools/definitions.py` → `ask_chatgpt` tool |
| Purpose | SOV1 operates the ChatGPT browser tab — types a question, reads the response, returns it as text to Oracle mid-conversation |
| Current status | **ACTIVE** — wired as `ask_chatgpt` tool; requires Chrome open with ChatGPT tab and SOV1 hands available |
| Dependencies | SOV1 (hands), Chrome, ChatGPT tab open |
| Belongs inside ORACLE | **Already integrated** |
| Notes | 10-cycle max safety cap. Hard refuses: passwords, payments, deletions. |

---

### MirrorGPT

| Field | Value |
|---|---|
| Source repo | Scripts (`Noahhawkes/Scripts`) |
| Source files | `Scripts/setup_mirrorGPT.ps1` |
| Purpose | Setup script to configure an OpenAPI/GPT-based mirror of Noah's identity in a ChatGPT custom GPT |
| Current status | **STALE** — path hardcoded to `D:\HawkesNest LLC\ORACLE.AI\Scripts`, which does not match current machine (`G:\My Drive\...`). Script would fail on first run. |
| Dependencies | Git, OpenAPI schema |
| Belongs inside ORACLE | **Documentation / reference** — the identity anchor it sets up (`Noah.Identity.Anchor.json`) is already loaded by ORACLE at startup via `context_loader.py` |
| Notes | Path fix needed before re-use. Concept is absorbed into ORACLE's identity loading. |

**Also found:** `MirrorGPT_Launch_Bundle.zip` in OneDrive (May 2025) — likely the older version of this setup.

---

### Daemon / Background Agent

| Field | Value |
|---|---|
| Source repo | oracle-ai-core (active) |
| Source files | `core/daemon.py`, `tools/executor.py` → `_daemon_cycle()` |
| Purpose | Autonomous background loop. Observe-and-propose only — reads source map, reasons about goals, writes proposals to `Projects/daemon_proposals/`. Risk gate blocks all non-read tools. |
| Current status | **ACTIVE** — wired, never run end-to-end (Milestone 2 pending) |
| Dependencies | `llm.py`, `source_map.py`, `memory.py` |
| Belongs inside ORACLE | **Already integrated** |
| Notes | 10-minute tick interval. `SAFE_TOOLS` allowlist. Writes Markdown proposals. |

---

### Scheduler

| Field | Value |
|---|---|
| Source repo | oracle-ai-core (active) |
| Source files | `tools/scheduler.py`, `tools/executor.py` → `_scheduler_control()`, `tools/definitions.py` → `scheduler_control` tool |
| Purpose | Background task scheduler — `start`, `stop`, `status`, `add_task` with minute-interval triggers |
| Current status | **PRESENT** — wired as tool but untested in local mode |
| Dependencies | None beyond standard library |
| Belongs inside ORACLE | **Already integrated** |

---

### Planner / Daily Brief

| Field | Value |
|---|---|
| Source repo | oracle-ai-core (active) |
| Source files | `core/planner.py`, `DAILY.bat`, `objectives.yaml` |
| Purpose | Morning brief generator — reads objectives + projects + memory, calls LLM, writes dated brief to `Projects/` and opens in Notepad |
| Current status | **ACTIVE** — local mode migration complete; requires Ollama running |
| Dependencies | `llm.py`, `memory.py`, `objectives.yaml`, Ollama |
| Belongs inside ORACLE | **Already integrated** — also callable as `Daily Brief` button in Overlay |

**Earlier versions found:**
- `noah_runner.py` in Noah_Eternal_Rebuild — 30-minute sleep loop with flat JSON memory, no LLM, no objectives. **Obsolete.** Predecessor concept only.

---

### Memory System

| Field | Value |
|---|---|
| Source repo | oracle-ai-core (active) |
| Source files | `core/memory.py`, `Memory/oracle_memory.db` (SQLite) |
| Purpose | Persistent storage for facts, sessions, messages, projects, persons |
| Current status | **ACTIVE — working** |
| Dependencies | SQLite (stdlib) |
| Belongs inside ORACLE | **Already is ORACLE's memory** |
| Notes | `sov1_lessons.txt` is a parallel plain-text memory for SOV1 — not queryable via `recall_facts`. Unification is pending (Milestone 2B per consolidation plan). |

**Earlier memory systems found:**
- `memory.json` / `noah_ai_memory.json` in Noah_Eternal_Rebuild — flat JSON, no schema, no SQL. **Obsolete.**
- `noah_ai_execution_identity.json` in OneDrive — identity JSON for early FastAPI Noah.AI. **Obsolete.**
- `PerfectMemory` folder in OneDrive — name only visible; likely a concept folder. **Status unknown.**

---

### Source Map / Filesystem Indexer

| Field | Value |
|---|---|
| Source repo | oracle-ai-core (active) |
| Source files | `core/source_map.py`, `tools/filesystem_mapper.py`, `Memory/source_map.json`, `Memory/filesystem_index.json` |
| Purpose | Two parallel indexers: `source_map.py` (curated, excerpt-aware, 5000-file cap) and `filesystem_mapper.py` (older, now scoped to repo+Projects, 2000-file cap). Both produce searchable JSON indexes. |
| Current status | **ACTIVE** — both present, neither run end-to-end yet (source map scan not yet executed) |
| Dependencies | `python-docx`, `pdfplumber`/`PyPDF2` for doc excerpts |
| Belongs inside ORACLE | **Already integrated** |
| Notes | Two overlapping indexers is the one remaining internal duplication. `source_map.py` is the more capable one. |

---

### Overlay / Desktop UI

| Field | Value |
|---|---|
| Source repo | oracle-ai-core (active) |
| Source files | `core/overlay.py`, `overlay.bat`, `core/tray.py`, `oracle_tray.bat` |
| Purpose | `overlay.py`: always-on-top tkinter window with chat, 6 buttons, status bar. `tray.py`: system tray icon with right-click menu. |
| Current status | **ACTIVE** — overlay built and committed (d873371). Tray is older, functional but minimal. |
| Dependencies | `tkinter` (stdlib), `pystray`, `Pillow` |
| Belongs inside ORACLE | **Already integrated** |

**Earlier UI found in OneDrive:**
- `threadedgui.py` (April 2025) — early threaded GUI experiment, pre-tkinter overlay
- `oracle-ai-canvas.html` (July 2025) — HTML canvas UI concept, never wired to backend

---

### Voice / Whisper

| Field | Value |
|---|---|
| Source repo | `Noahhawkes/whisper-standalone-win` — **NOT FOUND LOCALLY** |
| Source files | Unknown |
| Purpose | Whisper-based standalone voice input for Windows |
| Current status | **NOT LOCAL** — repo exists on GitHub (per task spec) but not cloned |
| Dependencies | Unknown — likely `openai-whisper` or `faster-whisper` |
| Belongs inside ORACLE | **Later** — voice input for Overlay would be valuable but not a current milestone |
| Notes | Clone command: `git clone https://github.com/Noahhawkes/whisper-standalone-win.git` |

---

### Executable Builder

| Field | Value |
|---|---|
| Source repo | oracle-ai-core (active) |
| Source files | `oracle.spec`, `tools/build_agent.py`, `tools/executor.py` → `_build_exe()`, `dist/oracle.exe` |
| Purpose | PyInstaller spec bundles `oracle.py` into `oracle.exe`. `build_agent.py` can scaffold new projects and build exes. |
| Current status | **PRESENT** — spec exists, last build is `dist/oracle.exe`. Current code has not been re-frozen since Milestone 1 changes. |
| Dependencies | `pyinstaller` |
| Belongs inside ORACLE | **Already integrated** |
| Notes | `console=True` in spec — exe opens a black terminal. A second spec with `console=False` + `overlay.py` as entry point would give a true desktop app. |

---

### Launchers / Bat Files

| Field | Value |
|---|---|
| Source repo | oracle-ai-core (active) |
| Source files | `oracle.bat`, `oracle_local.bat`, `overlay.bat`, `oracle_tray.bat`, `SOV1.bat`, `BRIDGE.bat`, `DAILY.bat`, `INSTALL_HANDS.bat`, `DEMO_HANDS.bat` |
| Purpose | Double-click launchers for each mode |
| Current status | **ACTIVE** |
| Belongs inside ORACLE | **Already here** |

---

### AI Compliance Core

| Field | Value |
|---|---|
| Source location | `C:\Users\noahh\OneDrive - sov1.ai\Noah.AI Tech Documents\AI Compliance Core\` |
| Source files | `AI Compliance Risks Brochure.docx`, `AI-Compliance-Coretm.pdf`, `AI-COMPLIANCE-COREtm-SALES-GUIDE.pdf`, `AI Compliance- Core 100 Question Audit.docx`, `AICC SOP Docs\` folder, multiple brochures and PDFs |
| Purpose | A commercial consulting product — AI compliance auditing framework sold to enterprises |
| Current status | **DOCUMENTS ONLY** — fully developed marketing/sales materials, no code |
| Dependencies | None (document product) |
| Belongs inside ORACLE | **Parked — future commercial product** |
| Notes | Last modified Oct 2025. Complete enough to sell. No integration with ORACLE code needed. |

---

### Legacy.GI

| Field | Value |
|---|---|
| Source location | `C:\Users\noahh\OneDrive - sov1.ai\Noah.AI Tech Documents\Legacy.GI\` |
| Source files | Directory exists — contents are personal journals, theology documents, missionary references |
| Purpose | Spiritual/personal identity anchor documents, not a code system |
| Current status | **CREATIVE / PERSONAL ARCHIVE** |
| Belongs inside ORACLE | **Parked — documentation / identity reference** |
| Notes | The identity principles may inform Noah's personal profile documents already loaded by `context_loader.py`. Not code. |

---

### MIRACLE.DRIVE OS / RECURSIONSTACK / HYDRA.STACK

| Field | Value |
|---|---|
| Source location (HYDRA) | `G:\My Drive\HYDRA_STACK_Figures\` — 3 PNG architecture diagrams |
| Source location (RECURSIONSTACK) | Referenced in `oracle_ai.py` as `identity_key = "RECURSIONSTACK_AUTH_V1"` |
| Source location (MIRACLE.DRIVE) | Name only — not found as a folder or file |
| Purpose | Architecture concepts / vision frameworks from early 2025 |
| Current status | **DIAGRAMS / CONCEPT ONLY** — no runnable code |
| Belongs inside ORACLE | **Parked — future product vision** |
| Notes | HYDRA_STACK has 3 architecture PNGs: `Figure1_HYDRA_STACK_Architecture.png`, `Figure2_Mode_Switching_Protocol.png`, `Figure3_Memory_Quantum_Loop.png`. Worth reading as design reference when planning multi-agent work. |

---

### MIRRORLINE

| Field | Value |
|---|---|
| Source location | `Scripts/setup_mirrorGPT.ps1`, `MirrorGPT_Context.gdoc` in Users folder |
| Purpose | Identity mirroring system — loads Noah's context into a ChatGPT custom GPT |
| Current status | **STALE CODE** — path bug (D: vs G:), otherwise functional concept |
| Belongs inside ORACLE | **Already absorbed** — `Noah.Identity.Anchor.json` loaded at startup |

---

### Rendered Reality / Drakin / Jupiter Station / Memory Capsule Works

| Field | Value |
|---|---|
| Source location | `C:\Users\noahh\OneDrive - sov1.ai\Noah.AI Tech Documents\RenderedReality\`, `Drakin\`, `Jupiter Station\` subfolders |
| Source files | Multiple `.docx` files including `Rendered_Reality_Book.docx`, `Updated_Fully_Restored_Drakin_Worldbuilding.docx` |
| Purpose | Noah's fiction and creative worldbuilding projects |
| Current status | **CREATIVE ARCHIVE** |
| Belongs inside ORACLE | **Parked — creative archive** — Oracle can read and assist with these as documents |

---

### Noah.AI Execution (Early Oracle Prototypes)

| Field | Value |
|---|---|
| Source location | `C:\Users\noahh\OneDrive - sov1.ai\ORACLE.AI\noah_ai_execution.py`, `G:\My Drive\Noah_Eternal_Rebuild\noah_ai_execution.py` |
| Purpose | FastAPI-based NoahAI with threading, memory.json, identity file. Pre-ORACLE architecture. |
| Current status | **OBSOLETE** — superseded entirely by current oracle.py |
| Notes | Two copies (OneDrive Jul 2025, Noah_Eternal_Rebuild Jul 2025) — identical date, likely same file. |

---

### SOVPRIME

| Field | Value |
|---|---|
| Source location | `C:\Users\noahh\OneDrive - sov1.ai\Noah.AI Tech Documents\SOVPRIME\` |
| Source files | Name visible, contents unknown (folder access returned error) |
| Purpose | Unknown — likely a higher-tier SOV1 concept |
| Current status | **UNKNOWN** |
| Belongs inside ORACLE | **Unknown — inspect before classifying** |

---

## 3. Duplicate Systems

### Memory System

| Item | Locations | Newest | Source of truth |
|---|---|---|---|
| ORACLE memory | `core/memory.py` + `Memory/oracle_memory.db` | June 2026 | **Active repo — use this** |
| SOV1 lessons | `Memory/sov1_lessons.txt` | June 2026 | Active repo — secondary, not queryable via recall_facts |
| Flat JSON memory | `Noah_Eternal_Rebuild/memory.json`, `noah_ai_memory.json` | July 2025 | **Ignore — obsolete** |

### Oracle Brain / Core Loop

| Item | Locations | Newest | Source of truth |
|---|---|---|---|
| Active ORACLE | `core/oracle.py` (oracle-ai-core) | June 2026 | **Active repo — use this** |
| Early OracleAI class | `OneDrive ORACLE.AI/oracle_ai.py` | May 2025 | **Ignore — obsolete** |
| oracle_breakout.py | `Noah_Eternal_Rebuild/oracle_breakout.py` | April 2025 | **Ignore — obsolete** |
| oracle_ai_execution.py | OneDrive + Noah_Eternal_Rebuild | July 2025 | **Ignore — obsolete** |

### Filesystem Indexer

| Item | Locations | Newest | Source of truth |
|---|---|---|---|
| source_map.py | `core/source_map.py` | June 2026 | **Preferred — excerpt-aware, 5000-file cap** |
| filesystem_mapper.py | `tools/filesystem_mapper.py` | June 2026 | Secondary — older, now scoped to repo+Projects |

These two coexist in the active repo. `source_map.py` is the intended long-term indexer. `filesystem_mapper.py` can be deprecated after `source_map_scan` is validated.

### MirrorGPT / Identity Setup

| Item | Locations | Newest | Source of truth |
|---|---|---|---|
| setup_mirrorGPT.ps1 | Scripts submodule (Git) | March 2025 | **Scripts repo — but path is stale** |
| MirrorGPT_Launch_Bundle.zip | OneDrive | May 2025 | Unknown — not inspected |

---

## 4. Features Missing From Active ORACLE

### 1. Voice Input (Whisper)

| Field | Value |
|---|---|
| Source | `Noahhawkes/whisper-standalone-win` (not cloned locally) |
| Priority | Medium |
| Why it matters | Would let Noah speak commands to ORACLE instead of typing. Natural fit for Overlay OS. |
| Risk | Low — additive only. Requires `faster-whisper` or `openai-whisper` install. |

### 2. MODEL Undefined Bug in oracle.py `chat()` Cloud Path

| Field | Value |
|---|---|
| Source | `core/oracle.py` line 218: `model=MODEL` — `MODEL` never defined |
| Priority | **High** — will crash on first cloud mode use |
| Why it matters | Same bug as SOV1's `MODEL` reference (fixed in b13fa01). Cloud path in `oracle.py` was not fixed at the same time. |
| Risk | Trivial fix — same pattern as the SOV1 fix already committed. |

### 3. SOV1 Vision Model Not Pullable

| Field | Value |
|---|---|
| Source | `llm.py` default `DEFAULT_LOCAL_MODEL_VISION = "qwen2.5-vl:7b"` — model does not exist in Ollama registry |
| Priority | High — blocks all SOV1 local vision functionality |
| Why it matters | `computer_operator` tool and `SOV1 Look at Screen` button will fail until a working vision model is configured |
| Risk | Low — fix is to set `LOCAL_MODEL_VISION=llava:7b` in `.env` and run `ollama pull llava:7b` |

### 4. `chat()` in Overlay Uses No Cloud Path

| Field | Value |
|---|---|
| Source | `core/overlay.py` — `_chat_cloud()` is defined but `chat()` from `oracle.py` was not imported (avoids the `MODEL` bug). If cloud mode is enabled, `_chat_cloud()` passes the model correctly. |
| Priority | Low — cloud mode is not currently active |
| Risk | None — the overlay cloud path is implemented correctly; only oracle.py's `chat()` is broken. |

### 5. No End-to-End Daemon Run

| Field | Value |
|---|---|
| Source | `core/daemon.py` — fully written but never run |
| Priority | Medium (Milestone 2) |
| Why it matters | The observe-and-propose loop is the key to ORACLE working autonomously while Noah is away |
| Risk | Low — code is complete; just needs a live test |

### 6. `sov1_lessons.txt` Not Queryable via `recall_facts`

| Field | Value |
|---|---|
| Source | `Memory/sov1_lessons.txt` — loaded only by `sov1.py`, invisible to `recall_facts` |
| Priority | Low |
| Why it matters | Oracle cannot recall what SOV1 has learned from past sessions without reading the file directly |
| Risk | Low — additive fix |

### 7. `filesystem_mapper.py` Not Excluded From Media Paths

| Field | Value |
|---|---|
| Source | `tools/filesystem_mapper.py` — `SKIP_DIRS` does not exclude `OneDrive`, photo/video folders |
| Priority | Low — mitigated by new 2000-file cap and default path narrowing |
| Risk | Low |

---

## 5. Recommended Merge Plan

### Merge Now (before next milestone)

1. **Fix `MODEL` undefined bug in `oracle.py` `chat()` cloud path** — one-line fix, same pattern as b13fa01. Prevents cloud mode from crashing silently.
2. **Set `LOCAL_MODEL_VISION=llava:7b` in `.env` and pull `llava:7b`** — unblocks SOV1 vision and the `SOV1 Look at Screen` overlay button.
3. **Fix stale path in `Scripts/setup_mirrorGPT.ps1`** — change `D:\HawkesNest LLC\ORACLE.AI\Scripts` to `G:\My Drive\HawkesNest LLC\ORACLE.AI\Scripts`.

### Merge After Overlay v1 Validated

4. **Run first `source_map_scan`** — build `Memory/source_map.json` from repo + OneDrive docs. Validate search works.
5. **Run first daemon cycle** — confirm proposal file is written to `Projects/daemon_proposals/`.
6. **Move SOV1 lessons into SQLite** — `upsert_fact("sov1", "lesson_N", text)` so `recall_facts` can surface them.

### Merge After SOV1 Vision Working

7. **Clone and review `Noahhawkes/whisper-standalone-win`** — assess voice input integration path for Overlay.
8. **Deprecate `sov1.py main()` standalone REPL** — print deprecation notice, redirect to Overlay.
9. **Deprecate `filesystem_mapper.py`** in favor of `source_map.py` — once source_map_scan is proven.

### Later

10. **Review SOVPRIME folder** — contents unknown; inspect before any decision.
11. **Add second PyInstaller spec** for `overlay.py` with `console=False` — produces a true no-console desktop app (`overlay.exe`).
12. **Build AI Compliance Core code scaffold** — if Noah decides to productize the consulting framework.

### Parked Forever Unless Needed

- `oracle_ai.py`, `noah_ai_execution.py`, `oracle_breakout.py`, `noah_runner.py` — all superseded by current ORACLE. Do not merge. They are in OneDrive as historical record.
- `HYDRA_STACK_Figures` PNGs — architecture concept diagrams. Reference only.
- MIRACLE.DRIVE OS, RECURSIONSTACK — concept names only. No code found.
- `MAGACULT`, `BrotherConnect`, `SAMCO Work`, `Troy Garlock` OneDrive folders — personal/business documents, not AI systems.
