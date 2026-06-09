# ORACLE Thread Continuity Ingest

**Module:** `core/thread_continuity_ingest.py`
**Status:** v0.1 — production candidate
**Doctrine reference:** `docs/ORACLE_DOCTRINE.md`

---

## What this is

A governed ingest pipe that converts a raw conversation thread (ChatGPT export,
text blob, any multi-turn dialogue) into structured ORACLE continuity artifacts.

ORACLE does not absorb raw memory. She ingests governed candidate packs.

This module is the safe interface between "a thread happened" and "ORACLE knows about it."
Without it, dumping a thread into memory creates the Surveillance Garbage problem:
unverified beliefs masquerading as facts, private content stored without consent,
and entropy accumulating faster than signal.

---

## What it does

| Step | Behavior |
|------|----------|
| Accept input | Thread file path via `--input` |
| Hash source | SHA-256 of raw text — provenance, not surveillance |
| Redact secrets | API keys, tokens, emails, passwords, .env assignments stripped |
| Extract candidates | Tasks, risks, memory cands, doctrine cands, book cands, milestones |
| Mark all PENDING | Nothing is approved until Noah reviews |
| Preserve unknowns | UNKNOWN sentinel when nothing is detectable |
| Write outputs | Structured JSON to `Memory/thread_ingest/` |

## What it never does

- Store raw thread text
- Call any cloud API or LLM
- Move, delete, rename, upload, or sync files
- Auto-approve any candidate
- Invent progress not verifiable from the thread text

---

## CLI

```bash
# Parse only — report but write nothing
python core/thread_continuity_ingest.py --input path/to/thread.txt --dry-run

# Parse and write structured candidates
python core/thread_continuity_ingest.py --input path/to/thread.txt --write-candidates

# Show status of last ingest
python core/thread_continuity_ingest.py --status

# Run smoke tests
python core/thread_continuity_ingest.py --smoke-test
```

---

## Output files

All outputs land in `Memory/thread_ingest/`. None contains raw thread text.

| File | Contents |
|------|----------|
| `thread_summary.json` | Source hash, timestamps, extraction counts, raw-stored flag |
| `thread_candidates.json` | Memory candidates — all PENDING |
| `thread_engineering_tasks.json` | Build tasks, milestones, risks, status signals — all PENDING |
| `thread_book_candidates.json` | Manuscript / chapter candidates — all PENDING |
| `thread_governance_candidates.json` | Doctrine candidates — all PENDING |
| `thread_next_actions.md` | Prioritized next action list |

---

## Candidate schema

Every extracted item follows this shape:

```json
{
  "status": "PENDING",
  "category": "build_task",
  "text": "TODO: implement the memory pipeline",
  "approval_required": true
}
```

`status` is always `"PENDING"` on write. Approval is a separate human step.

---

## Extraction logic

Pattern-based heuristics — no LLM call, no network access.

| Category | Trigger patterns |
|----------|-----------------|
| Engineering tasks | TODO, TASK, BUILD, IMPLEMENT, FIX, WIRE, ADD, CREATE, SHIP, NEXT:, ACTION: |
| Risks | RISK, BLOCKER, UNRESOLVED, UNKNOWN, MISSING, BROKEN, FAIL, BUG, PROBLEM, GAP |
| Memory candidates | REMEMBER, STORE, SAVE TO MEMORY, MEMORY:, PREFERENCE:, STYLE:, PERSONA: |
| Doctrine candidates | DOCTRINE, PRINCIPLE, RULE:, SOVEREIGNTY, 51/49, ORACLE IS, ORACLE NEVER |
| Book candidates | CHAPTER, MANUSCRIPT, BOOK:, ESSAY:, DRAFT:, PUBLISH, NARRATIVE: |
| Milestones | COMPLETE, DONE, SHIPPED, VERIFIED, WORKING, MILESTONE, BUILT |
| Status signals | ORACLE STATUS, CURRENT STATE, BUILD STATE, WHAT IS BUILT, WHAT REMAINS |

These are intentionally over-sensitive. False positives are cheap; missed signal is expensive.
The human review step is where noise gets filtered.

---

## Redaction patterns

The following are scrubbed from the clean text before any extraction:

- `sk-...` OpenAI-style API keys
- `Bearer ...` auth headers
- `ghp_...` GitHub tokens
- `xoxb-...` Slack tokens
- Long base64/hex strings (40+ chars)
- Email addresses
- `password = ...` inline assignments
- `.env`-style `KEY=value` assignments

Raw text is never written. The hash is computed from the original before redaction
so provenance is preserved without storing the content.

---

## Smoke tests

```
python core/thread_continuity_ingest.py --smoke-test
```

12 tests covering:

1. Raw thread text not stored by default
2. Source hash is created
3. Secrets are redacted
4. Engineering tasks are extracted
5. Memory candidates are PENDING only
6. Doctrine candidates are PENDING only
7. Book candidates are PENDING only
8. Unknowns are preserved
9. Output files write to `Memory/thread_ingest/`
10. Dry-run does not write candidates
11. Write-candidates writes structured output only
12. No destructive or external action occurs

---

## Workflow

1. Export thread to a `.txt` file
2. Run `--dry-run` to see extraction counts without writing
3. Run `--write-candidates` to produce the candidate pack
4. Review `Memory/thread_ingest/thread_next_actions.md` for the action list
5. Approve or reject individual candidates manually
6. Commit the approved candidates; discard rejected ones

---

## Governance

This module is governed by the same rules as all ORACLE memory operations:

- `ORACLE_MEMORY_APPROVAL_REQUIRED = True` (default, always)
- Candidate approval is a human step — not automatic
- The 51/49 rule applies: Noah holds final say on every approved item
- Raw private content is never stored — only structured summaries

See `core/governance.py` and `docs/ORACLE_DOCTRINE.md`.
