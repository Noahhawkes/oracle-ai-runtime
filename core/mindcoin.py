"""
core/mindcoin.py — ORACLE MindCoin v0.1

MindCoin is not cryptocurrency.
MindCoin is not money.
MindCoin is not transferable.
MindCoin is not a security.
MindCoin is not an investment.

MindCoin is an internal, non-financial scoring and provenance ledger
for meaningful continuity work inside ORACLE.

It measures meaning preserved, not money earned.

What earns MindCoin:
  Approved memory compression. Project state recovery. Session recovery.
  Blocker resolution. Verified action completion. Candidate creation.
  Relationship continuity updates. Source provenance preservation.
  Continuity exports. Video intelligence candidates. Governance approvals.

What does NOT earn MindCoin:
  Raw surveillance. Unapproved memory. Invented progress. Unverified claims.
  Financial events of any kind. Anything that could be mistaken for money.

Hard rules:
  1. No event may claim value without evidence.
  2. No event may be financial.
  3. No event may be transferable.
  4. No external blockchain.
  5. Pending points are not approved points.
  6. Revoked/quarantined events are preserved but excluded from totals.
  7. Do not mint points for unapproved memory.
  8. Preserve unknowns.

Persistence: Memory/mindcoin_ledger.json  (gitignored)

CLI:
  python core/mindcoin.py --smoke-test
  python core/mindcoin.py --summary
  python core/mindcoin.py --pending
  python core/mindcoin.py --award <event_type> --title <title> --evidence <evidence>
"""

from __future__ import annotations

import json
import sys
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Root ──────────────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

LEDGER_FILE = ROOT / "Memory" / "mindcoin_ledger.json"

# ── Status constants ──────────────────────────────────────────────────────────
STATUS_PENDING     = "pending"
STATUS_APPROVED    = "approved"
STATUS_REJECTED    = "rejected"
STATUS_REVOKED     = "revoked"
STATUS_QUARANTINED = "quarantined"

_APPROVED_STATUSES   = {STATUS_APPROVED}
_PENDING_STATUSES    = {STATUS_PENDING}
_EXCLUDED_STATUSES   = {STATUS_REVOKED, STATUS_QUARANTINED, STATUS_REJECTED}

# ── Event types ───────────────────────────────────────────────────────────────
EVENT_MEMORY_APPROVED              = "memory_approved"
EVENT_CANDIDATE_CREATED            = "candidate_created"
EVENT_PROJECT_STATE_RECOVERED      = "project_state_recovered"
EVENT_SESSION_RECOVERED            = "session_recovered"
EVENT_BLOCKER_RESOLVED             = "blocker_resolved"
EVENT_VERIFIED_ACTION_COMPLETED    = "verified_action_completed"
EVENT_CONTINUITY_EXPORT_CREATED    = "continuity_export_created"
EVENT_VIDEO_CANDIDATE_CREATED      = "video_candidate_created"
EVENT_FILE_CLEANUP_CANDIDATE       = "file_cleanup_candidate_created"
EVENT_RELATIONSHIP_CONTEXT         = "relationship_context_preserved"
EVENT_GOVERNANCE_RULE_APPROVED     = "governance_rule_approved"
EVENT_SOURCE_PROVENANCE            = "source_provenance_preserved"
EVENT_UNKNOWN_PRESERVED            = "unknown_preserved"
EVENT_REVOKED                      = "revoked_event"

VALID_EVENT_TYPES = {
    EVENT_MEMORY_APPROVED,
    EVENT_CANDIDATE_CREATED,
    EVENT_PROJECT_STATE_RECOVERED,
    EVENT_SESSION_RECOVERED,
    EVENT_BLOCKER_RESOLVED,
    EVENT_VERIFIED_ACTION_COMPLETED,
    EVENT_CONTINUITY_EXPORT_CREATED,
    EVENT_VIDEO_CANDIDATE_CREATED,
    EVENT_FILE_CLEANUP_CANDIDATE,
    EVENT_RELATIONSHIP_CONTEXT,
    EVENT_GOVERNANCE_RULE_APPROVED,
    EVENT_SOURCE_PROVENANCE,
    EVENT_UNKNOWN_PRESERVED,
    EVENT_REVOKED,
}

# ── Forbidden terms (guard against financial/crypto framing) ──────────────────
_FORBIDDEN_TERMS = {
    "cryptocurrency", "crypto", "token", "blockchain", "wallet",
    "exchange", "trading", "investment", "securities", "transferable",
    "mint", "ico", "nft", "defi", "yield", "staking", "airdrop",
    "market cap", "market value", "price", "buy", "sell", "hodl",
}

# ── Point schedule ────────────────────────────────────────────────────────────
POINT_SCHEDULE: dict[str, int] = {
    EVENT_UNKNOWN_PRESERVED:           1,
    EVENT_CANDIDATE_CREATED:           1,
    EVENT_SOURCE_PROVENANCE:           2,
    EVENT_VIDEO_CANDIDATE_CREATED:     2,
    EVENT_FILE_CLEANUP_CANDIDATE:      2,
    EVENT_RELATIONSHIP_CONTEXT:        3,
    EVENT_SESSION_RECOVERED:           5,
    EVENT_PROJECT_STATE_RECOVERED:     5,
    EVENT_GOVERNANCE_RULE_APPROVED:    5,
    EVENT_MEMORY_APPROVED:             8,
    EVENT_BLOCKER_RESOLVED:           10,
    EVENT_CONTINUITY_EXPORT_CREATED:  15,
    EVENT_VERIFIED_ACTION_COMPLETED:  20,
    EVENT_REVOKED:                     0,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_financial(text: str) -> bool:
    """Return True if text contains forbidden financial/crypto language."""
    lower = text.lower()
    return any(term in lower for term in _FORBIDDEN_TERMS)


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class MindCoinEvent:
    id:              str   = field(default_factory=lambda: uuid.uuid4().hex[:12])
    event_type:      str   = ""
    title:           str   = ""
    description:     str   = ""
    source_module:   str   = ""
    source_id:       str   = ""
    project_name:    str   = ""
    points:          int   = 0
    confidence:      float = 1.0
    approval_status: str   = STATUS_PENDING
    evidence:        str   = ""
    unknowns:        list  = field(default_factory=list)
    created_at:      str   = field(default_factory=_now)
    updated_at:      str   = field(default_factory=_now)

    def touch(self) -> None:
        self.updated_at = _now()

    def summary_line(self) -> str:
        pts = f"+{self.points}" if self.approval_status == STATUS_APPROVED else f"({self.points}p pending)"
        return f"[{self.approval_status[:4].upper()}] {self.event_type:<30s} {pts:>15s}  {self.title[:50]}"


@dataclass
class MindCoinLedger:
    id:              str   = field(default_factory=lambda: uuid.uuid4().hex[:8])
    owner:           str   = "Noah Hawkes"
    events:          list  = field(default_factory=list)      # list[dict] after JSON round-trip
    created_at:      str   = field(default_factory=_now)
    updated_at:      str   = field(default_factory=_now)

    # Computed — not stored, recalculated on load
    approved_points: int   = 0
    pending_points:  int   = 0
    revoked_points:  int   = 0
    total_points:    int   = 0

    def recompute(self, events: list["MindCoinEvent"]) -> None:
        self.approved_points = sum(
            e.points for e in events if e.approval_status == STATUS_APPROVED
        )
        self.pending_points = sum(
            e.points for e in events if e.approval_status == STATUS_PENDING
        )
        self.revoked_points = sum(
            e.points for e in events if e.approval_status in (STATUS_REVOKED, STATUS_QUARANTINED)
        )
        self.total_points = self.approved_points
        self.updated_at   = _now()

    def summary(self) -> str:
        return (
            f"MindCoin Ledger — {self.owner}\n"
            f"  Approved : {self.approved_points} points\n"
            f"  Pending  : {self.pending_points} points\n"
            f"  Revoked  : {self.revoked_points} points\n"
            f"  Total    : {self.total_points} approved points\n"
            f"  Updated  : {self.updated_at[:19].replace('T',' ')} UTC"
        )


# ── Persistence ───────────────────────────────────────────────────────────────

def _events_from_dicts(raw: list[dict]) -> list[MindCoinEvent]:
    out = []
    for d in raw:
        if not isinstance(d, dict):
            continue
        e = MindCoinEvent()
        for k, v in d.items():
            if hasattr(e, k):
                setattr(e, k, v)
        out.append(e)
    return out


def load_ledger() -> tuple["MindCoinLedger", list["MindCoinEvent"]]:
    """Load ledger + events from disk. Returns (ledger, events)."""
    LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not LEDGER_FILE.exists():
        ledger = MindCoinLedger()
        return ledger, []

    try:
        raw = json.loads(LEDGER_FILE.read_text(encoding="utf-8"))
    except Exception:
        return MindCoinLedger(), []

    ledger = MindCoinLedger()
    for k in ("id", "owner", "created_at", "updated_at"):
        if k in raw:
            setattr(ledger, k, raw[k])

    events = _events_from_dicts(raw.get("events", []))
    ledger.recompute(events)
    return ledger, events


def save_ledger(ledger: "MindCoinLedger", events: list["MindCoinEvent"]) -> None:
    """Persist ledger + events to disk."""
    LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
    ledger.recompute(events)
    payload = asdict(ledger)
    payload["events"] = [asdict(e) for e in events]
    LEDGER_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Core API ──────────────────────────────────────────────────────────────────

def create_event(
    event_type:    str,
    title:         str,
    evidence:      str,
    description:   str   = "",
    source_module: str   = "",
    source_id:     str   = "",
    project_name:  str   = "",
    confidence:    float = 1.0,
    unknowns:      list  = None,
    auto_approve:  bool  = False,
) -> "MindCoinEvent":
    """
    Create a new MindCoin event. Validates event type, evidence,
    and guards against financial/crypto framing.
    Raises ValueError on invalid input.
    """
    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(f"Unknown event type: {event_type!r}. Valid: {sorted(VALID_EVENT_TYPES)}")

    if not evidence or not evidence.strip():
        raise ValueError("Evidence is required. No event may claim value without evidence.")

    # Guard: no financial or crypto language in title, description, or evidence
    for field_name, text in [("title", title), ("description", description), ("evidence", evidence)]:
        if _check_financial(text):
            raise ValueError(
                f"Financial/crypto language detected in {field_name!r}. "
                f"MindCoin is not cryptocurrency or money."
            )

    points = POINT_SCHEDULE.get(event_type, 0)
    status = STATUS_APPROVED if auto_approve else STATUS_PENDING

    event = MindCoinEvent(
        event_type=event_type,
        title=title,
        description=description,
        source_module=source_module,
        source_id=source_id,
        project_name=project_name,
        points=points,
        confidence=confidence,
        approval_status=status,
        evidence=evidence,
        unknowns=unknowns or [],
    )
    return event


def approve_event(event_id: str, events: list["MindCoinEvent"]) -> "MindCoinEvent":
    for e in events:
        if e.id == event_id:
            if e.approval_status in (STATUS_REVOKED, STATUS_QUARANTINED):
                raise ValueError(f"Cannot approve {e.approval_status} event.")
            e.approval_status = STATUS_APPROVED
            e.touch()
            return e
    raise KeyError(f"Event not found: {event_id}")


def reject_event(event_id: str, events: list["MindCoinEvent"]) -> "MindCoinEvent":
    for e in events:
        if e.id == event_id:
            e.approval_status = STATUS_REJECTED
            e.touch()
            return e
    raise KeyError(f"Event not found: {event_id}")


def revoke_event(event_id: str, events: list["MindCoinEvent"]) -> "MindCoinEvent":
    """Revoke an approved event. Points removed from approved total but event preserved."""
    for e in events:
        if e.id == event_id:
            e.approval_status = STATUS_REVOKED
            e.touch()
            return e
    raise KeyError(f"Event not found: {event_id}")


def quarantine_event(event_id: str, events: list["MindCoinEvent"]) -> "MindCoinEvent":
    for e in events:
        if e.id == event_id:
            e.approval_status = STATUS_QUARANTINED
            e.touch()
            return e
    raise KeyError(f"Event not found: {event_id}")


def get_totals(ledger: "MindCoinLedger") -> dict:
    return {
        "approved_points": ledger.approved_points,
        "pending_points":  ledger.pending_points,
        "revoked_points":  ledger.revoked_points,
        "total_points":    ledger.total_points,
    }


def list_pending(events: list["MindCoinEvent"]) -> list["MindCoinEvent"]:
    return [e for e in events if e.approval_status == STATUS_PENDING]


def list_approved(events: list["MindCoinEvent"]) -> list["MindCoinEvent"]:
    return [e for e in events if e.approval_status == STATUS_APPROVED]


def summarize_ledger(ledger: "MindCoinLedger", events: list["MindCoinEvent"]) -> str:
    lines = [ledger.summary(), ""]
    approved = list_approved(events)
    pending  = list_pending(events)
    if approved:
        lines.append(f"Approved events ({len(approved)}):")
        for e in approved[-10:]:
            lines.append("  " + e.summary_line())
        lines.append("")
    if pending:
        lines.append(f"Pending events ({len(pending)}):")
        for e in pending[-10:]:
            lines.append("  " + e.summary_line())
    return "\n".join(lines)


def award_for_candidate(
    candidate_type: str,
    source_id:      str,
    evidence:       str,
    project_name:   str = "",
) -> "MindCoinEvent":
    """
    Award points for a created candidate.
    candidate_type: 'video', 'memory', 'file_cleanup', or 'general'
    """
    type_map = {
        "video":        EVENT_VIDEO_CANDIDATE_CREATED,
        "file_cleanup": EVENT_FILE_CLEANUP_CANDIDATE,
        "general":      EVENT_CANDIDATE_CREATED,
        "memory":       EVENT_CANDIDATE_CREATED,
    }
    event_type = type_map.get(candidate_type, EVENT_CANDIDATE_CREATED)
    return create_event(
        event_type=event_type,
        title=f"Candidate created: {source_id[:40]}",
        evidence=evidence,
        source_module="obs_ingest" if "video" in candidate_type else "remember_me",
        source_id=source_id,
        project_name=project_name,
    )


def award_for_completion(
    event_type:  str,
    source_id:   str,
    evidence:    str,
    title:       str    = "",
    project_name: str   = "",
) -> "MindCoinEvent":
    """Award points for a completed governed action."""
    return create_event(
        event_type=event_type,
        title=title or f"Completed: {event_type}",
        evidence=evidence,
        source_module="actuation_engine",
        source_id=source_id,
        project_name=project_name,
    )


# ── Smoke tests ───────────────────────────────────────────────────────────────

def run_smoke_tests() -> int:
    failures = 0
    results  = []

    def check(name: str, passed: bool, detail: str = "") -> None:
        nonlocal failures
        if not passed:
            failures += 1
        status = "PASS" if passed else "FAIL"
        results.append(f"  [{status}] {name}" + (f" -- {detail}" if detail else ""))

    # 1. Create ledger
    ledger, events = load_ledger()
    check("create ledger: returns MindCoinLedger", isinstance(ledger, MindCoinLedger))
    check("create ledger: events is list", isinstance(events, list))

    # 2. Create pending event
    e = create_event(
        event_type=EVENT_CANDIDATE_CREATED,
        title="Test candidate",
        evidence="smoke test run",
    )
    check("create pending event: is MindCoinEvent", isinstance(e, MindCoinEvent))
    check("create pending event: status is pending", e.approval_status == STATUS_PENDING)
    check("create pending event: points = 1", e.points == 1)

    # 3. Pending event -> pending_points only
    events_test = [e]
    ledger_test = MindCoinLedger()
    ledger_test.recompute(events_test)
    check("pending event: pending_points += 1", ledger_test.pending_points == 1)
    check("pending event: approved_points == 0", ledger_test.approved_points == 0)

    # 4. Approve event -> approved_points
    approve_event(e.id, events_test)
    ledger_test.recompute(events_test)
    check("approve event: status = approved", e.approval_status == STATUS_APPROVED)
    check("approve event: approved_points == 1", ledger_test.approved_points == 1)
    check("approve event: pending_points == 0", ledger_test.pending_points == 0)

    # 5. Revoke event -> removed from approved total, event preserved
    revoke_event(e.id, events_test)
    ledger_test.recompute(events_test)
    check("revoke event: status = revoked", e.approval_status == STATUS_REVOKED)
    check("revoke event: approved_points == 0", ledger_test.approved_points == 0)
    check("revoke event: event still in list", len(events_test) == 1)
    check("revoke event: revoked_points == 1", ledger_test.revoked_points == 1)

    # 6. Quarantine event -> excluded from approved total
    e2 = create_event(
        event_type=EVENT_CANDIDATE_CREATED,
        title="Quarantine test",
        evidence="smoke test quarantine",
    )
    events_q = [e2]
    quarantine_event(e2.id, events_q)
    ledger_q = MindCoinLedger()
    ledger_q.recompute(events_q)
    check("quarantine event: status = quarantined", e2.approval_status == STATUS_QUARANTINED)
    check("quarantine event: approved_points == 0", ledger_q.approved_points == 0)
    check("quarantine event: event preserved", len(events_q) == 1)

    # 7. unknown_preserved awards 1 point
    eu = create_event(
        event_type=EVENT_UNKNOWN_PRESERVED,
        title="Unknown preserved test",
        evidence="smoke test unknown",
    )
    check("unknown_preserved: points == 1", eu.points == 1)

    # 8. continuity_export_created awards 15 points
    ec = create_event(
        event_type=EVENT_CONTINUITY_EXPORT_CREATED,
        title="Continuity export test",
        evidence="smoke test export",
    )
    check("continuity_export_created: points == 15", ec.points == 15)

    # 9. verified_action_completed awards 20 points
    ev = create_event(
        event_type=EVENT_VERIFIED_ACTION_COMPLETED,
        title="Verified action test",
        evidence="smoke test action",
    )
    check("verified_action_completed: points == 20", ev.points == 20)

    # 10. Financial/crypto language rejected in title
    try:
        create_event(
            event_type=EVENT_CANDIDATE_CREATED,
            title="MindCoin is cryptocurrency",
            evidence="test",
        )
        check("financial language rejected in title", False, "should have raised ValueError")
    except ValueError:
        check("financial language rejected in title", True)

    # Financial language in evidence
    try:
        create_event(
            event_type=EVENT_CANDIDATE_CREATED,
            title="Safe title",
            evidence="this is a blockchain token",
        )
        check("financial language rejected in evidence", False, "should have raised ValueError")
    except ValueError:
        check("financial language rejected in evidence", True)

    # Invalid event type
    try:
        create_event(event_type="earn_money", title="x", evidence="y")
        check("invalid event type rejected", False, "should have raised ValueError")
    except ValueError:
        check("invalid event type rejected", True)

    # 11. Missing evidence rejected
    try:
        create_event(event_type=EVENT_CANDIDATE_CREATED, title="No evidence", evidence="")
        check("missing evidence rejected", False, "should have raised ValueError")
    except ValueError:
        check("missing evidence rejected", True)

    # Missing evidence (whitespace only)
    try:
        create_event(event_type=EVENT_CANDIDATE_CREATED, title="Whitespace", evidence="   ")
        check("whitespace-only evidence rejected", False)
    except ValueError:
        check("whitespace-only evidence rejected", True)

    # 12. Ledger persists to JSON (direct serialization test, no monkey-patching)
    import tempfile, os
    tmp_path = Path(tempfile.mktemp(suffix=".json"))

    try:
        el = create_event(
            event_type=EVENT_MEMORY_APPROVED,
            title="Persist test",
            evidence="smoke test persistence",
            auto_approve=True,
        )
        events_p = [el]
        ledger_p  = MindCoinLedger()
        ledger_p.recompute(events_p)

        # Serialize directly to tmp_path
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(ledger_p)
        payload["events"] = [asdict(e) for e in events_p]
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        check("ledger persists: file created", tmp_path.exists())

        # Deserialize directly from tmp_path
        raw2    = json.loads(tmp_path.read_text(encoding="utf-8"))
        loaded_e2 = _events_from_dicts(raw2.get("events", []))
        ledger2 = MindCoinLedger()
        ledger2.recompute(loaded_e2)

        check("ledger persists: events reloaded", len(loaded_e2) == 1)
        check("ledger persists: approved_points correct", ledger2.approved_points == 8)
        check("ledger persists: event_type preserved", loaded_e2[0].event_type == EVENT_MEMORY_APPROVED)
    finally:
        if tmp_path.exists():
            os.unlink(tmp_path)

    # approve already-revoked event raises ValueError
    e_rev = create_event(
        event_type=EVENT_CANDIDATE_CREATED,
        title="Revoke then approve test",
        evidence="smoke test",
    )
    events_rev = [e_rev]
    revoke_event(e_rev.id, events_rev)
    try:
        approve_event(e_rev.id, events_rev)
        check("cannot approve revoked event", False, "should have raised ValueError")
    except ValueError:
        check("cannot approve revoked event", True)

    # summarize_ledger: no crash
    ledger_sum, events_sum = load_ledger()
    summary = summarize_ledger(ledger_sum, events_sum)
    check("summarize_ledger: no crash", isinstance(summary, str))
    check("summarize_ledger: contains MindCoin", "MindCoin" in summary)

    # award_for_candidate: video type
    ev_c = award_for_candidate("video", "vid_001", "smoke test video candidate")
    check("award_for_candidate video: correct event_type",
          ev_c.event_type == EVENT_VIDEO_CANDIDATE_CREATED)
    check("award_for_candidate video: points == 2", ev_c.points == 2)

    # award_for_completion: blocker resolved
    ev_b = award_for_completion(
        EVENT_BLOCKER_RESOLVED,
        source_id="proj_001",
        evidence="blocker cleared: qwen desktop control removed",
        title="Blocker resolved: qwen desktop restriction",
    )
    check("award_for_completion blocker: points == 10", ev_b.points == 10)

    # get_totals returns dict
    totals = get_totals(ledger_sum)
    check("get_totals: returns dict", isinstance(totals, dict))
    check("get_totals: has approved_points", "approved_points" in totals)

    # point schedule complete
    for et in VALID_EVENT_TYPES:
        check(f"point schedule covers: {et}", et in POINT_SCHEDULE)

    # Print results
    print(f"\n{'='*55}")
    print("ORACLE MindCoin v0.1 -- Smoke Tests")
    print(f"{'='*55}")
    for r in results:
        print(r)
    total  = len(results)
    passed = total - failures
    print(f"{'='*55}")
    print(f"Result: {passed}/{total} passed")
    print(f"STATUS: {'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    print(f"{'='*55}\n")
    return failures


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="ORACLE MindCoin -- proof-of-meaning ledger")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--summary",    action="store_true", help="Print ledger summary")
    parser.add_argument("--pending",    action="store_true", help="List pending events")
    parser.add_argument("--award",      metavar="EVENT_TYPE", help="Award points for event type")
    parser.add_argument("--title",      default="", help="Title for --award")
    parser.add_argument("--evidence",   default="", help="Evidence for --award")
    parser.add_argument("--project",    default="", help="Project name for --award")
    args = parser.parse_args()

    if args.smoke_test:
        sys.exit(run_smoke_tests())

    ledger, events = load_ledger()

    if args.summary:
        print(summarize_ledger(ledger, events))
        return

    if args.pending:
        p = list_pending(events)
        print(f"Pending MindCoin events: {len(p)}")
        for e in p:
            print("  " + e.summary_line())
        return

    if args.award:
        if not args.evidence:
            print("ERROR: --evidence required")
            sys.exit(1)
        try:
            e = create_event(
                event_type=args.award,
                title=args.title or f"Awarded: {args.award}",
                evidence=args.evidence,
                project_name=args.project,
            )
            events.append(e)
            save_ledger(ledger, events)
            print(f"Event created: {e.id[:8]} | {e.event_type} | {e.points}p (pending)")
        except ValueError as ex:
            print(f"ERROR: {ex}")
            sys.exit(1)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
