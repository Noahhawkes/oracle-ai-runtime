"""Guarded bridge from USER.AI relationship memory to NPC seed candidates.

This module does not create NPCs automatically. It translates approved
relationship records into *candidate* seeds with explicit consent gates. ORACLE
is the law layer; the active_npc runtime is the life layer; this bridge is the
receipt-bearing handoff between them.
"""
from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any


def _slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return text or "unknown"


def relationship_to_npc_seed(record: Any) -> dict[str, Any]:
    """Render one approved relationship record as a guarded NPC seed candidate."""
    data = record.to_dict() if hasattr(record, "to_dict") else (
        asdict(record) if hasattr(record, "__dataclass_fields__") else dict(record or {})
    )
    name = str(data.get("name") or "UNKNOWN").strip() or "UNKNOWN"
    sov_id = str(data.get("sov_id") or "").strip() or None
    rel_type = str(data.get("relationship_type") or "unknown").strip() or "unknown"
    trust_tier = str(data.get("trust_tier") or "").strip() or None
    is_self = rel_type.lower() == "self" or (sov_id or "").upper() == "SOV1.AI"

    consent_status = "owner_approved" if is_self else "requires_subject_opt_in"
    creation_allowed = bool(is_self)
    seed_key = sov_id or name
    return {
        "seed_id": f"npc-seed:{_slug(seed_key)}",
        "source_relationship_id": data.get("id"),
        "source_status": data.get("status"),
        "display_name": name,
        "sov_id": sov_id,
        "relationship_type": rel_type,
        "trust_tier": trust_tier,
        "tags": list(data.get("tags") or [])[:12],
        "consent_status": consent_status,
        "npc_creation_allowed": creation_allowed,
        "life_engine": "modules.active_npc",
        "memory_policy": "approved_relationship_summary_only",
        "blocked_inputs": [
            "raw_recordings",
            "raw_transcripts",
            "ambient_surveillance",
            "unapproved_private_memory",
        ],
        "next_gate": (
            "Subject explicitly opts in and approves the seed"
            if not creation_allowed else
            "Noah may instantiate his own self/assistant seed"
        ),
    }


def list_seed_candidates(limit: int = 25) -> list[dict[str, Any]]:
    """Return guarded NPC seed candidates from approved relationship memory."""
    from relationship_memory import RelationshipMemoryStore

    store = RelationshipMemoryStore()
    records = store.list_approved()
    seeds = [relationship_to_npc_seed(record) for record in records]
    seeds.sort(key=lambda item: (not item.get("npc_creation_allowed"), item.get("display_name") or ""))
    return seeds[: max(0, int(limit))]


def bridge_status() -> dict[str, Any]:
    """Summarize whether the law-to-life bridge can produce seed candidates."""
    try:
        seeds = list_seed_candidates()
        return {
            "available": True,
            "seed_candidate_count": len(seeds),
            "creation_allowed_count": sum(1 for seed in seeds if seed.get("npc_creation_allowed")),
            "server_bridge_status": "seed_candidates_only",
            "runtime_instantiation_status": "not_wired",
            "seed_candidates": seeds[:8],
        }
    except Exception as exc:
        return {
            "available": False,
            "seed_candidate_count": 0,
            "creation_allowed_count": 0,
            "server_bridge_status": "unavailable",
            "runtime_instantiation_status": "unknown",
            "error": f"{type(exc).__name__}: {exc}",
            "seed_candidates": [],
        }
