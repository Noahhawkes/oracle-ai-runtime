"""
core/capability_broker.py - one honest broker for ORACLE capability evidence.

The broker does three things:
  1. Discover what ORACLE has registered/implemented.
  2. Invoke only non-destructive, permitted smoke probes.
  3. Persist receipts so status reports can separate evidence from narrative.

It intentionally does not widen access. If a capability needs a browser
permission, microphone/camera grant, external account auth, audible output, or a
live human-approved send, the broker reports that boundary instead of faking it.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request
import uuid
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "core"
MEMORY = ROOT / "Memory"
RECEIPT_FILE = MEMORY / "capability_broker_receipts.jsonl"

for _p in (str(ROOT), str(CORE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short_id() -> str:
    return uuid.uuid4().hex[:12]


def _exists(path: str | Path) -> bool:
    return Path(path).exists()


def _module_exists(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def _bool_text(value: bool | None) -> str:
    if value is True:
        return "YES"
    if value is False:
        return "NO"
    return "UNKNOWN"


def _status_bool(status: str) -> bool | None:
    s = (status or "").lower()
    if s in {"yes", "not_required", "read_only", "dry_run_only", "report_only", "local_only"}:
        return True
    if s in {"no", "blocked"}:
        return False
    return None


def _safe_json(value: Any, limit: int = 600) -> Any:
    """Return a JSON-safe, size-bounded evidence value."""
    try:
        raw = json.dumps(value, ensure_ascii=True, default=str)
        if len(raw) <= limit:
            return json.loads(raw)
        return raw[:limit] + "...[truncated]"
    except Exception:
        return str(value)[:limit]


def _socket_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _url_json(url: str, timeout: float = 3.0) -> tuple[bool, dict[str, Any]]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ORACLE capability broker"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", errors="replace")
            return True, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        return False, {"error": f"HTTPError:{exc.code}"}
    except Exception as exc:
        return False, {"error": f"{type(exc).__name__}: {exc}"}


@dataclass
class SmokeOutcome:
    status: str
    evidence: dict[str, Any] = field(default_factory=dict)
    blocker: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "success"


@dataclass
class CapabilityReceipt:
    receipt_id: str
    component: str
    action: str
    status: str
    started_at: str
    completed_at: str
    progress: list[dict[str, Any]]
    evidence: dict[str, Any]
    blocker: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CapabilityStatus:
    component: str
    registered: bool
    implemented: bool
    authenticated: str
    permitted: str
    available: bool
    callable_from_oracle_web: bool
    callable_from_oracle_core: bool
    last_tested: str
    last_successful_receipt: str
    current_status: str
    blocker: str
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def installed(self) -> bool:
        return self.implemented

    @property
    def callable(self) -> bool:
        return self.current_status == "verified" and bool(self.last_successful_receipt)

    @property
    def tested(self) -> bool:
        return bool(self.last_tested)

    @property
    def degraded(self) -> bool:
        return self.current_status == "degraded"

    @property
    def blocked(self) -> bool:
        return self.current_status == "blocked"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.update({
            "installed": self.installed,
            "callable": self.callable,
            "tested": self.tested,
            "degraded": self.degraded,
            "blocked": self.blocked,
        })
        return data


@dataclass
class CapabilityDef:
    key: str
    component: str
    modules: tuple[str, ...] = ()
    files: tuple[str, ...] = ()
    auth: str = "not_required"
    permitted: str = "read_only"
    web_surface: bool = True
    core_surface: bool = True
    available: Callable[[], tuple[bool, dict[str, Any]]] | None = None
    smoke: Callable[[], SmokeOutcome] | None = None
    note: str = ""


_ACTIVE_TASKS: dict[str, dict[str, Any]] = {}
_ACTIVE_LOCK = threading.RLock()


def _record_progress(task_id: str | None, stage: str, detail: str = "") -> None:
    if not task_id:
        return
    with _ACTIVE_LOCK:
        task = _ACTIVE_TASKS.get(task_id)
        if not task:
            return
        task.setdefault("progress", []).append({"at": _now(), "stage": stage, "detail": detail})


def _persist_receipt(receipt: CapabilityReceipt) -> None:
    RECEIPT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with RECEIPT_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(receipt.to_dict(), ensure_ascii=True, sort_keys=True) + "\n")


def _read_receipts(limit: int = 500) -> list[dict[str, Any]]:
    if not RECEIPT_FILE.exists():
        return []
    try:
        lines = RECEIPT_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
        out = []
        for line in lines[-limit:]:
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
        return out
    except Exception:
        return []


def _last_receipts_by_component() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for receipt in _read_receipts():
        component = str(receipt.get("component", ""))
        if component:
            out[component] = receipt
    return out


def _last_success_by_component() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for receipt in _read_receipts():
        if receipt.get("status") == "success":
            component = str(receipt.get("component", ""))
            if component:
                out[component] = receipt
    return out


# ---------------------------------------------------------------------------
# Non-destructive smoke probes
# ---------------------------------------------------------------------------

def _smoke_web_ui() -> SmokeOutcome:
    from runtime_config import runtime_authority, runtime_base_url
    ok, data = _url_json(f"{runtime_base_url()}/api/mode", timeout=3)
    if ok and data.get("mode"):
        return SmokeOutcome("success", {"endpoint": "/api/mode", "mode": data.get("mode"), "session_id": data.get("session_id")})
    return SmokeOutcome("degraded", data, f"{runtime_authority()} did not return a usable ORACLE mode response")


def _smoke_conversation_core() -> SmokeOutcome:
    from conversation_mode import classify_route, MODE_BUILDER
    r = classify_route("are you there", current_mode=MODE_BUILDER, no_route=False)
    return SmokeOutcome("success", {"route": r.route, "external_routing": r.external_routing, "reason": r.reason})


def _smoke_l1_memory() -> SmokeOutcome:
    from working_memory import get_working_memory
    wm = get_working_memory()
    key = "capability_broker_probe"
    version = wm.set_state(key, "ok", source="capability_broker", status="verified")
    state = wm.snapshot().get("state", {}).get(key, {})
    if state.get("value") == "ok":
        return SmokeOutcome("success", {"state_version": version, "probe_status": state.get("status")})
    return SmokeOutcome("failed", {"state": state}, "L1 state probe was not readable after set_state")


def _smoke_l2_fts5() -> SmokeOutcome:
    import memory
    memory.init_db()
    migration = memory.migrate_memory_index(rebuild_if_stale=False)
    rows = memory.search_memory_index("ORACLE", limit=1)
    if migration.get("fts_available") or migration.get("fts5"):
        return SmokeOutcome("success", {"migration": _safe_json(migration), "sample_hits": len(rows)})
    return SmokeOutcome("blocked", {"migration": _safe_json(migration)}, "SQLite FTS5 is not available")


def _smoke_durable_memory() -> SmokeOutcome:
    import memory
    memory.init_db()
    with memory.get_conn() as conn:
        fact_count = conn.execute("SELECT COUNT(*) AS n FROM durable_facts").fetchone()["n"]
    return SmokeOutcome("success", {"db_path": str(memory.DB_PATH), "durable_facts": int(fact_count)})


def _smoke_operational_world_model() -> SmokeOutcome:
    from operational_state import build_operational_state
    state = build_operational_state()
    verified = state.get("verified", {})
    return SmokeOutcome("success", {
        "observed_at": state.get("observed_at"),
        "branch": verified.get("branch"),
        "commit": verified.get("commit"),
        "runtime": verified.get("runtime", {}).get("runtime_status"),
    })


def _smoke_vision_model() -> SmokeOutcome:
    from oracle_sight import sight_available
    status = sight_available()
    if status.get("available"):
        return SmokeOutcome("success", _safe_json(status))
    return SmokeOutcome("degraded", _safe_json(status), "No local vision model was resolved through Ollama")


def _smoke_live_visual_observer() -> SmokeOutcome:
    from runtime_config import runtime_base_url
    ok, data = _url_json(f"{runtime_base_url()}/api/see/status", timeout=4)
    if not ok:
        return SmokeOutcome("blocked", data, "ORACLE web vision status endpoint is not reachable")
    if data.get("available"):
        return SmokeOutcome(
            "degraded",
            {"endpoint": "/api/see/status", "model": data.get("model"), "raw_frame_stored": data.get("raw_frame_stored")},
            "Vision model is available, but no browser camera frame was supplied in this smoke test",
        )
    return SmokeOutcome("blocked", data, "Live observer requires browser camera permission and a posted frame")


def _smoke_current_observation_receipt() -> SmokeOutcome:
    from current_observation import current_observation_state
    state = current_observation_state()
    evidence = {
        "receipt_id": state.get("receipt_id"),
        "receipt_status": state.get("receipt_status"),
        "fresh": state.get("fresh"),
        "unknown_fields": state.get("unknown_fields", []),
    }
    if state.get("fresh"):
        return SmokeOutcome("success", evidence)
    return SmokeOutcome(
        "degraded",
        evidence,
        "No fresh current-observation receipt exists; dependent visual/window fields remain UNKNOWN",
    )


def _smoke_obs() -> SmokeOutcome:
    from obs_runtime_context import get_obs_context
    ctx = get_obs_context()
    if ctx.get("available"):
        return SmokeOutcome("success", {
            "scene": ctx.get("scene"),
            "recording": ctx.get("recording"),
            "streaming": ctx.get("streaming"),
            "raw_video_stored": ctx.get("raw_video_stored"),
        })
    return SmokeOutcome("degraded", _safe_json(ctx), ctx.get("last_obs_error") or "OBS WebSocket is not connected")


def _smoke_sov1_vision() -> SmokeOutcome:
    from oracle_presence import _take_screenshot
    raw, digest, width, height = _take_screenshot()
    # Do not store raw pixels in the receipt.
    size = len(raw)
    del raw
    return SmokeOutcome("success", {"screen_hash_prefix": digest, "width": width, "height": height, "png_bytes": size})


def _smoke_sov1_actuation() -> SmokeOutcome:
    from actuation_engine import ACTION_DRY_RUN, ActuationRequest, execute
    req = ActuationRequest(action_type=ACTION_DRY_RUN, dry_run=True)
    res = execute(req)
    if getattr(res, "dry_run", False) and not getattr(res, "scope_blocked", False):
        return SmokeOutcome("success", {
            "request_id": getattr(res, "request_id", ""),
            "dry_run": getattr(res, "dry_run", False),
            "success": getattr(res, "success", False),
            "stopped_reason": getattr(res, "stopped_reason", ""),
        })
    return SmokeOutcome("blocked", _safe_json(getattr(res, "__dict__", {})), getattr(res, "stopped_reason", "Dry-run actuation did not complete"))


def _smoke_local_file_access() -> SmokeOutcome:
    from execution_receipt import read_file
    target = ROOT / "README.md"
    if not target.exists():
        target = ROOT / "kernel.md"
    receipt = read_file(target)
    if receipt.status == "success":
        return SmokeOutcome("success", {"execution_receipt": receipt.operation_id, "path": receipt.evidence.get("path"), "sha256": receipt.evidence.get("sha256", "")[:16]})
    return SmokeOutcome("failed", receipt.evidence, "Local read_file receipt failed")


def _smoke_qr_scan() -> SmokeOutcome:
    import cv2
    import qr_scan

    with tempfile.TemporaryDirectory(prefix="oracle_cap_qr_") as td:
        target = Path(td) / "broker_probe_qr.png"
        try:
            encoder = cv2.QRCodeEncoder_create(cv2.QRCodeEncoder_Params())
            image = encoder.encode("oracle-capability-broker-qr-smoke")
            image = cv2.resize(image, None, fx=20, fy=20, interpolation=cv2.INTER_NEAREST)
            image = cv2.copyMakeBorder(image, 80, 80, 80, 80, cv2.BORDER_CONSTANT, value=255)
            if not cv2.imwrite(str(target), image):
                return SmokeOutcome("failed", {"path": str(target)}, "OpenCV could not write the temporary QR probe")
        except Exception as exc:
            return SmokeOutcome(
                "blocked",
                {"error": f"{type(exc).__name__}: {exc}"},
                "OpenCV QR encoder is unavailable",
            )

        result = qr_scan.scan_image_file(target, write_receipt=False)
        if result.get("decoded_text") == "oracle-capability-broker-qr-smoke":
            return SmokeOutcome(
                "success",
                {
                    "capability": result.get("capability"),
                    "decoded": result.get("decoded"),
                    "write_receipt": False,
                    "external_write": result.get("external_write"),
                    "camera_used": result.get("camera_used"),
                    "raw_image_stored": result.get("raw_image_stored"),
                },
            )
        return SmokeOutcome(
            "degraded",
            _safe_json(result),
            "QR decoder ran but did not decode the temporary probe payload",
        )


def _smoke_sandbox_candidate_writes() -> SmokeOutcome:
    import sandbox_files

    write_fn = getattr(sandbox_files, "sandbox_initiative_write", None)
    sandbox_root = ROOT / "sandbox"
    receipts_dir = sandbox_root / "receipts"
    latest_receipt = ""
    try:
        receipts = sorted(
            receipts_dir.glob("*sandbox_initiative_write*receipt.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if receipts:
            latest_receipt = str(receipts[0])
    except Exception:
        latest_receipt = ""

    if callable(write_fn) and sandbox_root.exists():
        return SmokeOutcome(
            "success",
            {
                "sandbox_root": str(sandbox_root),
                "write_function_present": True,
                "non_destructive_probe": True,
                "latest_initiative_receipt": latest_receipt or None,
                "approval_required_inside_sandbox": False,
                "canon_promotion": False,
                "external_write": False,
            },
        )
    return SmokeOutcome(
        "blocked",
        {
            "sandbox_root": str(sandbox_root),
            "sandbox_root_exists": sandbox_root.exists(),
            "write_function_present": callable(write_fn),
        },
        "Sandbox initiative write function or sandbox root is missing",
    )


def _smoke_git_access() -> SmokeOutcome:
    try:
        from git_state_reader import read_git_snapshot
        snap = read_git_snapshot(ROOT)
        if snap.get("available"):
            return SmokeOutcome(
                "success",
                {
                    "branch": snap.get("branch"),
                    "commit": snap.get("commit"),
                    "source": snap.get("source"),
                    "subprocess_used": False,
                    "dirty": "UNKNOWN",
                },
                "Git identity is readable from .git files; dirty status intentionally not probed from ORACLE chat",
            )
        return SmokeOutcome("degraded", snap, "Git metadata not readable without subprocess")
    except Exception as exc:
        return SmokeOutcome("degraded", {"error": f"{type(exc).__name__}: {exc}"}, "Git metadata reader failed")


def _smoke_github_access() -> SmokeOutcome:
    remote_text = ""
    try:
        config = ROOT / ".git" / "config"
        if config.exists():
            remote_lines = [
                line.strip() for line in config.read_text(encoding="utf-8", errors="replace").splitlines()
                if line.strip().startswith("url =")
            ]
            remote_text = "\n".join(remote_lines)
    except Exception as exc:
        remote_text = f"remote config unreadable: {type(exc).__name__}: {exc}"
    return SmokeOutcome(
        "degraded" if remote_text else "blocked",
        {"git_remote": remote_text[:300], "subprocess_used": False},
        "GitHub remotes are read from .git/config; auth/push checks are build-lane only",
    )


def _smoke_google_drive_access() -> SmokeOutcome:
    import drive_scope
    root = Path("G:/My Drive")
    scope = drive_scope.load_scope()
    approved = str(ROOT) in {str(Path(p)) for p in scope.get("approved_paths", [])}
    if root.exists() and ROOT.exists():
        try:
            sample_count = sum(1 for _ in root.iterdir())
        except Exception:
            sample_count = -1
        return SmokeOutcome("success", {"drive_root": str(root), "drive_root_exists": True, "top_level_count": sample_count, "workspace_in_scope": approved})
    return SmokeOutcome("blocked", {"drive_root": str(root), "drive_root_exists": root.exists()}, "Google Drive local sync path is not reachable")


def _smoke_miracledrive_index() -> SmokeOutcome:
    import miracledrive_index

    state = miracledrive_index.drive_state()
    evidence = {
        "building": bool(state.get("building")),
        "total_files": state.get("total_files", 0),
        "total_mb": state.get("total_mb", 0),
        "source_paths_scanned": state.get("source_paths_scanned", [])[:8],
        "source_paths_missing_count": len(state.get("source_paths_missing", [])),
        "recent_files": state.get("recent_files", [])[:3],
        "api_surfaces": ["/miracledrive", "/api/drive-state", "/api/drive-search", "/api/drive-read"],
    }
    if state.get("building"):
        return SmokeOutcome("degraded", evidence, "MiracleDrive index is building; query/read surfaces are wired but cache is not ready")
    if state.get("source_paths_scanned") or int(state.get("total_files", 0) or 0) > 0:
        return SmokeOutcome("success", evidence)
    return SmokeOutcome("degraded", evidence, "MiracleDrive index returned no scanned source paths")


def _smoke_internet_recall() -> SmokeOutcome:
    import internet_recall

    state = internet_recall.self_check()
    return SmokeOutcome("success", state)


def _patch_file_channel(module: Any, names: tuple[str, ...], send_name: str, reply_name: str, wait_name: str, pending_name: str) -> SmokeOutcome:
    originals = {name: getattr(module, name) for name in names}
    with tempfile.TemporaryDirectory(prefix="oracle_cap_channel_") as td:
        base = Path(td)
        try:
            for name in names:
                if name.startswith("ORACLE_TO"):
                    setattr(module, name, base / "outbox.md")
                elif "LOG" in name:
                    setattr(module, name, base / "channel_log.md")
                else:
                    setattr(module, name, base / "inbox.md")
            send_ok = getattr(module, send_name)("capability broker smoke", context="temp-path only")
            pending = getattr(module, pending_name)() or ""
            reply_ok = getattr(module, reply_name)("capability broker reply")
            response = getattr(module, wait_name)(timeout=1, poll=0.05) or ""
            if send_ok and reply_ok and "capability broker" in pending and "capability broker reply" in response:
                return SmokeOutcome("success", {"temp_dir": str(base), "sent": True, "reply_read": True})
            return SmokeOutcome("failed", {"sent": send_ok, "reply_ok": reply_ok, "pending": pending[:80], "response": response[:80]}, "Temp file channel round-trip failed")
        finally:
            for name, value in originals.items():
                setattr(module, name, value)


def _smoke_codex_bridge() -> SmokeOutcome:
    import oracle_codex_channel as ch
    return _patch_file_channel(
        ch,
        ("ORACLE_TO_CODEX", "CODEX_TO_ORACLE", "CHANNEL_LOG"),
        "send_to_codex",
        "reply_from_codex",
        "wait_for_response",
        "pending_task",
    )


def _smoke_claude_bridge() -> SmokeOutcome:
    import oracle_claude_channel as ch
    return _patch_file_channel(
        ch,
        ("ORACLE_TO_CLAUDE", "CLAUDE_TO_ORACLE", "CHANNEL_LOG"),
        "send_to_claude",
        "reply_from_claude",
        "wait_for_response",
        "pending_task",
    )


def _smoke_chatgpt_relay() -> SmokeOutcome:
    import desktop_ai_bridge as bridge
    original = bridge.STAGED_PROMPT_FILE
    with tempfile.TemporaryDirectory(prefix="oracle_cap_chatgpt_") as td:
        bridge.STAGED_PROMPT_FILE = Path(td) / "staged.json"
        try:
            staged = bridge.stage_prompt("chatgpt", "Capability broker smoke: status only.", source="capability_broker")
            loaded = bridge.load_staged()
            if loaded and loaded.target == "chatgpt" and staged.requires_confirmation:
                return SmokeOutcome(
                    "degraded",
                    {"staged": True, "requires_confirmation": True, "target": loaded.target},
                    "Relay staging works, but no live ChatGPT send/auth was performed without Noah confirmation",
                )
            return SmokeOutcome("failed", {"staged": bool(loaded)}, "ChatGPT staging did not round-trip")
        finally:
            bridge.STAGED_PROMPT_FILE = original


def _smoke_ollama() -> SmokeOutcome:
    from llm import check_ollama, get_model
    ok, message = check_ollama()
    if ok:
        return SmokeOutcome("success", {"message": message, "model": get_model(False), "vision_model": get_model(True)})
    return SmokeOutcome("degraded", {"message": message}, message)


def _smoke_tts() -> SmokeOutcome:
    import voice
    try:
        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty("voices") or []
        try:
            engine.stop()
        except Exception:
            pass
        return SmokeOutcome(
            "degraded",
            {"voice_enabled": voice.is_voice_enabled(), "engine_init": True, "voices": len(voices)},
            "TTS engine initialized, but audible speech was not played during non-destructive smoke",
        )
    except Exception as exc:
        return SmokeOutcome("blocked", {"voice_enabled": voice.is_voice_enabled(), "error": f"{type(exc).__name__}: {exc}"}, "TTS engine could not initialize")


def _smoke_stt() -> SmokeOutcome:
    ui = ROOT / "ui" / "index.html"
    text = ui.read_text(encoding="utf-8", errors="replace") if ui.exists() else ""
    implemented = "SpeechRecognition" in text or "webkitSpeechRecognition" in text
    if implemented:
        return SmokeOutcome(
            "blocked",
            {"ui_support_code": True, "browser_permission_required": True},
            "STT is browser-side only and requires a live browser microphone permission grant",
        )
    return SmokeOutcome("blocked", {"ui_support_code": False}, "No STT implementation evidence found in the web UI")


def _smoke_approval_queue() -> SmokeOutcome:
    from approval_center import list_pending
    items = list_pending()
    return SmokeOutcome("success", {"pending_count": len(items), "sources": sorted({i.get("source", "") for i in items})})


def _smoke_execution_receipts() -> SmokeOutcome:
    from execution_receipt import get_receipt_count, self_pid
    receipt = self_pid()
    return SmokeOutcome("success", {"execution_receipt": receipt.operation_id, "receipt_count": get_receipt_count(), "pid": receipt.evidence.get("process_id")})


def _smoke_background_watchers() -> SmokeOutcome:
    import ambient_watch
    recent = ambient_watch.get_recent(limit=1)
    started = bool(getattr(ambient_watch, "_started", False))
    return SmokeOutcome(
        "degraded" if not started else "success",
        {"ambient_recent_count": len(recent), "started_in_this_process": started},
        "" if started else "Ambient watcher read path works, but this process has no proof the watcher threads are currently running",
    )


def _smoke_event_polling() -> SmokeOutcome:
    buf = StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        import presence_daemon
    has = bool(getattr(presence_daemon, "HAS_DAEMON", False))
    daemon = getattr(presence_daemon, "_daemon", None) if has else None
    running = bool(getattr(daemon, "running", False)) if daemon else False
    events = daemon.get_daemon_events(1) if daemon else []
    if has and running:
        return SmokeOutcome("success", {"daemon_available": has, "running": running, "recent_events": len(events)})
    return SmokeOutcome(
        "degraded" if has else "blocked",
        {"daemon_available": has, "running": running, "recent_events": len(events), "import_notes": buf.getvalue()[:200]},
        "Presence event daemon is implemented, but no running daemon receipt exists in this process",
    )


def _smoke_replication_workers() -> SmokeOutcome:
    import continuity_scheduler
    report = continuity_scheduler.status_report()
    return SmokeOutcome(
        "degraded",
        {"continuity_scheduler_report": report[:500]},
        "Continuity scheduler exists, but no dedicated brokered replication worker live receipt was found",
    )


# Federation Replicator / Pattern Buffer doctrine (TP_004_FEDERATION_REPLICATOR_PATTERN_BUFFER).
# The pattern buffer is an approved continuity record plus a staging area for
# candidate records. It is a constraint, not mystical state reconstruction.
FEDERATION_DOCTRINE = "Replicate from approved truth; do not manufacture truth."


def _smoke_federation() -> SmokeOutcome:
    """Federation pattern buffer probe.

    Reads both ends of the buffer without promoting or manufacturing anything:
      - approved-truth store (durable facts = canon the replicator may draw from)
      - candidate staging area (approval queue = records pending Noah.Physical canon)
    The replicator only materializes from approved records; candidates stay
    staged until approved. This probe is read-only and never promotes a record.
    """
    import memory
    memory.init_db()
    with memory.get_conn() as conn:
        approved = conn.execute("SELECT COUNT(*) AS n FROM durable_facts").fetchone()["n"]
    try:
        from approval_center import list_pending
        candidates = len(list_pending())
        staging_ok = True
        staging_error = ""
    except Exception as exc:
        candidates = -1
        staging_ok = False
        staging_error = f"{type(exc).__name__}: {exc}"
    evidence = {
        "doctrine": FEDERATION_DOCTRINE,
        "approved_records": int(approved),
        "candidate_records_staged": candidates,
        "buffer_mode": "read_only_no_promotion",
    }
    if staging_ok:
        return SmokeOutcome("success", evidence)
    return SmokeOutcome(
        "degraded",
        evidence,
        f"Candidate staging area unreachable; pattern buffer is read-degraded ({staging_error})",
    )


def _available_web() -> tuple[bool, dict[str, Any]]:
    from runtime_config import runtime_host, runtime_port
    port = runtime_port()
    return _socket_open(runtime_host(), port), {"port": port}


def _available_module(name: str) -> Callable[[], tuple[bool, dict[str, Any]]]:
    def inner() -> tuple[bool, dict[str, Any]]:
        return _module_exists(name), {"module": name}
    return inner


def _available_files(*paths: str) -> Callable[[], tuple[bool, dict[str, Any]]]:
    def inner() -> tuple[bool, dict[str, Any]]:
        checked = {p: _exists(ROOT / p) for p in paths}
        return any(checked.values()), {"files": checked}
    return inner


COMPONENTS: list[CapabilityDef] = [
    CapabilityDef("oracle_web_ui", "ORACLE web UI", files=("oracle_server.py", "ui/index.html"), available=_available_web, smoke=_smoke_web_ui),
    CapabilityDef("oracle_conversation_core", "ORACLE conversation core", modules=("conversation_mode",), available=_available_module("conversation_mode"), smoke=_smoke_conversation_core),
    CapabilityDef("continuity_l1_memory", "Continuity Fabric L1 memory", modules=("working_memory",), available=_available_module("working_memory"), smoke=_smoke_l1_memory),
    CapabilityDef("continuity_l2_fts5", "Continuity Fabric L2 FTS5 recall", modules=("memory",), available=_available_module("memory"), smoke=_smoke_l2_fts5),
    CapabilityDef("durable_memory", "durable memory", modules=("memory",), available=_available_module("memory"), smoke=_smoke_durable_memory),
    CapabilityDef("operational_world_model", "operational world model", modules=("operational_state",), available=_available_module("operational_state"), smoke=_smoke_operational_world_model),
    CapabilityDef("vision_model", "vision model", modules=("oracle_sight",), available=_available_module("oracle_sight"), smoke=_smoke_vision_model),
    CapabilityDef("live_visual_observer", "live visual observer", files=("oracle_server.py", "ui/index.html"), available=_available_web, smoke=_smoke_live_visual_observer, permitted="camera_permission_required"),
    CapabilityDef("current_observation_receipt", "current observation receipt", modules=("current_observation",), available=_available_module("current_observation"), smoke=_smoke_current_observation_receipt, permitted="read_only_status"),
    CapabilityDef("obs_integration", "OBS integration", modules=("obs_runtime_context",), available=_available_module("obs_runtime_context"), smoke=_smoke_obs, auth="unknown"),
    CapabilityDef("sov1_vision", "SOV1 vision", modules=("oracle_presence",), available=_available_module("oracle_presence"), smoke=_smoke_sov1_vision, permitted="read_only"),
    CapabilityDef("sov1_actuation", "SOV1 actuation", modules=("actuation_engine",), available=_available_module("actuation_engine"), smoke=_smoke_sov1_actuation, permitted="dry_run_only"),
    CapabilityDef("local_file_access", "local file access", modules=("execution_receipt",), available=_available_module("execution_receipt"), smoke=_smoke_local_file_access, permitted="read_only"),
    CapabilityDef("qr_scan", "QR scan", modules=("qr_scan",), available=_available_module("qr_scan"), smoke=_smoke_qr_scan, permitted="local_image_decode_readonly"),
    CapabilityDef("sandbox_candidate_writes", "sandbox candidate writes", modules=("sandbox_files",), files=("sandbox",), available=_available_module("sandbox_files"), smoke=_smoke_sandbox_candidate_writes, permitted="sandbox_write_only_no_external_no_promotion"),
    CapabilityDef("git_access", "Git access", files=(".git",), available=_available_files(".git"), smoke=_smoke_git_access, permitted="read_only"),
    CapabilityDef("github_access", "GitHub access", files=(".git",), available=_available_files(".git"), smoke=_smoke_github_access, auth="unknown", permitted="read_only"),
    CapabilityDef("google_drive_local_sync", "Google Drive local sync", modules=("drive_scope",), available=_available_module("drive_scope"), smoke=_smoke_google_drive_access, auth="local_sync_only", permitted="read_only"),
    CapabilityDef("miracledrive_index", "MiracleDrive index", modules=("miracledrive_index",), files=("ui/miracledrive.html",), available=_available_module("miracledrive_index"), smoke=_smoke_miracledrive_index, auth="local_sync_only", permitted="read_search_readonly"),
    CapabilityDef("internet_recall", "Internet recall", modules=("internet_recall",), available=_available_module("internet_recall"), smoke=_smoke_internet_recall, auth="not_required", permitted="public_http_get_readonly_no_login"),
    CapabilityDef("claude_code_bridge", "Claude Code bridge", modules=("oracle_claude_channel",), available=_available_module("oracle_claude_channel"), smoke=_smoke_claude_bridge, auth="unknown", permitted="staging_only"),
    CapabilityDef("codex_bridge", "Codex bridge", modules=("oracle_codex_channel",), available=_available_module("oracle_codex_channel"), smoke=_smoke_codex_bridge, auth="not_required", permitted="staging_only"),
    CapabilityDef("chatgpt_relay", "ChatGPT relay", modules=("desktop_ai_bridge",), available=_available_module("desktop_ai_bridge"), smoke=_smoke_chatgpt_relay, auth="unknown", permitted="staging_only"),
    CapabilityDef("ollama", "Ollama", modules=("llm",), available=_available_module("llm"), smoke=_smoke_ollama, auth="not_required", permitted="local_only"),
    CapabilityDef("tts", "TTS", modules=("voice",), available=_available_module("voice"), smoke=_smoke_tts, auth="not_required", permitted="engine_probe_only"),
    CapabilityDef("stt", "STT", files=("ui/index.html",), available=_available_files("ui/index.html"), smoke=_smoke_stt, auth="browser_permission_required", permitted="microphone_permission_required"),
    CapabilityDef("approval_queue", "approval queue", modules=("approval_center",), available=_available_module("approval_center"), smoke=_smoke_approval_queue, permitted="read_only"),
    CapabilityDef("execution_receipts", "execution receipts", modules=("execution_receipt",), available=_available_module("execution_receipt"), smoke=_smoke_execution_receipts, permitted="read_only"),
    CapabilityDef("background_watchers", "background watchers", modules=("ambient_watch",), available=_available_module("ambient_watch"), smoke=_smoke_background_watchers, permitted="read_only_status"),
    CapabilityDef("event_polling", "event polling", modules=("presence_daemon",), available=_available_module("presence_daemon"), smoke=_smoke_event_polling, permitted="read_only_status"),
    CapabilityDef("replication_workers", "replication workers", modules=("continuity_scheduler",), available=_available_module("continuity_scheduler"), smoke=_smoke_replication_workers, permitted="read_only_status"),
    CapabilityDef("federation", "Federation pattern buffer", modules=("memory", "approval_center"), available=_available_module("memory"), smoke=_smoke_federation, auth="not_required", permitted="read_only_no_promotion", note=FEDERATION_DOCTRINE),
]

_BY_KEY = {c.key: c for c in COMPONENTS}
_BY_COMPONENT = {c.component.lower(): c for c in COMPONENTS}


def _definition_for(component: str) -> CapabilityDef | None:
    key = component.strip().lower().replace(" ", "_")
    return _BY_KEY.get(key) or _BY_COMPONENT.get(component.strip().lower())


def invoke_capability(component: str, action: str = "smoke", *, task_id: str | None = None) -> CapabilityReceipt:
    """Invoke a permitted broker action and persist a structured receipt."""
    started = _now()
    receipt_id = _short_id()
    progress: list[dict[str, Any]] = [{"at": started, "stage": "start", "detail": f"{component}:{action}"}]
    cap = _definition_for(component)
    if action != "smoke":
        receipt = CapabilityReceipt(receipt_id, component, action, "blocked", started, _now(), progress, {}, "Only smoke actions are brokered")
        _persist_receipt(receipt)
        return receipt
    if cap is None:
        receipt = CapabilityReceipt(receipt_id, component, action, "blocked", started, _now(), progress, {}, "Unknown capability")
        _persist_receipt(receipt)
        return receipt
    if cap.smoke is None:
        receipt = CapabilityReceipt(receipt_id, cap.component, action, "blocked", started, _now(), progress, {}, "No non-destructive smoke probe is registered")
        _persist_receipt(receipt)
        return receipt

    try:
        _record_progress(task_id, "probe", cap.component)
        progress.append({"at": _now(), "stage": "probe", "detail": cap.component})
        outcome = cap.smoke()
        progress.append({"at": _now(), "stage": "receipt", "detail": outcome.status})
        receipt = CapabilityReceipt(
            receipt_id=receipt_id,
            component=cap.component,
            action=action,
            status=outcome.status,
            started_at=started,
            completed_at=_now(),
            progress=progress,
            evidence=_safe_json(outcome.evidence),
            blocker=outcome.blocker,
        )
    except Exception as exc:
        receipt = CapabilityReceipt(
            receipt_id=receipt_id,
            component=cap.component,
            action=action,
            status="failed",
            started_at=started,
            completed_at=_now(),
            progress=progress + [{"at": _now(), "stage": "exception", "detail": f"{type(exc).__name__}: {exc}"}],
            evidence={"traceback": traceback.format_exc(limit=4)},
            blocker=f"{type(exc).__name__}: {exc}",
        )
    _persist_receipt(receipt)
    return receipt


def _base_status(cap: CapabilityDef) -> CapabilityStatus:
    implemented_modules = all(_module_exists(m) for m in cap.modules) if cap.modules else True
    implemented_files = all(_exists(ROOT / f) for f in cap.files) if cap.files else True
    implemented = implemented_modules and implemented_files
    available = implemented
    evidence: dict[str, Any] = {
        "modules": {m: _module_exists(m) for m in cap.modules},
        "files": {f: _exists(ROOT / f) for f in cap.files},
    }
    if cap.available:
        try:
            available, ev = cap.available()
            evidence.update(_safe_json(ev))
        except Exception as exc:
            available = False
            evidence["availability_error"] = f"{type(exc).__name__}: {exc}"
    status = "unknown"
    blocker = ""
    if not implemented:
        status = "blocked"
        blocker = "Implementation evidence missing"
    elif not available:
        status = "degraded"
        blocker = "Implementation exists, but runtime availability probe did not pass"
    return CapabilityStatus(
        component=cap.component,
        registered=True,
        implemented=implemented,
        authenticated=cap.auth,
        permitted=cap.permitted,
        available=available,
        callable_from_oracle_web=False,
        callable_from_oracle_core=False,
        last_tested="",
        last_successful_receipt="",
        current_status=status,
        blocker=blocker,
        evidence=evidence,
    )


def _apply_receipt(status: CapabilityStatus, receipt: dict[str, Any], success: dict[str, Any] | None) -> None:
    status.last_tested = str(receipt.get("completed_at") or receipt.get("started_at") or "")
    receipt_status = str(receipt.get("status") or "")
    if success:
        status.last_successful_receipt = str(success.get("receipt_id") or "")
    if receipt_status == "success":
        status.current_status = "verified"
        status.blocker = ""
        status.callable_from_oracle_web = True
        status.callable_from_oracle_core = True
    elif receipt_status in {"degraded", "failed"}:
        status.current_status = "degraded"
        status.blocker = str(receipt.get("blocker") or "Latest smoke receipt did not verify live invocation")
    elif receipt_status == "blocked":
        status.current_status = "blocked"
        status.blocker = str(receipt.get("blocker") or "Latest smoke receipt was blocked")
    if receipt.get("evidence"):
        status.evidence["last_receipt_evidence"] = _safe_json(receipt.get("evidence"))


def discover_capabilities(*, run_smokes: bool = False) -> list[CapabilityStatus]:
    """Discover current capability status, optionally refreshing smoke receipts."""
    last = _last_receipts_by_component()
    success = _last_success_by_component()
    statuses: list[CapabilityStatus] = []
    for cap in COMPONENTS:
        st = _base_status(cap)
        if run_smokes and st.implemented and cap.smoke is not None:
            receipt = invoke_capability(cap.key, "smoke")
            last[cap.component] = receipt.to_dict()
            if receipt.status == "success":
                success[cap.component] = receipt.to_dict()
        if cap.component in last:
            _apply_receipt(st, last[cap.component], success.get(cap.component))
        elif st.current_status == "unknown":
            st.blocker = "No smoke receipt has been generated yet"
        statuses.append(st)
    return statuses


def start_task(component: str, action: str = "smoke") -> str:
    """Start a broker invocation in the background and keep conversation free."""
    task_id = _short_id()
    with _ACTIVE_LOCK:
        _ACTIVE_TASKS[task_id] = {
            "task_id": task_id,
            "component": component,
            "action": action,
            "status": "running",
            "started_at": _now(),
            "progress": [],
            "receipt": None,
        }

    def runner() -> None:
        try:
            receipt = invoke_capability(component, action, task_id=task_id)
            with _ACTIVE_LOCK:
                task = _ACTIVE_TASKS.get(task_id)
                if task:
                    task["status"] = receipt.status
                    task["completed_at"] = receipt.completed_at
                    task["receipt"] = receipt.to_dict()
        except Exception as exc:
            with _ACTIVE_LOCK:
                task = _ACTIVE_TASKS.get(task_id)
                if task:
                    task["status"] = "failed"
                    task["completed_at"] = _now()
                    task["error"] = f"{type(exc).__name__}: {exc}"

    threading.Thread(target=runner, daemon=True, name=f"capability-broker-{task_id}").start()
    return task_id


def active_tasks() -> list[dict[str, Any]]:
    with _ACTIVE_LOCK:
        return [dict(v) for v in _ACTIVE_TASKS.values()]


def _flags(st: CapabilityStatus) -> str:
    auth = st.authenticated
    parts = [
        f"installed={_bool_text(st.installed)}",
        f"available={_bool_text(st.available)}",
        f"authenticated={auth}",
        f"permitted={st.permitted}",
        f"callable={_bool_text(st.callable)}",
        f"tested={_bool_text(st.tested)}",
        f"degraded={_bool_text(st.degraded)}",
        f"blocked={_bool_text(st.blocked)}",
    ]
    return " ".join(parts)


def format_capabilities(*, run_smokes: bool = False) -> str:
    statuses = discover_capabilities(run_smokes=run_smokes)
    lines = ["ORACLE CAPABILITY BROKER", f"observed_at: {_now()}", f"smoke_tests_refreshed: {_bool_text(run_smokes)}", ""]
    lines.append("Legend: REGISTERED IMPLEMENTED AUTHENTICATED PERMITTED AVAILABLE WEB CORE LAST_TESTED LAST_SUCCESSFUL_RECEIPT CURRENT_STATUS BLOCKER")
    lines.append("")
    for st in statuses:
        lines.append(f"[{st.component}]")
        lines.append(f"  flags: {_flags(st)}")
        lines.append(
            "  matrix: "
            f"REGISTERED={_bool_text(st.registered)} "
            f"IMPLEMENTED={_bool_text(st.implemented)} "
            f"AUTHENTICATED={st.authenticated} "
            f"PERMITTED={st.permitted} "
            f"AVAILABLE={_bool_text(st.available)} "
            f"CALLABLE_FROM_ORACLE_WEB={_bool_text(st.callable_from_oracle_web)} "
            f"CALLABLE_FROM_ORACLE_CORE={_bool_text(st.callable_from_oracle_core)}"
        )
        lines.append(f"  LAST_TESTED={st.last_tested or 'NEVER'}")
        lines.append(f"  LAST_SUCCESSFUL_RECEIPT={st.last_successful_receipt or 'NONE'}")
        lines.append(f"  CURRENT_STATUS={st.current_status.upper()}")
        lines.append(f"  BLOCKER={st.blocker or 'NONE'}")
    return "\n".join(lines)


def format_tool_status(*, run_smokes: bool = False) -> str:
    statuses = discover_capabilities(run_smokes=run_smokes)
    counts = {
        "verified": sum(1 for s in statuses if s.current_status == "verified"),
        "degraded": sum(1 for s in statuses if s.current_status == "degraded"),
        "blocked": sum(1 for s in statuses if s.current_status == "blocked"),
        "untested": sum(1 for s in statuses if not s.tested),
    }
    lines = ["ORACLE TOOL STATUS", f"observed_at: {_now()}"]
    lines.append(f"verified={counts['verified']} degraded={counts['degraded']} blocked={counts['blocked']} untested={counts['untested']}")
    lines.append("")
    for s in statuses:
        receipt = s.last_successful_receipt or "none"
        lines.append(f"- {s.component}: {s.current_status.upper()} callable={_bool_text(s.callable)} last_success={receipt} blocker={s.blocker or 'none'}")
    return "\n".join(lines)


def format_active_tasks() -> str:
    tasks = active_tasks()
    if not tasks:
        return "ORACLE ACTIVE TASKS\nnone"
    lines = ["ORACLE ACTIVE TASKS"]
    for t in tasks:
        lines.append(f"- {t.get('task_id')} {t.get('component')} {t.get('action')} status={t.get('status')}")
        for p in t.get("progress", [])[-5:]:
            lines.append(f"  {p.get('at')} {p.get('stage')}: {p.get('detail')}")
    return "\n".join(lines)


def format_doctor(*, run_smokes: bool = True) -> str:
    statuses = discover_capabilities(run_smokes=run_smokes)
    verified = [s for s in statuses if s.current_status == "verified"]
    degraded = [s for s in statuses if s.current_status == "degraded"]
    blocked = [s for s in statuses if s.current_status == "blocked"]
    lines = ["ORACLE CAPABILITY DOCTOR", f"observed_at: {_now()}", ""]
    lines.append(f"verified: {len(verified)}")
    lines.append(f"degraded: {len(degraded)}")
    lines.append(f"blocked: {len(blocked)}")
    lines.append("")
    if degraded:
        lines.append("DEGRADED")
        for s in degraded:
            lines.append(f"- {s.component}: {s.blocker or 'latest receipt degraded'}")
    if blocked:
        lines.append("")
        lines.append("BLOCKED")
        for s in blocked:
            lines.append(f"- {s.component}: {s.blocker or 'blocked'}")
    lines.append("")
    lines.append("Use /capabilities for the full matrix and /active-tasks for background work.")
    return "\n".join(lines)


def as_json(*, run_smokes: bool = False) -> dict[str, Any]:
    return {
        "observed_at": _now(),
        "capabilities": [s.to_dict() for s in discover_capabilities(run_smokes=run_smokes)],
        "active_tasks": active_tasks(),
    }


if __name__ == "__main__":
    print(format_doctor(run_smokes=True))
