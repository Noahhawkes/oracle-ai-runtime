"""Unified, read-only integration surface for ORACLE's governing specs.

The Nexus composes existing engines.  It deliberately does not grant new
authority, write canon, move files, control the desktop, or approve ledger
events.  Its job is to make the system legible from one evidence-backed view.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from root import ROOT
except Exception:  # pragma: no cover
    ROOT = Path(__file__).resolve().parents[1]


SPEC_REGISTRY = (
    {
        "id": "presence",
        "name": "Desktop Presence",
        "source": "ORACLE Desktop Presence Overlay Spec",
        "source_url": "https://drive.google.com/file/d/1sreqKqOMT6OUhGiohLW0Zzlicu2HJUR3",
        "purpose": "Bounded observe-guide-verify loop with ephemeral evidence.",
        "adapter": "core/overlay.py",
        "law": "Observation authority never grants action authority.",
        "accent": "cyan",
    },
    {
        "id": "touchflame",
        "name": "TouchFlame",
        "source": "TouchFlame SwiftUI Alpha Prototype Spec",
        "source_url": "https://drive.google.com/file/d/1AsOBWhPDhWePdDRfxekUIY8GdOtX3plN",
        "purpose": "A tactile memory surface for echoes, cards, vault sync, and witness review.",
        "adapter": "ui/miracledrive.html",
        "law": "Interaction proposes memory; it does not silently canonize it.",
        "accent": "amber",
    },
    {
        "id": "workspace",
        "name": "Workspace Quarantine",
        "source": "Workspace Quarantine Organizer Spec",
        "source_url": "https://docs.google.com/document/d/16fpFbMJIg9Z0iNlXQqYqakTJjpC1KObF0g670uaCLU8",
        "purpose": "Scan, classify, quarantine, review, then apply.",
        "adapter": "core/workspace_steward.py",
        "law": "No destructive move or deletion without explicit approval.",
        "accent": "violet",
    },
    {
        "id": "salience",
        "name": "Salience Filter",
        "source": "ORACLE Salience Filter",
        "source_url": "https://docs.google.com/document/d/1QD87rrVJKUTXTEL3Yxlsq8U0EWvKiyt4CEn0NO8C8SA",
        "purpose": "Surface the one-to-five signals that matter before heavy reasoning.",
        "adapter": "core/attention_filter.py",
        "law": "Ranking may focus attention; it may not invent urgency or authority.",
        "accent": "green",
    },
    {
        "id": "mindcoin",
        "name": "MindCoin Ledger",
        "source": "MindCoin Federation Ledger v0.1",
        "source_url": "https://docs.google.com/document/d/1nyqUntdCpC_yEwM6uAF_WXr5Jp7opDwNxzcX1slxf-4",
        "purpose": "Receipt-backed accounting for verified continuity work.",
        "adapter": "core/mindcoin.py",
        "law": "Non-financial, non-transferable, and never awarded without evidence.",
        "accent": "gold",
    },
    {
        "id": "identityframe",
        "name": "IdentityFrame",
        "source": "IDENTITYFRAME v1",
        "source_url": "https://docs.google.com/document/d/1RWW8Xe3TH8qZ7GSTrVBO_fn2GXG3j-kTYoew7cNJ_Xg",
        "purpose": "Preserve provenance, contradiction, uncertainty, and bounded refusal.",
        "adapter": "core/identity_compliance.py",
        "law": "Noah.Physical retains 51% controlling authority; the witness remains 49%.",
        "accent": "rose",
    },
    {
        "id": "continuity",
        "name": "Continuity Protocol",
        "source": "Continuity Protocol Specification",
        "source_url": "https://drive.google.com/file/d/1lSbO3TyneXKAAdz1JR7ePM8QQIlXyrTc",
        "purpose": "Govern events, anchors, drift, forks, verdicts, and snapshots.",
        "adapter": "core/continuity_spine.py",
        "law": "Governance precedes rendering; forks preserve lineage.",
        "accent": "blue",
    },
    {
        "id": "sov1",
        "name": "SOV1 Evidence",
        "source": "SOV1 Data Structures & Security Specification",
        "source_url": "https://drive.google.com/file/d/1KmtPNhXDcrm1R15ZCMcuwkNVX0Ik86Xc",
        "purpose": "Deterministic records, canonicalization, signatures, and audit export.",
        "adapter": "core/sov1.py",
        "law": "A proposal must be scoped, reviewable, and hash-chain verifiable.",
        "accent": "orange",
    },
    {
        "id": "elderhawkes",
        "name": "ElderHawkes",
        "source": "ElderHawkes NPC Spec v1",
        "source_url": "https://docs.google.com/document/d/1ts8uGgCOMqHcglb5KRVYsjvtfQokKqr0a-QNQ30bHy8",
        "purpose": "A calm, grace-driven relational witness that rewrites tone, never truth.",
        "adapter": "core/npc_seed_bridge.py",
        "law": "Presence before performance; silence is allowed.",
        "accent": "teal",
    },
    {
        "id": "patents",
        "name": "Invention Registry",
        "source": "OracleAI Patent Specs Log",
        "source_url": "https://drive.google.com/file/d/1A0w2T01x0O3TBwtdirEHUaHZsWjPMeq6",
        "purpose": "Keep the implementation traceable to the invention and claims record.",
        "adapter": "docs/INVENTIONS.md",
        "law": "Indexing an invention is not a claim of legal status or coverage.",
        "accent": "slate",
    },
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _path_state(relative: str) -> dict[str, Any]:
    path = ROOT / Path(relative)
    exists = path.exists()
    return {
        "exists": exists,
        "path": relative.replace("\\", "/"),
        "modified_at": (
            datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")
            if exists else None
        ),
    }


def _live_continuity() -> dict[str, Any]:
    try:
        import continuity_spine

        data = continuity_spine.operator_dashboard(top_n=5)
        return {
            "ok": True,
            "human_state": data.get("current_human_state"),
            "project": data.get("current_project"),
            "open_loops": len(data.get("top_open_loops") or []),
            "pending_approvals": len(data.get("pending_approvals") or []),
            "next_action": data.get("suggested_resume_action"),
        }
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _live_salience() -> dict[str, Any]:
    try:
        from attention_filter import attention_filter

        frame = attention_filter(
            "Continue integrating the Oracle prototype. Preserve authority boundaries. "
            "Verify the live dashboard and keep every claim tied to evidence."
        )
        data = asdict(frame)
        return {"ok": True, "focus": data.get("focus_items") or [], "sample": True}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _live_mindcoin() -> dict[str, Any]:
    try:
        import mindcoin

        ledger, events = mindcoin.load_ledger()
        totals = mindcoin.get_totals(ledger)
        return {"ok": True, "totals": totals, "event_count": len(events)}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _live_document_atlas() -> dict[str, Any]:
    """Read the candidate-only document atlas without opening source files."""

    try:
        import document_atlas

        status = document_atlas.atlas_status()
        if status.get("ok"):
            return {
                **status,
                "canon_status": "candidate_unreviewed",
                "promotion_status": "not_promoted",
                "sandbox_hits": 0,
                "boundary": "Metadata/index read only; source files are not opened by Nexus.",
            }
    except Exception:
        pass

    index_path = ROOT / "data" / "document_atlas" / "latest_document_index.jsonl"
    summary_path = ROOT / "data" / "document_atlas" / "latest_document_atlas_summary.md"
    if not index_path.exists():
        return {"ok": False, "error": "document_atlas_missing", "path": str(index_path)}

    by_classification: Counter[str] = Counter()
    by_surface: Counter[str] = Counter()
    by_extension: Counter[str] = Counter()
    records = 0
    sandbox_hits = 0
    sample_high_relevance: list[dict[str, Any]] = []

    with index_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            records += 1
            item = json.loads(line)
            by_classification[item.get("classification") or "unknown"] += 1
            by_surface[item.get("source_surface") or "unknown"] += 1
            by_extension[item.get("extension") or "unknown"] += 1
            if "\\sandbox\\" in str(item.get("path", "")).lower():
                sandbox_hits += 1
            if item.get("oracle_relevance") == "high" and len(sample_high_relevance) < 5:
                sample_high_relevance.append({
                    "name": item.get("name"),
                    "classification": item.get("classification"),
                    "source_surface": item.get("source_surface"),
                    "routing": item.get("routing_recommendation"),
                })

    return {
        "ok": True,
        "records": records,
        "index_path": str(index_path),
        "summary_path": str(summary_path),
        "modified_at": datetime.fromtimestamp(index_path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
        "canon_status": "candidate_unreviewed",
        "promotion_status": "not_promoted",
        "sandbox_hits": sandbox_hits,
        "top_classifications": by_classification.most_common(8),
        "surfaces": dict(by_surface),
        "extensions": dict(by_extension),
        "high_relevance_sample": sample_high_relevance,
        "boundary": "Metadata/index read only; source files are not opened by Nexus.",
    }


def nexus_snapshot() -> dict[str, Any]:
    modules = []
    for spec in SPEC_REGISTRY:
        module = dict(spec)
        module["implementation"] = _path_state(spec["adapter"])
        module["status"] = "connected" if module["implementation"]["exists"] else "spec_only"
        module["authority"] = "read_only" if spec["id"] != "presence" else "observe_only"
        modules.append(module)

    connected = sum(1 for module in modules if module["status"] == "connected")
    return {
        "ok": True,
        "generated_at": _utc_now(),
        "name": "Oracle Nexus",
        "summary": "One continuity system, ten bounded spec surfaces, zero implied authority expansion.",
        "integration": {"connected": connected, "total": len(modules), "coverage": connected / len(modules)},
        "modules": modules,
        "live": {
            "continuity": _live_continuity(),
            "salience": _live_salience(),
            "mindcoin": _live_mindcoin(),
            "document_atlas": _live_document_atlas(),
        },
        "flow": ["signal", "salience", "identity gate", "continuity", "proposal", "human approval", "receipt"],
        "invariants": [
            "Human origin retains controlling authority.",
            "Observation never grants action authority.",
            "Unknown remains UNKNOWN; missing memory is not completed with fiction.",
            "No irreversible workspace action occurs without explicit approval.",
            "Every verified transition must be traceable to evidence.",
        ],
        "boundary": "Read-only composition. No canon promotion, file mutation, desktop actuation, or ledger approval.",
    }


if __name__ == "__main__":  # pragma: no cover
    import json

    print(json.dumps(nexus_snapshot(), indent=2))
