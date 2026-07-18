"""Build Witness receipts for ORACLE construction events.

This layer sits above creation_witness. The creation witness records metadata
about files changing; this module records the construction event: why the build
changed, who requested it, who executed it, what tests were run, and what local
evidence links the event to the runtime timeline.

Boundary: this module writes only under Memory/build_witness. It never captures
file contents, uploads data, commits, pushes, deletes, moves, or promotes canon.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from root import ROOT as RUNTIME_ROOT
except Exception:  # pragma: no cover
    RUNTIME_ROOT = Path(__file__).resolve().parents[1]

MEMORY_DIR = RUNTIME_ROOT / "Memory"
BUILD_DIR = MEMORY_DIR / "build_witness"
RECEIPTS_DIR = BUILD_DIR / "receipts"
RECEIPT_LOG = BUILD_DIR / "build_receipts.jsonl"
LATEST_RECEIPT = BUILD_DIR / "latest_build_receipt.json"
CREATION_FEED = MEMORY_DIR / "creation_feed.jsonl"

SCHEMA_VERSION = "oracle.build_witness.v1"
PROJECT = "ORACLE"
DEFAULT_REQUESTED_BY = "Noah.Physical"
DEFAULT_EXECUTED_BY = "Codex"

MAX_GIT_LINES = 120
MAX_CREATION_EVENTS = 25


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def hash_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _tail_lines(path: Path, limit: int) -> list[str]:
    if not path.exists():
        return []
    bounded = max(1, int(limit or 1))
    lines: deque[str] = deque(maxlen=bounded)
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped:
                    lines.append(stripped)
    except Exception:
        return []
    return list(lines)


def _read_jsonl_tail(path: Path, limit: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in _tail_lines(path, limit):
        try:
            item = json.loads(raw)
        except Exception:
            continue
        if isinstance(item, dict):
            out.append(item)
    return out


def _run_git(args: list[str]) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(RUNTIME_ROOT),
            text=True,
            capture_output=True,
            timeout=12,
            check=False,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "").strip(),
            "stderr": (proc.stderr or "").strip(),
        }
    except Exception as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
        }


def _parse_status_line(line: str) -> dict[str, str]:
    status = line[:2].strip() or "unknown"
    # Porcelain v1 normally uses two status columns followed by whitespace, but
    # some submodule/legacy lines arrive as a single status plus a path. Taking
    # everything after the two status columns preserves both shapes.
    path = line[2:].strip() if len(line) > 2 else line.strip()
    previous_path = ""
    if " -> " in path:
        previous_path, path = path.split(" -> ", 1)
    return {
        "status": status,
        "path": path.strip('"'),
        "previous_path": previous_path.strip('"'),
        "raw": line,
    }


def collect_git_state() -> dict[str, Any]:
    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    head = _run_git(["rev-parse", "HEAD"])
    status = _run_git(["status", "--short", "--untracked-files=all"])
    diff_stat = _run_git(["diff", "--stat", "--", "."])
    staged_stat = _run_git(["diff", "--cached", "--stat", "--", "."])

    status_lines = [line for line in status.get("stdout", "").splitlines() if line.strip()]
    status_lines = status_lines[:MAX_GIT_LINES]
    changed = [_parse_status_line(line) for line in status_lines]
    diff_lines = [line for line in diff_stat.get("stdout", "").splitlines() if line.strip()]
    staged_lines = [line for line in staged_stat.get("stdout", "").splitlines() if line.strip()]

    return {
        "available": bool(status.get("ok") or branch.get("ok") or head.get("ok")),
        "branch": branch.get("stdout") if branch.get("ok") else None,
        "head": head.get("stdout") if head.get("ok") else None,
        "status_count": len(changed),
        "changed_files": changed,
        "status_lines": status_lines,
        "diff_stat": diff_lines[:MAX_GIT_LINES],
        "staged_diff_stat": staged_lines[:MAX_GIT_LINES],
        "errors": [
            item.get("stderr")
            for item in (branch, head, status, diff_stat, staged_stat)
            if not item.get("ok") and item.get("stderr")
        ],
    }


def tail_creation_feed(limit: int = MAX_CREATION_EVENTS) -> list[dict[str, Any]]:
    return _read_jsonl_tail(CREATION_FEED, max(1, min(int(limit or 1), 200)))


def _normal_tests(tests_run: Any) -> list[str]:
    if tests_run is None:
        return []
    if isinstance(tests_run, str):
        return [tests_run] if tests_run.strip() else []
    if isinstance(tests_run, list):
        return [str(item) for item in tests_run if str(item).strip()]
    return [str(tests_run)]


def build_receipt(
    *,
    reason: str,
    task_id: str | None = None,
    tests_run: Any = None,
    test_result: str = "unverified",
    approval_status: str = "candidate",
    requested_by: str = DEFAULT_REQUESTED_BY,
    executed_by: str = DEFAULT_EXECUTED_BY,
    commit: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    observed_at = now_utc()
    git_state = collect_git_state()
    creation_tail = tail_creation_feed()
    files_changed = [item.get("path") for item in git_state.get("changed_files", []) if item.get("path")]

    receipt_id = f"build_change_{observed_at.replace('-', '').replace(':', '').replace('.', '_')}_{uuid.uuid4().hex[:12]}"
    receipt_path = RECEIPTS_DIR / f"{receipt_id}.json"

    receipt: dict[str, Any] = {
        "ok": True,
        "event_type": "build_change",
        "schema_version": SCHEMA_VERSION,
        "receipt_id": receipt_id,
        "project": PROJECT,
        "task_id": task_id or "build-witness",
        "requested_by": requested_by,
        "executed_by": executed_by,
        "observed_at": observed_at,
        "reason": str(reason or "Build witness receipt"),
        "files_changed": files_changed,
        "git": git_state,
        "source_events": creation_tail,
        "tests_run": _normal_tests(tests_run),
        "test_result": str(test_result or "unverified"),
        "commit": commit,
        "approval_status": str(approval_status or "candidate"),
        "notes": notes or "",
        "receipt_path": str(receipt_path),
        "receipt_log_path": str(RECEIPT_LOG),
        "timeline_path": str(RECEIPT_LOG),
        "boundaries": {
            "captures_file_content": False,
            "writes_outside_memory_build_witness": False,
            "uploads": False,
            "commits_or_pushes": False,
            "promotes_canon": False,
            "receipt_status": "candidate_until_noah_approval",
        },
    }
    receipt["receipt_hash_sha256"] = hash_payload(receipt)
    return receipt


def write_build_receipt(**kwargs: Any) -> dict[str, Any]:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    receipt = build_receipt(**kwargs)
    receipt_path = Path(receipt["receipt_path"])
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    LATEST_RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    with RECEIPT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True, ensure_ascii=True) + "\n")
    return receipt


def read_latest_receipt() -> dict[str, Any] | None:
    try:
        data = json.loads(LATEST_RECEIPT.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _timeline_event_from_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    files = receipt.get("files_changed") or []
    tests = receipt.get("tests_run") or []
    return {
        "kind": "build_receipt",
        "observed_at": receipt.get("observed_at"),
        "event_type": receipt.get("event_type"),
        "task_id": receipt.get("task_id"),
        "reason": receipt.get("reason"),
        "requested_by": receipt.get("requested_by"),
        "executed_by": receipt.get("executed_by"),
        "approval_status": receipt.get("approval_status"),
        "test_result": receipt.get("test_result"),
        "tests_run": tests,
        "files_changed_count": len(files),
        "files_changed": files[:20],
        "receipt_path": receipt.get("receipt_path"),
        "receipt_hash_sha256": receipt.get("receipt_hash_sha256"),
    }


def _timeline_event_from_creation(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "file_witness",
        "observed_at": event.get("ts"),
        "event_type": event.get("event"),
        "path": event.get("path"),
        "witness": event.get("witness"),
        "boundary": event.get("boundary"),
    }


def timeline_payload(limit: int = 50) -> dict[str, Any]:
    bounded = max(1, min(int(limit or 50), 200))
    receipts = _read_jsonl_tail(RECEIPT_LOG, bounded)
    creation = tail_creation_feed(min(MAX_CREATION_EVENTS, bounded))
    events = [_timeline_event_from_receipt(item) for item in receipts]
    events.extend(_timeline_event_from_creation(item) for item in creation)
    events.sort(key=lambda item: str(item.get("observed_at") or ""), reverse=True)
    latest = read_latest_receipt()
    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_utc(),
        "project": PROJECT,
        "receipt_dir": str(BUILD_DIR),
        "receipt_log_path": str(RECEIPT_LOG),
        "latest_receipt_path": str(LATEST_RECEIPT),
        "latest_receipt": latest,
        "receipt_count_returned": len(receipts),
        "creation_events_returned": len(creation),
        "events": events[:bounded],
        "boundary": "build receipts plus metadata-only creation witness; no file contents captured",
    }


def status_payload() -> dict[str, Any]:
    latest = read_latest_receipt()
    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "build_witness_active": True,
        "latest_receipt_path": str(LATEST_RECEIPT),
        "receipt_log_path": str(RECEIPT_LOG),
        "has_latest_receipt": latest is not None,
        "latest_receipt": latest,
        "boundary": "candidate construction receipts only; no canon promotion or external action",
    }


if __name__ == "__main__":  # pragma: no cover
    print(json.dumps(timeline_payload(), indent=2))
