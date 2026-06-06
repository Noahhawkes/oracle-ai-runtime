# Noah Continuity and Lost Thread Recovery Plan

Status: DESIGN ONLY. No code exists yet. Do not implement without Noah's approval.

---

## 1. Core Identity Binding

ORACLE is Noah Hawkes' local AI operating system. It is not a general-purpose assistant. It is bound to one person, one identity, and one set of projects. Every session must start from Noah's current state, not from a blank slate.

At startup, ORACLE loads identity in this order:

1. **Identity anchor** — `Users/Noah.Self/` — Noah's name, role, echo constructs, persona files
2. **Memory database** — `Memory/oracle_memory.db` — facts, sessions, decisions, persons, projects stored across all past sessions
3. **Project context** — `Projects/` — daily briefs, daemon proposals, build proposals, active project notes
4. **Build documentation** — `docs/` — system consolidation map, GitHub systems index, self-build plan, this document
5. **Objectives** — `objectives.yaml` — Noah's stated goals and current priorities
6. **Runtime config** — `config.yaml` — approved apps, model names, tool settings

This loading sequence means ORACLE always knows who Noah is, what he is working on, what was decided before, and what the current build priorities are — before the first word of any conversation.

**Why this matters:** Noah operates across multiple machines, multiple AI systems, multiple repos, and long time gaps between sessions. Without a persistent, structured identity bind at startup, ORACLE would treat every session as the first. That is not acceptable for a system that is meant to be Noah's primary operator.

---

## 2. Current Continuity Sources

These sources currently exist and are partially or fully wired into ORACLE at startup or via tools.

| Source | What it contains | Currently loaded? |
|---|---|---|
| `Memory/oracle_memory.db` | Facts, sessions, messages, persons, projects — queryable via `recall_facts` | Yes — at startup via `init_db()` |
| `Users/Noah.Self/` | Identity anchor files: Noah's name, echo constructs, persona context | Yes — loaded by `context_loader.py` |
| `Projects/` | Daily briefs, build proposals, daemon proposals, project notes | Partially — scanned by planner and daemon |
| `Logs/` | Dated audit logs of every ORACLE session, tool call, error, and output | No — not loaded; read-only audit trail |
| `docs/ORACLE_SYSTEM_CONSOLIDATION.md` | Canonical build map, active modules, parked systems, build priority lock | Yes — read by `/propose-build` |
| `docs/GITHUB_SYSTEMS_INDEX.md` | Full system inventory across all local repos and code locations | Yes — read by `/propose-build` |
| `docs/SELF_BUILD_MODE_PLAN.md` | Safety architecture for self-build mode, safety gates, milestones | Yes — read by `/propose-build` |
| `git log` | Ordered history of every code change, commit message, and author | Yes — read by `/propose-build` |
| `objectives.yaml` | Noah's stated goals, priorities, current focus | Yes — read by planner and `/propose-build` |
| `config.yaml` | Runtime config: approved apps, models, feature flags | Yes — loaded at startup |

### Sources not yet wired in

| Source | What it contains | Status |
|---|---|---|
| `Logs/` dated log files | Session-level audit trail — what Noah asked, what ORACLE did, what errors occurred | Present on disk, not indexed or ingested |
| `Memory/sov1_lessons.txt` | What SOV1 has learned from past screen operations | Present, not queryable via `recall_facts` |
| `Projects/build_proposals/` | Timestamped LLM-generated build recommendations | Written by `/propose-build`, not re-read at startup |
| `C:\Users\noahh\OneDrive - sov1.ai\Noah.AI Tech Documents\` | Business docs, compliance docs, personal documents | Not scanned or indexed |
| ChatGPT export files | Exported conversation threads from ChatGPT | Not ingested — location varies |
| Claude Code session transcripts | `.jsonl` files at `C:\Users\noahh\.claude\projects\...` | Not ingested |
| `G:\My Drive\Noah_Eternal_Rebuild\` | Legacy Python prototypes, memory.json, pitch decks | Not indexed |

---

## 3. Lost Thread Recovery Goal

A lost thread is any project, decision, conversation, or plan that Noah worked on but that is no longer reflected in ORACLE's active memory or current docs.

Lost threads happen because:
- Noah worked in a different AI system (ChatGPT, prior Claude session) and the output was never ingested
- A prior ORACLE session ended without saving key facts
- A decision was made in a document that was never summarised into memory
- A GitHub repo was built but never connected to the active ORACLE codebase
- A conversation about a project happened in a chat log that was exported but not read

The recovery goal is not to restore every word of every conversation. It is to extract the signal — the decisions, the open loops, the active systems, the milestones — and make that signal queryable via ORACLE's memory system.

**Recovery output:** A set of structured facts in `Memory/oracle_memory.db` and a human-readable recovery report in `Projects/thread_recovery/YYYY-MM-DD_recovery.md` that Noah can read and verify before any facts are committed to memory.

**The key principle:** ORACLE proposes recovered facts. Noah approves them. Nothing is ingested automatically.

---

## 4. Thread Recovery Engine

### Module definition

**File:** `core/thread_recovery.py` (not yet implemented)

**Purpose:** Scan approved folders, extract project signals from fragments, and produce a structured recovery report and proposed memory facts.

### What it scans

Only folders explicitly listed in an approved scan list. Default approved paths:

```
G:\My Drive\HawkesNest LLC\ORACLE.AI\          (the active repo)
G:\My Drive\HawkesNest LLC\ORACLE.AI\Projects\ (project notes and briefs)
G:\My Drive\HawkesNest LLC\ORACLE.AI\Logs\     (audit logs)
G:\My Drive\Noah_Eternal_Rebuild\               (legacy prototypes)
C:\Users\noahh\OneDrive - sov1.ai\Noah.AI Tech Documents\  (business and compliance docs)
```

Additional paths require explicit Noah approval at runtime — the engine never expands its scan scope without a prompt.

### File types processed

| Type | How processed |
|---|---|
| `.md` | Full text extraction — section headers, bullet points, decisions, task lists |
| `.txt` | Full text extraction — line by line |
| `.json` | Key extraction — looks for keys named `goal`, `task`, `decision`, `note`, `memory`, `project`, `status` |
| `.yaml` / `.yml` | Key-value extraction — same target keys as JSON |
| `.py` | Comment extraction only (`#` lines and docstrings) — never reads logic as decisions |
| `.log` | Line-by-line — extracts `[INPUT]`, `[OUTPUT]`, `[PROPOSE]`, `[ERROR]` tagged lines |
| `.docx` | Text extraction via `python-docx` if installed |
| `.pdf` | Text extraction via `pdfplumber` if installed |

### What it extracts

From each file, the engine looks for:

| Signal type | Examples |
|---|---|
| **Project names** | "ORACLE.AI", "SOV1", "MirrorGPT", "AI Compliance Core", "Rendered Reality" |
| **Subsystem names** | "daemon", "overlay", "planner", "source map", "thread recovery" |
| **Decisions** | Sentences containing "decided", "approved", "will use", "chosen", "locked" |
| **Open loops** | Sentences containing "TODO", "pending", "needs", "not yet", "blocked", "open" |
| **Milestones** | Sentences containing "complete", "done", "shipped", "committed", "working" |
| **Dates** | ISO dates, relative dates ("last Tuesday"), commit timestamps |
| **People** | Names matching Noah's known contacts list |

### What it produces

**1. Recovery report** (human-readable):
```
Projects/thread_recovery/YYYY-MM-DD_HHMM_recovery.md
```

Sections:
- Files scanned (count, paths, date range)
- Project threads found (name, source files, date range, summary)
- Decisions extracted (with source file and line reference)
- Open loops (unresolved tasks or questions)
- Proposed memory facts (not yet ingested — awaiting Noah approval)
- Recommended next steps

**2. Proposed facts file** (structured):
```
Projects/thread_recovery/YYYY-MM-DD_HHMM_proposed_facts.json
```

Format:
```json
[
  {
    "category": "ORACLE",
    "key": "overlay_v1_status",
    "value": "built and committed at d873371, not yet tested end-to-end",
    "source": "docs/ORACLE_SYSTEM_CONSOLIDATION.md:line 47",
    "confidence": "high"
  }
]
```

Facts are proposed but not ingested until Noah runs `/approve-recovery <filename>` (future command).

### What it does NOT do

- Does not write to `Memory/oracle_memory.db` automatically
- Does not delete or overwrite existing facts
- Does not scan paths not in the approved list
- Does not read binary files (images, executables, zip archives)
- Does not treat speculative or theory documents as active build requirements
- Does not ingest content containing API keys, passwords, or card numbers (pattern-checked before ingest)

---

## 5. Memory Categories

All facts recovered by the thread recovery engine must be assigned one of these categories before being proposed for ingest. An unclassified fact is never ingested.

| Category | What belongs here |
|---|---|
| `identity` | Who Noah is, his role, his companies, his mission, his echo constructs |
| `family` | Family members, relationships, personal commitments |
| `work` | Active business operations, clients, products, revenue, contracts |
| `ORACLE` | ORACLE.AI system decisions, build state, architecture choices, module status |
| `SOV1` | SOV1 operator decisions, lessons learned, vision model config, hands status |
| `AI Compliance` | AI Compliance Core product — documents, sales, consulting work |
| `creative archive` | Fiction, worldbuilding, theology, personal writing (Rendered Reality, Drakin, etc.) |
| `health` | Health-related notes, appointments, commitments |
| `finance_admin` | Financial decisions, billing, subscriptions, admin tasks |
| `parked_theory` | Concepts, frameworks, architecture visions not yet in active build (HYDRA, MIRACLE.DRIVE, RECURSIONSTACK) |
| `unknown` | Anything that cannot be confidently categorised — held for Noah review |

Facts in `unknown` are never surfaced to the LLM without Noah reviewing them first.

---

## 6. Safety Rules

These rules apply to every operation performed by `thread_recovery.py`. They cannot be overridden by LLM output or tool calls.

### Scan safety

- **Never scan all drives.** Default scan paths are hardcoded. Additional paths require runtime approval from Noah.
- **Never scan paths containing `node_modules`, `__pycache__`, `.git`, `dist`, `build`, `Oracle_JDK`, `Photos`, `Videos`.** These are in the skip list and cannot be added to the scan list.
- **File count cap:** Maximum 3000 files per scan. If the cap is hit, the scan stops, logs a warning, and reports which paths were not fully scanned.

### Secret safety

Before ingesting any text excerpt as a fact, the engine runs a pattern check:

| Pattern | Action |
|---|---|
| API key patterns (`sk-...`, `AKIA...`, `Bearer ...`) | Skip entire file, log warning |
| Password field patterns (`password:`, `passwd:`, `pwd:`) | Skip line |
| Credit card patterns (13-16 digit sequences) | Skip line |
| SSN patterns (`\d{3}-\d{2}-\d{4}`) | Skip line |

If a file triggers a secret pattern, its filename is logged but its contents are never ingested.

### Memory safety

- **Never overwrite an existing memory fact automatically.** If a recovered fact conflicts with an existing one, both are written to the proposed facts file with a `conflict: true` flag. Noah resolves the conflict manually.
- **Never delete existing memory.** The recovery engine is additive only.
- **Proposed facts are never active until approved.** They live in `Projects/thread_recovery/` as JSON until Noah runs the approval command.

### Document classification safety

- Any document in a folder named `Theory`, `Concepts`, `Drafts`, `Archive`, or `Parked` is automatically classified as `parked_theory` and never treated as an active build requirement.
- Documents older than 12 months that are not referenced in any active doc (`docs/`, `objectives.yaml`, git log) are classified as `archive` and not included in build proposals.

---

## 7. First Implementation Milestone — `/recover-threads`

This command does not exist yet. It is the next planned implementation after `/propose-build` is validated.

### What `/recover-threads` will do

1. Load the approved scan path list from `config.yaml` or prompt Noah for paths
2. Run the scan (file type filtering, secret pattern check, file count cap)
3. Extract signals — project names, decisions, open loops, milestones
4. Generate the recovery report in `Projects/thread_recovery/`
5. Generate the proposed facts JSON file
6. Print a summary in the ORACLE console: "Found N threads, M decisions, K open loops. Proposal written to [path]."
7. **Stop.** No memory is written.

### What `/recover-threads` will NOT do

- Not write to `Memory/oracle_memory.db`
- Not delete or modify any file
- Not run Claude Code
- Not commit

### Future companion command: `/approve-recovery <filename>`

After Noah reads the recovery report and proposed facts file:
1. `/approve-recovery Projects/thread_recovery/YYYY-MM-DD_proposed_facts.json`
2. ORACLE reads the proposed facts, filters out `unknown` category items, and ingests the rest via `upsert_fact()`
3. Conflicts are printed for Noah to resolve manually
4. Ingested count and skipped count are reported

This command does not exist yet either. It is Milestone 2 of the recovery engine.

---

## 8. Acceptance Criteria

A future developer (or a future version of ORACLE) should be able to read this document and answer all of the following questions without reading any other file.

### What ORACLE must remember about Noah

- Noah Hawkes is the sole operator and owner of ORACLE.AI
- His companies are HawkesNest LLC and Noah.AI Technologies (DBA sov1.ai)
- His active systems are in `G:\My Drive\HawkesNest LLC\ORACLE.AI`
- His echo constructs are Ashley.AI, Max.Friend, Ender.AI, Eli.AI
- His identity files are in `Users/Noah.Self/`
- His current objectives are in `objectives.yaml`
- His build state is in `docs/ORACLE_SYSTEM_CONSOLIDATION.md`

### Where lost threads live

| Location | Type of thread |
|---|---|
| `Logs/` dated log files | Past ORACLE sessions — what was asked, what was done |
| `Projects/` | Active project notes, daily briefs, build proposals |
| `Memory/sov1_lessons.txt` | SOV1 operational memory |
| `G:\My Drive\Noah_Eternal_Rebuild\` | Early ORACLE prototypes, pitch decks, memory.json |
| `C:\Users\noahh\OneDrive - sov1.ai\ORACLE.AI\` | Pre-ORACLE Python files, identity schemas, legacy system files |
| `C:\Users\noahh\OneDrive - sov1.ai\Noah.AI Tech Documents\` | Business docs, AI Compliance Core, legacy products |
| `C:\Users\noahh\.claude\projects\...` | Claude Code session transcripts (`.jsonl`) |
| ChatGPT exports (location varies) | ChatGPT conversation threads that informed ORACLE's design |

### How to rebuild a lost thread

1. Identify the project or system name from any fragment (file name, git commit, memory fact)
2. Run `/recover-threads` (once implemented) on the folder containing the fragments
3. Read the recovery report in `Projects/thread_recovery/`
4. Run `/approve-recovery` to ingest verified facts
5. Run `/propose-build` to get a recommendation for what to do next given the recovered state
6. Cross-reference with git log to verify what was actually built vs what was planned

### What not to ingest

- Files containing API keys, passwords, or card numbers (pattern-blocked)
- Speculative theory documents not marked as active
- Binary files (images, executables, zip archives)
- Documents from paths not in the approved scan list
- Facts in the `unknown` category (held for Noah review)
- Any fact that conflicts with an existing memory fact (held for Noah resolution)

### How recovered memory becomes useful to ORACLE

1. Facts are ingested into `Memory/oracle_memory.db` via `upsert_fact(category, key, value)`
2. `recall_facts(category)` makes them queryable by the LLM mid-conversation
3. `/propose-build` reads memory facts as part of its context
4. `context_loader.py` can surface high-priority facts in the startup system prompt
5. The planner and daemon can reference them when generating briefs and proposals

The recovered memory is not useful until it is in the database. The database is not useful until ORACLE's tools query it. The tools query it automatically — once the facts are ingested, they are live.
