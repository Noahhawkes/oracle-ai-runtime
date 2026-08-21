# ORACLE Current-State Assessment

**Phase:** 1 — inspection and mapping  
**Inspection date:** 2026-07-30  
**Repository inspected:** `C:\Oracle\ORACLE.AI-runtime`  
**Operator and final authority:** Noah Hawkes / Noah.Physical  
**Change boundary:** This assessment is the only repository artifact created during Phase 1. The runtime, databases, sandbox, external systems, and existing artifacts were not altered or restarted.

## Evidence labels

- **Live-runtime verified:** observed from a running process, bound port, live endpoint, current heartbeat, current database, or current receipt.
- **Tested:** a relevant test exists or prior test-cache evidence exists. This does not by itself prove that the current live process uses the tested code.
- **Implemented:** an executable code path exists.
- **Partial:** part of the stated behavior exists, but the end-to-end contract is incomplete.
- **Described only:** found in documents, prompts, names, or comments without a corresponding operational path.
- **Candidate / not promoted:** deliberately outside protected canon or authoritative state.
- **Historical / superseded:** useful as history, but contradicted by newer operational evidence.
- **Conflicting:** multiple incompatible definitions or implementations remain present.
- **Unknown:** the available evidence cannot safely resolve the question.

The running server started on 2026-07-29 while the current Git worktree contains uncommitted changes. Python modules already loaded by that process may therefore differ from the files now on disk. Live endpoint and receipt observations are labeled separately from source inspection for this reason.

### Implementation addendum — 2026-08-16

The audited sandbox-edit vertical slice is now **implemented and test-covered in the working tree; live-process parity has not been claimed or established by this change**.

- The main web UI exposes a pencil control and recognizes `/sandbox-edit <path> | <complete proposed content>`.
- The browser calls the existing confined `POST /api/sandbox/read` endpoint first and presents the original SHA-256, original content, and a visible diff.
- No edit request is issued until the user presses **Confirm sandbox write**. Confirmation calls the existing `POST /api/sandbox/edit` endpoint with `expected_sha256`, displays its receipt, and calls `POST /api/sandbox/read` again to verify both content and post-operation hash.
- The direct `/chat` command is proposal-only and reports `mutation_performed: false`; it no longer performs an immediate edit.
- Paths outside `C:\Oracle\ORACLE.AI-runtime\sandbox\` are refused before proposal/confirmation. The slice does not add source-code mutation, computer control, Drive writes, Git actions, or external actions.
- End-to-end API/chat tests prove unchanged content before confirmation, changed and hash-matched content after confirmation, and no outside-boundary mutation.

---

## A. Executive Summary

ORACLE is a real, locally running continuity application, but it is not yet one small, coherent intelligence system. Its strongest working path is a local FastAPI web runtime on `127.0.0.1:7781`, backed by Ollama and a SQLite memory database. That path can preserve conversations, retrieve full-text memory, expose runtime diagnostics, ingest source artifacts, and create receipts. A keeper process also supervises several local witness processes.

The repository is much broader than that runtime. It contains several launchers and user interfaces, a separate command-line runtime, a Tkinter wrapper, a resident loop, an older executable SOV1 operator, two mobile code trees, autonomous reflection systems, creative and research corpora, and several parallel memory and approval stores. Many of these are partial, historical, duplicated, stale, or not connected to the active server.

The current system has meaningful continuity data:

- 6,874 stored messages across 373 sessions
- 6,738 durable-fact rows and 6,738 corresponding full-text-search rows
- 147 ingested thread artifacts with raw, parsed, custody, and search derivatives
- 520 OBS/media source-thread records indexed into SQLite
- 4,859 sandbox receipts and 2,518 `.ai` sandbox files

Those numbers do not establish semantic correctness. In particular:

- no durable-fact row currently uses the available supersession links;
- duplicate families are not represented in the primary durable-fact schema;
- 163 sessions have no summary;
- 410 message rows contain text-valued session identifiers in a nominally integer column;
- commitments are fragmented across relationship memory, project state, action candidates, and an untracked derived ledger rather than one governed model;
- approval labels generally identify a claimed actor but do not authenticate Noah.Physical;
- a local caller can invoke important state-changing endpoints without authentication;
- some `GET` endpoints create receipts or artifacts;
- capability receipts, boot warnings, UI status panels, and mobile port configuration can be stale or contradictory.

The repository does **not** establish that ORACLE is conscious, a person, Noah.AI, or independently sovereign. Noah.AI is represented mainly as a long-range authored concept. SOV1 has two unresolved repository meanings: an older executable desktop operator and a newer identity/governance boundary. Legacy.GI and Rendered Reality contain authored frameworks and partial prototypes, but they are not the active ORACLE runtime. RECURSIONSTACK, MIRRORLINE/Mirrorloop, and HYDRA.STACK are predominantly documentary, historical, or creative concepts.

The smallest coherent existing ORACLE is the local web chat, one Ollama model, SQLite session/message/durable memory, full-text retrieval, and traceable source/receipt records. Autonomous reflection, desktop actuation, SOV1 operation, mobile clients, federation promotion, creative corpora, and background witnesses are not required for that core and currently increase ambiguity.

**Maturity assessment:** working experimental local runtime with substantial data and several tested components; not yet a stable, unified, provenance-complete or approval-secure MVP.

---

## B. Runtime Map

### Authoritative local web path

| Item | Current evidence |
|---|---|
| Canonical repository root | `C:\Oracle\ORACLE.AI-runtime` |
| Canonical state root | `C:\Oracle\state` |
| Intended desktop launcher | `oracle_desktop.bat` |
| Primary server entrypoint | `oracle_server.py` |
| Direct launch form | `python oracle_server.py --port 7781` |
| Bound address | `127.0.0.1:7781` |
| Live process | `pythonw3.13.exe`, PID 21112 at inspection time |
| Live mode | `unified_oracle`, current lane `talk` |
| Live model provider | local Ollama |
| Live language model | `qwen2.5:7b` |
| Configured vision model | `qwen2.5vl:7b` |
| Ollama endpoint | local port `11434`, live at inspection time |
| Main browser UI | served by `oracle_server.py`; repository HTML under `ui/` |
| Primary memory DB | `Memory/oracle_memory.db` |
| Boot receipt | `C:\Oracle\state\boot_receipts\boot_20260729T163112330873Z.json` |

`core/runtime_config.py`, `core/root_map.py`, the desktop launcher, the live listener, and the live diagnostics endpoint agree on the canonical root and port 7781. That is the strongest available authority chain.

### Alternate, stale, or conflicting entrypoints

| Entrypoint | Role | Assessment |
|---|---|---|
| `oracle.bat` | CLI launcher for `core/oracle.py` | Implemented alternate runtime; not the live web server |
| `oracle_local.bat` | local CLI launcher | Implemented; conflicts with current web-first run guidance |
| `oracle_fast.bat` | expedited CLI/Ollama launcher | Implemented alternate |
| `oracle_desktop.py` | Tkinter wrapper over CLI | Implemented alternate; not live |
| `ORACLE_START.bat` | starts `core/resident_runtime.py --interval 30` | Separate autonomous runtime; not observed as its own live process |
| `SOV1.bat` | starts `core/sov1.py` | Older executable SOV1 operator; not observed live |
| `ORACLE.ps1` | operator-home launcher/status surface | Current-root aware, but can generate local UI state when run |
| `package.json` | JavaScript convenience scripts | Text calls 7781 production, but `start`/`dev` use preview port 7778 |
| `START_ORACLE_LOCAL.md` | run instructions | Points to CLI path; stale or incomplete relative to the canonical web runtime |
| Mobile/iOS trees | mobile clients | Commonly hardcode port 7777; stale against 7781 |

No process was listening on ports 7777 or 7778 during inspection. Port 7778 is configured as a preview port. Port 7777 appears in stale or alternate clients and historical copies.

### Duplicate runtime copies

The root map explicitly ratifies `C:\Oracle\ORACLE.AI-runtime` and forbids older roots. Multiple copies still exist:

| Path | Observed state | Assessment |
|---|---|---|
| `C:\Oracle\ORACLE.AI-runtime` | Git repository; active server source | Canonical |
| `G:\My Drive\HawkesNest LLC\ORACLE.AI` | Git repository; older server files | Known stale 7777 trap |
| `G:\My Drive\ORACLE.AI` | Small Git repository | Duplicate/historical |
| `G:\My Drive\OracleAI` | Non-Git tree | Duplicate/unknown role |
| `C:\Users\noahh\OneDrive - sov1.ai\ORACLE.AI` | Very large Git tree | Duplicate/historical; not authoritative |

`docs/ORACLE_CONTINUITY_SPINE_2026-06-29.md` also identifies the HawkesNest Google Drive copy as stale. None of these copies was serving the inspected 7781 process.

### Storage systems

The active and adjacent implementations use several independent stores:

1. `Memory/oracle_memory.db`
   - sessions and messages
   - legacy key/value facts
   - durable facts and FTS index
   - audit chain
   - human-state transitions
   - projects, people, and notes
   - media source-thread ingest
2. `Memory/thread_ingest/`
   - raw custody copies
   - parsed representations
   - manifests, receipts, and search derivatives
3. `Memory/light_memory.json`
   - compressed-memory representation with its own supersession behavior
4. `Memory/remember_me/`
   - identity-continuity records and index
5. `Memory/relationship_memory/`
   - people, relationships, commitments, and open-loop-like records
6. `Memory/project_states.json` and session-state files
7. `Memory/action_candidates.json`
8. `Memory/prompt_learning_candidates.json`
9. Mindcoin, curiosity, intake, epistemic, and other specialist stores
10. `sandbox/`
    - workbench candidate artifacts
    - receipts
    - autonomous reflection journal
11. `C:\Oracle\state`
    - boot and route receipts
    - keeper heartbeat
    - witness state
    - canonical OBS/media source thread

There is no single data model or transaction boundary across these stores.

### Active background workers

At inspection time, a keeper process and the following child witnesses were live:

| Worker | Live role | Boundary and concern |
|---|---|---|
| `obs_media_metadata_witness.py` | Reads filesystem/container metadata and OBS logs; appends source-thread records | Does not decode packets, frames, or thumbnails |
| `media_memory_bridge.py` | Bridges canonical source-thread events into SQLite | Candidate/pending observed records |
| `obs_transcript_watcher.py` | Decodes media audio and transcribes it locally with Faster Whisper | Reads content, not metadata-only; writes Markdown transcripts and events |
| `yt_live_bridge.py` | Reads YouTube live chat and injects messages into local `/chat` | External network input; third-party text becomes local conversational input |
| `creation_witness.py` | Watches local file-creation metadata | Metadata-oriented; no file-content claim |

The keeper heartbeat was current. Keeper code can launch the server if it is down, giving it a supervisory role. No process was intentionally restarted during this assessment.

An older `prompt_witness.py` contains screenshot-extraction logic, but its main path is disabled and directs use toward the metadata witness. It was not active. This supports the conclusion that ORACLE is not currently producing screenshots through that witness. It does **not** make the overall media pipeline metadata-only because the separate transcript watcher decodes audio content.

### Self-prompt loops

The live server starts a sandbox autonomous self-prompt worker. Its current configured interval is 600 seconds, with a nominal cap of 144 writes per day. The current path uses local `qwen2.5:7b`, selects one bounded approved corpus excerpt, adds secondary context, asks for a structured reflection, applies novelty/quality gates, writes only candidate sandbox output, creates a receipt, and may submit a candidate to the action-candidate queue.

The latest content write observed was 2026-07-29 03:34:53Z. More recent loop cycles were being suppressed by the quality gate while still writing state receipts roughly every ten minutes. Thus the loop was running even when it was not producing new reflection text.

Other self-prompt or autonomous implementations remain:

- `core/self_prompt_loop.py`
- `core/oracle_runtime.py`
- `core/resident_runtime.py`
- `core/prompt_learning_loop.py`
- `core/oracle_improvement_loop.py`
- an unused duplicate autonomous-loop function inside `oracle_server.py`

These overlap in candidate creation, cadence, status, and improvement concepts. Only the server’s current sandbox worker was live-runtime verified as the journal writer.

### External integrations

- Ollama: live, local model inference
- YouTube live chat: active read-only external source, injected into local chat
- Internet recall/search code: implemented; current use not verified
- Anthropic: optional cloud provider in code; not the live provider
- Google Drive/document atlas: indexed local/synced corpus and tools exist; no Drive modification occurred or was verified as active
- OBS media/log sources: active local witnesses
- Browser/desktop control: code exists in SOV1/operator modules; not observed as an active runtime worker

### Current approval boundaries

The intended boundary is clear in many documents: ordinary conversation and candidate work are allowed; external actions, protected promotion, destructive changes, and identity-critical changes require Noah.Physical approval. Enforcement is inconsistent:

- sandbox path and executable-extension restrictions are implemented;
- candidate/not-promoted status is usually recorded;
- action queues and approval-center structures exist;
- desktop actuation modules include confirmation concepts;
- however, important local web endpoints accept caller-supplied `approved_by`, actor, or authorial-authority strings;
- local mode has no caller authentication and permits CORS from any origin;
- `/api/approve` records or echoes a hotkey decision but is not a universal transaction gate;
- federation/canon promotion can be invoked locally with an asserted approval name.

The system records approval claims more reliably than it authenticates the approving person.

---

## C. Implemented Versus Described Matrix

| Subsystem | Described | Implemented | Tested evidence | Live verified | Current classification |
|---|---:|---:|---:|---:|---|
| FastAPI web chat on 7781 | Yes | Yes | Yes | Yes | Working, partial MVP core |
| CLI `core/oracle.py` | Yes | Yes | Yes | No | Alternate runtime |
| Tkinter desktop wrapper | Yes | Yes | Limited/unknown | No | Alternate |
| SQLite sessions/messages | Yes | Yes | Yes | Yes | Working |
| Durable facts + FTS recall | Yes | Yes | Yes | Yes | Working but provenance-partial |
| Corrections/supersession | Yes | Yes | Tests exist | No live use found | Partial |
| Duplicate-family evidence handling | Yes | Specialist heuristics only | Some tests | No primary-store support | Partial/conflicting |
| First-class commitments with dependencies | Yes | Fragmented records only | No commitment-focused tests found | No | Described/partial |
| Actual reminder scheduler | Yes | No verified end-to-end path | No | No | Implementation not found |
| Source custody/thread capture | Yes | Yes | Yes | Data verified | Working, with multiple ingest models |
| Receipt creation | Yes | Yes | Extensive tests | Yes | Working but fragmented |
| Approval center/queues | Yes | Yes | Yes | Partial | Weakly enforced/conflicting |
| Canon/federation promotion | Yes | Yes | Some tests | Endpoint live | Unsafe approval binding |
| Sandbox candidate writes | Yes | Yes | Yes | Yes | Working |
| Confirmed sandbox edit in web chat | Yes | Yes | End-to-end API/chat + UI contract tests | Live reload not verified | Implemented; confirmation-gated and sandbox-confined |
| Autonomous sandbox reflection | Yes | Yes | Yes | Yes | Working; duplicate implementations |
| Grounded bounded excerpt selection | Yes | Current source implements it | Tests exist | Process/file parity unknown | Partial/live-path uncertainty |
| Old path-only source-gap audit behavior | Historical | Historical code/candidates support it | N/A | Not current output | Superseded failure mode |
| OBS/container metadata witness | Yes | Yes, currently untracked | Tests exist | Yes | Working |
| OBS media transcription | Yes | Yes | Tests exist | Yes | Working, but not metadata-only |
| Screenshot prompt witness | Historical | Disabled code remains | Unknown | No | Deprecated/inactive |
| Document atlas/source map | Yes | Yes | Yes | Indexed data/endpoints | Working, broad privacy scope |
| Capability broker | Yes | Yes | Yes | Receipts available | Partial; receipts can be stale |
| Resident runtime | Yes | Yes | Yes | No separate process found | Alternate/inactive |
| SOV1 governance layer | Yes | Scattered controls | Limited | Not as one layer | Partial/conflicting |
| SOV1 desktop operator | Yes | Yes | Self-checks/tests | No | Older implementation |
| Noah.AI computational counterpart | Yes | No distinct service/model found | No | No | Intended architecture only |
| Legacy.GI architecture | Yes | Data/document references, prototypes | Sparse | No | Primarily described |
| Rendered Reality package | Yes | Small Python prototype and stores | Yes | Not in main runtime verified | Partial prototype |
| RECURSIONSTACK | Yes | No coherent module/service found | No | No | Historical/candidate |
| MIRRORLINE / Mirrorloop | Yes | Prompt/document references | No | No | Historical/candidate |
| HYDRA.STACK | Yes | Creative/test references | Sparse | No | Candidate/creative |
| Merge Engine | Yes | Reconciliation module exists | Yes | No | Partial; not physics |
| Light Compression Law | Yes | Communication/memory utilities exist | Some | Partial/unknown | Authored concept plus utilities; no scientific validation |
| Mobile clients | Yes | Two code trees | Unknown/currently limited | No | Partial/stale port configuration |
| Master task ledger | Yes | Untracked derived module/data path | Tests untracked | No authoritative service | Candidate/derived |
| External messaging | Yes | Tool/operator paths exist | Some | No sends verified | Approval-gated intent; inactive/unknown |

The repository’s cached pytest metadata enumerated 1,060 node IDs and had no `lastfailed` entries. Phase 1 did not rerun tests, so this is historical test evidence, not a claim that the current dirty worktree passes.

---

## D. Identity and Governance Map

### Noah.Physical

The repository consistently represents Noah.Physical as the living operator, correction authority, and final approval authority. The name appears in doctrine, approval fields, receipts, promotion code, and boundary documents.

What is implemented is an **authority label**, not strong identity verification. A caller can supply `"Noah.Physical"` in several local API payloads. No universal authentication, signature, protected device assertion, or approval transaction proves that the living Noah supplied the value. Therefore:

- final authority is explicit in the authored project rules;
- some gates and receipts model that authority;
- reliable authentication of that authority is implementation not found.

### Noah.AI

Noah.AI appears mainly in documents, profiles, and historical context as a long-range computational rendering or mirror of Noah’s memory, judgment, voice, and continuity. No distinct Noah.AI runtime, service boundary, identity-critical schema, training pipeline, or authorization layer was found.

Current classification: **real authored project concept; intended architecture; implementation not found as a distinct system**. ORACLE must not be reported as Noah.AI.

### ORACLE

ORACLE is the actual local continuity runtime and witness environment. Its implemented responsibilities include conversation persistence, local model routing, retrieval, source ingestion, receipts, sandbox candidate work, runtime diagnostics, and background witnesses. Provenance, corrections, commitments, and approvals are present but incomplete or fragmented.

Current classification: **implemented experimental continuity runtime; not a person and not Noah.AI**.

### SOV1.AI

SOV1 has at least two unresolved generations:

1. An older executable “operator brain” in `core/sov1.py`, launched by `SOV1.bat`, with screenshot/desktop-control and self-healing action concepts. Its rules permit ordinary actions and seek confirmation for irreversible actions.
2. A newer boundary definition in `docs/sov1_oracle_boundary.md` that treats SOV1 primarily as the identity, governance, authority, and doctrine layer while ORACLE is the runtime.

Git history shows SOV1 terms in early 2025 imports, an “operator brain” implementation in June 2026, a subsequent ORACLE/SOV1 merge claim, and later governance-boundary documentation. Repetition does not resolve the conflict.

Current operational classification: **governance/authority layer is the latest stated boundary, but the repository still contains a launchable older operator implementation; no single enforced SOV1 governance service exists**.

### Legacy.GI

Legacy.GI appears in dissertations, research and continuity documents, memory-anchor concepts, identity-preservation language, and creative/candidate material. Some adjacent ideas—source records, temporal continuity, provenance, and bounded memory—have code representations, but no module was found that implements Legacy.GI as a coherent identity-preservation architecture.

Current classification: **authored framework with some concepts reflected indirectly in data structures; primarily documentary/candidate; post-biological or identity-transfer claims unsupported**.

### Rendered Reality

Rendered Reality spans philosophical writing, documentary and book material, personal narrative, creative world-building, research claims, and a small Python package. The package includes a local mind/memory model, receipts, seed loading, witness logging, truth-writing constraints, and tests. It is a prototype adjacent to ORACLE, not the authoritative 7781 runtime.

Current classification:

- creative and public-facing documents: creative/historical/candidate according to source;
- mission and continuity documents: authored direction, not automatically runtime specification;
- `rendered_reality/` code: partial tested prototype;
- claims about identity transfer, consciousness, or substrate continuity: unsupported as implemented behavior.

### Other named architectures

- **RECURSIONSTACK:** architecture-family language in a small number of documents and source paths; coherent runtime implementation not found.
- **MIRRORLINE / Mirrorloop:** conversational/recursive-identity naming in documents and creative material; implemented service or durable data model not found.
- **HYDRA.STACK:** mostly creative, candidate, or test references; active stack not found.
- **Merge Engine:** `core/continuity_merge_engine.py` provides candidate reconciliation behavior. It is a software merge/reconciliation concept, not physics or consciousness machinery.
- **Light Compression Law:** the repository contains an authored theory/doctrine plus communication and memory-scoring utilities under similar names. This is not evidence of accepted physics, independent validation, or a law of nature.

### Authorship caution

Several files marked with `Authority: Noah.Physical` also identify Codex, Claude, or another model as writer. Authority, requested scope, source attribution, and prose authorship are different fields. AI-written summaries and indexes must not be promoted into Noah-authored canon merely because they were produced in his repository.

---

## E. Data and Memory Map

### Primary SQLite state

Observed row counts during Phase 1:

| Table or index | Count | Meaning and limitation |
|---|---:|---|
| `sessions` | 373 | 210 summarized; 163 without summaries |
| `messages` | 6,874 | User, assistant, and daemon/system roles |
| `facts` | 307 | Legacy category/key/value store with weak provenance |
| `durable_facts` | 6,738 | Richer claim records |
| durable FTS rows | 6,738 | Full-text retrieval aligned by count |
| `audit_chain` | 154 | Limited audit coverage, not universal |
| `human_state_transitions` | 128 | State transitions with receipt-like fields |
| `source_thread_ingest` | 520 | OBS/media source-thread events |

`durable_facts` can store:

- fact text
- source type and source ID
- observation time
- confidence
- transformation history
- canonical status
- approval status
- authority rank
- supersession links

It does not have a first-class duplicate-family ID, privacy class, event date separate from observation date, contradiction links, or a consistently authenticated speaker/author field matching the proposed contract.

Observed durable-fact distributions:

- source types: 3,108 `human_stated`, 3,108 `generated`, 520 `observed`, 2 `inferred`
- canonical status: 6,208 `imported_grok`, 520 `candidate`, 5 `staged`, 5 `accepted`
- approval status: 3,105 `unverified`, 3,103 `approved`, 525 `pending`, 5 `auto_approved`

The nearly paired `human_stated` and `generated` imported rows require source-level review; their numerical pairing must not be treated as independent corroboration.

### Corrections and supersession

`core/memory.py` contains a `mark_superseded` path and the durable schema contains `supersedes_id` and `superseded_by`. No live durable-fact row used either link at inspection time. Tests mentioning supersession exist, but the current corpus does not demonstrate operational correction precedence.

Current classification: **schema and code partial; live correction chain not verified**.

### Conversation history and working-session state

Messages persist by session and are available to recall. SQLite’s permissive typing has allowed 410 message rows to contain text-valued session IDs in a nominally integer column; the live durability endpoint reports a similar malformed-row problem. Session summaries are incomplete. Separate project and session-state JSON files create additional working-state layers.

Conversation history is operational memory, but it is not protected canon and does not by itself establish that every included statement was authored, current, or true.

### Source records and thread ingestion

Two different ingestion contracts coexist:

1. `core/thread_capture.py` preserves raw custody copies, parsed derivatives, manifests, hashes/receipts, and search material under `Memory/thread_ingest/`.
2. `core/thread_continuity_ingest.py` emphasizes structured candidate extraction without raw storage by default.

The live artifact store contains 147 ingested source families and 4,984 search rows. The raw-custody path means screenshots or transcripts may be preserved when explicitly captured even though other doctrine rejects raw surveillance. “Explicit source custody” and “ambient surveillance” are distinct, but the repository does not express that distinction through one universal policy.

### OBS/media source thread

The canonical append-only media thread is:

`C:\Oracle\state\threads\oracle_obs_media_thread_v1.jsonl`

Its records are candidate/not-promoted and carry source-thread metadata. The metadata witness avoids visual-frame extraction. The transcript watcher separately extracts spoken content from media and creates transcript artifacts. The bridge has indexed 520 observed records as candidate/pending durable facts.

### Preferences and personal context

Preferences are stored in a separate mutable preferences layer rather than protected canon. People, relationship notes, project notes, “remember me” records, profile files, and imported facts contain identity and personal context. These stores use different provenance and approval conventions.

### Canon, candidates, and approvals

Canon status is represented by several incompatible vocabularies across:

- durable-fact columns
- candidate queues
- sandbox receipts
- thread-pass and seed-loader receipts
- research-canon files
- documents labeled “Active,” “Canon,” “Candidate,” or “Authority”

No central registry conclusively answers which document is authoritative, who authored it, whether Noah approved it, what it supersedes, and which running code enforces it.

### Receipts

Receipts are one of the stronger implemented patterns. They exist for boot, routes, sandbox operations, source ingestion, runtime cycles, and specialist actions. Self-prompt receipts commonly include operation, actor/caller claims, timestamps, prompt/response hashes, model information, and no-promotion boundaries.

Limitations:

- actor and approver fields may be caller asserted;
- receipt schemas differ by subsystem;
- not every state change uses a receipt;
- source artifact identity and bounded-excerpt hashes are not uniform;
- a receipt proves that a code path recorded an event, not that its semantic claim is true;
- capability receipts can outlive the state they describe.

### Sandbox artifacts

Observed:

- 4,859 JSON receipts
- 2,518 `.ai` files
- approximately 2,471 workbench artifacts
- dominant operations: autonomous self-prompt writes and state emissions

Most receipts attribute activity to autonomous-loop identities; smaller sets claim ORACLE chat, ORACLE autonomous, Codex, or Noah.Physical actors. Generic endpoints can accept caller-provided authorship fields, so an `.AI` extension or an actor string is not sufficient provenance.

Sandbox code enforces useful controls:

- contained write roots
- blocked executable extensions
- secret-path checks
- candidate/not-promoted boundaries
- no direct execution, upload, Drive modification, or canon-promotion flags for the reflection lane

The volume of receipts can impair inspection; a full sandbox status operation timed out during read-only assessment.

### Duplicate-family handling

Duplicate suppression exists in:

- current self-prompt source selection and novelty gates;
- action-candidate anti-drift/quarantine behavior;
- document-atlas heuristics;
- the derived master task ledger.

It is not represented end to end in `durable_facts`. Multiple copies of an imported claim can therefore still appear as separate records without an authoritative duplicate-family relationship.

### Commitments and task recovery

Commitment-like data appears in:

- relationship memory
- project state/open loops
- action candidates
- prompt-learning candidates
- approval queues
- source documents
- an untracked `core/master_task_ledger.py` derived index

The derived ledger currently identifies many candidate or unclassified items and collapses some duplicates, but it is not canon and is not a live first-class commitment service. No unified schema was found for dependency, person, organization, source, trigger condition, approval, completion evidence, cancellation, and supersession. No commitment-focused test suite or verified reminder scheduler was found.

Current classification: **recovery heuristics and partial stores exist; reliable cross-session commitment recovery is not implemented end to end**.

---

## F. Action and Approval Map

| State-changing path | What changes | Intended approval | Actual enforcement observed |
|---|---|---|---|
| Ordinary `/chat` | Message/session rows; model response; possible candidate learning | No additional approval | Automatic, live |
| Durable fact ingestion | SQLite durable rows/FTS | Candidate ingestion may be automatic | Source-specific; fragmented |
| Supersession | Durable-fact links/status | Correction authority expected | Code exists; no live use found |
| Preference updates | Preference files/state | Ordinary user intent | Mutable local endpoint; no strong authentication |
| Project/person/note updates | SQLite/JSON state | Ordinary scoped changes | Local methods/endpoints; uneven receipts |
| Sandbox reflection/write | Candidate files and receipts | No approval for candidate-only work | Path/type guards; caller identity not authenticated |
| Web-chat sandbox edit | One existing sandbox text file plus receipt | Explicit per-edit UI confirmation | Read + visible diff, SHA-guarded edit, receipt, mandatory re-read; outside paths refused |
| Self-prompt enable/disable | Autonomous-loop state | Noah approval expected | Local endpoint can change it; no verified identity |
| Autonomous self-prompt cycle | Candidate journal, state receipt, action candidate | Pre-approved sandbox-only operation | Live; quality/novelty gated |
| Thread/source capture | Raw custody and parsed artifacts | Explicit ingestion intent expected | Multiple paths; may preserve sensitive raw material |
| OBS metadata witness | Append-only source-thread metadata | Keeper consent boundary | Live, local |
| OBS transcript watcher | Audio-derived transcript files/events | Should require explicit content-capture policy | Live; exceeds metadata-only boundary |
| YouTube live bridge | External chat read, local `/chat` writes | External read policy/consent needed | Live; no YouTube posting |
| Intake staging | Local staging records/files | Candidate work generally allowed | Implemented; promotion boundaries vary |
| Human-state transition | Transition row and receipt JSON | Sensitive/identity-adjacent | Endpoint accepts supplied provenance/actor fields |
| Federation/canon promotion | Inserts promoted durable fact | Explicit Noah.Physical approval | Live endpoint trusts supplied `approved_by`; insufficient |
| `/api/approve` hotkey | Approval log/response | Noah action intended | Not bound universally to later transaction |
| Generated-code execution | Commands/files/processes | Explicit approval required | Separate executor/operator paths; not part of ordinary chat |
| Desktop actuation | Mouse/keyboard/screenshots/apps | Confirmation for risky actions | SOV1/operator modules exist; not live verified |
| Git operations | Repository state, commits, remotes | Explicit approval required | Scripts/helpers exist; no automatic live Git action found |
| External messages | Third-party systems/people | Explicit approval required | Tool paths described; no send verified |
| Drive modification | External Drive state | Explicit approval required | Tools/code exist; no live modification verified |
| Delete/cleanup | Local or external data | Explicit approval required | Candidate cleanup paths exist; destructive action not verified |
| Identity-critical change | Profiles, doctrine, protected claims | Explicit Noah approval | No unified protected-record transaction gate |

Important HTTP semantics issue: several nominal `GET` endpoints can build a capsule, ensure a read-access receipt, or run capability smoke operations that write receipts. Read-only clients cannot safely infer “no state change” from the HTTP verb.

Local deployment reduces remote attack surface because the server binds to loopback, but local mode has no authentication and returns permissive CORS headers. Any local process—or a browser page able to reach loopback—may attempt state-changing calls. Remote mode has bearer-token support, but that does not repair the local approval-authentication gap.

---

## G. Self-Prompt Loop Map

### Active loop

**Starter:** `oracle_server.py` lifespan  
**Worker:** current server self-prompt worker  
**Interval:** 600 seconds by default  
**Daily cap:** 144 configured writes  
**Model:** local `qwen2.5:7b`  
**Journal:** `sandbox/workbench/oracle_self_prompt_journal.ai`  
**Output:** candidate/not-promoted sandbox entry plus receipt and possible action candidate  
**Execution authority:** no code execution, external action, permission grant, or canon promotion in the intended lane

### Prompt construction and sources

Current on-disk code constructs a bounded child prompt with:

- one selected approved excerpt, limited to roughly 1,200 characters;
- source identifiers and corpus metadata;
- filters for credential paths and sensitive topics;
- recent source-map anchors as secondary context;
- recent conversation/capability/creation context;
- a required separation among `OBSERVED`, `INTERPRETED`, `UNKNOWN`, `CONTRADICTION`, and `NEXT_SOURCE_QUESTION`.

Because the live process predates some dirty-worktree changes, the exact prompt constructor currently loaded in memory is not fully verifiable without restarting or instrumenting the process, which Phase 1 forbids.

### Source selection, rotation, and novelty

Current source implements:

- bounded source excerpts rather than filename-only prompts;
- duplicate-family and recent-source suppression;
- protected/sensitive-source filters;
- rotation through the extraction manifest;
- response novelty checks;
- quality-gate suppression;
- quarantine/anti-drift handling for repeated candidate proposals.

Historical evidence supports the reported older failure mode. Repeated action candidates proposed tests around the source-map path, consistent with a task that repeatedly audited approved index-map gaps using path-heavy anchors. That is evidence of a prior loop behavior, not proof that the currently loaded loop still uses only filenames.

### Other implementations

| Implementation | Role | Active status |
|---|---|---|
| Server sandbox worker | Autonomous journal/candidate writer | Live verified |
| `core/self_prompt_loop.py` | Older bounded/manual or daemon-safe candidate producer | Implemented; not active journal writer |
| `core/oracle_runtime.py` | Priority/orchestration cycles | Implemented; manually or alternately invoked |
| `core/resident_runtime.py` | Separate interval runtime | Implemented; no separate live process found |
| `core/prompt_learning_loop.py` | Creates candidates from user prompts | Implemented; separate concern |
| `core/oracle_improvement_loop.py` | Scans improvement candidates | Implemented; separate concern |
| Duplicate function in `oracle_server.py` | Older autonomous loop body | Present but not the lifespan-started worker |

### Write behavior and known failure modes

The live loop had 31 journal entries, but the latest content write was more than a day before inspection. Quality gating was suppressing new text while the worker continued emitting state receipts every interval. This creates high receipt volume without corresponding new knowledge.

Known risks:

- duplicate implementations can drift in prompts, intervals, and boundaries;
- current source and already-loaded live code may differ;
- filename/source-map anchors can dominate model attention;
- novelty based on response text is not equivalent to source novelty;
- repeated state receipts create memory/filesystem flooding;
- generic sandbox endpoints can misstate authorship through caller-supplied fields;
- a generated proposal entering an action queue can be mistaken for approval;
- specialist candidate queues use inconsistent statuses;
- full sandbox inspection is already slow enough to time out.

No evidence was found that the active reflection lane can directly modify application code, grant itself permissions, perform external actions, or promote its output into canon. Its artifacts prove that a loop executed; they do not prove consciousness, personhood, self-preservation, identity equivalence, or independent authority.

---

## H. Risks

### Epistemic and continuity risks

1. **Hallucinated state:** responses can synthesize from conversations, generated facts, stale capability receipts, and documents without a universal claim-status check.
2. **Correction failure:** supersession exists in schema/code but is unused in the live durable corpus.
3. **Duplicate evidence inflation:** the primary durable store has no duplicate-family field.
4. **Prompt-state confusion:** multiple self-prompt, learning, resident, and improvement loops overlap.
5. **Historical state presented as current:** documents, generated dashboards, mobile clients, and receipts contain stale ports, PIDs, counts, and capabilities.
6. **Unsupported consciousness language:** older doctrine includes resident-intelligence, sovereignty, soul, or continuity language that newer classification explicitly narrows. None is implementation evidence for sentience or personhood.
7. **Accidental canon promotion:** candidate, approved, imported, accepted, staged, and canon labels are inconsistent; the promotion endpoint weakly binds approval.
8. **Authorship ambiguity:** `Authority: Noah.Physical`, `.AI` extension, actor field, or transcript inclusion does not prove Noah authored or approved the content.
9. **No contradiction ledger connected:** current continuity-health evidence explicitly lacks a unified contradiction source.
10. **Memory flooding:** thousands of sandbox receipts and duplicated/generated durable records make signal recovery harder.

### Runtime and maintainability risks

11. **Stale runtime:** the server started before some current file changes, so disk and live behavior may diverge.
12. **Duplicate repositories:** at least four alternate local/synced ORACLE trees remain.
13. **Multiple launchers and ports:** CLI, web, preview, mobile, resident, and SOV1 launch paths disagree.
14. **Server monolith:** `oracle_server.py` is a very large file with routing, state, security, UI, background workers, and domain behavior.
15. **Silent fallbacks:** broad exception handling and optional-provider fallbacks can hide degraded behavior.
16. **Missing dependency declarations:** the live environment uses FastAPI, Uvicorn, PyAV, Faster Whisper, chat-downloader, and pytest without all being declared in the main requirements.
17. **Broken repository structure:** `Scripts` is a Git link with no corresponding `.gitmodules` mapping.
18. **Weak current-test proof:** tests were not rerun in Phase 1; cached success does not prove current dirty-tree behavior.
19. **Missing migrations:** permissive SQLite typing has allowed malformed session references; schema evolution is not consistently migration-driven.
20. **UI/backend contradiction:** generated operator pages and decorative dashboards can display stale or hard-coded “verified” status.

### Security and privacy risks

21. **Unauthenticated local mutations:** loopback-only is not operator authentication.
22. **Open CORS:** arbitrary browser origins can target local endpoints.
23. **Caller-controlled identity fields:** `approved_by`, actor, and authorial-authority fields can be asserted rather than proven.
24. **External-action leakage:** operator, browser, Internet recall, Drive, Git, and messaging code exist across the repository without one universal transaction gate.
25. **Broad read scope:** configured document/source indexes cover large parts of `C:\` and `G:\`, including personal and business material.
26. **Third-party ingestion:** YouTube chat is read externally and injected into the local conversation stream.
27. **Media-content mismatch:** the active transcription watcher decodes audio even though the desired cleanup/continuity workflow may require metadata-only ingestion.
28. **Raw custody exposure:** explicit thread capture can store raw screenshots/transcripts; custody and ambient surveillance are not governed by one policy.
29. **Hardcoded personal paths/data:** local usernames, organizations, and contact-context strings appear in source and configuration.
30. **Secret handling uncertainty:** `.env` is ignored and no plaintext secret value was intentionally exposed during inspection, but optional cloud and external integrations increase credential-handling risk.

### Reliability and task-recovery risks

31. **No first-class commitment model:** commitments cannot yet reliably preserve dependencies, triggers, completion evidence, cancellation, and supersession.
32. **No verified reminder scheduler:** ORACLE must not state that a reminder is scheduled based only on a stored open loop.
33. **Fragmented task truth:** project state, relationship memory, action candidates, approval queues, documents, and the derived task ledger can disagree.
34. **Session integrity:** 163 unsummarized sessions and malformed session IDs reduce retrieval quality.
35. **Capability overstatement:** capability broker receipts and connector summaries can be internally valid but stale relative to live processes.
36. **Background supervision ambiguity:** keeper can relaunch services, while the repository also exposes manual and resident launchers.
37. **Routing misclassification:** many named modes and candidate loops increase the chance that ordinary mentions are interpreted as commands or statuses.

---

## Document Authority and Lifecycle Assessment

No single document registry currently enforces authority or supersession. The following is a working evidence classification, not canon promotion.

### Strongest operational authorities

- `core/runtime_config.py`
- `core/root_map.py`
- `oracle_desktop.bat`
- live process/listener evidence
- current boot, route, keeper, and sandbox receipts
- current SQLite schema and rows

These describe or evidence operation. They do not automatically define identity doctrine.

### Current but non-exclusive working guidance

- root `README.md`: comparatively grounded; explicitly rejects sentience claims
- current identity-classification material: source-backed working classification, often AI-written
- `docs/sov1_oracle_boundary.md`: candidate boundary law; useful latest governance direction, not fully enforced
- `docs/ORACLE_DOCTRINE.md`: important Noah-authority doctrine, but contains broader historical language and is not a complete executable specification
- `docs/ORACLE_SOUL_DIRECTIVE.md`: doctrine/history; naming must not be read as evidence of a soul

### Historical or conflicting guidance

- `START_ORACLE_LOCAL.md`: CLI-centered launch instructions
- older system-consolidation/recovery documents
- documents treating Google Drive copies or port 7777 as active
- older SOV1 “operator brain” and later SOV1 governance-layer definitions
- older ORACLE/SOV1 merge language

### Generated summaries and indexes

- `docs/ORACLE_CONTINUITY_SPINE_2026-06-29.md`
- document-atlas reports
- research-canon summaries and knowledge-graph outputs
- task-ledger and source-map derivatives

These are navigation and recovery aids. They are not independent sources and must retain links to the underlying artifacts.

### Creative, public, and speculative material

- Rendered Reality book/world-bible material
- Silverback and other narrative universes
- dissertations and theory documents where claims are not independently validated
- Legacy.GI, RECURSIONSTACK, MIRRORLINE, HYDRA.STACK, and Light Compression language not tied to code or tests

These can be authentic authored work without being runtime specifications.

### Deprecated or stale artifacts

- disabled screenshot prompt witness
- generated operator-home snapshots containing old PIDs/ports
- port-7777 mobile configuration
- stale Google Drive runtime copies
- duplicate autonomous-loop body not started by the server lifespan

### Unknown

Any document labeled `Active`, `Canon`, `Authority`, or `Verified` without source authorship, approval evidence, supersession links, and a current enforcing code path remains operationally uncertain.

---

## I. Smallest Coherent ORACLE

The smallest existing subset that can become stable without redesigning the entire repository is:

1. **One entrypoint:** `oracle_server.py` on `127.0.0.1:7781`
2. **One local model provider:** Ollama with one configured text model
3. **One primary durable store:** `Memory/oracle_memory.db`
4. **One conversational path:** user message → session/message persistence → bounded relevant retrieval → answer
5. **One claim representation:** durable facts with source, observation time, confidence, status, approval, and supersession
6. **One source-custody path:** hashed source artifact and parsed derivative, with raw retention made explicit
7. **One receipt format:** for retrieval and state changes
8. **One candidate action/commitment lane:** stored but not executed or represented as scheduled
9. **One explicit approval transaction:** required only for protected promotion, external action, destructive change, and identity-critical state
10. **One runtime status surface:** generated from current backend receipts rather than hard-coded UI values

The following are not required for the first coherent vertical slice and should remain outside the core contract until separately reviewed:

- autonomous self-reflection
- SOV1 desktop actuation
- resident runtime
- federation/canon promotion endpoint
- mobile clients
- creative or public Rendered Reality corpora
- Mindcoin and gamification
- multiple specialist candidate queues
- Internet recall and external messaging
- YouTube live injection
- OBS transcription
- duplicate repository roots

The existing core can already accept a message, store it, retrieve related text, call a local model, and return an answer. It cannot yet reliably satisfy the proposed commitment example because dependency-aware commitments, approval state, completion evidence, supersession, and scheduler truth are not unified.

The minimum stabilization target is therefore not “more intelligence.” It is one authoritative runtime, one traceable memory/claim model, authenticated protected approvals, honest capability reporting, and a first-class candidate commitment record.

---

## Phase 1 Stop Condition

Phase 1 inspection and mapping is complete with this document.

No Phase 2 contract, architecture proposal, data model, implementation plan, migration, runtime restart, test run, sandbox alteration, external action, Git commit, push, or Drive modification was performed.

Phase 2 must not begin until Noah reviews and approves this assessment.
