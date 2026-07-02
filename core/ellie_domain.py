"""Read-only registry helpers for the Ellie Rendered Reality domain."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "data" / "domains" / "ellie" / "domain_profile.json"
MANIFEST_PATH = ROOT / "data" / "domains" / "ellie" / "source_manifest.jsonl"
DOC_PATH = ROOT / "docs" / "ellie_rendered_reality_domain.md"


def load_profile() -> dict[str, Any]:
    if not PROFILE_PATH.exists():
        return {
            "name": "ellie",
            "status": "missing",
            "canon_status": "candidate",
            "promotion_status": "not_promoted",
            "read_allowed": True,
            "write_allowed": False,
            "error": f"profile missing: {PROFILE_PATH}",
        }
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def load_manifest() -> list[dict[str, Any]]:
    if not MANIFEST_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in MANIFEST_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _count(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(str(row.get(key) or "unknown") for row in rows))


def _sample_sources(rows: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    samples = []
    for row in rows[:limit]:
        samples.append({
            "source_id": row.get("source_id"),
            "title": row.get("title"),
            "layer": row.get("layer"),
            "source_family": row.get("source_family"),
            "ingestion_status": row.get("ingestion_status"),
            "canon_status": row.get("canon_status"),
            "promotion_status": row.get("promotion_status"),
            "sha256": row.get("sha256"),
            "path": row.get("path") or row.get("drive_url_or_id"),
            "notes": row.get("notes"),
        })
    return samples


def status_payload(limit: int = 8) -> dict[str, Any]:
    """Return an operator-safe Ellie domain status. No writes, no promotion."""
    profile = load_profile()
    rows = load_manifest()
    verified_rows = [
        row for row in rows
        if "verified" in str(row.get("ingestion_status") or "").lower()
    ]
    pending_rows = [
        row for row in rows
        if "pending" in str(row.get("ingestion_status") or "").lower()
    ]
    hashed_rows = [row for row in rows if row.get("sha256")]

    return {
        "ok": bool(rows) and profile.get("status") != "missing",
        "domain": "ellie",
        "status": profile.get("status", "candidate"),
        "canon_status": profile.get("canon_status", "candidate"),
        "promotion_status": profile.get("promotion_status", "not_promoted"),
        "sensitivity": profile.get("sensitivity", "high"),
        "read_allowed": bool(profile.get("read_allowed", True)),
        "write_allowed": bool(profile.get("write_allowed", False)),
        "source_count": len(rows),
        "hash_verified_source_count": len(hashed_rows),
        "connector_verified_source_count": len([
            row for row in rows
            if "connector" in str(row.get("ingestion_status") or "").lower()
        ]),
        "verified_source_count": len(verified_rows),
        "pending_source_count": len(pending_rows),
        "layers": _count(rows, "layer"),
        "source_families": profile.get("source_families", {}),
        "source_family_counts": _count(rows, "source_family"),
        "ingestion_status_counts": _count(rows, "ingestion_status"),
        "profile_path": str(PROFILE_PATH.resolve()),
        "manifest_path": str(MANIFEST_PATH.resolve()),
        "domain_document_path": str(DOC_PATH.resolve()),
        "sample_sources": _sample_sources(rows, limit=limit),
        "answer_policy": profile.get("answer_policy"),
        "boundary_rules": profile.get("boundary_rules", []),
        "suggested_prompts": [
            "Who is Ellie from the grounded Ellie Rendered Reality domain?",
            "Separate creative-fiction Ellie, Ellie.AI, and Rendered Reality Ellie.",
            "What is grounded about Ellie, and what remains candidate?",
        ],
        "no_write_actions": {
            "files_mutated": 0,
            "canon_promoted": False,
            "cloud_upload": False,
            "git_commit": False,
            "git_push": False,
        },
    }
