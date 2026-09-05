"""Local LootDrop continuity artifacts for ORACLE SourceMap.

LootDrop artifacts are symbolic continuity records. They are not currency,
not crypto, not transferable, and not financial assets. This module writes only
local JSON/JSONL records under the ratified private state root.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from root_map import RATIFIED_STATE_ROOT
except Exception:  # pragma: no cover - direct execution fallback
    RATIFIED_STATE_ROOT = Path(r"C:\Oracle\state")


STATE_ROOT = Path(RATIFIED_STATE_ROOT)
ARTIFACTS_DIR = STATE_ROOT / "artifacts" / "lootdrops"
RECEIPTS_DIR = STATE_ROOT / "receipts"
LEDGER_PATH = STATE_ROOT / "ledger" / "mindcoin_ledger.jsonl"

ALLOWED_ARTIFACT_TYPES = {
    "game_drop",
    "writing_milestone",
    "coding_breakthrough",
    "source_map_receipt",
    "boot_receipt",
    "continuity_anchor",
    "operator_morale",
    "unknown",
}

ALLOWED_EVIDENCE_STATES = {
    "DISCOVERED",
    "METADATA_READ",
    "CONTENT_OBSERVED",
    "INTERPRETED",
    "HUMAN_CONFIRMED",
}

NONFINANCIAL_NOTICE = (
    "MindCoin is symbolic, local-only, nonfinancial, nontransferable, and has "
    "no cash, crypto, market, or exchange value."
)

DEFAULT_MYRMIDON_LOOTDROP = {
    "artifact_type": "game_drop",
    "title": "Myrmidon\u2019s Signet of Thread Authority",
    "source_context": "World of Warcraft screenshot during ORACLE SourceMap work",
    "evidence_state": "HUMAN_CONFIRMED",
    "human_authority": "Noah.Physical",
    "description": (
        "Noah received Myrmidon\u2019s Signet while working on ORACLE SourceMap. "
        "ORACLE stores the symbolic continuity artifact; Codex built the shelf."
    ),
    "symbolic_stats": {
        "strength": 10,
        "agility": 7,
        "stamina": 17,
        "requires_level": 53,
    },
    "linked_files": [],
    "linked_receipts": [],
    "mindcoin_award": {
        "points": 53,
        "bonus_continuity_xp": 420,
        "reason": "Operator morale and continuity artifact captured during SourceMap build",
    },
    "notes": (
        "Human-confirmed game drop metadata only. No screenshot was uploaded, "
        "moved, copied, or embedded by this module."
    ),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def validate_lootdrop(artifact: dict[str, Any]) -> None:
    artifact_type = str(artifact.get("artifact_type") or "")
    evidence_state = str(artifact.get("evidence_state") or "")
    if artifact_type not in ALLOWED_ARTIFACT_TYPES:
        raise ValueError(f"invalid artifact_type: {artifact_type}")
    if evidence_state not in ALLOWED_EVIDENCE_STATES:
        raise ValueError(f"invalid evidence_state: {evidence_state}")
    if artifact.get("nonfinancial") is not True or artifact.get("nontransferable") is not True:
        raise ValueError("LootDrop artifacts must be nonfinancial and nontransferable")
    award = artifact.get("mindcoin_award") or {}
    if not isinstance(award, dict):
        raise ValueError("mindcoin_award must be an object")
    if int(award.get("points") or 0) < 0:
        raise ValueError("mindcoin_award.points cannot be negative")


def build_lootdrop_artifact(**overrides: Any) -> dict[str, Any]:
    data = json.loads(json.dumps(DEFAULT_MYRMIDON_LOOTDROP))
    for key, value in overrides.items():
        if value is not None:
            data[key] = value
    artifact = {
        "lootdrop_id": _id("lootdrop"),
        "timestamp": _now(),
        "artifact_type": data["artifact_type"],
        "title": data["title"],
        "source_context": data["source_context"],
        "evidence_state": data["evidence_state"],
        "human_authority": data["human_authority"],
        "description": data["description"],
        "symbolic_stats": data["symbolic_stats"],
        "linked_files": list(data.get("linked_files") or []),
        "linked_receipts": list(data.get("linked_receipts") or []),
        "mindcoin_award": data["mindcoin_award"],
        "nonfinancial": True,
        "nontransferable": True,
        "notes": data["notes"],
        "nonfinancial_notice": NONFINANCIAL_NOTICE,
    }
    validate_lootdrop(artifact)
    return artifact


def write_lootdrop_artifact(artifact: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = artifact or build_lootdrop_artifact()
    validate_lootdrop(payload)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS_DIR / f"lootdrop_{_stamp()}.json"
    _write_json(path, payload)
    out = dict(payload)
    out["artifact_path"] = str(path)
    return out


def latest_lootdrop_artifact() -> dict[str, Any] | None:
    try:
        paths = sorted(ARTIFACTS_DIR.glob("lootdrop_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:
        return None
    for path in paths:
        data = _read_json(path)
        if data:
            data["artifact_path"] = str(path)
            return data
    return None


def write_lootdrop_receipt(artifact: dict[str, Any] | None = None) -> dict[str, Any]:
    chosen = artifact or latest_lootdrop_artifact()
    if not chosen:
        chosen = write_lootdrop_artifact()
    artifact_path = chosen.get("artifact_path")
    receipt = {
        "receipt_id": _id("lootdrop_receipt"),
        "timestamp": _now(),
        "operation": "lootdrop_artifact_receipt",
        "lootdrop_id": chosen.get("lootdrop_id"),
        "artifact_title": chosen.get("title"),
        "artifact_type": chosen.get("artifact_type"),
        "artifact_path": artifact_path,
        "evidence_state": chosen.get("evidence_state"),
        "human_authority": "Noah.Physical",
        "files_moved": 0,
        "files_deleted": 0,
        "files_renamed": 0,
        "files_synced": 0,
        "files_uploaded": 0,
        "git_commits": 0,
        "git_pushes": 0,
        "nonfinancial": True,
        "nontransferable": True,
        "warnings": [],
        "notes": "Receipt for a symbolic local LootDrop artifact. No screenshot upload occurred.",
    }
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RECEIPTS_DIR / f"lootdrop_receipt_{_stamp()}.json"
    _write_json(path, receipt)
    out = dict(receipt)
    out["receipt_path"] = str(path)
    return out


def _ledger_rows() -> list[dict[str, Any]]:
    if not LEDGER_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in LEDGER_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    except Exception:
        return rows
    return rows


def ledger_summary() -> dict[str, Any]:
    rows = _ledger_rows()
    total = sum(int(row.get("points") or 0) for row in rows if row.get("nonfinancial") is True)
    bonus = sum(int(row.get("bonus_continuity_xp") or 0) for row in rows if row.get("nonfinancial") is True)
    latest = rows[-1] if rows else None
    return {
        "ledger_path": str(LEDGER_PATH),
        "event_count": len(rows),
        "mindcoin_total": total,
        "bonus_continuity_xp_total": bonus,
        "last_award_reason": (latest or {}).get("reason"),
        "latest_event": latest,
        "nonfinancial_notice": NONFINANCIAL_NOTICE,
    }


def award_mindcoin_for_lootdrop(
    artifact: dict[str, Any] | None = None,
    receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    chosen = artifact or latest_lootdrop_artifact()
    if not chosen:
        chosen = write_lootdrop_artifact()
    chosen_receipt = receipt or write_lootdrop_receipt(chosen)
    award = chosen.get("mindcoin_award") or {}
    event = {
        "event_id": _id("mindcoin"),
        "timestamp": _now(),
        "award_name": chosen.get("title"),
        "points": int(award.get("points") or 0),
        "bonus_continuity_xp": int(award.get("bonus_continuity_xp") or 0),
        "reason": award.get("reason") or "",
        "evidence_receipt_id": chosen_receipt.get("receipt_id"),
        "receipt_path": chosen_receipt.get("receipt_path"),
        "lootdrop_id": chosen.get("lootdrop_id"),
        "artifact_path": chosen.get("artifact_path"),
        "nonfinancial": True,
        "nontransferable": True,
        "notes": NONFINANCIAL_NOTICE,
    }
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER_PATH.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=True, sort_keys=True) + "\n")
    return event


def create_manual_lootdrop(**overrides: Any) -> dict[str, Any]:
    artifact = write_lootdrop_artifact(build_lootdrop_artifact(**overrides))
    receipt = write_lootdrop_receipt(artifact)
    mindcoin_event = award_mindcoin_for_lootdrop(artifact, receipt)
    return {
        "artifact": artifact,
        "receipt": receipt,
        "mindcoin_event": mindcoin_event,
        "ledger": ledger_summary(),
    }


def status_payload() -> dict[str, Any]:
    latest = latest_lootdrop_artifact()
    ledger = ledger_summary()
    return {
        "latest_lootdrop": latest,
        "ledger": ledger,
        "mindcoin_total": ledger["mindcoin_total"],
        "last_award_reason": ledger["last_award_reason"],
        "linked_receipt": (ledger.get("latest_event") or {}).get("receipt_path"),
        "nonfinancial_notice": NONFINANCIAL_NOTICE,
        "buttons": ["Create manual LootDrop", "Write LootDrop receipt", "Award MindCoin"],
    }


if __name__ == "__main__":
    print(json.dumps(status_payload(), indent=2, ensure_ascii=True, sort_keys=True))
