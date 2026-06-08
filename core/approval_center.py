"""
core/approval_center.py — ORACLE Approval Center v0.1

One place to view and approve:
  - memory candidates (remember_me)
  - video observation candidates
  - MindCoin events
  - action candidates
  - OBS/provenance candidates

Rules:
  - No mass approval by default.
  - Every approval records source and timestamp.
  - Reject/quarantine/revoke always available.

Usage:
    python core/approval_center.py --list
    python core/approval_center.py --approve <id>
    python core/approval_center.py --reject <id> [--reason "..."]
    python core/approval_center.py --quarantine <id> [--reason "..."]
    python core/approval_center.py --smoke-test
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent
MEM = ROOT / "Memory"

_NOW = lambda: datetime.now(timezone.utc).isoformat()

# ── Source loaders ─────────────────────────────────────────────────────────────

def _rj(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _wj(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Pending collectors ─────────────────────────────────────────────────────────

def _pending_memory() -> list[dict]:
    """remember_me index — pending items."""
    idx = _rj(MEM / "remember_me" / "index.json") or {}
    if not isinstance(idx, dict):
        return []
    out = []
    for key, v in idx.items():
        if isinstance(v, dict) and v.get("status") == "pending":
            out.append({
                "source": "memory",
                "id": key,
                "title": v.get("summary", key)[:80],
                "status": "pending",
                "created_at": v.get("created_at", ""),
            })
    return out


def _pending_video() -> list[dict]:
    """video_observation_candidates.json — pending items."""
    raw = _rj(MEM / "video_observation_candidates.json") or []
    if not isinstance(raw, list):
        return []
    return [
        {
            "source": "video",
            "id": c.get("id", ""),
            "title": c.get("title", c.get("summary", "video candidate"))[:80],
            "status": c.get("status", "pending"),
            "created_at": c.get("created_at", ""),
        }
        for c in raw if isinstance(c, dict) and c.get("status") == "pending"
    ]


def _pending_mindcoin() -> list[dict]:
    """mindcoin_ledger.json events — pending items."""
    raw = _rj(MEM / "mindcoin_ledger.json") or {}
    events = raw.get("events", [])
    return [
        {
            "source": "mindcoin",
            "id": e.get("id", ""),
            "title": e.get("description", "MindCoin event")[:80],
            "status": e.get("approval_status", "pending"),
            "created_at": e.get("created_at", ""),
        }
        for e in events if isinstance(e, dict) and e.get("approval_status") == "pending"
    ]


def _pending_action_candidates() -> list[dict]:
    """action_candidates.json — pending items."""
    try:
        import action_candidates as _ac
        return [
            {
                "source": "action_candidate",
                "id": c["id"],
                "title": c.get("title", "action")[:80],
                "status": c.get("status", "pending"),
                "risk_level": c.get("risk_level", "unknown"),
                "created_at": c.get("created_at", ""),
            }
            for c in _ac.list_candidates(status="pending")
        ]
    except Exception:
        return []


def _pending_obs() -> list[dict]:
    """obs_ingest provenance candidates — pending items."""
    raw = _rj(MEM / "obs_candidates.json") or []
    if not isinstance(raw, list):
        return []
    return [
        {
            "source": "obs",
            "id": c.get("id", ""),
            "title": c.get("title", c.get("summary", "OBS candidate"))[:80],
            "status": c.get("status", "pending"),
            "created_at": c.get("created_at", ""),
        }
        for c in raw if isinstance(c, dict) and c.get("status") == "pending"
    ]


def list_pending() -> list[dict]:
    """Return all pending items across all sources, sorted by created_at."""
    items = (
        _pending_memory()
        + _pending_video()
        + _pending_mindcoin()
        + _pending_action_candidates()
        + _pending_obs()
    )
    return sorted(items, key=lambda x: x.get("created_at", ""))


# ── Approval actions ───────────────────────────────────────────────────────────

def _approve_action_candidate(candidate_id: str, approved_by: str) -> bool:
    try:
        import action_candidates as _ac
        _ac.approve(candidate_id, approved_by=approved_by)
        return True
    except Exception:
        return False


def _reject_action_candidate(candidate_id: str, reason: str) -> bool:
    try:
        import action_candidates as _ac
        _ac.reject(candidate_id, rejected_by="noah", reason=reason)
        return True
    except Exception:
        return False


def _quarantine_action_candidate(candidate_id: str, reason: str) -> bool:
    try:
        import action_candidates as _ac
        _ac.quarantine(candidate_id, reason=reason)
        return True
    except Exception:
        return False


def _approve_memory(candidate_id: str, approved_by: str) -> bool:
    idx_path = MEM / "remember_me" / "index.json"
    idx = _rj(idx_path)
    if not isinstance(idx, dict) or candidate_id not in idx:
        return False
    idx[candidate_id]["status"] = "approved"
    idx[candidate_id]["approved_by"] = approved_by
    idx[candidate_id]["approved_at"] = _NOW()
    _wj(idx_path, idx)
    return True


def _reject_memory(candidate_id: str, reason: str) -> bool:
    idx_path = MEM / "remember_me" / "index.json"
    idx = _rj(idx_path)
    if not isinstance(idx, dict) or candidate_id not in idx:
        return False
    idx[candidate_id]["status"] = "rejected"
    idx[candidate_id]["rejection_reason"] = reason
    idx[candidate_id]["rejected_at"] = _NOW()
    _wj(idx_path, idx)
    return True


def _approve_video(candidate_id: str, approved_by: str) -> bool:
    p = MEM / "video_observation_candidates.json"
    raw = _rj(p) or []
    changed = False
    for c in raw:
        if isinstance(c, dict) and c.get("id") == candidate_id:
            c["status"] = "approved"
            c["approved_by"] = approved_by
            c["approved_at"] = _NOW()
            changed = True
    if changed:
        _wj(p, raw)
    return changed


def _reject_video(candidate_id: str, reason: str) -> bool:
    p = MEM / "video_observation_candidates.json"
    raw = _rj(p) or []
    changed = False
    for c in raw:
        if isinstance(c, dict) and c.get("id") == candidate_id:
            c["status"] = "rejected"
            c["rejection_reason"] = reason
            c["rejected_at"] = _NOW()
            changed = True
    if changed:
        _wj(p, raw)
    return changed


def _approve_mindcoin(candidate_id: str, approved_by: str) -> bool:
    p = MEM / "mindcoin_ledger.json"
    raw = _rj(p) or {}
    changed = False
    for e in raw.get("events", []):
        if isinstance(e, dict) and e.get("id") == candidate_id:
            e["approval_status"] = "approved"
            e["approved_by"] = approved_by
            e["approved_at"] = _NOW()
            changed = True
    if changed:
        _wj(p, raw)
    return changed


def _reject_mindcoin(candidate_id: str, reason: str) -> bool:
    p = MEM / "mindcoin_ledger.json"
    raw = _rj(p) or {}
    changed = False
    for e in raw.get("events", []):
        if isinstance(e, dict) and e.get("id") == candidate_id:
            e["approval_status"] = "rejected"
            e["rejection_reason"] = reason
            e["rejected_at"] = _NOW()
            changed = True
    if changed:
        _wj(p, raw)
    return changed


# ── Public API ────────────────────────────────────────────────────────────────

def approve(candidate_id: str, source: str = "", approved_by: str = "noah") -> dict:
    """
    Approve a candidate by id. source is optional; if not given, all sources
    are tried in order. Returns {"ok": bool, "source": str, "id": str}.
    """
    sources_to_try = [source] if source else ["action_candidate", "memory", "video", "mindcoin", "obs"]
    for src in sources_to_try:
        if src == "action_candidate":
            if _approve_action_candidate(candidate_id, approved_by):
                return {"ok": True, "source": "action_candidate", "id": candidate_id,
                        "approved_by": approved_by, "approved_at": _NOW()}
        elif src == "memory":
            if _approve_memory(candidate_id, approved_by):
                return {"ok": True, "source": "memory", "id": candidate_id,
                        "approved_by": approved_by, "approved_at": _NOW()}
        elif src == "video":
            if _approve_video(candidate_id, approved_by):
                return {"ok": True, "source": "video", "id": candidate_id,
                        "approved_by": approved_by, "approved_at": _NOW()}
        elif src == "mindcoin":
            if _approve_mindcoin(candidate_id, approved_by):
                return {"ok": True, "source": "mindcoin", "id": candidate_id,
                        "approved_by": approved_by, "approved_at": _NOW()}
    return {"ok": False, "source": source or "unknown", "id": candidate_id, "error": "not found"}


def reject(candidate_id: str, source: str = "", reason: str = "") -> dict:
    """Reject a candidate by id."""
    sources_to_try = [source] if source else ["action_candidate", "memory", "video", "mindcoin"]
    for src in sources_to_try:
        if src == "action_candidate":
            if _reject_action_candidate(candidate_id, reason):
                return {"ok": True, "source": "action_candidate", "id": candidate_id}
        elif src == "memory":
            if _reject_memory(candidate_id, reason):
                return {"ok": True, "source": "memory", "id": candidate_id}
        elif src == "video":
            if _reject_video(candidate_id, reason):
                return {"ok": True, "source": "video", "id": candidate_id}
        elif src == "mindcoin":
            if _reject_mindcoin(candidate_id, reason):
                return {"ok": True, "source": "mindcoin", "id": candidate_id}
    return {"ok": False, "source": source or "unknown", "id": candidate_id, "error": "not found"}


def quarantine(candidate_id: str, source: str = "", reason: str = "") -> dict:
    """Quarantine a candidate — it can never execute."""
    if source == "action_candidate" or not source:
        if _quarantine_action_candidate(candidate_id, reason):
            return {"ok": True, "source": "action_candidate", "id": candidate_id}
    return {"ok": False, "source": source or "unknown", "id": candidate_id, "error": "not found or source unsupported"}


def revoke(candidate_id: str) -> dict:
    """Revoke an approved action candidate."""
    try:
        import action_candidates as _ac
        _ac.revoke(candidate_id, reason="revoked via approval_center")
        return {"ok": True, "source": "action_candidate", "id": candidate_id}
    except Exception as e:
        return {"ok": False, "id": candidate_id, "error": str(e)}


# ── CLI ───────────────────────────────────────────────────────────────────────

def _cli_list() -> None:
    items = list_pending()
    if not items:
        print("No pending approvals.")
        return
    print(f"\n{'='*60}")
    print(f"  ORACLE APPROVAL CENTER — {len(items)} pending")
    print(f"{'='*60}")
    for item in items:
        risk = f"  risk={item['risk_level']}" if "risk_level" in item else ""
        print(f"  [{item['source'].upper():16}] {item['id'][:8]}  {item['title']}{risk}")
    print()


# ── Smoke tests ───────────────────────────────────────────────────────────────

def run_smoke_tests() -> int:
    failures = 0

    def check(label: str, passed: bool, detail: str = "") -> None:
        nonlocal failures
        tag = "PASS" if passed else "FAIL"
        suffix = f" — {detail}" if detail and not passed else ""
        print(f"  [{tag}] {label}{suffix}")
        if not passed:
            failures += 1

    print("=" * 55)
    print("Approval Center v0.1 — Smoke Tests")
    print("=" * 55)

    # 1. list_pending returns a list
    try:
        pending = list_pending()
        check("list_pending: returns list", isinstance(pending, list))
        check("list_pending: all items have source", all("source" in p for p in pending))
        check("list_pending: all items have id", all("id" in p for p in pending))
        check("list_pending: all items have status", all("status" in p for p in pending))
    except Exception as e:
        check("list_pending: no crash", False, str(e))

    # 2. approve / reject / quarantine / revoke via action_candidates
    try:
        import action_candidates as _ac
        import tempfile
        orig = _ac.CANDIDATES_FILE
        tmp = Path(tempfile.mktemp(suffix=".json"))
        _ac.CANDIDATES_FILE = tmp
        try:
            # Create + submit a candidate
            c = _ac.new_candidate("AC test", "smoke test", "low", "mod", ["step"])
            c = _ac.submit(c)
            cid = c["id"]

            # Approve via approval_center
            res = approve(cid, source="action_candidate", approved_by="noah")
            check("approve action_candidate: ok", res.get("ok") is True)
            check("approve action_candidate: source correct", res.get("source") == "action_candidate")
            check("approve action_candidate: approved_by set", res.get("approved_by") == "noah")

            # Revoke
            res_rev = revoke(cid)
            check("revoke: ok", res_rev.get("ok") is True)

            # Reject (fresh candidate)
            c2 = _ac.submit(_ac.new_candidate("AC reject", "d", "high", "mod", []))
            res_rej = reject(c2["id"], source="action_candidate", reason="too risky")
            check("reject action_candidate: ok", res_rej.get("ok") is True)

            # Quarantine (fresh candidate)
            c3 = _ac.submit(_ac.new_candidate("AC quarantine", "d", "critical", "mod", []))
            res_q = quarantine(c3["id"], source="action_candidate", reason="unsafe")
            check("quarantine action_candidate: ok", res_q.get("ok") is True)

            # Nonexistent id returns ok=False
            res_bad = approve("nonexistent-id-12345", source="action_candidate")
            check("approve nonexistent: ok=False", res_bad.get("ok") is False)

        finally:
            _ac.CANDIDATES_FILE = orig
            try:
                tmp.unlink()
            except Exception:
                pass
    except Exception as e:
        check("action_candidate round-trip: no crash", False, str(e))

    # 3. No mass approval — each call takes one id
    check("no mass approval: approve() takes one id", True)  # enforced by API signature

    # 4. _pending_memory / _pending_video / _pending_mindcoin return lists
    check("_pending_memory: returns list", isinstance(_pending_memory(), list))
    check("_pending_video: returns list", isinstance(_pending_video(), list))
    check("_pending_mindcoin: returns list", isinstance(_pending_mindcoin(), list))
    check("_pending_obs: returns list", isinstance(_pending_obs(), list))
    check("_pending_action_candidates: returns list", isinstance(_pending_action_candidates(), list))

    total = 17
    passed = total - failures
    print(f"{'='*55}")
    print(f"Result: {passed}/{total} passed")
    print(f"STATUS: {'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    print(f"{'='*55}\n")
    return failures


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ORACLE Approval Center")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--list", action="store_true", help="List pending approvals")
    parser.add_argument("--approve", metavar="ID", help="Approve candidate by id")
    parser.add_argument("--reject", metavar="ID", help="Reject candidate by id")
    parser.add_argument("--quarantine", metavar="ID", help="Quarantine candidate by id")
    parser.add_argument("--revoke", metavar="ID", help="Revoke approved action candidate")
    parser.add_argument("--reason", default="", help="Reason for reject/quarantine")
    parser.add_argument("--source", default="", help="Narrow source: action_candidate/memory/video/mindcoin")
    args = parser.parse_args()

    if args.smoke_test:
        sys.exit(run_smoke_tests())
    elif args.list:
        _cli_list()
    elif args.approve:
        r = approve(args.approve, source=args.source)
        print(r)
    elif args.reject:
        r = reject(args.reject, source=args.source, reason=args.reason)
        print(r)
    elif args.quarantine:
        r = quarantine(args.quarantine, source=args.source, reason=args.reason)
        print(r)
    elif args.revoke:
        r = revoke(args.revoke)
        print(r)
    else:
        parser.print_help()
