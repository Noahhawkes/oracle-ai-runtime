"""Read-only evidence manifest for ORACLE answers and runtime surfaces.

The cockpit does not add memory, authority, or action capability. It makes the
existing evidence stack legible: which surfaces are available, which records are
enumerable, which limits remain open, and what can honestly be said about an
answer's context.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from root import ROOT
except Exception:  # pragma: no cover
    ROOT = Path(__file__).resolve().parents[1]


MEMORY = ROOT / "Memory"

BOUNDARIES = {
    "read_only": True,
    "sandbox_touched": False,
    "source_file_mutation": False,
    "drive_mutation": False,
    "external_send": False,
    "canon_promotion": False,
    "raw_content_stored": False,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _iso_mtime(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")
    except OSError:
        return None


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _jsonl_stats(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "count": 0, "latest": None}
    count = 0
    latest: dict[str, Any] | None = None
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.strip():
                    continue
                count += 1
                try:
                    item = json.loads(line)
                    if isinstance(item, dict):
                        latest = item
                except Exception:
                    continue
    except OSError:
        return {"exists": True, "count": count, "latest": None, "error": "read_failed"}
    return {"exists": True, "count": count, "latest": latest}


def _path_payload(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "modified_at": _iso_mtime(path),
    }


def _surface(
    surface_id: str,
    label: str,
    *,
    status: str,
    records: int = 0,
    source_path: Path | None = None,
    used_in_last_answer: bool = False,
    details: dict[str, Any] | None = None,
    boundary: str = "read-only metadata",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": surface_id,
        "label": label,
        "status": status,
        "records": int(records or 0),
        "used_in_last_answer": bool(used_in_last_answer),
        "boundary": boundary,
    }
    if source_path is not None:
        payload["source"] = _path_payload(source_path)
    if details:
        payload["details"] = details
    return payload


def _document_atlas_surface() -> dict[str, Any]:
    receipt = MEMORY / "document_atlas" / "unified_document_atlas_receipt_latest.json"
    data = _read_json(receipt)
    if not data:
        return _surface(
            "document_atlas",
            "Document Atlas",
            status="missing",
            source_path=receipt,
            boundary="not queried; no atlas receipt found",
        )
    stats = data.get("stats") or {}
    unresolved = data.get("unresolved_connector_intervals") or []
    return _surface(
        "document_atlas",
        "Document Atlas",
        status="available_with_holes" if unresolved else "available",
        records=stats.get("unified_record_count") or 0,
        source_path=receipt,
        details={
            "local_records": stats.get("local_record_count", 0),
            "connector_records": stats.get("connector_unique_record_count", 0),
            "top_categories": stats.get("by_category", {}),
            "unresolved_connector_intervals": len(unresolved),
            "index_sha256": data.get("index_sha256"),
            "receipt_sha256": data.get("receipt_sha256"),
            "canon_status": "candidate_unreviewed",
            "promotion_status": "not_promoted",
        },
        boundary="candidate index only; source files are not opened by the cockpit",
    )


def _ai_lockbox_surface() -> dict[str, Any]:
    status_path = MEMORY / "ai_lockbox" / "latest_status.json"
    data = _read_json(status_path)
    if not data:
        return _surface("ai_lockbox", ".AI Lockbox", status="missing", source_path=status_path)
    return _surface(
        "ai_lockbox",
        ".AI Lockbox",
        status="available",
        records=data.get("capsule_count") or 0,
        source_path=status_path,
        details={
            "receipt_count": data.get("receipt_count", 0),
            "manifest_path": data.get("manifest_path"),
            "latest_receipt_hash": (data.get("latest_receipt") or {}).get("receipt_hash_sha256"),
        },
        boundary="local shorthand recall only; no external send or source mutation",
    )


def _file_recall_surface() -> dict[str, Any]:
    path = MEMORY / "file_recall_receipts.jsonl"
    stats = _jsonl_stats(path)
    return _surface(
        "file_recall",
        "File Recall",
        status="available" if stats["exists"] else "missing",
        records=stats["count"],
        source_path=path,
        details={"latest_operation": (stats.get("latest") or {}).get("operation_type")},
        boundary="read-only receipts; credential-risk content blocked",
    )


def _internet_recall_surface() -> dict[str, Any]:
    path = MEMORY / "internet_recall_receipts.jsonl"
    stats = _jsonl_stats(path)
    return _surface(
        "internet_recall",
        "Internet Recall",
        status="available" if stats["exists"] else "missing",
        records=stats["count"],
        source_path=path,
        details={"latest_operation": (stats.get("latest") or {}).get("operation_type")},
        boundary="read/fetch receipts only; no posting or external mutation",
    )


def _qr_scan_surface() -> dict[str, Any]:
    path = MEMORY / "qr_scan_receipt_latest.json"
    data = _read_json(path)
    return _surface(
        "qr_scan",
        "QR Scan",
        status="available" if data else "missing",
        records=1 if data else 0,
        source_path=path,
        details={
            "decoded": bool((data or {}).get("decoded")),
            "decoded_text_present": bool((data or {}).get("decoded_text")),
            "last_image_sha256": (data or {}).get("sha256"),
            "holes": (data or {}).get("holes", []),
        },
        boundary="local image read only; no camera, upload, or identity proof claim",
    )


def _build_witness_surface() -> dict[str, Any]:
    root = MEMORY / "build_witness"
    receipts = sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True) if root.exists() else []
    return _surface(
        "build_witness",
        "Build Witness",
        status="available" if receipts else "missing",
        records=len(receipts),
        source_path=root,
        details={"latest_receipt": str(receipts[0]) if receipts else None},
        boundary="build metadata only; no commit, push, or file content capture",
    )


def _intent_router_surface() -> dict[str, Any]:
    try:
        from oracle_intent import capability_registry

        reg = capability_registry()
        missing = [key for key, value in reg.items() if value.get("status") in {"missing", "blocked"}]
        available = [key for key, value in reg.items() if value.get("status") == "available"]
    except Exception as exc:
        return _surface(
            "intent_router",
            "Intent Router",
            status="error",
            source_path=ROOT / "core" / "oracle_intent.py",
            details={"error": f"{type(exc).__name__}: {exc}"},
            boundary="router import failed; no capability claim made",
        )
    return _surface(
        "intent_router",
        "Intent Router",
        status="available",
        records=len(reg),
        source_path=ROOT / "core" / "oracle_intent.py",
        details={"available": len(available), "missing_or_blocked": missing},
        boundary="classification only; routing is not execution",
    )


def evidence_surfaces() -> list[dict[str, Any]]:
    return [
        _intent_router_surface(),
        _document_atlas_surface(),
        _ai_lockbox_surface(),
        _file_recall_surface(),
        _internet_recall_surface(),
        _qr_scan_surface(),
        _build_witness_surface(),
    ]


def _response_mode(user_text: str, *, mode: str | None, effective_route: str | None, route_type: str | None) -> str:
    joined = " ".join(str(part or "").lower() for part in (mode, effective_route, route_type, user_text))
    if "build" in joined or "patch" in joined or "commit" in joined or "push" in joined:
        return "build"
    if any(token in joined for token in ("scan", "recall", "remember", "what is", "who is", "did ", "does ", "status")):
        return "witness"
    if any(token in joined for token in ("write", "draft", "create", "imagine", "continue", "story")):
        return "author"
    return "talk"


def response_evidence(
    user_text: str,
    *,
    mode: str | None = None,
    effective_route: str | None = None,
    route_type: str | None = None,
    reason: str | None = None,
    fallback_used: bool = False,
) -> dict[str, Any]:
    """Build a compact, honest evidence packet for one chat turn."""

    intents: list[str] = []
    capability: str | None = None
    try:
        from oracle_intent import action_capability, classify_intent

        intents = sorted(classify_intent(user_text))
        capability = action_capability(user_text)
    except Exception:
        intents = []
        capability = None

    answer_mode = _response_mode(user_text, mode=mode, effective_route=effective_route, route_type=route_type)
    queried = ["current_session_user_message", "intent_router"]
    if answer_mode == "witness":
        queried.extend(["runtime_receipts", "candidate_indexes"])
    if capability:
        queried.append(f"capability:{capability}")

    unknowns = [
        "full model context usage is not yet instrumented",
        "records_used remains zero unless a deterministic surface reports enumerable records",
    ]
    if fallback_used:
        unknowns.append("fallback path was used; evidence may be route-level only")

    return {
        "ok": True,
        "generated_at": _utc_now(),
        "mode": answer_mode,
        "route": {
            "ui_mode": mode,
            "effective_route": effective_route,
            "route_type": route_type,
            "reason": reason,
            "fallback_used": bool(fallback_used),
        },
        "intents": intents,
        "capability": capability,
        "sources_queried": queried,
        "sources_proven_used": ["current_session_user_message", "intent_router"],
        "records_used_count": 0,
        "records_used": [],
        "contradictions": [],
        "unknowns": unknowns,
        "confidence": "route_level",
        "boundaries": BOUNDARIES.copy(),
    }


def cockpit_snapshot() -> dict[str, Any]:
    surfaces = evidence_surfaces()
    available = [item for item in surfaces if str(item.get("status", "")).startswith("available")]
    holes = []
    for item in surfaces:
        if item["status"] not in {"available"}:
            holes.append({"surface": item["id"], "status": item["status"]})
        if item["id"] == "document_atlas":
            intervals = (item.get("details") or {}).get("unresolved_connector_intervals") or 0
            if intervals:
                holes.append({"surface": item["id"], "status": f"{intervals} connector saturation windows"})
    return {
        "ok": True,
        "generated_at": _utc_now(),
        "name": "ORACLE Evidence Cockpit",
        "definition": "A read-only manifest that shows what ORACLE can prove it checked, used, skipped, and cannot yet know.",
        "surface_count": len(surfaces),
        "available_surface_count": len(available),
        "surfaces": surfaces,
        "holes": holes,
        "current_answer_contract": {
            "no_count_without_records": True,
            "no_file_claim_without_path": True,
            "no_memory_claim_without_record": True,
            "unknown_when_evidence_missing": True,
            "witness_author_separation": True,
        },
        "quick_readout_fields": [
            "mode",
            "sources_queried",
            "sources_proven_used",
            "records_used_count",
            "unknowns",
            "confidence",
        ],
        "next_best_action": "Instrument deterministic retrieval calls so records_used can move from route-level evidence to exact source rows.",
        "boundaries": BOUNDARIES.copy(),
    }


if __name__ == "__main__":  # pragma: no cover
    print(json.dumps(cockpit_snapshot(), indent=2, sort_keys=True))
