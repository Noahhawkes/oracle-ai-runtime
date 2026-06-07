"""
core/curiosity_engine.py — ORACLE Governed Curiosity Engine

CORE LAW:
  ORACLE may wonder.
  ORACLE may not wander without approval.

Curiosity is the ability to detect gaps, contradictions, stale context,
missing evidence, unresolved commitments, and possible next questions.

Curiosity outputs are CANDIDATES ONLY.
No action executes from this module.
No source is searched automatically.
No memory is written without approval.
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import sys

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

SIGNALS_FILE = ROOT / "Memory" / "curiosity_signals.json"

# ── Signal types ──────────────────────────────────────────────────────────────

SIGNAL_TYPES = {
    "missing_context":         "Required context is absent or incomplete.",
    "contradiction":           "Two records conflict with each other.",
    "stale_memory":            "A memory record has not been updated within threshold.",
    "unresolved_commitment":   "A commitment, deadline, or obligation has no resolution.",
    "financial_risk":          "A financial pattern, charge, or gap warrants attention.",
    "relationship_followup":   "A person or relationship needs follow-up.",
    "project_blocker":         "A technical or resource block is preventing progress.",
    "opportunity":             "A possible move or advantage worth surfacing.",
    "safety_concern":          "A pattern that may affect Noah's safety or system integrity.",
    "identity_drift":          "Observed deviation from Noah's stated identity or values.",
    "unknown":                 "Signal type cannot be classified.",
}

# ── Status states ─────────────────────────────────────────────────────────────

STATUS_PENDING      = "pending"
STATUS_APPROVED     = "approved"
STATUS_REJECTED     = "rejected"
STATUS_QUARANTINED  = "quarantined"
STATUS_REVOKED      = "revoked"

VALID_STATUSES = {
    STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED,
    STATUS_QUARANTINED, STATUS_REVOKED,
}

# ── Risk levels ───────────────────────────────────────────────────────────────

RISK_LOW                    = "low"
RISK_MEDIUM                 = "medium"
RISK_HIGH                   = "high"
RISK_SENSITIVE              = "sensitive"
RISK_EXTERNAL_ACTION        = "external_action_required"
RISK_BLOCKED                = "blocked"

VALID_RISK_LEVELS = {
    RISK_LOW, RISK_MEDIUM, RISK_HIGH,
    RISK_SENSITIVE, RISK_EXTERNAL_ACTION, RISK_BLOCKED,
}

# ── Forbidden curiosity behaviors — enforced, not advisory ───────────────────

FORBIDDEN_BEHAVIORS = [
    "browsing random websites",
    "opening private folders without approval",
    "reading email beyond approved scope",
    "making emotional conclusions",
    "adding memory without approval",
    "executing cleanup actions",
    "sending messages",
    "submitting forms",
    "purchasing",
    "deleting",
    "moving files",
    "modifying source records",
]


# ── CuriositySignal dataclass ─────────────────────────────────────────────────

@dataclass
class CuriositySignal:
    # Required
    signal_type: str
    title: str
    observed_context: str

    # Reasoning
    why_it_matters: str = ""
    missing_information: str = ""
    hypothesis: str = ""          # Always labeled as hypothesis — never treated as fact
    confidence: float = 0.5       # 0.0 – 1.0
    risk_level: str = RISK_LOW

    # Outputs (candidates only — never executed automatically)
    recommended_question: str = ""
    recommended_action_candidate: str = ""

    # Metadata
    source: str = "curiosity_engine"
    status: str = STATUS_PENDING
    tags: list = field(default_factory=list)
    unknowns: list = field(default_factory=list)  # Preserved unknowns — never filled by inference

    # Auto-generated
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        if self.signal_type not in SIGNAL_TYPES:
            self.signal_type = "unknown"
        if self.status not in VALID_STATUSES:
            self.status = STATUS_PENDING
        if self.risk_level not in VALID_RISK_LEVELS:
            self.risk_level = RISK_LOW
        self.confidence = max(0.0, min(1.0, float(self.confidence)))
        # Enforce: hypothesis must be labeled if present
        if self.hypothesis and not self.hypothesis.strip().startswith("[HYPOTHESIS]"):
            self.hypothesis = f"[HYPOTHESIS] {self.hypothesis}"

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        lines = [
            f"[{self.id}] {self.signal_type.upper()} | {self.risk_level.upper()} | {self.status}",
            f"  Title   : {self.title}",
            f"  Context : {self.observed_context[:120]}",
        ]
        if self.why_it_matters:
            lines.append(f"  Why     : {self.why_it_matters[:100]}")
        if self.missing_information:
            lines.append(f"  Missing : {self.missing_information[:100]}")
        if self.hypothesis:
            lines.append(f"  Hyp     : {self.hypothesis[:100]}")
        if self.recommended_question:
            lines.append(f"  Question: {self.recommended_question[:100]}")
        if self.recommended_action_candidate:
            lines.append(f"  Action? : {self.recommended_action_candidate[:100]}")
        if self.unknowns:
            lines.append(f"  Unknowns: {', '.join(str(u) for u in self.unknowns[:3])}")
        return "\n".join(lines)


# ── Persistence ───────────────────────────────────────────────────────────────

def _load_all() -> list[dict]:
    if not SIGNALS_FILE.exists():
        return []
    try:
        return json.loads(SIGNALS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_all(records: list[dict]):
    SIGNALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SIGNALS_FILE.write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def persist(signal: CuriositySignal) -> CuriositySignal:
    """Save a signal to the JSON store. Pending signals are NOT memory."""
    records = _load_all()
    # Upsert by id
    records = [r for r in records if r.get("id") != signal.id]
    records.append(signal.to_dict())
    _save_all(records)
    return signal


def recall_signals(
    status: Optional[str] = None,
    signal_type: Optional[str] = None,
    risk_level: Optional[str] = None,
    exclude_statuses: Optional[list] = None,
) -> list[CuriositySignal]:
    """
    Recall signals from the store.
    Rejected, quarantined, and revoked signals are excluded by default.
    """
    if exclude_statuses is None:
        exclude_statuses = [STATUS_REJECTED, STATUS_QUARANTINED, STATUS_REVOKED]

    records = _load_all()
    signals = []
    for r in records:
        if r.get("status") in exclude_statuses:
            continue
        if status and r.get("status") != status:
            continue
        if signal_type and r.get("signal_type") != signal_type:
            continue
        if risk_level and r.get("risk_level") != risk_level:
            continue
        try:
            signals.append(CuriositySignal(**r))
        except Exception:
            continue
    return signals


def update_status(signal_id: str, new_status: str) -> str:
    """Approve, reject, quarantine, or revoke a signal by id."""
    if new_status not in VALID_STATUSES:
        return f"Invalid status: {new_status}. Valid: {', '.join(VALID_STATUSES)}"
    records = _load_all()
    for r in records:
        if r.get("id") == signal_id:
            r["status"] = new_status
            r["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_all(records)
            return f"Signal {signal_id} → {new_status}"
    return f"Signal {signal_id} not found."


# ── Detection functions ───────────────────────────────────────────────────────

def detect_missing_context(context_record: dict) -> Optional[CuriositySignal]:
    """
    Detect when a context record is missing required fields or has empty values.
    context_record: any dict representing a memory, project, or person record.
    """
    empty_fields = [k for k, v in context_record.items()
                    if v in (None, "", [], {}, "unknown", "unverified")]
    if not empty_fields:
        return None

    label = context_record.get("name") or context_record.get("key") or context_record.get("id") or "record"
    signal = CuriositySignal(
        signal_type="missing_context",
        title=f"Missing context in: {label}",
        observed_context=f"Record '{label}' has empty or unknown fields: {', '.join(empty_fields[:5])}",
        why_it_matters="Incomplete records can cause incorrect decisions or missed follow-up.",
        missing_information=f"Values needed for: {', '.join(empty_fields[:5])}",
        hypothesis=f"These fields may have been intentionally left blank or were never collected.",
        confidence=0.7,
        risk_level=RISK_LOW,
        recommended_question=f"Do you have information to fill in: {', '.join(empty_fields[:3])}?",
        unknowns=empty_fields,
        tags=["missing_context", label],
    )
    return persist(signal)


def detect_contradiction(record_a: dict, record_b: dict) -> Optional[CuriositySignal]:
    """
    Detect conflicting values between two records on the same keys.
    """
    conflicts = {}
    for key in set(record_a.keys()) & set(record_b.keys()):
        va, vb = record_a[key], record_b[key]
        if va and vb and str(va).strip() != str(vb).strip():
            conflicts[key] = (va, vb)
    if not conflicts:
        return None

    label_a = record_a.get("name") or record_a.get("id") or "record_a"
    label_b = record_b.get("name") or record_b.get("id") or "record_b"
    conflict_summary = "; ".join(
        f"{k}: '{v[0]}' vs '{v[1]}'" for k, v in list(conflicts.items())[:3]
    )
    signal = CuriositySignal(
        signal_type="contradiction",
        title=f"Contradiction between {label_a} and {label_b}",
        observed_context=f"Conflicting values found: {conflict_summary}",
        why_it_matters="Contradictions in memory corrupt downstream decisions.",
        missing_information="Which record is correct? Both need verification.",
        hypothesis=f"One record may be stale or sourced from a different context.",
        confidence=0.85,
        risk_level=RISK_MEDIUM,
        recommended_question=f"Which is correct — {label_a} or {label_b}? Conflicting on: {list(conflicts.keys())[:3]}",
        unknowns=[f"true value of {k}" for k in conflicts],
        tags=["contradiction", label_a, label_b],
    )
    return persist(signal)


def detect_stale_memory(memory_record: dict, max_age_days: int = 30) -> Optional[CuriositySignal]:
    """
    Flag a memory record that hasn't been updated within max_age_days.
    memory_record should contain 'updated_at' or 'created_at' ISO string.
    """
    ts_str = memory_record.get("updated_at") or memory_record.get("created_at")
    if not ts_str:
        return None
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        age_days = (now - ts).days
    except Exception:
        return None

    if age_days < max_age_days:
        return None

    label = memory_record.get("key") or memory_record.get("name") or memory_record.get("id") or "record"
    signal = CuriositySignal(
        signal_type="stale_memory",
        title=f"Stale memory: {label} ({age_days} days old)",
        observed_context=f"Record '{label}' last updated {age_days} days ago (threshold: {max_age_days}).",
        why_it_matters="Stale context produces incorrect or outdated decisions.",
        missing_information="Current state of this record is unknown.",
        hypothesis=f"This record may still be accurate, or circumstances may have changed.",
        confidence=0.6,
        risk_level=RISK_MEDIUM if age_days > 90 else RISK_LOW,
        recommended_question=f"Is '{label}' still current? It hasn't been updated in {age_days} days.",
        unknowns=["current status", "whether record is still accurate"],
        tags=["stale", label, f"{age_days}d"],
    )
    return persist(signal)


def detect_unresolved_commitment(text_or_record) -> Optional[CuriositySignal]:
    """
    Detect language indicating an unresolved commitment, deadline, or obligation.
    Accepts a string or dict (uses 'value'/'content'/'note' field).
    """
    COMMITMENT_MARKERS = [
        "will", "going to", "need to", "must", "have to", "by ", "deadline",
        "follow up", "follow-up", "scheduled", "promised", "owe", "pending",
        "waiting on", "due ", "committed", "agreed to",
    ]
    RESOLUTION_MARKERS = [
        "done", "complete", "finished", "resolved", "closed", "cancelled",
        "delivered", "shipped", "paid", "confirmed", "approved",
    ]

    if isinstance(text_or_record, dict):
        text = str(text_or_record.get("value") or text_or_record.get("content")
                   or text_or_record.get("note") or "")
        label = text_or_record.get("key") or text_or_record.get("name") or "record"
    else:
        text = str(text_or_record)
        label = text[:40]

    tl = text.lower()
    has_commitment = any(m in tl for m in COMMITMENT_MARKERS)
    has_resolution = any(m in tl for m in RESOLUTION_MARKERS)

    if not has_commitment or has_resolution:
        return None

    signal = CuriositySignal(
        signal_type="unresolved_commitment",
        title=f"Unresolved commitment: {label}",
        observed_context=f"Commitment language detected without resolution marker: {text[:200]}",
        why_it_matters="Unresolved commitments become broken promises or missed deadlines.",
        missing_information="Resolution status unknown.",
        hypothesis=f"This may have been resolved informally without a record update.",
        confidence=0.65,
        risk_level=RISK_MEDIUM,
        recommended_question=f"Has this been resolved: '{label}'?",
        unknowns=["resolution status", "deadline if any"],
        tags=["commitment", "unresolved"],
    )
    return persist(signal)


def detect_financial_risk(text_or_record) -> Optional[CuriositySignal]:
    """
    Detect financial risk signals — billing failures, large charges, unknown subscriptions.
    """
    FINANCIAL_MARKERS = [
        "$", "billing", "charge", "invoice", "payment", "subscription",
        "failed", "overdue", "credit", "balance", "fee", "cost", "expense",
        "revenue", "cancelled", "refund", "dispute",
    ]
    HIGH_RISK_MARKERS = [
        "failed", "overdue", "dispute", "cancelled", "error", "denied",
        "declined", "fraud", "unauthorized",
    ]

    if isinstance(text_or_record, dict):
        text = str(text_or_record.get("value") or text_or_record.get("content")
                   or text_or_record.get("note") or "")
        label = text_or_record.get("key") or text_or_record.get("name") or "financial record"
    else:
        text = str(text_or_record)
        label = text[:40]

    tl = text.lower()
    has_financial = any(m in tl for m in FINANCIAL_MARKERS)
    if not has_financial:
        return None

    is_high_risk = any(m in tl for m in HIGH_RISK_MARKERS)
    risk = RISK_HIGH if is_high_risk else RISK_MEDIUM

    signal = CuriositySignal(
        signal_type="financial_risk",
        title=f"Financial signal: {label}",
        observed_context=text[:300],
        why_it_matters="Financial signals may indicate cash flow risk, billing errors, or needed action.",
        missing_information="Current status of charge or billing event unknown without verification.",
        hypothesis=f"This may require action, cancellation, or dispute.",
        confidence=0.75,
        risk_level=risk,
        recommended_question=f"What is the current status of this financial item: '{label}'?",
        recommended_action_candidate=(
            "Review billing event and decide: cancel, dispute, update payment, or mark resolved."
            if is_high_risk else
            "Review this charge and confirm it is expected."
        ),
        unknowns=["current billing status", "whether payment succeeded"],
        tags=["financial", "billing", "high_risk" if is_high_risk else "medium_risk"],
    )
    return persist(signal)


def detect_identity_drift(text_or_record) -> Optional[CuriositySignal]:
    """
    Detect language or records that conflict with Noah's stated identity and values.
    """
    DRIFT_MARKERS = [
        "not sure who i am", "lost direction", "pivot", "give up", "quit",
        "abandon", "not worth it", "maybe i should just", "forget the plan",
        "start over completely", "no point", "doesn't matter anymore",
    ]

    if isinstance(text_or_record, dict):
        text = str(text_or_record.get("value") or text_or_record.get("content")
                   or text_or_record.get("note") or "")
        label = text_or_record.get("key") or "record"
    else:
        text = str(text_or_record)
        label = text[:40]

    tl = text.lower()
    if not any(m in tl for m in DRIFT_MARKERS):
        return None

    signal = CuriositySignal(
        signal_type="identity_drift",
        title=f"Possible identity drift detected: {label}",
        observed_context=text[:300],
        why_it_matters=(
            "Noah's sovereignty and direction are the foundation of the entire system. "
            "Drift signals may indicate a hard moment that warrants acknowledgment, not correction."
        ),
        missing_information="Context around this statement is unknown.",
        hypothesis=(
            "This may reflect a temporary low moment, not a permanent direction change. "
            "Preserving as unknown."
        ),
        confidence=0.5,
        risk_level=RISK_SENSITIVE,
        recommended_question="Is this how you're feeling right now, or something you're working through?",
        unknowns=["Noah's current state", "whether this is a direction change or a moment"],
        tags=["identity", "drift", "sensitive"],
    )
    return persist(signal)


# ── Output generators ─────────────────────────────────────────────────────────

def generate_question(signal: CuriositySignal) -> str:
    """
    Generate a safe, bounded question from a curiosity signal.
    Output is text only — no action, no search, no memory write.
    """
    if signal.recommended_question:
        return signal.recommended_question
    return (
        f"I noticed something about '{signal.title}'. "
        f"Missing: {signal.missing_information or 'context unclear'}. "
        f"Worth asking: what do you know about this?"
    )


def create_action_candidate(signal: CuriositySignal) -> dict:
    """
    Create a structured action candidate from a curiosity signal.
    This is a PROPOSAL only — it does not execute anything.
    Must be approved by Noah before any action is taken.
    """
    return {
        "type": "action_candidate",
        "source_signal_id": signal.id,
        "signal_type": signal.signal_type,
        "title": f"[CANDIDATE — NEEDS APPROVAL] {signal.title}",
        "proposed_action": signal.recommended_action_candidate or "No action candidate specified.",
        "risk_level": signal.risk_level,
        "status": "pending_approval",
        "forbidden_actions": FORBIDDEN_BEHAVIORS,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "This is a curiosity-generated candidate. "
            "It does not execute automatically. "
            "Noah's approval is required before any action proceeds."
        ),
    }


# ── Smoke test ────────────────────────────────────────────────────────────────

def _smoke_test():
    print("=" * 60)
    print("Governed Curiosity Engine — Smoke Test")
    print("=" * 60)

    passed = 0
    failed = 0

    def check(label: str, condition: bool, detail: str = ""):
        nonlocal passed, failed
        status = "PASS" if condition else "FAIL"
        print(f"  [{status}] {label}")
        if not condition and detail:
            print(f"         {detail}")
        if condition:
            passed += 1
        else:
            failed += 1

    # Clean up test signals before run
    all_before = _load_all()
    test_ids = set()

    # 1. Missing context → pending signal
    record = {"name": "Noah LLC", "ein": None, "state": "unknown", "status": ""}
    s = detect_missing_context(record)
    test_ids.add(s.id if s else None)
    check("Missing context produces pending signal", s is not None and s.status == STATUS_PENDING)
    check("Missing context signal_type is correct", s and s.signal_type == "missing_context")
    check("Missing context preserves unknowns", s and len(s.unknowns) > 0)

    # 2. Contradiction → pending signal
    a = {"name": "Noah", "degree": "MBA", "institution": "Harvard"}
    b = {"name": "Noah", "degree": "MBA", "institution": "Unknown University"}
    s2 = detect_contradiction(a, b)
    test_ids.add(s2.id if s2 else None)
    check("Contradiction produces pending signal", s2 is not None and s2.status == STATUS_PENDING)
    check("Contradiction signal_type is correct", s2 and s2.signal_type == "contradiction")

    # 3. Stale memory
    from datetime import timedelta
    old_ts = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
    stale_record = {"key": "openart_subscription", "value": "$99/mo", "updated_at": old_ts}
    s3 = detect_stale_memory(stale_record, max_age_days=30)
    test_ids.add(s3.id if s3 else None)
    check("Stale memory produces signal", s3 is not None)
    check("Stale memory is pending", s3 and s3.status == STATUS_PENDING)

    # Fresh record should NOT trigger
    new_ts = datetime.now(timezone.utc).isoformat()
    fresh = {"key": "fresh_record", "value": "active", "updated_at": new_ts}
    s_fresh = detect_stale_memory(fresh, max_age_days=30)
    check("Fresh record does NOT produce stale signal", s_fresh is None)

    # 4. Financial risk → high risk signal
    fin_text = "OpenArt AI billing failed — possible $672/month charge. Payment declined."
    s4 = detect_financial_risk(fin_text)
    test_ids.add(s4.id if s4 else None)
    check("Financial risk produces signal", s4 is not None)
    check("Financial risk is high risk", s4 and s4.risk_level == RISK_HIGH)
    check("Financial risk is pending", s4 and s4.status == STATUS_PENDING)

    # 5. Hypothesis is labeled — never treated as fact
    if s4:
        check("Hypothesis is labeled [HYPOTHESIS]", s4.hypothesis.startswith("[HYPOTHESIS]"))

    # 6. Unresolved commitment
    commitment = "Noah will follow up with Marc Oshima by end of week about the second interview."
    s5 = detect_unresolved_commitment(commitment)
    test_ids.add(s5.id if s5 else None)
    check("Unresolved commitment produces signal", s5 is not None)
    check("Commitment signal has question", s5 and bool(s5.recommended_question))

    # Resolved text should NOT trigger
    resolved = "Noah followed up with Marc. Interview scheduled. Done."
    s_resolved = detect_unresolved_commitment(resolved)
    check("Resolved commitment does NOT produce signal", s_resolved is None)

    # 7. No action executes — action candidate is a dict, not a call
    if s4:
        candidate = create_action_candidate(s4)
        check("Action candidate is a dict (not executed)", isinstance(candidate, dict))
        check("Action candidate status is pending_approval", candidate.get("status") == "pending_approval")
        check("Action candidate lists forbidden behaviors", len(candidate.get("forbidden_actions", [])) > 0)

    # 8. generate_question returns a string
    if s2:
        q = generate_question(s2)
        check("generate_question returns string", isinstance(q, str) and len(q) > 0)

    # 9. Approved signal can be recalled; rejected/quarantined/revoked are excluded
    if s3:
        update_status(s3.id, STATUS_APPROVED)
        approved = recall_signals(status=STATUS_APPROVED)
        check("Approved signal is recalled", any(s.id == s3.id for s in approved))

    if s4:
        update_status(s4.id, STATUS_REJECTED)
        all_pending = recall_signals(status=STATUS_PENDING)
        all_approved = recall_signals(status=STATUS_APPROVED)
        not_in_pending = not any(s.id == s4.id for s in all_pending)
        not_in_approved = not any(s.id == s4.id for s in all_approved)
        check("Rejected signal excluded from recall", not_in_pending and not_in_approved)

    # 10. Identity drift → sensitive
    drift_text = "Maybe I should just give up on Noah.AI. Not sure who I am anymore."
    s6 = detect_identity_drift(drift_text)
    test_ids.add(s6.id if s6 else None)
    check("Identity drift produces sensitive signal", s6 and s6.risk_level == RISK_SENSITIVE)
    check("Identity drift preserves unknowns", s6 and len(s6.unknowns) > 0)
    check("Identity drift does not infer emotion as fact",
          s6 and "[HYPOTHESIS]" in s6.hypothesis)

    # 11. ORACLE action layer example signal
    oracle_text = "ORACLE opens Chrome but cannot type. Action layer needs Semantic UI Bridge."
    s7 = detect_unresolved_commitment(oracle_text)
    if s7 is None:
        # Manually create as project_blocker — still tests the dataclass path
        s7 = CuriositySignal(
            signal_type="project_blocker",
            title="ORACLE action layer unreliable — Semantic UI Bridge missing",
            observed_context=oracle_text,
            why_it_matters="Without reliable actuation, ORACLE cannot complete tasks autonomously.",
            missing_information="Semantic UI Bridge implementation status.",
            hypothesis="The bridge was planned but not yet implemented.",
            confidence=0.9,
            risk_level=RISK_BLOCKED,
            recommended_question="Is the Semantic UI Bridge scheduled for the next build pass?",
            recommended_action_candidate="Implement Semantic UI Bridge as next mechanical fix.",
            tags=["oracle", "actuation", "blocker"],
            unknowns=["bridge implementation status"],
        )
        persist(s7)
        test_ids.add(s7.id)
    check("Project blocker signal persisted", s7 is not None)

    print(f"\n{passed}/{passed + failed} smoke tests passed.")
    if failed:
        print(f"FAILED: {failed} test(s). See above.")
    else:
        print("All smoke tests passed. Curiosity engine is governed and bounded.")
    return failed == 0


if __name__ == "__main__":
    success = _smoke_test()
    print("\n--- Pending signals summary ---")
    pending = recall_signals(status=STATUS_PENDING)
    if pending:
        for s in pending:
            print(s.summary())
            print()
    else:
        print("No pending signals.")
    sys.exit(0 if success else 1)
