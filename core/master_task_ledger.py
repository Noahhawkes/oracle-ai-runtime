"""Build one deduplicated, derived ledger from ORACLE's pending stores."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from root import ROOT

MEMORY = ROOT / "Memory"
OUTPUT_JSON = MEMORY / "master_task_ledger.json"
OUTPUT_MD = MEMORY / "master_task_ledger.md"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_title(value: Any) -> str:
    title = re.sub(r"\s+", " ", str(value or "")).strip()
    while title.lower().startswith("stale pending item:"):
        title = title.split(":", 1)[1].strip()
    return title


def _task_id(category: str, title: str) -> str:
    key = f"{category}|{normalize_title(title).lower()}".encode("utf-8")
    return "task_" + hashlib.sha256(key).hexdigest()[:16]


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _add(
    tasks: dict[str, dict[str, Any]],
    *,
    title: str,
    category: str,
    status: str,
    source_ref: str,
    approval_required: bool = False,
    detail: str = "",
    risk: str = "unknown",
) -> None:
    title = normalize_title(title)
    if not title:
        return
    task_id = _task_id(category, title)
    current = tasks.get(task_id)
    if current:
        if source_ref not in current["source_refs"]:
            current["source_refs"].append(source_ref)
        current["duplicate_records"] += 1
        return
    tasks[task_id] = {
        "task_id": task_id,
        "title": title,
        "category": category,
        "status": status,
        "approval_required": approval_required,
        "risk": risk,
        "detail": detail,
        "source_refs": [source_ref],
        "duplicate_records": 0,
    }


def build_ledger() -> dict[str, Any]:
    tasks: dict[str, dict[str, Any]] = {}

    pending_path = MEMORY / "source_maps" / "pending_actions.jsonl"
    if pending_path.exists():
        states: dict[str, dict[str, Any]] = {}
        for line in pending_path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except Exception:
                continue
            states[str(row.get("route_id") or "")] = row
        for row in states.values():
            if str(row.get("status") or "").lower() == "pending":
                _add(
                    tasks,
                    title=row.get("original_intent_summary") or "Pending routed action",
                    category="routed_action",
                    status="pending_approval",
                    source_ref=str(pending_path),
                    approval_required=True,
                    risk=str(row.get("risk_tier") or "unknown"),
                )

    candidates_path = MEMORY / "action_candidates.json"
    for row in _read_json(candidates_path, []):
        if str(row.get("status") or "").lower() in {"pending", "approved"}:
            _add(
                tasks,
                title=row.get("title") or "Action candidate",
                category="action_candidate",
                status=str(row.get("status") or "pending"),
                source_ref=str(candidates_path),
                approval_required=bool(row.get("required_approval", True)),
                risk=str(row.get("risk_level") or "unknown"),
                detail=str(row.get("description") or ""),
            )

    improvement_path = MEMORY / "improvement_loop" / "improvement_candidates.json"
    improvement_data = _read_json(improvement_path, [])
    improvement_rows = improvement_data if isinstance(improvement_data, list) else improvement_data.get("candidates", [])
    for row in improvement_rows:
        if str(row.get("status") or "").lower() == "pending":
            _add(
                tasks,
                title=row.get("title") or "Improvement candidate",
                category="code_quality",
                status="candidate",
                source_ref=str(improvement_path),
                detail=str(row.get("description") or ""),
                risk="low",
            )

    ingest_dir = MEMORY / "thread_ingest"
    ingest_sources = (
        ("thread_engineering_tasks.json", ("tasks", "milestones", "risks"), "thread_extracted"),
        ("thread_candidates.json", (None,), "memory_candidate"),
        ("thread_governance_candidates.json", (None,), "governance_candidate"),
        ("thread_book_candidates.json", (None,), "book_candidate"),
    )
    for filename, groups, category in ingest_sources:
        path = ingest_dir / filename
        data = _read_json(path, [])
        rows: list[dict[str, Any]] = []
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            for group in groups:
                if group:
                    rows.extend(data.get(group, []))
        for row in rows:
            if str(row.get("status") or "").lower() == "pending":
                _add(
                    tasks,
                    title=row.get("text") or row.get("title") or "Thread-extracted candidate",
                    category=category,
                    status="pending_classification",
                    source_ref=str(path),
                    approval_required=bool(row.get("approval_required", True)),
                )

    scope_path = MEMORY / "scoped_paths_proposed.json"
    scope = _read_json(scope_path, {})
    proposed = [row for row in scope.get("proposals", []) if row.get("status") == "proposed"]
    if proposed:
        names = ", ".join(str(row.get("name")) for row in proposed)
        _add(
            tasks,
            title=f"Review {len(proposed)} proposed read-scope paths",
            category="scope_approval",
            status="pending_approval",
            source_ref=str(scope_path),
            approval_required=True,
            detail=names,
            risk="high",
        )

    try:
        from continuity_spine import pending_approvals

        for row in pending_approvals(limit=500):
            if row.get("source") != "intake":
                continue
            _add(
                tasks,
                title=row.get("summary") or "Intake item",
                category="intake_classification",
                status="pending_classification",
                source_ref="continuity_spine.pending_approvals",
                approval_required=True,
            )
    except Exception:
        pass

    ordered = sorted(tasks.values(), key=lambda row: (row["category"], row["title"].lower()))
    counts = {
        "total_unique": len(ordered),
        "by_status": dict(Counter(row["status"] for row in ordered)),
        "by_category": dict(Counter(row["category"] for row in ordered)),
        "duplicate_records_collapsed": sum(row["duplicate_records"] for row in ordered),
    }
    return {
        "schema_version": 1,
        "generated_at": _utc_now(),
        "authority": "derived_task_index_not_canon",
        "counts": counts,
        "tasks": ordered,
    }


def write_ledger() -> dict[str, Any]:
    ledger = build_ledger()
    OUTPUT_JSON.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [
        "# ORACLE Master Task Ledger",
        "",
        f"Generated: {ledger['generated_at']}",
        "",
        "Authority: derived task index; source records remain authoritative.",
        "",
    ]
    for category in sorted({row["category"] for row in ledger["tasks"]}):
        lines.extend((f"## {category.replace('_', ' ').title()}", ""))
        for row in [item for item in ledger["tasks"] if item["category"] == category]:
            approval = "; approval required" if row["approval_required"] else ""
            lines.append(f"- [{row['status']}] {row['title']}{approval}")
        lines.append("")
    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")
    return ledger

