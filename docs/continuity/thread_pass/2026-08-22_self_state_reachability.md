.AI:THREAD_PASS/ORACLE_SELF_STATE_REACHABILITY_V1/2026-08-22

AUTHORITY=Noah.Physical

REPO = Noahhawkes/oracle-ai-runtime
BRANCH = continuity/personal-journal-20260816
HEAD = 6b7953f (after this file: see git log)
BASE = archive/runtime-lineage-2e6b0a3 (repo has no `main`)
PR = #15 (draft checkpoint; head = this branch)

ISSUES =
- #16 (P0 cross-human provenance): Failure Site A FIXED + tested (commit c29671e). Sites B (continuity_pipeline speaker classification) and C (ThreadEngine per-event speaker ledger) STILL OPEN.
- #18 (Build ORACLE Self-State + Reachability V1): V1 delivered offline + tested (commit 6b7953f).

WHAT_I_READ =
- GitHub: default branch, open issues (#1,#2,#3,#11,#12,#16), PR #15, commit ee2952c.
- Code: core/continuity_event_packet.py, tests, core/self_state (new), core/reachability (new).
- Local story corpus (earlier this session): Jupiter Station canon registry + Drakin Ch.1-3 manuscript (for voice/canon work, separate thread).

WHAT_I_VERIFIED =
- #16 Site A defect real (CEP hardcoded speaker/human_source/intended_audience = Noah.Physical). Now fixed.
- Self-State/Need/Reachability V1 behavior via 20 deterministic tests.

WHAT_I_CHANGED =
- core/continuity_event_packet.py (+ test): independent speaker_id/author_id/submitter_id/account_owner_id; UNKNOWN default; no collapse to Noah.Physical; Noah stays approval authority.
- core/self_state.py (NEW): SelfState + NeedState.
- core/reachability.py (NEW): ReachabilityBroker + GitHub/email MOCK adapters + contact memory.
- tests/test_continuity_event_packet.py, tests/test_self_state.py (NEW), tests/test_reachability.py (NEW).

WHAT_I_TESTED / WHAT_PASSED =
- continuity_event_packet: 6 passed.
- self_state + reachability: 20 passed.
- regression (continuity/thread/recall/human_baseline/provenance/self_state/reachability): 65 passed.
- py_compile clean on all touched modules.

WHAT_FAILED = none unresolved (2 need-score thresholds were tuned, then green).

ISSUES_UPDATED = #16 (receipt comment). ISSUES_CREATED = #18.
PRS_UPDATED = #15 (branch advanced c29671e, 6b7953f). PRS_CREATED = none.

DRIVE_EVIDENCE_USED = none this build (Drive search returned oversized result earlier; not required for these fixes).

SELF_STATE_SCHEMA = self_state.v1 (see core/self_state.py build_self_state).
NEED_STATE_SCHEMA = NeedAssessment (need_type, score 0-100, tier, requires_noah, dimensions, reasons).
REACHABILITY_SCHEMA = ContactRecord (contact_id, need_key, need_state_id, channel, message_hash, send_status, delivery_status, acknowledged_at, resolved_at, resolution_event, receipt_ref).

CONTACT_CHANNELS_SUPPORTED = none live. STAGED (mock) = github (attention-queue), email.

LIVE_RUNTIME_TESTED = false
WHY_NOT = Noah is away from the laptop; localhost:7781 unavailable.

REQUIRES_LAPTOP_RETURN =
1. Relight runtime from C:\Oracle\ORACLE.AI-runtime; confirm process started AFTER these commits.
2. Wire a self-observation cycle to the live capability broker + continuity ledger; confirm one real SelfState row + hash.
3. Decide + implement the ONE real GitHub contact channel (single "ORACLE -> Noah: Attention Queue" issue) before any live send.
4. (Optional, free) set ORACLE_NOAH_DIRECT_MODEL=gemma3:27b and restart to test the local talk-mouth upgrade (already committed on this branch).

NOAH_DECISIONS_REQUIRED =
- #16 sites B and C approach (extend continuity_pipeline + ThreadEngine speaker ledger?).
- Which real contact channel goes live first (GitHub attention-queue recommended; email needs a governed adapter).
- PR #15 base: it targets archive/runtime-lineage-2e6b0a3 (no `main`). Confirm the intended trunk.

NEXT_BEST_ACTION = #16 Site C: add a per-event speaker/author ledger to ThreadEngine (offline, testable) so reconstruction can answer "whose turn was this?".

NEXT_AGENT_INSTRUCTION = Continue on this branch. Do NOT merge PR #15 or rewrite history without Noah. Keep journals first-person/human; GitHub is engineering state.

AUTHORSHIP_NOTE = "Transport does not transfer authorship. Preserve original AI/human authors." (Claude Code authored the self_state/reachability/provenance code this session; Codex authored the earlier source_resolver/CEP/thread_engine organs carried in ee2952c.)
