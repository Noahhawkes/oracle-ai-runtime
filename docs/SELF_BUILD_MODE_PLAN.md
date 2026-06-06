# ORACLE Self-Build Mode — Design Plan

Status: PROPOSAL ONLY. No code exists yet. Do not implement without Noah's approval.

---

## 1. Build Guidance Files

When ORACLE inspects itself to generate a build proposal, it reads these sources in order:

### Primary directives
| File | Purpose |
|---|---|
| `docs/ORACLE_SYSTEM_CONSOLIDATION.md` | Canonical build map — active modules, parked subsystems, build priority lock |
| `docs/GITHUB_SYSTEMS_INDEX.md` | Full system inventory — what exists, what is duplicate, what is missing |
| `objectives.yaml` | Noah's stated goals and priorities |
| `config.yaml` | Runtime configuration — approved apps, model names, feature flags |

### Repository state
| Source | Purpose |
|---|---|
| `git log --oneline -20` | Recent build history — what was just changed, what direction the repo is moving |
| `git status` | Uncommitted work in progress |
| `git diff HEAD~3 HEAD --stat` | What files have changed most recently |
| All source files in `core/` and `tools/` | What is currently implemented |

### Memory and context
| Source | Purpose |
|---|---|
| `Memory/oracle_memory.db` | Facts Noah has stored — preferences, decisions, past errors |
| `Memory/sov1_lessons.txt` | What SOV1 has learned from past screen operations |
| `Projects/Daily_Brief_*.txt` | Recent daily briefs — Noah's current focus |
| `Projects/daemon_proposals/` | Past daemon proposals — what has already been suggested |

### Personal and identity context
| Source | Purpose |
|---|---|
| `Users/Noah.Self/` | Noah's identity files loaded at startup — informs tone and priorities |
| `docs/` folder | All design documents — informs what has been planned vs built |

---

## 2. What Proposal-Only Mode Means

Proposal-only mode means ORACLE reads, thinks, and writes a recommendation — nothing more.

It is the equivalent of a senior engineer reviewing a codebase and handing you a one-page memo that says "here is what I would do next, and why." The memo does not touch the codebase. It does not schedule itself to run again. It does not invoke any tool that modifies state.

The output of proposal-only mode is always a Markdown document written to `Projects/build_proposals/`. Noah reads it. Noah decides. Nothing happens without Noah.

This is the permanent ceiling of autonomous ORACLE behavior until all safety gates in Section 5 are in place and Noah explicitly unlocks the next level.

---

## 3. Allowed Actions (Proposal-Only Mode)

These actions are safe and permitted in proposal-only mode:

| Action | Tool / Method |
|---|---|
| Read any file in the repo | `read_file` tool |
| Read git log and status | `run_shell` → `git log`, `git status`, `git diff` |
| Search the source map index | `source_map_search` tool |
| Query memory facts | `recall_facts` tool |
| List directory contents | `list_directory` tool |
| Summarize systems and modules | LLM reasoning over read content |
| Propose the next build task | Write a proposal to `Projects/build_proposals/YYYY-MM-DD_HHMM.md` |
| Create a build plan document | Write a structured plan with rationale and file targets |
| Report what is missing or broken | Read-derived analysis only |

---

## 4. Forbidden Actions (Proposal-Only Mode)

These actions are permanently blocked until safety gates are in place:

| Forbidden Action | Reason |
|---|---|
| Edit any source file | No self-modification without branch + review |
| `git commit` | No automatic commits — Noah must commit |
| `git push` | No automatic pushes under any circumstance |
| Delete any file | Irreversible without rollback |
| Run `compileall` on modified files | Only useful after edits — edits are forbidden |
| Invoke Claude Code CLI | Claude Code makes file changes — requires approval gate |
| Start an autonomous loop | No scheduled self-triggering |
| Call `scheduler_control start` | Would create unsupervised recurring execution |
| Call `daemon_cycle` without Noah present | Daemon is for observe-and-propose; not for acting |
| Install packages | Changes system state outside the repo |

---

## 5. Required Safety Gates Before True Self-Build

The following infrastructure must exist and be tested before ORACLE is permitted to edit its own code autonomously. Each gate is a hard prerequisite for the next.

### Gate 1 — Branch per task
Every build task runs on its own git branch. ORACLE never commits directly to `main`.

```
Before any edit:  git checkout -b auto/task-name-YYYYMMDD
After edit:       git diff main...HEAD  (shown to Noah for review)
```

### Gate 2 — Test command required
Every proposal must include a test command that must pass before commit is allowed. If no test command exists, the proposal is incomplete and cannot proceed.

```
test_command: python -m compileall core tools -q
              python -m pytest tests/ -q   (once tests exist)
```

### Gate 3 — Diff review
Before any commit, a full `git diff` is written to the proposal document and displayed to Noah. No commit occurs until Noah has seen the diff.

### Gate 4 — Rollback command
Every proposal must include the exact rollback command. It must be verified runnable before the edit begins.

```
rollback: git checkout main && git branch -D auto/task-name-YYYYMMDD
```

### Gate 5 — Human approval before commit
Noah types an explicit approval command. No implicit approval. The approval is logged with timestamp.

```
/approve-commit <proposal-id>
```

### Gate 6 — No push without approval
Push to GitHub is a separate explicit command. Approval of commit does not imply approval of push. These are always two separate decisions.

```
/approve-push <proposal-id>
```

---

## 6. First Safe Implementation Milestone — `/propose-build`

### What it is
A single ORACLE command that reads the repo state and returns one recommended next build task. It does not modify anything.

### Trigger
```
/propose-build
```
or natural language: *"What should we build next?"*

### Execution sequence

1. Read `docs/ORACLE_SYSTEM_CONSOLIDATION.md`
2. Read `docs/GITHUB_SYSTEMS_INDEX.md`
3. Read `objectives.yaml`
4. Run `git log --oneline -10` → read output
5. Run `git status` → read output
6. Run `source_map_search` on recently modified files
7. Query `recall_facts` for any Noah preferences or decisions
8. LLM reasoning: given everything above, what is the single highest-value next task?
9. Write proposal to `Projects/build_proposals/YYYY-MM-DD_HHMM.md`
10. Return the proposal text to Noah in the ORACLE chat window

### Proposal document format
```markdown
# Build Proposal — YYYY-MM-DD HH:MM

## Recommended task
[one sentence]

## Rationale
[2-3 sentences: why this task, what problem it solves, what it unblocks]

## Files to change
- core/foo.py — [what change and why]
- tools/bar.py — [what change and why]

## Files to read first
- [list of files the implementer should read before starting]

## Test command
python -m compileall core tools -q

## Rollback command
git checkout main && git branch -D auto/[branch-name]

## Approximate complexity
[small / medium / large]

## Dependencies
[what must be true before this task can start]

## Noah must approve before any code is written.
```

### What it does NOT do
- Does not open any file for editing
- Does not call Claude Code
- Does not commit
- Does not push
- Does not schedule itself to run again

---

## 7. Future Milestone — `/approve-build`

This milestone is explicitly NOT scheduled. It requires all six safety gates from Section 5 to be in place and tested first.

### What it would do

1. Noah runs `/propose-build` → reads the proposal
2. Noah types `/approve-build <proposal-id>`
3. ORACLE constructs a Claude Code prompt from the proposal document — file targets, rationale, test command, rollback command
4. ORACLE displays the full Claude Code prompt to Noah before invoking anything
5. Noah explicitly confirms: *"Run this"*
6. Claude Code CLI is invoked with the prompt in non-interactive mode
7. Output is captured and written to the proposal log
8. `compileall` and test command run automatically
9. If both pass: diff is shown to Noah
10. Noah types `/approve-commit <proposal-id>` to commit to the branch
11. Noah separately types `/approve-push <proposal-id>` to push

At no point does ORACLE commit or push without an explicit typed approval. The human is in the loop at every irreversible step.

---

## 8. What Is Not Planned (Permanently Parked)

| Feature | Why parked |
|---|---|
| Fully autonomous commit loop | No safety gates exist yet; too high risk of breaking working code |
| ORACLE editing its own `core/oracle.py` | Highest-risk file — self-modification of the entry point is last, not first |
| Automatic dependency installation | System state changes outside the repo scope |
| Automatic branch merges to main | Merge decisions require Noah |
| Cross-repo self-modification | ORACLE only modifies its own repo |
| Invocation of other AI systems without approval | ChatGPT/Claude Code are tools Noah directs, not autonomous collaborators |

---

## Implementation Order (When Noah Approves)

1. **`/propose-build` command** — read-only, no code changes, writes proposal document
2. **Safety gate infrastructure** — branch creation helper, test runner, diff display
3. **`/approve-build` prompt generator** — constructs Claude Code prompt, waits for Noah confirmation
4. **Claude Code invocation** — non-interactive CLI call, output captured
5. **Commit gate** — diff shown, Noah types explicit approval
6. **Push gate** — separate explicit approval

Each step is a separate milestone. None is started until the previous is confirmed working by Noah.
