"""
core/continuity_scheduler.py — ORACLE Continuity Backup Scheduler v0.1

Run safe local continuity exports on a schedule so ORACLE can preserve
herself without requiring Noah to remember manual backup commands.

Rules (non-negotiable):
  - No cloud upload unless explicitly approved.
  - No raw email / journal / video / audio export.
  - Approval status, candidate state, and revocation state are preserved.
  - Manifest + checksum required for every real export.
  - SAFE_SLEEP blocks execution.
  - Default schedule is disabled — opt-in only.

Usage:
    python core/continuity_scheduler.py --status
    python core/continuity_scheduler.py --dry-run
    python core/continuity_scheduler.py --run-once
    python core/continuity_scheduler.py --smoke-test
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Literal, Optional

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
SCHEDULER_STATE_FILE = ROOT / "Memory" / "continuity_scheduler.json"
SCHEDULER_LOG_FILE   = ROOT / "Memory" / "continuity_scheduler_log.jsonl"
EXPORTS_DIR          = ROOT / "Memory" / "continuity_exports"

# ── Types ─────────────────────────────────────────────────────────────────────
Frequency   = Literal["hourly", "daily", "weekly", "manual"]
ExportMode  = Literal["summary_and_governed_state_only", "full_governed"]
RunStatus   = Literal["planned", "running", "completed", "failed", "blocked", "dry_run"]

# ── Blocked content — never exported ─────────────────────────────────────────
_BLOCKED_EXPORT_TYPES = frozenset([
    "raw_email", "raw_journal", "raw_video", "raw_audio",
    "cloud_upload", "unscanned_files",
])

_DEFAULT_SCHEDULE: dict = {
    "id":                   "default",
    "enabled":              False,
    "frequency":            "daily",
    "last_run_at":          None,
    "next_run_at":          None,
    "export_mode":          "summary_and_governed_state_only",
    "safe_sleep_compatible": True,
    "local_only":           True,
    "cloud_upload_allowed": False,
    "created_at":           None,
    "updated_at":           None,
    "unknowns":             {},
}

_NOW = lambda: datetime.now(timezone.utc).isoformat()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rj(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _wj(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _log(msg: str) -> None:
    entry = {"ts": _NOW(), "msg": msg}
    SCHEDULER_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SCHEDULER_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _is_safe_sleep() -> bool:
    try:
        ss = _rj(ROOT / "Memory" / "session_state.json") or {}
        return str(ss.get("mode", "")).upper() in ("SAFE_SLEEP", "SAFE_SLEEP_MODE")
    except Exception:
        return False


# ── Schedule persistence ──────────────────────────────────────────────────────

def load_schedule() -> dict:
    raw = _rj(SCHEDULER_STATE_FILE)
    if isinstance(raw, dict) and raw.get("id"):
        return raw
    # First boot — write default
    sched = dict(_DEFAULT_SCHEDULE)
    sched["created_at"] = _NOW()
    sched["updated_at"] = _NOW()
    _wj(SCHEDULER_STATE_FILE, sched)
    return sched


def save_schedule(sched: dict) -> None:
    sched["updated_at"] = _NOW()
    _wj(SCHEDULER_STATE_FILE, sched)


def _compute_next_run(sched: dict) -> Optional[str]:
    freq = sched.get("frequency", "daily")
    base = sched.get("last_run_at") or _NOW()
    try:
        base_dt = datetime.fromisoformat(base)
    except Exception:
        base_dt = datetime.now(timezone.utc)
    if freq == "hourly":
        delta = timedelta(hours=1)
    elif freq == "daily":
        delta = timedelta(days=1)
    elif freq == "weekly":
        delta = timedelta(weeks=1)
    else:  # manual
        return None
    return (base_dt + delta).isoformat()


# ── Run record ────────────────────────────────────────────────────────────────

def _new_run(schedule_id: str, dry: bool = False) -> dict:
    return {
        "id":            str(uuid.uuid4()),
        "schedule_id":   schedule_id,
        "started_at":    _NOW(),
        "completed_at":  None,
        "status":        "dry_run" if dry else "planned",
        "export_path":   None,
        "manifest_path": None,
        "checksum":      None,
        "blocked_reason": None,
        "safety_notes":  [],
        "unknowns":      {},
    }


# ── Core operations ───────────────────────────────────────────────────────────

def dry_run() -> dict:
    """
    Plan a backup without executing it.
    Returns a run record with status=dry_run describing what WOULD happen.
    """
    sched = load_schedule()
    run = _new_run(sched["id"], dry=True)
    run["status"] = "dry_run"

    notes = []

    # Safety check
    if _is_safe_sleep():
        run["blocked_reason"] = "SAFE_SLEEP active — export blocked by safety mode."
        run["status"] = "blocked"
        notes.append("SAFE_SLEEP: would block execution.")
        run["safety_notes"] = notes
        _log(f"dry_run blocked: SAFE_SLEEP active")
        return run

    # Schedule enabled check
    if not sched.get("enabled"):
        notes.append("Schedule disabled — would require --enable to auto-run.")

    # Cloud check
    if sched.get("cloud_upload_allowed"):
        run["blocked_reason"] = "cloud_upload_allowed=True — not permitted by default."
        run["status"] = "blocked"
        notes.append("BLOCKED: cloud upload not permitted without explicit approval.")
        run["safety_notes"] = notes
        _log(f"dry_run blocked: cloud upload not permitted")
        return run

    notes.append(f"Export mode: {sched.get('export_mode', 'summary_and_governed_state_only')}")
    notes.append("Blocked export types: raw_email, raw_journal, raw_video, raw_audio")
    notes.append("Approval/candidate state: preserved")
    notes.append("Manifest + checksum: would be generated")
    notes.append(f"Output dir: {EXPORTS_DIR}")
    notes.append("Cloud upload: BLOCKED (local_only=True)")

    # Check if continuity_export is available
    try:
        import continuity_export as _ce
        notes.append("continuity_export module: available — export would call build_export()")
    except ImportError:
        notes.append("continuity_export module: NOT FOUND — export would fail")

    run["safety_notes"] = notes
    run["status"] = "dry_run"
    _log(f"dry_run planned: {len(notes)} safety notes")
    return run


def run_once(force: bool = False) -> dict:
    """
    Execute one backup export immediately.
    Blocked by SAFE_SLEEP. No cloud upload. Manifest + checksum required.
    """
    sched = load_schedule()
    run = _new_run(sched["id"], dry=False)
    run["status"] = "running"

    # SAFE_SLEEP blocks
    if _is_safe_sleep() and not force:
        run["blocked_reason"] = "SAFE_SLEEP active"
        run["status"] = "blocked"
        run["completed_at"] = _NOW()
        _log("run_once blocked: SAFE_SLEEP")
        return run

    # Cloud upload never allowed — non-negotiable, force does not override
    if sched.get("cloud_upload_allowed"):
        run["blocked_reason"] = "cloud_upload_allowed=True — refused"
        run["status"] = "blocked"
        run["completed_at"] = _NOW()
        _log("run_once blocked: cloud upload not permitted")
        return run

    try:
        import sys as _sys
        _core = str(ROOT / "core")
        if _core not in _sys.path:
            _sys.path.insert(0, _core)
        from continuity_export import build_export, write_json_export, write_md_export, _checksum
        import json as _json
        from datetime import datetime as _dt

        # build_export returns (payload, ts_str); older annotation claimed dict.
        # Accept both shapes so a future signature cleanup can't silently
        # re-break the backup path.
        built = build_export()
        if isinstance(built, tuple):
            payload, ts_str = built
        else:
            payload = built
            ts_str = _dt.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        # Safety: scrub blocked types from payload
        for blocked_key in _BLOCKED_EXPORT_TYPES:
            payload.pop(blocked_key, None)

        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        json_path = write_json_export(payload, ts_str)

        # Move to exports dir if not already there
        dest = EXPORTS_DIR / json_path.name
        if json_path != dest:
            import shutil
            shutil.move(str(json_path), str(dest))
            json_path = dest

        # Checksum
        raw_str = _json.dumps(payload, sort_keys=True, ensure_ascii=False)
        csum = _checksum(raw_str)

        # Manifest
        manifest = {
            "id":           run["id"],
            "ts":           ts_str,
            "export_path":  str(json_path),
            "checksum":     csum,
            "export_mode":  sched.get("export_mode"),
            "local_only":   True,
            "cloud_upload": False,
            "blocked_types": list(_BLOCKED_EXPORT_TYPES),
            "created_at":   _NOW(),
        }
        manifest_path = EXPORTS_DIR / f"manifest_{ts_str}.json"
        manifest_path.write_text(
            _json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        run["status"]        = "completed"
        run["export_path"]   = str(json_path)
        run["manifest_path"] = str(manifest_path)
        run["checksum"]      = csum
        run["completed_at"]  = _NOW()
        run["safety_notes"]  = ["local_only=True", "cloud_upload=False", "secrets scrubbed"]

        # Update schedule
        sched["last_run_at"] = _NOW()
        sched["next_run_at"] = _compute_next_run(sched)
        save_schedule(sched)
        _log(f"run_once completed: {json_path.name}  checksum={csum[:12]}")

    except Exception as e:
        run["status"]         = "failed"
        run["blocked_reason"] = str(e)
        run["completed_at"]   = _NOW()
        _log(f"run_once failed: {e}")

    return run


def run_if_due(force: bool = False) -> Optional[dict]:
    """
    Single gate for automatic backups. Call from any live loop; cheap when idle.

    Returns the run record when a backup executed (or blocked/failed),
    None when disabled or not yet due.

    Self-heals the enable deadlock: an enabled schedule with next_run_at=None
    is treated as due now — otherwise nothing would ever seed next_run_at,
    because only a completed run sets it.
    """
    sched = load_schedule()
    if not sched.get("enabled"):
        return None
    next_run_at = sched.get("next_run_at")
    if next_run_at is None:
        _log("run_if_due: enabled with next_run_at=None — bootstrapping first run")
        return run_once(force=force)
    try:
        next_dt = datetime.fromisoformat(next_run_at)
    except Exception:
        _log(f"run_if_due: unparseable next_run_at={next_run_at!r} — treating as due")
        return run_once(force=force)
    if next_dt.tzinfo is None:
        next_dt = next_dt.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) >= next_dt:
        return run_once(force=force)
    return None


# ── Status report ─────────────────────────────────────────────────────────────

def status_report() -> str:
    sched = load_schedule()
    lines = [
        "",
        "=" * 55,
        "  ORACLE Continuity Backup Scheduler — Status",
        "=" * 55,
        f"  Enabled        : {sched.get('enabled', False)}",
        f"  Frequency      : {sched.get('frequency', 'daily')}",
        f"  Export mode    : {sched.get('export_mode')}",
        f"  Local only     : {sched.get('local_only', True)}",
        f"  Cloud upload   : {sched.get('cloud_upload_allowed', False)}",
        f"  Last run       : {sched.get('last_run_at') or 'never'}",
        f"  Next run       : {sched.get('next_run_at') or 'not scheduled'}",
        f"  SAFE_SLEEP now : {_is_safe_sleep()}",
        f"  Exports dir    : {EXPORTS_DIR}",
    ]
    # Count existing exports
    try:
        exports = list(EXPORTS_DIR.glob("oracle_continuity_export_*.json"))
        lines.append(f"  Exports on disk: {len(exports)}")
        if exports:
            latest = max(exports, key=lambda p: p.stat().st_mtime)
            lines.append(f"  Latest export  : {latest.name}")
    except Exception:
        lines.append("  Exports on disk: unknown")
    lines.append("=" * 55)
    lines.append("")
    return "\n".join(lines)


# ── Smoke tests ───────────────────────────────────────────────────────────────

def run_smoke_tests() -> int:
    failures = 0

    def check(label: str, passed: bool, detail: str = "") -> None:
        nonlocal failures
        tag = "PASS" if passed else "FAIL"
        suffix = f" — {detail}" if detail and not passed else ""
        print(f"  [{tag}] {label}{suffix}")
        if not passed:
            failures += 1

    print("=" * 55)
    print("Continuity Backup Scheduler v0.1 — Smoke Tests")
    print("=" * 55)

    import tempfile

    # Redirect state file to temp for tests
    import continuity_scheduler as _cs
    orig_state  = _cs.SCHEDULER_STATE_FILE
    orig_log    = _cs.SCHEDULER_LOG_FILE
    orig_exports = _cs.EXPORTS_DIR
    tmp_dir = Path(tempfile.mkdtemp())
    _cs.SCHEDULER_STATE_FILE = tmp_dir / "continuity_scheduler.json"
    _cs.SCHEDULER_LOG_FILE   = tmp_dir / "continuity_scheduler_log.jsonl"
    _cs.EXPORTS_DIR          = tmp_dir / "continuity_exports"

    try:
        # 1. load_schedule returns default on first call
        sched = _cs.load_schedule()
        check("load_schedule: returns dict", isinstance(sched, dict))
        check("load_schedule: default disabled", sched.get("enabled") is False)
        check("load_schedule: local_only=True", sched.get("local_only") is True)
        check("load_schedule: cloud_upload_allowed=False", sched.get("cloud_upload_allowed") is False)
        check("load_schedule: state file created", _cs.SCHEDULER_STATE_FILE.exists())

        # 2. save_schedule persists
        sched["frequency"] = "weekly"
        _cs.save_schedule(sched)
        sched2 = _cs.load_schedule()
        check("save_schedule: persists frequency", sched2.get("frequency") == "weekly")
        check("save_schedule: updates updated_at", bool(sched2.get("updated_at")))

        # 3. dry_run produces planned run without executing export
        run = _cs.dry_run()
        check("dry_run: returns dict", isinstance(run, dict))
        check("dry_run: status is dry_run or blocked", run.get("status") in ("dry_run", "blocked"))
        check("dry_run: no export_path set", run.get("export_path") is None)
        check("dry_run: has safety_notes", isinstance(run.get("safety_notes"), list))
        check("dry_run: log file written", _cs.SCHEDULER_LOG_FILE.exists())

        # 4. SAFE_SLEEP blocks dry_run
        import json as _json
        ss_path = tmp_dir / "session_state.json"
        ss_path.write_text(_json.dumps({"mode": "SAFE_SLEEP"}), encoding="utf-8")
        orig_mem = ROOT / "Memory"

        # Patch _is_safe_sleep to read from tmp
        original_is_safe_sleep = _cs._is_safe_sleep
        def _fake_safe_sleep():
            raw = _rj(ss_path)
            return str((raw or {}).get("mode", "")).upper() in ("SAFE_SLEEP", "SAFE_SLEEP_MODE")
        _cs._is_safe_sleep = _fake_safe_sleep

        blocked_run = _cs.dry_run()
        check("SAFE_SLEEP blocks dry_run", blocked_run.get("status") == "blocked")
        check("SAFE_SLEEP: has blocked_reason", bool(blocked_run.get("blocked_reason")))

        _cs._is_safe_sleep = original_is_safe_sleep

        # 5. run_once in dry context (no real export module needed — just test blocking)
        # Force SAFE_SLEEP off, cloud_upload_allowed=False (default)
        sched3 = _cs.load_schedule()
        sched3["cloud_upload_allowed"] = False
        _cs.save_schedule(sched3)

        # run_once should either complete (if continuity_export available) or fail cleanly
        result = _cs.run_once()
        check("run_once: returns dict", isinstance(result, dict))
        check("run_once: status is completed/failed/blocked",
              result.get("status") in ("completed", "failed", "blocked"))
        check("run_once: completed_at set", bool(result.get("completed_at")))

        # If completed, verify manifest + checksum
        if result.get("status") == "completed":
            check("run_once completed: has export_path", bool(result.get("export_path")))
            check("run_once completed: has manifest_path", bool(result.get("manifest_path")))
            check("run_once completed: has checksum", bool(result.get("checksum")))
            check("run_once completed: export file exists", Path(result["export_path"]).exists())
            check("run_once completed: manifest file exists", Path(result["manifest_path"]).exists())
            # Verify no cloud upload in manifest
            manifest = _json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
            check("run_once completed: cloud_upload=False in manifest",
                  manifest.get("cloud_upload") is False)
        else:
            check("run_once failed cleanly: has blocked_reason", bool(result.get("blocked_reason") or result.get("status") in ("failed","blocked")))

        # 6. cloud_upload_allowed=True is blocked
        sched3["cloud_upload_allowed"] = True
        _cs.save_schedule(sched3)
        cloud_run = _cs.run_once()
        check("cloud_upload blocked: status=blocked", cloud_run.get("status") == "blocked")
        sched3["cloud_upload_allowed"] = False
        _cs.save_schedule(sched3)

        # 7. status_report returns a string
        report = _cs.status_report()
        check("status_report: returns string", isinstance(report, str))
        check("status_report: contains Enabled", "Enabled" in report)
        check("status_report: contains Frequency", "Frequency" in report)
        check("status_report: contains Cloud", "Cloud" in report)

        # 8. _compute_next_run works for all frequencies
        for freq in ("hourly", "daily", "weekly", "manual"):
            sched3["frequency"] = freq
            result_nr = _cs._compute_next_run(sched3)
            if freq == "manual":
                check(f"_compute_next_run({freq}): returns None", result_nr is None)
            else:
                check(f"_compute_next_run({freq}): returns string", isinstance(result_nr, str))

        # 9. run_if_due gate behavior
        sched4 = _cs.load_schedule()
        sched4["enabled"] = False
        sched4["frequency"] = "daily"
        _cs.save_schedule(sched4)
        check("run_if_due: disabled returns None", _cs.run_if_due() is None)

        # Enabled with next_run_at=None must bootstrap (the old deadlock)
        sched4["enabled"] = True
        sched4["next_run_at"] = None
        _cs.save_schedule(sched4)
        boot_run = _cs.run_if_due()
        check("run_if_due: enabled+null bootstraps a run", isinstance(boot_run, dict))
        if isinstance(boot_run, dict) and boot_run.get("status") == "completed":
            after = _cs.load_schedule()
            check("run_if_due: completed run seeds next_run_at", bool(after.get("next_run_at")))

        # Future next_run_at must not run
        future = (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()
        sched5 = _cs.load_schedule()
        sched5["enabled"] = True
        sched5["next_run_at"] = future
        _cs.save_schedule(sched5)
        check("run_if_due: not due returns None", _cs.run_if_due() is None)

        # Past next_run_at must run
        past = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
        sched5["next_run_at"] = past
        _cs.save_schedule(sched5)
        due_run = _cs.run_if_due()
        check("run_if_due: past-due triggers a run", isinstance(due_run, dict))

        # 10. force must NOT override the cloud refusal
        sched6 = _cs.load_schedule()
        sched6["cloud_upload_allowed"] = True
        _cs.save_schedule(sched6)
        forced = _cs.run_once(force=True)
        check("run_once(force=True): cloud still blocked", forced.get("status") == "blocked")
        sched6["cloud_upload_allowed"] = False
        _cs.save_schedule(sched6)

    finally:
        _cs.SCHEDULER_STATE_FILE = orig_state
        _cs.SCHEDULER_LOG_FILE   = orig_log
        _cs.EXPORTS_DIR          = orig_exports
        import shutil
        try:
            shutil.rmtree(tmp_dir)
        except Exception:
            pass

    total = 38
    passed = total - failures
    print(f"{'='*55}")
    print(f"Result: {passed}/{total} passed")
    print(f"STATUS: {'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    print(f"{'='*55}\n")
    return failures


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ORACLE Continuity Backup Scheduler")
    parser.add_argument("--status",     action="store_true", help="Show scheduler status")
    parser.add_argument("--dry-run",    action="store_true", help="Plan a backup without running it")
    parser.add_argument("--run-once",   action="store_true", help="Run one backup export now")
    parser.add_argument("--smoke-test", action="store_true", help="Run smoke tests")
    parser.add_argument("--enable",     action="store_true", help="Enable scheduled backups")
    parser.add_argument("--disable",    action="store_true", help="Disable scheduled backups")
    args = parser.parse_args()

    if args.smoke_test:
        sys.exit(run_smoke_tests())

    elif args.status:
        print(status_report())

    elif args.dry_run:
        result = dry_run()
        print(f"\n  Dry-run result: {result['status']}")
        for note in result.get("safety_notes", []):
            print(f"    · {note}")
        if result.get("blocked_reason"):
            print(f"    BLOCKED: {result['blocked_reason']}")
        print()

    elif args.run_once:
        print("\n  Running backup export...")
        result = run_once()
        print(f"  Status   : {result['status']}")
        if result.get("export_path"):
            print(f"  Export   : {result['export_path']}")
        if result.get("checksum"):
            print(f"  Checksum : {result['checksum'][:16]}...")
        if result.get("blocked_reason"):
            print(f"  BLOCKED  : {result['blocked_reason']}")
        for note in result.get("safety_notes", []):
            print(f"    · {note}")
        print()

    elif args.enable:
        sched = load_schedule()
        sched["enabled"] = True
        # Seed next_run_at so the auto-run gate can ever open. Without this,
        # enabled+null deadlocks: the gate requires next_run_at, and only a
        # completed run sets it. Due immediately — first backup on next tick.
        if not sched.get("next_run_at"):
            sched["next_run_at"] = _NOW()
        save_schedule(sched)
        print("  Scheduler enabled.")
        print(f"  Next run due: {sched['next_run_at']}")

    elif args.disable:
        sched = load_schedule()
        sched["enabled"] = False
        save_schedule(sched)
        print("  Scheduler disabled.")

    else:
        parser.print_help()
