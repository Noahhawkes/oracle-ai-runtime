"""
core/action_candidates.py — ORACLE Action Candidates v0.1

ORACLE proposes actions before executing them.
All candidates are born pending. Only approved candidates may be passed to
Actuation Engine. Rejected / revoked / quarantined candidates never execute.

Usage:
    python core/action_candidates.py --smoke-test
    python core/action_candidates.py --list
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
CANDIDATES_FILE = ROOT / "Memory" / "action_candidates.json"

# ── Types ─────────────────────────────────────────────────────────────────────
CandidateStatus = Literal["pending", "approved", "rejected", "revoked", "quarantined"]
RiskLevel = Literal["low", "medium", "high", "critical"]


# ── Data model ────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_INACTIVE_STATUSES: frozenset[str] = frozenset({"rejected", "revoked", "quarantined"})
_ACTIVE_STATUSES:   frozenset[str] = frozenset({"pending", "approved"})


def new_candidate(
    title: str,
    description: str,
    risk_level: RiskLevel,
    target_module: str,
    proposed_steps: list[str],
    reversibility: str = "unknown",
    required_approval: bool = True,
    evidence: Optional[str] = None,
) -> dict:
    """Create a new action candidate dict in pending state."""
    return {
        "id":               str(uuid.uuid4()),
        "title":            title,
        "description":      description,
        "risk_level":       risk_level,
        "required_approval": required_approval,
        "target_module":    target_module,
        "proposed_steps":   list(proposed_steps),
        "reversibility":    reversibility,
        "evidence":         evidence or "",
        "status":           "pending",
        "approved_by":      None,
        "approved_at":      None,
        "rejected_by":      None,
        "rejected_at":      None,
        "revoked_at":       None,
        "quarantined_at":   None,
        "rejection_reason": None,
        "created_at":       _now(),
        "updated_at":       _now(),
    }


# ── Persistence ───────────────────────────────────────────────────────────────

def _load() -> list[dict]:
    try:
        raw = json.loads(CANDIDATES_FILE.read_text(encoding="utf-8"))
        return raw if isinstance(raw, list) else []
    except Exception:
        return []


def _save(candidates: list[dict]) -> None:
    CANDIDATES_FILE.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATES_FILE.write_text(
        json.dumps(candidates, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ── Public API ────────────────────────────────────────────────────────────────

def submit(candidate: dict) -> dict:
    """Persist a new candidate. Returns the candidate with its id."""
    candidates = _load()
    # Reject duplicates by id
    if any(c.get("id") == candidate.get("id") for c in candidates):
        return candidate
    candidates.append(candidate)
    _save(candidates)
    return candidate


def get(candidate_id: str) -> Optional[dict]:
    """Retrieve a candidate by id."""
    for c in _load():
        if c.get("id") == candidate_id:
            return c
    return None


def list_candidates(status: Optional[CandidateStatus] = None) -> list[dict]:
    """Return all candidates, optionally filtered by status."""
    all_c = _load()
    if status:
        return [c for c in all_c if c.get("status") == status]
    return all_c


def approve(candidate_id: str, approved_by: str = "noah") -> dict:
    """Approve a pending candidate. Returns updated candidate."""
    candidates = _load()
    for c in candidates:
        if c.get("id") == candidate_id:
            if c.get("status") != "pending":
                raise ValueError(f"Cannot approve candidate in status={c['status']!r}")
            c["status"] = "approved"
            c["approved_by"] = approved_by
            c["approved_at"] = _now()
            c["updated_at"] = _now()
            _save(candidates)
            return c
    raise KeyError(f"Candidate {candidate_id!r} not found")


def reject(candidate_id: str, rejected_by: str = "noah", reason: str = "") -> dict:
    """Reject a pending candidate."""
    candidates = _load()
    for c in candidates:
        if c.get("id") == candidate_id:
            if c.get("status") not in ("pending",):
                raise ValueError(f"Cannot reject candidate in status={c['status']!r}")
            c["status"] = "rejected"
            c["rejected_by"] = rejected_by
            c["rejected_at"] = _now()
            c["rejection_reason"] = reason
            c["updated_at"] = _now()
            _save(candidates)
            return c
    raise KeyError(f"Candidate {candidate_id!r} not found")


def revoke(candidate_id: str, reason: str = "") -> dict:
    """Revoke an already-approved candidate before execution."""
    candidates = _load()
    for c in candidates:
        if c.get("id") == candidate_id:
            if c.get("status") != "approved":
                raise ValueError(f"Cannot revoke candidate in status={c['status']!r}")
            c["status"] = "revoked"
            c["revoked_at"] = _now()
            c["rejection_reason"] = reason
            c["updated_at"] = _now()
            _save(candidates)
            return c
    raise KeyError(f"Candidate {candidate_id!r} not found")


def quarantine(candidate_id: str, reason: str = "") -> dict:
    """Quarantine a candidate — it can never execute, regardless of prior status."""
    candidates = _load()
    for c in candidates:
        if c.get("id") == candidate_id:
            c["status"] = "quarantined"
            c["quarantined_at"] = _now()
            c["rejection_reason"] = reason
            c["updated_at"] = _now()
            _save(candidates)
            return c
    raise KeyError(f"Candidate {candidate_id!r} not found")


def is_inactive(candidate: dict) -> bool:
    """True if candidate is rejected, revoked, or quarantined — will never execute."""
    return candidate.get("status") in _INACTIVE_STATUSES


def is_executable(candidate: dict) -> bool:
    """True only if status==approved and required_approval is satisfied."""
    return (
        candidate.get("status") == "approved"
        and candidate.get("approved_by") is not None
    )


def list_active() -> list[dict]:
    """
    Return only pending and approved candidates — the ones still in play.
    Use this instead of list_candidates() when feeding the approval cycle
    or actuation engine to prevent dead candidates from resurfacing.
    """
    return [c for c in _load() if c.get("status") in _ACTIVE_STATUSES]


def purge_inactive(older_than_days: int = 30) -> int:
    """
    Remove rejected/revoked/quarantined candidates older than `older_than_days`.
    Returns the count of removed records. Safe to call periodically.
    """
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    candidates = _load()
    before = len(candidates)
    kept = []
    for c in candidates:
        if c.get("status") not in _INACTIVE_STATUSES:
            kept.append(c)
            continue
        # Keep recent inactive ones so audit trail isn't immediately lost
        try:
            updated = datetime.fromisoformat(c.get("updated_at", ""))
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            if updated >= cutoff:
                kept.append(c)
        except Exception:
            kept.append(c)  # keep if timestamp unreadable
    _save(kept)
    return before - len(kept)


# ── CLI ───────────────────────────────────────────────────────────────────────

def _cli_list() -> None:
    candidates = _load()
    if not candidates:
        print("No candidates.")
        return
    for c in candidates:
        print(f"  [{c['status'].upper():12}] {c['id'][:8]}  {c['title']}  risk={c['risk_level']}")


# ── Smoke tests ───────────────────────────────────────────────────────────────

def run_smoke_tests() -> int:
    """Returns failure count (0 = all pass)."""
    failures = 0

    def check(label: str, passed: bool, detail: str = "") -> None:
        nonlocal failures
        tag = "PASS" if passed else "FAIL"
        suffix = f" — {detail}" if detail and not passed else ""
        print(f"  [{tag}] {label}{suffix}")
        if not passed:
            failures += 1

    print("=" * 55)
    print("Action Candidates v0.1 — Smoke Tests")
    print("=" * 55)

    # Use an isolated test file
    import tempfile, os
    orig = CANDIDATES_FILE
    tmp = Path(tempfile.mktemp(suffix=".json"))

    import action_candidates as ac
    ac.CANDIDATES_FILE = tmp

    try:
        # 1. new_candidate creates pending
        c = ac.new_candidate(
            title="Test action",
            description="Smoke test candidate",
            risk_level="low",
            target_module="actuation_engine",
            proposed_steps=["find window", "click OK"],
            reversibility="reversible",
        )
        check("new_candidate: has id", bool(c.get("id")))
        check("new_candidate: status=pending", c.get("status") == "pending")
        check("new_candidate: required_approval=True", c.get("required_approval") is True)
        check("new_candidate: has proposed_steps", isinstance(c.get("proposed_steps"), list))
        check("new_candidate: has created_at", bool(c.get("created_at")))

        # 2. submit persists
        submitted = ac.submit(c)
        check("submit: returns candidate", submitted.get("id") == c["id"])
        check("submit: file created", tmp.exists())

        # 3. get retrieves
        fetched = ac.get(c["id"])
        check("get: returns correct candidate", fetched is not None and fetched["id"] == c["id"])
        check("get: nonexistent returns None", ac.get("nonexistent-id") is None)

        # 4. list_candidates
        all_c = ac.list_candidates()
        check("list_candidates: returns list", isinstance(all_c, list))
        check("list_candidates: contains submitted", any(x["id"] == c["id"] for x in all_c))
        pending = ac.list_candidates(status="pending")
        check("list_candidates(pending): finds it", any(x["id"] == c["id"] for x in pending))

        # 5. approve
        approved = ac.approve(c["id"], approved_by="noah")
        check("approve: status=approved", approved.get("status") == "approved")
        check("approve: approved_by=noah", approved.get("approved_by") == "noah")
        check("approve: approved_at set", bool(approved.get("approved_at")))

        # 6. is_executable
        check("is_executable: approved candidate", ac.is_executable(approved))
        pending_c = ac.new_candidate("p2", "d2", "medium", "mod", ["step1"])
        check("is_executable: pending=False", not ac.is_executable(pending_c))

        # 7. revoke (must be approved first)
        revoked = ac.revoke(c["id"], reason="changed mind")
        check("revoke: status=revoked", revoked.get("status") == "revoked")
        check("is_executable: revoked=False", not ac.is_executable(revoked))

        # 8. reject (on a fresh pending)
        c2 = ac.submit(ac.new_candidate("reject-test", "d", "high", "mod", []))
        rejected = ac.reject(c2["id"], rejected_by="noah", reason="too risky")
        check("reject: status=rejected", rejected.get("status") == "rejected")
        check("reject: rejection_reason set", bool(rejected.get("rejection_reason")))

        # 9. quarantine
        c3 = ac.submit(ac.new_candidate("quarantine-test", "d", "critical", "mod", []))
        qed = ac.quarantine(c3["id"], reason="unsafe")
        check("quarantine: status=quarantined", qed.get("status") == "quarantined")
        check("is_executable: quarantined=False", not ac.is_executable(qed))

        # 10. rejected/revoked/quarantined cannot be approved
        try:
            ac.approve(c["id"])  # c is already revoked
            check("revoked cannot be re-approved", False)
        except ValueError:
            check("revoked cannot be re-approved", True)

        # 11. duplicate submit is idempotent
        before = len(ac.list_candidates())
        ac.submit(approved)  # same id
        after = len(ac.list_candidates())
        check("submit duplicate: idempotent", before == after)

        # 12. list by status
        qlist = ac.list_candidates(status="quarantined")
        check("list_candidates(quarantined): finds quarantined", any(x["id"] == c3["id"] for x in qlist))

        # 13. is_inactive
        check("is_inactive: rejected=True",    ac.is_inactive(rejected))
        check("is_inactive: revoked=True",     ac.is_inactive(revoked))
        check("is_inactive: quarantined=True", ac.is_inactive(qed))
        fresh = ac.new_candidate("fresh", "d", "low", "mod", [])
        check("is_inactive: pending=False", not ac.is_inactive(fresh))

        # 14. list_active excludes dead states
        c_active = ac.submit(ac.new_candidate("active-test", "d", "low", "mod", ["step1"]))
        active = ac.list_active()
        active_ids = {x["id"] for x in active}
        check("list_active: includes pending",     c_active["id"] in active_ids)
        check("list_active: excludes rejected",    c2["id"] not in active_ids)
        check("list_active: excludes revoked",     c["id"]  not in active_ids)
        check("list_active: excludes quarantined", c3["id"] not in active_ids)

        # 15. revoked_at and quarantined_at timestamps set
        revoked_full = ac.get(c["id"])
        check("revoke: revoked_at set",        bool(revoked_full and revoked_full.get("revoked_at")))
        qed_full = ac.get(c3["id"])
        check("quarantine: quarantined_at set", bool(qed_full and qed_full.get("quarantined_at")))

        # 16. purge_inactive removes old dead records
        removed = ac.purge_inactive(older_than_days=0)
        check("purge_inactive: removed dead records", removed >= 3)
        after_purge = ac.list_candidates()
        dead_ids = {c["id"], c2["id"], c3["id"]}
        check("purge_inactive: dead records gone", not any(x["id"] in dead_ids for x in after_purge))
        still_active = ac.list_active()
        check("purge_inactive: active records preserved", c_active["id"] in {x["id"] for x in still_active})

    finally:
        ac.CANDIDATES_FILE = orig
        try:
            tmp.unlink()
        except Exception:
            pass

    total = 33
    passed = total - failures
    print(f"{'=' * 55}")
    print(f"Result: {passed}/{total} passed")
    print(f"STATUS: {'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    print(f"{'=' * 55}\n")
    return failures


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ORACLE Action Candidates")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.smoke_test:
        sys.exit(run_smoke_tests())
    elif args.list:
        _cli_list()
    else:
        parser.print_help()
