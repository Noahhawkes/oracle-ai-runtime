# ORACLE Data Scope — Verified Answer to the Investigation Ticket

Answered by: Claude Code, 2026-07-16
Ticket origin: claude.ai session "Oracle data scope investigation" (Noah's
security thread, 2026-07-15/16)
Method: read the actual enforcement code and receipts, not the loop's
self-description.

## The ticket's crux, answered

> "Sandboxed for writes and sandboxed for reads are not the same thing —
> which one did Noah actually build?"

**Both claims are true, and they are different scopes — by design:**

### Writes: sandbox-only. Verified in code.

- The only autonomous write lane is `core/sandbox_files.py`. Every write
  resolves through `_resolve_sandbox_path()` which hard-walls to
  `C:\Oracle\ORACLE.AI-runtime\sandbox`. Escapes raise `SandboxWriteError`.
- Boundary flags on every receipt (`no_gdrive_edit`, `no_execution`,
  `no_computer_control`, `no_external_upload`, `inside_sandbox`) are
  enforcement results, not configuration hopes.
- Drive sync of sandbox content is the Google Drive desktop client mirroring
  the folder — ORACLE holds no Drive token and makes no Drive API calls.

### Reads: broad, governed, and receipted. Verified in code.

Noah's claim "she has full view of my files, threads and data" is **correct**
as of the 2026-07-13 file-recall build plus the readonly-access grant:

- `core/file_recall.py` — read roots: the full runtime (including sandbox),
  `C:\Users\noahh\Documents`, `Desktop`, `Downloads`, and `G:\My Drive`
  (filename-search only on Drive; no bulk content download).
- `core/readonly_access.py` — formal grant: `access_status: granted`,
  `approval_required_for_read: false`. Reading is free; mutation is gated.
  This is Noah's own doctrine ("conversation is free, mutation requires
  approval") applied to the filesystem.
- Her durable thread memory (`Memory/oracle_memory.db`, 5,800+ messages) and
  thread-recall facts give her the threads dimension.
- **Every read leaves a receipt**: `Memory/file_recall_receipts.jsonl` (and
  `Memory/internet_recall_receipts.jsonl` for web recall). The claude.ai
  session couldn't see these because they live outside the Drive-synced
  sandbox paths it inspected.

### Hard limits that hold in both directions

- Secret/credential paths blocked by directory and filename pattern
  (`.ssh`, `.aws`, `.git`, `obs_captures`, `id_rsa`, `*.pem`, `token`,
  `password`, `api_key`, `.env`, `oauth`, ...). The sensitive-inventory lane
  can list such paths' metadata but never reads their contents.
- No external send, no execution, no computer control, no canon promotion —
  all gated behind Noah.Physical approval regardless of read scope.

## On "self-thinking unprompted"

The claude.ai session's reading was accurate and is not in tension with
Noah's: every pulse has a `seed_prompt` because the loop is code-triggered on
a schedule Noah armed. Within each pulse, the content is the local model
reflecting over her real memory, threads, prior reflections, and the creation
feed. Scheduled trigger, grounded reflection. Candleholder, not flame.

## Security consequence (the part worth acting on)

Because reads are broad, the compromise-blast-radius of this machine includes
everything in the read roots. Mitigations already in place: read-only
enforcement, secret-path blocks, receipts for every access. Mitigations that
remain Noah's hand: Google security checkup, scoped OAuth audit, and making
the public `Oracle` GitHub repo private (issue #2 exposes DOB/MRN/report
numbers publicly — flagged 2026-07-15, still open).
