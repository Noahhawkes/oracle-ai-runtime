"""agent_gateway.py — read-only ORACLE -> ChatGPT Agent gateway (V1).

Exposes VERIFIED state from the running local ORACLE runtime to an external
agent WITHOUT widening ORACLE's permissions. Every endpoint reuses ORACLE's
existing functions; this file adds no memory, no continuity engine, and no
personality service.

Security posture:
  * Read-only. No file writes, no shell, no Git, no restart, no SOV1 actuation,
    no approval/canon mutation, no deletion, no external messaging, no arbitrary
    path access. (There are no filesystem-path inputs on any endpoint.)
  * Bearer-token gated. Token loaded from env / gitignored file, never hardcoded,
    never logged, never returned.
  * ORACLE stays bound to localhost. This gateway is the only surface intended to
    later sit behind a secure HTTPS tunnel / MCP transport. It is NOT exposed here.

Run:  python agent_gateway.py   (binds 127.0.0.1:7782 by default)
"""
from __future__ import annotations

import hmac
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
CORE = ROOT / "core"
for _p in (ROOT, CORE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
# Importing ORACLE library functions must never boot a second server.
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

ORACLE_BASE = os.environ.get("ORACLE_RUNTIME_URL", "http://127.0.0.1:7781")
OLLAMA_BASE = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")

app = FastAPI(
    title="ORACLE Agent Gateway",
    version="1.0.0",
    docs_url=None, redoc_url=None, openapi_url=None,  # no schema surface exposed
)


# ── authentication ────────────────────────────────────────────────────────────

def _load_token() -> str | None:
    """Bearer token from env, or a gitignored file. Never hardcoded."""
    tok = os.environ.get("ORACLE_AGENT_GATEWAY_TOKEN")
    if tok and tok.strip():
        return tok.strip()
    f = ROOT / "agent_gateway_token.txt"
    try:
        if f.exists():
            v = f.read_text(encoding="utf-8").strip()
            return v or None
    except OSError:
        pass
    return None


def _require_auth(request: Request) -> None:
    expected = _load_token()
    if not expected:
        # Fail CLOSED: with no configured token the gateway refuses everything.
        raise HTTPException(status_code=503, detail="gateway_not_configured")
    header = request.headers.get("authorization") or ""
    if not header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing_bearer_token")
    presented = header.split(" ", 1)[1].strip()
    if not hmac.compare_digest(presented, expected):
        raise HTTPException(status_code=401, detail="invalid_token")


# ── provenance envelope ────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env(status: str, source: str, data: Any) -> dict[str, Any]:
    """status: verified | partial | unknown | unavailable."""
    return {"status": status, "retrieved_at": _now(), "source": source, "data": data}


def _probe(base: str, path: str, timeout: float = 3.0) -> tuple[bool, Any]:
    """Read-only GET against a localhost ORACLE surface. (ok, json|text|None)."""
    url = base.rstrip("/") + path
    try:
        req = urllib.request.Request(url, method="GET")  # noqa: S310 (localhost only)
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8", errors="replace")
        try:
            return True, json.loads(raw)
        except ValueError:
            return True, raw
    except Exception:
        return False, None


def _load_cognitive_state():
    try:
        from state_store import list_recent_transitions, load_current_state

        return load_current_state(), list_recent_transitions(limit=1)
    except Exception:
        return None, None


def _configured_model() -> str:
    """The model the runtime is configured to use — same source as oracle_server."""
    return os.environ.get("ORACLE_NOAH_DIRECT_MODEL", "qwen2.5:7b")


# ── endpoints (all read-only) ──────────────────────────────────────────────────

@app.get("/agent/health")
def agent_health(_: None = Depends(_require_auth)) -> dict[str, Any]:
    ok, mode = _probe(ORACLE_BASE, "/api/mode")
    if not (ok and isinstance(mode, dict)):
        ok, mode = _probe(ORACLE_BASE, "/api/health")
    if not (ok and isinstance(mode, dict)):
        return _env("unavailable", f"{ORACLE_BASE}/api/mode",
                    {"runtime": "offline", "note": "ORACLE runtime did not respond on localhost"})
    return _env("verified", f"{ORACLE_BASE}/api/mode", {
        "runtime": "online",
        "runtime_mode": mode.get("mode") or mode.get("cognition_mode"),
        "runtime_version": mode.get("version") or mode.get("schema_version"),
        "current_model": mode.get("active_model") or _configured_model(),
        "runtime_fingerprint": mode.get("build_fingerprint") or mode.get("boot_receipt_path"),
        "session_id": mode.get("session_id"),
        "safety": mode.get("safety") or mode.get("safety_status"),
        "network_boundary": mode.get("network_boundary"),
    })


@app.get("/agent/state")
def agent_state(_: None = Depends(_require_auth)) -> dict[str, Any]:
    st, recent = _load_cognitive_state()
    ok, mode = _probe(ORACLE_BASE, "/api/mode")
    cap = None
    if ok and isinstance(mode, dict):
        cap = mode.get("capability_summary") or {
            k: mode.get(k) for k in ("verified", "degraded", "blocked") if k in mode
        } or None

    if st is None:
        if ok and isinstance(mode, dict):
            return _env("partial", "cognitive_state:UNAVAILABLE + /api/mode", {
                "current_session": mode.get("session_id"),
                "current_cognitive_state": "UNKNOWN",
                "capability_summary": cap,
            })
        return _env("unavailable", "cognitive_state + /api/mode",
                    {"current_cognitive_state": "UNKNOWN"})

    d = st.to_dict()
    return _env("verified", "state_store.load_current_state", {
        "current_session": d.get("session_id"),
        "current_state_id": d.get("state_id"),
        "current_intent": d.get("current_intent"),
        "current_goals": d.get("active_goals", []),
        "known_unknowns": list(d.get("unknown_ids", []) or []) + list(d.get("unresolved_questions", []) or []),
        "open_contradictions": d.get("contradiction_ids", []),
        "pending_approvals_count": len(d.get("pending_action_ids", []) or []),
        "capability_summary": cap if cap is not None else d.get("capability_snapshot_id"),
        "model_id": d.get("model_id"),
        "build_fingerprint": d.get("build_fingerprint"),
        "state_hash_verified": bool(st.verify_hash()),
        "last_state_change": d.get("updated_at"),
        "created_at": d.get("created_at"),
        "last_transition": (recent[0] if recent else None),
    })


class RecallIn(BaseModel):
    query: str = Field(..., min_length=1, max_length=800)
    limit: int = Field(10, ge=1, le=50)


@app.post("/agent/recall")
def agent_recall(body: RecallIn, _: None = Depends(_require_auth)) -> dict[str, Any]:
    try:
        from recall_orchestrator import build_context, evidence_payload
    except Exception:
        return _env("unavailable", "recall_orchestrator",
                    {"query": body.query, "records": [], "note": "recall subsystem unavailable"})
    try:
        ctx = build_context(body.query)
        ev = evidence_payload(ctx)
    except Exception as exc:
        return _env("unavailable", "recall_orchestrator.build_context",
                    {"query": body.query, "records": [], "error_class": type(exc).__name__})

    ctx_d = ctx if isinstance(ctx, dict) else {}
    records = list(ctx_d.get("records") or [])[: body.limit]
    # Empty is an honest "nothing on record", NOT a failure and NEVER a fabrication.
    return _env("verified", "recall_orchestrator.build_context", {
        "query": body.query,
        "records": records,
        "record_count": len(records),
        "evidence": ev,
        "note": None if records else "no matching records in ORACLE recall",
    })


@app.get("/agent/open-questions")
def agent_open_questions(_: None = Depends(_require_auth)) -> dict[str, Any]:
    signals: list | None
    try:
        from curiosity_engine import recall_signals

        signals = [{
            "id": getattr(s, "id", None),
            "type": getattr(s, "signal_type", None),
            "title": getattr(s, "title", None),
            "risk": getattr(s, "risk_level", None),
            "status": getattr(s, "status", None),
        } for s in recall_signals()]
    except Exception:
        signals = None

    st, _r = _load_cognitive_state()
    cog = None
    if st is not None:
        d = st.to_dict()
        cog = {
            "unresolved_questions": d.get("unresolved_questions", []),
            "contradiction_ids": d.get("contradiction_ids", []),
            "unknown_ids": d.get("unknown_ids", []),
        }

    if signals is None and cog is None:
        return _env("unavailable", "curiosity_engine + cognitive_state",
                    {"open_questions": "UNAVAILABLE"})
    return _env("verified" if signals is not None else "partial",
                "curiosity_engine.recall_signals + cognitive_state",
                {"signals": signals or [], "cognitive": cog})


@app.get("/agent/receipts/latest")
def agent_receipts_latest(_: None = Depends(_require_auth), limit: int = 5) -> dict[str, Any]:
    limit = max(1, min(int(limit or 5), 25))
    latest = None
    try:
        from build_witness import read_latest_receipt

        latest = read_latest_receipt()
    except Exception:
        latest = None

    recent: list = []
    try:
        jl = ROOT / "Memory" / "build_witness" / "build_receipts.jsonl"
        if jl.exists():
            for ln in jl.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
                try:
                    recent.append(json.loads(ln))
                except ValueError:
                    continue
    except OSError:
        pass

    if latest is None and not recent:
        return _env("unavailable", "build_witness", {"latest": None, "recent": []})
    return _env("verified", "build_witness.read_latest_receipt + build_receipts.jsonl",
                {"latest": latest, "recent": recent, "recent_count": len(recent)})


@app.get("/agent/models")
def agent_models(_: None = Depends(_require_auth)) -> dict[str, Any]:
    ok, mode = _probe(ORACLE_BASE, "/api/mode")
    md = mode if (ok and isinstance(mode, dict)) else {}
    ook, tags = _probe(OLLAMA_BASE, "/api/tags")
    pok, ps = _probe(OLLAMA_BASE, "/api/ps")

    available: Any = "UNAVAILABLE"
    if ook and isinstance(tags, dict):
        available = [m.get("name") for m in (tags.get("models") or []) if isinstance(m, dict)]
    loaded = None
    if pok and isinstance(ps, dict):
        loaded = [m.get("name") for m in (ps.get("models") or []) if isinstance(m, dict)] or None
    vision = None
    if isinstance(available, list):
        vision = next((n for n in available if n and ("vl" in n.lower() or "vision" in n.lower())), None)

    return _env("verified" if (ok or ook) else "unavailable",
                f"{OLLAMA_BASE}/api/tags + /api/ps + config(ORACLE_NOAH_DIRECT_MODEL)", {
                    "configured_model": _configured_model(),
                    "currently_loaded_model": loaded,  # None when idle — models unload
                    "ollama_available_models": available,
                    "vision_model": vision,
                    "router_state": md.get("current_lane") or md.get("lane_label"),
                })


if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("ORACLE_AGENT_GATEWAY_HOST", "127.0.0.1")
    port = int(os.environ.get("ORACLE_AGENT_GATEWAY_PORT", "7782"))
    # access log records method + path only; the bearer token lives in a header, never the URL.
    uvicorn.run(app, host=host, port=port, log_level="info")
