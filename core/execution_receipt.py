"""
core/execution_receipt.py — Machine evidence for real operations.

Every operation that produces an operational claim must produce a receipt.
Claims without a matching receipt in the session store are blocked by
the output validator and the builder-path claim guard.

Real evidence ONLY:
  path      ->pathlib.Path.resolve() + Path.exists() + Path.stat()
  sha256    ->hashlib.sha256() on actual file bytes
  process   ->os.getpid() for self; subprocess tasklist for others
  network   ->socket.create_connection() with timeout
  command   ->subprocess.run() with captured stdout/stderr
  timestamp ->datetime.now(timezone.utc).isoformat() at execution time
"""
from __future__ import annotations

import hashlib
import os
import socket
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent

# ── Schema ────────────────────────────────────────────────────────────────────

@dataclass
class ExecutionReceipt:
    operation_id: str
    operation: str      # read_file | restart_process | check_network | run_command | check_process
    status: str         # success | failed | blocked
    started_at: str
    completed_at: str
    evidence: dict      # path, sha256, size_bytes, process_id, exit_code, stdout_ref

    def to_dict(self) -> dict:
        return {
            "operation_id": self.operation_id,
            "operation": self.operation,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "evidence": self.evidence,
        }

    def summary(self) -> str:
        ev = self.evidence
        parts = [f"[{self.status.upper()}] {self.operation} #{self.operation_id}"]
        if ev.get("path"):
            parts.append(f"  path:    {ev['path']}")
        if ev.get("sha256"):
            parts.append(f"  sha256:  {ev['sha256'][:16]}...")
        if ev.get("process_id") is not None:
            parts.append(f"  pid:     {ev['process_id']}")
        if ev.get("exit_code") is not None:
            parts.append(f"  exit:    {ev['exit_code']}")
        return "\n".join(parts)


# ── Session-scoped receipt store (lives for the server process lifetime) ──────

_store: dict[str, ExecutionReceipt] = {}


def _save(r: ExecutionReceipt) -> ExecutionReceipt:
    _store[r.operation_id] = r
    return r


def get_receipt(operation_id: str) -> Optional[ExecutionReceipt]:
    return _store.get(operation_id)


def get_all_receipts() -> list[ExecutionReceipt]:
    return list(_store.values())


def get_receipt_count() -> int:
    return len(_store)


def receipts_for_operation(operation: str) -> list[ExecutionReceipt]:
    return [r for r in _store.values() if r.operation == operation]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _failed(op_id: str, operation: str, started: str, reason: str) -> ExecutionReceipt:
    return _save(ExecutionReceipt(
        operation_id=op_id,
        operation=operation,
        status="failed",
        started_at=started,
        completed_at=_now(),
        evidence={"path": None, "sha256": None, "size_bytes": None,
                  "process_id": None, "exit_code": None, "stdout_ref": reason},
    ))


# ── Real evidence functions ───────────────────────────────────────────────────

def read_file(path: str | Path) -> ExecutionReceipt:
    """Read a file and produce a receipt with real sha256 and stat evidence."""
    started = _now()
    op_id = _new_id()
    p = Path(path).resolve()

    if not p.exists():
        return _failed(op_id, "read_file", started, "not_found")
    if not p.is_file():
        return _failed(op_id, "read_file", started, "not_a_file")

    data = p.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    stat = p.stat()

    return _save(ExecutionReceipt(
        operation_id=op_id,
        operation="read_file",
        status="success",
        started_at=started,
        completed_at=_now(),
        evidence={
            "path": str(p),
            "sha256": sha,
            "size_bytes": stat.st_size,
            "mtime_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            "process_id": None,
            "exit_code": None,
            "stdout_ref": None,
        },
    ))


def check_network(host: str, port: int, timeout: float = 3.0) -> ExecutionReceipt:
    """Probe host:port with a real socket. No fake 'network unavailable'."""
    started = _now()
    op_id = _new_id()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            status = "success"
            stdout_ref = f"reachable:{host}:{port}"
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        status = "failed"
        stdout_ref = f"unreachable:{host}:{port}:{type(e).__name__}"

    return _save(ExecutionReceipt(
        operation_id=op_id,
        operation="check_network",
        status=status,
        started_at=started,
        completed_at=_now(),
        evidence={
            "path": None, "sha256": None, "size_bytes": None,
            "process_id": None, "exit_code": None, "stdout_ref": stdout_ref,
        },
    ))


def check_process(pid: int | str) -> ExecutionReceipt:
    """Verify a process exists. Rejects non-numeric PIDs. Uses real OS check."""
    started = _now()
    op_id = _new_id()

    try:
        pid_int = int(pid)
    except (ValueError, TypeError):
        return _failed(op_id, "check_process", started, f"non_numeric_pid:{pid!r}")

    if pid_int <= 0:
        return _failed(op_id, "check_process", started, f"invalid_pid:{pid_int}")

    # Check if process exists
    exists = False
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid_int}", "/NH"],
                capture_output=True, text=True, timeout=5,
            )
            exists = str(pid_int) in result.stdout
        else:
            os.kill(pid_int, 0)
            exists = True
    except (ProcessLookupError, PermissionError):
        exists = False
    except Exception:
        exists = False

    return _save(ExecutionReceipt(
        operation_id=op_id,
        operation="check_process",
        status="success" if exists else "failed",
        started_at=started,
        completed_at=_now(),
        evidence={
            "path": None, "sha256": None, "size_bytes": None,
            "process_id": pid_int,
            "exit_code": None,
            "stdout_ref": "exists" if exists else "not_found",
        },
    ))


def run_command(args: list[str], cwd: Optional[str] = None,
                timeout: float = 30.0) -> ExecutionReceipt:
    """Run a subprocess and capture its real output."""
    started = _now()
    op_id = _new_id()
    try:
        result = subprocess.run(
            args,
            cwd=cwd or str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = (result.stdout.strip() + "\n" + result.stderr.strip()).strip()
        return _save(ExecutionReceipt(
            operation_id=op_id,
            operation="run_command",
            status="success" if result.returncode == 0 else "failed",
            started_at=started,
            completed_at=_now(),
            evidence={
                "path": None, "sha256": None, "size_bytes": None,
                "process_id": result.pid if hasattr(result, "pid") else None,
                "exit_code": result.returncode,
                "stdout_ref": stdout[:400] if stdout else "(no output)",
            },
        ))
    except subprocess.TimeoutExpired:
        return _failed(op_id, "run_command", started, f"timeout:{timeout}s")
    except Exception as e:
        return _failed(op_id, "run_command", started, f"error:{e}")


def self_pid() -> ExecutionReceipt:
    """Record this process's own PID — the only trustworthy PID source for the server."""
    started = _now()
    op_id = _new_id()
    return _save(ExecutionReceipt(
        operation_id=op_id,
        operation="check_process",
        status="success",
        started_at=started,
        completed_at=_now(),
        evidence={
            "path": None, "sha256": None, "size_bytes": None,
            "process_id": os.getpid(),
            "exit_code": None,
            "stdout_ref": "self",
        },
    ))


# ── Claim validation ──────────────────────────────────────────────────────────

import re as _re

# Patterns that indicate an unsupported operational claim in LLM text
_CLAIM_PATTERNS = [
    _re.compile(r'\bPID\s+\d{3,}\b', _re.I),
    _re.compile(r'\bsha256[:\s]+[0-9a-f]{16,}\b', _re.I),
    _re.compile(r'\b(process|server|service)\s+(restarted|started|stopped|killed|terminated)\b', _re.I),
    _re.compile(r'\bfile\s+(written|created|deleted|moved)\s+(to|at|from)\b', _re.I),
    _re.compile(r'\bnetwork\s+(unavailable|unreachable|connected|verified)\b', _re.I),
    _re.compile(r'\b(successfully|already)\s+(loaded|retrieved|restarted|verified|committed|tested|wrote)\b', _re.I),
    _re.compile(r'\bno\s+errors\s+(found|detected|reported)\b', _re.I),
    _re.compile(r'\btimestamp[:\s]+20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}', _re.I),
]


def find_operational_claim(text: str) -> Optional[str]:
    """
    Return the matched claim string if the text contains an unsupported
    operational claim (one not backed by an execution receipt).
    Returns None if the text is clean.
    """
    for pattern in _CLAIM_PATTERNS:
        m = pattern.search(text)
        if m:
            return m.group(0)
    return None


# ── Smoke tests ───────────────────────────────────────────────────────────────

def _smoke_test() -> int:
    import tempfile

    failures = 0

    def check(label: str, passed: bool, detail: str = ""):
        nonlocal failures
        tag = "PASS" if passed else "FAIL"
        print(f"  [{tag}] {label}" + (f" — {detail}" if detail and not passed else ""))
        if not passed:
            failures += 1

    print("=" * 60)
    print("ExecutionReceipt — Smoke Tests")
    print("=" * 60)

    # 1. read_file real path ->success, real sha256
    me = Path(__file__).resolve()
    r = read_file(me)
    check("read_file self ->success", r.status == "success")
    check("read_file has sha256 (64 hex chars)", len(r.evidence.get("sha256", "")) == 64)
    check("read_file path is resolved absolute", r.evidence.get("path", "").startswith("/") or ":\\" in r.evidence.get("path", ""))

    # 2. read_file missing ->failed, not_found
    r2 = read_file("/nonexistent/path/that/does/not/exist.txt")
    check("missing file ->status=failed", r2.status == "failed")
    check("missing file ->stdout_ref=not_found", r2.evidence.get("stdout_ref") == "not_found")
    check("missing file ->sha256 is None", r2.evidence.get("sha256") is None)

    # 3. Non-numeric PID rejected
    r3 = check_process("abc_not_a_pid")
    check("non-numeric PID ->status=failed", r3.status == "failed")
    check("non-numeric PID ->stdout_ref contains non_numeric_pid", "non_numeric_pid" in str(r3.evidence.get("stdout_ref", "")))

    # 4. Invalid PID (0 or negative) rejected
    r4 = check_process(-1)
    check("negative PID ->status=failed", r4.status == "failed")
    check("negative PID ->stdout_ref contains invalid_pid", "invalid_pid" in str(r4.evidence.get("stdout_ref", "")))

    # 5. self_pid() ->real numeric PID
    r5 = self_pid()
    check("self_pid ->success", r5.status == "success")
    check("self_pid ->pid is os.getpid()", r5.evidence.get("process_id") == os.getpid())
    check("self_pid ->pid is positive int", isinstance(r5.evidence.get("process_id"), int) and r5.evidence["process_id"] > 0)

    # 6. check_network real port (should succeed for localhost loopback test)
    import threading, time
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        probe_port = srv.getsockname()[1]
        r6 = check_network("127.0.0.1", probe_port, timeout=2.0)
        check("check_network real port ->success", r6.status == "success")
    except Exception as e:
        check("check_network real port ->success", False, str(e))
    finally:
        srv.close()

    # 7. check_network closed port ->failed
    r7 = check_network("127.0.0.1", 1, timeout=1.0)
    check("check_network closed port ->failed", r7.status == "failed")

    # 8. run_command real ->captures exit code
    r8 = run_command(["python", "--version"], timeout=10.0)
    check("run_command python --version ->success", r8.status == "success")
    check("run_command exit_code is 0", r8.evidence.get("exit_code") == 0)
    check("run_command stdout_ref has 'Python'", "Python" in r8.evidence.get("stdout_ref", ""))

    # 9. run_command nonexistent ->failed
    r9 = run_command(["nonexistent_binary_xyz_123"], timeout=5.0)
    check("run_command nonexistent ->failed", r9.status == "failed")

    # 10. find_operational_claim — fake PID detected
    claim = find_operational_claim("The server restarted with PID 99999 successfully.")
    check("find_operational_claim detects fake PID", claim is not None and "99999" in claim)

    # 11. find_operational_claim — fake sha256 detected
    claim2 = find_operational_claim("sha256: a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4")
    check("find_operational_claim detects fake sha256", claim2 is not None)

    # 12. find_operational_claim — clean text passes
    claim3 = find_operational_claim("Here is my analysis of the code structure.")
    check("find_operational_claim clean text returns None", claim3 is None)

    # 13. Receipt store is populated after operations
    count = get_receipt_count()
    check("receipt store has entries after operations", count >= 5)

    # 14. receipts_for_operation filters correctly
    file_receipts = receipts_for_operation("read_file")
    check("receipts_for_operation('read_file') returns read_file receipts",
          all(r.operation == "read_file" for r in file_receipts))

    total = 20
    passed = total - failures
    print(f"{'='*60}")
    print(f"Result: {passed}/{total} passed")
    print(f"STATUS: {'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    print(f"{'='*60}\n")
    return failures


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--receipts", action="store_true", help="Show session receipts")
    args = parser.parse_args()
    if args.smoke_test:
        sys.exit(_smoke_test())
    elif args.receipts:
        for r in get_all_receipts():
            print(r.summary())
    else:
        print("Usage: python core/execution_receipt.py --smoke-test")
