# ORACLE.AI System Consolidation

## 1. Core Decision

ORACLE.AI is the main local desktop AI operating system.

SOV1 is a module inside ORACLE.AI, not a separate app.

Claude/Anthropic is optional turbo mode only.

Local Ollama/OpenAI-compatible models are the default runtime.

The system must be able to run without paid API calls.

---

## 2. Active Build System

### Module 1 — Memory Core

**Purpose:** Persist everything Oracle knows across sessions. Facts, project notes, people, conversation history, and ingested document summaries all land here. This is the long-term brain.

**Existing files:**
- `core/memory.py` — SQLite wrapper; tables: `sessions`, `messages`, `facts`, `projects`, `persons`
- `Memory/oracle_memory.db` — live database (SQLite file)
- `Memory/sov1_lessons.txt` — plain-text log of SOV1 computer-use outcomes

**Missing pieces:**
- No memory search by semantic similarity (keyword-only today)
- No automatic session summarization at end of conversation
- No expiry or ranking of stale facts

**Immediate next build task:** Add a `search_facts(query)` function to `memory.py` that does keyword matching across `category + key + value`, so Oracle can retrieve relevant facts without knowing the exact key.

---

### Module 2 — Knowledge Core

**Purpose:** Index Noah's files (code repo + OneDrive archive), make them searchable by Oracle, and ingest high-value documents as memory facts. Turns files on disk into context Oracle can actually use.

**Existing files:**
- `core/source_map.py` — scans configured folders, builds `Memory/source_map.json` (path, size, date, excerpt per file)
- `Memory/source_map.json` — the live file index (built on scan)
- `Memory/filesystem_index.json` — earlier filesystem scan index (predates source_map)
- `tools/filesystem_mapper.py` — filesystem walk utility used by executor
- `config.yaml` — lists `priority_docs` (Noah's identity/profile documents)
- `core/context_loader.py` — loads identity anchor and priority docs into system prompt at startup

**Missing pieces:**
- Source map scan has never been run end-to-end (Ollama not running during dev)
- No scheduled rescan — currently manual or daemon-triggered only
- `Memory/filesystem_index.json` and `source_map.json` overlap in purpose; one should feed the other

**Immediate next build task:** Run `source_map_scan` via Oracle REPL once Ollama is running and confirm the JSON index populates with entries from both the repo and the OneDrive archive.

---

### Module 3 — Reasoning Core

**Purpose:** The brain. Oracle receives user input, reasons about it, calls tools, and produces output. Supports two API formats: Anthropic (cloud) and OpenAI-compatible (Ollama local).

**Existing files:**
- `core/oracle.py` — main REPL entry point; `chat()` (Anthropic) and `chat_local()` (Ollama) loops
- `core/llm.py` — unified adapter: `make_client()`, `get_model()`, `is_local()`, `check_ollama()`, `startup_status()`, `to_openai_tools()`, `image_block()`
- `core/planner.py` — daily brief generator; reads objectives + projects + memory, calls LLM, writes brief to `Projects/`
- `core/context_loader.py` — builds system prompt from identity anchor + priority docs
- `core/audit_log.py` — writes timestamped log entries to `Logs/YYYY-MM-DD.log`
- `core/root.py` — resolves `ROOT` path for both source and frozen (PyInstaller) builds
- `config.yaml` — model selection, path config, approved apps/scripts
- `objectives.yaml` — Noah's standing objectives (revenue first); used by planner and daemon

**Missing pieces:**
- `chat()` (cloud loop) still references bare `MODEL` variable — should use `get_model()` consistently
- No conversation length management (context window will overflow on long sessions)
- Retry logic only in cloud path; local path has no reconnect on Ollama drop

**Immediate next build task:** Validate `python core/oracle.py` end-to-end with Ollama running and `qwen2.5:7b` pulled. Confirm the REPL accepts input and returns a response.

---

### Module 4 — Operator Core (SOV1)

**Purpose:** Oracle's hands. SOV1 takes a goal string, opens a vision loop, sees the screen via screenshots, and executes mouse/keyboard actions to accomplish the goal. Oracle calls SOV1 as a tool (`computer_operator`). SOV1 can also run standalone.

**Existing files:**
- `core/sov1.py` — vision + action loop; `operate()` (Anthropic cloud), `operate_local()` (Ollama); returns task_done summary string
- `core/computer_control.py` — raw input layer: `click`, `type_text`, `hotkey`, `scroll`, `screenshot`, `focus_window`, `find_window`; `HANDS_AVAILABLE` flag gates on pyautogui + pillow
- `core/bridge.py` — ChatGPT live bridge: SOV1 types a question into the ChatGPT tab, reads the response, returns it as text
- `Memory/sov1_lessons.txt` — records what SOV1 learned from past sessions (window targeting, failures)
- `tools/executor.py` → `_computer_operator()` — the tool handler that calls `sov1.operate()`
- `tools/definitions.py` → `computer_operator` tool schema
- `SOV1.bat` — standalone launcher for SOV1 (double-click to run)
- `BRIDGE.bat` — standalone launcher for the ChatGPT bridge
- `INSTALL_HANDS.bat` — installs pyautogui, pillow, mss, pygetwindow
- `DEMO_HANDS.bat` — runs a hands demo
- `Models/` — SOV1 screenshot captures (PNG files from live sessions)

**Missing pieces:**
- SOV1 vision model (`qwen2.5-vl:7b`) not yet pulled; local vision loop untested
- `operate_local()` path untested end-to-end
- No automatic lesson writing after task_done — `sov1_lessons.txt` is manual

**Immediate next build task:** Pull `ollama pull qwen2.5-vl:7b` and run a single SOV1 task via the Oracle REPL (`computer_operator` tool) to verify the vision loop works locally.

---

### Module 5 — Governance Core

**Purpose:** Ensures Oracle cannot take irreversible or dangerous actions autonomously. Implements the risk gate, proposal file pattern, and approval workflow. The daemon operates in observe-and-propose mode — it reads, reasons, and writes proposals, but does not execute unless the action is on the safe list.

**Existing files:**
- `core/daemon.py` — background operator loop; `SAFE_TOOLS` allowlist; `_preflight()`, `_gated_execute()`, `_write_proposal()`, `_daemon_prompt()`; writes proposals to `Projects/daemon_proposals/`
- `tools/executor.py` → `_daemon_cycle()` — lets Oracle trigger one daemon cycle from the REPL
- `tools/definitions.py` → `daemon_cycle` tool schema
- `config.yaml` → `approved_apps` and `approved_scripts` lists
- `objectives.yaml` — bounds what Oracle considers relevant work
- `.claude/settings.local.json` — Claude Code tool permissions

**Missing pieces:**
- `Projects/daemon_proposals/` directory not yet created (first daemon run will create it)
- No human approval UI — proposals are plain Markdown files that Noah reads and acts on manually
- No mechanism to mark a proposal as approved and have Oracle re-execute it

**Immediate next build task:** Run one daemon cycle (`python core/daemon.py` or via `/daemon_cycle` in REPL) and confirm a proposal file is written to `Projects/daemon_proposals/`.

---

## 3. Subsystems That Become Documentation, Not Separate Apps

### Legacy.GI

**What it is:** An earlier generative intelligence framework or concept that predates the ORACLE.AI architecture. Referenced in Noah's OneDrive documents as a prior system design.

**Where it belongs:** `documentation` — archive reference only. The reasoning patterns from Legacy.GI that are worth keeping have already been absorbed into the `core/context_loader.py` identity system and `objectives.yaml`. Do not build new code for this.

---

### AI Compliance Core

**What it is:** A framework concept for ensuring AI systems meet regulatory and ethical standards. Referenced in OneDrive archive under `AI Compliance Core/`. Has documentation but no active code in this repo.

**Where it belongs:** `governance reference` — future commercial product or white paper. The immediate compliance implementation is already handled by the Governance Core (daemon risk gate + approval workflow). Full AI Compliance Core is a future product, not a Milestone 1–4 build task.

---

### MIRACLE.DRIVE OS

**What it is:** A concept for a larger AI operating system layer, distinct from ORACLE.AI. Appears in Noah's documents as a broader vision.

**Where it belongs:** `future commercial product` — this is a product name and concept to preserve for later. ORACLE.AI is the immediate build target. MIRACLE.DRIVE OS may describe what ORACLE.AI eventually becomes at commercial scale. Do not build separate code.

---

### RECURSIONSTACK

**What it is:** A technical architecture concept — likely describing a self-improving or recursive AI reasoning stack.

**Where it belongs:** `documentation` — theoretical framework. The ideas inform how Oracle's reasoning loop should evolve (agentic tool use, self-correction), but no separate codebase is needed. Park as a design reference.

---

### HYDRA.STACK

**What it is:** A multi-agent or multi-instance architecture concept — multiple AI agents working in parallel on different tasks.

**Where it belongs:** `future commercial product` — multi-agent orchestration is not needed until ORACLE.AI's single-agent core is proven stable. Park this until Milestone 5+.

---

### MIRRORLINE

**What it is:** Appears in `Scripts/setup_mirrorGPT.ps1` and `Users/Noah.Self/MirrorGPT_Context.gdoc`. A framework for mirroring Noah's identity and context into a GPT-based assistant.

**Where it belongs:** `code module` — already partially wired. `Scripts/setup_mirrorGPT.ps1` is the setup script; it is in `approved_scripts` in `config.yaml`. The identity context it sets up (`Noah.Identity.Anchor.json`) is the same one ORACLE.AI loads at startup. No new code needed — it feeds the Knowledge Core.

---

### Rendered Reality

**What it is:** Noah's book project. Multiple `.docx` files in `Users/Noah.Self/Noah.Self Upload Repository/RenderedReality/` — "The Silverback Tales", worldbuilding documents, the full book draft.

**Where it belongs:** `creative archive` — not a code module. Files exist on disk and are indexed by the source map. Oracle can read them if asked. No build work needed.

---

### Drakin / Jupiter Station / Memory Capsule Works

**What it is:** Worldbuilding and creative projects — Drakin is a character/world in Rendered Reality. Jupiter Station and Memory Capsule Works appear to be related fiction or concept projects referenced in Noah's documents.

**Where it belongs:** `creative archive` — these live in `Users/Noah.Self/Noah.Self Upload Repository/RenderedReality/` and related docs. Oracle can read and assist with them as documents. No separate code modules.

---

## 4. Repository Reality

### Core files (`core/`)

| File | Role |
|------|------|
| `oracle.py` | Main REPL entry point — the single command to start ORACLE |
| `llm.py` | LLM adapter — Ollama (local) or Anthropic (cloud) |
| `memory.py` | SQLite memory layer — facts, sessions, projects, persons |
| `context_loader.py` | Builds system prompt from identity + priority docs |
| `source_map.py` | File indexer — scans folders, builds searchable JSON cache |
| `daemon.py` | Background operator — observe-and-propose loop with risk gate |
| `planner.py` | Daily brief generator — reads objectives + memory, writes brief |
| `sov1.py` | Vision + action loop — Oracle's hands (computer operator) |
| `computer_control.py` | Raw input layer — click, type, screenshot, window focus |
| `bridge.py` | ChatGPT live bridge — SOV1 types question, reads response |
| `tray.py` | System tray icon for background operation |
| `audit_log.py` | Timestamped log writer |
| `root.py` | ROOT path resolver (source vs frozen) |
| `build_consulting_kit.py` | Utility for building consulting output packages |

### Tools files (`tools/`)

| File | Role |
|------|------|
| `definitions.py` | All tool schemas (Anthropic format) — the API contract |
| `executor.py` | Tool dispatcher — routes tool calls to Python functions |
| `browser_agent.py` | Browser navigation and search (Playwright) |
| `shell_agent.py` | PowerShell command execution |
| `filesystem_mapper.py` | Filesystem walk and search utilities |
| `build_agent.py` | Build/compile task utilities |
| `scheduler.py` | Task scheduling utilities |

### Memory / log / context folders

| Folder | Contents |
|--------|----------|
| `Memory/` | `oracle_memory.db` (SQLite), `source_map.json`, `filesystem_index.json`, `sov1_lessons.txt` |
| `Logs/` | Daily audit logs (`YYYY-MM-DD.log`) |
| `Models/` | SOV1 screenshots from live sessions (PNG) |
| `Context/` | Global Trends, Personal, Professional context documents |
| `Projects/` | Active project folders (EcoWater, NoahAI, ORACLE.AI, Personal) + daily briefs |
| `Users/Noah.Self/` | Noah's identity anchor, profile docs, journals, legal, Rendered Reality archive |

### Entry points

| File | What it starts |
|------|---------------|
| `oracle.bat` | Runs `python core/oracle.py` — the main system |
| `oracle_tray.bat` | Starts tray icon version |
| `DAILY.bat` | Runs `python core/planner.py` — morning brief |
| `SOV1.bat` | Runs SOV1 standalone (without Oracle) |
| `BRIDGE.bat` | Runs ChatGPT bridge standalone |
| `INSTALL_HANDS.bat` | Installs SOV1 dependencies |
| `DEMO_HANDS.bat` | SOV1 demonstration run |
| `dist/oracle.exe` | PyInstaller-compiled executable (last frozen build) |

### Local / cloud model files

| File | Role |
|------|------|
| `core/llm.py` | Central adapter — all model routing goes through here |
| `config.yaml` | Cloud model selection (`claude-sonnet-4-6`) |
| `.env` | `LOCAL_MODE`, `LOCAL_MODEL`, `LOCAL_MODEL_VISION`, `OLLAMA_BASE`, `ANTHROPIC_API_KEY` (optional) |
| `requirements.txt` | `openai>=1.0.0` (core), `anthropic>=0.40.0` (optional, commented out) |

Local defaults (set in `llm.py`):
- Text model: `qwen2.5:7b`
- Vision model: `qwen2.5-vl:7b`
- Ollama base: `http://localhost:11434/v1`

### SOV1 / operator files

| File | Role |
|------|------|
| `core/sov1.py` | Vision loop + tool execution for screen control |
| `core/computer_control.py` | Low-level input: click, type, hotkey, scroll, screenshot |
| `core/bridge.py` | ChatGPT tab operator (live bridge) |
| `tools/definitions.py` → `computer_operator` | Tool schema for calling SOV1 from Oracle |
| `tools/executor.py` → `_computer_operator()` | Dispatch handler |
| `Memory/sov1_lessons.txt` | Persistent lesson log from past SOV1 sessions |
| `Models/` | Screenshot captures from SOV1 sessions |

---

## 5. Build Priority Lock

1. **Local startup with no API keys** — `python core/oracle.py` starts, banner shows, REPL is interactive. Ollama running with `qwen2.5:7b` pulled. *(In progress — code complete, needs live test)*
2. **Reliable memory save/recall** — facts survive session restarts; `search_facts()` returns relevant results; `/memory` command shows useful state.
3. **File and project indexing** — `source_map_scan` populates `Memory/source_map.json` from repo + OneDrive; Oracle can find and read docs by keyword.
4. **SOV1 operator under ORACLE** — `computer_operator` tool works end-to-end; SOV1 can complete a real goal (open app, click button, read screen).
5. **Approval gates for dangerous actions** — daemon proposal files written; risk gate tested; no tool outside `SAFE_TOOLS` executes without Noah's manual approval.
6. **Daily brief/planner local mode** — `python core/planner.py` runs, calls Ollama, writes brief to `Projects/`, opens Notepad.
7. **Desktop packaging** — `oracle.bat` is the reliable launch; optionally update PyInstaller spec to produce a clean `dist/oracle.exe`.
8. **Optional cloud escalation** — set `LOCAL_MODE=false` + `ANTHROPIC_API_KEY` in `.env` and Oracle switches to Claude with no code changes.

---

## 6. Do Not Build Yet

- New product names
- New theory frameworks
- Public website
- Payment system
- SaaS version
- Advanced autonomy (self-modifying code, unsupervised multi-step execution)
- Commercial compliance platform
- Voice interface
- Mobile app

---

## 7. Acceptance Criteria

This document is successful if a new developer can understand:

**What ORACLE is:** A local desktop AI operating system that runs on Noah's Windows PC. It has a conversation REPL, persistent memory, file indexing, and a daily planning loop. It runs free using Ollama local models by default. Claude is optional.

**What SOV1 is:** Oracle's hands. A computer-use module that takes a goal, looks at the screen via screenshots, and executes mouse and keyboard actions. It lives in `core/sov1.py` and is called by Oracle via the `computer_operator` tool. It is not a separate product.

**Which subsystems are active (build now):**
- Memory Core — `core/memory.py` + `Memory/oracle_memory.db`
- Knowledge Core — `core/source_map.py` + `Memory/source_map.json`
- Reasoning Core — `core/oracle.py` + `core/llm.py` + `core/planner.py`
- Operator Core — `core/sov1.py` + `core/computer_control.py`
- Governance Core — `core/daemon.py` + risk gate + proposal files

**Which subsystems are parked (not code priorities):**
- Legacy.GI — documentation/archive
- AI Compliance Core — future product
- MIRACLE.DRIVE OS — future product
- RECURSIONSTACK — design reference
- HYDRA.STACK — future product
- MIRRORLINE — already wired (feeds Knowledge Core)
- Rendered Reality — creative archive (files on disk, Oracle can read them)
- Drakin / Jupiter Station / Memory Capsule Works — creative archive

**What files already exist:** See Section 4.

**What to build next:** Run `ollama pull qwen2.5:7b` and `ollama pull qwen2.5-vl:7b`, then run `python core/oracle.py` to complete the Milestone 1 live test. Then proceed in the order defined in Section 5.
