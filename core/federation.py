"""core/federation.py — Federation Replicator / Pattern Buffer engine.

Doctrine (TP_004_FEDERATION_REPLICATOR_PATTERN_BUFFER):
    "Replicate from approved truth; do not manufacture truth."

The pattern buffer holds two things: an approved-truth store (durable canon the
replicator may draw from) and a staging area for candidate records (the approval
queue). This module is the *replicator with a pulse* — it promotes a single
staged candidate into approved canon.

Hard constraints, enforced here, not assumed:
  - It only ever copies the candidate's EXISTING text verbatim. It never
    generates, rewrites, summarizes, or smooths. raw_preserved is always True.
  - Every promotion requires an explicit approver (default Noah.Physical).
  - Secret/credential candidates are refused (reused approval-center guard).
  - Promotion is idempotent: a candidate already replicated to canon is never
    double-written (keyed on source_id).
  - Every promotion writes a receipt to Memory/federation_promotions.jsonl.

This is the live engine behind the Federation pattern-buffer gauge that the
capability broker reports to the operator console.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "core"
MEMORY = ROOT / "Memory"
RECEIPT_FILE = MEMORY / "federation_promotions.jsonl"

for _p in (str(ROOT), str(CORE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DOCTRINE = "Replicate from approved truth; do not manufacture truth."

# Sources whose candidates carry promotable free-text truth. Action/video/obs
# candidates describe *actions or observations*, not stated truth, so they are
# not auto-promotable into canon by this engine.
PROMOTABLE_SOURCES = ("memory",)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _memory_index_path() -> Path:
    return MEMORY / "remember_me" / "index.json"


def _load_memory_candidate(candidate_id: str) -> dict | None:
    idx = _read_json(_memory_index_path())
    if isinstance(idx, dict) and candidate_id in idx and isinstance(idx[candidate_id], dict):
        return idx[candidate_id]
    return None


def _candidate_text(entry: dict) -> str:
    """The candidate's raw text, preferred field order. Never rewritten."""
    for key in ("content", "summary", "title", "value"):
        v = entry.get(key)
        if v and str(v).strip():
            return str(v).strip()
    return ""


def _source_id(source: str, candidate_id: str) -> str:
    return f"federation:{source}:{candidate_id}"


def _already_canon(source_id: str) -> int | None:
    """Return the canon row id if this candidate was already replicated, else None."""
    import memory
    memory.init_db()
    with memory.get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM durable_facts WHERE source_id=? ORDER BY id DESC LIMIT 1",
            (source_id,),
        ).fetchone()
    return int(row["id"]) if row else None


def _persist_receipt(receipt: dict) -> None:
    RECEIPT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with RECEIPT_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(receipt, ensure_ascii=True, sort_keys=True) + "\n")


def canon_count() -> int:
    import memory
    memory.init_db()
    with memory.get_conn() as conn:
        return int(conn.execute("SELECT COUNT(*) AS n FROM durable_facts").fetchone()["n"])


def list_candidates(limit: int = 50) -> list[dict]:
    """Staged candidate records the replicator can promote, with raw text preview.

    Wraps the approval-center pending view but enriches promotable (memory)
    candidates with the verbatim text and a not-yet-replicated flag so the
    operator sees exactly what would enter canon.
    """
    import approval_center as ac
    out: list[dict] = []
    for item in ac.list_pending():
        source = item.get("source", "")
        cid = item.get("id", "")
        promotable = source in PROMOTABLE_SOURCES
        enriched = {
            "source": source,
            "id": cid,
            "title": item.get("title", ""),
            "created_at": item.get("created_at", ""),
            "sensitive_flag": bool(item.get("sensitive_flag", False)),
            "promotable": promotable,
            "raw_text": "",
            "already_canon": False,
        }
        if promotable:
            entry = _load_memory_candidate(cid)
            if entry is not None:
                enriched["raw_text"] = _candidate_text(entry)
                enriched["already_canon"] = _already_canon(_source_id(source, cid)) is not None
        out.append(enriched)
        if len(out) >= limit:
            break
    return out


def promote(candidate_id: str, *, source: str = "memory", approved_by: str = "Noah.Physical") -> dict:
    """Replicate one staged candidate into approved canon. Verbatim, gated, audited.

    Order of operations is recovery-safe: write canon first (idempotent on
    source_id), then mark the source candidate approved, then receipt.
    """
    started = _now()

    if source not in PROMOTABLE_SOURCES:
        return _fail(candidate_id, source, approved_by, started,
                     f"source '{source}' is not promotable into canon by the federation replicator")

    entry = _load_memory_candidate(candidate_id)
    if entry is None:
        return _fail(candidate_id, source, approved_by, started, "candidate not found in staging area")

    raw_text = _candidate_text(entry)
    if not raw_text:
        return _fail(candidate_id, source, approved_by, started, "candidate has no text to replicate")

    # Secret guard — reuse the approval-center policy. Manufacture nothing, leak nothing.
    import approval_center as ac
    if ac._contains_secret(raw_text):
        ac.reject(candidate_id, source=source,
                  reason="AUTO-BLOCKED: secret pattern detected — federation promotion refused")
        return _fail(candidate_id, source, approved_by, started,
                     "candidate contains a secret/credential pattern; refused and auto-rejected")

    source_id = _source_id(source, candidate_id)
    existing = _already_canon(source_id)
    if existing is not None:
        # Already replicated. Idempotent no-op; still ensure the source is marked approved.
        ac.approve(candidate_id, source=source, approved_by=approved_by)
        receipt = _receipt(candidate_id, source, approved_by, started, "noop_already_canon",
                           canon_id=existing, raw_text=raw_text)
        _persist_receipt(receipt)
        return receipt

    # 1) Replicate verbatim into canon with full provenance.
    import memory
    provenance = {
        "source_type": "human_stated",          # Noah-authorized approved truth
        "source_id": source_id,
        "observed_at": entry.get("created_at") or started,
        "confidence": 0.95,
        "transformation_history": [{
            "step": "federation_promotion",
            "by": approved_by,
            "at": started,
            "doctrine": DOCTRINE,
            "raw_preserved": True,
            "from_source": source,
            "candidate_id": candidate_id,
        }],
        "canonical_status": "canon",
        "approval_status": "approved",
    }
    try:
        canon_id = memory.insert_durable_fact(raw_text, provenance)
    except Exception as exc:
        return _fail(candidate_id, source, approved_by, started,
                     f"canon write failed: {type(exc).__name__}: {exc}")

    # 2) Mark the source candidate approved (replicated). Canon already holds it.
    approve_res = ac.approve(candidate_id, source=source, approved_by=approved_by)

    receipt = _receipt(candidate_id, source, approved_by, started, "replicated",
                       canon_id=canon_id, raw_text=raw_text,
                       source_marked=bool(approve_res.get("ok")))
    _persist_receipt(receipt)
    return receipt


def reject(candidate_id: str, *, source: str = "memory", reason: str = "") -> dict:
    """Reject a staged candidate (does not enter canon)."""
    import approval_center as ac
    res = ac.reject(candidate_id, source=source, reason=reason or "federation: rejected by operator")
    receipt = _receipt(candidate_id, source, "Noah.Physical", _now(), "rejected", reason=reason)
    _persist_receipt(receipt)
    receipt["source_result"] = res
    return receipt


def _receipt(candidate_id, source, approved_by, started, status, **extra) -> dict:
    r = {
        "status": status,
        "candidate_id": candidate_id,
        "source": source,
        "approved_by": approved_by,
        "started_at": started,
        "completed_at": _now(),
        "doctrine": DOCTRINE,
    }
    r.update(extra)
    return r


def _fail(candidate_id, source, approved_by, started, blocker) -> dict:
    receipt = _receipt(candidate_id, source, approved_by, started, "blocked", blocker=blocker)
    _persist_receipt(receipt)
    receipt["ok"] = False
    return receipt


def status() -> dict:
    """Live pattern-buffer status: canon size, candidate counts, doctrine."""
    cands = list_candidates()
    promotable = [c for c in cands if c["promotable"] and not c["already_canon"]]
    return {
        "doctrine": DOCTRINE,
        "approved_records": canon_count(),
        "candidate_records_staged": len(cands),
        "promotable_now": len(promotable),
        "next_candidate": promotable[0] if promotable else None,
    }


def format_status() -> str:
    st = status()
    lines = [
        "FEDERATION PATTERN BUFFER",
        f"doctrine: {st['doctrine']}",
        f"approved canon records: {st['approved_records']}",
        f"candidate records staged: {st['candidate_records_staged']}",
        f"promotable now: {st['promotable_now']}",
    ]
    nxt = st["next_candidate"]
    if nxt:
        lines.append(f"next candidate: [{nxt['source']}:{nxt['id']}] {nxt['title']}")
    lines.append("Promote with: /federation-promote <id>")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Federation pattern-buffer replicator")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--promote", metavar="ID")
    ap.add_argument("--reject", metavar="ID")
    ap.add_argument("--reason", default="")
    ap.add_argument("--by", default="Noah.Physical")
    args = ap.parse_args()
    if args.promote:
        print(json.dumps(promote(args.promote, approved_by=args.by), indent=2))
    elif args.reject:
        print(json.dumps(reject(args.reject, reason=args.reason), indent=2))
    elif args.list:
        print(json.dumps(list_candidates(), indent=2))
    else:
        print(format_status())
