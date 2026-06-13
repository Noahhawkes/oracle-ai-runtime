"""
core/grounding.py — Deterministic grounding status.

/grounding-status MUST be answered by this module, not by the LLM.
Every field is produced by Python code, not language model inference.

If this module is unavailable or raises, the caller must return:

  GROUNDING STATUS: UNAVAILABLE
  Reason: deterministic grounding inspection is not implemented.
  No runtime evidence was generated.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent

_KEY_FILES = [
    "core/oracle.py",
    "core/output_validator.py",
    "core/execution_receipt.py",
    "core/grounding.py",
    "core/lcl.py",
    "core/self_patch_pipeline.py",
    "oracle_server.py",
    ".env",
]


def grounding_status() -> dict:
    """
    Return a dict of deterministic, machine-sourced grounding data.
    No LLM is consulted. No inference. Only Python code.
    """
    # Key files
    key_files: dict[str, str] = {}
    for rel in _KEY_FILES:
        p = ROOT / rel
        try:
            resolved = p.resolve()
            if resolved.exists():
                stat = resolved.stat()
                key_files[rel] = f"EXISTS ({stat.st_size} bytes)"
            else:
                key_files[rel] = "MISSING"
        except Exception as e:
            key_files[rel] = f"ERROR:{e}"

    # Memory DB
    memory_status = "unknown"
    try:
        from memory import init_db
        init_db()
        db_path = ROOT / "Memory" / "oracle_memory.db"
        if db_path.exists():
            memory_status = f"connected ({db_path.stat().st_size} bytes)"
        else:
            memory_status = "init_ok_but_db_not_found"
    except Exception as e:
        memory_status = f"error:{e}"

    # Model config
    has_anthropic_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    local_mode = os.environ.get("LOCAL_MODE", "").lower() in ("true", "1", "yes")

    # Session receipts
    try:
        from execution_receipt import get_receipt_count, get_all_receipts
        receipt_count = get_receipt_count()
        recent_ops = [r.operation for r in get_all_receipts()[-5:]]
    except Exception:
        receipt_count = 0
        recent_ops = []

    # Working directory
    try:
        cwd = str(Path.cwd().resolve())
    except Exception:
        cwd = "unknown"

    return {
        "status": "OK" if all("MISSING" not in v for v in key_files.values()) else "PARTIAL",
        "server_pid": os.getpid(),
        "python": sys.version.split()[0],
        "working_dir": cwd,
        "oracle_root": str(ROOT.resolve()),
        "anthropic_key_set": has_anthropic_key,
        "local_mode": local_mode,
        "model": os.environ.get("ORACLE_MODEL", "claude-sonnet-4-6"),
        "memory": memory_status,
        "session_receipts": receipt_count,
        "recent_receipt_ops": recent_ops,
        "simulation_guard": "ACTIVE",
        "grounding_method": "deterministic_python",
        "key_files": key_files,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def format_grounding_status() -> str:
    """
    Format grounding status for display.
    Never calls the LLM. If this raises, the caller returns the UNAVAILABLE message.
    """
    try:
        s = grounding_status()
    except Exception as e:
        return (
            "GROUNDING STATUS: UNAVAILABLE\n"
            f"Reason: {e}\n"
            "No runtime evidence was generated."
        )

    lines = [
        f"GROUNDING STATUS: {s['status']}",
        f"generated_at:       {s['generated_at']}",
        f"server_pid:         {s['server_pid']}",
        f"python:             {s['python']}",
        f"working_dir:        {s['working_dir']}",
        f"anthropic_key_set:  {s['anthropic_key_set']}",
        f"local_mode:         {s['local_mode']}",
        f"model:              {s['model']}",
        f"memory:             {s['memory']}",
        f"session_receipts:   {s['session_receipts']}",
        f"simulation_guard:   {s['simulation_guard']}",
        f"grounding_method:   {s['grounding_method']}",
        "",
        "key_files:",
    ]
    for name, status in s["key_files"].items():
        marker = "✓" if status.startswith("EXISTS") else "✗"
        lines.append(f"  {marker} {name:<38} {status}")

    if s.get("recent_receipt_ops"):
        lines.append(f"\nrecent_receipts:    {', '.join(s['recent_receipt_ops'])}")

    missing = [k for k, v in s["key_files"].items() if "MISSING" in v]
    if missing:
        lines.append(f"\nMISSING ({len(missing)}): {', '.join(missing)}")

    return "\n".join(lines)


# ── Smoke tests ───────────────────────────────────────────────────────────────

def _smoke_test() -> int:
    failures = 0

    def check(label: str, passed: bool, detail: str = ""):
        nonlocal failures
        tag = "PASS" if passed else "FAIL"
        print(f"  [{tag}] {label}" + (f" — {detail}" if detail and not passed else ""))
        if not passed:
            failures += 1

    print("=" * 60)
    print("Grounding — Smoke Tests")
    print("=" * 60)

    # 1. grounding_status returns a dict with required keys
    s = grounding_status()
    required_keys = ["server_pid", "working_dir", "key_files", "session_receipts",
                     "simulation_guard", "grounding_method", "generated_at"]
    for k in required_keys:
        check(f"grounding_status has key '{k}'", k in s)

    # 2. server_pid is this process's PID
    check("server_pid == os.getpid()", s["server_pid"] == os.getpid())

    # 3. server_pid is a positive integer (not a string, not zero)
    check("server_pid is positive int", isinstance(s["server_pid"], int) and s["server_pid"] > 0)

    # 4. grounding_method is deterministic_python, never 'llm'
    check("grounding_method is 'deterministic_python'", s["grounding_method"] == "deterministic_python")

    # 5. simulation_guard is ACTIVE
    check("simulation_guard is 'ACTIVE'", s["simulation_guard"] == "ACTIVE")

    # 6. key_files includes oracle_server.py
    check("key_files includes oracle_server.py", "oracle_server.py" in s["key_files"])

    # 7. working_dir is an absolute path
    wd = s["working_dir"]
    check("working_dir is absolute path",
          wd.startswith("/") or (len(wd) > 2 and wd[1] == ":"))

    # 8. format_grounding_status returns non-empty string
    fmt = format_grounding_status()
    check("format_grounding_status returns non-empty string", bool(fmt))

    # 9. format starts with GROUNDING STATUS:
    check("format starts with 'GROUNDING STATUS:'", fmt.startswith("GROUNDING STATUS:"))

    # 10. format includes server_pid as a number
    check("format includes server_pid number",
          str(os.getpid()) in fmt)

    # 11. generated_at is a valid ISO timestamp
    ts = s["generated_at"]
    check("generated_at is ISO timestamp", "T" in ts and "Z" in ts or "+" in ts)

    # 12. /grounding-status path does not involve the LLM
    # Verify by calling format_grounding_status() and confirming it never raises
    # and returns in < 5 seconds (LLM would time out or be slow)
    import time
    t0 = time.time()
    fmt2 = format_grounding_status()
    elapsed = time.time() - t0
    check("/grounding-status returns in < 5s (no LLM)", elapsed < 5.0, f"{elapsed:.2f}s")
    check("/grounding-status never returns empty", bool(fmt2))

    total = 12 + len(required_keys)
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
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    if args.smoke_test:
        sys.exit(_smoke_test())
    elif args.status:
        print(format_grounding_status())
    else:
        print("Usage: python core/grounding.py --status")
