"""Active Context Sync for unified ORACLE mode.

Refreshes ORACLE's current working context from ratified local state without
resetting conversation history, syncing roots, uploading, or treating linked
Drive mirrors as canonical.
"""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from root_map import RATIFIED_RUNTIME_ROOT, RATIFIED_STATE_ROOT
except Exception:  # pragma: no cover - direct execution fallback
    RATIFIED_RUNTIME_ROOT = Path(r"C:\Oracle\ORACLE.AI-runtime")
    RATIFIED_STATE_ROOT = Path(r"C:\Oracle\state")


RUNTIME_ROOT = Path(RATIFIED_RUNTIME_ROOT)
STATE_ROOT = Path(RATIFIED_STATE_ROOT)
CONTEXT_DIR = STATE_ROOT / "context"
RECEIPTS_DIR = STATE_ROOT / "receipts"
SOURCES_LATEST = STATE_ROOT / "sources" / "oracle_source_manifest_latest.json"
GAME_CAPTURES_DIR = STATE_ROOT / "game" / "captures"
MINDCOIN_LEDGER = STATE_ROOT / "ledger" / "mindcoin_ledger.jsonl"
COMPANION_DIR = STATE_ROOT / "companion"
GOVERNANCE_DIR = STATE_ROOT / "governance"
ROUTING_DIR = STATE_ROOT / "routing"
LOOTDROP_DIR = STATE_ROOT / "artifacts" / "lootdrops"
LATEST_CONTEXT = CONTEXT_DIR / "active_context_latest.json"

CONTEXT_PRIORITY_RULES = [
    "Noah.Physical explicit current-session instruction",
    r"Ratified local state under C:\Oracle\state",
    "Active SourceMap manifest",
    "Receipts",
    "Current runtime Git state",
    "Linked Drive mirror metadata",
    "Older exports and thread merges",
    "Unresolved clones or stale folders",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _read_json(path: Path) -> dict[str, Any] | list[Any] | None:
    try:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")


def _file_meta(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
        return {
            "path": str(path),
            "exists": True,
            "size_bytes": stat.st_size,
            "modified_timestamp": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
        }
    except Exception:
        return {
            "path": str(path),
            "exists": False,
            "size_bytes": 0,
            "modified_timestamp": None,
        }


def _latest_files(directory: Path, pattern: str = "*", *, limit: int = 10) -> list[Path]:
    if not directory.exists():
        return []
    try:
        files = [p for p in directory.glob(pattern) if p.is_file()]
        return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    except Exception:
        return []


def _load_source_manifest() -> tuple[dict[str, Any] | None, list[str], list[str]]:
    warnings: list[str] = []
    unknowns: list[str] = []
    raw = _read_json(SOURCES_LATEST)
    if raw is None:
        unknowns.append(f"source manifest missing: {SOURCES_LATEST}")
        return None, warnings, unknowns
    if not isinstance(raw, dict):
        warnings.append("source manifest is not a JSON object")
        return None, warnings, unknowns

    sources = raw.get("sources") if isinstance(raw.get("sources"), list) else []
    for source in sources:
        if not isinstance(source, dict):
            continue
        full_path = str(source.get("full_path") or "")
        canonical_status = str(source.get("canonical_status") or "")
        if ("G:\\My Drive" in full_path or "G:/My Drive" in full_path) and canonical_status in {"ratified_runtime", "ratified_state"}:
            warnings.append(f"Drive-linked source is incorrectly marked canonical: {full_path}")
    return raw, warnings, unknowns


def _summarize_sources(manifest: dict[str, Any] | None) -> dict[str, Any]:
    if not manifest:
        return {
            "source_manifest_id": None,
            "source_manifest_path": str(SOURCES_LATEST),
            "source_count": 0,
            "sources": [],
            "drive_linked_sources": [],
        }
    sources = [item for item in manifest.get("sources", []) if isinstance(item, dict)]
    compact_sources: list[dict[str, Any]] = []
    drive_sources: list[dict[str, Any]] = []
    for item in sources[:200]:
        compact = {
            "source_id": item.get("source_id"),
            "full_path": item.get("full_path"),
            "source_type": item.get("source_type"),
            "canonical_status": item.get("canonical_status"),
            "evidence_state": item.get("evidence_state"),
            "newest_modified_timestamp": item.get("newest_modified_timestamp"),
            "retrieval_allowed": item.get("retrieval_allowed"),
        }
        compact_sources.append(compact)
        full_path = str(item.get("full_path") or "")
        if "G:\\My Drive" in full_path or "G:/My Drive" in full_path:
            drive_sources.append({
                **compact,
                "canonical_status": item.get("canonical_status") or "linked_source",
                "write_allowed": bool(item.get("write_allowed")),
                "canonical_allowed": False,
            })
    return {
        "source_manifest_id": manifest.get("manifest_id") or manifest.get("manifest_name") or str(SOURCES_LATEST),
        "source_manifest_path": str(SOURCES_LATEST),
        "source_count": int(manifest.get("source_count") or len(sources)),
        "sources": compact_sources,
        "drive_linked_sources": drive_sources[:25],
    }


def _load_latest_receipts(limit: int = 25) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in _latest_files(RECEIPTS_DIR, "*.json", limit=limit):
        data = _read_json(path)
        row = _file_meta(path)
        if isinstance(data, dict):
            row.update(
                {
                    "receipt_id": data.get("receipt_id"),
                    "operation": data.get("operation"),
                    "timestamp": data.get("timestamp"),
                    "detected_lane": data.get("detected_lane"),
                    "transcript_available": data.get("transcript_available"),
                    "blocker": data.get("blocker"),
                }
            )
        out.append(row)
    return out


def _load_game_captures(limit: int = 20) -> list[dict[str, Any]]:
    return [_file_meta(path) for path in _latest_files(GAME_CAPTURES_DIR, "*", limit=limit)]


def _load_lootdrops(limit: int = 20) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in _latest_files(LOOTDROP_DIR, "lootdrop_*.json", limit=limit):
        data = _read_json(path)
        row = _file_meta(path)
        if isinstance(data, dict):
            row.update(
                {
                    "lootdrop_id": data.get("lootdrop_id"),
                    "title": data.get("title"),
                    "artifact_type": data.get("artifact_type"),
                    "evidence_state": data.get("evidence_state"),
                    "timestamp": data.get("timestamp"),
                }
            )
        out.append(row)
    return out


def _load_mindcoin_events(limit: int = 20) -> list[dict[str, Any]]:
    if not MINDCOIN_LEDGER.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = MINDCOIN_LEDGER.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    for line in lines[-limit:]:
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(
                {
                    "event_id": item.get("event_id"),
                    "timestamp": item.get("timestamp"),
                    "award_name": item.get("award_name"),
                    "points": item.get("points"),
                    "reason": item.get("reason"),
                    "receipt_path": item.get("receipt_path"),
                    "nonfinancial": item.get("nonfinancial"),
                    "nontransferable": item.get("nontransferable"),
                }
            )
    return rows


def _load_latest_json_from_dir(directory: Path, pattern: str = "*.json") -> dict[str, Any] | None:
    files = _latest_files(directory, pattern, limit=1)
    if not files:
        return None
    data = _read_json(files[0])
    if isinstance(data, dict):
        data = dict(data)
        data["_path"] = str(files[0])
        return data
    return {"_path": str(files[0]), "_unreadable": True}


def _load_pending_tasks(limit: int = 20) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for path in _latest_files(COMPANION_DIR, "pending_task_*.json", limit=limit):
        data = _read_json(path)
        row = _file_meta(path)
        if isinstance(data, dict):
            row.update(
                {
                    "task_id": data.get("task_id"),
                    "title": data.get("title"),
                    "status": data.get("status"),
                    "timestamp": data.get("timestamp"),
                }
            )
        tasks.append(row)
    return tasks


def _git_state() -> dict[str, Any]:
    def run(args: list[str]) -> str:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=str(RUNTIME_ROOT),
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            return (result.stdout or "").strip()
        except Exception as exc:
            return f"unavailable: {type(exc).__name__}: {exc}"

    status_short = run(["status", "--short"])
    return {
        "branch": run(["branch", "--show-current"]),
        "head_sha": run(["rev-parse", "HEAD"]),
        "status_short": status_short,
        "dirty": bool(status_short.strip()),
    }


def load_active_context_latest() -> dict[str, Any] | None:
    data = _read_json(LATEST_CONTEXT)
    return data if isinstance(data, dict) else None


def build_snapshot() -> dict[str, Any]:
    warnings: list[str] = []
    unknowns: list[str] = []
    manifest, manifest_warnings, manifest_unknowns = _load_source_manifest()
    warnings.extend(manifest_warnings)
    unknowns.extend(manifest_unknowns)
    source_summary = _summarize_sources(manifest)

    if not RECEIPTS_DIR.exists():
        unknowns.append(f"receipts directory missing: {RECEIPTS_DIR}")
    if not GAME_CAPTURES_DIR.exists():
        unknowns.append(f"game captures directory missing: {GAME_CAPTURES_DIR}")
    if not COMPANION_DIR.exists():
        unknowns.append(f"companion directory missing: {COMPANION_DIR}")
    if not GOVERNANCE_DIR.exists():
        unknowns.append(f"governance directory missing: {GOVERNANCE_DIR}")
    if not ROUTING_DIR.exists():
        unknowns.append(f"routing directory missing: {ROUTING_DIR}")

    return {
        "snapshot_id": _id("active_context"),
        "timestamp": _now(),
        "runtime_root": str(RUNTIME_ROOT),
        "state_root": str(STATE_ROOT),
        "source_manifest_id": source_summary["source_manifest_id"],
        "source_manifest_path": source_summary["source_manifest_path"],
        "source_count": source_summary["source_count"],
        "sources": source_summary["sources"],
        "drive_linked_sources": source_summary["drive_linked_sources"],
        "latest_receipts": _load_latest_receipts(),
        "latest_game_captures": _load_game_captures(),
        "latest_lootdrops": _load_lootdrops(),
        "latest_mindcoin_events": _load_mindcoin_events(),
        "governance_state": _load_latest_json_from_dir(GOVERNANCE_DIR) or {},
        "routing_state": _load_latest_json_from_dir(ROUTING_DIR, "unified_oracle_route_*.json") or {},
        "pending_tasks": _load_pending_tasks(),
        "current_runtime_git_state": _git_state(),
        "active_warnings": warnings,
        "unknowns": unknowns,
        "human_authority": "Noah.Physical",
        "context_priority_rules": CONTEXT_PRIORITY_RULES,
        "conversation_reset": False,
        "discovered_paths_are_understood_content": False,
        "drive_canonical_status": "linked_source_or_mirror_only",
        "cloud_sync_performed": False,
        "cloud_api_calls": 0,
    }


def _keyed(items: list[dict[str, Any]], keys: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        key = ""
        for field in keys:
            if item.get(field):
                key = str(item.get(field))
                break
        if key:
            out[key] = item
    return out


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, default=str)


def build_diff(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    previous = previous or {}
    prev_sources = _keyed(previous.get("sources") or [], ("source_id", "full_path", "path"))
    cur_sources = _keyed(current.get("sources") or [], ("source_id", "full_path", "path"))
    new_sources = [item for key, item in cur_sources.items() if key not in prev_sources]
    updated_sources = [
        item
        for key, item in cur_sources.items()
        if key in prev_sources and _stable_json(item) != _stable_json(prev_sources[key])
    ]

    prev_receipts = _keyed(previous.get("latest_receipts") or [], ("receipt_id", "path"))
    cur_receipts = _keyed(current.get("latest_receipts") or [], ("receipt_id", "path"))
    new_receipts = [item for key, item in cur_receipts.items() if key not in prev_receipts]

    prev_captures = _keyed(previous.get("latest_game_captures") or [], ("path",))
    cur_captures = _keyed(current.get("latest_game_captures") or [], ("path",))
    new_game_captures = [item for key, item in cur_captures.items() if key not in prev_captures]

    prev_lootdrops = _keyed(previous.get("latest_lootdrops") or [], ("lootdrop_id", "path"))
    cur_lootdrops = _keyed(current.get("latest_lootdrops") or [], ("lootdrop_id", "path"))
    new_lootdrops = [item for key, item in cur_lootdrops.items() if key not in prev_lootdrops]

    prev_tasks = _keyed(previous.get("pending_tasks") or [], ("task_id", "path"))
    cur_tasks = _keyed(current.get("pending_tasks") or [], ("task_id", "path"))
    new_pending_tasks = [item for key, item in cur_tasks.items() if key not in prev_tasks]

    governance_changed = bool(
        previous
        and _stable_json(previous.get("governance_state") or {}) != _stable_json(current.get("governance_state") or {})
    )
    governance_changes = [current.get("governance_state") or {}] if governance_changed else []

    warnings = list(current.get("active_warnings") or [])
    unknowns = list(current.get("unknowns") or [])
    new_count = (
        len(new_sources)
        + len(new_receipts)
        + len(new_game_captures)
        + len(new_lootdrops)
        + len(new_pending_tasks)
        + len(governance_changes)
    )
    return {
        "generated_at": _now(),
        "previous_snapshot_id": previous.get("snapshot_id"),
        "current_snapshot_id": current.get("snapshot_id"),
        "new_sources": new_sources,
        "updated_sources": updated_sources,
        "new_receipts": new_receipts,
        "new_game_captures": new_game_captures,
        "new_lootdrops": new_lootdrops,
        "new_governance_changes": governance_changes,
        "new_pending_tasks": new_pending_tasks,
        "warnings": warnings,
        "unknowns": unknowns,
        "new_items_detected": new_count,
        "updated_items_detected": len(updated_sources),
        "conversation_reset": False,
    }


def write_sync_receipt(snapshot: dict[str, Any], diff: dict[str, Any], *, notes: str = "") -> dict[str, Any]:
    receipt = {
        "receipt_id": _id("active_context_sync_receipt"),
        "timestamp": _now(),
        "operation": "active_context_sync",
        "sources_checked": [
            str(SOURCES_LATEST),
            str(RECEIPTS_DIR),
            str(GAME_CAPTURES_DIR),
            str(MINDCOIN_LEDGER),
            str(COMPANION_DIR),
            str(GOVERNANCE_DIR),
            str(ROUTING_DIR),
            str(LOOTDROP_DIR),
        ],
        "sources_loaded": sources_loaded(snapshot),
        "new_items_detected": diff.get("new_items_detected", 0),
        "updated_items_detected": diff.get("updated_items_detected", 0),
        "warnings": diff.get("warnings") or [],
        "unknowns": diff.get("unknowns") or [],
        "conversation_reset": False,
        "files_moved": 0,
        "files_deleted": 0,
        "files_renamed": 0,
        "files_synced": 0,
        "cloud_uploads": 0,
        "cloud_api_calls": 0,
        "git_commits": 0,
        "git_pushes": 0,
        "recordings_created": 0,
        "human_authority": "Noah.Physical",
        "notes": notes,
    }
    path = RECEIPTS_DIR / f"active_context_sync_receipt_{_stamp()}.json"
    _write_json(path, receipt)
    receipt["receipt_path"] = str(path)
    return receipt


def sources_loaded(snapshot: dict[str, Any]) -> list[str]:
    loaded: list[str] = []
    if snapshot.get("source_manifest_id"):
        loaded.append(str(SOURCES_LATEST))
    if snapshot.get("latest_receipts"):
        loaded.append(str(RECEIPTS_DIR))
    if snapshot.get("latest_game_captures"):
        loaded.append(str(GAME_CAPTURES_DIR))
    if snapshot.get("latest_lootdrops"):
        loaded.append(str(LOOTDROP_DIR))
    if snapshot.get("latest_mindcoin_events"):
        loaded.append(str(MINDCOIN_LEDGER))
    if snapshot.get("governance_state"):
        loaded.append(str(GOVERNANCE_DIR))
    if snapshot.get("routing_state"):
        loaded.append(str(ROUTING_DIR))
    if snapshot.get("pending_tasks"):
        loaded.append(str(COMPANION_DIR))
    return loaded


def refresh_active_context(*, notes: str = "") -> dict[str, Any]:
    previous = load_active_context_latest()
    snapshot = build_snapshot()
    diff = build_diff(previous, snapshot)
    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_path = CONTEXT_DIR / f"active_context_snapshot_{_stamp()}.json"
    snapshot["diff"] = diff
    _write_json(snapshot_path, snapshot)
    _write_json(LATEST_CONTEXT, snapshot)
    receipt = write_sync_receipt(snapshot, diff, notes=notes)
    return {
        "snapshot": snapshot,
        "diff": diff,
        "receipt": receipt,
        "snapshot_path": str(snapshot_path),
        "latest_context_path": str(LATEST_CONTEXT),
        "conversation_reset": False,
        "sources_loaded": sources_loaded(snapshot),
    }


def status_payload() -> dict[str, Any]:
    latest = load_active_context_latest()
    return {
        "name": "Active Context Sync",
        "latest_context_path": str(LATEST_CONTEXT),
        "latest": latest,
        "loaded": latest is not None,
        "last_refresh_time": (latest or {}).get("timestamp"),
        "sources_loaded": sources_loaded(latest or {}),
        "new_changes_since_last_refresh": ((latest or {}).get("diff") or {}).get("new_items_detected", 0),
        "warnings": (latest or {}).get("active_warnings") or [],
        "reset_status": "Not reset",
        "conversation_reset": False,
    }


def format_refresh_response(result: dict[str, Any]) -> str:
    diff = result.get("diff") or {}
    warnings = diff.get("warnings") or []
    return (
        "I refreshed active local context from C:\\Oracle\\state without resetting the conversation. "
        f"I found {int(diff.get('new_items_detected') or 0)} new items, "
        f"{int(diff.get('updated_items_detected') or 0)} updates, and {len(warnings)} warnings. "
        "Nothing was moved, deleted, synced, uploaded, committed, or pushed."
    )


def format_diff_response(latest: dict[str, Any] | None = None) -> str:
    latest = latest or load_active_context_latest()
    if not latest:
        return "No active context snapshot exists yet. Use Refresh Context first."
    diff = latest.get("diff") or {}
    return (
        "Active Context Diff\n"
        f"New sources: {len(diff.get('new_sources') or [])}\n"
        f"Updated sources: {len(diff.get('updated_sources') or [])}\n"
        f"New receipts: {len(diff.get('new_receipts') or [])}\n"
        f"New game captures: {len(diff.get('new_game_captures') or [])}\n"
        f"New LootDrops: {len(diff.get('new_lootdrops') or [])}\n"
        f"New governance changes: {len(diff.get('new_governance_changes') or [])}\n"
        f"New pending tasks: {len(diff.get('new_pending_tasks') or [])}\n"
        f"Warnings: {len(diff.get('warnings') or [])}\n"
        "Conversation reset: false"
    )


if __name__ == "__main__":
    result = refresh_active_context(notes="manual CLI refresh")
    print(json.dumps({k: result[k] for k in ("snapshot_path", "latest_context_path", "sources_loaded")}, indent=2))
