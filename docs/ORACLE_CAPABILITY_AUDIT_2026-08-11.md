# ORACLE Current Capability Audit

**Date:** 2026-08-11
**Requested by:** Noah.Physical, in response to the "ORACLE Project Reset and Current Intent" handoff
**Method:** Static repository inspection (five parallel forensic passes) + direct spot-verification of the highest-stakes claims. Live baseline testing (Phase 2 of the handoff) is **not included** — no ORACLE process was running at session start, and starting one requires your explicit go-ahead per `.claude/launch.json`'s own warning that the canonical 7781 instance must never be started by tooling and the 7778 preview instance shares your live `Memory/oracle_memory.db`. This document is code-truth only. It will be wrong wherever the live process diverges from disk.

**Standard applied throughout:** a capability counts as real only if it is reachable from the interface you actually use (`ui/index.html`, served at `GET /`) and does something, not merely exists. Code presence, docstrings, module names ("self_build", "autonomous", "memory"), and passing tests that don't exercise the live path are not evidence.

**Implementation update — 2026-08-16:** The §14 vertical slice is implemented in the current working tree and covered by end-to-end API/chat tests plus UI contract tests. `ui/index.html` now provides an explicit `/sandbox-edit` proposal card: it reads through `/api/sandbox/read`, shows the original content/SHA and a diff, performs no mutation until **Confirm sandbox write**, writes through `/api/sandbox/edit` with `expected_sha256`, displays the receipt, and re-reads through `/api/sandbox/read` to verify the content/hash. Outside-sandbox paths receive a visible refusal. The direct `/chat` command is proposal-only. This update does not claim the already-running 7781 process has reloaded the working tree, and it adds no self-modifying source-code, computer-control, Drive-write, Git, or external-action path.

---

## 1. Current Runtime Topology

Nothing was running when this audit started — no listener on 7781, 7777, or 7778 (verified with a direct socket probe, not just `netstat`). Only Ollama (11434) was live.

**Entrypoint:** `oracle_server.py`, a 10,442-line FastAPI app. Default port 7781, set in `core/runtime_config.py:24`, overridable by `ORACLE_PORT` env or `--port`. Launched via `oracle_desktop.bat:54`.

**Twenty root launcher scripts exist** (`.bat`/`.ps1`), most of which do *not* start the web server:
- `oracle.bat`, `oracle_local.bat`, `oracle_fast.bat` → `core/oracle.py`, a separate terminal REPL, not the web app.
- `oracle_desktop.bat` → the actual web server on 7781.
- `ORACLE_HOME.bat` → `ORACLE.ps1`, which hardcodes port 7781 and explicitly documents 7777 as stale/legacy in its own comments.
- `ORACLE_START.bat` → `core/resident_runtime.py`, a third, independent cyclical runtime.
- `ORACLE_HEART.bat`, `ORACLE_PRESENCE.bat`, `oracle_tray.bat`, `SOV1.bat`, `BRIDGE.bat`, `DAILY.bat`, `overlay.bat` → six more standalone entrypoints, each its own process.

**Verdict: there are (at least) four independent, non-unified runtimes that all call themselves ORACLE** — the FastAPI web server, the `core/oracle.py` terminal CLI, `core/resident_runtime.py`, and an orphaned Tkinter GUI (`oracle_desktop.py`, launched by no current script). None of these share a process. This is the literal, mechanical version of "pile of programs."

**Supervision:** `tools/witness/oracle_keeper.py` polls `http://127.0.0.1:7781/health` every 60s and auto-restarts `oracle_server.py` if it's down, plus five witness subprocesses (media metadata, transcript, YouTube-chat bridge, creation watcher). Whether `oracle_keeper.py` itself is currently scheduled/running could not be confirmed statically — no Task Scheduler entry or `.bat` in the repo references it.

**Dependency declarations are broken.** `requirements.txt` (60 packages, oddly UTF-16 encoded) does not list `fastapi`, `uvicorn`, or `starlette` — the entire web framework `oracle_server.py` is built on is undeclared. Also missing: `faster_whisper`, `chat_downloader`, `av`/PyAV — all used by the witness processes. `anthropic` and `openai` SDKs *are* declared.

**Model config is dead code split across two places.** `config.yaml:4` declares `model: claude-sonnet-4-6` — but `oracle_server.py` never reads `config.yaml` at all (verified: zero references). The value that actually governs behavior lives in `.env`: `LOCAL_MODE=true`, `LOCAL_MODEL=qwen2.5:7b`. An `ANTHROPIC_API_KEY` is present in `.env` but inert while `LOCAL_MODE=true`. `config.yaml`'s model name only matters if `LOCAL_MODE` is ever flipped to `false` (`core/llm.py:87-93`).

---

## 2. User-Visible Capabilities

The real interactive surface of `ui/index.html` (what you actually see and can click) is:
- A text send box + send button (SSE-streamed replies from `POST /chat`, not a websocket — verified `oracle_server.py:9425` and `ui/index.html:2779`)
- Mic/voice/camera toggles
- Mode pills (Companion/Builder)
- A handful of suggestion chips (e.g., "propose a self-improvement")
- Read-only diagnostic panels under "More": SourceMap, Storage Census, Intake, Witness
- Plain links to four other pages: `/nexus`, `/evidence`, `/console` (via evidence), `/miracledrive`, `/sandbox-mirror`

**That's it.** No button anywhere performs code editing, file writes, or computer control. Those exist only as slash commands you'd have to already know to type (`/self-patch implement <id>`, `/ask-sov1 <goal>`) — no chip or UI element surfaces or hints at them except the propose-only `/self-patch` chip.

---

## 3. Hidden or Disconnected Capabilities

Of ~156 registered backend routes in `oracle_server.py`, roughly **85 (about half) are never called by anything in `ui/*.html`.** The largest disconnected block is a complete sandbox file-editing API — `/api/sandbox/write`, `/edit`, `/rename`, `/mkdir`, `/append`, `/trash`, `/read`, `/list` — fully implemented server-side, zero UI callers. Also unreachable from the UI: `/api/drive-search`, `/api/drive-read`, `/api/internet-recall/*`, `/api/quote-corpus/*`, `/api/document-atlas/*`, `/api/unified-oracle/*`, most of `/api/continuity/*`.

Two entire pages are built but orphaned — nothing in the UI links to them, they only work if you type the URL directly:
- `ui/jupiter_station.html` (`/jupiter`) — the quest-log feature from a prior autopilot session
- `ui/phone.html` (`/phone`, `/mobile`)

`config.yaml`'s cloud-model declaration (§1) is functionally dead — set but never read by the live server.

`core/safe_git.py` calls itself "the only way this runtime should ever invoke git" in its own docstring. **It is imported by zero other files in the repository.** Verified directly — it's not called from anywhere, including itself being run standalone.

---

## 4. Broken Capabilities

Nothing crashed outright in static inspection, but several things are built to *look* like they work while doing nothing:

- **Supersession (fact-correction):** the schema and read-path fully support marking an old fact superseded by a newer one, and retrieval correctly filters superseded facts out *if any existed*. But `mark_superseded()` (`core/memory.py:527`) has exactly one caller in the entire repository — `tests/test_memory_index.py:65`. Verified directly with a repo-wide grep. **No production code path has ever called it.** The correction mechanism is schema and a unit test, not a working feature.
- **Self-patch "implementation":** `implement()` explicitly does not write code. Its own comment: *"The LLM solution is implementation guidance, not a literal file replacement... actual code edits require Noah to review"* (`self_patch_pipeline.py:393-396`). It writes a markdown note and smoke-tests the **unmodified** file. If you've ever asked ORACLE to "fix" something via self-patch and believed the fix landed, it didn't.
- **`/ask-sov1` desktop dispatch:** explicitly returns `execution_completed: False` with the comment *"No SOV1 execution worker consumed it in this handoff"* (`desktop_ai_bridge.py:587-607`).

---

## 5. External-AI Dependencies

**As currently configured (`.env: LOCAL_MODE=true`), an ordinary chat message never leaves the machine.** Traced end to end: `POST /chat` → `_stream_reply` → `web_engine_response` (`core/oracle.py:1541`) → `direct_response` (`core/conversation_mode.py:442`) → an OpenAI-SDK-shaped client call pointed at `http://localhost:11434/v1` (Ollama), model `qwen2.5:7b`. No Anthropic/OpenAI/Google network call occurs in this path. If Ollama is unreachable, the code returns a canned local error string (`fallback_response()`, `core/conversation_mode.py:334`) — it does **not** fail over to Claude, even though a live Anthropic key sits right there in `.env`.

Anthropic *is* wired (`core/llm.py:149`) and would activate if `LOCAL_MODE=false`. Nothing else — no Gemini, Grok, or Codex network call exists anywhere in `core/*.py`. Mentions of those names elsewhere are just string labels for import-source classification, not live integrations.

The one place another AI genuinely gets consulted automatically (no manual Noah step) is `core/claude_code_bridge.py:ask_claude()`, which shells out to the local `claude` CLI. It's gated behind explicit "builder" trigger phrases ("ask claude," "write code," "commit") and is **not reachable from the default chat endpoint at all** — only from the separate `core/oracle.py` terminal REPL, which is not the interface you use.

Every other "AI bridge" module (`bridge.py`, `chatgpt_bridge.py`, `oracle_claude_channel.py`, `oracle_codex_channel.py`, `oracle_codex_watcher.py`, `desktop_ai_bridge.py`) either requires you to already have that AI's app/tab open, requires your explicit confirmation before any action, or is a passive file-drop channel that does nothing without a human or another process polling it.

**Bottom line: today, ORACLE's actual intelligence for ordinary conversation is 100% a local 7B Ollama model.** The "she secretly leans on Claude" worry is not what's happening — if anything, the opposite: she's currently *less* capable than Claude by design, because local mode is on and nothing routes around that.

---

## 6. Local Intelligence

Local model: `qwen2.5:7b` via Ollama, no pip client — raw HTTP against an OpenAI-compatible endpoint. Vision model configured (`qwen2.5vl:7b`) for the camera/see feature. There is no fine-tuning, no local training loop, no local embedding model. "Local intelligence" today means: one 7B open-weight chat model, plus deterministic Python logic around it (routing, memory read/write, provenance tagging). All actual language generation is that one model.

---

## 7. Memory

This is the section most in need of correction relative to how it's been described in the past.

**What an ordinary chat turn actually does:**
- **Reads:** the last 12 messages of the current session, always (`_noah_direct_history_block`, `core/memory.py:113-119`). Nothing else, unless your message contains a specific trigger word (things like "remember," "recall," "history," "who is"), in which case it also does a keyword/full-text search over `durable_facts`.
- **Writes:** the user message and the assistant reply get saved to the `messages` table. That's it, automatically, every turn.
- **Does NOT happen automatically:** fact extraction into `durable_facts`, provenance classification, and supersession all exist as real code (`core/continuity_pipeline.py`) but only run when you explicitly type `/remember` or clear a session. A normal conversation never triggers them.

So: ORACLE remembers the raw transcript of a session (as SQL rows), and can look things up if you use the right words. She does not, on her own, distill what you tell her into durable, retrievable facts unless you explicitly ask her to.

**No vector/semantic search exists anywhere in the live path.** All retrieval is SQL keyword/full-text search (FTS5). A frozen prototype (`rendered_reality/vector_db_DO_NOT_USE/`) is explicitly labeled in its own README as a stub returning fake similarity scores — "do not call anything here semantic search."

**Provenance is real but narrower than it sounds.** `classify_source_type()` genuinely tags messages `human_stated`/`inferred`/`generated`/`observed`, and this genuinely affects both what gets auto-approved and retrieval ranking. But it only runs on the explicit-command path above, not per turn, and there's no distinct "external corpus" category — importers just reuse the same four labels and aren't called from the live server at all.

**Verdict per module:**
- `core/memory.py` — WORKING END TO END for session history; durable-fact side works but is keyword/command-gated, not automatic.
- `core/recall_orchestrator.py` — PARTIALLY IMPLEMENTED; fully wired but dormant unless a message trips its keyword gate.
- `core/continuity_pipeline.py` (fact extraction, supersession) — CODE EXISTS BUT NOT PROVEN in ordinary use; supersession specifically is DISCONNECTED FROM CURRENT RUNTIME.

---

## 8. Computer Access

`core/computer_control.py` has real, working `pyautogui`-backed mouse/keyboard/screenshot/window functions. Two gates control it: `ORACLE_HANDS_ON=1` env or `Memory/hands_on.flag` must be present to turn hands on at all, and `Memory/hands_off.flag` overrides everything as a kill switch. **`Memory/hands_off.flag` currently exists in your repo** — hands are off right now. Separately, and more importantly: even when that flag isn't there, **zero routes in `oracle_server.py` ever call the actual click/type functions** — the SOV1 chat commands only run a dry-run status check or stage a request, never dispatch it. There is no live path today, gate open or closed, where a chat message makes the mouse move.

---

## 9. File Access

This one is real. `file_recall.py` is wired directly into ordinary message parsing (`oracle_server.py:4573-4590`) — any unmatched chat message gets checked against a file-request pattern, and if it matches, ORACLE can search and read across the repo, `Documents`, `Desktop`, `Downloads`, and `G:\My Drive`, with a credential/secret-name blocklist. This is a genuinely working, chat-triggered capability, not aspirational.

Writes are real but sandboxed hard: `sandbox_files.py` confines every write to `<repo>/sandbox/`, with path-escape checks that raise on any attempt to leave it. **Verdict: file READ is WORKING END TO END and reachable from ordinary chat. File WRITE is WORKING but confined to a sandbox directory — she cannot write anywhere else on the machine from chat.**

`core/context_loader.py` and `tools/extract_documents_corpus.py` exist but are not imported anywhere in `oracle_server.py` — disconnected from the live server, CLI-only.

---

## 10. Coding Capability

Covered in detail in §3/§4. Short version: ORACLE can *draft* a proposed fix (`/self-patch`) and can *read* your code (file recall). She cannot apply a patch to her own or any other repository from chat — `implement()` deliberately refuses to write code and only produces a markdown note. `core/self_build.py` and `core/propose_build.py` are CLI-only, not reachable from the web chat. Nothing in the current live system lets a chat message actually change source code on disk.

---

## 11. Autonomy

The one thing that runs continuously without you is the self-prompt reflection loop, started in `oracle_server.py`'s lifespan (`asyncio.create_task`, not a subprocess). It's genuinely sandbox-confined: every write goes through `sandbox_self_prompt_write` (hard-confined to `sandbox/workbench/`), and its output can only be `skipped`/`quarantined`/`submitted` as a candidate — it never executes code, calls an external action, or promotes anything to canon. Checked the live state file directly: as of the last update it's active but its most recent candidate was `quarantined`, `content_written: false`.

**Multi-step autonomy in the sense of "ORACLE carries state between several tools to complete a task without you manually relaying it" — not found anywhere in the live chat path.** Everything that looks multi-step (self-patch, ask-sov1, desktop bridges) either stops at a draft/proposal stage or requires your explicit follow-up confirmation at each step.

---

## 12. Failure Points — why visible capability has stalled

Based on everything above, the mechanical reasons a month of work hasn't produced visible new capability:

1. **Half the backend has no front door.** ~85 of ~156 routes — including the entire sandbox file-editing API — exist and presumably work in isolation, but nothing in `ui/index.html` ever calls them. Building backend capability without wiring it to the interface you actually use produces exactly the experience you described: work happens, nothing changes for you.
2. **Four separate runtimes named ORACLE.** Time spent on `core/oracle.py`, `core/resident_runtime.py`, or the orphaned Tkinter GUI doesn't show up in the Chrome window at all, because they're different processes.
3. **Safety-conscious code paths that look complete but were deliberately built not to finish the job** — `/self-patch implement` and `/ask-sov1` both stop short of the actual action by design (draft-only, dry-run-only), which is defensible as a safety posture but means "I built self-patch" and "self-patch works" are two different claims that got merged somewhere along the way.
4. **Two entire built pages (`jupiter_station.html`, `phone.html`) with zero UI links to them.** Real, recent work (the Jupiter Station quest log came out of a prior autopilot session) that is invisible unless you already know the URL.
5. **Memory that writes a transcript but doesn't distill it automatically.** If the expectation was "she remembers what matters from our conversations," the honest current behavior is "she keeps a raw log and can search it if you use the right words" — a meaningfully smaller claim.

---

## 13. Dead Weight

Candidates for archiving rather than continued investment, based on zero live callers:
- `core/safe_git.py` — orphaned, zero importers anywhere.
- `oracle_desktop.py` (Tkinter GUI) — no current launcher references it.
- `config.yaml`'s `oracle.model` key — dead while `LOCAL_MODE=true`; either wire it up or remove it to stop it lying about what model is active.
- `rendered_reality/vector_db_DO_NOT_USE/` — already self-labeled as a stub; the filename says it all.
- `ui/jupiter_station.html`, `ui/phone.html` and their backend routes — either link them from the UI or accept they're not part of the live product right now.

This list is not exhaustive — it's what surfaced during this pass, not a full dead-code sweep.

---

## 14. Implemented One-Week Vertical Slice

The recommended slice has now been implemented in the working tree:

**The existing sandbox file-editing API is wired into the chat UI as an audited, confirmation-gated edit.** A `/sandbox-edit` request now goes: confined API read → visible original content and diff → explicit confirmation → SHA-guarded confined API edit → visible receipt → confined API re-read and hash/content verification. The chat route itself only proposes and cannot mutate the file. Tests cover the pre-confirmation unchanged state, the confirmed write, the verified re-read, and outside-boundary refusal.

This deliberately does not touch `/self-patch implement` (which would mean writing outside the sandbox to ORACLE's own source — a bigger, riskier decision that deserves its own conversation, not a side effect of this slice) or computer control (currently killed by your own `hands_off.flag`, which should stay your call to lift).

---

## 15. Acceptance Test

**Before:** to edit a file in the sandbox, you'd open Claude Code (or another editor) yourself — ORACLE's own chat window could read a sandbox file but had no confirmation-gated way to change one.

**After:** use the pencil control or type `/sandbox-edit workbench/notes.md | <complete proposed content>`. ORACLE reads the file through the existing API and shows the diff with the state **not written**. Only **Confirm sandbox write** calls the existing edit API; the same card then shows its receipt and verified re-read content.

**Verification:** automated tests perform the chat proposal, prove the file is still unchanged, submit the confirmed API edit with the read SHA, and re-read the file to match the post-operation SHA and content. A separate test proves an outside path is refused and untouched. The UI reports success only after that re-read matches.

---

## What This Audit Deliberately Did Not Do

- Did not start a live server (blocked on your approval — see note at top).
- Did not run a capability benchmark through the real interface (Phase 2 of your handoff) — that requires the live baseline above.
- Did not touch, rewrite, or judge `docs/oracle-current-state.md` (the July 30 Phase 1 assessment) — it's a separate, earlier document; this one is scoped to your handoff's specific 15-section request.
- Did not propose any architecture, rewrite, or new module. Everything above is either "this works," "this doesn't," or "this exists but isn't connected."
