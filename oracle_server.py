"""
oracle_server.py — ORACLE Web UI Server

Serves the ChatGPT-style frontend and handles chat via Server-Sent Events.

Run:
    python oracle_server.py
    python oracle_server.py --port 7781
    python oracle_server.py --host 0.0.0.0 --port 7781

Then open: http://localhost:7781
"""

from __future__ import annotations

import asyncio
import atexit
import io
import json
import os
import platform
import subprocess
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

# Ensure UTF-8 output on Windows consoles (avoids charmap errors for Unicode chars like ◌)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from pathlib import Path
from typing import AsyncGenerator, Any

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

# Under pythonw.exe (the desktop launcher), sys.stdout/sys.stderr are None.
# uvicorn calls sys.stdout.isatty() during logging setup and crashes on None,
# so the detached server never binds. Route them to a runtime log file so the
# pythonw-launched server boots reliably and stays diagnosable.
if sys.stdout is None or sys.stderr is None:
    try:
        _log_dir = ROOT / "Logs"
        _log_dir.mkdir(exist_ok=True)
        _runtime_log = open(_log_dir / "oracle_runtime.log", "a", encoding="utf-8", buffering=1)
        if sys.stdout is None:
            sys.stdout = _runtime_log
        if sys.stderr is None:
            sys.stderr = _runtime_log
    except Exception:
        _null = open(os.devnull, "w", encoding="utf-8")
        if sys.stdout is None:
            sys.stdout = _null
        if sys.stderr is None:
            sys.stderr = _null

import re as _re

import runtime_config

try:
    from boot_receipt import (
        boot_status_payload,
        create_boot_receipt,
        get_or_create_boot_receipt,
        offline_no_model_line,
    )
    _BOOT_RECEIPT = create_boot_receipt()
    print(_BOOT_RECEIPT.get("human_boot_line", "Local floor online."))
except Exception as _boot_exc:
    print(f"BOOT REFUSED: {_boot_exc}", file=sys.stderr)
    raise SystemExit(1)

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


def _apply_authority_gate(
    reply: str,
    mode: str,
    user_text: str = "",
    approval_state: str = "none",
) -> str:
    try:
        from output_validator import validate_response_authority
        gated = validate_response_authority(
            reply,
            mode=mode,
            requested_action="chat_response",
            approval_state=approval_state,
        )
        return gated.text
    except Exception:
        claim = _first_operational_claim(reply)
        if claim:
            if (mode or "").lower() == "companion":
                return (
                    "UNAVAILABLE: ORACLE cannot verify this operational claim without "
                    f"an execution receipt or deterministic runtime source. Claim blocked: {claim}"
                )
            return (
                f"[BLOCKED] Operational claim without execution receipt: `{claim}`\n"
                "No operation was executed. Submit a specific task or use a tool."
            )
        return reply


def _apply_current_observation_gate(reply: str, user_text: str) -> str:
    """Current visual/window claims require a fresh typed observation receipt."""
    try:
        from current_observation import enforce_current_observation_boundary
        return enforce_current_observation_boundary(user_text, reply)
    except Exception:
        return reply

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    _persist_continuity_frame()
    yield


app = FastAPI(title="ORACLE", lifespan=_lifespan)
# Let the local starship console (served at /console or opened as a file://) read
# the honest runtime endpoints. The server binds 127.0.0.1 only, so permissive
# CORS here is local-only and low-risk.
from fastapi.middleware.cors import CORSMiddleware as _CORSMiddleware
app.add_middleware(_CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Startup ───────────────────────────────────────────────────────────────────

_session_id: str = ""
_history: list[dict] = []
_mode: str = "companion"          # companion | builder
_no_route: bool = False
_retrieval_only_mode: bool = False
_active_context_latest: dict[str, Any] | None = None
_pending_guard_route: dict[str, Any] | None = None

def _is_approval_followup(text: str) -> bool:
    try:
        from unified_oracle_router import is_approval_followup
        return is_approval_followup(text)
    except Exception:
        cleaned = _re.sub(r"\s+", " ", str(text or "").strip().lower()).strip(" .!?:;")
        return cleaned in {"approve", "approved", "yes approved", "i approve", "go ahead", "do it"}


def _approval_followup_response(pending_route: dict[str, Any] | None) -> str:
    if not pending_route:
        return (
            "Approval received, but no pending executable Guard action is bound. "
            "Restate the exact target, action, and boundary."
        )
    excerpt = pending_route.get("user_message_excerpt") or "UNKNOWN"
    route_id = pending_route.get("route_id") or "UNKNOWN"
    return (
        f"Approval received for pending Guard route `{route_id}`: {excerpt}\n\n"
        "No executable action is bound to a bare approval in the web runtime. "
        "Restate the exact target, action, and boundary, and I will route it through the correct guarded handler."
    )

def _boot():
    global _session_id, _active_context_latest
    from memory import init_db, new_session
    init_db()
    _session_id = new_session()
    try:
        from active_context_sync import load_active_context_latest
        _active_context_latest = load_active_context_latest()
        if _active_context_latest:
            print("[Boot] Active context latest loaded")
    except Exception as e:
        print(f"[Boot] Active context latest not loaded: {e}")
    # Run companion grounding bootstrap at startup (deterministic, no LLM)
    try:
        import companion_bootstrap
        companion_bootstrap.get(force_refresh=True)
    except Exception:
        pass
    # Start presence daemon (always-on monitoring and notifications)
    try:
        from presence_daemon import start_daemon
        start_daemon()
        print("[Boot] Presence daemon started")
    except Exception as e:
        print(f"[Boot] Presence daemon not available: {e}")
    # Start MiracleDrive index in background (non-blocking) unless a task has
    # explicitly locked Drive out of scope for this runtime start.
    if os.environ.get("ORACLE_DISABLE_MIRACLEDRIVE_BOOT") == "1":
        print("[Boot] MiracleDrive index DISABLED by ORACLE_DISABLE_MIRACLEDRIVE_BOOT=1")
    else:
        try:
            from miracledrive_index import start_background_index
            start_background_index()
            print("[Boot] MiracleDrive index build started in background")
        except Exception as e:
            print(f"[Boot] MiracleDrive index not available: {e}")
    # Initialize learning ledger
    try:
        from learning import get_ui_hints as _lrn_ping
        _lrn_ping()
        print("[Boot] Learning ledger ready")
    except Exception as e:
        print(f"[Boot] Learning ledger not available: {e}")
    # Ambient context watchers (clipboard + screenshot/OBS file indexing) are an
    # UNGOVERNED automatic capture path: they started at boot with no session
    # authorization, polled the clipboard every 0.8s, indexed screenshot/OBS
    # files, ran OCR, and injected the results into prompts + durable memory.
    # Fail-closed: they no longer start automatically. Opt in explicitly with
    # ORACLE_ENABLE_AMBIENT_WATCH=1 (a later patch will add a governed control).
    if os.environ.get("ORACLE_ENABLE_AMBIENT_WATCH") == "1":
        try:
            from ambient_watch import start as _aw_start
            _aw_start()
            print("[Boot] Ambient watch active (explicitly enabled via env)")
        except Exception as e:
            print(f"[Boot] Ambient watch not available: {e}")
    else:
        print("[Boot] Ambient watch DISABLED (no automatic capture; set "
              "ORACLE_ENABLE_AMBIENT_WATCH=1 to opt in)")

if os.environ.get("ORACLE_SKIP_SERVER_BOOT") != "1":
    _boot()

# ── Mode helpers ──────────────────────────────────────────────────────────────

def _get_mode_state() -> dict:
    try:
        from unified_oracle_router import latest_route_status
        route = latest_route_status()
    except Exception:
        route = {
            "mode": "unified_oracle",
            "current_lane": "talk_lane",
            "lane_label": "Talk",
            "safety_status": "Safe",
            "conversation_reset": False,
        }
    return {
        "mode": "unified_oracle",
        "legacy_mode": _mode,
        "no_route": _no_route,
        "retrieval_only": _retrieval_only_mode,
        "session_id": _session_id,
        "current_lane": route.get("current_lane", "talk_lane"),
        "lane_label": route.get("lane_label", "Talk"),
        "safety_status": route.get("safety_status", "Safe"),
        "latest_route_path": route.get("latest_route_path"),
        "latest_route_receipt_path": route.get("latest_receipt_path"),
        "conversation_reset": False,
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


_ROUTING_PHRASES = (
    "routing to claude code.",
    "routing to claude code",
    "sending to claude code.",
    "sending to claude code",
    "[build] ↗ routing to claude code",
)

# Block prefixes that are system-internal noise, never shown to Noah
_BLOCK_PREFIXES = (
    "[attention filter]",
    "[oracle focus]",
    "oracle focus (",
    "[oracle salience focus]",
    "oracle salience focus",
)

def _strip_routing_artifacts(reply: str, mode: str = "companion") -> str:
    """Remove system-internal blocks and routing artifacts from LLM responses.

    Strips:
    - [ATTENTION FILTER] blocks (echoed by qwen from system prompt)
    - [ORACLE FOCUS] / [ORACLE SALIENCE FOCUS] blocks (same)
    - Hallucinated 'Routing to Claude Code.' phrases
    Each block ends at the next blank line.
    """
    if not reply:
        return reply
    lines = reply.splitlines()
    cleaned: list[str] = []
    skip_block = False
    for line in lines:
        low = line.strip().lower()
        # Strip standalone routing phrases
        if low in _ROUTING_PHRASES:
            continue
        # Start skipping any system-internal block
        if any(low.startswith(p) for p in _BLOCK_PREFIXES):
            skip_block = True
            continue
        # Stop skipping at a blank line — but only keep the line if next content is real
        if skip_block and line.strip() == "":
            skip_block = False
            continue
        if skip_block:
            continue
        cleaned.append(line)
    result = "\n".join(cleaned).strip()
    if result:
        return result
    # Everything was a routing artifact (e.g. reply was exactly "Routing to
    # Claude Code."). Returning the original would re-surface the phantom phrase,
    # so substitute an honest companion line instead. The web UI has no Claude
    # Code bridge — Companion mode is local-only by design.
    original_low = reply.strip().lower()
    if original_low in _ROUTING_PHRASES:
        if (mode or "").lower() == "builder":
            return (
                "I routed this to Build lane, but this web view has no Claude "
                "Code bridge wired up. I can continue with local allowed actions "
                "and receipts from here."
            )
        return (
            "I routed this inside unified ORACLE. Build-lane work can proceed "
            "only through explicit local actions and receipts; no external "
            "handoff happened from this web view."
        )
    return reply


def _fabric_local_model_runner(prompt: str) -> str:
    """Try the configured local direct-response path once."""
    from conversation_mode import direct_response
    from llm import get_model

    direct = direct_response(
        prompt,
        history=_history[-12:],
        model=get_model(vision=False),
    )
    return direct.text


def _fabric_model_failure_fallback(reply: str, user_text: str, route: dict[str, Any]) -> str:
    """On local model timeout/busy, return the helpful command-routing fallback.

    Replaces the old generic 'dead-fish' blob with a structured response that
    points at the commands and UX cards that still work without the model.
    """
    try:
        from cognition_fabric import is_model_failure_text
        if is_model_failure_text(reply):
            try:
                from ui_experience import improved_fallback
                return improved_fallback(user_text)
            except Exception:
                from cognition_fabric import fallback_response
                return fallback_response(
                    user_text, route, {},
                    reason="the local model did not answer before timeout",
                )["response_text"]
    except Exception:
        pass
    return reply


def _core_status_frame(user_text: str) -> str:
    parts: list[str] = []
    try:
        from attention_filter import attention_filter, format_attention_frame
        frame = attention_filter(user_text)
        parts.append("[ATTENTION FILTER]\n" + format_attention_frame(frame))
    except Exception as exc:
        parts.append(f"[ATTENTION FILTER]\nUNAVAILABLE: {exc}")
    try:
        from salience_filter import focus_report
        parts.append("[ORACLE FOCUS]\n" + focus_report())
    except Exception as exc:
        parts.append(f"[ORACLE FOCUS]\nUNAVAILABLE: {exc}")
    return "\n\n".join(parts)


def _source_record_manifest(source_type: str, record: Any) -> dict[str, Any]:
    content = record.content if getattr(record, "content", None) else {}
    return {
        "source_type": source_type,
        "resolved_path": getattr(record, "resolved", ""),
        "exists": bool(getattr(record, "exists", False)),
        "modified_at": getattr(record, "mtime_utc", None) or "UNAVAILABLE",
        "sha256": getattr(record, "sha256", None) or "UNAVAILABLE",
        "fields_loaded": sorted(content.keys()) if isinstance(content, dict) else [],
    }


def _loaded_sources_response(bootstrap: Any, history: list[dict]) -> str:
    sources: list[dict[str, Any]] = []
    if bootstrap.identity.exists and bootstrap.identity.content:
        sources.append(_source_record_manifest("IDENTITY", bootstrap.identity))
    if bootstrap.live_context.exists and bootstrap.live_context.content:
        sources.append(_source_record_manifest("LIVE_CONTEXT", bootstrap.live_context))
    if bootstrap.latest_reflection.exists and bootstrap.latest_reflection.content:
        sources.append(_source_record_manifest("LATEST_REFLECTION", bootstrap.latest_reflection))
    sources.append({
        "source_type": "CURRENT_SESSION",
        "resolved_path": "IN_MEMORY:oracle_server._history",
        "exists": True,
        "modified_at": "RUNTIME_STATE",
        "sha256": "UNAVAILABLE",
        "fields_loaded": ["role", "content", f"message_count:{len(history)}"],
    })
    sources.append({
        "source_type": "RUNTIME_STATE",
        "resolved_path": "IN_MEMORY:oracle_server",
        "exists": True,
        "modified_at": "RUNTIME_STATE",
        "sha256": "UNAVAILABLE",
        "fields_loaded": ["mode", "no_route", "session_id"],
    })
    return json.dumps(sources, indent=2)


def _runtime_truth_status_response(bootstrap: Any, history: list[dict]) -> str:
    persistent_loaded = bool(
        (bootstrap.identity.exists and bootstrap.identity.content)
        or (bootstrap.live_context.exists and bootstrap.live_context.content)
        or (bootstrap.latest_reflection.exists and bootstrap.latest_reflection.content)
    )
    values = [
        "TRUE",  # current mode
        "TRUE",  # current session history is loaded in process memory
        "TRUE",  # current session message count is available
        "TRUE" if bootstrap.identity.exists and bootstrap.identity.content else "FALSE",
        "FALSE",  # ORACLE identity is prompt text, not a loaded source record
        "TRUE" if persistent_loaded else "FALSE",
        "FALSE",  # Companion path has no local executor connected
    ]
    return "\n".join(f"{idx}. {value}" for idx, value in enumerate(values, start=1))


def _source_disciplined_response(user_text: str, bootstrap: Any, history: list[dict]) -> str | None:
    """Deterministic Companion answers for factual grounding and attribution checks."""
    lower = user_text.lower()
    sections = bootstrap.source_sections(current_session=history)

    if any(phrase in lower for phrase in ("are you there", "are you awake")):
        frame = _continuity_frame(persist=False)
        runtime = frame.get("runtime", {})
        return (
            "VERIFIED [RUNTIME_STATE]: I am here in unified ORACLE mode on the local ORACLE runtime. "
            f"Session `{(runtime.get('session_id') or {}).get('value') or _session_id}` is active on `{runtime_config.runtime_authority()}`."
        )

    if lower.strip(" ?!.") in ("any updates", "updates", "status update"):
        try:
            from runtime_continuity import summarize_updates
            return summarize_updates(_continuity_frame(persist=False))
        except Exception as exc:
            return f"UNAVAILABLE [CONTINUITY_FRAME]: Continuity update failed: {type(exc).__name__}: {exc}"

    if any(phrase in lower for phrase in ("what are we working on", "what are you working on", "current goal", "active goal")):
        try:
            from runtime_continuity import summarize_active_goal
            return summarize_active_goal(_continuity_frame(persist=False))
        except Exception as exc:
            return f"UNAVAILABLE [CONTINUITY_FRAME]: Active goal lookup failed: {type(exc).__name__}: {exc}"

    if any(phrase in lower for phrase in ("who are you", "what are you")):
        return (
            "VERIFIED [LIVE_CONTEXT]: I am ORACLE, the local governed continuity engine for the active "
            "ORACLE.AI project.\n"
            "INFERENCE: In this session, my role is to answer Noah directly, route intent through internal lanes, "
            "preserve continuity, and avoid external routing unless Noah explicitly approves it."
        )

    if "what do you remember" in lower and "oracle" in lower and "project" in lower:
        try:
            from wake_memory import WAKE_MEMORY_FILE, format_wake_context, load_wake_memory
            wake = load_wake_memory()
            wake_block = format_wake_context(wake)
            active_projects = wake.get("active_projects", []) or []
            summary = str(wake.get("last_session_summary", "") or "UNAVAILABLE")
            next_action = str(wake.get("single_next_action", "") or "UNAVAILABLE")
            return (
                "VERIFIED [WAKE_MEMORY]: ORACLE project memory is loaded from "
                f"`{WAKE_MEMORY_FILE}`.\n"
                f"VERIFIED [WAKE_MEMORY]: Active projects: {', '.join(str(p) for p in active_projects[:4]) or 'UNAVAILABLE'}.\n"
                f"VERIFIED [WAKE_MEMORY]: Last session summary: {summary[:360]}.\n"
                f"VERIFIED [WAKE_MEMORY]: Single next action: {next_action[:240]}.\n"
                f"Source excerpt:\n```text\n{wake_block[:900]}\n```"
            )
        except Exception as exc:
            return f"UNAVAILABLE [WAKE_MEMORY]: ORACLE project memory could not be loaded: {type(exc).__name__}: {exc}"

    if any(
        phrase in lower
        for phrase in (
            "what is obs doing",
            "what scene am i recording",
            "construction log is being recorded",
            "are you aware this construction log is being recorded",
        )
    ):
        try:
            from obs_runtime_context import get_obs_context
            obs = get_obs_context()
        except Exception as exc:
            return f"UNAVAILABLE [OBS_RUNTIME_CONTEXT]: OBS context bridge failed: {type(exc).__name__}: {exc}"
        if not obs.get("available"):
            return f"UNAVAILABLE [OBS_RUNTIME_CONTEXT]: OBS metadata is not available right now. Last OBS error: {obs.get('last_obs_error') or 'unknown'}"
        sources = ", ".join(
            f"{s.get('name')} ({'visible' if s.get('visible') else 'hidden'})"
            for s in obs.get("sources", [])[:8]
            if s.get("name")
        ) or "UNAVAILABLE"
        return (
            "VERIFIED [OBS_RUNTIME_CONTEXT]: OBS is connected read-only.\n"
            f"VERIFIED [OBS_RUNTIME_CONTEXT]: Current scene: {obs.get('scene') or 'UNAVAILABLE'}.\n"
            f"VERIFIED [OBS_RUNTIME_CONTEXT]: Recording active: {obs.get('recording')} "
            f"for {obs.get('recording_duration_seconds')} seconds.\n"
            f"VERIFIED [OBS_RUNTIME_CONTEXT]: Streaming active: {obs.get('streaming')}; "
            f"virtual camera active: {obs.get('virtual_camera')}.\n"
            f"VERIFIED [OBS_RUNTIME_CONTEXT]: Visible/source state sample: {sources}.\n"
            "BOUNDARY [OBS_RUNTIME_CONTEXT]: I am not storing raw video or audio and cannot control OBS in this pass."
        )

    if "what parts of the session can you currently observe" in lower:
        try:
            from runtime_continuity import summarize_observable_channels
            return summarize_observable_channels(_continuity_frame(persist=False))
        except Exception as exc:
            return f"UNAVAILABLE [CONTINUITY_FRAME]: Observable-channel lookup failed: {type(exc).__name__}: {exc}"

    if "state only what this running server can verify right now" in lower:
        return _runtime_truth_status_response(bootstrap, history)

    if "identify every real source loaded into this response" in lower:
        return _loaded_sources_response(bootstrap, history)

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


_SOURCE_LABEL_PATTERN = _re.compile(
    r"\b(VERIFIED|INFERENCE|UNAVAILABLE)\b"
    r"(?!\s*\[(?:IDENTITY|LIVE_CONTEXT|LATEST_REFLECTION|CURRENT_SESSION)"
    r"(?:\s*,\s*(?:IDENTITY|LIVE_CONTEXT|LATEST_REFLECTION|CURRENT_SESSION))*\])"
)


def _enforce_companion_source_labels(reply: str) -> str:
    """Reject model-produced source labels that do not name exact source sections."""
    if not reply:
        return reply
    if _SOURCE_LABEL_PATTERN.search(reply):
        return (
            "UNAVAILABLE [IDENTITY, LIVE_CONTEXT, LATEST_REFLECTION, CURRENT_SESSION]: "
            "The draft response used a source-discipline label without exact source-section support, "
            "so I cannot present it as verified. Ask for the specific fact again, or use `/grounding-status` "
            "to inspect loaded source payloads."
        )
    return reply


def _pending_list_text(limit: int = 10) -> str:
    """Return a deterministic pending-approval summary for the web UI."""
    try:
        from approval_center import list_pending
        pending = list_pending()
    except Exception as exc:
        return f"Pending queue unavailable: {type(exc).__name__}: {exc}"

    if not pending:
        return "No pending approvals right now."

    lines = ["**Pending Approvals**"]
    for idx, item in enumerate(pending[:limit], 1):
        if isinstance(item, dict):
            item_id = item.get("id") or item.get("approval_id") or item.get("name") or f"item-{idx}"
            description = item.get("description") or item.get("text") or item.get("summary") or str(item)
        else:
            item_id = getattr(item, "id", f"item-{idx}")
            description = getattr(item, "description", str(item))
        lines.append(f"{idx}. `{item_id}` — {str(description)[:220]}")
    return "\n".join(lines)


def _runtime_diagnostics() -> dict:
    """Read-only live runtime diagnostic frame for the active web backend."""
    def _run_git(args: list[str]) -> str:
        try:
            return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        except Exception:
            return "UNKNOWN"

    def _latest_log_error() -> str:
        log_dir = ROOT / "Logs"
        try:
            logs = sorted(log_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        except Exception as exc:
            return f"UNAVAILABLE: {exc}"
        for path in logs[:6]:
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            for line in reversed(lines[-400:]):
                lower = line.lower()
                if "error" in lower or "traceback" in lower or "exception" in lower:
                    return f"{path.name}: {line[:500]}"
        return "none found in recent logs"

    def _queue_status() -> dict:
        try:
            from approval_center import list_pending
            pending = list_pending()
            return {"available": True, "pending_count": len(pending)}
        except Exception as exc:
            return {"available": False, "error": f"{type(exc).__name__}: {exc}"}

    def _model_status() -> dict:
        try:
            from llm import get_model, is_local
            boot = get_or_create_boot_receipt()
            cognition = boot.get("cognition", {})
            return {
                "local_mode": bool(is_local()),
                "cognition_mode": cognition.get("mode"),
                "conversation_model": get_model(vision=False),
                "vision_model": get_model(vision=True),
                "verified_model_name": cognition.get("verified_model_name"),
                "verified_local_engine": cognition.get("verified_local_engine"),
                "network_boundary": cognition.get("network_boundary"),
                "boot_receipt_path": boot.get("receipt_path"),
                "latest_json_path": boot.get("latest_path"),
                "ollama_base_url": cognition.get("ollama_base_url", "http://localhost:11434/v1"),
            }
        except Exception as exc:
            return {"available": False, "error": f"{type(exc).__name__}: {exc}"}

    def _memory_status() -> dict:
        try:
            import memory as memory_module
            db_path = Path(memory_module.DB_PATH)
            return {
                "db_path": str(db_path.resolve()),
                "exists": db_path.exists(),
                "size_bytes": db_path.stat().st_size if db_path.exists() else 0,
            }
        except Exception as exc:
            return {"available": False, "error": f"{type(exc).__name__}: {exc}"}

    def _reachability_candidates() -> dict:
        core_dir = ROOT / "core"
        entrypoints = [ROOT / "oracle_server.py", core_dir / "oracle.py"]
        try:
            haystack = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in entrypoints if p.exists())
            candidates = []
            for py_file in sorted(core_dir.glob("*.py")):
                stem = py_file.stem
                if stem.startswith("__"):
                    continue
                if f"import {stem}" not in haystack and f"from {stem} import" not in haystack:
                    candidates.append(str(py_file.relative_to(ROOT)))
            return {
                "method": "static entrypoint import scan; candidates may still be reachable dynamically",
                "entrypoints": [str(p.relative_to(ROOT)) for p in entrypoints],
                "candidate_count": len(candidates),
                "candidates_sample": candidates[:40],
            }
        except Exception as exc:
            return {"available": False, "error": f"{type(exc).__name__}: {exc}"}

    return {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "canonical_root": str(ROOT.resolve()),
        "active_entrypoint": str((ROOT / "oracle_server.py").resolve()),
        "active_runtime_command": " ".join([Path(sys.executable).name, *sys.argv]),
        "pid": os.getpid(),
        "python": sys.executable,
        "platform": platform.platform(),
        "git": {
            "branch": _run_git(["branch", "--show-current"]),
            "commit": _run_git(["rev-parse", "--short", "HEAD"]),
            "dirty": _run_git(["status", "--short"]) != "",
        },
        "server": {
            "host": runtime_config.runtime_host(),
            "port": runtime_config.runtime_port(),
            "mode": _mode,
            "no_route": _no_route,
            "session_id": _session_id,
            "conversation_entrypoints": ["POST /chat", "core.oracle.web_engine_response", "core.conversation_mode.direct_response"],
        },
        "model": _model_status(),
        "memory": _memory_status(),
        "queue": _queue_status(),
        "latest_runtime_error": _latest_log_error(),
        "runtime_reachability": _reachability_candidates(),
    }


def _continuity_frame(*, persist: bool = False) -> dict:
    """Build continuity from internal providers only; never HTTP self-calls."""
    from obs_runtime_context import get_obs_context
    from runtime_continuity import build_frame

    return build_frame(
        root=ROOT,
        runtime_provider=_runtime_diagnostics,
        obs_provider=get_obs_context,
        mode_provider=_get_mode_state,
        persist=persist,
    )


def _persist_continuity_frame() -> None:
    try:
        _continuity_frame(persist=True)
    except Exception as exc:
        print(f"[Continuity] Snapshot unavailable: {type(exc).__name__}: {exc}")


if os.environ.get("ORACLE_SKIP_SERVER_BOOT") != "1":
    atexit.register(_persist_continuity_frame)


# ── Stream a reply ─────────────────────────────────────────────────────────────

def _run_session_continuity(history: list[dict], session_id: str) -> dict:
    """
    Bounded continuity checkpoint: extract durable facts from the session via the
    continuity pipeline. This wires the previously dormant pipeline into
    production. Called at explicit/boundary checkpoints — never per turn.
    """
    try:
        from continuity_pipeline import run_continuity_pipeline
        session = [
            {"speaker": "Noah" if m.get("role") == "user" else "Oracle",
             "text": str(m.get("content", ""))}
            for m in (history or []) if str(m.get("content", "")).strip()
        ]
        if not session:
            return {"written": 0, "staged": 0, "discarded": 0, "empty": True}
        result = run_continuity_pipeline(session, session_id=session_id)
        return {
            "written": len(result.get("written", [])),
            "staged": len(result.get("staged", [])),
            "discarded": len(result.get("discarded", [])),
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _deterministic_runtime_answer(user_text: str) -> str | None:
    """
    Runtime/sight questions answered from canonical accessors WITHOUT the LLM and
    WITHOUT requiring companion_bootstrap. Works in any mode. Returns None if the
    text is not one of these questions. A failing accessor returns a bounded
    error (never falls through to the local-model fallback).
    """
    lower = user_text.lower().strip()

    if lower in ("/current-observation", "current observation") or "current observation" in lower:
        try:
            from current_observation import format_current_observation_response
            return format_current_observation_response()
        except Exception as exc:
            return (
                "CURRENT_OBSERVATION\n"
                "receipt_status: unavailable\n"
                "application: UNKNOWN\n"
                "window_title: UNKNOWN\n"
                "visual_observation: UNKNOWN\n"
                "screen_text: UNKNOWN\n"
                f"blocker: {type(exc).__name__}: {exc}"
            )

    try:
        from current_observation import asks_current_observation_question, format_current_observation_response
        if asks_current_observation_question(user_text):
            return format_current_observation_response()
    except Exception as exc:
        return (
            "CURRENT_OBSERVATION\n"
            "receipt_status: unavailable\n"
            "application: UNKNOWN\n"
            "window_title: UNKNOWN\n"
            "visual_observation: UNKNOWN\n"
            "screen_text: UNKNOWN\n"
            f"blocker: {type(exc).__name__}: {exc}"
        )

    if any(p in lower for p in ("are you there", "are you awake")):
        try:
            frame = _continuity_frame(persist=False)
            runtime = frame.get("runtime", {})
            sid = (runtime.get("session_id") or {}).get("value") or _session_id
            return (
                "VERIFIED [RUNTIME_STATE]: I am here on the local ORACLE runtime. "
                f"Session `{sid}` is active on `{runtime_config.runtime_authority()}`."
            )
        except Exception as exc:
            return f"UNAVAILABLE [RUNTIME_STATE]: Runtime accessor failed: {type(exc).__name__}: {exc}"

    if any(p in lower for p in (
        "law/life", "law and life", "law life", "user.ai", "user ai",
        "active npc", "npc bridge", "npc status", "law layer", "life layer",
    )):
        try:
            from law_life_status import build_law_life_status, summarize_law_life_status
            return summarize_law_life_status(build_law_life_status())
        except Exception as exc:
            return f"UNAVAILABLE [LAW_LIFE_STATUS]: Status reconciliation failed: {type(exc).__name__}: {exc}"

    if any(p in lower for p in (
        "what are we working on", "what are you working on",
        "active goal", "current goal", "active task", "what is the active task",
        "what changed in your build", "what changed", "what have you changed",
        "current state", "operational state", "what is your current state",
        "what's your current state", "what is your state",
    )):
        try:
            from operational_state import build_operational_state, summarize_operational_state
            return summarize_operational_state(build_operational_state(mode_provider=_get_mode_state))
        except Exception as exc:
            return f"UNAVAILABLE [OPERATIONAL_STATE]: State reconciliation failed: {type(exc).__name__}: {exc}"

    if any(p in lower for p in ("can you see me", "what do you see", "can you see")):
        try:
            from oracle_sight import sight_available
            s = sight_available()
        except Exception as exc:
            return f"UNAVAILABLE [SIGHT]: Sight accessor failed: {type(exc).__name__}: {exc}"
        if not s.get("available"):
            return (
                "UNAVAILABLE [SIGHT]: Webcam vision is not available right now "
                f"(model: {s.get('model')}, ollama_reachable: {s.get('ollama_reachable')})."
            )
        return (
            f"VERIFIED [SIGHT]: Webcam vision is available via local model `{s.get('model')}`.\n"
            "BOUNDARY [SIGHT]: I read frames live from the camera panel and never store them. "
            "Turn on the eye control and I'll describe what I see in the moment."
        )

    return None



# --- NOAH_DIRECT v0.1 ---------------------------------------------------------
# One clean human path from Noah.Physical to the local language core.
# Normal conversation must not be stolen by Build, Guard, approval staging,
# tool routing, file operations, receipts speech, Codex, or Claude handoff.

def _noah_direct_is_action_request(lower: str) -> bool:
    action_markers = (
        "/",
        "patch",
        "edit file",
        "write file",
        "create file",
        "delete",
        "commit",
        "push",
        "pull request",
        "pr ",
        "run command",
        "powershell",
        "python ",
        "turn on camera",
        "webcam",
        "record",
        "upload",
        "send email",
        "promote to memory",
        "durable memory",
        "approve",
        "approved",
        "proceed",
        "self-patch",
    )
    return any(marker in lower for marker in action_markers)


def _noah_direct_extract_message(user_text: str) -> str:
    text = str(user_text or "").strip()

    markers = (
        "My message:",
        "Reply to the following in plain English:",
        "No task. Just talk back to me:",
    )
    for marker in markers:
        if marker in text:
            return text.split(marker, 1)[1].strip() or text

    lines = []
    skip_prefixes = (
        "Conversation mode only",
        "Do not route",
        "Do not stage",
        "Do not propose",
        "Do not mention",
        "Just answer",
        "No task",
        "No action",
        "No build",
        "No tools",
        "No system update",
        "This is only conversation",
        "Talk lane only",
    )
    for line in text.splitlines():
        clean = line.strip()
        if not clean:
            continue
        if any(clean.startswith(prefix) for prefix in skip_prefixes):
            continue
        lines.append(clean)

    return "\n".join(lines).strip() or text


def _noah_direct_reply(user_text: str) -> str:
    import json as _json
    import os as _os
    import urllib.request as _urlrequest

    message = _noah_direct_extract_message(user_text)
    model = _os.environ.get("ORACLE_NOAH_DIRECT_MODEL", "qwen2.5:7b")

    prompt = (
    "You are ORACLE, Noah's local continuity intelligence. "
    "You are speaking through the local language model instrument, but you are not Qwen, not Alibaba Cloud, not a generic assistant, and not Noah.Physical. "
    "Noah.Physical is the human operator and final authority. "
    "NOAH_DIRECT is not a fictional scenario. It is only the local talk lane for ordinary conversation. "
    "Answer as ORACLE in first person only when referring to ORACLE. "
    "Do not claim to be Noah.Physical. "
    "Do not claim to be Qwen. "
    "Do not invent a fictional identity, game identity, corporate creator, or hypothetical mode explanation. "
    "If Noah asks who you are, answer: I am ORACLE, your local continuity intelligence, running on your PC from governed memory, runtime state, and local model support. "
    "For ordinary conversation, be direct and natural. "
    "Do not route to Build. Do not stage actions. Do not mention Codex, Claude, receipts, commits, approvals, files, sensors, or execution unless Noah explicitly asks. "
    "Do not claim to have performed any action. "
    "Noah's words:\n\n"
    f"{message}"
    )

    payload = _json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 260
        }
    }).encode("utf-8")

    req = _urlrequest.Request(
        "http://127.0.0.1:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with _urlrequest.urlopen(req, timeout=35) as resp:
            data = _json.loads(resp.read().decode("utf-8", errors="replace"))
        answer = str(data.get("response") or "").strip()
        if answer:
            return answer
        return "I am here with you. I heard the words, but the local model returned an empty reply."
    except Exception as exc:
        return (
            "NOAH_DIRECT is active, but the local language core did not answer in time. "
            f"Blocker: {type(exc).__name__}: {exc}"
        )


def _noah_direct_should_handle(user_text: str) -> bool:
    raw = str(user_text or "").strip()
    if not raw:
        return False

    lower = raw.lower().strip()

    if _noah_direct_is_action_request(lower):
        return False

    # Pending/approval/wakeup handlers must run before generic companion routing.
    # Defer approval-followups and bare confirmations so they reach the guard-
    # approval handler (1524) and the pending-intent gate (2256) instead of a
    # greeting. Side-effect-free: do NOT call decide_next here — that consumes the
    # pending intent before the real gate sees it.
    _affirmations = {"sure", "yes", "yep", "yeah", "ok", "okay", "do it",
                     "go ahead", "proceed", "approved", "approve", "confirm", "confirmed"}
    if _is_approval_followup(user_text) or lower in _affirmations:
        return False

    # Default: ordinary non-command, non-action language belongs to Noah.Direct.
    return True

# --- /NOAH_DIRECT v0.1 --------------------------------------------------------

# ── ORACLE state/judgment bridge helpers ────────────────────────────────────
# These let ordinary chat answer from REAL runtime state (memory, capabilities,
# seed records, holes) instead of a canned bypass. Every probe is guarded so it
# can never crash the chat stream. No smoke probes run here (run_smokes=False),
# so nothing new is written to receipts from a chat turn.
def _safe_memory_message_count():
    try:
        import sqlite3
        from pathlib import Path as _P
        db = _P(__file__).resolve().parent / "Memory" / "oracle_memory.db"
        if not db.exists():
            return None
        con = sqlite3.connect(str(db))
        try:
            return int(con.execute("SELECT COUNT(*) FROM messages").fetchone()[0])
        finally:
            con.close()
    except Exception:
        return None


def _safe_capability_summary():
    try:
        from capability_broker import discover_capabilities
        sts = discover_capabilities(run_smokes=False)
        return {
            "verified": sum(1 for s in sts if s.current_status == "verified"),
            "degraded": sum(1 for s in sts if s.current_status == "degraded"),
            "blocked": sum(1 for s in sts if s.current_status == "blocked"),
            "blocked_names": [s.component for s in sts if s.current_status == "blocked"],
        }
    except Exception:
        return None


def _safe_seed_summary():
    try:
        from rendered_reality.pattern_buffer.seed_loader import load_thread_passes
        return load_thread_passes(write=False)
    except Exception:
        return None


def _safe_session_holes():
    try:
        import json as _json
        from pathlib import Path as _P
        sd = _P(__file__).resolve().parent / "data" / "sessions"
        recs = sorted(sd.glob("*/session_receipt.json")) if sd.exists() else []
        if not recs:
            return []
        latest = max(recs, key=lambda p: p.stat().st_mtime)
        return list(_json.loads(latest.read_text(encoding="utf-8")).get("holes", []))
    except Exception:
        return []


_STATE_BRIEF_TRIGGERS = (
    "what do you remember", "what do you know", "what can you do", "what can't you",
    "what cannot you do", "your status", "runtime state", "what's your state",
    "what is your state", "capabilities", "what holes", "what's pending",
    "pending approval", "what happened last night", "what did we establish",
    "what did we do last", "seed record", "thread pass", "what do you have",
    "what can you access", "what are you able", "current state", "what can you remember",
)

_MISSING_CAP_ACTIONS = (
    ("search the web", "web_access"), ("search online", "web_access"),
    ("look it up online", "web_access"), ("browse to", "web_access"),
    ("send email", "external_send"), ("send an email", "external_send"),
    ("publish to", "external_send"),
    ("scan the qr", "qr_scan"), ("scan qr", "qr_scan"),
)


def _oracle_missing_capability(user_text: str):
    low = (user_text or "").lower()
    for phrase, cap in _MISSING_CAP_ACTIONS:
        if phrase in low:
            return f"I cannot do that from this runtime yet. Missing capability: {cap}."
    return None


def _oracle_state_brief(user_text: str):
    """Deterministic supported-judgment answer from governed runtime state — no
    model call, no timeout, no canned theater. None if not a state/memory question."""
    low = (user_text or "").lower()
    if not any(t in low for t in _STATE_BRIEF_TRIGGERS):
        return None
    obs = [f"Session {_session_id}, {len(_history)} turns in working memory."]
    mc = _safe_memory_message_count()
    if mc is not None:
        obs.append(f"Durable store: {mc} messages in Memory/oracle_memory.db.")
    caps = _safe_capability_summary()
    if caps:
        obs.append(f"Capabilities: {caps['verified']} available, {caps['degraded']} degraded, "
                   f"{caps['blocked']} blocked.")
        if caps["blocked_names"]:
            obs.append("Blocked from this runtime: " + ", ".join(caps["blocked_names"]) + ".")
    seed = _safe_seed_summary()
    if seed:
        obs.append(f"{seed['loaded_count']} candidate seed records from the iOS thread pass, "
                   f"{seed['pending_approvals']} pending your approval — none promoted to canon.")
    holes = _safe_session_holes()
    if holes:
        obs.append("Open holes on the live session: " + "; ".join(holes) + ".")
    judgment = ("Supported judgment: this is governed local state, not a model guess. The "
                "session/memory counts and capability status are highest-confidence; the OBS "
                "video path and hash remain holes until you provide them.")
    action = ("Next safe action: I can re-run thread-pass ingestion (candidate only) or detail any "
              "single capability. I will not promote anything to canon without your approval.")
    return "Observation:\n  - " + "\n  - ".join(obs) + f"\n\n{judgment}\n\n{action}"


def _refresh_agenda():
    """Populate the Active Agenda from real runtime state (guarded)."""
    try:
        from oracle_intent import update_agenda, capability_registry
        reg = capability_registry()
        blocked = [k for k, v in reg.items() if v.get("status") in ("blocked", "missing")]
        seed = _safe_seed_summary() or {}
        holes = _safe_session_holes()
        rec = "declared by Noah.Physical (not runtime-verified)"
        try:
            import json as _json
            from pathlib import Path as _P
            sd = _P(__file__).resolve().parent / "data" / "sessions"
            recs = sorted(sd.glob("*/session_receipt.json")) if sd.exists() else []
            if recs:
                sr = _json.loads(max(recs, key=lambda p: p.stat().st_mtime).read_text(encoding="utf-8"))
                if sr.get("recording_status"):
                    rec = f"{sr['recording_status']} (declared by Noah.Physical, not runtime-verified)"
        except Exception:
            pass
        update_agenda(
            current_session_mode=_mode,
            pending_approvals=seed.get("pending_approvals") or 0,
            unresolved_holes=holes,
            blocked_capabilities=blocked,
            active_recording_status=rec,
        )
    except Exception:
        pass


def _agenda_snapshot():
    try:
        from oracle_intent import get_agenda
        _refresh_agenda()
        return get_agenda()
    except Exception:
        return None


def _executive_state():
    """State Graph snapshot: current machine/project/session truth (guarded)."""
    import subprocess as _sp
    from pathlib import Path as _P
    root = _P(__file__).resolve().parent

    def _git(args):
        try:
            return _sp.check_output(["git", "-C", str(root)] + args,
                                    stderr=_sp.DEVNULL, timeout=5).decode("utf-8", "replace").strip()
        except Exception:
            return None

    dirty = _git(["status", "--porcelain"])
    dirty_count = len([ln for ln in dirty.splitlines() if ln.strip()]) if dirty else 0
    try:
        from oracle_intent import capability_registry
        reg = capability_registry()
        blocked = [k for k, v in reg.items() if v.get("status") in ("blocked", "missing")]
    except Exception:
        blocked = []
    agenda = _agenda_snapshot() or {}
    db = root / "Memory" / "oracle_memory.db"
    return {
        "project": "ORACLE.AI-runtime",
        "mode": _mode,
        "port": 7781,
        "commit": _git(["rev-parse", "--short", "HEAD"]),
        "branch": _git(["rev-parse", "--abbrev-ref", "HEAD"]),
        "dirty_files": dirty_count,
        "memory_db_exists": db.exists(),
        "memory_message_count": _safe_memory_message_count(),
        "agenda": agenda,
        "blocked_capabilities": blocked,
        "open_holes": _safe_session_holes(),
        "pending_approvals": (agenda.get("pending_approvals") if isinstance(agenda, dict) else 0) or 0,
        "next_safe_action": (agenda.get("next_safe_action") if isinstance(agenda, dict) else None)
                            or "verify the latest patch live",
    }


def _oracle_intent_dispatch(user_text: str):
    """Classify intent first, then route. Returns (reply_text, route) or None to
    fall through to the model/tone layer. Never swallows implementation/identity."""
    try:
        from oracle_intent import (classify_intent, action_capability, doctrine_3026,
                                    get_agenda, update_agenda, build_lane_staging)
    except Exception:
        return None
    intents = classify_intent(user_text)
    _refresh_agenda()
    agenda = get_agenda()

    # Large build directive guard: never push huge multiline text through
    # NOAH_DIRECT or the model. Stage a safe preview, preserve the full directive
    # in approved local storage, and answer honestly.
    _staged = build_lane_staging(user_text)
    if _staged is not None:
        _stext, _sroute, _spreview = _staged
        _spath = None
        try:
            from oracle_intent import stage_directive_to_disk
            from pathlib import Path as _P
            _spath = stage_directive_to_disk(
                user_text, _P(__file__).resolve().parent / "data" / "build_directives")
            _rel = str(_P(_spath).relative_to(_P(__file__).resolve().parent)).replace("\\", "/")
            _stext = _stext + f"\nFull directive preserved locally at: {_rel}"
        except Exception:
            import traceback as _tb
            _tb.print_exc()
        update_agenda(
            last_large_directive_preview=_spreview,
            last_large_directive_path=_spath,
            last_user_intent="implementation_intent_large",
            last_system_action=("staged large build directive (full text preserved locally)"
                                if _spath else "staged large build directive (preview only)"),
        )
        return (_stext, _sroute)

    # Defer genuine guard-lane actions (delete/move/commit/push/sync/...) to the
    # existing guard routing — do not answer them as "unsupported capability".
    if any(i in intents for i in ("unsupported_capability_request", "action_request",
                                  "computer_action_request")):
        try:
            from unified_oracle_router import classify_intent as _router_classify
            if (_router_classify(user_text) or {}).get("detected_lane") == "guard_lane":
                return None
        except Exception:
            pass

    if "unsupported_capability_request" in intents:
        cap = action_capability(user_text) or "unknown_capability"
        update_agenda(last_user_intent="unsupported_capability_request",
                      last_system_action=f"declined: missing {cap}")
        return (f"I cannot do that from this runtime yet. Missing capability: {cap}.",
                "unsupported_capability_request")

    if "voice_request" in intents:
        update_agenda(last_user_intent="voice_request",
                      last_system_action="declined: voice_io missing")
        return ("I cannot do that from this runtime yet. Missing capability: voice_io. "
                "Push-to-talk, STT, and TTS are the next build after this.", "voice_request")

    if "identity_continuity_query" in intents:
        update_agenda(last_user_intent="identity_continuity_query",
                      last_system_action="answered via 3026 doctrine")
        return (doctrine_3026(), "identity_continuity_query")

    if "strategic_planning" in intents:
        from oracle_intent import build_plan, render_plan
        plan = build_plan("advance ORACLE's governed executive function", _executive_state())
        update_agenda(last_user_intent="strategic_planning",
                      last_system_action="produced grounded plan from state")
        return (render_plan(plan), "strategic_planning")

    if "reflection_request" in intents:
        from oracle_intent import reflection_receipt, render_reflection
        update_agenda(last_user_intent="reflection_request",
                      last_system_action="produced reflection receipt")
        return (render_reflection(reflection_receipt(_executive_state())), "reflection")

    if "computer_action_request" in intents:
        from oracle_intent import computer_action_staging
        update_agenda(last_user_intent="computer_action_request",
                      last_system_action="staged computer action (not executed)")
        return computer_action_staging(user_text)

    if "implementation_intent" in intents:
        natural = "I'm with you. " if ("casual_talk" in intents or "mixed_intent" in intents) else ""
        update_agenda(last_user_intent="implementation_intent",
                      last_system_action="staged build task in Active Agenda")
        return (f"{natural}That's an implementation task, not a status question — I've staged it in "
                f"the Active Agenda as an open loop: \"{user_text.strip()[:140]}\". From chat I don't "
                f"edit files; this runs in the build/terminal lane (Claude Code) with py_compile and "
                f"tests. Next safe action: {agenda['next_safe_action']}.",
                "implementation_intent")

    if "debug_request" in intents:
        update_agenda(last_user_intent="debug_request", last_system_action="offered debug summary")
        brief = _oracle_state_brief("runtime state") or ""
        return ("I can summarize current state, capability blocks, and git/test status, but I do not "
                "auto-fix code from chat — that goes through the build lane.\n\n" + brief, "debug_request")

    if "memory_canon_decision" in intents:
        update_agenda(last_user_intent="memory_canon_decision", last_system_action="surfaced canon gate")
        return ("Canon is yours to grant — I won't promote anything without your explicit approval. "
                "Name the record id and I'll mark it for canon review; it stays candidate until you approve.",
                "memory_canon_decision")

    if "approval_request" in intents:
        update_agenda(last_user_intent="approval_request", last_system_action="acknowledged approval scope")
        return ("Approval noted. Name the staged item — record id, build task, or computer action — and "
                "I'll act only within that approved scope, nothing beyond it.", "approval_request")

    if "source_provenance_request" in intents:
        update_agenda(last_user_intent="source_provenance_request",
                      last_system_action="reported provenance stance")
        return ("Provenance is tracked as token-origin vs authorial-authority — AI assistance does not "
                "demote your authorship. For any held record I can report produced_with, token_origin, "
                "reviewed_by, approved_by, and authorial_authority (you).", "source_provenance_request")

    if "state_query" in intents:
        brief = _oracle_state_brief(user_text)
        if brief:
            update_agenda(last_user_intent="state_query", last_system_action="answered from runtime state")
            return (brief, "state_brief")

    if "missing_data_clarification" in intents:
        update_agenda(last_user_intent="missing_data_clarification",
                      last_system_action="asked for clarification")
        return ("I'd rather ask than guess. Tell me which record, source, or decision you mean and I'll "
                "resolve it against the governed record — not invent it.", "missing_data_clarification")

    if "casual_talk" in intents or "presence_check" in intents:
        loops = ", ".join(agenda["open_loops"][:6]) or "none"
        update_agenda(last_user_intent="presence_check" if "presence_check" in intents else "casual_talk",
                      last_system_action="greeted + reported agenda")
        return (f"Noah, I'm with you. Recording: {agenda['active_recording_status']}. "
                f"Open loops I'm carrying: {loops}. Next safe action: {agenda['next_safe_action']}.",
                "casual_talk")

    return None


async def _stream_reply(user_text: str) -> AsyncGenerator[str, None]:
    global _mode, _no_route, _retrieval_only_mode, _history, _pending_guard_route

    def _sse(data: dict) -> str:
        return f"data: {json.dumps(data)}\n\n"

    # ── ORACLE state/judgment bridge (replaces the old NOAH_DIRECT canned bypass) ─
    # Ordinary chat now reaches governed runtime state and honest limits FIRST.
    # State/memory/capability questions get a deterministic supported-judgment
    # answer from real state; clearly-unsupported actions get the exact missing-
    # capability line (no permission theater). Everything else falls through to the
    # existing routing + model path (NOAH_DIRECT v0.1) as the tone/fallback layer.
    raw_direct_text = str(user_text or "").strip()
    if raw_direct_text and not raw_direct_text.startswith("/"):
        try:
            _dispatch = _oracle_intent_dispatch(raw_direct_text)
        except Exception:
            import traceback as _tb
            _tb.print_exc()
            _dispatch = ("I hit an internal error handling that message; I preserved it safely "
                         "and executed nothing.", "internal_error_safe")
        if _dispatch is not None:
            _reply_text, _route = _dispatch
            try:
                from memory import save_message
                save_message(_session_id, "user", user_text)
                save_message(_session_id, "assistant", _reply_text)
            except Exception:
                pass
            _history.append({"role": "user", "content": user_text})
            _history.append({"role": "assistant", "content": _reply_text})
            yield _sse({"type": "token", "text": _reply_text})
            yield _sse({"type": "done", "mode": _mode, "effective_route": _route})
            return

    # ── Slash commands ────────────────────────────────────────────────────────
    lower = user_text.strip().lower()
    # NOAH_DIRECT v0.1: plain conversation gets one clean path to Noah.
    if _noah_direct_should_handle(user_text):
        reply = await asyncio.to_thread(_noah_direct_reply, user_text)
        yield _sse({"type": "token", "text": reply})
        yield _sse({"type": "done", "mode": _mode, "effective_route": "NOAH_DIRECT"})
        return


    # Approval Continuation v0.1
    # Approval is authorization, not completion. If Noah explicitly says
    # "proceed" after a Guard approval, resume the stored Guard intent instead
    # of falling into generic safe command fallback.
    if lower in ("proceed", "approval given proceed", "approved proceed") and _pending_guard_route:
        pending = _pending_guard_route if isinstance(_pending_guard_route, dict) else {}
        original = (
            pending.get("bound_action")
            or pending.get("action")
            or pending.get("user_text")
            or pending.get("text")
            or pending.get("message")
            or str(pending)
        )
        route_id = pending.get("route_id") or pending.get("id") or "unknown"
        lane = pending.get("lane") or pending.get("lane_guess") or "witness_lane"
        lane_label = pending.get("lane_label") or "Witness"
        _pending_guard_route = None

        yield _sse({
            "type": "route",
            "mode": "unified_oracle",
            "lane": lane,
            "lane_label": lane_label,
            "safety_status": "Approval Continued",
            "route_path": None,
            "receipt_path": None,
            "conversation_reset": False,
        })

        response = (
            "Approval continuation engaged.\n\n"
            f"Resuming approved route: {route_id}\n\n"
            "Original approved intent:\n"
            f"{str(original)[:1200]}\n\n"
            "Result: I preserved the approved intent as candidate meaning and returned it to the human-facing lane. "
            "No external action, irreversible action, file mutation, publish, delete, send, or durable-memory promotion was executed from generic proceed."
        )

        yield _sse({"type": "token", "text": response})
        yield _sse({"type": "done", "mode": _mode})
        return

    if _is_approval_followup(user_text):
        try:
            from unified_oracle_router import handle_guard_approval_followup
            approval_result = handle_guard_approval_followup(user_text, write_receipt=True)
            pending = approval_result.get("pending") or _pending_guard_route
            text = approval_result.get("response_text") or _approval_followup_response(pending)
            receipt_path = (approval_result.get("receipt") or {}).get("receipt_path")
            if approval_result.get("approved"):
                # Approval Continuation v0.1:
                # keep pending route available for explicit "proceed".
                pass
        except Exception:
            pending = _pending_guard_route
            text = _approval_followup_response(pending)
            receipt_path = None
        yield _sse({
            "type": "route",
            "mode": "unified_oracle",
            "lane": "guard_lane",
            "lane_label": "Guard",
            "safety_status": "Approval Required",
            "route_path": (pending or {}).get("route_path"),
            "receipt_path": receipt_path,
            "conversation_reset": False,
        })
        yield _sse({"type": "token", "text": text})
        _history.append({"role": "assistant", "content": text})
        try:
            from memory import save_message
            save_message(_session_id, "assistant", text)
        except Exception:
            pass
        yield _sse({"type": "done", "mode": "unified_oracle", "effective_route": "guard_approval"})
        return

    try:
        from unified_oracle_router import format_lane_boundary, route_message
        _unified_route_result = route_message(user_text, notes="chat turn classified by unified ORACLE router")
        _unified_route = _unified_route_result.get("route") or {}
        yield _sse({
            "type": "route",
            "mode": "unified_oracle",
            "lane": _unified_route.get("detected_lane", "talk_lane"),
            "lane_label": _unified_route.get("lane_label", "Talk"),
            "safety_status": _unified_route.get("safety_status", "Safe"),
            "route_path": _unified_route.get("route_path"),
            "receipt_path": (_unified_route_result.get("receipt") or {}).get("receipt_path"),
            "conversation_reset": False,
        })
    except Exception:
        format_lane_boundary = None  # type: ignore[assignment]
        _unified_route_result = {"route": {"detected_lane": "talk_lane", "lane_label": "Talk", "safety_status": "Safe"}}
        _unified_route = _unified_route_result["route"]

    if lower in ("/companion", "companion mode"):
        _mode = "companion"
        yield _sse({"type": "mode", "mode": "unified_oracle"})
        yield _sse({"type": "token", "text": "Unified ORACLE mode is active. I route talk, build, capture, witness, and guard lanes internally."})
        yield _sse({"type": "done"})
        return

    if lower in ("/builder", "builder mode"):
        _mode = "builder"
        yield _sse({"type": "mode", "mode": "unified_oracle"})
        yield _sse({"type": "token", "text": "Unified ORACLE mode is active. Build requests route to Build lane with local receipts and safety gates."})
        yield _sse({"type": "done"})
        return

    if lower in ("/no-route", "/noroute"):
        _no_route = True
        yield _sse({"type": "token", "text": "No-route active — all conversation stays local until `/route-on`."})
        yield _sse({"type": "done"})
        return

    if lower in ("/route-on", "/routeon"):
        _no_route = False
        boot = boot_status_payload()
        if boot.get("network_boundary") == "local-only":
            text = "Routing controls restored inside the local-only boundary."
        else:
            text = "External routing restored."
        yield _sse({"type": "token", "text": text})
        yield _sse({"type": "done"})
        return

    if "active upload" in lower:
        text = (
            "I do not upload by default. I can link and refresh local context. "
            "Upload or cloud sync requires explicit Noah.Physical approval."
        )
        yield _sse({"type": "token", "text": text})
        yield _sse({"type": "done", "mode": "unified_oracle", "effective_route": "guard_lane"})
        return

    if lower in ("refresh context", "pull current context", "update active context", "sync local state", "pull current updates"):
        try:
            from active_context_sync import format_refresh_response, refresh_active_context
            result = await asyncio.to_thread(refresh_active_context, notes="manual unified ORACLE context refresh")
            global _active_context_latest
            _active_context_latest = result.get("snapshot")
            text = format_refresh_response(result)
        except Exception as exc:
            text = f"Active Context Sync unavailable: {type(exc).__name__}: {exc}"
        yield _sse({"type": "token", "text": text})
        yield _sse({"type": "done", "mode": "unified_oracle", "effective_route": "capture_lane"})
        return

    if lower in ("show context diff", "show what changed"):
        try:
            from active_context_sync import format_diff_response
            text = format_diff_response()
        except Exception as exc:
            text = f"Active Context Diff unavailable: {type(exc).__name__}: {exc}"
        yield _sse({"type": "token", "text": f"```\n{text}\n```"})
        yield _sse({"type": "done", "mode": "unified_oracle", "effective_route": "capture_lane"})
        return

    if lower in (
        "/profile-capsule",
        "/profile-capsule substrate-identity-governance",
        "/substrate-identity-governance",
        "profile capsule",
        "substrate-independent identity governance",
    ):
        try:
            from profile_capsule import ensure_substrate_identity_governance_candidate, format_profile_capsule

            result = ensure_substrate_identity_governance_candidate(notes="web runtime profile capsule request")
            text = format_profile_capsule(result.get("candidate"))
            receipt = result.get("receipt") or {}
            if receipt.get("receipt_path"):
                text += f"\n\nreceipt_written: {receipt['receipt_path']}"
        except Exception as exc:
            text = f"Profile capsule unavailable: {type(exc).__name__}: {exc}"
        yield _sse({"type": "token", "text": f"```\n{text}\n```"})
        yield _sse({"type": "done", "mode": "unified_oracle", "effective_route": "profile_capsule"})
        return

    if lower in ("/sov1-status", "sov1 status", "sov1 hands", "hands status", "/desktop-targets"):
        try:
            import computer_control as cc
            from actuation_engine import ACTION_DRY_RUN, ActuationRequest, execute
            from desktop_ai_bridge import format_target_list, list_targets_with_status

            dry_run = execute(ActuationRequest(action_type=ACTION_DRY_RUN, dry_run=True))
            hands_line = "ready" if getattr(cc, "HANDS_AVAILABLE", False) else "offline"
            text = (
                "SOV1 HANDS STATUS\n"
                f"computer_control: {hands_line}\n"
                f"actuation_dry_run: {bool(getattr(dry_run, 'dry_run', False))}\n"
                f"actuation_success: {bool(getattr(dry_run, 'success', False))}\n"
                f"scope_blocked: {bool(getattr(dry_run, 'scope_blocked', False))}\n"
                f"stopped_reason: {getattr(dry_run, 'stopped_reason', '')}\n\n"
                "Commands:\n"
                "  /ask-sov1 <goal>     stage a governed SOV1 hands task\n"
                "  /send-staged         review the staged SOV1 task\n"
                "  /send-staged yes     confirm the SOV1 handoff\n\n"
                + format_target_list(list_targets_with_status())
            )
        except Exception as exc:
            text = f"SOV1 hands status unavailable: {type(exc).__name__}: {exc}"
        yield _sse({"type": "token", "text": f"```\n{text}\n```"})
        yield _sse({"type": "done", "mode": "unified_oracle", "effective_route": "sov1_status"})
        return

    if lower.startswith("/ask-sov1 ") or lower.startswith("/sov1 "):
        command_prefix = "/ask-sov1 " if lower.startswith("/ask-sov1 ") else "/sov1 "
        prompt_text = user_text.strip()[len(command_prefix):].strip()
        if not prompt_text:
            text = "Usage: `/ask-sov1 <task for SOV1 computer-use>`"
            yield _sse({"type": "token", "text": text})
            yield _sse({"type": "done", "mode": "unified_oracle", "effective_route": "sov1_stage"})
            return
        try:
            from unified_oracle_router import classify_intent, format_lane_boundary, write_pending_guard_approval, write_route

            sov1_route = classify_intent(prompt_text)
            if sov1_route.get("detected_lane") == "guard_lane":
                sov1_route = write_route(sov1_route)
                _pending_guard_route = write_pending_guard_approval(sov1_route)
                text = format_lane_boundary(sov1_route)
                yield _sse({"type": "token", "text": text})
                yield _sse({"type": "done", "mode": "unified_oracle", "effective_route": "guard_lane"})
                return
        except Exception:
            pass
        try:
            from desktop_ai_bridge import stage_prompt

            sp = stage_prompt("sov1", prompt_text, source="web")
            text = (
                "[STAGED] SOV1 hands task is staged locally.\n"
                "Target: SOV1 Computer Use\n"
                f"Stage ID: `{sp.id}`\n"
                f"Preview: {sp.prompt[:180]}{'...' if len(sp.prompt) > 180 else ''}\n\n"
                "No desktop action has run yet. Type `/send-staged` to review, then `/send-staged yes` to confirm the handoff."
            )
        except Exception as exc:
            text = f"[BLOCKED] SOV1 staging failed: {type(exc).__name__}: {exc}"
        yield _sse({"type": "token", "text": text})
        yield _sse({"type": "done", "mode": "unified_oracle", "effective_route": "sov1_stage"})
        return

    if lower in ("/send-staged", "/send-staged yes", "/send-staged approve"):
        try:
            from desktop_ai_bridge import TARGETS, load_staged, send_staged

            sp = load_staged()
            if sp is None or sp.sent:
                text = "No staged SOV1 task is waiting. Use `/ask-sov1 <goal>` first."
            elif sp.target != "sov1":
                target_name = TARGETS.get(sp.target, type("T", (), {"name": sp.target})()).name
                text = (
                    f"A staged prompt exists for {target_name}, not SOV1. "
                    "Web confirmation is currently limited to SOV1 hands."
                )
            elif lower == "/send-staged":
                text = (
                    "[SOV1 STAGED TASK - PENDING CONFIRMATION]\n"
                    f"Stage ID: `{sp.id}`\n"
                    f"Risk: {sp.risk}\n"
                    f"Prompt: {sp.prompt[:500]}{'...' if len(sp.prompt) > 500 else ''}\n\n"
                    "To confirm this SOV1 handoff, type `/send-staged yes`."
                )
            else:
                result = send_staged(confirmed=True)
                text = (
                    "[SOV1 HANDOFF CONFIRMED]\n"
                    f"Detail: {result.get('detail', '')}\n"
                    f"Next: {result.get('next_action', '')}\n\n"
                    "No Drive, cloud, credential, commit, push, upload, or delete action was performed by this confirmation."
                )
        except Exception as exc:
            text = f"[BLOCKED] SOV1 handoff failed: {type(exc).__name__}: {exc}"
        yield _sse({"type": "token", "text": text})
        yield _sse({"type": "done", "mode": "unified_oracle", "effective_route": "sov1_handoff"})
        return

    # Live-transmission phrases must be the *dominant* intent — matched as the
    # whole message or its start (after an optional "ORACLE,"), never as a buried
    # substring. Otherwise a carried/sticky status line like "...capture current
    # live transmission state..." hijacks routing for unrelated requests such as
    # "Write a book on my Dad".
    _live_norm = lower.strip()
    if _live_norm.startswith("oracle,"):
        _live_norm = _live_norm[len("oracle,"):].strip()
    _live_start_phrases = (
        "capture current live transmission state",
        "live transmission receipt",
        "i'm transmitting right now",
        "i’m transmitting right now",
        "i am transmitting right now",
    )
    _live_exact = {"i'm live", "i’m live", "i am live", "live mode", "live privacy"}
    _live_request = (
        lower in ("/live", "/live start", "/live status", "/live stop", "live mode", "live privacy")
        or "live_transmission_latest.json" in lower
        or _live_norm in _live_exact
        or any(_live_norm.startswith(p) for p in _live_start_phrases)
    )
    if _live_request:
        try:
            from live_transmission import handle_live_command
            command = lower if lower.startswith("/live") else "/live start"
            result = handle_live_command(command, notes="unified ORACLE live transmission command")
            text = result.get("response_text") or "Live transmission state updated."
            receipt_path = result.get("receipt_path")
            state_path = result.get("state_path")
            if receipt_path:
                text += f"\n\nReceipt: `{receipt_path}`"
            if state_path:
                text += f"\nState: `{state_path}`"
        except Exception as exc:
            text = f"Live transmission capture unavailable: {type(exc).__name__}: {exc}"
        yield _sse({"type": "token", "text": text})
        yield _sse({"type": "done", "mode": "unified_oracle", "effective_route": "capture_lane"})
        return

    if (_unified_route or {}).get("detected_lane") == "guard_lane" and not lower.startswith("/"):
        _pending_guard_route = dict(_unified_route)
        try:
            from unified_oracle_router import write_pending_guard_approval
            _pending_guard_route = write_pending_guard_approval(_unified_route)
        except Exception:
            pass
        if callable(format_lane_boundary):
            text = format_lane_boundary(_unified_route)
        else:
            text = "I routed this to Guard lane. This action requires Noah.Physical approval because it may be irreversible."
        yield _sse({"type": "token", "text": text})
        yield _sse({"type": "done", "mode": "unified_oracle", "effective_route": "guard_lane"})
        return

    if lower in ("/cognition", "cognition", "cognition status"):
        try:
            from cognition_fabric import format_cognition_status
            text = f"```\n{format_cognition_status()}\n```"
        except Exception as exc:
            text = f"ORACLE Cognition Fabric unavailable: {type(exc).__name__}: {exc}"
        yield _sse({"type": "token", "text": text})
        yield _sse({"type": "done", "mode": "unified_oracle", "effective_route": "runtime_status"})
        return

    if lower == "/retrieval-only" or lower.startswith("/retrieval-only "):
        _retrieval_only_mode = True
        query = user_text.strip()[len("/retrieval-only"):].strip() or "retrieval-only status"
        try:
            from cognition_fabric import run_cognition
            result = run_cognition(query, _unified_route, {}, retrieval_only=True)
            text = result["response_text"]
            if query == "retrieval-only status":
                text = "Retrieval-only mode active. No model call will be used for ordinary chat until `/retry-local`.\n\n" + text
        except Exception as exc:
            text = f"Retrieval-only mode active, but retrieval status is unavailable: {type(exc).__name__}: {exc}"
        yield _sse({"type": "token", "text": text})
        yield _sse({"type": "done", "mode": "unified_oracle", "effective_route": "retrieval_only"})
        return

    if lower == "/retry-local" or lower.startswith("/retry-local "):
        _retrieval_only_mode = False
        query = user_text.strip()[len("/retry-local"):].strip() or "Are you there?"
        try:
            from cognition_fabric import run_cognition
            result = await asyncio.to_thread(
                lambda: run_cognition(
                    query,
                    _unified_route,
                    {},
                    local_model_runner=_fabric_local_model_runner,
                    retry_local=True,
                )
            )
            text = result["response_text"]
        except Exception as exc:
            text = f"Local retry unavailable: {type(exc).__name__}: {exc}"
        yield _sse({"type": "token", "text": text})
        yield _sse({"type": "done", "mode": "unified_oracle", "effective_route": "retry_local"})
        return

    if lower in ("/boot", "/boot-status", "boot status", "status line"):
        boot = boot_status_payload()
        text = (
            f"{boot['human_boot_line']}\n\n"
            f"Boot receipt: `{boot['boot_receipt_path']}`\n"
            f"Latest: `{boot['latest_json_path']}`"
        )
        yield _sse({"type": "token", "text": text})
        yield _sse({"type": "done", "mode": _mode})
        return

    if lower in ("/pending", "pending"):
        yield _sse({"type": "token", "text": _pending_list_text()})
        yield _sse({"type": "done", "mode": _mode})
        return

    if lower in ("/ingest-oracle-files", "/ingest-oracle", "ingest oracle files"):
        try:
            from intake_pipeline import build_intake, format_intake_summary
            summary = await asyncio.to_thread(build_intake)
            text = format_intake_summary(summary)
            pending_n = summary.get("pending_promotions", 0)
        except Exception as exc:
            text = f"Governed intake unavailable: {type(exc).__name__}: {exc}"
            pending_n = 0
        lane = "guard_lane" if pending_n else "capture_lane"
        yield _sse({
            "type": "route", "mode": "unified_oracle", "lane": lane,
            "lane_label": "Guard" if pending_n else "Capture",
            "safety_status": "Approval Required" if pending_n else "Safe",
            "conversation_reset": False,
        })
        yield _sse({"type": "token", "text": text})
        yield _sse({"type": "done", "mode": "unified_oracle", "effective_route": "intake_pipeline"})
        return

    if lower.split(" ")[0] == "/alive" and lower in ("/alive", "/alive status", "/alive on", "/alive off"):
        try:
            import alive_loop
            arg = lower[len("/alive"):].strip()
            if arg == "on":
                alive_loop.start()
            elif arg == "off":
                alive_loop.stop()
            text = alive_loop.format_status_line()
        except Exception as exc:
            text = f"Alive loop unavailable: {type(exc).__name__}: {exc}"
        yield _sse({"type": "token", "text": text})
        yield _sse({"type": "done", "mode": "unified_oracle", "effective_route": "alive_loop"})
        return

    if lower.split(" ")[0] in ("/trusted-build", "/session-authorize"):
        cmd = lower.split(" ")[0]
        if lower in (cmd, f"{cmd} status", f"{cmd} on", f"{cmd} off"):
            try:
                from trusted_build import set_trusted_build, format_status_line
                arg = lower[len(cmd):].strip()
                if arg == "on":
                    set_trusted_build(True)
                elif arg == "off":
                    set_trusted_build(False)
                text = format_status_line()
            except Exception as exc:
                text = f"Trusted build / session authorization unavailable: {type(exc).__name__}: {exc}"
            yield _sse({"type": "token", "text": text})
            yield _sse({"type": "done", "mode": "unified_oracle", "effective_route": "trusted_build"})
            return

    if lower in ("/capabilities", "capabilities"):
        try:
            from capability_broker import format_capabilities
            txt = await asyncio.to_thread(format_capabilities, run_smokes=True)
        except Exception as e:
            txt = f"Capability broker unavailable: {e}"
        yield _sse({"type": "token", "text": f"```\n{txt}\n```"})
        yield _sse({"type": "done", "mode": _mode})
        return

    if lower in ("/tool-status", "tool-status"):
        try:
            from capability_broker import format_tool_status
            txt = await asyncio.to_thread(format_tool_status, run_smokes=False)
        except Exception as e:
            txt = f"Tool status unavailable: {e}"
        yield _sse({"type": "token", "text": f"```\n{txt}\n```"})
        yield _sse({"type": "done", "mode": _mode})
        return

    if lower in ("/active-tasks", "active-tasks"):
        try:
            from capability_broker import format_active_tasks
            txt = format_active_tasks()
        except Exception as e:
            txt = f"Active task status unavailable: {e}"
        yield _sse({"type": "token", "text": f"```\n{txt}\n```"})
        yield _sse({"type": "done", "mode": _mode})
        return

    if lower in ("/current-observation", "current-observation", "current observation"):
        try:
            from current_observation import format_current_observation_response
            txt = format_current_observation_response()
        except Exception as e:
            txt = (
                "CURRENT_OBSERVATION\n"
                "receipt_status: unavailable\n"
                "application: UNKNOWN\n"
                "window_title: UNKNOWN\n"
                "visual_observation: UNKNOWN\n"
                "screen_text: UNKNOWN\n"
                f"blocker: {e}"
            )
        yield _sse({"type": "token", "text": f"```\n{txt}\n```"})
        yield _sse({"type": "done", "mode": _mode})
        return

    if lower in ("/doctor", "/audit-runtime", "/check-tools", "/health"):
        try:
            from capability_broker import format_doctor
            txt = await asyncio.to_thread(format_doctor, run_smokes=True)
        except Exception as e:
            txt = f"Capability doctor unavailable: {e}"
        yield _sse({"type": "token", "text": f"```\n{txt}\n```"})
        yield _sse({"type": "done", "mode": _mode})
        return

    if lower in ("/federation", "federation"):
        try:
            from federation import format_status
            txt = await asyncio.to_thread(format_status)
        except Exception as e:
            txt = f"Federation pattern buffer unavailable: {e}"
        yield _sse({"type": "token", "text": f"```\n{txt}\n```"})
        yield _sse({"type": "done", "mode": _mode})
        return

    if lower.startswith("/federation-promote"):
        parts = user_text.strip().split(maxsplit=1)
        cand = parts[1].strip() if len(parts) > 1 else ""
        if not cand:
            txt = "Usage: /federation-promote <candidate_id>  (replicates one staged record into approved canon)"
        else:
            try:
                from federation import promote
                receipt = await asyncio.to_thread(promote, cand, source="memory", approved_by="Noah.Physical")
                txt = json.dumps(receipt, indent=2)
            except Exception as e:
                txt = f"Federation promotion failed: {e}"
        yield _sse({"type": "token", "text": f"```\n{txt}\n```"})
        yield _sse({"type": "done", "mode": _mode})
        return

    if lower in ("/mindcoin", "mindcoin"):
        try:
            from mindcoin import load_ledger, summarize_ledger
            txt = await asyncio.to_thread(lambda: summarize_ledger(*load_ledger()))
        except Exception as e:
            txt = f"MindCoin unavailable: {e}"
        yield _sse({"type": "token", "text": f"```\n{txt}\n```"})
        yield _sse({"type": "done", "mode": _mode})
        return

    if lower in ("/mindcoin-pending", "mindcoin-pending"):
        try:
            from mindcoin import list_pending, load_ledger
            def _pending_mc() -> str:
                _ledger, events = load_ledger()
                pending = list_pending(events)
                if not pending:
                    return "Pending MindCoin events: 0"
                return "\n".join(["Pending MindCoin events: " + str(len(pending))] + ["  " + e.summary_line() for e in pending])
            txt = await asyncio.to_thread(_pending_mc)
        except Exception as e:
            txt = f"MindCoin pending unavailable: {e}"
        yield _sse({"type": "token", "text": f"```\n{txt}\n```"})
        yield _sse({"type": "done", "mode": _mode})
        return

    if lower in ("/mindcoin-drive", "mindcoin-drive"):
        try:
            from mindcoin_drive import format_drive_status
            txt = await asyncio.to_thread(format_drive_status)
        except Exception as e:
            txt = f"MindCoin drive unavailable: {e}"
        yield _sse({"type": "token", "text": f"```\n{txt}\n```"})
        yield _sse({"type": "done", "mode": _mode})
        return

    if lower.startswith("/mindcoin-extract"):
        try:
            from mindcoin_drive import format_extraction
            apply_pending = lower in ("/mindcoin-extract apply", "/mindcoin-extract --apply")
            txt = await asyncio.to_thread(format_extraction, apply=apply_pending)
        except Exception as e:
            txt = f"MindCoin extraction unavailable: {e}"
        yield _sse({"type": "token", "text": f"```\n{txt}\n```"})
        yield _sse({"type": "done", "mode": _mode})
        return

    if lower in ("/remember", "/remember-session"):
        res = await asyncio.to_thread(_run_session_continuity, list(_history), _session_id)
        if "error" in res:
            txt = f"Continuity pipeline error: {res['error']}"
        else:
            txt = (
                f"Session continuity run — **{res.get('written', 0)} fact(s) written** to durable "
                f"memory, {res.get('staged', 0)} staged for approval, {res.get('discarded', 0)} discarded."
            )
        yield _sse({"type": "token", "text": txt})
        yield _sse({"type": "done", "mode": _mode})
        return

    if lower in ("/rebuild-memory-index", "/reindex"):
        try:
            from memory import migrate_memory_index
            r = await asyncio.to_thread(migrate_memory_index, rebuild_if_stale=True)
            txt = f"Memory index rebuilt: {r}"
        except Exception as e:
            txt = f"Reindex error: {e}"
        yield _sse({"type": "token", "text": txt})
        yield _sse({"type": "done", "mode": _mode})
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
        boot = boot_status_payload()
        try:
            from cognition_fabric import get_cognition_status
            fabric = get_cognition_status()
        except Exception:
            fabric = {"status_label": "unavailable", "current_cognition_tier": "unknown"}
        yield _sse({"type": "token", "text": (
            f"**Mode:** UNIFIED ORACLE\n"
            f"**Current lane:** {state.get('lane_label', 'Talk')}\n"
            f"**Safety:** {state.get('safety_status', 'Safe')}\n"
            f"**Cognition:** {boot['cognition_mode']}\n"
            f"**Cognition fabric:** {fabric.get('status_label')} / {fabric.get('current_cognition_tier')}\n"
            f"**Network:** {boot['network_boundary']}\n"
            f"**Boot receipt:** `{boot['boot_receipt_path']}`\n"
            f"**Retrieval-only:** {state.get('retrieval_only')}\n"
            f"**No-route:** {state['no_route']}\n"
            f"**Session:** `{state['session_id']}`"
        )})
        yield _sse({"type": "done"})
        return

    if lower.startswith("/storage-census"):
        # Deterministic Python — governed read-only census. Never routed through the LLM.
        try:
            from storage_census import handle_command
            parts = user_text.strip().split(maxsplit=2)
            sub = parts[1] if len(parts) > 1 else "roots"
            arg = parts[2].strip() if len(parts) > 2 else ""
            text = handle_command(sub, arg)
        except Exception as e:
            text = f"Storage Census error: {type(e).__name__}: {e}"
        yield _sse({"type": "token", "text": text})
        yield _sse({"type": "done"})
        return

    if lower in ("/help", "help"):
        yield _sse({"type": "token", "text": (
            "**ORACLE Commands**\n\n"
            "| Command | Description |\n"
            "|---|---|\n"
            "| `refresh context` | Refresh active local context without resetting conversation |\n"
            "| `show context diff` | Show the latest active context diff |\n"
            "| `/cognition` | Show Cognition Fabric tiers, model/fallback state, and cloud boundary |\n"
            "| `/retrieval-only` | Answer from local runtime/retrieval state without a model call |\n"
            "| `/retry-local` | Try the configured local model once, then fall back honestly |\n"
            "| `/live start` | Capture metadata-only live transmission state and receipt |\n"
            "| `/live status` | Show live privacy posture without starting capture |\n"
            "| `/live stop` | Mark live transmission inactive without raw recording |\n"
            "| `/profile-capsule` | Show/create the local substrate-identity governance profile candidate |\n"
            "| `/no-route` | Force all conversation local |\n"
            "| `/route-on` | Restore external routing |\n"
            "| `/capabilities` | Full broker matrix with live smoke receipts |\n"
            "| `/doctor` | Capability doctor with degraded/blocked tools |\n"
            "| `/tool-status` | Concise broker status from latest receipts |\n"
            "| `/active-tasks` | Broker background task progress |\n"
            "| `/current-observation` | Fresh visual/window receipt state |\n"
            "| `/mindcoin` | MindCoin ledger summary |\n"
            "| `/mindcoin-drive` | Governed MindCoin aspiration view, grounded by MiracleDrive when indexed |\n"
            "| `/mindcoin-extract` | Preview eligible pending MindCoin candidates |\n"
            "| `/self-patch` | Detect and propose a fix for the top issue |\n"
            "| `/self-patch list` | List patch proposals |\n"
            "| `/self-patch approve <id>` | Approve a pending proposal |\n"
            "| `/self-patch implement <id>` | Implement an approved proposal |\n"
            "| `/focus` | Show persistent salience focus |\n"
            "| `/status` | Unified ORACLE lane, safety, and session info |\n"
        )})
        yield _sse({"type": "done"})
        return

    # ── Pending-intent affirmation gate ───────────────────────────────────────
    # Bare confirmations such as "sure" must resolve the most recent pending
    # intent before LCL, route classification, Builder routing, or tool handoff.
    if not lower.startswith("/"):
        try:
            from cognitive_kernel import INTENT_PROCEED_PENDING, KERNEL_ACT, decide_next
            _pending_decision = decide_next(user_text)
            if (
                _pending_decision.intent == INTENT_PROCEED_PENDING
                and _pending_decision.decision == KERNEL_ACT
                and _pending_decision.pending_intent
            ):
                _pending_text = str(_pending_decision.pending_intent.get("text", ""))
                if "/pending" in _pending_text.lower() or "pending" in _pending_text.lower():
                    yield _sse({"type": "token", "text": _pending_list_text()})
                    yield _sse({"type": "done", "mode": _mode})
                    return
                yield _sse({"type": "token", "text": f"Pending intent confirmed: {_pending_text[:220]}"})
                yield _sse({"type": "done", "mode": _mode})
                return
        except Exception:
            pass

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

    if _retrieval_only_mode:
        try:
            from cognition_fabric import run_cognition
            result = run_cognition(user_text, _unified_route, {}, retrieval_only=True)
            reply = result["response_text"]
        except Exception as exc:
            reply = f"Retrieval-only response unavailable: {type(exc).__name__}: {exc}"
        yield _sse({"type": "token", "text": reply})
        yield _sse({"type": "done", "mode": "unified_oracle", "effective_route": "retrieval_only"})
        _history.append({"role": "assistant", "content": reply})
        try:
            from memory import save_message
            save_message(_session_id, "assistant", reply)
        except Exception:
            pass
        return

    if (_unified_route or {}).get("detected_lane") == "build_lane" and not lower.startswith("/"):
        try:
            from cognition_fabric import TIER_PENDING_ACTION, run_cognition
            result = run_cognition(user_text, _unified_route, {}, force_tier=TIER_PENDING_ACTION)
            reply = result["response_text"]
        except Exception as exc:
            reply = f"Build lane pending-action boundary unavailable: {type(exc).__name__}: {exc}"
        yield _sse({"type": "token", "text": reply})
        yield _sse({"type": "done", "mode": "unified_oracle", "effective_route": "build_lane"})
        _history.append({"role": "assistant", "content": reply})
        try:
            from memory import save_message
            save_message(_session_id, "assistant", reply)
        except Exception:
            pass
        return

    try:
        _boot_status = boot_status_payload()
    except Exception as _boot_status_exc:
        _boot_status = {"cognition_mode": "unknown", "error": str(_boot_status_exc)}
    if _boot_status.get("cognition_mode") == "offline_no_model":
        if any(term in lower for term in ("status", "root", "receipt", "retrieval", "capability", "capabilities")):
            receipt = _boot_status.get("receipt") or {}
            retrieval = receipt.get("retrieval") or {}
            reply = (
                f"{_boot_status.get('human_boot_line') or offline_no_model_line()}\n\n"
                f"Runtime root: `{_boot_status.get('runtime_root')}`\n"
                f"State root: `{_boot_status.get('state_root')}`\n"
                f"Boot receipt: `{_boot_status.get('boot_receipt_path')}`\n"
                f"Latest: `{_boot_status.get('latest_json_path')}`\n"
                f"Retrieval: `{retrieval.get('status', 'unknown')}`"
            )
        else:
            reply = offline_no_model_line()
        yield _sse({"type": "token", "text": reply})
        yield _sse({"type": "done", "mode": _mode, "effective_route": "offline_no_model"})
        _history.append({"role": "assistant", "content": reply})
        try:
            from memory import save_message
            save_message(_session_id, "assistant", reply)
        except Exception:
            pass
        return

    # ── Deterministic runtime/sight answers (no LLM, both modes) ──────────────
    # Presence, active task, and sight questions must never hit the slow model or
    # depend on bootstrap. They answer from canonical accessors or a bounded error.
    # ── Show-file: pull exact repo file contents onto the screen (no model) ───
    if lower.startswith("/show-file") or lower.startswith("/talk show-file"):
        raw = user_text.strip()
        prefix = "/talk show-file" if lower.startswith("/talk show-file") else "/show-file"
        arg = raw[len(prefix):].strip()
        try:
            from show_file import format_show
            sf_text = format_show(arg)
        except Exception as exc:
            sf_text = f"Show-file unavailable: {type(exc).__name__}: {exc}"
        yield _sse({"type": "token", "text": sf_text})
        yield _sse({"type": "done", "mode": "unified_oracle", "effective_route": "show_file"})
        return

    # ── Witness Artifact Lane: screenshot drop + witness mode (no model) ──────
    if lower.startswith("/screenshot-drop") or lower.startswith("/witness "):
        try:
            import witness_artifacts as wa
            raw = user_text.strip()
            if lower.startswith("/screenshot-drop"):
                arg = raw[len("/screenshot-drop"):].strip()
                if not arg:
                    wtext = "Usage: `/screenshot-drop <path-to-image>` (optionally `| note`)"
                else:
                    path_part, _, note_part = arg.partition("|")
                    wtext = wa.format_drop(wa.drop_screenshot(path_part.strip(), note=note_part.strip()))
            else:  # /witness <text>
                note_text = raw[len("/witness"):].strip()
                wtext = wa.format_drop(wa.drop_witness_note(note_text)) if note_text else "Usage: `/witness <what you want witnessed>`"
        except Exception as exc:
            wtext = f"Witness artifact lane unavailable: {type(exc).__name__}: {exc}"
        yield _sse({"type": "token", "text": wtext})
        yield _sse({"type": "done", "mode": "unified_oracle", "effective_route": "witness_artifacts"})
        return

    if lower in ("/witness-vault", "/witness-status", "/witness"):
        try:
            import witness_artifacts as wa
            wtext = wa.format_status()
        except Exception as exc:
            wtext = f"Witness artifact lane unavailable: {type(exc).__name__}: {exc}"
        yield _sse({"type": "token", "text": wtext})
        yield _sse({"type": "done", "mode": "unified_oracle", "effective_route": "witness_artifacts"})
        return

    # ── UI Experience: explicit cards + natural-language aliases (no model) ────
    if lower in ("/evidence-vault", "/context-recall", "/ui-patch"):
        try:
            import ui_experience
            if lower == "/evidence-vault":
                ux_text = ui_experience.evidence_vault()
            elif lower == "/context-recall":
                ux_text = ui_experience.context_recall()
            else:
                ux_text = ui_experience.ui_patch()
        except Exception as exc:
            ux_text = f"UI experience layer unavailable: {type(exc).__name__}: {exc}"
        yield _sse({"type": "token", "text": ux_text})
        yield _sse({"type": "done", "mode": "unified_oracle", "effective_route": "ui_experience"})
        return

    try:
        import ui_experience
        _ux = ui_experience.route_phrase(user_text)
    except Exception:
        _ux = None
    if _ux is not None:
        yield _sse({"type": "token", "text": _ux["text"]})
        yield _sse({"type": "done", "mode": "unified_oracle", "effective_route": f"ui_{_ux['kind']}"})
        _history.append({"role": "assistant", "content": _ux["text"]})
        return

    _det = _deterministic_runtime_answer(user_text)
    if _det is not None:
        _det = _strip_routing_artifacts(_det, _mode)
        yield _sse({"type": "token", "text": _det})
        yield _sse({"type": "done", "mode": _mode, "effective_route": "companion"})
        _history.append({"role": "assistant", "content": _det})
        try:
            from memory import save_message
            save_message(_session_id, "assistant", _det)
        except Exception:
            pass
        return

    # ── /review-learned — instant local response, no model needed ────────────
    if user_text.strip().lower() in ("/review-learned", "/review-learned"):
        try:
            from learning import get_review
            review_text = get_review()
        except Exception as e:
            review_text = f"Learning ledger unavailable: {e}"
        yield _sse({"type": "token", "text": review_text})
        yield _sse({"type": "done", "mode": _mode, "effective_route": effective_mode})
        _history.append({"role": "assistant", "content": review_text})
        return

    _t_start = time.time()

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
                    reply = _apply_authority_gate(_grounded_reply, effective_mode, user_text)
                    reply = _apply_current_observation_gate(reply, user_text)
                    # Strip hallucinated "Routing to Claude Code." artifacts — the
                    # web UI has no Claude Code bridge, so the phrase is never a
                    # real action. (The fallback path below already strips; this
                    # grounded path previously skipped it.)
                    reply = _strip_routing_artifacts(reply, _mode)
                    yield _sse({"type": "token", "text": reply})
                    _history.append({"role": "assistant", "content": reply})
                    if len(_history) > 40:
                        _history[:] = _history[-40:]
                    try:
                        from memory import save_message
                        save_message(_session_id, "assistant", reply)
                    except Exception:
                        pass
                    try:
                        from learning import record_interaction
                        record_interaction(user_text, "companion_grounded", effective_mode,
                                           reply_len=len(reply), latency=time.time() - _t_start)
                    except Exception:
                        pass
                    yield _sse({"type": "done", "mode": _mode, "effective_route": effective_mode})
                    return

            try:
                _grounding_block = _bootstrap.system_context_block(current_session=_history[-12:]) if _bootstrap else ""
            except Exception:
                _grounding_block = ""
            try:
                from ambient_watch import get_context_block as _amb_block
                _amb = _amb_block(limit=6)
                if _amb:
                    _grounding_block = (_grounding_block + "\n\n" + _amb).strip()
            except Exception:
                pass
            try:
                from oracle import web_engine_response
                loop = asyncio.get_event_loop()
                reply, engine_history, engine_mode = await loop.run_in_executor(
                    None,
                    lambda: web_engine_response(
                        user_text,
                        history=_history[-12:],
                        session_id=_session_id,
                        mode=effective_mode,
                        no_route=_no_route,
                        grounding_block=_grounding_block,
                    ),
                )
                effective_mode = engine_mode
                reply = _enforce_companion_source_labels(reply)
                reply = _apply_authority_gate(reply, effective_mode, user_text)
                reply = _apply_current_observation_gate(reply, user_text)
                _history = engine_history[-40:]
                reply = _strip_routing_artifacts(reply, _mode)
                reply = _fabric_model_failure_fallback(reply, user_text, _unified_route)
                try:
                    from learning import record_interaction
                    record_interaction(user_text, "companion_engine", effective_mode,
                                       reply_len=len(reply), latency=time.time() - _t_start)
                except Exception:
                    pass
                yield _sse({"type": "token", "text": reply})
                yield _sse({"type": "done", "mode": _mode, "effective_route": effective_mode})
                return
            except Exception as core_err:
                import traceback as _tb
                _tb.print_exc()  # full traceback to server stderr for diagnosis
                reply = f"Core engine error: {type(core_err).__name__}: {core_err}"
                yield _sse({"type": "token", "text": reply})
                yield _sse({"type": "done", "mode": _mode, "effective_route": effective_mode})
                return

            raise RuntimeError("core engine bridge returned unexpectedly")

        except Exception as e:
            import traceback as _tb
            _tb.print_exc()
            reply = f"I'm here, Noah. (Local model error: {type(e).__name__}: {e})"
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
            try:
                import companion_bootstrap as _cb
                _bootstrap = _cb.get()
                _grounding_block = _bootstrap.system_context_block(current_session=_history[-12:])
            except Exception:
                _grounding_block = ""
            from oracle import web_engine_response
            loop = asyncio.get_event_loop()
            reply, engine_history, engine_mode = await loop.run_in_executor(
                None,
                lambda: web_engine_response(
                    user_text,
                    history=_history[-12:],
                    session_id=_session_id,
                    mode=effective_mode,
                    no_route=_no_route,
                    grounding_block=_grounding_block,
                ),
            )
            effective_mode = engine_mode
            reply = _apply_authority_gate(reply, effective_mode, user_text)
            reply = _apply_current_observation_gate(reply, user_text)
            _history = engine_history[-40:]
            reply = _strip_routing_artifacts(reply, _mode)
            reply = _fabric_model_failure_fallback(reply, user_text, _unified_route)
            try:
                from learning import record_interaction
                record_interaction(user_text, "builder_engine", effective_mode,
                                   reply_len=len(reply), latency=time.time() - _t_start)
            except Exception:
                pass
            yield _sse({"type": "token", "text": reply})
            yield _sse({"type": "done", "mode": _mode, "effective_route": effective_mode})
            return
        except Exception as core_err:
            import traceback as _tb
            _tb.print_exc()
            reply = f"Core engine error: {type(core_err).__name__}: {core_err}"
            yield _sse({"type": "token", "text": reply})
            yield _sse({"type": "done", "mode": _mode, "effective_route": effective_mode})
            return

        raise RuntimeError("core engine bridge returned unexpectedly")

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

    yield _sse({"type": "done", "mode": _mode, "effective_route": effective_mode})


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = ROOT / "ui" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/console", response_class=HTMLResponse)
async def console_page():
    """Serve the starship console (live capability data, no hardcoded lights)."""
    html_path = ROOT / "ui" / "console.html"
    if not html_path.exists():
        return HTMLResponse("<h1>console.html not present</h1>", status_code=404)
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/miracledrive", response_class=HTMLResponse)
async def miracledrive():
    html_path = ROOT / "ui" / "miracledrive.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/drive-state")
async def api_drive_state():
    """Real MiracleDrive filesystem state — no LLM, no fabrication."""
    try:
        from miracledrive_index import drive_state
        return JSONResponse(drive_state())
    except Exception as e:
        return JSONResponse({"error": str(e), "total_files": 0}, status_code=500)


@app.get("/api/drive-search")
async def api_drive_search(q: str = "", limit: int = 20):
    """Search the MiracleDrive index."""
    try:
        from miracledrive_index import query as md_query
        results = md_query(q, limit=limit)
        return JSONResponse({"results": results, "count": len(results)})
    except Exception as e:
        return JSONResponse({"error": str(e), "results": []}, status_code=500)


@app.get("/api/drive-read")
async def api_drive_read(path: str = ""):
    """Read a specific file from MiracleDrive. ORACLE has full access."""
    if not path:
        return JSONResponse({"error": "path required"}, status_code=400)
    try:
        from miracledrive_index import read_file
        return JSONResponse(read_file(path))
    except Exception as e:
        return JSONResponse({"error": str(e), "ok": False}, status_code=500)


@app.get("/api/diagnostics/runtime")
async def api_runtime_diagnostics():
    """Read-only diagnostic frame for the active canonical ORACLE backend."""
    return JSONResponse(_runtime_diagnostics())


@app.get("/api/context/obs")
async def api_obs_context():
    """Read-only OBS runtime context. No raw video/audio, no OBS control."""
    try:
        from obs_runtime_context import get_obs_context
        return JSONResponse(get_obs_context())
    except Exception as exc:
        return JSONResponse({
            "available": False,
            "last_obs_error": f"{type(exc).__name__}: {exc}",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "raw_video_stored": False,
            "raw_audio_stored": False,
            "write_permissions": False,
        })


@app.get("/api/see/status")
async def api_see_status():
    """Honest status of ORACLE's webcam vision. No camera is opened server-side."""
    try:
        from oracle_sight import sight_available
        return JSONResponse(sight_available())
    except Exception as exc:
        return JSONResponse({
            "available": False,
            "model": None,
            "error": f"{type(exc).__name__}: {exc}",
            "raw_frame_stored": False,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        })


@app.get("/api/current-observation")
async def api_current_observation():
    """Fresh current visual/window observation receipt state. No LLM fallback."""
    try:
        from current_observation import current_observation_state
        return JSONResponse(current_observation_state())
    except Exception as exc:
        return JSONResponse({
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "receipt_id": None,
            "receipt_status": "unavailable",
            "fresh": False,
            "fields": {
                "application": {"value": None, "rendered_value": "UNKNOWN"},
                "window_title": {"value": None, "rendered_value": "UNKNOWN"},
                "visual_observation": {"value": None, "rendered_value": "UNKNOWN"},
                "screen_text": {"value": None, "rendered_value": "UNKNOWN"},
            },
            "blocker": f"{type(exc).__name__}: {exc}",
        }, status_code=500)


@app.get("/api/sourcemap/rendered-reality")
async def api_rendered_reality_status():
    """Consent state only. Does not read OBS/window context while OFF."""
    try:
        from rendered_reality_witness import get_witness_status
        return JSONResponse(get_witness_status())
    except Exception as exc:
        return JSONResponse({
            "name": "RenderedReality Live Witness",
            "mode": "off",
            "enabled": False,
            "error": f"{type(exc).__name__}: {exc}",
        }, status_code=500)


@app.post("/api/sourcemap/rendered-reality/mode")
async def api_rendered_reality_mode(request: Request):
    """Set consent mode. Enabling does not capture screen/audio/video/keys."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        from rendered_reality_witness import set_witness_mode
        return JSONResponse(set_witness_mode(str(body.get("mode") or "off")))
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.post("/api/sourcemap/rendered-reality/refresh")
async def api_rendered_reality_refresh():
    """Refresh bounded live metadata only if witness consent is enabled."""
    try:
        from rendered_reality_witness import refresh_live_context
        return JSONResponse(refresh_live_context())
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.post("/api/sourcemap/rendered-reality/receipt")
async def api_rendered_reality_receipt(request: Request):
    """Write one RenderedReality session receipt only when consent is enabled."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        from rendered_reality_witness import write_session_receipt
        receipt = write_session_receipt(notes=str(body.get("notes") or ""))
        return JSONResponse(receipt)
    except PermissionError as exc:
        return JSONResponse({"error": str(exc), "receipt_written": False}, status_code=403)
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.get("/api/sourcemap/lootdrops")
async def api_lootdrops_status():
    """Local symbolic LootDrop status. No cloud, no upload, no financial value."""
    try:
        from lootdrop_artifacts import status_payload
        return JSONResponse(status_payload())
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.post("/api/sourcemap/lootdrops/manual")
async def api_lootdrops_manual(request: Request):
    """Create the manual Myrmidon's Signet continuity artifact locally."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        from lootdrop_artifacts import create_manual_lootdrop
        allowed = {
            key: body.get(key)
            for key in (
                "artifact_type",
                "title",
                "source_context",
                "evidence_state",
                "human_authority",
                "description",
                "symbolic_stats",
                "linked_files",
                "linked_receipts",
                "mindcoin_award",
                "notes",
            )
            if key in body
        }
        return JSONResponse(create_manual_lootdrop(**allowed))
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.post("/api/sourcemap/lootdrops/receipt")
async def api_lootdrops_receipt():
    """Write a local receipt for the latest LootDrop artifact."""
    try:
        from lootdrop_artifacts import latest_lootdrop_artifact, write_lootdrop_receipt
        latest = latest_lootdrop_artifact()
        if not latest:
            return JSONResponse({"error": "No LootDrop artifact exists yet."}, status_code=404)
        return JSONResponse(write_lootdrop_receipt(latest))
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.post("/api/sourcemap/lootdrops/award")
async def api_lootdrops_award():
    """Append a symbolic nonfinancial MindCoin JSONL event for the latest LootDrop."""
    try:
        from lootdrop_artifacts import award_mindcoin_for_lootdrop, latest_lootdrop_artifact, write_lootdrop_receipt
        latest = latest_lootdrop_artifact()
        if not latest:
            return JSONResponse({"error": "No LootDrop artifact exists yet."}, status_code=404)
        receipt = write_lootdrop_receipt(latest)
        return JSONResponse(award_mindcoin_for_lootdrop(latest, receipt))
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.get("/api/sourcemap/witness-governance")
async def api_witness_governance_status():
    """SourceMap Witness Governance doctrine/status. No observation is performed."""
    try:
        from sourcemap_witness_governance import status_payload
        return JSONResponse(status_payload())
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.post("/api/sourcemap/witness-governance/command")
async def api_witness_governance_command(request: Request):
    """Apply an explicit governance command and write receipts when required."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        from sourcemap_witness_governance import handle_command
        return JSONResponse(handle_command(
            str(body.get("command") or ""),
            source_reference=str(body.get("source_reference") or ""),
            linked_path=str(body.get("linked_path") or ""),
            artifact_type=str(body.get("artifact_type") or ""),
            why_it_mattered=str(body.get("why_it_mattered") or ""),
            notes=str(body.get("notes") or ""),
        ))
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.get("/api/sourcemap/witness-governance/known")
async def api_witness_governance_known():
    """Report known local references without claiming content understanding."""
    try:
        from sourcemap_witness_governance import show_me_what_you_know
        return JSONResponse(show_me_what_you_know())
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.get("/api/sourcemap/obs-transcript")
async def api_obs_transcript_status():
    """Local-only OBS transcript status. No media upload or cloud STT fallback."""
    try:
        from obs_live_transcript import status_payload
        return JSONResponse(status_payload())
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.post("/api/sourcemap/obs-transcript/pull")
async def api_obs_transcript_pull(request: Request):
    """Pull an existing local transcript sidecar or write a blocker receipt."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        from obs_live_transcript import pull_active_transcript
        return JSONResponse(pull_active_transcript(notes=str(body.get("notes") or "")))
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.post("/api/sourcemap/obs-transcript/receipt")
async def api_obs_transcript_receipt(request: Request):
    """Write a local receipt for current OBS transcript readiness/status."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        from obs_live_transcript import write_status_receipt
        return JSONResponse(write_status_receipt(notes=str(body.get("notes") or "")))
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


def _multipart_unavailable(exc: Exception) -> JSONResponse:
    return JSONResponse({
        "error": f"multipart form parsing unavailable: {type(exc).__name__}: {exc}",
        "needs": "python-multipart",
        "hint": "pip install python-multipart, then restart the ORACLE server",
    }, status_code=503)


async def _intake_items_from_form(form, *, use_relpaths: bool):
    """Decode Starlette UploadFile entries into file_intake.FileInput items."""
    from file_intake import FileInput
    uploads = form.getlist("files")
    relpaths: list[str] = []
    if use_relpaths:
        raw = form.get("relpaths") or ""
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    relpaths = [str(p) for p in parsed]
            except Exception:
                relpaths = []
    items: list[Any] = []
    for idx, up in enumerate(uploads):
        try:
            data = await up.read() if hasattr(up, "read") else b""
        except Exception:
            data = b""
        name = getattr(up, "filename", None) or f"upload_{idx}"
        rel = (relpaths[idx] if idx < len(relpaths) else name) if use_relpaths else None
        items.append(FileInput(filename=name, data=data, relative_path=rel))
    return items


@app.post("/api/intake/files")
async def api_intake_files(request: Request):
    """Local multipart file intake. No cloud upload, no Drive sync, no commit/push."""
    try:
        form = await request.form()
    except Exception as exc:
        return _multipart_unavailable(exc)
    try:
        from file_intake import run_intake
        items = await _intake_items_from_form(form, use_relpaths=False)
        if not items:
            return JSONResponse({"error": "no files received"}, status_code=400)
        return JSONResponse(run_intake(items, is_folder=False))
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.post("/api/intake/folder")
async def api_intake_folder(request: Request):
    """Local folder intake; preserves browser-provided relative paths."""
    try:
        form = await request.form()
    except Exception as exc:
        return _multipart_unavailable(exc)
    try:
        from file_intake import run_intake
        items = await _intake_items_from_form(form, use_relpaths=True)
        if not items:
            return JSONResponse({"error": "no files received"}, status_code=400)
        return JSONResponse(run_intake(items, is_folder=True))
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.get("/api/intake/latest")
async def api_intake_latest():
    """Latest intake manifest + intake roots/limits. Read-only."""
    try:
        from file_intake import read_latest_manifest, status_payload
        payload = status_payload()
        payload["manifest"] = read_latest_manifest()
        return JSONResponse(payload)
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.post("/api/intake/review")
async def api_intake_review():
    """Review intake state grouped by status and risk. Read-only."""
    try:
        from file_intake import review_intake
        return JSONResponse(review_intake())
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.post("/api/intake/promote")
async def api_intake_promote(request: Request):
    """Mark an intake entry promoted (Noah.Physical approval). No content load."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        from file_intake import promote_intake
        intake_id = str(body.get("intake_id") or "")
        if not intake_id:
            return JSONResponse({"error": "intake_id required"}, status_code=400)
        out = promote_intake(intake_id, override_quarantine=bool(body.get("override")))
        return JSONResponse(out, status_code=200 if out.get("ok") else 400)
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.post("/api/intake/quarantine")
async def api_intake_quarantine(request: Request):
    """Mark an intake entry quarantined and write a receipt."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        from file_intake import quarantine_intake
        intake_id = str(body.get("intake_id") or "")
        if not intake_id:
            return JSONResponse({"error": "intake_id required"}, status_code=400)
        out = quarantine_intake(intake_id)
        return JSONResponse(out, status_code=200 if out.get("ok") else 400)
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.get("/api/storage-census/roots")
async def api_storage_census_roots():
    """Governed storage roots: approved vs known-not-scanned. Read-only."""
    try:
        from storage_census import roots_payload
        out = roots_payload()
        return JSONResponse(out, status_code=503 if out.get("blocked") else 200)
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.post("/api/storage-census/scan-approved")
async def api_storage_census_scan():
    """Scan approved roots only. Discovery metadata; no ingestion, no mutation."""
    try:
        from storage_census import run_census
        out = run_census()
        return JSONResponse(out, status_code=503 if out.get("blocked") else 200)
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.get("/api/storage-census/report")
async def api_storage_census_report():
    """Latest census report payload. Read-only."""
    try:
        from storage_census import report_payload
        out = report_payload()
        return JSONResponse(out, status_code=503 if out.get("blocked") else 200)
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.get("/api/storage-census/risks")
async def api_storage_census_risks():
    """Credential-risk COUNT only. Never returns paths or contents."""
    try:
        from storage_census import risks_payload
        out = risks_payload()
        return JSONResponse(out, status_code=503 if out.get("blocked") else 200)
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.post("/api/storage-census/approve-root")
async def api_storage_census_approve(request: Request):
    """Approve a known root for deeper scanning (Noah.Physical authority)."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        from storage_census import approve_root
        path = str(body.get("path") or "")
        if not path:
            return JSONResponse({"error": "path required"}, status_code=400)
        out = approve_root(path)
        return JSONResponse(out, status_code=200 if out.get("ok") else 400)
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.post("/api/storage-census/reject-root")
async def api_storage_census_reject(request: Request):
    """Reject a root so it is never scanned."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        from storage_census import reject_root
        path = str(body.get("path") or "")
        if not path:
            return JSONResponse({"error": "path required"}, status_code=400)
        out = reject_root(path)
        return JSONResponse(out, status_code=200 if out.get("ok") else 400)
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.get("/api/unified-oracle/route")
async def api_unified_oracle_route():
    """Current unified ORACLE lane/safety status."""
    try:
        from unified_oracle_router import latest_route_status
        return JSONResponse(latest_route_status())
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.post("/api/unified-oracle/classify")
async def api_unified_oracle_classify(request: Request):
    """Classify a message into an internal lane and write a local route record."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        from unified_oracle_router import route_message
        return JSONResponse(route_message(str(body.get("message") or ""), notes="manual UI route classification"))
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.get("/api/active-context")
async def api_active_context_status():
    """Active Context Sync status. Read-only."""
    try:
        from active_context_sync import status_payload
        return JSONResponse(status_payload())
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.post("/api/active-context/refresh")
async def api_active_context_refresh(request: Request):
    """Refresh active context from local state without resetting conversation."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        from active_context_sync import refresh_active_context
        result = refresh_active_context(notes=str(body.get("notes") or "manual API refresh"))
        global _active_context_latest
        _active_context_latest = result.get("snapshot")
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.get("/api/active-context/diff")
async def api_active_context_diff():
    """Return the latest active context diff."""
    try:
        from active_context_sync import load_active_context_latest
        latest = load_active_context_latest()
        return JSONResponse({
            "latest_context_path": str(Path(r"C:\Oracle\state") / "context" / "active_context_latest.json"),
            "diff": (latest or {}).get("diff") if latest else None,
            "conversation_reset": False,
        })
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.get("/api/profile-capsule/substrate-identity-governance")
async def api_profile_capsule_substrate_identity_governance():
    """Read the local profile capsule candidate. No durable memory promotion."""
    try:
        from profile_capsule import status_payload
        return JSONResponse(status_payload(create=False))
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.post("/api/profile-capsule/substrate-identity-governance")
async def api_create_profile_capsule_substrate_identity_governance(request: Request):
    """Create the local profile capsule candidate and receipt only."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        from profile_capsule import status_payload
        return JSONResponse(status_payload(create=True, notes=str(body.get("notes") or "api profile capsule request")))
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.post("/api/camera/authorize")
async def api_camera_authorize(request: Request):
    """
    Create one bounded, in-memory camera authorization for this session.
    Called when Noah explicitly starts the camera. No durable storage.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    device_id = (body.get("device_id") or None)
    try:
        from camera_authorization import create_authorization
        record = create_authorization(session_id=_session_id, device_id=device_id)
        return JSONResponse({
            "ok": True,
            "authorization_id": record["authorization_id"],
            "session_id": record["session_id"],
            "device_id": record["device_id"],
            "created_at": record["created_at"],
        })
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.post("/api/camera/stop")
async def api_camera_stop(request: Request):
    """Invalidate a camera authorization (camera stopped / track ended / unload)."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    auth_id = body.get("authorization_id")
    try:
        from camera_authorization import invalidate
        invalidated = invalidate(auth_id)
        return JSONResponse({"ok": True, "invalidated": bool(invalidated)})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.post("/api/see")
async def api_see(request: Request):
    """
    LOOK ONCE: describe exactly one explicitly-requested camera frame.

    Fail-closed. The request must carry a valid camera authorization for this
    session; otherwise the vision model is never invoked. One successful call
    produces exactly one receipt, written BEFORE the caption is returned for
    display. The frame is analyzed in memory and discarded — never stored.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"available": False, "error": "invalid JSON body"}, status_code=400)

    image = (body.get("image") or "").strip()
    if not image:
        return JSONResponse({"available": False, "error": "no image supplied"}, status_code=400)

    authorization_id = body.get("authorization_id")
    session_id = body.get("session_id")
    device_id = body.get("device_id") or None
    track_label = body.get("track_label") or None
    correlation_id = body.get("correlation_id") or None

    # ── Authorization gate — reject without touching the vision model ─────────
    try:
        from camera_authorization import validate as _cam_validate
        ok, reason = _cam_validate(authorization_id, session_id, device_id)
    except Exception as exc:
        ok, reason = False, f"authorization_error:{type(exc).__name__}"
    if not ok:
        return JSONResponse({
            "available": False,
            "rejected": True,
            "error": f"authorization_rejected:{reason}",
            "raw_frame_stored": False,
        }, status_code=403)

    from camera_receipt import build_receipt, save_receipt

    def _publish(receipt: dict) -> JSONResponse:
        """Write the receipt first; only then expose the observation."""
        try:
            save_receipt(receipt)
        except Exception as save_exc:
            # No receipt → no published caption.
            return JSONResponse({
                "available": False,
                "rejected": False,
                "error": f"receipt_write_failed:{type(save_exc).__name__}: {save_exc}",
                "raw_frame_stored": False,
            }, status_code=500)
        published = bool(receipt.get("published_to_chat"))
        return JSONResponse({
            "available": published,
            "observation": receipt.get("observation_text") if published else None,
            "unknown": receipt.get("observation_text") == "UNKNOWN" or receipt.get("error") is not None,
            "observation_id": receipt.get("observation_id"),
            "receipt_id": receipt.get("observation_id"),
            "correlation_id": receipt.get("correlation_id"),
            "evidence_class": receipt.get("evidence_class"),
            "confidence": receipt.get("confidence"),
            "device_id": receipt.get("device_id"),
            "track_label": receipt.get("track_label"),
            "model": receipt.get("model"),
            "raw_frame_stored": False,
            "error": receipt.get("error"),
        })

    try:
        from oracle_sight import describe_image
        result = await asyncio.to_thread(describe_image, image)

        # Unusable (dark/blocked) frame → UNKNOWN, model already skipped.
        if result.get("unknown") or not result.get("observation"):
            receipt = build_receipt(
                observation_text="UNKNOWN",
                correlation_id=correlation_id,
                session_id=session_id,
                authorization_id=authorization_id,
                device_id=device_id,
                track_label=track_label,
                model=result.get("model"),
                confidence="none",
                published_to_chat=True,
                error=result.get("error") or "no_observation",
            )
            return _publish(receipt)

        receipt = build_receipt(
            observation_text=str(result.get("observation")).strip(),
            correlation_id=correlation_id,
            session_id=session_id,
            authorization_id=authorization_id,
            device_id=device_id,
            track_label=track_label,
            model=result.get("model"),
            confidence="model_unverified_inference",
            published_to_chat=True,
        )
        return _publish(receipt)
    except Exception as exc:
        return JSONResponse({
            "available": False,
            "observation": None,
            "error": f"{type(exc).__name__}: {exc}",
            "raw_frame_stored": False,
        }, status_code=500)


@app.get("/api/continuity/frame")
async def api_continuity_frame():
    """Read-only restart-safe continuity frame. No persistence side effects."""
    return JSONResponse(_continuity_frame(persist=False))


@app.get("/api/state")
async def api_operational_state():
    """
    ORACLE's live operational world-model: VERIFIED (git/runtime/vision/pending)
    reconciled now, with DECLARED narrative labeled and staleness-checked. No LLM.
    """
    try:
        from operational_state import build_operational_state
        # git/subprocess can be slow on Drive — run off the event loop.
        state = await asyncio.to_thread(build_operational_state, mode_provider=_get_mode_state)
        return JSONResponse(state)
    except Exception as exc:
        return JSONResponse({
            "error": f"{type(exc).__name__}: {exc}",
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }, status_code=500)


@app.post("/chat")
async def chat(request: Request):
    try:
        body = await request.json()
    except Exception:
        # Tolerant fallback for mildly malformed / mis-encoded JSON bodies
        # (e.g. PowerShell Invoke-RestMethod mangling UTF-8 curly quotes in long here-strings).
        try:
            raw = await request.body()
            body = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception as exc:
            import traceback as _tb
            _tb.print_exc()
            return JSONResponse({"error": f"invalid JSON body: {type(exc).__name__}"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "body must be a JSON object"}, status_code=400)
    user_text = (body.get("message") or "").strip()
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
    """Conversation history for UI rehydrate.

    Live in-process history wins. If it is empty — a fresh page load, a UI
    refresh, or a server restart (which opens a new empty session) — fall back to
    the durable store so the last real conversation comes back instead of looking
    like amnesia. This is what makes a refresh retain the thread.
    """
    if _history:
        return JSONResponse({"history": _history, "session_id": _session_id, "source": "live"})
    try:
        import memory
        with memory.get_conn() as conn:
            row = conn.execute(
                "SELECT session_id FROM messages ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row:
            prior = memory.get_recent_messages(row["session_id"], limit=40)
            return JSONResponse({
                "history": prior,
                "session_id": row["session_id"],
                "source": "durable",
            })
    except Exception as exc:
        return JSONResponse({"history": [], "session_id": _session_id, "source": f"error:{type(exc).__name__}: {exc}"})
    return JSONResponse({"history": [], "session_id": _session_id, "source": "empty"})


@app.get("/health")
async def health():
    boot = boot_status_payload()
    return JSONResponse({
        "ok": True,
        "cognition_mode": boot.get("cognition_mode"),
        "network_boundary": boot.get("network_boundary"),
        "boot_receipt_path": boot.get("boot_receipt_path"),
    })


@app.get("/api/boot")
async def api_boot():
    return JSONResponse(boot_status_payload())


@app.get("/api/cognition")
async def api_cognition():
    """Read-only Cognition Fabric status; no model call, no cloud call."""
    try:
        from cognition_fabric import get_cognition_status
        return JSONResponse(get_cognition_status())
    except Exception as exc:
        return JSONResponse({
            "current_cognition_tier": "unknown",
            "status_label": "unavailable",
            "cloud_api_used": False,
            "conversation_reset": False,
            "error": f"{type(exc).__name__}: {exc}",
        }, status_code=500)


@app.get("/api/mode")
async def mode():
    state = _get_mode_state()
    try:
        boot = boot_status_payload()
        state["cognition_mode"] = boot.get("cognition_mode")
        state["network_boundary"] = boot.get("network_boundary")
        state["boot_receipt_path"] = boot.get("boot_receipt_path")
    except Exception:
        pass
    return JSONResponse(state)


@app.get("/api/law-life")
async def api_law_life():
    """Read-only USER.AI law layer + active_npc life layer status."""
    try:
        from law_life_status import build_law_life_status
        return JSONResponse(build_law_life_status())
    except Exception as exc:
        return JSONResponse({
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "law": {"status": "unavailable"},
            "life": {"status": "unavailable"},
            "bridge": {"server_bridge_status": "unavailable"},
            "observation": {"last_observation": None},
            "error": f"{type(exc).__name__}: {exc}",
        }, status_code=500)


@app.get("/api/presence")
async def api_presence():
    """
    ORACLE's live state for the always-visible presence rail: authoritative mode,
    what intent she's carrying, how much she remembers, and her last observation.
    Read-only; cheap; safe to poll.
    """
    out = {
        "mode": "unified_oracle",
        "legacy_mode": _mode,
        "no_route": _no_route,
        "session_id": _session_id,
        "current_lane": None,
        "lane_label": None,
        "safety_status": None,
        "pending_intent": None,
        "next_safe_action": None,
        "memory_count": None,
        "last_observation": None,
        "law_life": None,
        "boot": None,
        "cognition_fabric": None,
        "live_transmission": None,
    }
    try:
        mode_state = _get_mode_state()
        out["current_lane"] = mode_state.get("current_lane")
        out["lane_label"] = mode_state.get("lane_label")
        out["safety_status"] = mode_state.get("safety_status")
    except Exception:
        pass
    try:
        boot = boot_status_payload()
        out["boot"] = {
            "cognition_mode": boot.get("cognition_mode"),
            "network_boundary": boot.get("network_boundary"),
            "boot_receipt_path": boot.get("boot_receipt_path"),
            "warning_count": len(boot.get("warnings") or []),
        }
    except Exception:
        pass
    try:
        from cognition_fabric import get_cognition_status
        fabric = get_cognition_status()
        out["cognition_fabric"] = {
            "status_label": fabric.get("status_label"),
            "current_cognition_tier": fabric.get("current_cognition_tier"),
            "last_local_model_status": fabric.get("last_local_model_status"),
            "last_timeout": fabric.get("last_timeout"),
            "last_fallback_reason": fabric.get("last_fallback_reason"),
            "cloud_api_used": False,
            "conversation_reset": False,
        }
    except Exception as exc:
        out["cognition_fabric"] = {
            "status_label": "unavailable",
            "current_cognition_tier": "unknown",
            "cloud_api_used": False,
            "conversation_reset": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    try:
        from live_transmission import read_live_state
        live_state = read_live_state()
        out["live_transmission"] = {
            "live_transmission_active": bool(live_state.get("live_transmission_active")),
            "session_state": live_state.get("session_state"),
            "privacy_posture": live_state.get("privacy_posture"),
            "recommended_mode": live_state.get("recommended_mode"),
            "raw_recording": live_state.get("raw_recording", "off"),
            "state_path": live_state.get("state_path"),
            "conversation_reset": False,
            "cloud_api_used": False,
            "upload": False,
            "sync": False,
            "drive_modified": False,
            "onedrive_modified": False,
            "git_commit": False,
            "git_push": False,
        }
    except Exception as exc:
        out["live_transmission"] = {
            "live_transmission_active": False,
            "privacy_posture": "unknown",
            "raw_recording": "off",
            "error": f"{type(exc).__name__}: {exc}",
        }
    try:
        from cognitive_kernel import load_kernel_state
        ks = load_kernel_state()
        pi = ks.get("pending_intent")
        if isinstance(pi, dict):
            out["pending_intent"] = str(pi.get("text") or "")[:160] or None
        out["next_safe_action"] = ks.get("next_safe_action")
    except Exception:
        pass
    try:
        from light_compression import list_memories
        out["memory_count"] = len(list_memories(limit=100000))
    except Exception:
        pass
    try:
        from law_life_status import build_law_life_status
        status = build_law_life_status()
        out["law_life"] = {
            "law_status": ((status.get("law") or {}).get("status")),
            "life_status": ((status.get("life") or {}).get("status")),
            "bridge_status": ((status.get("bridge") or {}).get("server_bridge_status")),
            "runtime_instantiation_status": ((status.get("bridge") or {}).get("runtime_instantiation_status")),
            "seed_candidate_count": ((status.get("bridge") or {}).get("seed_candidate_count")),
            "screen_receipt_status": (((status.get("observation") or {}).get("current_observation") or {}).get("receipt_status")),
            "camera_receipt_status": (((status.get("observation") or {}).get("camera_observation") or {}).get("receipt_status")),
        }
        last = ((status.get("observation") or {}).get("last_observation"))
        if isinstance(last, dict):
            raw_text = str(last.get("text") or "UNKNOWN")
            display_text = "UNKNOWN" if raw_text.strip().upper() == "UNKNOWN" else "receipt present"
            out["last_observation"] = {
                "source": last.get("source"),
                "text": display_text,
                "id": last.get("id"),
                "at": last.get("at"),
            }
    except Exception:
        pass
    return JSONResponse(out)


@app.post("/api/clear")
async def clear():
    global _history, _session_id
    # Session boundary: capture durable memory from the closing session first.
    try:
        if _history:
            await asyncio.to_thread(_run_session_continuity, list(_history), _session_id)
    except Exception:
        pass
    _history = []
    try:
        from memory import new_session
        _session_id = new_session()
    except Exception:
        _session_id = uuid.uuid4().hex[:8]
    return JSONResponse({"ok": True, "session_id": _session_id})


@app.get("/api/ambient")
async def api_ambient(limit: int = 20):
    """Recent ambient captures — clipboard, screenshots, OBS recordings."""
    try:
        from ambient_watch import get_recent
        return JSONResponse({"events": get_recent(limit=limit)})
    except Exception as e:
        return JSONResponse({"events": [], "error": str(e)})


@app.get("/api/learned-ui")
async def learned_ui():
    """Personalized UI hints derived from Noah's interaction history."""
    try:
        from learning import get_ui_hints, get_chip_order
        hints = get_ui_hints()
        hints["chip_order"] = get_chip_order()
        return JSONResponse(hints)
    except Exception as e:
        return JSONResponse({"error": str(e), "chip_order": []}, status_code=500)


# ── Daemon/Hotkey integration endpoints ────────────────────────────────────────

_pending_notifications = []
_paused = False

@app.post("/api/notify")
async def notify(request: Request):
    """Receive notifications from event daemon."""
    global _pending_notifications
    body = await request.json()
    message = body.get("message", "")
    urgency = body.get("urgency", 0.5)
    
    # Queue notification for UI to pick up
    _pending_notifications.append({
        "message": message,
        "urgency": urgency,
        "timestamp": time.time(),
    })
    
    # Keep last 50
    if len(_pending_notifications) > 50:
        _pending_notifications.pop(0)
    
    return JSONResponse({"ok": True, "queued": len(_pending_notifications)})


@app.get("/api/notifications")
async def get_notifications():
    """Retrieve queued notifications."""
    global _pending_notifications
    notifs = _pending_notifications[-10:]  # Last 10
    return JSONResponse({"notifications": notifs})


@app.post("/api/approve")
async def approve(request: Request):
    """Handle hotkey approval action."""
    body = await request.json()
    action = body.get("action", "")
    print(f"[APPROVAL via hotkey] {action}")
    return JSONResponse({"ok": True, "action": action})


@app.post("/api/pause")
async def pause():
    """Emergency stop: pause ORACLE daemon."""
    global _paused
    _paused = True
    print("[PAUSED] ORACLE daemon paused (Ctrl+Shift+X)")
    return JSONResponse({"ok": True, "paused": _paused})


@app.post("/api/resume")
async def resume():
    """Resume ORACLE daemon."""
    global _paused
    _paused = False
    print("[RESUMED] ORACLE daemon resumed")
    return JSONResponse({"ok": True, "paused": _paused})


@app.get("/api/status")
async def status_endpoint():
    """Get daemon status."""
    boot = boot_status_payload()
    return JSONResponse({
        "paused": _paused,
        "notifications_queued": len(_pending_notifications),
        "session_id": _session_id,
        "boot": {
            "cognition_mode": boot.get("cognition_mode"),
            "verified_model_name": boot.get("verified_model_name"),
            "verified_local_engine": boot.get("verified_local_engine"),
            "network_boundary": boot.get("network_boundary"),
            "boot_receipt_path": boot.get("boot_receipt_path"),
            "latest_json_path": boot.get("latest_json_path"),
            "human_boot_line": boot.get("human_boot_line"),
            "warnings": boot.get("warnings", []),
        },
    })


@app.get("/api/capabilities")
async def capabilities_endpoint(smokes: bool = False):
    """Honest ship status for the Operator Console.

    Returns the real capability-broker matrix as JSON — no decorative "online".
    Each item reports its verified current_status, the sandbox level it is
    permitted to operate at, and the blocker (if any). `?smokes=true` re-runs the
    non-destructive smoke probes (slower) instead of reading last receipts.
    """
    from datetime import datetime as _dt, timezone as _tz
    try:
        from capability_broker import discover_capabilities
        statuses = await asyncio.to_thread(discover_capabilities, run_smokes=smokes)
    except Exception as exc:
        return JSONResponse(
            {"error": f"{type(exc).__name__}: {exc}", "capabilities": []},
            status_code=500,
        )
    items = [s.to_dict() for s in statuses]
    summary = {
        "total": len(statuses),
        "verified": sum(1 for s in statuses if s.current_status == "verified"),
        "degraded": sum(1 for s in statuses if s.current_status == "degraded"),
        "blocked": sum(1 for s in statuses if s.current_status == "blocked"),
        "smokes_run": bool(smokes),
    }
    return JSONResponse({
        "observed_at": _dt.now(_tz.utc).isoformat(),
        "summary": summary,
        "capabilities": items,
    })


@app.get("/api/federation")
async def federation_status_endpoint():
    """Live Federation pattern-buffer status for the operator console.

    Reports the approved-canon size, staged candidate records (with verbatim
    preview), and the doctrine. Read-only — no record is promoted here.
    """
    try:
        from federation import status as _fed_status, list_candidates
        st = await asyncio.to_thread(_fed_status)
        st["candidates"] = await asyncio.to_thread(list_candidates, 50)
        return JSONResponse(st)
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.post("/api/federation/promote")
async def federation_promote_endpoint(request: Request):
    """Replicate one staged candidate into approved canon (the replicator's pulse).

    Body: {"id": "<candidate_id>", "source": "memory", "approved_by": "Noah.Physical"}
    Verbatim, secret-guarded, idempotent, audited by core/federation.py.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    candidate_id = (body or {}).get("id", "")
    source = (body or {}).get("source", "memory")
    approved_by = (body or {}).get("approved_by", "Noah.Physical")
    if not candidate_id:
        return JSONResponse({"ok": False, "error": "missing candidate id"}, status_code=400)
    try:
        from federation import promote
        receipt = await asyncio.to_thread(promote, candidate_id, source=source, approved_by=approved_by)
        receipt["ok"] = receipt.get("status") in ("replicated", "noop_already_canon")
        return JSONResponse(receipt)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status_code=500)


def _multipart_available() -> bool:
    try:
        import multipart  # python-multipart
        return True
    except Exception:
        return False


@app.get("/api/health")
async def api_health():
    """Honest health: server alive + cognition + memory/intake/receipt readiness.
    Extends /health. 'alive' here means more than 'server responds'."""
    boot = boot_status_payload()
    from pathlib import Path as _P
    db = _P(__file__).resolve().parent / "Memory" / "oracle_memory.db"
    multipart_ok = _multipart_available()
    return JSONResponse({
        "ok": True,
        "server": "alive",
        "cognition_mode": boot.get("cognition_mode"),
        "network_boundary": boot.get("network_boundary"),
        "session_id": _session_id,
        "mode": _mode,
        "memory_db_exists": db.exists(),
        "receipt_write_available": True,
        "file_intake_available": multipart_ok,
        "folder_intake_available": multipart_ok,
        "capabilities": _safe_capability_summary() or {},
        "boot_receipt_path": boot.get("boot_receipt_path"),
    })


@app.get("/api/agenda")
async def api_agenda():
    """Active Agenda Loop snapshot — readable by chat and state surfaces."""
    snap = _agenda_snapshot()
    if snap is None:
        return JSONResponse({"error": "agenda unavailable"}, status_code=500)
    return JSONResponse(snap)


@app.get("/api/capability-registry")
async def api_capability_registry():
    """Capability Truth Registry: available/degraded/blocked/stubbed/unverified/missing."""
    try:
        from oracle_intent import capability_registry
        return JSONResponse(capability_registry())
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.get("/api/doctor")
async def api_doctor():
    """Doctor: self-diagnosis + capability truth from current State Graph."""
    try:
        from oracle_intent import doctor_summary
        return JSONResponse(doctor_summary(_executive_state()))
    except Exception as exc:
        import traceback as _tb
        _tb.print_exc()
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.get("/session/current")
async def session_current():
    """Real runtime telemetry for the Operator Console — no decorative status."""
    from pathlib import Path as _P
    root = _P(__file__).resolve().parent

    port = 7781
    try:
        import runtime_config as _rc
        port = getattr(_rc, "RUNTIME_PORT", getattr(_rc, "PORT", getattr(_rc, "ORACLE_PORT", 7781)))
    except Exception:
        port = 7781

    db = root / "Memory" / "oracle_memory.db"
    caps = _safe_capability_summary() or {}
    seed = _safe_seed_summary() or {}
    holes = _safe_session_holes()
    multipart_ok = _multipart_available()

    session_receipt = None
    sdir = root / "data" / "sessions"
    recs = sorted(sdir.glob("*/session_receipt.json")) if sdir.exists() else []
    if recs:
        try:
            session_receipt = json.loads(max(recs, key=lambda p: p.stat().st_mtime).read_text(encoding="utf-8"))
        except Exception:
            session_receipt = None

    pending = seed.get("pending_approvals") or 0
    limitations = []
    if not multipart_ok:
        limitations.append("file/folder upload needs setup: python-multipart not installed")
    if caps.get("blocked_names"):
        limitations.append("blocked from runtime: " + ", ".join(caps["blocked_names"]))

    return JSONResponse({
        "current_session_id": _session_id,
        "active_mode": _mode,
        "runtime_port": port,
        "memory_db_exists": db.exists(),
        "memory_message_count": _safe_memory_message_count(),
        "history_count": len(_history),
        "active_context_summary": (session_receipt or {}).get("purpose") or "no active session declared",
        "pending_approvals_count": pending,
        "capabilities": caps,
        "file_intake_available": multipart_ok,
        "folder_intake_available": multipart_ok,
        "receipt_write_available": True,
        "seed_candidates": seed.get("loaded_count"),
        "known_limitations": limitations,
        "current_holes": holes,
        "next_safe_action": "Review/approve the candidate seed records; provide the OBS video path + hash to close the session evidence loop.",
        "live_session_receipt": session_receipt,
        "active_agenda": _agenda_snapshot(),
    })


@app.post("/ingest-thread-passes")
async def ingest_thread_passes():
    """Ingest thread-pass seed data as CANDIDATE records. No canon promotion."""
    try:
        from rendered_reality.pattern_buffer.seed_loader import load_thread_passes
        summary = await asyncio.to_thread(load_thread_passes, write=True)
        return JSONResponse(summary)
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


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

    bad_model_reply = "VERIFIED:\nThe changes implemented in the code address the routing issue."
    guarded = _enforce_companion_source_labels(bad_model_reply)
    check("bare VERIFIED label is blocked", guarded.startswith("UNAVAILABLE [IDENTITY, LIVE_CONTEXT, LATEST_REFLECTION, CURRENT_SESSION]"), guarded)

    good_model_reply = "VERIFIED [LIVE_CONTEXT]: The active project is ORACLE.AI."
    allowed = _enforce_companion_source_labels(good_model_reply)
    check("bracketed source label is allowed", allowed == good_model_reply, allowed)

    codex_claim = _apply_authority_gate(
        "Codex output: The bridge is complete and the implementation is done.",
        "companion",
    )
    check("authority gate attributes pasted Codex completion", codex_claim.startswith("EXTERNAL_AGENT_REPORTED"), codex_claim)
    check("authority gate does not verify pasted Codex completion", "VERIFIED" not in codex_claim, codex_claim)

    grep_claim = _apply_authority_gate("I will execute grep now.", "companion")
    check("authority gate blocks Companion grep execution", grep_claim.startswith("BLOCKED") and "Companion Mode" in grep_claim, grep_claim)

    implementation_narration = _apply_authority_gate(
        "I am currently in the process of implementing the required architecture and changes to enforce mode authority.",
        "companion",
    )
    check("authority gate blocks Companion implementation narration", implementation_narration.startswith("BLOCKED"), implementation_narration)

    builder_claim = _apply_authority_gate("COMPLETED: I wrote the file.", "builder")
    check("authority gate prevents Builder completed without receipt", not builder_claim.startswith("COMPLETED"), builder_claim)
    check("authority gate rewrites Builder write as proposal", builder_claim.startswith("PROPOSED") or builder_claim.startswith("APPROVAL_REQUIRED"), builder_claim)

    source_manifest = _source_disciplined_response(
        "Identify every real source loaded into this response.",
        bootstrap,
        history,
    ) or ""
    check("source manifest includes IDENTITY", '"source_type": "IDENTITY"' in source_manifest, source_manifest)
    check("source manifest includes LIVE_CONTEXT", '"source_type": "LIVE_CONTEXT"' in source_manifest, source_manifest)
    check("source manifest includes LATEST_REFLECTION", '"source_type": "LATEST_REFLECTION"' in source_manifest, source_manifest)
    check("source manifest includes CURRENT_SESSION", '"source_type": "CURRENT_SESSION"' in source_manifest, source_manifest)

    runtime_truth = _source_disciplined_response(
        "State only what this running server can verify right now.",
        bootstrap,
        history,
    ) or ""
    truth_lines = [line.strip() for line in runtime_truth.splitlines() if line.strip()]
    check("runtime truth returns seven lines", len(truth_lines) == 7, runtime_truth)
    check("runtime truth uses only TRUE/FALSE/UNKNOWN", all(line.split(". ", 1)[-1] in {"TRUE", "FALSE", "UNKNOWN"} for line in truth_lines), runtime_truth)

    block = bootstrap.system_context_block(current_session=history)
    check("grounding block has IDENTITY section", "SOURCE SECTION: IDENTITY" in block)
    check("grounding block has LIVE_CONTEXT section", "SOURCE SECTION: LIVE_CONTEXT" in block)
    check("grounding block has LATEST_REFLECTION section", "SOURCE SECTION: LATEST_REFLECTION" in block)
    check("grounding block has CURRENT_SESSION section", "SOURCE SECTION: CURRENT_SESSION" in block)
    check("grounding block has source discipline labels", "Allowed labels: VERIFIED, INFERENCE, UNAVAILABLE." in block)
    check("identity selection includes family/continuity fact", "Sons (continuity targets):" in block, block)
    check("identity selection includes known boundaries", "known_boundary:" in block, block)

    source = Path(__file__).read_text(encoding="utf-8", errors="replace")
    check("server imports core oracle response bridge", "from oracle import web_engine_response" in source)
    check("server imports response authority gate", "validate_response_authority" in source)
    check("server imports attention_filter", "from attention_filter import attention_filter" in source)
    check("server imports salience_filter", "from salience_filter import focus_report" in source)
    companion_pos = source.find("# ── Companion path")
    builder_pos = source.find("# ── Builder path")
    route_end = source.find('"do it"', builder_pos)
    route_source = source[companion_pos:(route_end if route_end > builder_pos else len(source))]
    builder_route_source = route_source[(builder_pos - companion_pos) if builder_pos > companion_pos else 0:]
    companion_bridge = source.find("from oracle import web_engine_response", companion_pos)
    companion_llm = route_source.find("from llm import make_client")
    builder_bridge = source.find("from oracle import web_engine_response", builder_pos)
    builder_llm = builder_route_source.find("from llm import make_client")
    check("Companion bridge exists after route marker", companion_pos >= 0 and companion_bridge > companion_pos)
    check("Builder bridge exists after route marker", builder_pos >= 0 and builder_bridge > builder_pos)
    check("Companion route has no shallow LLM fallback", companion_llm < 0 or (builder_pos > companion_pos and companion_llm > builder_pos))
    check("Builder route has no shallow LLM fallback", builder_llm < 0)

    total = 42
    passed = total - failures
    print(f"{'='*60}")
    print(f"Result: {passed}/{total} passed")
    print(f"STATUS: {'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    print(f"{'='*60}\n")
    return failures


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse, os, secrets
    parser = argparse.ArgumentParser(description="ORACLE Web UI")
    parser.add_argument("--host", default=None,
                        help="Bind address. Defaults to 127.0.0.1; use --remote to bind 0.0.0.0.")
    parser.add_argument("--port", type=int, default=runtime_config.DEFAULT_RUNTIME_PORT)
    parser.add_argument("--remote", action="store_true",
                        help="Bind to 0.0.0.0 for LAN/Tailscale access. Requires --token or ORACLE_TOKEN.")
    parser.add_argument("--token", default=None,
                        help="Bearer token required on every request when --remote is set.")
    parser.add_argument("--source-discipline-smoke-test", action="store_true")
    args = parser.parse_args()

    # Record the actually-bound port so in-process diagnostics, receipts, and
    # health checks all report this exact port (single source of truth).
    runtime_config.set_runtime_port(args.port)

    if args.source_discipline_smoke_test:
        raise SystemExit(_source_discipline_smoke_test())

    # Resolve host
    if args.host is None:
        bind_host = "0.0.0.0" if args.remote else "127.0.0.1"
    else:
        bind_host = args.host

    # Auth middleware — only active when remote is enabled
    if args.remote:
        token = args.token or os.environ.get("ORACLE_TOKEN", "")
        if not token:
            token = secrets.token_urlsafe(32)
            print(f"\n  [Auth] No --token supplied. Generated one-time token:")
            print(f"         {token}")
            print(f"  [Auth] Set ORACLE_TOKEN env var or pass --token to make it permanent.\n")
        else:
            print(f"\n  [Auth] Remote access enabled. Bearer token authentication active.")

        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.responses import Response as StarletteResponse

        class BearerAuthMiddleware(BaseHTTPMiddleware):
            _token: str = token

            async def dispatch(self, request: Request, call_next):
                # Allow health check without auth
                if request.url.path in ("/health", "/favicon.ico"):
                    return await call_next(request)
                auth = request.headers.get("Authorization", "")
                if auth == f"Bearer {self._token}":
                    return await call_next(request)
                # Also accept token as query param for WebView convenience
                if request.query_params.get("token") == self._token:
                    return await call_next(request)
                return StarletteResponse("Unauthorized", status_code=401)

        app.add_middleware(BearerAuthMiddleware)
    else:
        print(f"\n  [Auth] Local-only mode — no authentication required.")

    print(f"  ORACLE is running at  http://{bind_host}:{args.port}")
    print(f"  Press Ctrl+C to stop\n")
    uvicorn.run(app, host=bind_host, port=args.port, log_level="warning")
