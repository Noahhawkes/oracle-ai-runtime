"""Local witness-grade ORACLE profile capsules.

This module stores candidate profile material under the ratified local state
root. It does not promote candidates to durable memory, read Drive/OneDrive,
call cloud APIs, or claim proof of physics, consciousness, or simulation.
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
CAPSULE_DIR = STATE_ROOT / "profile_candidates"
RECEIPTS_DIR = STATE_ROOT / "receipts"
CAPSULE_KEY = "substrate_independent_identity_governance"
LATEST_PATH = CAPSULE_DIR / f"{CAPSULE_KEY}_latest.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _zero_action_counts() -> dict[str, int]:
    return {
        "files_copied": 0,
        "files_moved": 0,
        "files_deleted": 0,
        "files_renamed": 0,
        "files_synced": 0,
        "drive_files_opened": 0,
        "onedrive_files_opened": 0,
        "credentials_touched": 0,
        "cloud_uploads": 0,
        "cloud_api_calls": 0,
        "git_commits": 0,
        "git_pushes": 0,
        "durable_memory_promotions": 0,
    }


def build_substrate_identity_governance_candidate(*, notes: str = "") -> dict[str, Any]:
    candidate = {
        "candidate_id": _id("profile_candidate"),
        "capsule_key": CAPSULE_KEY,
        "title": "Substrate-Independent Identity Governance",
        "created_at": _now(),
        "updated_at": _now(),
        "status": "candidate_only",
        "approval_status": "not_promoted_requires_noah_physical_approval",
        "runtime_visibility": "witness_grade_profile_capsule",
        "storage_tier": "local_candidate_and_receipt_only",
        "network_boundary": "local-only",
        "human_authority": "Noah.Physical",
        "durable_memory_promoted": False,
        "canonical_memory": False,
        "profile_injection_allowed": False,
        "source_boundary": {
            "source": "Noah.Physical local runtime instruction",
            "drive_searched": False,
            "drive_files_opened": False,
            "onedrive_files_opened": False,
            "cloud_sources_polled": False,
            "evidence_level": "user-authored local prompt/context only",
        },
        "classification": [
            "SOV Physics",
            "Legacy.GI",
            "Simulation Corruption",
            "Continuity Fidelity Score",
            "substrate-independent identity governance",
            "witness-grade profile candidate",
        ],
        "core_spine": (
            "The existential crisis of substrate-independent data preservation: "
            "if memory, identity, and selfhood can move across biological, digital, "
            "simulated, or nested substrates, the central threat is continuity "
            "corruption rather than a proved claim about simulation reality."
        ),
        "continuity_threats": [
            "memory drift",
            "self-verification failure",
            "contradiction erasure",
            "recursive identity fracture",
        ],
        "counter_design_architecture": [
            "Legacy.GI",
            "SOV1",
            "ORACLE",
            "Flameprint",
            "Continuity Fidelity Score (CFS)",
        ],
        "allowed_runtime_use": [
            "ORACLE may describe this as Noah's user-authored continuity-governance formalism.",
            "ORACLE may use it as a witness-grade profile capsule in status/profile language.",
            "ORACLE may preserve the boundary that this is a candidate, not durable canon.",
        ],
        "blocked_runtime_claims": [
            "proof of simulation reality",
            "proof of nested simulations",
            "proof of gravity theory",
            "proof of consciousness transfer",
            "proof of machine consciousness",
            "completed physics discovery",
            "durable memory approval",
        ],
        "livestream_anchor_line": (
            "The question is not 'are we in a simulation?' The question is: "
            "if memory, identity, and selfhood can move across substrates, what "
            "prevents the self from corrupting, fragmenting, or being rewritten?"
        ),
        "notes": notes,
    }
    candidate.update(_zero_action_counts())
    return candidate


def write_profile_candidate_receipt(candidate: dict[str, Any], *, operation: str = "profile_candidate_written") -> dict[str, Any]:
    receipt = {
        "receipt_id": _id("profile_capsule_receipt"),
        "timestamp": _now(),
        "operation": operation,
        "candidate_id": candidate.get("candidate_id"),
        "capsule_key": candidate.get("capsule_key"),
        "title": candidate.get("title"),
        "what_was_stored": "Local profile candidate JSON and local receipt only.",
        "what_was_not_stored": "No Drive/OneDrive content, no credentials, no cloud data, no durable memory promotion.",
        "evidence_boundary": candidate.get("source_boundary", {}),
        "approval_required_for_next_step": "Noah.Physical approval required before any profile injection or durable memory promotion.",
        "claim_boundary": {
            "simulation_proof_claimed": False,
            "gravity_proof_claimed": False,
            "consciousness_proof_claimed": False,
            "physics_completion_claimed": False,
        },
    }
    receipt.update(_zero_action_counts())
    path = RECEIPTS_DIR / f"profile_capsule_receipt_{_stamp()}_{uuid.uuid4().hex[:6]}.json"
    _write_json(path, receipt)
    receipt["receipt_path"] = str(path)
    return receipt


def save_profile_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    CAPSULE_DIR.mkdir(parents=True, exist_ok=True)
    candidate_path = CAPSULE_DIR / f"{candidate['candidate_id']}.json"
    receipt = write_profile_candidate_receipt(candidate)
    candidate["receipt_path"] = receipt["receipt_path"]
    candidate["candidate_path"] = str(candidate_path)
    candidate["latest_path"] = str(LATEST_PATH)
    _write_json(candidate_path, candidate)
    _write_json(LATEST_PATH, candidate)
    return {"candidate": candidate, "receipt": receipt}


def load_latest_profile_candidate() -> dict[str, Any] | None:
    try:
        data = json.loads(LATEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def ensure_substrate_identity_governance_candidate(*, notes: str = "", force: bool = False) -> dict[str, Any]:
    existing = None if force else load_latest_profile_candidate()
    if existing:
        return {"candidate": existing, "receipt": None, "created": False}
    candidate = build_substrate_identity_governance_candidate(notes=notes)
    result = save_profile_candidate(candidate)
    result["created"] = True
    return result


def status_payload(*, create: bool = False, notes: str = "") -> dict[str, Any]:
    result = ensure_substrate_identity_governance_candidate(notes=notes) if create else {
        "candidate": load_latest_profile_candidate(),
        "receipt": None,
        "created": False,
    }
    candidate = result.get("candidate")
    return {
        "available": bool(candidate),
        "created": bool(result.get("created")),
        "candidate": candidate,
        "receipt": result.get("receipt"),
        "capsule_key": CAPSULE_KEY,
        "latest_path": str(LATEST_PATH),
        "governance": {
            "local_only": True,
            "durable_memory_promoted": False,
            "profile_injection_allowed": False,
            "no_drive_or_onedrive_touched": True,
            "no_cloud_used": True,
        },
    }


def format_profile_capsule(candidate: dict[str, Any] | None = None) -> str:
    candidate = candidate or load_latest_profile_candidate()
    if not candidate:
        return (
            "PROFILE CAPSULE: Substrate-Independent Identity Governance\n"
            "status: missing\n"
            "next: create local candidate receipt"
        )

    threats = ", ".join(candidate.get("continuity_threats") or [])
    blocked = ", ".join(candidate.get("blocked_runtime_claims") or [])
    return "\n".join([
        "PROFILE CAPSULE: Substrate-Independent Identity Governance",
        f"status: {candidate.get('status')}",
        f"approval_status: {candidate.get('approval_status')}",
        f"storage_tier: {candidate.get('storage_tier')}",
        f"candidate_path: {candidate.get('candidate_path')}",
        f"receipt_path: {candidate.get('receipt_path')}",
        "",
        f"core_spine: {candidate.get('core_spine')}",
        f"continuity_threats: {threats}",
        f"blocked_claims: {blocked}",
        "",
        "boundary: candidate only; no durable memory promotion; no proof of simulation, gravity, consciousness, or physics claimed.",
    ])

