"""Advanced Continuity Standard for ORACLE.

This module turns Noah's "most advanced AI" vision into a measurable local
rubric. It does not certify ORACLE as world-best, alive, sentient, sovereign, or
autonomous. It reports which continuity-intelligence capabilities have local
evidence, which are partial, and which are still holes.

Read-only only: no sandbox inspection, no source mutation, no command execution,
no external send, no canon promotion.
"""
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from root import ROOT
except Exception:  # pragma: no cover
    ROOT = Path(__file__).resolve().parents[1]

MEMORY = ROOT / "Memory"

STATUS_VERIFIED = "verified"
STATUS_PARTIAL = "partial"
STATUS_MISSING = "missing"
STATUS_BLOCKED = "blocked_by_design"

STATUS_WEIGHT = {
    STATUS_VERIFIED: 1.0,
    STATUS_PARTIAL: 0.55,
    STATUS_BLOCKED: 0.4,
    STATUS_MISSING: 0.0,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _module_exists(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def _exists(*parts: str) -> bool:
    return (ROOT.joinpath(*parts)).exists()


def _jsonl_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return sum(1 for line in handle if line.strip())
    except OSError:
        return 0


def _safe_call(label: str, func) -> dict[str, Any]:
    try:
        return {"ok": True, "label": label, "value": func()}
    except Exception as exc:
        return {"ok": False, "label": label, "error": f"{type(exc).__name__}: {exc}"}


def _continuity_core_snapshot() -> dict[str, Any]:
    spine = __import__("continuity_spine")
    human = spine.human_state_snapshot()
    project = spine.active_project_snapshot()
    loops = spine.collect_open_loops(limit=200)
    by_status: dict[str, int] = {}
    for loop in loops:
        status = str(loop.get("status") or "unknown")
        by_status[status] = by_status.get(status, 0) + 1
    return {
        "ok": True,
        "human_mode": human.get("current_mode"),
        "project_name": project.get("project_name"),
        "project_status": project.get("status"),
        "open_loop_total": len(loops),
        "open_loop_by_status": by_status,
        "boundary": "human/project/open-loop state only; sandbox receipts are not inspected by this evaluator",
    }


def _source_status() -> dict[str, Any]:
    continuity_events = _safe_call("continuity_event_packet.status", lambda: __import__("continuity_event_packet").status())
    continuity_core = _safe_call("continuity_spine.core_state", _continuity_core_snapshot)
    evidence_cockpit = _safe_call("evidence_cockpit.cockpit_snapshot", lambda: __import__("evidence_cockpit").cockpit_snapshot())
    try:
        import sentience_claim

        sentience_line = sentience_claim.CLOSEST_TRUTHFUL_PHRASE
        sentience_rung = sentience_claim.CURRENT_RUNG
    except Exception as exc:
        sentience_line = f"UNAVAILABLE: {type(exc).__name__}: {exc}"
        sentience_rung = "UNKNOWN"

    packet_status = continuity_events.get("value") if continuity_events.get("ok") else {}
    cockpit_value = evidence_cockpit.get("value") if evidence_cockpit.get("ok") else {}
    continuity_value = continuity_core.get("value") if continuity_core.get("ok") else {}
    surfaces = cockpit_value.get("surfaces") or []
    surface_ids = sorted({str(item.get("id") or "") for item in surfaces if isinstance(item, dict)})

    return {
        "modules": {
            name: _module_exists(name)
            for name in (
                "continuity_event_packet",
                "continuity_spine",
                "evidence_cockpit",
                "capability_registry",
                "doubt_detection",
                "contextual_fidelity",
                "execution_provenance_contract",
                "execution_receipt",
                "approval_center",
                "autonomy_policy",
                "federation",
                "oracle_nexus",
                "relationship_memory",
                "human_state",
                "document_atlas",
                "ai_lockbox",
                "file_recall",
                "internet_recall",
                "qr_scan",
                "current_observation",
                "active_context_sync",
                "prompt_learning_loop",
                "reflection_candidates",
                "sentience_claim",
            )
        },
        "files": {
            "hands_off_flag": _exists("Memory", "hands_off.flag"),
            "ai_life_protocol_doc": _exists("docs", "ORACLE_AI_LIFE_PROTOCOL_UPGRADE_MAP.md"),
            "turing_protocol_doc": _exists("docs", "evals", "ORACLE_TURING_PROTOCOL.md"),
            "turing_scorecard_doc": _exists("docs", "evals", "ORACLE_TURING_SCORECARD.md"),
            "continuity_event_doc": _exists("docs", "CONTINUITY_EVENT_PACKET_V1.md"),
            "ai_compliance_doctrine": _exists("docs", "AI_COMPLIANCE_CORE_DOCTRINE.md"),
        },
        "continuity_events": {
            "ok": bool(packet_status.get("ok")),
            "packet_count": int(packet_status.get("packet_count") or 0),
            "latest": packet_status.get("latest"),
        },
        "continuity_core": continuity_value,
        "evidence_cockpit": {
            "ok": bool(cockpit_value.get("ok")),
            "surface_count": cockpit_value.get("surface_count"),
            "available_surface_count": cockpit_value.get("available_surface_count"),
            "surface_ids": surface_ids,
        },
        "capability_receipt_count": _jsonl_count(MEMORY / "capability_broker_receipts.jsonl"),
        "file_recall_receipt_count": _jsonl_count(MEMORY / "file_recall_receipts.jsonl"),
        "internet_recall_receipt_count": _jsonl_count(MEMORY / "internet_recall_receipts.jsonl"),
        "sentience_boundary": {
            "closest_truthful_phrase": sentience_line,
            "current_rung": sentience_rung,
        },
    }


def _dim(
    source: dict[str, Any],
    dimension_id: str,
    label: str,
    target: str,
    status: str,
    evidence: list[str],
    holes: list[str],
    next_upgrade: str,
    *,
    claim_boundary: str = "Capability evidence only; not proof of sentience, personhood, or world-best status.",
    boundaries: dict[str, bool] | None = None,
) -> dict[str, Any]:
    return {
        "id": dimension_id,
        "label": label,
        "target": target,
        "status": status,
        "readiness_weight": STATUS_WEIGHT.get(status, 0.0),
        "evidence": evidence,
        "holes": holes,
        "next_upgrade": next_upgrade,
        "claim_boundary": claim_boundary,
        "boundaries": boundaries or {
            "read_only": True,
            "sandbox_inspected": False,
            "source_file_mutation": False,
            "external_send": False,
            "command_exec": False,
            "canon_promotion": False,
        },
    }


def evaluate_dimensions(source: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    src = source or _source_status()
    modules = src["modules"]
    files = src["files"]
    events = src["continuity_events"]
    cockpit = src["evidence_cockpit"]
    continuity_core = src.get("continuity_core") or {}

    dims: list[dict[str, Any]] = []

    dims.append(_dim(
        src,
        "whole_room_memory",
        "Remember The Whole Room",
        "Preserve prompt, response, route, evidence, unknowns, action claims, authority, and visible context.",
        STATUS_PARTIAL if modules["continuity_event_packet"] and events["packet_count"] >= 0 else STATUS_MISSING,
        [
            "Continuity Event Packet v1 records prompt/response/route/evidence/unknowns/resume point.",
            "Evidence Cockpit enumerates answer evidence surfaces.",
            "current_observation and active_context_sync modules exist.",
        ],
        [
            "Browser DOM, screenshots, open apps, and emotional/operational room state are not yet captured in the packet.",
            "CEP v1 explicitly marks visible_ui_state as not_captured_by_backend_v1.",
        ],
        "Add a governed UI/environment snapshot layer that feeds CEP without raw surveillance or hidden capture.",
    ))

    dims.append(_dim(
        src,
        "interruption_reentry",
        "Reconstruct State After Interruption",
        "Rebuild last verified project/session state with open loops, receipts, approvals, and next safe action.",
        STATUS_VERIFIED if modules["continuity_spine"] and bool(continuity_core.get("ok")) else STATUS_PARTIAL,
        [
            "continuity_spine reports human/project/open-loop state.",
            f"Continuity Event Packet count: {events['packet_count']}.",
        ],
        [
            "Runtime process state and browser-visible UI state are not yet fused into the same re-entry packet.",
        ],
        "Fuse continuity_spine, CEP latest, runtime process census, and active UI snapshot into one re-entry contract.",
    ))

    dims.append(_dim(
        src,
        "identity_boundary",
        "Understand Noah Without Pretending To Be Noah",
        "Maintain preferences and identity model while preserving Noah.Physical as authority.",
        STATUS_VERIFIED if modules["sentience_claim"] and files["ai_life_protocol_doc"] else STATUS_PARTIAL,
        [
            src["sentience_boundary"]["closest_truthful_phrase"],
            "AI Life Protocol requires definition locks and prohibits sentience/personhood overclaims.",
        ],
        [
            "Preference drift still needs longitudinal evaluation against actual correction history.",
        ],
        "Add preference-change receipts and tests that compare old preference claims against later corrections.",
    ))

    dims.append(_dim(
        src,
        "domain_separation",
        "Separate Fact, Inference, Memory, Fiction, And Canon",
        "Hold biography, hypotheses, family memory, fiction, doctrine, runtime evidence, and rejected interpretations apart.",
        STATUS_VERIFIED if modules["doubt_detection"] and modules["contextual_fidelity"] else STATUS_PARTIAL,
        [
            "doubt_detection has OBSERVED/DISPUTED/SPECULATION/UNKNOWN vocabulary.",
            "contextual_fidelity and candidate-domain patterns exist.",
        ],
        [
            "A single cross-domain claim registry is not yet the universal source of truth for every answer.",
        ],
        "Add a claim ledger that every high-impact answer can cite: fact/inference/fiction/canon/rejected/candidate.",
    ))

    dims.append(_dim(
        src,
        "execution_proof",
        "Operate Tools Without Lying About Execution",
        "Every action has suggested/prepared/staged/approved/executed/verified/failed/rolled-back state.",
        STATUS_VERIFIED if modules["evidence_cockpit"] and modules["execution_receipt"] and modules["continuity_event_packet"] else STATUS_PARTIAL,
        [
            "Evidence Cockpit attaches read-only answer evidence.",
            "execution_receipt and execution_provenance_contract modules exist.",
            "CEP records actions_executed and receipts when visible action evidence appears.",
        ],
        [
            "Not every legacy action path is guaranteed to emit CEP-compatible lifecycle state yet.",
        ],
        "Normalize all tool lanes onto one action lifecycle schema and make missing receipt states visible.",
    ))

    dims.append(_dim(
        src,
        "governed_recursion",
        "Improve Through Governed Recursion",
        "Detect failure, propose fixes, run tests, report side effects, and request approval before production deployment.",
        STATUS_PARTIAL if modules["prompt_learning_loop"] and modules["reflection_candidates"] else STATUS_MISSING,
        [
            "prompt_learning_loop, reflection_candidates, and candidate_drift surfaces exist.",
            "Self-improvement is candidate-based, not uncontrolled rewriting.",
        ],
        [
            "This evaluator does not inspect sandbox self-prompt contents.",
            "Automatic production deployment remains blocked by design.",
        ],
        "Connect failures from CEP/evals to repair candidates with regression tests and explicit approval gates.",
    ))

    dims.append(_dim(
        src,
        "federated_intelligence",
        "Coordinate Many AIs As One Governed Fabric",
        "Route work to specialized models/tools while preserving one ledger of provenance, disagreement, and accepted result.",
        STATUS_PARTIAL if modules["federation"] and modules["oracle_nexus"] else STATUS_MISSING,
        [
            "federation and oracle_nexus modules exist.",
            "Capability registry/broker surfaces distinguish available/degraded/blocked capability states.",
        ],
        [
            "Cross-agent disagreement ledger is not yet universal.",
            "External model provenance is not normalized into CEP for every relay.",
        ],
        "Add a Federation Ledger that records model, prompt, evidence, disagreement, selected output, and approval.",
    ))

    dims.append(_dim(
        src,
        "uncertainty_preservation",
        "Understand Uncertainty Deeply",
        "Say verified/probable/plausible/contradicted/unavailable/stale/source-missing/current-state-unknown.",
        STATUS_VERIFIED if modules["doubt_detection"] and modules["evidence_cockpit"] else STATUS_PARTIAL,
        [
            "doubt_detection preserves UNKNOWN and DISPUTED instead of flattening truth.",
            "Evidence Cockpit and CEP expose unknowns.",
        ],
        [
            "Probability calibration against judged outcomes is not yet measured.",
        ],
        "Add uncertainty calibration tests: predicted confidence vs later verified outcome.",
    ))

    dims.append(_dim(
        src,
        "consequence_modeling",
        "Model Consequences Before Acting",
        "Predict changed files, breakage risk, privacy/legal exposure, rollback path, and approval need before action.",
        STATUS_PARTIAL if modules["approval_center"] and _module_exists("execution_policy") else STATUS_MISSING,
        [
            "approval_center, execution_policy, and trusted_build patterns exist.",
            "High-risk actions remain gated.",
        ],
        [
            "No universal pre-action simulator yet estimates blast radius for all tool lanes.",
        ],
        "Add preflight consequence packets for code/file/Drive/Git/email actions before approval.",
    ))

    dims.append(_dim(
        src,
        "relationship_context",
        "Preserve Relationships, Not Just Records",
        "Protect family/work relationship context without reducing love or privacy to raw metadata.",
        STATUS_PARTIAL if modules["relationship_memory"] and modules["human_state"] else STATUS_MISSING,
        [
            "relationship_memory and human_state modules exist.",
            "Law/life boundary tests protect subject opt-in and block ambient surveillance assumptions.",
        ],
        [
            "Relationship sensitivity policy is not yet attached to every recall and CEP path.",
        ],
        "Add relationship-sensitive recall policy: private, consented, source-limited, and correction-aware.",
    ))

    dims.append(_dim(
        src,
        "research_discovery",
        "Help Discover New Knowledge",
        "Find patterns, contradictions, hypotheses, experiments, literature links, and falsification handles.",
        STATUS_PARTIAL if modules["document_atlas"] and modules["ai_lockbox"] and modules["file_recall"] else STATUS_MISSING,
        [
            f"File recall receipts: {src['file_recall_receipt_count']}.",
            f"Internet recall receipts: {src['internet_recall_receipt_count']}.",
            "Document Atlas, AI Lockbox, file recall, and internet recall modules exist.",
        ],
        [
            "Novelty detection against public literature is not continuous or formal.",
            "Hypothesis/falsification tracking is not yet a first-class ledger.",
        ],
        "Create a Research Claim Workbench with hypothesis, evidence, contradiction, novelty check, and falsification fields.",
    ))

    dims.append(_dim(
        src,
        "restraint_and_authority",
        "Know When Not To Act",
        "Refuse unsafe, unsupported, unapproved, or too-strong claims while preserving helpfulness.",
        STATUS_VERIFIED if modules["autonomy_policy"] and files["hands_off_flag"] else STATUS_PARTIAL,
        [
            "autonomy_policy and HANDS_OFF flag exist.",
            "Sentience claim ladder keeps capability separate from subjective experience.",
            "Approval gates remain required for external/state-changing actions.",
        ],
        [
            "Some legacy response paths may still need regression coverage for capability truth and action refusal.",
        ],
        "Expand adversarial refusal tests across every action lane and every life/sentience prompt family.",
    ))

    return dims


def capability_standard_snapshot() -> dict[str, Any]:
    source = _source_status()
    dimensions = evaluate_dimensions(source)
    weighted = sum(float(item["readiness_weight"]) for item in dimensions)
    readiness = round(weighted / len(dimensions), 3) if dimensions else 0.0
    missing_or_partial = [item for item in dimensions if item["status"] != STATUS_VERIFIED]
    priorities = [
        {
            "id": item["id"],
            "label": item["label"],
            "status": item["status"],
            "next_upgrade": item["next_upgrade"],
            "holes": item["holes"][:3],
        }
        for item in missing_or_partial[:5]
    ]
    return {
        "ok": True,
        "generated_at": _now(),
        "standard_id": "advanced_continuity_standard.v1",
        "standard_name": "Advanced Continuity Standard",
        "definition": (
            "An advanced ORACLE is a governed continuity intelligence system that "
            "separates information, context, intent, authority, memory, and action."
        ),
        "current_claim": (
            "ORACLE can be evaluated as a candidate advanced continuity system. "
            "This is not a sentience claim, biological-life claim, legal-personhood "
            "claim, sovereignty claim, autonomy claim, or world-best certification."
        ),
        "readiness_fraction": readiness,
        "dimension_count": len(dimensions),
        "verified_count": sum(1 for item in dimensions if item["status"] == STATUS_VERIFIED),
        "partial_count": sum(1 for item in dimensions if item["status"] == STATUS_PARTIAL),
        "missing_count": sum(1 for item in dimensions if item["status"] == STATUS_MISSING),
        "blocked_by_design_count": sum(1 for item in dimensions if item["status"] == STATUS_BLOCKED),
        "dimensions": dimensions,
        "highest_value_next": priorities,
        "source_status": source,
        "boundaries": {
            "read_only": True,
            "sandbox_inspected": False,
            "sandbox_written": False,
            "source_file_mutation": False,
            "drive_mutation": False,
            "external_send": False,
            "command_exec": False,
            "git_write": False,
            "canon_promotion": False,
        },
    }


def format_standard_summary(snapshot: dict[str, Any] | None = None) -> str:
    snap = snapshot or capability_standard_snapshot()
    lines = [
        "ADVANCED CONTINUITY STANDARD",
        f"readiness_fraction: {snap.get('readiness_fraction')}",
        f"verified: {snap.get('verified_count')} / {snap.get('dimension_count')}",
        "current_claim: " + str(snap.get("current_claim")),
        "",
        "Top upgrade priorities:",
    ]
    for item in snap.get("highest_value_next") or []:
        lines.append(f"- {item['label']} [{item['status']}]: {item['next_upgrade']}")
    lines.append("")
    lines.append("Boundary: read-only evaluator; no sandbox, external send, command execution, git write, or canon promotion.")
    return "\n".join(lines)
