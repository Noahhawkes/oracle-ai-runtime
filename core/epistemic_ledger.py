"""ORACLE Epistemic Claim Ledger.

Versioned local claim accounting for open ended knowledge expansion.

Rules:
  - Language models may propose claims.
  - Language models may not verify claims.
  - VERIFIED requires deterministic application approval and a machine receipt.
  - Contradictions coexist and link to each other.
  - Updates preserve revision history; no claim silently overwrites another.
  - Runtime state lives under Memory/ by default, which is gitignored.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import uuid
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent
DEFAULT_LEDGER_PATH = ROOT / "Memory" / "epistemic_claim_ledger.json"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))


class ClaimStatus(str, Enum):
    OBSERVED = "OBSERVED"
    VERIFIED = "VERIFIED"
    SUPPORTED = "SUPPORTED"
    DISPUTED = "DISPUTED"
    INFERENCE = "INFERENCE"
    SPECULATION = "SPECULATION"
    UNKNOWN = "UNKNOWN"
    RETRACTED = "RETRACTED"


class ApprovalState(str, Enum):
    NONE = "none"
    PROPOSED = "proposed"
    EXPLICIT = "explicit"
    PRE_AUTHORIZED = "pre_authorized"


class ActorMode(str, Enum):
    COMPANION = "COMPANION"
    BUILDER = "BUILDER"
    APPLICATION = "APPLICATION"


MODEL_ACTORS = {"model", "llm", "oracle_model", "companion_model", "builder_model"}
APPROVAL_STATES = {ApprovalState.EXPLICIT.value, ApprovalState.PRE_AUTHORIZED.value}
AUTHORIZED_APPROVERS = {"Noah", "Noah Alexander Hawkes Sr.", "application", "deterministic_policy"}
POLICY_VERSION = "EEP-0.1"
MIN_INDEPENDENT_EVIDENCE_FOR_VERIFIED = 1

ALLOWED_TRANSITIONS = {
    ClaimStatus.OBSERVED.value: {ClaimStatus.SUPPORTED.value},
    ClaimStatus.SUPPORTED.value: {ClaimStatus.VERIFIED.value},
    ClaimStatus.DISPUTED.value: {ClaimStatus.SUPPORTED.value},
    ClaimStatus.INFERENCE.value: {ClaimStatus.SUPPORTED.value},
    ClaimStatus.SPECULATION.value: {ClaimStatus.INFERENCE.value, ClaimStatus.SUPPORTED.value},
    ClaimStatus.UNKNOWN.value: {ClaimStatus.OBSERVED.value, ClaimStatus.SUPPORTED.value},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str = "claim") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _hash_payload(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _status(value: ClaimStatus | str) -> ClaimStatus:
    if isinstance(value, ClaimStatus):
        return value
    return ClaimStatus(str(value).upper())


def _approval(value: ApprovalState | str) -> ApprovalState:
    if isinstance(value, ApprovalState):
        return value
    return ApprovalState(str(value).lower())


def _mode(value: ActorMode | str) -> ActorMode:
    if isinstance(value, ActorMode):
        return value
    return ActorMode(str(value).upper())


def _curiosity_score(
    importance: float,
    uncertainty: float,
    expected_information_gain: float,
    cost_and_risk: float,
) -> float:
    return (
        max(importance, 0.0)
        * max(uncertainty, 0.0)
        * max(expected_information_gain, 0.0)
        / max(cost_and_risk, 0.01)
    )


@dataclass
class ClaimRevision:
    revision_id: str
    changed_at: str
    changed_by: str
    reason: str
    before: dict[str, Any]


@dataclass
class EpistemicClaim:
    claim_id: str
    claim_text: str
    status: str
    confidence: float
    source_ids: list[str]
    source_type: str
    scope: str
    contradiction_ids: list[str]
    created_at: str
    last_reviewed_at: str
    supersedes: str | None
    created_by: str
    approval_state: str
    revision: int = 1
    revisions: list[dict[str, Any]] = field(default_factory=list)
    importance: float = 0.5
    expected_information_gain: float = 0.5
    cost_and_risk: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def uncertainty(self) -> float:
        return max(0.0, min(1.0, 1.0 - self.confidence))

    @property
    def curiosity_score(self) -> float:
        return _curiosity_score(
            self.importance,
            self.uncertainty,
            self.expected_information_gain,
            self.cost_and_risk,
        )


class ClaimLedgerError(Exception):
    """Raised when a claim ledger operation violates epistemic policy."""


def _empty_state() -> dict[str, Any]:
    return {
        "schema_version": "epistemic_claim_ledger.v0.1",
        "claims": {},
        "evidence": {},
        "approval_tokens": {},
        "approval_receipts": {},
        "created_at": _now(),
        "updated_at": _now(),
    }


def _load(path: str | Path = DEFAULT_LEDGER_PATH) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return _empty_state()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ClaimLedgerError(f"ledger JSON is invalid: {exc}") from exc
    data.setdefault("schema_version", "epistemic_claim_ledger.v0.1")
    data.setdefault("claims", {})
    data.setdefault("evidence", {})
    data.setdefault("approval_tokens", {})
    data.setdefault("approval_receipts", {})
    data.setdefault("created_at", _now())
    data.setdefault("updated_at", _now())
    return data


def _save(state: dict[str, Any], path: str | Path = DEFAULT_LEDGER_PATH) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = _now()
    p.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _claim_from_dict(data: dict[str, Any]) -> EpistemicClaim:
    return EpistemicClaim(
        claim_id=data["claim_id"],
        claim_text=data["claim_text"],
        status=data["status"],
        confidence=float(data["confidence"]),
        source_ids=list(data.get("source_ids", [])),
        source_type=data.get("source_type", "unknown"),
        scope=data.get("scope", "unknown"),
        contradiction_ids=list(data.get("contradiction_ids", [])),
        created_at=data["created_at"],
        last_reviewed_at=data["last_reviewed_at"],
        supersedes=data.get("supersedes"),
        created_by=data.get("created_by", "unknown"),
        approval_state=data.get("approval_state", ApprovalState.NONE.value),
        revision=int(data.get("revision", 1)),
        revisions=list(data.get("revisions", [])),
        importance=float(data.get("importance", 0.5)),
        expected_information_gain=float(data.get("expected_information_gain", 0.5)),
        cost_and_risk=float(data.get("cost_and_risk", 1.0)),
    )


def _assert_mutation_allowed(actor_mode: ActorMode | str) -> None:
    if _mode(actor_mode) == ActorMode.COMPANION:
        raise ClaimLedgerError("Companion Mode may read the claim ledger but may not mutate it.")


def _assert_model_cannot_verify(created_by: str, status: ClaimStatus) -> None:
    if created_by.lower() in MODEL_ACTORS and status == ClaimStatus.VERIFIED:
        raise ClaimLedgerError("A language model may propose claims but may not mark a claim VERIFIED.")


def _receipt_valid(receipt_id: str | None) -> bool:
    if not receipt_id:
        return False
    try:
        from execution_receipt import get_receipt
        receipt = get_receipt(receipt_id)
        return bool(receipt and receipt.status == "success")
    except Exception:
        return False


def _record_revision(claim: dict[str, Any], *, changed_by: str, reason: str) -> None:
    before = {k: v for k, v in claim.items() if k != "revisions"}
    revision = ClaimRevision(
        revision_id=_new_id("rev"),
        changed_at=_now(),
        changed_by=changed_by,
        reason=reason,
        before=before,
    )
    claim.setdefault("revisions", []).append(asdict(revision))
    claim["revision"] = int(claim.get("revision", 1)) + 1


def _blocked(reason_code: str, violations: list[str], claim_id: str, current_revision: int | None) -> dict[str, Any]:
    return {
        "status": "BLOCKED",
        "reason_code": reason_code,
        "violations": violations,
        "claim_id": claim_id,
        "current_revision": current_revision,
    }


def _evidence_has_integrity(evidence: dict[str, Any]) -> bool:
    provenance = evidence.get("provenance")
    integrity = evidence.get("integrity")
    return (
        isinstance(provenance, dict)
        and bool(provenance.get("source_id"))
        and bool(provenance.get("captured_at"))
        and isinstance(integrity, dict)
        and bool(integrity.get("content_hash"))
        and bool(integrity.get("hash_algorithm"))
    )


def _evidence_scope_matches(evidence: dict[str, Any], claim: dict[str, Any]) -> bool:
    return evidence.get("scope") in {claim.get("scope"), "global", "universal"}


def _evidence_is_independent(evidence: dict[str, Any]) -> bool:
    source_type = str(evidence.get("source_type", "")).lower()
    if source_type in {"model_output", "llm_output"}:
        return False
    if source_type in {"external_agent_reported", "external_agent_output"}:
        return bool(evidence.get("independently_confirmed"))
    return True


def _has_blocking_contradiction(claim: dict[str, Any]) -> bool:
    if not claim.get("contradiction_ids"):
        return False
    dispositions = claim.get("contradiction_dispositions", {})
    return any(cid not in dispositions for cid in claim.get("contradiction_ids", []))


def record_evidence(
    *,
    evidence_text: str,
    source_id: str,
    source_type: str,
    scope: str,
    created_by: str = "application",
    independently_confirmed: bool = False,
    ledger_path: str | Path = DEFAULT_LEDGER_PATH,
) -> dict[str, Any]:
    evidence_id = _new_id("evidence")
    now = _now()
    evidence = {
        "evidence_id": evidence_id,
        "evidence_text": evidence_text,
        "source_type": source_type,
        "scope": scope,
        "created_by": created_by,
        "independently_confirmed": independently_confirmed,
        "provenance": {
            "source_id": source_id,
            "captured_at": now,
            "created_by": created_by,
        },
        "integrity": {
            "hash_algorithm": "sha256",
            "content_hash": _hash_payload({
                "evidence_text": evidence_text,
                "source_id": source_id,
                "source_type": source_type,
                "scope": scope,
            }),
        },
    }
    state = _load(ledger_path)
    state["evidence"][evidence_id] = evidence
    _save(state, ledger_path)
    return evidence


def issue_approval_token(
    *,
    claim_id: str,
    expected_revision: int,
    approved_by: str,
    target_status: ClaimStatus | str,
    ttl_seconds: int = 300,
    ledger_path: str | Path = DEFAULT_LEDGER_PATH,
) -> dict[str, Any]:
    state = _load(ledger_path)
    if claim_id not in state["claims"]:
        raise KeyError(f"claim not found: {claim_id}")
    token_id = _new_id("approval")
    now = datetime.now(timezone.utc)
    token = {
        "token_id": token_id,
        "claim_id": claim_id,
        "expected_revision": expected_revision,
        "approved_by": approved_by,
        "target_status": _status(target_status).value,
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=ttl_seconds)).isoformat(),
        "used_at": None,
    }
    token["token_hash"] = _hash_payload({k: v for k, v in token.items() if k != "token_hash"})
    state["approval_tokens"][token_id] = token
    _save(state, ledger_path)
    return token


def _make_approval_receipt(
    *,
    claim_id: str,
    previous_status: str,
    new_status: str,
    previous_revision: int,
    new_revision: int,
    approved_by: str,
    evidence_ids: list[str],
    approval_reason: str,
    claim_hash_before: str,
    claim_hash_after: str,
) -> dict[str, Any]:
    receipt = {
        "receipt_id": _new_id("receipt"),
        "operation": "approve_claim",
        "claim_id": claim_id,
        "previous_status": previous_status,
        "new_status": new_status,
        "previous_revision": previous_revision,
        "new_revision": new_revision,
        "approved_by": approved_by,
        "evidence_ids": list(evidence_ids),
        "approval_reason": approval_reason,
        "approved_at": _now(),
        "policy_version": POLICY_VERSION,
        "claim_hash_before": claim_hash_before,
        "claim_hash_after": claim_hash_after,
        "receipt_hash": "",
    }
    receipt["receipt_hash"] = _hash_payload({k: v for k, v in receipt.items() if k != "receipt_hash"})
    return receipt


def propose_claim(
    claim_text: str,
    *,
    source_ids: list[str] | None = None,
    source_type: str = "user_input",
    scope: str = "unknown",
    status: ClaimStatus | str = ClaimStatus.INFERENCE,
    confidence: float = 0.5,
    created_by: str = "model",
    actor_mode: ActorMode | str = ActorMode.BUILDER,
    ledger_path: str | Path = DEFAULT_LEDGER_PATH,
    importance: float = 0.5,
    expected_information_gain: float = 0.5,
    cost_and_risk: float = 1.0,
) -> dict[str, Any]:
    """Create a candidate claim. Models cannot create VERIFIED claims."""
    _assert_mutation_allowed(actor_mode)
    desired_status = _status(status)
    _assert_model_cannot_verify(created_by, desired_status)
    if desired_status == ClaimStatus.VERIFIED:
        raise ClaimLedgerError("Use approve_claim() with evidence receipt to verify a claim.")

    now = _now()
    claim = EpistemicClaim(
        claim_id=_new_id(),
        claim_text=claim_text.strip(),
        status=desired_status.value,
        confidence=max(0.0, min(1.0, confidence)),
        source_ids=list(source_ids or []),
        source_type=source_type,
        scope=scope,
        contradiction_ids=[],
        created_at=now,
        last_reviewed_at=now,
        supersedes=None,
        created_by=created_by,
        approval_state=ApprovalState.PROPOSED.value,
        importance=importance,
        expected_information_gain=expected_information_gain,
        cost_and_risk=cost_and_risk,
    ).to_dict()
    state = _load(ledger_path)
    state["claims"][claim["claim_id"]] = claim
    _save(state, ledger_path)
    return claim


def approve_claim(
    claim_id: str,
    *,
    approved_by: str,
    approval_reason: str,
    evidence_ids: list[str],
    expected_revision: int,
    approval_token: str,
    actor_mode: ActorMode | str = ActorMode.APPLICATION,
    ledger_path: str | Path = DEFAULT_LEDGER_PATH,
) -> dict[str, Any]:
    """Approve a claim through deterministic policy, token, evidence, and receipt gates."""
    try:
        if _mode(actor_mode) != ActorMode.APPLICATION:
            return _blocked("UNAUTHORIZED_CALLER", ["Only the application layer may call approve_claim."], claim_id, None)
    except ValueError:
        return _blocked("UNAUTHORIZED_CALLER", ["Invalid actor mode."], claim_id, None)

    state = _load(ledger_path)
    original_state = deepcopy(state)
    claim = state["claims"].get(claim_id)
    if not claim:
        return _blocked("CLAIM_NOT_FOUND", ["Claim does not exist."], claim_id, None)

    current_revision = int(claim.get("revision", 1))
    previous_status = claim.get("status", ClaimStatus.UNKNOWN.value)

    def reject(reason_code: str, violations: list[str]) -> dict[str, Any]:
        # No save: failed approvals never partially update state or create receipts.
        return _blocked(reason_code, violations, claim_id, current_revision)

    if current_revision != expected_revision:
        return reject("STALE_REVISION", [f"Expected revision {expected_revision}, found {current_revision}."])
    if previous_status == ClaimStatus.RETRACTED.value:
        return reject("RETRACTED_CLAIM", ["Retracted claims cannot return to active status."])
    if any(c.get("supersedes") == claim_id for c in state["claims"].values()):
        return reject("CLAIM_SUPERSEDED", ["Claim has already been superseded by a newer claim."])
    if approved_by not in AUTHORIZED_APPROVERS:
        return reject("UNAUTHORIZED_APPROVER", [f"{approved_by!r} is not an authorized human sovereign or policy authority."])

    token = state["approval_tokens"].get(approval_token)
    if not token:
        return reject("INVALID_APPROVAL_TOKEN", ["Approval token does not exist."])
    token_violations = []
    now = datetime.now(timezone.utc)
    try:
        expires_at = _parse_time(token.get("expires_at", ""))
    except Exception:
        expires_at = now - timedelta(seconds=1)
    if token.get("used_at"):
        token_violations.append("Approval token has already been used.")
    if expires_at <= now:
        token_violations.append("Approval token is expired.")
    if token.get("claim_id") != claim_id:
        token_violations.append("Approval token is bound to another claim.")
    if int(token.get("expected_revision", -1)) != expected_revision:
        token_violations.append("Approval token revision binding does not match expected_revision.")
    if token.get("approved_by") != approved_by:
        token_violations.append("Approval token approver binding does not match approved_by.")
    target_status = token.get("target_status")
    if target_status not in {status.value for status in ClaimStatus}:
        token_violations.append("Approval token target status is invalid.")
    if token_violations:
        return reject("INVALID_APPROVAL_TOKEN", token_violations)

    allowed_targets = ALLOWED_TRANSITIONS.get(previous_status, set())
    if target_status not in allowed_targets:
        return reject("PROHIBITED_TRANSITION", [f"{previous_status} -> {target_status} is not an allowed direct transition."])

    if not evidence_ids:
        return reject("MISSING_EVIDENCE", ["At least one evidence_id is required."])

    evidence_records = []
    evidence_violations = []
    independent_count = 0
    for evidence_id in evidence_ids:
        evidence = state["evidence"].get(evidence_id)
        if not evidence:
            evidence_violations.append(f"Evidence record does not exist: {evidence_id}")
            continue
        evidence_records.append(evidence)
        if not _evidence_has_integrity(evidence):
            evidence_violations.append(f"Evidence lacks provenance or integrity metadata: {evidence_id}")
        if not _evidence_scope_matches(evidence, claim):
            evidence_violations.append(f"Evidence scope does not match claim scope: {evidence_id}")
        if not _evidence_is_independent(evidence):
            evidence_violations.append(f"Evidence is not independently verified: {evidence_id}")
        else:
            independent_count += 1
    if evidence_violations:
        return reject("INVALID_EVIDENCE", evidence_violations)

    if target_status == ClaimStatus.VERIFIED.value:
        if independent_count < MIN_INDEPENDENT_EVIDENCE_FOR_VERIFIED:
            return reject("INSUFFICIENT_EVIDENCE", ["VERIFIED requires independent evidence defined by policy."])
        if _has_blocking_contradiction(claim):
            return reject("UNRESOLVED_CONTRADICTION", ["Blocking contradiction lacks explicit disposition."])

    if previous_status == ClaimStatus.DISPUTED.value and target_status == ClaimStatus.SUPPORTED.value:
        if _has_blocking_contradiction(claim):
            return reject("UNRESOLVED_CONTRADICTION", ["DISPUTED -> SUPPORTED requires contradiction disposition."])

    new_state = deepcopy(original_state)
    claim = new_state["claims"][claim_id]
    claim_hash_before = _hash_payload(claim)
    _record_revision(claim, changed_by=approved_by, reason=f"approve_claim: {approval_reason}")
    previous_revision = current_revision
    new_revision = int(claim.get("revision", previous_revision + 1))
    claim["status"] = target_status
    if target_status == ClaimStatus.VERIFIED.value:
        claim["confidence"] = max(float(claim.get("confidence", 0.0)), 0.99)
    elif target_status == ClaimStatus.SUPPORTED.value:
        claim["confidence"] = max(float(claim.get("confidence", 0.0)), 0.75)
    elif target_status == ClaimStatus.OBSERVED.value:
        claim["confidence"] = max(float(claim.get("confidence", 0.0)), 0.5)
    claim["approval_state"] = ApprovalState.EXPLICIT.value
    claim["last_reviewed_at"] = _now()
    for evidence_id in evidence_ids:
        marker = f"evidence:{evidence_id}"
        if marker not in claim.setdefault("source_ids", []):
            claim["source_ids"].append(marker)
    claim_hash_after = _hash_payload(claim)
    receipt = _make_approval_receipt(
        claim_id=claim_id,
        previous_status=previous_status,
        new_status=target_status,
        previous_revision=previous_revision,
        new_revision=new_revision,
        approved_by=approved_by,
        evidence_ids=evidence_ids,
        approval_reason=approval_reason,
        claim_hash_before=claim_hash_before,
        claim_hash_after=claim_hash_after,
    )
    claim.setdefault("source_ids", []).append(f"approval_receipt:{receipt['receipt_id']}")
    new_state["approval_receipts"][receipt["receipt_id"]] = receipt
    new_state["approval_tokens"][approval_token]["used_at"] = _now()
    _save(new_state, ledger_path)
    result = dict(claim)
    result["approval_receipt"] = receipt
    return result


def dispute_claim(
    claim_id: str,
    *,
    reason: str,
    disputed_by: str = "application",
    actor_mode: ActorMode | str = ActorMode.BUILDER,
    ledger_path: str | Path = DEFAULT_LEDGER_PATH,
) -> dict[str, Any]:
    _assert_mutation_allowed(actor_mode)
    state = _load(ledger_path)
    claim = state["claims"].get(claim_id)
    if not claim:
        raise KeyError(f"claim not found: {claim_id}")
    _record_revision(claim, changed_by=disputed_by, reason=f"dispute_claim: {reason}")
    claim["status"] = ClaimStatus.DISPUTED.value
    claim["last_reviewed_at"] = _now()
    _save(state, ledger_path)
    return claim


def retract_claim(
    claim_id: str,
    *,
    reason: str,
    retracted_by: str = "application",
    actor_mode: ActorMode | str = ActorMode.BUILDER,
    ledger_path: str | Path = DEFAULT_LEDGER_PATH,
) -> dict[str, Any]:
    _assert_mutation_allowed(actor_mode)
    state = _load(ledger_path)
    claim = state["claims"].get(claim_id)
    if not claim:
        raise KeyError(f"claim not found: {claim_id}")
    _record_revision(claim, changed_by=retracted_by, reason=f"retract_claim: {reason}")
    claim["status"] = ClaimStatus.RETRACTED.value
    claim["last_reviewed_at"] = _now()
    _save(state, ledger_path)
    return claim


def link_contradiction(
    claim_id: str,
    other_claim_id: str,
    *,
    linked_by: str = "application",
    actor_mode: ActorMode | str = ActorMode.BUILDER,
    ledger_path: str | Path = DEFAULT_LEDGER_PATH,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _assert_mutation_allowed(actor_mode)
    if claim_id == other_claim_id:
        raise ClaimLedgerError("a claim cannot contradict itself")
    state = _load(ledger_path)
    claim = state["claims"].get(claim_id)
    other = state["claims"].get(other_claim_id)
    if not claim or not other:
        raise KeyError("both contradiction claims must exist")
    for left, right in ((claim, other_claim_id), (other, claim_id)):
        if right not in left.setdefault("contradiction_ids", []):
            _record_revision(left, changed_by=linked_by, reason="link_contradiction")
            left["contradiction_ids"].append(right)
            left["last_reviewed_at"] = _now()
            if left["status"] not in {ClaimStatus.RETRACTED.value, ClaimStatus.UNKNOWN.value}:
                left["status"] = ClaimStatus.DISPUTED.value
    _save(state, ledger_path)
    return claim, other


def supersede_claim(
    old_claim_id: str,
    new_claim_text: str,
    *,
    source_ids: list[str] | None = None,
    source_type: str = "revision",
    scope: str = "unknown",
    status: ClaimStatus | str = ClaimStatus.SUPPORTED,
    confidence: float = 0.75,
    created_by: str = "application",
    actor_mode: ActorMode | str = ActorMode.BUILDER,
    ledger_path: str | Path = DEFAULT_LEDGER_PATH,
) -> dict[str, Any]:
    _assert_mutation_allowed(actor_mode)
    state = _load(ledger_path)
    old = state["claims"].get(old_claim_id)
    if not old:
        raise KeyError(f"claim not found: {old_claim_id}")
    new_claim = propose_claim(
        new_claim_text,
        source_ids=source_ids,
        source_type=source_type,
        scope=scope,
        status=status,
        confidence=confidence,
        created_by=created_by,
        actor_mode=actor_mode,
        ledger_path=ledger_path,
    )
    state = _load(ledger_path)
    old = state["claims"][old_claim_id]
    _record_revision(old, changed_by=created_by, reason=f"superseded_by:{new_claim['claim_id']}")
    old["status"] = ClaimStatus.RETRACTED.value
    old["last_reviewed_at"] = _now()
    state["claims"][new_claim["claim_id"]]["supersedes"] = old_claim_id
    _save(state, ledger_path)
    return state["claims"][new_claim["claim_id"]]


def get_claim(claim_id: str, *, ledger_path: str | Path = DEFAULT_LEDGER_PATH) -> dict[str, Any] | None:
    claim = _load(ledger_path)["claims"].get(claim_id)
    if not claim:
        return None
    data = dict(claim)
    data["provenance"] = {
        "source_ids": list(data.get("source_ids", [])),
        "source_type": data.get("source_type", "unknown"),
        "status": data.get("status", ClaimStatus.UNKNOWN.value),
    }
    data["curiosity_score"] = _claim_from_dict(data).curiosity_score
    return data


def get_claim_revision(
    claim_id: str,
    revision: int,
    *,
    ledger_path: str | Path = DEFAULT_LEDGER_PATH,
) -> dict[str, Any] | None:
    claim = _load(ledger_path)["claims"].get(claim_id)
    if not claim:
        return None
    if int(claim.get("revision", 1)) == revision:
        return dict(claim)
    for event in claim.get("revisions", []):
        before = event.get("before", {})
        if int(before.get("revision", 1)) == revision:
            return dict(before)
    return None


def search_claims(
    query: str = "",
    *,
    status: ClaimStatus | str | None = None,
    ledger_path: str | Path = DEFAULT_LEDGER_PATH,
) -> list[dict[str, Any]]:
    state = _load(ledger_path)
    q = query.lower().strip()
    desired = _status(status).value if status is not None else None
    results = []
    for claim_id, claim in state["claims"].items():
        if q and q not in claim.get("claim_text", "").lower():
            continue
        if desired and claim.get("status") != desired:
            continue
        enriched = get_claim(claim_id, ledger_path=ledger_path)
        if enriched:
            results.append(enriched)
    return sorted(results, key=lambda c: c.get("last_reviewed_at", ""), reverse=True)


def get_open_questions(*, ledger_path: str | Path = DEFAULT_LEDGER_PATH) -> list[dict[str, Any]]:
    questions = []
    for claim in search_claims(ledger_path=ledger_path):
        if claim["status"] in {
            ClaimStatus.UNKNOWN.value,
            ClaimStatus.SPECULATION.value,
            ClaimStatus.INFERENCE.value,
            ClaimStatus.DISPUTED.value,
        } or claim.get("contradiction_ids"):
            questions.append({
                "claim_id": claim["claim_id"],
                "question": f"What evidence would strengthen, weaken, or resolve: {claim['claim_text']}",
                "priority": claim["curiosity_score"],
                "status": claim["status"],
                "source_ids": claim["source_ids"],
                "contradiction_ids": claim["contradiction_ids"],
            })
    return sorted(questions, key=lambda item: item["priority"], reverse=True)


def _smoke_test() -> int:
    failures = 0

    def check(label: str, passed: bool, detail: str = "") -> None:
        nonlocal failures
        tag = "PASS" if passed else "FAIL"
        print(f"  [{tag}] {label}" + (f" -- {detail}" if detail and not passed else ""))
        if not passed:
            failures += 1

    print("=" * 60)
    print("ORACLE Epistemic Claim Ledger -- Smoke Tests")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "claim_ledger.json"

        try:
            propose_claim(
                "A model is trying to verify itself.",
                status=ClaimStatus.VERIFIED,
                created_by="model",
                ledger_path=ledger,
            )
            check("model proposed claim cannot become VERIFIED automatically", False)
        except ClaimLedgerError:
            check("model proposed claim cannot become VERIFIED automatically", True)

        unsupported = propose_claim(
            "ORACLE can expand knowledge without omniscience.",
            status=ClaimStatus.INFERENCE,
            confidence=0.45,
            source_ids=[],
            source_type="model_output",
            ledger_path=ledger,
        )
        check("unsupported statements remain INFERENCE", unsupported["status"] == ClaimStatus.INFERENCE.value)

        unknown = propose_claim(
            "The next unknown variable has not been measured.",
            status=ClaimStatus.UNKNOWN,
            confidence=0.0,
            source_ids=[],
            source_type="absence_of_evidence",
            ledger_path=ledger,
        )
        check("unsupported unknown remains UNKNOWN", unknown["status"] == ClaimStatus.UNKNOWN.value)

        c1 = propose_claim(
            "The signal originated from source A.",
            source_ids=["source_a"],
            source_type="observation",
            ledger_path=ledger,
        )
        c2 = propose_claim(
            "The signal did not originate from source A.",
            source_ids=["source_b"],
            source_type="observation",
            ledger_path=ledger,
        )
        link_contradiction(c1["claim_id"], c2["claim_id"], ledger_path=ledger)
        c1r = get_claim(c1["claim_id"], ledger_path=ledger) or {}
        c2r = get_claim(c2["claim_id"], ledger_path=ledger) or {}
        check("two contradictory claims coexist", bool(c1r and c2r))
        check("contradictory claims reference each other",
              c2["claim_id"] in c1r.get("contradiction_ids", []) and c1["claim_id"] in c2r.get("contradiction_ids", []))

        newer = supersede_claim(
            unsupported["claim_id"],
            "ORACLE can expand knowledge while preserving epistemic labels.",
            source_ids=["source_c"],
            ledger_path=ledger,
        )
        old = get_claim(unsupported["claim_id"], ledger_path=ledger) or {}
        check("superseded claim remains in revision history", old.get("revisions") and newer.get("supersedes") == unsupported["claim_id"])

        try:
            propose_claim(
                "Companion should not mutate this.",
                actor_mode=ActorMode.COMPANION,
                ledger_path=ledger,
            )
            check("Companion Mode cannot mutate the ledger", False)
        except ClaimLedgerError:
            check("Companion Mode cannot mutate the ledger", True)

        supported = propose_claim(
            "The deterministic approval contract exists.",
            status=ClaimStatus.SUPPORTED,
            confidence=0.8,
            source_ids=["design_note"],
            source_type="human_observation",
            scope="approval_contract",
            created_by="application",
            ledger_path=ledger,
        )
        evidence = record_evidence(
            evidence_text="Smoke test observed deterministic approval contract behavior.",
            source_id="smoke_test",
            source_type="deterministic_test",
            scope="approval_contract",
            ledger_path=ledger,
        )

        token = issue_approval_token(
            claim_id=supported["claim_id"],
            expected_revision=supported["revision"],
            approved_by="Noah",
            target_status=ClaimStatus.VERIFIED,
            ledger_path=ledger,
        )

        r = approve_claim(
            supported["claim_id"],
            approved_by="Noah",
            approval_reason="verified by deterministic smoke evidence",
            evidence_ids=[evidence["evidence_id"]],
            expected_revision=supported["revision"],
            approval_token=token["token_id"],
            actor_mode=ActorMode.BUILDER,
            ledger_path=ledger,
        )
        check("Model/Builder cannot call approve_claim directly", r["status"] == "BLOCKED" and r["reason_code"] == "UNAUTHORIZED_CALLER", str(r))

        expired = issue_approval_token(
            claim_id=supported["claim_id"],
            expected_revision=supported["revision"],
            approved_by="Noah",
            target_status=ClaimStatus.VERIFIED,
            ttl_seconds=-1,
            ledger_path=ledger,
        )
        r = approve_claim(
            supported["claim_id"],
            approved_by="Noah",
            approval_reason="expired token should fail",
            evidence_ids=[evidence["evidence_id"]],
            expected_revision=supported["revision"],
            approval_token=expired["token_id"],
            ledger_path=ledger,
        )
        check("Expired approval token is blocked", r["status"] == "BLOCKED" and r["reason_code"] == "INVALID_APPROVAL_TOKEN", str(r))

        other = propose_claim(
            "Another claim for token binding.",
            status=ClaimStatus.SUPPORTED,
            source_ids=["other"],
            source_type="human_observation",
            scope="approval_contract",
            created_by="application",
            ledger_path=ledger,
        )
        wrong_claim_token = issue_approval_token(
            claim_id=other["claim_id"],
            expected_revision=other["revision"],
            approved_by="Noah",
            target_status=ClaimStatus.VERIFIED,
            ledger_path=ledger,
        )
        r = approve_claim(
            supported["claim_id"],
            approved_by="Noah",
            approval_reason="wrong claim token should fail",
            evidence_ids=[evidence["evidence_id"]],
            expected_revision=supported["revision"],
            approval_token=wrong_claim_token["token_id"],
            ledger_path=ledger,
        )
        check("Token for another claim is blocked", r["status"] == "BLOCKED" and r["reason_code"] == "INVALID_APPROVAL_TOKEN", str(r))

        stale_token = issue_approval_token(
            claim_id=supported["claim_id"],
            expected_revision=supported["revision"],
            approved_by="Noah",
            target_status=ClaimStatus.VERIFIED,
            ledger_path=ledger,
        )
        r = approve_claim(
            supported["claim_id"],
            approved_by="Noah",
            approval_reason="stale revision should fail",
            evidence_ids=[evidence["evidence_id"]],
            expected_revision=supported["revision"] + 1,
            approval_token=stale_token["token_id"],
            ledger_path=ledger,
        )
        check("Stale expected_revision is blocked", r["status"] == "BLOCKED" and r["reason_code"] == "STALE_REVISION", str(r))

        missing_evidence_token = issue_approval_token(
            claim_id=supported["claim_id"],
            expected_revision=supported["revision"],
            approved_by="Noah",
            target_status=ClaimStatus.VERIFIED,
            ledger_path=ledger,
        )
        r = approve_claim(
            supported["claim_id"],
            approved_by="Noah",
            approval_reason="missing evidence should fail",
            evidence_ids=["missing_evidence"],
            expected_revision=supported["revision"],
            approval_token=missing_evidence_token["token_id"],
            ledger_path=ledger,
        )
        check("Missing evidence is blocked", r["status"] == "BLOCKED" and r["reason_code"] == "INVALID_EVIDENCE", str(r))

        model_evidence = record_evidence(
            evidence_text="A model said this is true.",
            source_id="model_output_1",
            source_type="model_output",
            scope="approval_contract",
            ledger_path=ledger,
        )
        model_evidence_token = issue_approval_token(
            claim_id=supported["claim_id"],
            expected_revision=supported["revision"],
            approved_by="Noah",
            target_status=ClaimStatus.VERIFIED,
            ledger_path=ledger,
        )
        before_failed = _hash_payload(_load(ledger))
        r = approve_claim(
            supported["claim_id"],
            approved_by="Noah",
            approval_reason="model evidence should fail",
            evidence_ids=[model_evidence["evidence_id"]],
            expected_revision=supported["revision"],
            approval_token=model_evidence_token["token_id"],
            ledger_path=ledger,
        )
        after_failed = _hash_payload(_load(ledger))
        check("Model output as sole evidence is blocked", r["status"] == "BLOCKED" and r["reason_code"] == "INVALID_EVIDENCE", str(r))
        check("Failed approval leaves the ledger unchanged", before_failed == after_failed, str(r))

        disputed = propose_claim(
            "A disputed claim cannot be verified while blocked.",
            status=ClaimStatus.SUPPORTED,
            source_ids=["dispute_a"],
            source_type="human_observation",
            scope="approval_contract",
            created_by="application",
            ledger_path=ledger,
        )
        contradictor = propose_claim(
            "A disputed claim can be verified while blocked.",
            status=ClaimStatus.SUPPORTED,
            source_ids=["dispute_b"],
            source_type="human_observation",
            scope="approval_contract",
            created_by="application",
            ledger_path=ledger,
        )
        link_contradiction(disputed["claim_id"], contradictor["claim_id"], ledger_path=ledger)
        disputed_now = get_claim(disputed["claim_id"], ledger_path=ledger) or {}
        contradiction_token = issue_approval_token(
            claim_id=disputed["claim_id"],
            expected_revision=disputed_now["revision"],
            approved_by="Noah",
            target_status=ClaimStatus.SUPPORTED,
            ledger_path=ledger,
        )
        r = approve_claim(
            disputed["claim_id"],
            approved_by="Noah",
            approval_reason="unresolved contradiction should fail",
            evidence_ids=[evidence["evidence_id"]],
            expected_revision=disputed_now["revision"],
            approval_token=contradiction_token["token_id"],
            ledger_path=ledger,
        )
        check("Unresolved blocking contradiction is blocked", r["status"] == "BLOCKED" and r["reason_code"] == "UNRESOLVED_CONTRADICTION", str(r))

        valid_token = issue_approval_token(
            claim_id=supported["claim_id"],
            expected_revision=supported["revision"],
            approved_by="Noah",
            target_status=ClaimStatus.VERIFIED,
            ledger_path=ledger,
        )
        verified = approve_claim(
            supported["claim_id"],
            approved_by="Noah",
            approval_reason="verified by deterministic smoke evidence",
            evidence_ids=[evidence["evidence_id"]],
            expected_revision=supported["revision"],
            approval_token=valid_token["token_id"],
            actor_mode=ActorMode.APPLICATION,
            ledger_path=ledger,
        )
        receipt = verified.get("approval_receipt", {})
        check("Valid SUPPORTED to VERIFIED transition succeeds", verified.get("status") == ClaimStatus.VERIFIED.value, str(verified))
        check("Successful approval creates a new revision and receipt",
              verified.get("revision") == supported["revision"] + 1 and receipt.get("operation") == "approve_claim", str(verified))
        previous = get_claim_revision(supported["claim_id"], supported["revision"], ledger_path=ledger)
        check("Previous revision remains retrievable", previous and previous.get("status") == ClaimStatus.SUPPORTED.value, str(previous))

        r = approve_claim(
            supported["claim_id"],
            approved_by="Noah",
            approval_reason="token reuse should fail",
            evidence_ids=[evidence["evidence_id"]],
            expected_revision=verified["revision"],
            approval_token=valid_token["token_id"],
            actor_mode=ActorMode.APPLICATION,
            ledger_path=ledger,
        )
        check("Repeated use of the same approval token is blocked", r["status"] == "BLOCKED" and r["reason_code"] == "INVALID_APPROVAL_TOKEN", str(r))

        retrieved = get_claim(supported["claim_id"], ledger_path=ledger) or {}
        check("retrieved claim includes provenance", "provenance" in retrieved and retrieved["provenance"].get("source_ids"), str(retrieved))
        check("retrieved claim includes status", retrieved.get("status") == ClaimStatus.VERIFIED.value, str(retrieved))

        questions = get_open_questions(ledger_path=ledger)
        check("open questions include priority score", bool(questions) and all("priority" in q for q in questions), str(questions))

    total = 22
    passed = total - failures
    print(f"{'='*60}")
    print(f"Result: {passed}/{total} passed")
    print(f"STATUS: {'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    print(f"{'='*60}\n")
    return failures


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ORACLE Epistemic Claim Ledger")
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()

    if args.smoke_test:
        raise SystemExit(_smoke_test())

    print("Usage: python core/epistemic_ledger.py --smoke-test")
