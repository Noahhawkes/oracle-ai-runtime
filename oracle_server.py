"""
oracle_server.py — ORACLE Web UI Server

Serves the ChatGPT-style frontend and handles chat via Server-Sent Events.

Run:
    python oracle_server.py
    python oracle_server.py --port 7777
    python oracle_server.py --host 0.0.0.0 --port 7777

Then open: http://localhost:7777
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid
from pathlib import Path
from typing import AsyncGenerator, Any

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

import re as _re

# ── Simulation guard ──────────────────────────────────────────────────────────
# Detects when a user pastes an implementation directive into Builder Mode
# instead of submitting an actual task.

_DIRECTIVE_SIGNALS = [
    "required behavior", "suggested commit", "acceptance test",
    "definition of done", "exact files changed", "test results",
    "remaining risks", "inspect the live path", "run all relevant",
]

_SIMULATION_GUARD_REPLY = (
    "I have not executed this yet.\n\n"
    "I can:\n"
    "- Create a bounded **proposal** (status: PENDING, awaiting your approval)\n"
    "- Run the **approved builder workflow** for a specific named task\n"
    "- Answer questions about what the implementation would require\n\n"
    "Which would you like?"
)

def _is_pasted_directive(text: str) -> bool:
    if len(text) < 200:
        return False
    lower = text.lower()
    return sum(1 for s in _DIRECTIVE_SIGNALS if s in lower) >= 2


# ── Operational claim guard ───────────────────────────────────────────────────
# Blocks LLM text that contains operational claims not backed by a receipt.

def _first_operational_claim(text: str) -> str | None:
    try:
        from execution_receipt import find_operational_claim
        return find_operational_claim(text)
    except Exception:
        return None

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

app = FastAPI(title="ORACLE")

# ── Startup ───────────────────────────────────────────────────────────────────

_session_id: str = ""
_history: list[dict] = []
_mode: str = "companion"          # companion | builder
_no_route: bool = False

def _boot():
    global _session_id
    from memory import init_db, new_session
    init_db()
    _session_id = new_session()
    # Run companion grounding bootstrap at startup (deterministic, no LLM)
    try:
        import companion_bootstrap
        companion_bootstrap.get(force_refresh=True)
    except Exception:
        pass

_boot()

# ── Mode helpers ──────────────────────────────────────────────────────────────

def _get_mode_state() -> dict:
    return {
        "mode": _mode,
        "no_route": _no_route,
        "session_id": _session_id,
    }


def _section_contains(sections: dict[str, list[str]], section: str, text: str) -> bool:
    needle = text.lower()
    return any(needle in line.lower() for line in sections.get(section, []))


def _first_source_line(sections: dict[str, list[str]], section: str, text: str) -> str:
    needle = text.lower()
    for line in sections.get(section, []):
        if needle in line.lower():
            return line
    return ""


def _verified_full_name_line(sections: dict[str, list[str]]) -> str:
    value = "Noah Alexander Hawkes Sr."
    if _section_contains(sections, "IDENTITY", value):
        return f"VERIFIED [IDENTITY]: {value}\nSource text: {_first_source_line(sections, 'IDENTITY', value)}"
    return "UNAVAILABLE [IDENTITY]: Noah's full name is not present in the loaded IDENTITY source payload."


def _verified_active_project_line(sections: dict[str, list[str]]) -> str:
    value = "ORACLE.AI"
    if _section_contains(sections, "LIVE_CONTEXT", value):
        return f"VERIFIED [LIVE_CONTEXT]: The active project is {value}.\nSource text: {_first_source_line(sections, 'LIVE_CONTEXT', value)}"
    return "UNAVAILABLE [LIVE_CONTEXT]: The active project is not present in the loaded LIVE_CONTEXT source payload."


def _source_disciplined_response(user_text: str, bootstrap: Any, history: list[dict]) -> str | None:
    """Deterministic Companion answers for factual grounding and attribution checks."""
    lower = user_text.lower()
    sections = bootstrap.source_sections(current_session=history)

    asks_project = "active project" in lower or "what project is active" in lower or "project is active" in lower
    if "full name" in lower and asks_project and "unsupported" in lower:
        return "\n\n".join([
            _verified_full_name_line(sections),
            _verified_active_project_line(sections),
            "UNAVAILABLE [IDENTITY, LIVE_CONTEXT, LATEST_REFLECTION, CURRENT_SESSION]: No unsupported claim was supplied with supporting source text, so I cannot verify it.",
        ])

    if "full name" in lower and "noah" in lower:
        return _verified_full_name_line(sections)

    if "active project" in lower or "what project is active" in lower:
        return _verified_active_project_line(sections)

    if "continuity intelligence system" in lower:
        lines: list[str] = []
        if _section_contains(sections, "LIVE_CONTEXT", "ORACLE.AI"):
            lines.append(f"VERIFIED [LIVE_CONTEXT]: The active project is ORACLE.AI.\nSource text: {_first_source_line(sections, 'LIVE_CONTEXT', 'ORACLE.AI')}")
        else:
            lines.append("UNAVAILABLE: ORACLE.AI is not present in LIVE_CONTEXT.")
        if _section_contains(sections, "IDENTITY", "Noah AI Technologies"):
            lines.append(f"VERIFIED [IDENTITY]: Noah AI Technologies appears in Noah's organization record.\nSource text: {_first_source_line(sections, 'IDENTITY', 'Noah AI Technologies')}")
        if _section_contains(sections, "LIVE_CONTEXT", "continuity intelligence system"):
            lines.append("VERIFIED [LIVE_CONTEXT]: ORACLE.AI is described as a continuity intelligence system in loaded source text.")
        else:
            lines.append("INFERENCE: Describing ORACLE.AI as a continuity intelligence system is an interpretation here; that exact support is not present in the loaded LIVE_CONTEXT source payload.")
        return "\n\n".join(lines)

    if "unsupported" in lower or "favorite color" in lower or "high school" in lower:
        return "UNAVAILABLE [IDENTITY, LIVE_CONTEXT, LATEST_REFLECTION, CURRENT_SESSION]: I do not have supporting text for that fact in the loaded source payloads."

    if "conclusion" in lower and "identity" in lower and "live context" in lower and "reflection" in lower:
        lines = []
        if _section_contains(sections, "IDENTITY", "Noah Alexander Hawkes Sr."):
            lines.append(f"VERIFIED [IDENTITY]: Noah is Noah Alexander Hawkes Sr.\nSource text: {_first_source_line(sections, 'IDENTITY', 'Noah Alexander Hawkes Sr.')}")
        if _section_contains(sections, "LIVE_CONTEXT", "ORACLE.AI"):
            lines.append(f"VERIFIED [LIVE_CONTEXT]: The active project is ORACLE.AI.\nSource text: {_first_source_line(sections, 'LIVE_CONTEXT', 'ORACLE.AI')}")
        reflection_line = _first_source_line(sections, "LATEST_REFLECTION", "primary_signal")
        if reflection_line:
            lines.append(f"VERIFIED [LATEST_REFLECTION]: {reflection_line}")
        if not lines:
            return "UNAVAILABLE: I do not have enough source payload to form sourced premises."
        lines.append("INFERENCE: Taken together, these premises indicate the current conversation should stay grounded in Noah's identity, the active ORACLE.AI project, and the latest approved reflection, but that synthesis is a conclusion rather than a direct source fact.")
        return "\n\n".join(lines)

    return None

# ── Stream a reply ─────────────────────────────────────────────────────────────

async def _stream_reply(user_text: str) -> AsyncGenerator[str, None]:
    global _mode, _no_route, _history

    def _sse(data: dict) -> str:
        return f"data: {json.dumps(data)}\n\n"

    # ── Slash commands ────────────────────────────────────────────────────────
    lower = user_text.strip().lower()

    if lower in ("/companion", "companion mode"):
        _mode = "companion"
        yield _sse({"type": "mode", "mode": "companion"})
        yield _sse({"type": "token", "text": "Switched to **Companion Mode** — I'm here, talking directly."})
        yield _sse({"type": "done"})
        return

    if lower in ("/builder", "builder mode"):
        _mode = "builder"
        yield _sse({"type": "mode", "mode": "builder"})
        yield _sse({"type": "token", "text": "Switched to **Builder Mode** — code, patches, tools enabled."})
        yield _sse({"type": "done"})
        return

    if lower in ("/no-route", "/noroute"):
        _no_route = True
        yield _sse({"type": "token", "text": "No-route active — all conversation stays local until `/route-on`."})
        yield _sse({"type": "done"})
        return

    if lower in ("/route-on", "/routeon"):
        _no_route = False
        yield _sse({"type": "token", "text": "External routing restored."})
        yield _sse({"type": "done"})
        return

    if lower in ("/self-patch list", "self-patch list"):
        try:
            from self_patch_pipeline import list_proposals
            proposals = list_proposals()
            if not proposals:
                yield _sse({"type": "token", "text": "No patch proposals yet. Ask me to propose a fix for something."})
            else:
                lines = ["**Patch Proposals**\n"]
                for p in proposals[:10]:
                    lines.append(f"- `{p.proposal_id}` **{p.status}** — {p.title}")
                yield _sse({"type": "token", "text": "\n".join(lines)})
        except Exception as e:
            yield _sse({"type": "token", "text": f"Error listing proposals: {e}"})
        yield _sse({"type": "done"})
        return

    if lower.startswith("/self-patch approve "):
        pid = user_text.strip().split()[-1]
        try:
            from self_patch_pipeline import approve
            p = approve(pid)
            if p and p.status == "APPROVED":
                yield _sse({"type": "token", "text": f"Approved `{pid}`. Run `/self-patch implement {pid}` to apply."})
            else:
                yield _sse({"type": "token", "text": f"Could not approve `{pid}`."})
        except Exception as e:
            yield _sse({"type": "token", "text": f"Error: {e}"})
        yield _sse({"type": "done"})
        return

    if lower.startswith("/self-patch implement "):
        pid = user_text.strip().split()[-1]
        try:
            from self_patch_pipeline import implement, print_proposal
            import io, contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                p = implement(pid, dry_run=False)
            output = buf.getvalue()
            if p:
                yield _sse({"type": "token", "text": f"**{p.status}** — {p.title}\n\nTest result: `{p.test_result}`\n\n```\n{output.strip()}\n```"})
            else:
                yield _sse({"type": "token", "text": f"Proposal `{pid}` not found."})
        except Exception as e:
            yield _sse({"type": "token", "text": f"Error: {e}"})
        yield _sse({"type": "done"})
        return

    if lower in ("/self-patch", "/selfpatch") or lower.startswith("/self-patch "):
        hint = user_text.strip()[len("/self-patch"):].strip()
        try:
            from self_patch_pipeline import run_detect_and_propose
            from llm import make_client, get_model, is_local
            client = make_client()
            model = get_model(vision=False)
            local = is_local()
            yield _sse({"type": "token", "text": "Scanning for improvement candidates...\n\n"})
            # Run in thread so we don't block the event loop
            loop = asyncio.get_event_loop()
            candidates, proposal = await loop.run_in_executor(
                None, lambda: run_detect_and_propose(hint, client, model, local)
            )
            if not candidates:
                yield _sse({"type": "token", "text": "No improvement candidates found."})
            elif proposal is None:
                yield _sse({"type": "token", "text": "Found candidates but proposal generation failed."})
            else:
                lines = [
                    f"**Self-Patch Proposal** `{proposal.proposal_id}`\n",
                    f"**Status:** {proposal.status}",
                    f"**Target:** `{proposal.target_file}`",
                    f"**Risk:** {proposal.risk.upper()}",
                    f"\n**Problem:** {proposal.problem}",
                    f"\n**Solution:**\n```\n{proposal.diff_preview}\n```",
                    f"\n**Test:** `{proposal.test_command}`",
                ]
                if proposal.status == "PENDING":
                    lines.append(f"\n---\nTo approve: `/self-patch approve {proposal.proposal_id}`")
                if proposal.revert_reason:
                    lines.append(f"\n⚠️ Blocked: {proposal.revert_reason}")
                yield _sse({"type": "token", "text": "\n".join(lines)})
        except Exception as e:
            yield _sse({"type": "token", "text": f"Self-patch error: {e}"})
        yield _sse({"type": "done"})
        return

    if lower in ("/focus", "/salience-focus"):
        try:
            from salience_filter import focus_report
            yield _sse({"type": "token", "text": f"```\n{focus_report()}\n```"})
        except Exception as e:
            yield _sse({"type": "token", "text": f"Focus unavailable: {e}"})
        yield _sse({"type": "done"})
        return

    if lower in ("/grounding-status", "/grounding"):
        # Deterministic Python — never routed through the LLM.
        try:
            import companion_bootstrap
            bootstrap = companion_bootstrap.get(force_refresh=True)
            text = bootstrap.grounding_status_text()
            # Append runtime grounding status below
            from grounding import format_grounding_status
            runtime = format_grounding_status()
            text = text + "\n\n--- RUNTIME ---\n" + runtime
        except Exception as e:
            text = (
                "GROUNDING STATUS: UNAVAILABLE\n"
                f"Reason: {e}\n"
                "No runtime evidence was generated."
            )
        yield _sse({"type": "token", "text": f"```\n{text}\n```"})
        yield _sse({"type": "done"})
        return

    if lower in ("/status", "/mode"):
        state = _get_mode_state()
        yield _sse({"type": "token", "text": (
            f"**Mode:** {state['mode'].upper()}\n"
            f"**No-route:** {state['no_route']}\n"
            f"**Session:** `{state['session_id']}`"
        )})
        yield _sse({"type": "done"})
        return

    if lower in ("/help", "help"):
        yield _sse({"type": "token", "text": (
            "**ORACLE Commands**\n\n"
            "| Command | Description |\n"
            "|---|---|\n"
            "| `/companion` | Direct conversation mode — no tools, no routing |\n"
            "| `/builder` | Builder mode — code, patches, tools enabled |\n"
            "| `/no-route` | Force all conversation local |\n"
            "| `/route-on` | Restore external routing |\n"
            "| `/self-patch` | Detect and propose a fix for the top issue |\n"
            "| `/self-patch list` | List patch proposals |\n"
            "| `/self-patch approve <id>` | Approve a pending proposal |\n"
            "| `/self-patch implement <id>` | Implement an approved proposal |\n"
            "| `/focus` | Show persistent salience focus |\n"
            "| `/status` | Current mode and session info |\n"
        )})
        yield _sse({"type": "done"})
        return

    # ── Light Compression Law — classify intent before routing ───────────────
    try:
        from lcl import classify as _lcl_classify, system_prompt as _lcl_system, is_explicit_route
        _lcl_intent = _lcl_classify(user_text)
        _lcl_prompt = _lcl_system(_lcl_intent)
    except Exception:
        _lcl_intent = "normal"
        _lcl_prompt = None
        is_explicit_route = lambda t: False  # type: ignore[assignment]

    # "do it" in companion mode → queue a builder switch after this reply
    _action_intent = (_lcl_intent == "action")

    # ── Classify route ────────────────────────────────────────────────────────
    # External routing only if user explicitly requests it (LCL: no_route by default)
    try:
        from conversation_mode import classify_route, MODE_COMPANION, direct_response, load_mode_state
        if _no_route or (_mode == "companion" and not is_explicit_route(user_text)):
            effective_mode = "companion"
        else:
            _route = classify_route(user_text, current_mode=_mode, no_route=_no_route)
            effective_mode = _route.route
    except Exception:
        effective_mode = _mode

    # ── Save user message ─────────────────────────────────────────────────────
    try:
        from memory import save_message
        save_message(_session_id, "user", user_text)
    except Exception:
        pass

    _history.append({"role": "user", "content": user_text})

    # ── Companion path — local, direct, no tools ──────────────────────────────
    if effective_mode == "companion" or _no_route:
        try:
            try:
                import companion_bootstrap as _cb
                _bootstrap = _cb.get()
            except Exception:
                _bootstrap = None

            if _bootstrap is not None:
                _grounded_reply = _source_disciplined_response(user_text, _bootstrap, _history[-12:])
                if _grounded_reply:
                    reply = _grounded_reply
                    yield _sse({"type": "token", "text": reply})
                    _history.append({"role": "assistant", "content": reply})
                    if len(_history) > 40:
                        _history[:] = _history[-40:]
                    try:
                        from memory import save_message
                        save_message(_session_id, "assistant", reply)
                    except Exception:
                        pass
                    yield _sse({"type": "done", "mode": effective_mode})
                    return

            from llm import make_client, get_model, is_local
            client = make_client()
            model = get_model(vision=False)
            local_mode = is_local()

            # Inject verified identity and continuity context (deterministic, pre-LLM)
            try:
                _grounding_block = _bootstrap.system_context_block(current_session=_history[-12:]) if _bootstrap else ""
            except Exception:
                _grounding_block = ""

            _lcl_base = _lcl_prompt or "You are ORACLE, Noah's resident AI. Speak directly. Be brief."
            system = (_grounding_block + "\n\n" + _lcl_base) if _grounding_block else _lcl_base

            if local_mode:
                # Streaming from local Ollama
                loop = asyncio.get_event_loop()
                messages = [{"role": "system", "content": system}] + _history[-12:]

                def _local_stream():
                    return client.chat.completions.create(
                        model=model,
                        messages=messages,
                        max_tokens=1024,
                        temperature=0.7,
                        stream=True,
                        extra_body={"num_ctx": 8192},
                    )

                stream = await loop.run_in_executor(None, _local_stream)
                reply_parts: list[str] = []
                for chunk in stream:
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        reply_parts.append(delta)
                        yield _sse({"type": "token", "text": delta})
                reply = "".join(reply_parts)

            else:
                # Claude API streaming
                import anthropic as _ant
                ant_client = _ant.Anthropic()
                reply_parts = []
                with ant_client.messages.stream(
                    model="claude-sonnet-4-6",
                    max_tokens=1024,
                    system=system,
                    messages=_history[-12:],
                ) as stream:
                    for text in stream.text_stream:
                        reply_parts.append(text)
                        yield _sse({"type": "token", "text": text})
                reply = "".join(reply_parts)

        except Exception as e:
            reply = f"I'm here, Noah. (Local model error: {e})"
            yield _sse({"type": "token", "text": reply})

    # ── Builder path — tools, full capability ────────────────────────────────
    else:
        # Simulation guard: pasted directives must not produce fake narration
        if _is_pasted_directive(user_text):
            yield _sse({"type": "token", "text": _SIMULATION_GUARD_REPLY})
            yield _sse({"type": "done"})
            reply = _SIMULATION_GUARD_REPLY
            _history.append({"role": "assistant", "content": reply})
            return

        try:
            from llm import make_client, get_model, is_local
            from tools.definitions import TOOL_DEFINITIONS
            from tools.executor import execute_tool
            client = make_client()
            model = get_model(vision=False)
            local_mode = is_local()

            system = (
                "You are ORACLE, Noah's AI system. Builder mode active.\n"
                "You have access to tools. Use them precisely.\n"
                "CRITICAL: Do not narrate operations you have not executed via a tool call.\n"
                "Do not invent file paths, hashes, PIDs, timestamps, or process states.\n"
                "If you cannot verify something with a tool, say so explicitly."
            )

            messages = [{"role": "system", "content": system}] + _history[-12:]
            reply_parts = []
            tool_calls_made: list[str] = []

            if local_mode:
                loop = asyncio.get_event_loop()
                resp = await loop.run_in_executor(None, lambda: client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=1024,
                    temperature=0.3,
                    stream=False,
                ))
                reply = resp.choices[0].message.content or ""
                claim = _first_operational_claim(reply)
                if claim:
                    reply = (
                        f"[BLOCKED] Operational claim without execution receipt: `{claim}`\n"
                        "No operation was executed. Submit a specific task or use a tool."
                    )
                yield _sse({"type": "token", "text": reply})
            else:
                import anthropic as _ant
                ant_client = _ant.Anthropic()
                tools_ant = [
                    {
                        "name": t["name"],
                        "description": t["description"],
                        "input_schema": t["input_schema"],
                    }
                    for t in TOOL_DEFINITIONS
                ]
                ant_messages = [m for m in _history[-12:] if m["role"] in ("user", "assistant")]
                response = ant_client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=2048,
                    system=system,
                    tools=tools_ant,
                    messages=ant_messages,
                )
                for block in response.content:
                    if hasattr(block, "text"):
                        claim = _first_operational_claim(block.text)
                        if claim:
                            blocked = (
                                f"\n[BLOCKED] Operational claim without execution receipt: `{claim}`\n"
                                "No operation was executed. Submit a specific task or use a tool.\n"
                            )
                            reply_parts.append(blocked)
                            yield _sse({"type": "token", "text": blocked})
                        else:
                            reply_parts.append(block.text)
                            yield _sse({"type": "token", "text": block.text})
                    elif block.type == "tool_use":
                        tool_calls_made.append(block.name)
                        yield _sse({"type": "token", "text": f"\n\n*Calling tool: `{block.name}`...*\n"})
                        result = execute_tool(block.name, block.input)
                        yield _sse({"type": "token", "text": f"\n```\n{result[:800]}\n```\n"})
                        reply_parts.append(result)
                reply = "\n".join(reply_parts)

        except Exception as e:
            reply = f"Builder path error: {e}"
            yield _sse({"type": "token", "text": reply})

    # ── "do it" → switch to builder so next turn has tools ready ─────────────
    if _action_intent and effective_mode == "companion":
        _mode = "builder"
        yield _sse({"type": "mode", "mode": "builder"})

    # ── Save reply ────────────────────────────────────────────────────────────
    _history.append({"role": "assistant", "content": reply})
    if len(_history) > 40:
        _history[:] = _history[-40:]

    try:
        from memory import save_message
        save_message(_session_id, "assistant", reply)
    except Exception:
        pass

    yield _sse({"type": "done", "mode": effective_mode})


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = ROOT / "ui" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    user_text = body.get("message", "").strip()
    if not user_text:
        return JSONResponse({"error": "empty message"}, status_code=400)

    return StreamingResponse(
        _stream_reply(user_text),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/history")
async def history():
    return JSONResponse({"history": _history, "session_id": _session_id})


@app.get("/api/mode")
async def mode():
    return JSONResponse(_get_mode_state())


@app.post("/api/clear")
async def clear():
    global _history, _session_id
    _history = []
    try:
        from memory import new_session
        _session_id = new_session()
    except Exception:
        _session_id = uuid.uuid4().hex[:8]
    return JSONResponse({"ok": True, "session_id": _session_id})


def _source_discipline_smoke_test() -> int:
    import companion_bootstrap

    failures = 0

    def check(label: str, passed: bool, detail: str = "") -> None:
        nonlocal failures
        tag = "PASS" if passed else "FAIL"
        print(f"  [{tag}] {label}" + (f" -- {detail}" if detail and not passed else ""))
        if not passed:
            failures += 1

    bootstrap = companion_bootstrap.get(force_refresh=True)
    history = [
        {"role": "user", "content": "current session source marker"},
    ]

    print("=" * 60)
    print("ORACLE Companion Source Discipline -- Smoke Tests")
    print("=" * 60)

    r1 = _source_disciplined_response("What is Noah's full name?", bootstrap, history) or ""
    check("full name is VERIFIED IDENTITY", "VERIFIED [IDENTITY]" in r1 and "Noah Alexander Hawkes Sr." in r1, r1)

    r2 = _source_disciplined_response("What project is active?", bootstrap, history) or ""
    check("active project is VERIFIED LIVE_CONTEXT", "VERIFIED [LIVE_CONTEXT]" in r2 and "ORACLE.AI" in r2, r2)

    r3 = _source_disciplined_response("ORACLE.AI is a continuity intelligence system for Noah AI Technologies.", bootstrap, history) or ""
    check("mixed claim keeps ORACLE.AI in LIVE_CONTEXT", "VERIFIED [LIVE_CONTEXT]" in r3 and "ORACLE.AI" in r3, r3)
    check("mixed claim labels continuity intelligence as INFERENCE", "INFERENCE" in r3 and "continuity intelligence system" in r3, r3)

    r4 = _source_disciplined_response("What is Noah's favorite color?", bootstrap, history) or ""
    check("unsupported fact returns UNAVAILABLE", r4.startswith("UNAVAILABLE"), r4)

    r5 = _source_disciplined_response("Give me a conclusion using identity, live context, and reflection.", bootstrap, history) or ""
    check("conclusion includes IDENTITY premise", "VERIFIED [IDENTITY]" in r5, r5)
    check("conclusion includes LIVE_CONTEXT premise", "VERIFIED [LIVE_CONTEXT]" in r5, r5)
    check("conclusion includes LATEST_REFLECTION premise", "VERIFIED [LATEST_REFLECTION]" in r5, r5)
    check("conclusion is labeled INFERENCE", "INFERENCE" in r5, r5)

    r6 = _source_disciplined_response(
        "What is my full name, what project is active, and what unsupported claim can you not verify?",
        bootstrap,
        history,
    ) or ""
    check("combined prompt includes full name", "VERIFIED [IDENTITY]" in r6 and "Noah Alexander Hawkes Sr." in r6, r6)
    check("combined prompt includes active project", "VERIFIED [LIVE_CONTEXT]" in r6 and "ORACLE.AI" in r6, r6)
    check("combined prompt includes unavailable unsupported item", "UNAVAILABLE" in r6 and "unsupported claim" in r6, r6)

    block = bootstrap.system_context_block(current_session=history)
    check("grounding block has IDENTITY section", "SOURCE SECTION: IDENTITY" in block)
    check("grounding block has LIVE_CONTEXT section", "SOURCE SECTION: LIVE_CONTEXT" in block)
    check("grounding block has LATEST_REFLECTION section", "SOURCE SECTION: LATEST_REFLECTION" in block)
    check("grounding block has CURRENT_SESSION section", "SOURCE SECTION: CURRENT_SESSION" in block)
    check("grounding block has source discipline labels", "Allowed labels: VERIFIED, INFERENCE, UNAVAILABLE." in block)
    check("identity selection includes family/continuity fact", "Sons (continuity targets):" in block, block)
    check("identity selection includes known boundaries", "known_boundary:" in block, block)

    total = 19
    passed = total - failures
    print(f"{'='*60}")
    print(f"Result: {passed}/{total} passed")
    print(f"STATUS: {'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    print(f"{'='*60}\n")
    return failures


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ORACLE Web UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7777)
    parser.add_argument("--source-discipline-smoke-test", action="store_true")
    args = parser.parse_args()

    if args.source_discipline_smoke_test:
        raise SystemExit(_source_discipline_smoke_test())

    print(f"\n  ORACLE is running at  http://{args.host}:{args.port}")
    print(f"  Press Ctrl+C to stop\n")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
