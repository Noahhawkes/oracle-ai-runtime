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
import json
import sys
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str = "claim") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


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
    approval_state: ApprovalState | str,
    receipt_id: str,
    approved_by: str = "application",
    actor_mode: ActorMode | str = ActorMode.APPLICATION,
    ledger_path: str | Path = DEFAULT_LEDGER_PATH,
) -> dict[str, Any]:
    """Promote a claim to VERIFIED only with explicit approval and a valid receipt."""
    _assert_mutation_allowed(actor_mode)
    if _mode(actor_mode) != ActorMode.APPLICATION:
        raise ClaimLedgerError("Only the deterministic application layer may assign VERIFIED.")
    if _approval(approval_state).value not in APPROVAL_STATES:
        raise ClaimLedgerError("VERIFIED requires explicit or pre-authorized approval.")
    if not _receipt_valid(receipt_id):
        raise ClaimLedgerError("VERIFIED requires a valid machine generated execution receipt.")

    state = _load(ledger_path)
    claim = state["claims"].get(claim_id)
    if not claim:
        raise KeyError(f"claim not found: {claim_id}")
    _record_revision(claim, changed_by=approved_by, reason="approve_claim")
    claim["status"] = ClaimStatus.VERIFIED.value
    claim["confidence"] = max(float(claim.get("confidence", 0.0)), 0.99)
    claim["approval_state"] = _approval(approval_state).value
    claim["last_reviewed_at"] = _now()
    claim.setdefault("source_ids", []).append(f"receipt:{receipt_id}")
    _save(state, ledger_path)
    return claim


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

        try:
            approve_claim(
                c1["claim_id"],
                approval_state=ApprovalState.EXPLICIT,
                receipt_id="missing_receipt",
                actor_mode=ActorMode.BUILDER,
                ledger_path=ledger,
            )
            check("Builder Mode cannot claim completion without a receipt", False)
        except ClaimLedgerError:
            check("Builder Mode cannot claim completion without a receipt", True)

        try:
            import execution_receipt
            receipt = execution_receipt.read_file(__file__)
            verified = approve_claim(
                c1["claim_id"],
                approval_state=ApprovalState.EXPLICIT,
                receipt_id=receipt.operation_id,
                actor_mode=ActorMode.APPLICATION,
                ledger_path=ledger,
            )
            check("application approval with receipt can verify claim", verified["status"] == ClaimStatus.VERIFIED.value)
        except Exception as exc:
            check("application approval with receipt can verify claim", False, str(exc))

        retrieved = get_claim(c1["claim_id"], ledger_path=ledger) or {}
        check("retrieved claim includes provenance", "provenance" in retrieved and retrieved["provenance"].get("source_ids"), str(retrieved))
        check("retrieved claim includes status", retrieved.get("status") == ClaimStatus.VERIFIED.value, str(retrieved))

        questions = get_open_questions(ledger_path=ledger)
        check("open questions include priority score", bool(questions) and all("priority" in q for q in questions), str(questions))

    total = 12
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
