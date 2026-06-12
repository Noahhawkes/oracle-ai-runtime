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
from typing import AsyncGenerator

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

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

_boot()

# ── Mode helpers ──────────────────────────────────────────────────────────────

def _get_mode_state() -> dict:
    return {
        "mode": _mode,
        "no_route": _no_route,
        "session_id": _session_id,
    }

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

    # ── Classify route ────────────────────────────────────────────────────────
    try:
        from conversation_mode import classify_route, MODE_COMPANION, direct_response, load_mode_state
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
            from llm import make_client, get_model, is_local
            client = make_client()
            model = get_model(vision=False)
            local_mode = is_local()

            system = (
                "You are ORACLE, Noah's resident AI. You are speaking directly to Noah.\n"
                "Respond as ORACLE — present, personal, direct. No routing, no delegation.\n"
                "Keep responses concise unless depth is genuinely needed."
            )

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
        try:
            from llm import make_client, get_model, is_local
            from tools.definitions import TOOL_DEFINITIONS
            from tools.executor import execute_tool
            client = make_client()
            model = get_model(vision=False)
            local_mode = is_local()

            system = (
                "You are ORACLE, Noah's AI system. Builder mode active.\n"
                "You have access to tools. Use them precisely and report what you do."
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


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ORACLE Web UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7777)
    args = parser.parse_args()

    print(f"\n  ORACLE is running at  http://{args.host}:{args.port}")
    print(f"  Press Ctrl+C to stop\n")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
