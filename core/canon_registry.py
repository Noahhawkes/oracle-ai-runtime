"""Read-only canon registry helpers for governed story continuity.

The registry is deliberately inert: it reads local JSON, returns status
payloads, and never promotes, publishes, pushes, or mutates external systems.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "data" / "canon_registry" / "jupiter_station_2397.json"
JUPITER_PROFILE_PATH = ROOT / "data" / "domains" / "jupiter_station" / "domain_profile.json"
JUPITER_MANIFEST_PATH = ROOT / "data" / "domains" / "jupiter_station" / "source_manifest.jsonl"
JUPITER_DOC_PATH = ROOT / "docs" / "jupiter_station_2397_canon_registry.md"

ALLOWED_STATUSES = (
    "active_canon",
    "candidate_canon",
    "demoted_canon",
    "alternate_branch",
    "rejected",
    "unknown",
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return {
            "ok": False,
            "registry_id": "jupiter_station_2397_canon_registry",
            "status": "missing",
            "allowed_statuses": list(ALLOWED_STATUSES),
            "entries": [],
            "error": f"registry missing: {REGISTRY_PATH}",
        }
    registry = _read_json(REGISTRY_PATH)
    registry.setdefault("allowed_statuses", list(ALLOWED_STATUSES))
    registry.setdefault("entries", [])
    return registry


def load_manifest() -> list[dict[str, Any]]:
    if not JUPITER_MANIFEST_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in JUPITER_MANIFEST_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _status_counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(entry.get("canon_status") or "unknown") for entry in entries))


def _domain_counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for entry in entries:
        for domain in entry.get("domains") or []:
            counts[str(domain)] += 1
    return dict(counts)


def _violating_statuses(entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    allowed = set(ALLOWED_STATUSES)
    violations: list[dict[str, str]] = []
    for entry in entries:
        status = str(entry.get("canon_status") or "unknown")
        if status not in allowed:
            violations.append({
                "id": str(entry.get("id") or "unknown"),
                "canon_status": status,
            })
    return violations


def status_payload() -> dict[str, Any]:
    """Return read-only registry status. No writes and no promotion."""
    registry = load_registry()
    entries = list(registry.get("entries") or [])
    manifest_rows = load_manifest()
    violations = _violating_statuses(entries)
    active = [entry for entry in entries if entry.get("canon_status") == "active_canon"]
    demoted = [entry for entry in entries if entry.get("canon_status") == "demoted_canon"]

    return {
        "ok": bool(entries) and not violations,
        "registry_id": registry.get("registry_id", "jupiter_station_2397_canon_registry"),
        "authority": registry.get("authority", "Noah.Physical"),
        "status": registry.get("status", "candidate_registry"),
        "allowed_statuses": list(ALLOWED_STATUSES),
        "entry_count": len(entries),
        "manifest_source_count": len(manifest_rows),
        "canon_status_counts": _status_counts(entries),
        "domain_counts": _domain_counts(entries),
        "active_canon_ids": [entry.get("id") for entry in active],
        "demoted_canon_ids": [entry.get("id") for entry in demoted],
        "violating_statuses": violations,
        "registry_path": str(REGISTRY_PATH.resolve()),
        "profile_path": str(JUPITER_PROFILE_PATH.resolve()),
        "manifest_path": str(JUPITER_MANIFEST_PATH.resolve()),
        "domain_document_path": str(JUPITER_DOC_PATH.resolve()),
        "source_receipts": registry.get("source_receipts", []),
        "no_write_actions": {
            "files_overwritten": 0,
            "executables_generated": 0,
            "external_send": False,
            "cloud_upload": False,
            "drive_edit": False,
            "git_commit": False,
            "git_push": False,
            "canon_promoted_by_runtime": False,
        },
    }


def lookup(text: str, *, max_hits: int = 8) -> list[dict[str, Any]]:
    """Lookup registry entries by text terms. Deterministic and read-only."""
    low = str(text or "").lower()
    if not low:
        return []
    hits: list[dict[str, Any]] = []
    for entry in load_registry().get("entries") or []:
        hay = " ".join([
            str(entry.get("id") or ""),
            str(entry.get("title") or ""),
            str(entry.get("claim") or ""),
            " ".join(str(domain) for domain in entry.get("domains") or []),
            " ".join(str(alias) for alias in entry.get("aliases") or []),
            str(entry.get("notes") or ""),
        ]).lower()
        if any(term in hay for term in low.split() if len(term) >= 3):
            hits.append(entry)
        if len(hits) >= max_hits:
            break
    return hits
