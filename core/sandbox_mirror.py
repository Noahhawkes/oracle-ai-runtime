"""Read-only sandbox mirror for Recursion Arena.

This module never writes to ORACLE's sandbox. It samples recent sandbox files,
links them to available operation receipts, and returns enough metadata for a
frontend to compute new/modified/deleted deltas between polls.
"""
from __future__ import annotations

import hashlib
import heapq
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _iso_from_ts(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")


def _hash_file(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(root.resolve(strict=False)))
    except Exception:
        return str(path)


def _target_relative(receipt: dict[str, Any], root: Path) -> str | None:
    for key in ("target_path", "final_path", "path"):
        raw = receipt.get(key)
        if raw:
            try:
                return _relative(Path(str(raw)), root)
            except Exception:
                pass
    raw_requested = receipt.get("requested_path")
    if raw_requested:
        return str(raw_requested).replace("/", "\\")
    return None


def _recent_files(root: Path, *, limit: int) -> tuple[int, list[tuple[float, Path]]]:
    if not root.exists():
        return 0, []
    total = 0
    latest: list[tuple[float, Path]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        total += 1
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        item = (mtime, path)
        if len(latest) < limit:
            heapq.heappush(latest, item)
        elif mtime > latest[0][0]:
            heapq.heapreplace(latest, item)
    return total, sorted(latest, key=lambda item: item[0], reverse=True)


def _receipt_index(root: Path, *, limit: int) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    receipts_root = root / "receipts"
    if not receipts_root.exists():
        return {}, []
    receipt_items: list[tuple[float, Path]] = []
    for path in receipts_root.glob("*.json"):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        receipt_items.append((mtime, path))
    receipt_items.sort(key=lambda item: item[0], reverse=True)

    by_target: dict[str, dict[str, Any]] = {}
    recent: list[dict[str, Any]] = []
    for _, path in receipt_items[:limit]:
        data = _read_json(path) or {}
        rel = _relative(path, root)
        target = _target_relative(data, root)
        record = {
            "receipt_id": data.get("action_id") or data.get("receipt_id") or path.stem,
            "receipt_path": rel,
            "operation_type": data.get("operation_type") or data.get("operation"),
            "timestamp": data.get("timestamp"),
            "source_route": data.get("source_route") or data.get("actor") or data.get("caller"),
            "target_relative_path": target,
            "novelty_status": data.get("novelty_status"),
            "content_written": data.get("content_written"),
            "status_emit": data.get("status_emit"),
            "canon_status": data.get("canon_status"),
            "promotion_status": data.get("promotion_status"),
            "sha256": data.get("sha256") or data.get("post_operation_sha256"),
        }
        recent.append(record)
        if target and target not in by_target:
            by_target[target] = record
    return by_target, recent


def _receipt_from_file(path: Path, root: Path) -> dict[str, Any] | None:
    if "receipts" not in path.parts:
        return None
    data = _read_json(path)
    if not data:
        return None
    return {
        "receipt_id": data.get("action_id") or data.get("receipt_id") or path.stem,
        "receipt_path": _relative(path, root),
        "operation_type": data.get("operation_type") or data.get("operation"),
        "timestamp": data.get("timestamp"),
        "source_route": data.get("source_route") or data.get("actor") or data.get("caller"),
        "target_relative_path": _target_relative(data, root),
        "novelty_status": data.get("novelty_status"),
        "content_written": data.get("content_written"),
        "status_emit": data.get("status_emit"),
        "canon_status": data.get("canon_status"),
        "promotion_status": data.get("promotion_status"),
        "sha256": data.get("sha256") or data.get("post_operation_sha256"),
    }


def _author_class(receipt: dict[str, Any] | None) -> str:
    if not receipt:
        return "unknown_author"
    surface = " ".join(
        str(receipt.get(key) or "")
        for key in ("source_route", "operation_type", "receipt_id")
    ).lower()
    if "oracle" in surface or "self_prompt" in surface or "sandbox_self_prompt" in surface:
        return "oracle_write"
    if "codex" in surface:
        return "codex_code_change_outside_sandbox"
    return "unknown_author"


def _candidate_status(receipt: dict[str, Any] | None) -> str:
    if not receipt:
        return "unknown"
    if receipt.get("canon_status"):
        return str(receipt["canon_status"])
    if receipt.get("promotion_status"):
        return str(receipt["promotion_status"])
    if receipt.get("status_emit"):
        return "status_emit"
    return "candidate_or_receipted"


def _tail_text(path: Path, *, max_chars: int) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text[-max_chars:]


def build_sandbox_mirror(*, limit: int = 30, journal_chars: int = 3500) -> dict[str, Any]:
    """Return read-only sandbox mirror metadata.

    The caller/front-end is responsible for comparing consecutive payloads to
    determine new, modified, and deleted files for a particular arena round.
    """
    try:
        import sandbox_files

        root = Path(sandbox_files.SANDBOX_ROOT).resolve(strict=False)
        journal_path = root / "workbench" / "oracle_self_prompt_journal.ai"
    except Exception:
        root = Path(__file__).resolve().parents[1] / "sandbox"
        journal_path = root / "workbench" / "oracle_self_prompt_journal.ai"

    limit = max(1, min(int(limit), 100))
    journal_chars = max(0, min(int(journal_chars), 12000))

    total_files, newest = _recent_files(root, limit=limit)
    by_target, recent_receipts = _receipt_index(root, limit=max(limit * 4, 80))
    files: list[dict[str, Any]] = []
    for _, path in newest:
        rel = _relative(path, root)
        stat = path.stat()
        receipt = by_target.get(rel) or _receipt_from_file(path, root)
        sha256 = _hash_file(path)
        novelty = receipt.get("novelty_status") if receipt else None
        content_written = receipt.get("content_written") if receipt else None
        files.append({
            "relative_path": rel,
            "extension": path.suffix.lower(),
            "byte_size": stat.st_size,
            "created_at": _iso_from_ts(stat.st_ctime),
            "modified_at": _iso_from_ts(stat.st_mtime),
            "sha256": sha256,
            "author_class": _author_class(receipt),
            "receipt_id": receipt.get("receipt_id") if receipt else None,
            "receipt_path": receipt.get("receipt_path") if receipt else None,
            "operation_type": receipt.get("operation_type") if receipt else None,
            "source_route": receipt.get("source_route") if receipt else None,
            "novelty_status": novelty,
            "write_suppressed": bool(
                (isinstance(novelty, str) and "suppress" in novelty.lower())
                or content_written is False
            ),
            "candidate_status": _candidate_status(receipt),
        })

    journal_tail = _tail_text(journal_path, max_chars=journal_chars) if journal_chars else ""
    return {
        "ok": True,
        "generated_at": _now(),
        "read_only": True,
        "mutated_sandbox": False,
        "sandbox_root": str(root),
        "total_files": total_files,
        "sample_limit": limit,
        "files": files,
        "recent_receipts": recent_receipts[:limit],
        "journal": {
            "relative_path": _relative(journal_path, root),
            "exists": journal_path.exists(),
            "byte_size": journal_path.stat().st_size if journal_path.exists() else 0,
            "tail": journal_tail,
        },
        "delta_policy": "client_computes_new_modified_deleted_between_polls",
        "authorship_policy": "oracle_write_requires_matching_receipt_or_oracle_source_route; otherwise unknown_author",
    }
