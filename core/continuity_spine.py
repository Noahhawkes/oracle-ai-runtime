"""Operational Continuity Spine for ORACLE.

The spine composes existing ledgers into one operational view. It does not
replace Human State, project state, approvals, or receipts; it reads them and
normalizes their current continuity surface.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from root import ROOT
except Exception:  # pragma: no cover
    ROOT = Path(__file__).resolve().parents[1]


OPEN_LOOP_STATUSES = ("completed", "active", "blocked", "waiting", "abandoned")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _utc_now().isoformat().replace("+00:00", "Z")


def _compact(value: Any) -> str:
    return " ".join(str(value or "").split())


def _hash_id(prefix: str, *parts: Any) -> str:
    seed = "|".join(_compact(part).lower() for part in parts)
    return f"{prefix}_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]}"


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _elapsed_seconds(value: Any) -> int | None:
    dt = _parse_dt(value)
    if not dt:
        return None
    return max(0, int((_utc_now() - dt).total_seconds()))


def _dedupe(items: list[Any]) -> list[str]:
    out: list[str] = []
    seen = set()
    for item in items:
        text = _compact(item)
        key = text.lower()
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return out


def human_state_snapshot() -> dict[str, Any]:
    try:
        import human_state

        return human_state.current_state()
    except Exception as exc:
        return {
            "ok": False,
            "current_mode": "UNKNOWN",
            "last_transition": None,
            "continuity_gap": f"human_state unavailable: {type(exc).__name__}: {exc}",
        }


def _all_project_states() -> list[Any]:
    try:
        import project_state

        states = []
        for name in project_state.list_projects():
            state = project_state.load_state(name)
            if state:
                states.append(state)
        return states
    except Exception:
        return []


def active_project_snapshot() -> dict[str, Any]:
    human = human_state_snapshot()
    last = human.get("last_transition") or {}
    preferred = _compact(last.get("related_project"))
    states = _all_project_states()

    selected = None
    if preferred:
        for state in states:
            if state.project_name.lower() == preferred.lower():
                selected = state
                break
    if selected is None and states:
        selected = max(states, key=lambda state: _parse_dt(state.updated_at) or datetime.min.replace(tzinfo=timezone.utc))
    if selected is None:
        return {
            "project_name": preferred or None,
            "status": "unknown",
            "current_goal": None,
            "current_context": None,
            "current_priority": None,
            "current_risks": [],
            "confidence": 0.0,
            "evidence_sources": ["human_state.related_project"] if preferred else [],
            "dormant_projects": [],
        }

    dormant = [state.project_name for state in states if state.project_name != selected.project_name]
    risks = _dedupe(
        ([selected.current_blocker] if selected.current_blocker else [])
        + list(selected.unknowns or [])
        + [str(item) for item in selected.failed_attempts[-3:]]
    )
    return {
        "project_name": selected.project_name,
        "status": "active",
        "current_goal": selected.current_goal or None,
        "current_context": selected.current_phase or None,
        "current_priority": selected.next_recommended_step or None,
        "current_risks": risks,
        "last_completed_step": selected.last_completed_step or None,
        "last_completed_evidence": selected.last_completed_evidence or None,
        "updated_at": selected.updated_at,
        "confidence": float(selected.confidence or 0.0),
        "evidence_sources": ["project_state", "human_state.related_project" if preferred else "latest_project_state"],
        "dormant_projects": dormant,
    }


def pending_approvals(limit: int = 10) -> list[dict[str, Any]]:
    try:
        from approval_center import list_pending

        pending = list_pending()
    except Exception:
        return []
    rows = []
    for idx, item in enumerate(pending[:limit], 1):
        if not isinstance(item, dict):
            continue
        rows.append({
            "id": str(item.get("id") or item.get("approval_id") or f"pending-{idx}"),
            "summary": _compact(item.get("summary") or item.get("title") or item.get("action") or item.get("source") or "pending approval"),
            "source": item.get("source") or item.get("kind") or "approval_center",
            "status": item.get("status") or "waiting",
        })
    return rows


def collect_open_loops(limit: int = 50) -> list[dict[str, Any]]:
    loops: list[dict[str, Any]] = []
    for state in _all_project_states():
        base = {
            "originating_session": None,
            "owner": "Noah.Physical",
            "latest_modification": state.updated_at,
            "confidence": float(state.confidence or 0.0),
            "project": state.project_name,
        }
        if state.last_completed_step:
            loops.append({
                **base,
                "loop_id": _hash_id("loop", state.project_name, "completed", state.last_completed_step),
                "status": "completed",
                "title": state.last_completed_step,
                "timestamp": state.updated_at,
                "originating_witness": "project_state.last_completed_step",
                "evidence_sources": [state.last_completed_evidence or "project_state"],
            })
        if state.next_recommended_step:
            loops.append({
                **base,
                "loop_id": _hash_id("loop", state.project_name, "active", state.next_recommended_step),
                "status": "active",
                "title": state.next_recommended_step,
                "timestamp": state.updated_at,
                "originating_witness": "project_state.next_recommended_step",
                "evidence_sources": [state.next_step_reason or "project_state"],
            })
        if state.current_blocker:
            loops.append({
                **base,
                "loop_id": _hash_id("loop", state.project_name, "blocked", state.current_blocker),
                "status": "blocked",
                "title": state.current_blocker,
                "timestamp": state.updated_at,
                "originating_witness": "project_state.current_blocker",
                "evidence_sources": [state.blocker_evidence or "project_state"],
            })
        for question in list(state.open_questions or []):
            loops.append({
                **base,
                "loop_id": _hash_id("loop", state.project_name, "waiting", question),
                "status": "waiting",
                "title": question,
                "timestamp": state.updated_at,
                "originating_witness": "project_state.open_questions",
                "evidence_sources": ["project_state"],
            })
        for candidate in list(state.pending_candidates or [])[:10]:
            title = _compact(candidate)
            loops.append({
                **base,
                "loop_id": _hash_id("loop", state.project_name, "waiting", title),
                "status": "waiting",
                "title": title,
                "timestamp": state.updated_at,
                "originating_witness": "project_state.pending_candidates",
                "evidence_sources": ["project_state"],
            })
        for failed in list(state.failed_attempts or [])[-10:]:
            title = _compact((failed or {}).get("step") or (failed or {}).get("failure") or failed)
            loops.append({
                **base,
                "loop_id": _hash_id("loop", state.project_name, "abandoned", title),
                "status": "abandoned",
                "title": title,
                "timestamp": (failed or {}).get("at") or state.updated_at,
                "latest_modification": (failed or {}).get("at") or state.updated_at,
                "originating_witness": "project_state.failed_attempts",
                "evidence_sources": [(failed or {}).get("evidence") or "project_state"],
            })

    for item in pending_approvals(limit=25):
        title = item.get("summary") or item.get("id")
        loops.append({
            "loop_id": _hash_id("loop", "approval", item.get("id"), title),
            "status": "waiting",
            "title": title,
            "timestamp": None,
            "originating_session": None,
            "originating_witness": "approval_center",
            "latest_modification": None,
            "confidence": 1.0,
            "owner": "Noah.Physical",
            "project": None,
            "evidence_sources": [item.get("id") or "approval_center"],
        })

    loops = [loop for loop in loops if loop.get("status") in OPEN_LOOP_STATUSES and loop.get("title")]
    return sorted(
        loops,
        key=lambda loop: _parse_dt(loop.get("latest_modification") or loop.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )[:limit]


def recent_receipts(limit: int = 20) -> list[dict[str, Any]]:
    roots = [
        ROOT / "sandbox" / "receipts",
        ROOT / "state" / "receipts",
        ROOT / "Memory" / "build_witness",
        ROOT / "Memory" / "terminal",
        ROOT / "Memory" / "storage_census" / "receipts",
    ]
    paths: list[Path] = []
    for root in roots:
        if root.exists():
            paths.extend([path for path in root.rglob("*.json") if path.is_file()])
            paths.extend([path for path in root.rglob("*.jsonl") if path.is_file()])
    rows = []
    for path in sorted(paths, key=lambda item: item.stat().st_mtime, reverse=True)[:limit]:
        preview: dict[str, Any] = {}
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
            first = raw.splitlines()[0] if path.suffix.lower() == ".jsonl" else raw
            data = json.loads(first)
            if isinstance(data, dict):
                preview = {
                    "receipt_id": data.get("receipt_id") or data.get("action_id") or data.get("event_id"),
                    "operation": data.get("operation") or data.get("operation_type") or data.get("receipt_kind"),
                    "status": data.get("status") or data.get("canon_status") or data.get("approval_status"),
                }
        except Exception:
            preview = {}
        rows.append({
            "path": str(path.resolve(strict=False)),
            "modified_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
            "source": _receipt_source(path),
            "preview": preview,
        })
    return rows


def _receipt_source(path: Path) -> str:
    text = str(path).replace("\\", "/").lower()
    if "/sandbox/" in text:
        return "sandbox_receipt"
    if "/state/receipts/" in text:
        return "route_receipt"
    if "/build_witness/" in text:
        return "build_witness"
    if "/storage_census/" in text:
        return "storage_census"
    return "receipt"


def continuity_timeline(limit: int = 50) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    human = human_state_snapshot()
    transition = human.get("last_transition")
    if transition:
        nodes.append({
            "node_id": transition.get("event_id") or _hash_id("node", "human", transition.get("timestamp")),
            "timestamp": transition.get("timestamp"),
            "type": "human_transition",
            "label": transition.get("new_mode"),
            "links": {
                "receipt_hash": transition.get("receipt_hash"),
                "source_system": transition.get("source_system"),
                "session_id": transition.get("originating_session"),
            },
            "confidence": transition.get("confidence"),
            "unknowns": [],
        })
    for loop in collect_open_loops(limit=limit):
        nodes.append({
            "node_id": loop["loop_id"],
            "timestamp": loop.get("timestamp") or loop.get("latest_modification"),
            "type": "open_loop",
            "label": f"{loop['status']}: {loop['title']}",
            "links": {
                "project": loop.get("project"),
                "originating_witness": loop.get("originating_witness"),
                "evidence_sources": loop.get("evidence_sources"),
            },
            "confidence": loop.get("confidence"),
            "unknowns": [] if loop.get("timestamp") else ["timestamp_unknown"],
        })
    for receipt in recent_receipts(limit=limit):
        nodes.append({
            "node_id": _hash_id("node", receipt.get("path"), receipt.get("modified_at")),
            "timestamp": receipt.get("modified_at"),
            "type": "receipt",
            "label": receipt.get("preview", {}).get("operation") or receipt.get("source"),
            "links": {"path": receipt.get("path"), "source": receipt.get("source")},
            "confidence": 1.0,
            "unknowns": [] if receipt.get("preview") else ["receipt_preview_unavailable"],
        })
    return sorted(
        nodes,
        key=lambda node: _parse_dt(node.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )[:limit]


def continuity_health_metrics() -> dict[str, Any]:
    human = human_state_snapshot()
    transition = human.get("last_transition") or {}
    loops = collect_open_loops(limit=200)
    receipts = recent_receipts(limit=200)
    since = _utc_now() - timedelta(hours=24)
    receipts_24h = [r for r in receipts if (_parse_dt(r.get("modified_at")) or datetime.min.replace(tzinfo=timezone.utc)) >= since]
    by_status = {status: 0 for status in OPEN_LOOP_STATUSES}
    for loop in loops:
        by_status[loop["status"]] = by_status.get(loop["status"], 0) + 1
    unknown_count = 0
    if human.get("current_mode") == "UNKNOWN":
        unknown_count += 1
    unknown_count += sum(len(getattr(state, "unknowns", []) or []) for state in _all_project_states())
    objects_total = 1 + len(loops) + len(_all_project_states())
    objects_with_receipts = (1 if transition.get("receipt_hash") else 0) + sum(
        1 for loop in loops if any(src and src != "project_state" for src in loop.get("evidence_sources") or [])
    )
    evidence_ratio = round(objects_with_receipts / objects_total, 3) if objects_total else 0.0
    return {
        "generated_at": _iso_now(),
        "human_state_freshness_seconds": _elapsed_seconds(transition.get("timestamp")),
        "project_count": len(_all_project_states()),
        "dormant_project_count": len(active_project_snapshot().get("dormant_projects") or []),
        "open_loop_pressure": {
            "total": len(loops),
            "by_status": by_status,
        },
        "receipt_density_24h": {
            "count": len(receipts_24h),
            "sources": sorted({receipt.get("source") for receipt in receipts_24h if receipt.get("source")}),
        },
        "evidence_quality": {
            "objects_total": objects_total,
            "objects_with_receipts_or_external_evidence": objects_with_receipts,
            "ratio": evidence_ratio,
        },
        "contradiction_count": 0,
        "contradiction_source": "no contradiction ledger connected to continuity_spine yet",
        "unknown_count": unknown_count,
        "state_freshness": {
            "last_transition_at": transition.get("timestamp"),
            "mode": human.get("current_mode"),
        },
        "metric_boundary": "measured system counts only; no AI scoring",
    }


def evidence_density() -> dict[str, Any]:
    human = human_state_snapshot()
    project = active_project_snapshot()
    loops = collect_open_loops(limit=20)
    return {
        "human_state": {
            "evidence_sources": ["human_state_transitions"],
            "receipt_hash": (human.get("last_transition") or {}).get("receipt_hash"),
            "confidence": (human.get("last_transition") or {}).get("confidence"),
            "unknowns": [human.get("continuity_gap")] if human.get("continuity_gap") else [],
        },
        "active_project": {
            "evidence_sources": project.get("evidence_sources") or [],
            "confidence": project.get("confidence"),
            "unknowns": project.get("current_risks") or [],
        },
        "open_loops": [
            {
                "loop_id": loop.get("loop_id"),
                "evidence_sources": loop.get("evidence_sources") or [],
                "confidence": loop.get("confidence"),
                "unknowns": [] if loop.get("timestamp") else ["timestamp_unknown"],
            }
            for loop in loops
        ],
    }


def continuity_snapshot(limit: int = 20) -> dict[str, Any]:
    human = human_state_snapshot()
    project = active_project_snapshot()
    loops = collect_open_loops(limit=limit)
    approvals = pending_approvals(limit=10)
    receipts = recent_receipts(limit=10)
    timeline = continuity_timeline(limit=limit)
    metrics = continuity_health_metrics()
    resume = _resume_action(project, loops, human)
    return {
        "ok": True,
        "generated_at": _iso_now(),
        "continuity_owner": "core.continuity_spine",
        "source_ledgers": ["human_state", "project_state", "approval_center", "receipts"],
        "current_human_state": human,
        "current_project": project,
        "current_open_loops": loops,
        "current_priority": resume,
        "current_risks": project.get("current_risks") or [],
        "pending_approvals": approvals,
        "recent_receipts": receipts,
        "timeline": timeline,
        "evidence_density": evidence_density(),
        "health_metrics": metrics,
        "resume_brief": operator_dashboard(top_n=5),
        "boundary": "read-only continuity composition; no external systems touched",
    }


def _resume_action(project: dict[str, Any], loops: list[dict[str, Any]], human: dict[str, Any]) -> str:
    for status in ("blocked", "waiting", "active"):
        match = next((loop for loop in loops if loop.get("status") == status), None)
        if match:
            if status == "blocked":
                return f"Resolve blocker: {match['title']}"
            if status == "waiting":
                return f"Answer or clear waiting item: {match['title']}"
            return match["title"]
    if project.get("current_priority"):
        return str(project["current_priority"])
    transition = human.get("last_transition") or {}
    if transition.get("reentry_hint"):
        return str(transition["reentry_hint"])
    return "Ask Noah.Physical which lane to resume."


def operator_dashboard(top_n: int = 5) -> dict[str, Any]:
    human = human_state_snapshot()
    project = active_project_snapshot()
    loops = collect_open_loops(limit=max(top_n, 5))
    receipts = recent_receipts(limit=5)
    approvals = pending_approvals(limit=5)
    return {
        "ok": True,
        "current_human_state": human.get("current_mode"),
        "current_project": project.get("project_name"),
        "top_open_loops": loops[:top_n],
        "recent_receipts": receipts,
        "pending_approvals": approvals,
        "suggested_resume_action": _resume_action(project, loops, human),
        "boundary": "operator dashboard is read-only and actionable; nothing decorative",
    }


def daily_continuity_digest() -> dict[str, Any]:
    loops = collect_open_loops(limit=100)
    timeline = continuity_timeline(limit=100)
    since = _utc_now() - timedelta(days=1)
    recent_nodes = [
        node for node in timeline
        if (_parse_dt(node.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc)) >= since
    ]
    completed = [loop for loop in loops if loop.get("status") == "completed"]
    stalled = [loop for loop in loops if loop.get("status") in {"blocked", "waiting"}]
    active = [loop for loop in loops if loop.get("status") == "active"]
    return {
        "ok": True,
        "digest_date": _utc_now().date().isoformat(),
        "what_changed": recent_nodes[:10],
        "what_completed": completed[:10],
        "what_stalled": stalled[:10],
        "what_became_important": active[:10],
        "what_still_needs_attention": stalled[:5] + active[:5],
        "boundary": "derived from ledgers only; no invented work",
    }
