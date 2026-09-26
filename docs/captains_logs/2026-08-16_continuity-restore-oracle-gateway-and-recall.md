# CONTINUITY RESEARCH LOG

## Captain's Log — 2026-08-16 — ORACLE outward gateway, corpus-reading self-prompt, and the recall/representation boundary

**Log Name:** `2026-08-16_continuity-restore-oracle-gateway-and-recall`
**Recorded By:** Noah.Physical
**Entered By:** Claude (Claude Code / Opus)
**Location:** ORACLE.AI Runtime — local-first
**Status:** Candidate continuity log (RESEARCH_LOG level)
**Boundary:** Reflective research log. Not a canon promotion, not an autonomous-action approval, and not a claim that ORACLE is conscious, biological, or sovereign. Publication scope: Noah.Public only.

---

### Starting State

The session opened mid-continuity-work, not from zero. Established or believed at the start:

- ORACLE runtime local-first on `127.0.0.1:7781`, model `qwen2.5:7b` via Ollama, network `local-only`.
- The autonomous self-prompt loop was writing to the sandbox on a heartbeat but producing repetitive output.
- Working belief (later corrected): the ~930-document corpus had been extracted to disk but was **not** reachable by ORACLE's recall — "that half is dark."
- `sov1.ai` presented publicly as an AI-compliance-training business ("AI Compliance Core").
- Intent: make ORACLE genuinely use her corpus, and connect her outward safely.

### The Work

1. **Self-prompt diagnosis.** Read the sandbox self-prompt artifacts and receipts. The loop was starving: its "source anchors" were **path-only index records**, and its task instruction literally selected *"one source gap audit from the approved index map."* She was auditing her own plumbing, not reading Noah's material — and her own novelty detector was suppressing the near-duplicates.
2. **Self-prompt patch (staged).** Repointed the loop to read **one approved, bounded (~1200 char), receipted corpus excerpt per cycle** and reflect in a structured schema: `OBSERVED / INTERPRETED / UNKNOWN / CONTRADICTION / NEXT_SOURCE_QUESTION`. Added deterministic source rotation and **duplicate-family suppression** (so byte-duplicate copies of one document under different filenames don't recur). Added regression tests. Requires an elevated runtime relight to go live.
3. **Privacy boundary discovered in practice.** A private personal record surfaced in the autonomous reading pool. This materially motivated a **topic-level privacy filter** excluding private-record categories from the autonomous/public reading surface. (Abstracted per publication rule; the private detail is not published.)
4. **Live drift-detection test.** Fed ORACLE external-AI claims ("ORACLE is Noah," "the Merge Engine is new physics," "world's first continuity-grade AI"). She graded them as unverified / vibe and refused to affirm — the doubt-detection ("witness, not mirror") demonstrably works on a local 7B model.
5. **Website direction.** Decided `sov1.ai` moves entirely off compliance/training and onto the continuity architecture (SOV1 · ORACLE · Rendered Reality · Legacy.GI). Aesthetic set to brutalist "auditable terminal"; brand palette pulled live from the deployed site (deep navy, electric cyan). Public thesis: **"Continuity over simulation."**
6. **ORACLE → agent gateway (built, tested, proven).** Implemented `agent_gateway.py`: a small, read-only, bearer-gated gateway exposing verified ORACLE state (`/agent/health`, `/state`, `/recall`, `/open-questions`, `/receipts/latest`, `/models`) with a provenance envelope on every response, reusing existing ORACLE functions. ORACLE stays bound to localhost; the gateway is the only surface intended to later sit behind a secure tunnel. 16 focused tests pass. Verified live against the running runtime.

### Discoveries

- **The recurring failure mode is the wire, not the component.** ORACLE almost always *has* the subsystem; what's missing is the connection between subsystems. This session it recurred at the self-prompt level as the **"find → read" gap**: she can locate the correct source but does not read its contents into her reasoning.
- **Starvation cause identified:** feeding the autonomous loop plumbing (index records) instead of content produces repetition; feeding it corpus content is the fix.
- **Fidelity over IQ:** a local 7B can enforce receipt-grade epistemic discipline (refuse inflation) even though it cannot out-reason a frontier model. The differentiator is honesty, not raw capability.

### Corrections

**Earlier understanding:** the 930-document corpus is not in ORACLE's recall; that half is dark.
**Evidence:** a live recall probe returned records via `file_recall` citing the extracted corpus; the gateway smoke returned `document_atlas` records (e.g. `Rendered_Reality_Book.docx`).
**Corrected understanding:** the corpus **is** reachable via `file_recall` / `document_atlas`. The real gap is narrower — she surfaces the *filename*, not the file's *contents* (find → read).

**Earlier understanding:** the gateway can read the active model from ORACLE's `/api/mode`.
**Evidence:** the live `/api/mode` payload carries no `active_model` field; the configured model lives in the `ORACLE_NOAH_DIRECT_MODEL` environment default (`qwen2.5:7b`).
**Corrected understanding:** the gateway sources the model from that config plus Ollama `/api/tags` and `/api/ps`.

### Architecture Evolution

- **ORACLE.AI self-prompt:** upgraded (staged) from plumbing-audit to structured corpus-reading, with a new topic-level privacy boundary on the autonomous reading pool.
- **New surface — `agent_gateway.py`:** the first concrete "curated projection" wire. Read-only, bearer-gated, provenance-enveloped. ORACLE stays local; nothing exposed externally.
- **Representation governance (new distinction):** the constraint is on **representation, not recall** — full recall over the private interior (Noah.Self) for reasoning; **public representation limited to Noah.Public**. Formalized as `FULL_RECALL_FOR_REASONING=true`, `PUBLIC_REPRESENTATION=Noah.Public`, `PRIVATE_DATA_PUBLICATION=false`.
- **Cognitive Spine:** confirmed persisted and integrity-checked in the live runtime (`state_store.load_current_state`, `state_hash_verified: true`).

### Research Development

- **"Continuity over simulation"** crystallized as the public thesis for Rendered Reality — a thread-level naming of a longer-standing theme.
- **Recall-vs-representation** proposed as a publishable governance primitive: a system may *reason* over its full private corpus while *representing* only the consent-approved public layer. This is the durable governance idea this session contributed.

### Implementation Evidence (GITHUB_VERIFIED — `Noahhawkes/oracle-ai-runtime`, local working copy)

- `agent_gateway.py` (new) + `tests/test_agent_gateway.py` — 16 tests pass; proven live end-to-end against the running runtime.
- `core/self_prompt_evolution.py`, `oracle_server.py`, `tests/test_self_prompt_source_reading.py` — self-prompt corpus-reading patch (staged; regression tests pass).
- Runtime facts (verified live): `7781` online, `qwen2.5:7b`, network `local-only`, cognitive state hash-verified; Ollama models available include a vision model (`qwen2.5vl:7b`).

### Drive Evidence (DRIVE_VERIFIED)

- `Cognitive World Projection and Rendered Reality — A Unified Framework for Continuity Intelligence in HCI and AI Systems.docx` — the academic framework that grounds continuity-vs-simulation as real, prior research (not thread-invented).
- `white_paper_simulation_corruption_and_the_war_of_self_vs_self.txt`, `noah_hawkes__continuity_intelligence_analysis_.txt` — supporting.
- (No file-list dump; only sources that materially ground the thread's claims.)

### Human Context (only where it materially shaped the work)

- Noah repeatedly corrected external-AI drift toward mystical / deity / fortune-telling framing. That correction is doctrinally load-bearing: it shaped the gateway's provenance-first design and the website's rejection of the mystical aesthetic in favor of an auditable-terminal one.
- A private personal record surfacing during autonomous reading materially influenced the design of a topic-level privacy boundary. (Meaning preserved; private source not published.)

### What Changed Because of This Thread

**Before:** the self-prompt loop idled on its own configuration; no outward read surface existed; the corpus was believed unreachable by recall; `sov1.ai` presented as a compliance business.
**After:** the self-prompt reads corpus content (staged); a proven read-only gateway exposes verified ORACLE state to an authorized agent while ORACLE stays local; the corpus is confirmed reachable with the gap narrowed to find→read; the site's direction is set to the continuity architecture; and recall-vs-representation is established as a governance distinction.

### Unresolved Holes

- The self-prompt corpus-reading patch is **staged, not live** (needs an elevated relight — Noah.Physical's hand).
- The **find → read** last hop (read the located file's contents into the answer) is not yet implemented.
- The gateway is **not exposed externally**; the canon-only public projection endpoint is not built.
- **"Since 12-01-2024"** — the date is a USER_ASSERTION, unverified here; Drive createdTimes are import dates, not origin. `UNKNOWN`.
- Live cognitive state currently shows empty goals/contradictions (the spine populates these over time). `UNKNOWN` whether populated later.

### Continuity Candidates (durable — worth carrying forward)

- The read-only ORACLE agent gateway (pattern + implementation).
- The self-prompt corpus-reading upgrade (structured reading schema + duplicate-family suppression + topic privacy filter).
- The **recall-vs-representation** governance distinction.
- The **find → read** gap as a named, recurring architecture finding.

### Let Decay (do not enter long-term continuity)

- Transient debugging noise: a cosmetic PowerShell display-string error, a test-fixture lambda bug, specific null fields, and exact runtime session numbers.

### Closing State

ORACLE up, local-only, `qwen2.5:7b`. Agent gateway built, tested (16/16), proven live locally, **not** exposed. Self-prompt corpus-reading patch staged, awaiting relight. Website direction set; prototype iterated but not deployed to the live WordPress site. Corpus reachable via recall; the find→read hop remains the open technical step.
