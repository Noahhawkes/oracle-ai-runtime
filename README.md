# ORACLE.AI

**Personal AI Operator for Noah Hawkes — Noah.AI Technologies**

ORACLE is not a chatbot. It is an autonomous operator: a persistent, memory-driven AI agent that runs on Noah's Windows machine, executes tools, manages projects, and takes action on revenue-generating tasks without being asked.

Built with Python + Anthropic Claude API. Fully local. Fully owned.

---

## What ORACLE Is

| Capability | Status |
|---|---|
| Persistent memory (SQLite) across all sessions | Live |
| Identity anchor — knows who Noah is, always | Live |
| Context loading — reads Noah profile docs on startup | Live |
| Agentic tool-use loop — Claude calls tools, feeds results back | Live |
| Audit logging — every action logged APPROVED/DENIED | Live |
| App launcher (Chrome, VSCode, Notepad, Explorer) | Live |
| File read/write with overwrite protection | Live |
| Shell execution — PowerShell/CMD via shell_agent | Live |
| Browser automation — navigate, extract, interact | Live |
| Filesystem mapper — indexes and searches Noah drive | Live |
| Build agent — Python to Windows .exe via PyInstaller | Live |
| Scheduler — autonomous background task loop | Live |
| Computer control — keyboard/mouse automation | Live |
| SOV1.AI operator brain — self-healing action layer | Live |
| ChatGPT to SOV1 memory bridge | Live |
| Tray interface module | Live |
| Autonomous daemon — runs every N minutes, self-directed | Live |
| Windows .exe build (PyInstaller, 20.6 MB, no Python needed) | Built |
| GitHub remote backup | PENDING |
| Voice input/output | Phase 3 |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Anthropic API key
- Windows 10/11

### 1. Clone the repo

```powershell
git clone https://github.com/YOUR_USERNAME/ORACLE.AI.git
cd ORACLE.AI
```

### 2. Set your API key

```powershell
copy .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Launch interactive chat

```powershell
python core/oracle.py
# or double-click oracle.bat
```

### 5. Launch autonomous daemon

```powershell
# Runs every 10 minutes, self-selects tasks from revenue priorities
python core/daemon.py
# or double-click oracle_tray.bat
```

---

## Architecture

```
ORACLE.AI/
├── core/
│   ├── oracle.py              # Main entry — chat loop + agentic tool-use
│   ├── daemon.py              # Autonomous background scheduler
│   ├── memory.py              # SQLite memory (sessions, messages, facts)
│   ├── context_loader.py      # Identity anchor + context doc loader
│   ├── audit_log.py           # Full action audit trail
│   ├── sov1.py                # SOV1.AI operator brain — self-healing actions
│   ├── bridge.py              # ChatGPT to SOV1 memory bridge
│   ├── tray.py                # Windows system tray interface
│   ├── computer_control.py    # Keyboard/mouse automation
│   ├── build_consulting_kit.py # Revenue asset generator
│   └── root.py                # Project root path resolver
│
├── tools/
│   ├── definitions.py         # 7+ Claude tool-use API definitions
│   ├── executor.py            # Tool dispatcher + allowlist enforcement
│   ├── shell_agent.py         # PowerShell/CMD execution
│   ├── browser_agent.py       # Browser automation (navigate, click, extract)
│   ├── filesystem_mapper.py   # Drive index + search
│   ├── scheduler.py           # Autonomous task scheduling
│   └── build_agent.py         # PyInstaller .exe builder
│
├── Memory/                    # oracle_memory.db — NOT committed to git
├── Logs/                      # Daily audit logs — NOT committed to git
├── Users/                     # Identity docs, personal files — NOT committed
├── Context/                   # Contextual knowledge base
├── Scripts/                   # MirrorGPT submodule
│
├── config.yaml                # Approved apps, scripts, model settings
├── requirements.txt           # Python dependencies
├── oracle.spec                # PyInstaller build spec
├── oracle.bat                 # Quick launch — interactive
├── oracle_tray.bat            # Quick launch — daemon + tray
├── SOV1.bat                   # SOV1.AI operator mode
└── BRIDGE.bat                 # ChatGPT bridge mode
```

---

## How the Agentic Loop Works

1. Noah types input OR daemon fires on schedule
2. Claude receives message + system prompt (identity, memory, context)
3. Claude calls tools: shell, browser, file, memory, app, build, etc.
4. ORACLE executes tool, result returned to Claude
5. Claude reasons on result, may call more tools
6. Loop continues until Claude issues end_turn text reply
7. Console prints [Oracle → Tool: tool_name] on each fire
8. All tool calls: audit-logged APPROVED/DENIED

---

## Security Model

- .env never committed — API key stays local
- Users/ never committed — personal docs, identity, legal files
- Memory/ never committed — runtime database
- dist/ never committed — compiled .exe
- open_app restricted to allowlist in config.yaml
- run_script restricted to allowlist in config.yaml
- write_file overwrite requires explicit confirmation
- All tool calls audit-logged with APPROVED/DENIED flag

---

## Chat Commands

| Command | Action |
|---|---|
| /memory | Show stored facts + recent message count |
| /clear | Clear conversation history (memory persists) |
| /quit | Exit and save session |

---

## Building the .exe

```powershell
pyinstaller oracle.spec --clean --noconfirm
# Output: dist/oracle.exe (~20.6 MB, self-contained, no Python required)
```

---

## Revenue Priorities ORACLE Operates Against

ORACLE knows Noah active revenue levers and self-selects the highest actionable task each autonomous cycle:

1. TOUCHFLAME — iOS app (Swift/SwiftUI, App Store submission, TestFlight)
2. The Fixer / SOP King — Consulting brand (Upwork, LinkedIn outreach, first client)
3. Rendered Reality — Book (Amazon KDP publishing, cover design, launch)
4. ORACLE.AI — This system (GitHub backup, Phase 3 tools, voice layer)

---

## What ORACLE Built Autonomously on 2026-06-05

In a single evening of background cycles:

- Full Upwork profile package — ready to paste and go live
- Amazon KDP publishing package for Rendered Reality
- LinkedIn cold outreach sequence — 5 personas, DMs, Boolean search strings
- Unified Morning Mission Brief — zero-decision 90-min execution cockpit
- This README — full system documentation, committed to main

All output files saved to C:\Users\noahh\OneDrive\Documents\

---

## Phase Roadmap

| Phase | Status | Scope |
|---|---|---|
| Phase 1 | Complete | Core chat, memory, identity, context, audit, tool-use API |
| Phase 2 | Complete | Shell, browser, filesystem, scheduler, build, SOV1, daemon, tray |
| Phase 3 | Planned | Voice I/O, mobile companion, TOUCHFLAME integration, GitHub auto-sync |
| Phase 4 | Planned | Multi-agent (Ashley.AI, MirrorGPT, Ender.AI), distributed memory |

---

## Push to GitHub (first time — 4 minutes)

```powershell
cd "G:\My Drive\HawkesNest LLC\ORACLE.AI"
git remote add origin https://github.com/YOUR_USERNAME/ORACLE.AI.git
git branch -M main
git push -u origin main
```

Create the repo at github.com first. Set it Private. Do not initialize with a README.

---

## About

ORACLE.AI is a Noah.AI Technologies project.
Built by Noah Hawkes. Operated for Noah Hawkes.

"Render the Dream. Preserve the Signal. Become the Architect of a Reality Worth Remembering."
