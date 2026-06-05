# ORACLE.AI

Personal desktop companion for Noah Hawkes. Context-aware, memory-persistent, locally controlled.

---

## Quick Start

### 1. Add your API key

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=your_key_here
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Launch

```powershell
cd "G:\My Drive\HawkesNest LLC\ORACLE.AI"
python core/oracle.py
```

---

## What it does on launch

- Loads `Noah.Identity.Anchor.json` as the identity foundation
- Indexes priority context documents from `Users/Noah.Self/`
- Connects to SQLite memory database (`Memory/oracle_memory.db`)
- Opens a chat session via Claude API
- Logs all inputs, outputs, and events to `Logs/YYYY-MM-DD.log`

---

## Chat commands

| Command | Action |
|---|---|
| `/memory` | Show current facts and recent message count |
| `/clear` | Clear conversation history (memory persists) |
| `/quit` | Exit and save session |

---

## Project structure

```
ORACLE.AI/
├── core/
│   ├── oracle.py           # Main entry point
│   ├── memory.py           # SQLite memory service
│   ├── context_loader.py   # Loads identity + context docs
│   └── audit_log.py        # Action logging
├── tools/                  # Future: launcher, search, scripts
├── interface/              # Future: tray app
├── Context/                # Contextual knowledge (Personal, Professional, Global)
├── Users/                  # Identity and personal documents (excluded from git)
├── Memory/                 # oracle_memory.db (excluded from git)
├── Logs/                   # Daily audit logs (excluded from git)
├── Scripts/                # MirrorGPT submodule
├── config.yaml             # Approved apps, scripts, model settings
├── requirements.txt        # Python dependencies
└── .env.example            # API key template
```

---

## Memory persistence

Sessions, messages, and facts are stored in `Memory/oracle_memory.db`.
The database survives restarts. Facts written in one session are available in all future sessions.

---

## Phase 1 roadmap

- [x] Core chat loop with Claude API
- [x] SQLite memory (sessions, messages, facts)
- [x] Identity anchor + context document loading
- [x] Audit logging with approval flags
- [ ] Action router + approval gate
- [ ] Local document search
- [ ] Windows tray interface
- [ ] Windows startup integration
- [ ] Voice input / output

---

## Security

- `.env` is never committed
- `Users/` is never committed (personal documents, legal files, identity data)
- `Memory/` is never committed (runtime database)
- No action executes without explicit approval (coming in Phase 1 Week 2)
