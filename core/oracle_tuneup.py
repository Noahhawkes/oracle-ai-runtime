"""Read-only ORACLE tune-up status surfaces.

This module makes current runtime evidence legible for the UI. It reads
metadata, journal text, and receipts; it does not write sandbox files, mutate
source documents, send externally, promote canon, or call connector actions.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from root import ROOT
except Exception:  # pragma: no cover
    ROOT = Path(__file__).resolve().parents[1]


SANDBOX_ROOT = ROOT / "sandbox"
MEMORY_ROOT = ROOT / "Memory"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _iso_mtime(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")
    except OSError:
        return None


def _compact(text: Any, limit: int = 1200) -> str:
    value = str(text or "").replace("\r\n", "\n").strip()
    if len(value) > limit:
        return value[: max(0, limit - 31)].rstrip() + "\n[truncated_for_ui_preview]"
    return value


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _jsonl_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return sum(1 for line in handle if line.strip())
    except OSError:
        return 0


def _parse_cycle(block: str) -> dict[str, Any]:
    fields: dict[str, str] = {}
    sections: dict[str, list[str]] = {}
    current_section: str | None = None
    for raw in block.splitlines():
        line = raw.rstrip()
        if line == ".AI:ORACLE_SELF_PROMPT_CYCLE":
            continue
        if not line:
            if current_section:
                sections.setdefault(current_section, []).append("")
            continue
        if line.endswith(":") and "=" not in line and not line.startswith("."):
            current_section = line[:-1].strip().lower().replace(" ", "_")
            sections.setdefault(current_section, [])
            continue
        if current_section is None and "=" in line:
            key, value = line.split("=", 1)
            fields[key.strip().lower()] = value.strip()
            continue
        if current_section:
            sections.setdefault(current_section, []).append(line)

    rendered = {key: "\n".join(value).strip() for key, value in sections.items()}
    return {
        "timestamp": fields.get("timestamp"),
        "caller": fields.get("caller"),
        "source_route": fields.get("source_route"),
        "model_called": fields.get("model_called"),
        "model_name": fields.get("model_name"),
        "model_error": fields.get("model_error"),
        "child_prompt_sha256": fields.get("child_prompt_sha256"),
        "child_response_sha256": fields.get("child_response_sha256"),
        "canon_status": fields.get("canon_status"),
        "promotion_status": fields.get("promotion_status"),
        "seed_prompt_excerpt": _compact(rendered.get("seed_prompt_excerpt"), 700),
        "child_prompt_excerpt": _compact(rendered.get("child_prompt"), 900),
        "child_response": _compact(rendered.get("child_response"), 1400),
        "self_reflection": _compact(rendered.get("self_reflection"), 500),
        "boundary": {
            "sandbox_only": fields.get("sandbox_only") == "true",
            "external_send": fields.get("external_send") == "true",
            "git_push": fields.get("git_push") == "true",
            "gdrive_edit": fields.get("gdrive_edit") == "true",
            "command_exec": fields.get("command_exec") == "true",
            "computer_control": fields.get("computer_control") == "true",
            "canon_promotion": fields.get("canon_promotion") == "true",
        },
    }


def _journal_cycles(text: str) -> list[dict[str, Any]]:
    blocks = re.split(r"(?=^\.AI:ORACLE_SELF_PROMPT_CYCLE$)", text, flags=re.MULTILINE)
    cycles = [_parse_cycle(block) for block in blocks if block.strip().startswith(".AI:ORACLE_SELF_PROMPT_CYCLE")]
    return [cycle for cycle in cycles if cycle.get("timestamp") or cycle.get("child_response")]


def self_prompt_journal_payload(limit: int = 6, *, sandbox_root: Path | None = None) -> dict[str, Any]:
    root = sandbox_root or SANDBOX_ROOT
    bounded = max(1, min(int(limit or 6), 25))
    journal_path = root / "workbench" / "oracle_self_prompt_journal.ai"
    receipts_dir = root / "receipts"
    text = journal_path.read_text(encoding="utf-8", errors="replace") if journal_path.exists() else ""
    cycles = _journal_cycles(text)
    receipt_paths = sorted(receipts_dir.glob("sandbox_self_prompt_write*_receipt.json"), key=lambda p: p.stat().st_mtime, reverse=True) if receipts_dir.exists() else []
    latest_receipt = _read_json(receipt_paths[0]) if receipt_paths else None
    return {
        "ok": True,
        "operation_type": "self_prompt_journal_read",
        "generated_at": _utc_now(),
        "journal_path": str(journal_path),
        "journal_exists": journal_path.exists(),
        "journal_updated_at": _iso_mtime(journal_path),
        "entry_count": len(cycles),
        "receipt_count": len(receipt_paths),
        "latest_receipt_path": str(receipt_paths[0]) if receipt_paths else None,
        "latest_receipt": latest_receipt,
        "entries": list(reversed(cycles))[:bounded],
        "boundary": {
            "read_only": True,
            "sandbox_write": False,
            "external_send": False,
            "drive_mutation": False,
            "git_push": False,
            "canon_promotion": False,
            "raw_prompt_preview_truncated": True,
        },
    }


def _connector_item(
    connector_id: str,
    label: str,
    status: str,
    *,
    records: int = 0,
    detail: str = "",
    endpoint: str | None = None,
    boundary: str = "read-only status",
    holes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": connector_id,
        "label": label,
        "status": status,
        "records": int(records or 0),
        "detail": detail,
        "endpoint": endpoint,
        "boundary": boundary,
        "holes": list(holes or []),
    }


def connector_status_payload(self_prompt_status: dict[str, Any] | None = None) -> dict[str, Any]:
    connectors: list[dict[str, Any]] = []
    priorities: list[str] = []

    sp = self_prompt_status or {}
    if sp:
        daily_count = int(sp.get("daily_count") or 0)
        daily_cap = int(sp.get("daily_cap") or 0)
        connectors.append(_connector_item(
            "self_prompt",
            "Self-Prompt Writer",
            "verified" if sp.get("loop_running") or sp.get("journal_exists") else "degraded",
            records=int(sp.get("journal_entry_count") or 0),
            endpoint="/api/self-prompt/status",
            detail=f"{sp.get('current_state', 'UNKNOWN')} daily {daily_count}/{daily_cap}",
            boundary="sandbox-only writes by ORACLE lane; status read-only here",
        ))
        if daily_cap and daily_count / daily_cap >= 0.8:
            priorities.append("Self-prompt loop is near the daily cap; show status clearly and avoid accidental duplicate prompts.")
    else:
        connectors.append(_connector_item("self_prompt", "Self-Prompt Writer", "missing", endpoint="/api/self-prompt/status", holes=["status unavailable"]))

    try:
        import document_atlas

        atlas = document_atlas.atlas_status()
        stats = atlas.get("stats") or {}
        unresolved = atlas.get("unresolved_connector_intervals") or []
        connectors.append(_connector_item(
            "document_atlas",
            "Document Atlas",
            "verified" if atlas.get("available") else "missing",
            records=int(atlas.get("records") or stats.get("unified_record_count") or 0),
            endpoint="/api/document-atlas/status",
            detail=f"{stats.get('connector_unique_record_count', 0)} Google Drive connector records",
            boundary="candidate metadata only; source docs not mutated",
            holes=[f"{len(unresolved)} capped Drive windows"] if unresolved else [],
        ))
        if unresolved:
            priorities.append(f"Google Drive atlas still has {len(unresolved)} capped connector windows; completeness is not absolute.")
    except Exception as exc:
        connectors.append(_connector_item("document_atlas", "Document Atlas", "missing", endpoint="/api/document-atlas/status", holes=[f"{type(exc).__name__}: {exc}"]))

    try:
        import ai_lockbox

        lockbox = ai_lockbox.status_payload()
        connectors.append(_connector_item(
            "ai_lockbox",
            ".AI Lockbox",
            "verified" if lockbox.get("capsule_count") else "degraded",
            records=int(lockbox.get("capsule_count") or 0),
            endpoint="/api/ai-lockbox/status",
            detail=f"{lockbox.get('receipt_count', 0)} receipts",
            boundary="local shorthand recall; read-only unless explicit ingest command",
        ))
    except Exception as exc:
        connectors.append(_connector_item("ai_lockbox", ".AI Lockbox", "missing", endpoint="/api/ai-lockbox/status", holes=[f"{type(exc).__name__}: {exc}"]))

    try:
        import oracle_nexus

        nexus = oracle_nexus.nexus_snapshot()
        integration = nexus.get("integration") or {}
        connectors.append(_connector_item(
            "nexus",
            "Oracle Nexus",
            "verified" if integration.get("connected") else "degraded",
            records=int(integration.get("connected") or 0),
            endpoint="/api/nexus",
            detail=f"{integration.get('connected', 0)}/{integration.get('total', 0)} spec surfaces",
            boundary="read-only composition",
        ))
    except Exception as exc:
        connectors.append(_connector_item("nexus", "Oracle Nexus", "missing", endpoint="/api/nexus", holes=[f"{type(exc).__name__}: {exc}"]))

    try:
        import evidence_cockpit

        cockpit = evidence_cockpit.cockpit_snapshot()
        connectors.append(_connector_item(
            "evidence_cockpit",
            "Evidence Cockpit",
            "verified" if cockpit.get("ok") else "degraded",
            records=int(cockpit.get("available_surface_count") or cockpit.get("surface_count") or 0),
            endpoint="/api/evidence-cockpit",
            detail="answer evidence manifest",
            boundary="read-only evidence metadata",
        ))
    except Exception as exc:
        connectors.append(_connector_item("evidence_cockpit", "Evidence Cockpit", "missing", endpoint="/api/evidence-cockpit", holes=[f"{type(exc).__name__}: {exc}"]))
        priorities.append("Restart the live ORACLE server after merging Evidence Cockpit so the UI stops seeing 404s.")

    for connector_id, label, module_name, endpoint, receipt in (
        ("file_recall", "File Recall", "file_recall", "/api/file-recall/search", MEMORY_ROOT / "file_recall_receipts.jsonl"),
        ("internet_recall", "Internet Recall", "internet_recall", "/api/internet-recall/search", MEMORY_ROOT / "internet_recall_receipts.jsonl"),
        ("qr_scan", "QR Scan", "qr_scan", "/api/qr/scan", MEMORY_ROOT / "qr_scan_receipt_latest.json"),
    ):
        try:
            __import__(module_name)
            records = 1 if connector_id == "qr_scan" and receipt.exists() else _jsonl_count(receipt)
            connectors.append(_connector_item(
                connector_id,
                label,
                "verified" if records else "degraded",
                records=records,
                endpoint=endpoint,
                detail="module loaded; receipt trail present" if records else "module loaded; no recent status receipt",
                boundary="read-only capability; no mutation or external send",
                holes=[] if records else ["add a status endpoint or run one explicit smoke when needed"],
            ))
        except Exception as exc:
            connectors.append(_connector_item(connector_id, label, "missing", endpoint=endpoint, holes=[f"{type(exc).__name__}: {exc}"]))

    try:
        import readonly_access

        access = readonly_access.status_payload(ensure=False)
        connectors.append(_connector_item(
            "read_access",
            "Read Access",
            "verified" if access.get("access_status") == "granted" else "degraded",
            records=len(access.get("read_roots") or []),
            endpoint="/api/read-access",
            detail=str(access.get("access_mode") or "unknown"),
            boundary="read-only grant; actions still gated",
        ))
    except Exception as exc:
        connectors.append(_connector_item("read_access", "Read Access", "missing", endpoint="/api/read-access", holes=[f"{type(exc).__name__}: {exc}"]))

    status_order = {"verified": 0, "degraded": 1, "missing": 2, "blocked": 3}
    connectors.sort(key=lambda item: (status_order.get(item["status"], 9), item["label"]))
    summary = {
        "verified": sum(1 for item in connectors if item["status"] == "verified"),
        "degraded": sum(1 for item in connectors if item["status"] == "degraded"),
        "missing": sum(1 for item in connectors if item["status"] == "missing"),
        "blocked": sum(1 for item in connectors if item["status"] == "blocked"),
        "total": len(connectors),
    }
    if not priorities:
        priorities.append("Keep building evidence visibility: every connector should expose status, last receipt, and boundary.")
    priorities.append("Highest-value UI fix: make ORACLE's self-written sandbox trail visible without writing to sandbox.")
    return {
        "ok": True,
        "operation_type": "oracle_tuneup_connector_status",
        "generated_at": _utc_now(),
        "summary": summary,
        "connectors": connectors,
        "priorities": priorities[:8],
        "boundary": {
            "read_only": True,
            "sandbox_write": False,
            "source_mutation": False,
            "drive_mutation": False,
            "external_send": False,
            "canon_promotion": False,
        },
    }


__all__ = ["self_prompt_journal_payload", "connector_status_payload"]
