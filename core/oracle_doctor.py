"""
core/oracle_doctor.py - ORACLE enforced boot gate v0.3.

Daemon mode must run Doctor first. Exit 1 means refuse boot.
Stdlib only. Writes only local runtime state and kernel sidecar.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

MODULE_VERSION = "0.3"

ROOT = Path(__file__).parent.parent
STATE_DIR = Path(os.environ.get("ORACLE_STATE_DIR", str(ROOT / "state")))
KERNEL_FILE = ROOT / "kernel.md"
KERNEL_SHA_FILE = ROOT / "kernel.sha256"


def self_id_line() -> str:
    digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]
    return f"{Path(__file__).name} v{MODULE_VERSION} sha256 {digest}"


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".tmp.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _pid_live(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    try:
        if os.name == "nt":
            result = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True, timeout=5)
            return str(pid) in result.stdout
        os.kill(pid, 0)
        return True
    except Exception:
        return False


@dataclass
class DoctorResult:
    ok: bool
    failures: list[str]
    warnings: list[str]
    skips: list[str]
    boot_type: str
    state_dir: Path
    lock_acquired: bool = False


def _ledger(event: str, extra: dict | None = None, *, state_dir: Path = STATE_DIR) -> None:
    entry = {"ts": _now(), "event": event}
    if extra:
        entry.update(extra)
    path = state_dir / "doctor_ledger.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _boot_type(state_dir: Path, *, consume_clean: bool = True) -> str:
    clean = state_dir / "clean_shutdown.marker"
    heartbeat = state_dir / "heartbeat.json"
    if clean.exists():
        if consume_clean:
            clean.unlink()
        return "CLEAN"
    if heartbeat.exists():
        return "RECOVERED_FROM_CRASH"
    return "FIRST_BOOT"


def _check_state_path(state_dir: Path, warnings: list[str], failures: list[str]) -> None:
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        probe = state_dir / ".doctor_write_probe"
        _atomic_write_text(probe, "ok\n")
        probe.unlink(missing_ok=True)
    except Exception as exc:
        failures.append(f"state path not writable: {state_dir}: {exc}")
    lower = str(state_dir).lower()
    if any(marker in lower for marker in ("my drive", "google drive", "onedrive", "dropbox")):
        warnings.append(f"state path is inside sync folder: {state_dir}")


def _check_kernel(warnings: list[str], failures: list[str]) -> None:
    if not KERNEL_FILE.exists() or not KERNEL_FILE.read_text(encoding="utf-8", errors="replace").strip():
        failures.append(f"kernel.md missing or empty: {KERNEL_FILE}")
        return
    digest = _sha256(KERNEL_FILE)
    if not KERNEL_SHA_FILE.exists():
        _atomic_write_text(KERNEL_SHA_FILE, digest + "\n")
        warnings.append("kernel.sha256 missing; recorded trust-on-first-use sidecar")
        return
    recorded = KERNEL_SHA_FILE.read_text(encoding="utf-8").strip()
    if recorded != digest:
        failures.append("kernel.md sha256 mismatch; run --accept-kernel only after Noah verifies the change")


def _check_wake_memory(warnings: list[str], failures: list[str]) -> None:
    path = ROOT / "Memory" / "wake_memory.json"
    if not path.exists():
        warnings.append("wake_memory.json missing")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("wake memory must be object")
    except Exception as exc:
        failures.append(f"wake_memory.json corrupt: {exc}")


def _check_conflicts(state_dir: Path, failures: list[str]) -> None:
    if not state_dir.exists():
        return
    for path in state_dir.rglob("*"):
        name = path.name.lower()
        if "conflict" in name or " (1)" in name or " (2)" in name:
            failures.append(f"sync/conflict artifact in state dir: {path}")


def _check_raise_hand(state_dir: Path, failures: list[str]) -> int:
    queue = state_dir / "raise_hand_queue.json"
    if not queue.exists():
        return 0
    try:
        data = json.loads(queue.read_text(encoding="utf-8"))
        return len([r for r in data.get("requests", []) if r.get("status") == "OPEN"])
    except Exception as exc:
        failures.append(f"raise_hand_queue.json corrupt: {exc}")
        return 0


def _acquire_lock(state_dir: Path, warnings: list[str], failures: list[str]) -> bool:
    lock = state_dir / "oracle.lock"
    if lock.exists():
        try:
            pid = int(lock.read_text(encoding="utf-8").strip())
        except Exception:
            pid = -1
        if _pid_live(pid):
            failures.append(f"already running with PID {pid}")
            return False
        lock.unlink(missing_ok=True)
        warnings.append(f"removed stale oracle.lock for dead PID {pid}")
    _atomic_write_text(lock, str(os.getpid()) + "\n")
    return True


def _git_status(warnings: list[str], skips: list[str]) -> None:
    if not (ROOT / ".git").exists():
        skips.append("git status skipped: no repo")
        return
    try:
        result = subprocess.run(["git", "status", "--short"], cwd=str(ROOT), capture_output=True, text=True, timeout=8)
        if result.stdout.strip():
            warnings.append("git working tree dirty")
    except Exception as exc:
        skips.append(f"git status skipped: {exc}")


def _check_env(failures: list[str]) -> None:
    if os.environ.get("ORACLE_ACTUATION", "").lower() in {"1", "true", "yes", "enabled"}:
        failures.append("ORACLE_ACTUATION enabled at boot")


def run_check(*, state_dir: Path = STATE_DIR, acquire_lock: bool = True) -> DoctorResult:
    failures: list[str] = []
    warnings: list[str] = []
    skips: list[str] = []
    state_dir = Path(state_dir)
    boot_type = _boot_type(state_dir)
    _check_state_path(state_dir, warnings, failures)
    _check_kernel(warnings, failures)
    _check_wake_memory(warnings, failures)
    _check_conflicts(state_dir, failures)
    open_count = _check_raise_hand(state_dir, failures)
    locked = _acquire_lock(state_dir, warnings, failures) if acquire_lock else False
    _git_status(warnings, skips)
    _check_env(failures)
    ok = not failures
    if ok:
        _atomic_write_text(state_dir / "heartbeat.json", json.dumps({"ts": _now(), "pid": os.getpid(), "boot_type": boot_type}) + "\n")
        _ledger("BOOT_OK", {"boot_type": boot_type, "open_queue_count": open_count}, state_dir=state_dir)
    else:
        if locked:
            release_lock(state_dir=state_dir)
        _ledger("BOOT_REFUSED", {"boot_type": boot_type, "failures": failures}, state_dir=state_dir)
    return DoctorResult(ok, failures, warnings, skips, boot_type, state_dir, locked)


def format_startup_screen(result: DoctorResult) -> str:
    lines = [self_id_line(), "", "ORACLE STARTUP CHECK", ""]
    lines.append(f"Boot type: {result.boot_type}")
    lines.append(f"State path: {result.state_dir}")
    for warning in result.warnings:
        lines.append(f"WARN: {warning}")
    for skip in result.skips:
        lines.append(f"SKIP: {skip}")
    if result.failures:
        lines.append("")
        lines.append("FAILURES:")
        for failure in result.failures:
            lines.append(f"- {failure}")
        lines.append("BOOT REFUSED")
        return "\n".join(lines)
    try:
        from raise_hand import RaiseHandQueue
        open_count = RaiseHandQueue(result.state_dir).tray_badge()
    except Exception:
        open_count = 0
    lines.extend([
        "Wake Memory: OK",
        "Raise-Hand queue: OK",
        "Single-instance lock: OK",
        "Heartbeat: active",
        "External actuation: disabled",
        f"Noah authority required: {open_count if open_count else 'none'}",
        "",
        "Oracle is awake and operating in local governed mode.",
    ])
    return "\n".join(lines)


def release_lock(*, state_dir: Path = STATE_DIR) -> None:
    lock = Path(state_dir) / "oracle.lock"
    if lock.exists():
        lock.unlink()


def shutdown_clean(*, state_dir: Path = STATE_DIR) -> None:
    state_dir = Path(state_dir)
    _atomic_write_text(state_dir / "clean_shutdown.marker", _now() + "\n")
    (state_dir / "heartbeat.json").unlink(missing_ok=True)
    release_lock(state_dir=state_dir)
    _ledger("CLEAN_SHUTDOWN", {}, state_dir=state_dir)


def accept_kernel() -> None:
    if not KERNEL_FILE.exists():
        raise SystemExit("kernel.md missing")
    _atomic_write_text(KERNEL_SHA_FILE, _sha256(KERNEL_FILE) + "\n")


def run_doctor() -> str:
    return format_startup_screen(run_check(acquire_lock=False))


def run_smoke_tests() -> int:
    import shutil

    print(self_id_line())
    tmp = Path(tempfile.mkdtemp(prefix="oracle_doctor_test_"))
    passed = 0
    failed = 0
    orig_state = STATE_DIR
    orig_kernel = globals()["KERNEL_FILE"]
    orig_sha = globals()["KERNEL_SHA_FILE"]

    def check(name: str, cond: bool) -> None:
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            failed += 1
            print(f"  [FAIL] {name}")

    try:
        globals()["KERNEL_FILE"] = tmp / "kernel.md"
        globals()["KERNEL_SHA_FILE"] = tmp / "kernel.sha256"
        globals()["KERNEL_FILE"].write_text("kernel\n", encoding="utf-8")
        state = tmp / "state"
        (ROOT / "Memory").mkdir(exist_ok=True)

        result = run_check(state_dir=state)
        check("check passes with TOFU warning", result.ok and any("TOFU" in w or "trust-on-first-use" in w for w in result.warnings))
        check("heartbeat written", (state / "heartbeat.json").exists())
        check("lock acquired", (state / "oracle.lock").exists())
        shutdown_clean(state_dir=state)
        check("shutdown_clean marker written", (state / "clean_shutdown.marker").exists())
        clean = run_check(state_dir=state)
        check("clean boot type consumed marker", clean.boot_type == "CLEAN" and not (state / "clean_shutdown.marker").exists())
        release_lock(state_dir=state)
        (state / "heartbeat.json").write_text("{}", encoding="utf-8")
        recovered = run_check(state_dir=state)
        check("crash boot type detected", recovered.boot_type == "RECOVERED_FROM_CRASH")
        release_lock(state_dir=state)
        (state / "raise_hand_queue.json").write_text("{bad", encoding="utf-8")
        bad = run_check(state_dir=state)
        check("corrupt queue fails", not bad.ok and any("raise_hand_queue" in f for f in bad.failures))
        (state / "raise_hand_queue.json").unlink(missing_ok=True)
        release_lock(state_dir=state)
        (state / "file conflict.json").write_text("x", encoding="utf-8")
        conflict = run_check(state_dir=state)
        check("sync conflict file fails", not conflict.ok and any("conflict" in f for f in conflict.failures))
        (state / "file conflict.json").unlink(missing_ok=True)
        release_lock(state_dir=state)
        (state / "oracle.lock").write_text(str(os.getpid()), encoding="utf-8")
        locked = run_check(state_dir=state)
        check("live lock fails", not locked.ok and any("already running" in f for f in locked.failures))
        release_lock(state_dir=state)
        globals()["KERNEL_FILE"].write_text("changed\n", encoding="utf-8")
        mismatch = run_check(state_dir=state)
        check("kernel mismatch fails", not mismatch.ok and any("sha256 mismatch" in f for f in mismatch.failures))
        accept_kernel()
        fixed = run_check(state_dir=state)
        check("accept_kernel fixes mismatch", fixed.ok)
        release_lock(state_dir=state)
        old = os.environ.get("ORACLE_ACTUATION")
        os.environ["ORACLE_ACTUATION"] = "enabled"
        env_fail = run_check(state_dir=state)
        check("actuation env fails boot", not env_fail.ok and any("ORACLE_ACTUATION" in f for f in env_fail.failures))
        if old is None:
            del os.environ["ORACLE_ACTUATION"]
        else:
            os.environ["ORACLE_ACTUATION"] = old
        release_lock(state_dir=state)
        screen = format_startup_screen(run_check(state_dir=state))
        check("startup screen has awake line", "Oracle is awake and operating in local governed mode." in screen)
        check("run_doctor returns string", isinstance(run_doctor(), str))
    finally:
        globals()["STATE_DIR"] = orig_state
        globals()["KERNEL_FILE"] = orig_kernel
        globals()["KERNEL_SHA_FILE"] = orig_sha
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{passed}/{passed + failed} oracle_doctor smoke tests passed.")
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--shutdown-clean", action="store_true")
    parser.add_argument("--release-lock", action="store_true")
    parser.add_argument("--accept-kernel", action="store_true")
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    if args.smoke_test:
        return run_smoke_tests()
    if args.accept_kernel:
        accept_kernel()
        print(self_id_line())
        print("kernel.sha256 accepted")
        return 0
    if args.shutdown_clean:
        shutdown_clean()
        print(self_id_line())
        print("clean shutdown recorded")
        return 0
    if args.release_lock:
        release_lock()
        print(self_id_line())
        print("lock released")
        return 0
    result = run_check()
    print(format_startup_screen(result))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
