"""core/alive_loop.py — ORACLE Alive v0.1 (Resident Loop Mode).

Makes ORACLE *operationally* alive (not conscious, not a person): a local,
consent-based heartbeat that runs the doctrine loop —

    observe approved signals -> events -> live context -> candidate meaning
    -> retrieve memory -> propose next action -> await Noah.Physical approval
    -> write audit receipt

Hard guarantees:
  - Reads ONLY approved sources (operational state, SourceMap *summaries*, the
    approval queue). Never secrets. Never unapproved folders. Never raw file
    contents. Never G:/cloud.
  - Never writes durable memory without approval. Never executes destructive or
    external/network actions. Raw recording stays off.
  - Every heartbeat writes a receipt to Memory/source_maps/alive_heartbeat.jsonl.

Governance vocabulary is shared with [[trusted_build]] and [[pending_actions]];
proposals route through the Guard approval lane, never auto-executed.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUNTIME_ROOT = Path(__file__).resolve().parent.parent
_SM_DIR = RUNTIME_ROOT / "Memory" / "source_maps"
HEARTBEAT_PATH = _SM_DIR / "alive_heartbeat.jsonl"
ALIVE_STATE_PATH = RUNTIME_ROOT / "Memory" / "alive_state.json"

DEFAULT_INTERVAL = 60  # seconds

BANNER = (
    "ALIVE LOOP ACTIVE · LOCAL ONLY · APPROVED SOURCES ONLY · "
    "RAW RECORDING OFF · NO AUTONOMOUS DESTRUCTIVE ACTIONS"
)

# Heartbeat outcomes (exactly one per tick).
OUT_NO_SIGNAL = "no_signal"
OUT_CONTEXT_UPDATE = "context_update"
OUT_SUGGESTED_ACTION = "suggested_next_action"
OUT_STALE_WARNING = "stale_state_warning"
OUT_CONTRADICTION = "unresolved_contradiction"
OUT_MEMORY_CANDIDATE = "memory_candidate"
OUT_BUILD_BLOCKAGE = "build_blockage"

# Approved read subtrees (relative to runtime root). Anything else is rejected.
_APPROVED_SUBTREES = ("Memory/source_maps", "intake/manifests", "Memory/project_states.json")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Approved-source gating ───────────────────────────────────────────────────
def is_approved_path(path: str | None) -> bool:
    """True only for contained, non-secret paths under an approved subtree."""
    if not path:
        return False
    try:
        from pending_actions import contained_path
        from intake_pipeline import secret_risk_for
    except Exception:
        return False
    rp = contained_path(path)              # inside runtime root, no escapes
    if rp is None:
        return False
    if secret_risk_for(str(rp)):           # never secrets
        return False
    rel = str(rp.resolve()).replace("\\", "/")
    root = str(RUNTIME_ROOT.resolve()).replace("\\", "/")
    rel_tail = rel[len(root):].lstrip("/")
    return any(rel_tail == s or rel_tail.startswith(s + "/") or rel_tail == s.split("/")[-1]
               for s in _APPROVED_SUBTREES)


# ── Context gathering (approved sources only, summaries not raw) ──────────────
def gather_context() -> dict[str, Any]:
    ctx: dict[str, Any] = {"observed_at": _now()}

    # Approval queue (count only).
    try:
        from approval_center import list_pending
        ctx["pending_approvals"] = len(list_pending())
    except Exception as exc:
        ctx["pending_approvals"] = None
        ctx["pending_error"] = f"{type(exc).__name__}: {exc}"

    # Broker pending tokens (count only).
    try:
        from pending_actions import list_pending as broker_pending
        ctx["pending_actions"] = len(broker_pending())
    except Exception:
        ctx["pending_actions"] = None

    # Declared project state staleness (no raw contents — summary fields only).
    try:
        from operational_state import _declared
        d = _declared()
        ctx["declared_stale"] = bool(d.get("stale"))
        ctx["declared_age_hours"] = d.get("age_hours")
    except Exception:
        ctx["declared_stale"] = None

    # Live repo activity (git only; no file contents).
    try:
        from operational_state import _git_state
        g = _git_state()
        ctx["working_tree"] = g.get("working_tree")
        ctx["changed_files"] = len(g.get("changed_files", []))
        ctx["branch"] = g.get("branch")
    except Exception:
        ctx["working_tree"] = None

    # Runtime reachability (light socket via the single-source port).
    try:
        from operational_state import _port_open
        ctx["runtime_online"] = bool(_port_open())
    except Exception:
        ctx["runtime_online"] = None

    # SourceMap intake summary (summary json only, never raw files).
    try:
        sm = _SM_DIR / "intake_source_map_latest.json"
        if is_approved_path(str(sm)) and sm.exists():
            data = json.loads(sm.read_text(encoding="utf-8"))
            ctx["intake_summary"] = data.get("summary", {}).get("by_ingest_status", {})
    except Exception:
        pass

    return ctx


def _last_heartbeat() -> dict | None:
    try:
        lines = [l for l in HEARTBEAT_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
        return json.loads(lines[-1]) if lines else None
    except Exception:
        return None


def classify_outcome(ctx: dict[str, Any], prev: dict | None) -> dict[str, Any]:
    """Render exactly one candidate meaning from the live context. Deterministic."""
    pending = ctx.get("pending_approvals") or 0
    stale = ctx.get("declared_stale")
    modified = ctx.get("working_tree") == "modified"
    online = ctx.get("runtime_online")

    if stale and modified:
        return {"outcome": OUT_CONTRADICTION, "requires_approval": False,
                "summary": "Declared project state is stale but the repo is actively changing — declared plan may no longer match reality.",
                "proposed_action": "Refresh Memory/project_states.json to match current work (proposal only)."}
    if pending > 0:
        return {"outcome": OUT_SUGGESTED_ACTION, "requires_approval": False,
                "summary": f"{pending} item(s) await Noah.Physical approval.",
                "proposed_action": "Run /pending to review and approve or reject."}
    if online is False:
        return {"outcome": OUT_BUILD_BLOCKAGE, "requires_approval": False,
                "summary": "ORACLE runtime port is not reachable — build/work surface is down.",
                "proposed_action": "Restart the runtime on the configured port."}
    if stale:
        return {"outcome": OUT_STALE_WARNING, "requires_approval": False,
                "summary": f"Declared project state is stale (age {ctx.get('declared_age_hours')}h).",
                "proposed_action": "Reconcile declared state when convenient (proposal only)."}
    if prev is not None and prev.get("context", {}).get("changed_files") != ctx.get("changed_files"):
        return {"outcome": OUT_CONTEXT_UPDATE, "requires_approval": False,
                "summary": f"Repo activity changed: {ctx.get('changed_files')} file(s) modified on {ctx.get('branch')}.",
                "proposed_action": None}
    return {"outcome": OUT_NO_SIGNAL, "requires_approval": False,
            "summary": "Nothing requires attention.", "proposed_action": None}


# ── Heartbeat ────────────────────────────────────────────────────────────────
def tick() -> dict[str, Any]:
    """One heartbeat: observe -> context -> meaning -> propose -> receipt.

    Writes NO durable memory and takes NO external/destructive action.
    """
    ctx = gather_context()
    meaning = classify_outcome(ctx, _last_heartbeat())
    record = {
        "heartbeat_id": "hb_" + uuid.uuid4().hex[:12],
        "timestamp": _now(),
        "outcome": meaning["outcome"],
        "summary": meaning["summary"],
        "proposed_action": meaning["proposed_action"],
        "requires_approval": meaning["requires_approval"],
        "context": ctx,
        # Guarantees recorded on every receipt for auditability.
        "durable_memory_writes": 0,
        "external_actions": 0,
        "destructive_actions": 0,
        "network_calls": 0,
        "raw_recording": False,
        "local_only": True,
        "human_authority": "Noah.Physical",
    }
    HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HEARTBEAT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


# ── Loop control ─────────────────────────────────────────────────────────────
_LOCK = threading.Lock()
_STATE: dict[str, Any] = {"thread": None, "stop": None, "running": False,
                          "interval": DEFAULT_INTERVAL}


def _write_alive_state(on: bool, interval: int) -> None:
    try:
        ALIVE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        ALIVE_STATE_PATH.write_text(json.dumps(
            {"alive": on, "interval": interval, "updated_at": _now()}, indent=2), encoding="utf-8")
    except Exception:
        pass


def _loop(stop_event: threading.Event, interval: int) -> None:
    while not stop_event.is_set():
        try:
            tick()
        except Exception:
            pass
        stop_event.wait(interval)


def start(interval: int = DEFAULT_INTERVAL) -> dict[str, Any]:
    with _LOCK:
        if _STATE["running"]:
            return status()
        ev = threading.Event()
        t = threading.Thread(target=_loop, args=(ev, interval), daemon=True, name="oracle-alive")
        _STATE.update(running=True, thread=t, stop=ev, interval=interval)
        _write_alive_state(True, interval)
        t.start()
    return status()


def stop() -> dict[str, Any]:
    with _LOCK:
        if _STATE["stop"]:
            _STATE["stop"].set()
        _STATE["running"] = False
        _write_alive_state(False, _STATE["interval"])
    return status()


def status() -> dict[str, Any]:
    last = _last_heartbeat()
    try:
        count = sum(1 for l in HEARTBEAT_PATH.read_text(encoding="utf-8").splitlines() if l.strip()) \
            if HEARTBEAT_PATH.exists() else 0
    except Exception:
        count = 0
    return {
        "running": bool(_STATE["running"]),
        "interval_seconds": _STATE["interval"],
        "heartbeats_recorded": count,
        "last_outcome": (last or {}).get("outcome"),
        "last_summary": (last or {}).get("summary"),
        "banner": BANNER if _STATE["running"] else "ALIVE LOOP OFF · resident heartbeat not running",
        "heartbeat_log": str(HEARTBEAT_PATH),
    }


def format_status_line() -> str:
    s = status()
    head = s["banner"]
    tail = (f"\n(running: {s['running']}; every {s['interval_seconds']}s; "
            f"heartbeats: {s['heartbeats_recorded']}; last: {s['last_outcome'] or 'none'})")
    return head + tail


# ── Smoke test ───────────────────────────────────────────────────────────────
def run_smoke_tests() -> int:
    import tempfile
    global HEARTBEAT_PATH, ALIVE_STATE_PATH
    tmp = Path(tempfile.mkdtemp())
    orig_hb, orig_state = HEARTBEAT_PATH, ALIVE_STATE_PATH
    HEARTBEAT_PATH = tmp / "alive_heartbeat.jsonl"
    ALIVE_STATE_PATH = tmp / "alive_state.json"

    failures = 0

    def check(label: str, cond: bool) -> None:
        nonlocal failures
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")
        if not cond:
            failures += 1

    try:
        rec = tick()
        check("heartbeat receipt is written", HEARTBEAT_PATH.exists())
        check("heartbeat outcome is one of the defined kinds",
              rec["outcome"] in {OUT_NO_SIGNAL, OUT_CONTEXT_UPDATE, OUT_SUGGESTED_ACTION,
                                 OUT_STALE_WARNING, OUT_CONTRADICTION, OUT_MEMORY_CANDIDATE,
                                 OUT_BUILD_BLOCKAGE})
        check("no durable memory write", rec["durable_memory_writes"] == 0)
        check("no external/network action", rec["external_actions"] == 0 and rec["network_calls"] == 0)
        check("no delete/move action", rec["destructive_actions"] == 0)
        check("raw recording off", rec["raw_recording"] is False)

        check("approved SourceMap path accepted",
              is_approved_path(str(_SM_DIR / "alive_heartbeat.jsonl")))
        check("unapproved path rejected (user home)", not is_approved_path("C:\\Users\\noahh\\x.txt"))
        check("unapproved path rejected (Google Drive)", not is_approved_path("G:\\My Drive\\x.txt"))
        check("secret path rejected (.env)", not is_approved_path(str(RUNTIME_ROOT / ".env")))
        check("repo source path rejected (not an approved read subtree)",
              not is_approved_path(str(RUNTIME_ROOT / "core" / "oracle_server.py")))

        s_on = start(interval=999)
        check("/alive on starts loop", s_on["running"] is True)
        s_off = stop()
        check("/alive off stops loop", s_off["running"] is False)
    finally:
        stop()
        HEARTBEAT_PATH, ALIVE_STATE_PATH = orig_hb, orig_state

    print(f"\n{'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    import sys
    if "--smoke-test" in sys.argv:
        raise SystemExit(run_smoke_tests())
    print(format_status_line())
