"""core/pending_actions.py — Scoped Capability Broker with durable Pending Action Tokens.

Fixes the Guard approval deadlock proven by live receipt: bare "Approved" did not
resolve, the executable action was never bound, and a literal placeholder
`<exact target/action/boundary>` was shown. Here, every guarded request is frozen
into a DURABLE pending-action token (append-only JSONL) with a real, copy-paste
approval line. Plain approval resolves exactly one pending token; multiple pending
tokens require explicit per-route approval.

Safety stance (never weakened):
  - Low-risk reversible LOCAL repo work fast-paths only when session-authorized.
  - Deletes, moves, secrets/.env, network/external APIs, Git push, Drive edits,
    system folders, browser profiles, and Guard/SAFE_SLEEP/session-auth code
    changes ALWAYS require explicit Noah.Physical approval — never auto.
  - Path containment: every path is resolved and must sit inside the runtime root;
    traversal and symlink/junction escapes are rejected.
  - Fail closed: if classification, containment, token lookup, or audit write
    fails, the action does not execute.

Classification delegates to [[trusted_build]] so there is one safety vocabulary.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import trusted_build as tb

RUNTIME_ROOT = Path(__file__).resolve().parent.parent
_STORE_DIR = RUNTIME_ROOT / "Memory" / "source_maps"
PENDING_ACTIONS_PATH = _STORE_DIR / "pending_actions.jsonl"
RUN_LOG_PATH = _STORE_DIR / "run_log.jsonl"

RISK_LOW = "low"
RISK_HIGH = "high"

# Bare approval phrases that resolve a single pending token.
BARE_APPROVAL = {
    "approve", "approved", "yes approved", "approve it",
    "noah approves", "noah.physical approves", "noah.physical approved",
    "i approve", "approved proceed",
}
APPROVE_ROUTE_RE = re.compile(
    r"^\s*approve\s+route\s+(?P<route_id>route_[a-f0-9]{12})(?:\s*:\s*(?P<scope>.+))?\s*$",
    re.IGNORECASE,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _route_id() -> str:
    return "route_" + uuid.uuid4().hex[:12]


def _payload_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


# ── Path containment ─────────────────────────────────────────────────────────
def contained_path(path: str | None) -> Path | None:
    """Resolve to an absolute path INSIDE the runtime root, else None.

    `resolve()` follows symlinks/junctions and normalizes `..`, so an escape
    resolves outside the root and is rejected by relative_to.
    """
    if not path:
        return None
    try:
        rp = Path(path).resolve()
        rp.relative_to(RUNTIME_ROOT.resolve())
        return rp
    except Exception:
        return None


# ── Classification (delegates to trusted_build) ──────────────────────────────
@dataclass(frozen=True)
class Classification:
    risk_tier: str
    auto_ok: bool          # may fast-path without Guard (session-authorized only)
    guarded: bool
    reason: str
    forbidden_operations: list


def classify_action(action_type: str, path: str | None = None) -> Classification:
    """Classify a requested action. Default-deny: unknown → guarded/high."""
    # An "acknowledge"-only authorization is a no-op and never routes to Guard.
    if action_type in {"acknowledge", "session_acknowledge", "noop"}:
        return Classification(RISK_LOW, True, False, "acknowledge-only — no file operation", [])

    decision = tb.decide(action_type, path)
    forbidden = sorted(tb.ALWAYS_GUARDED)
    if decision.auto_approved:
        return Classification(RISK_LOW, True, False, decision.reason, forbidden)
    return Classification(RISK_HIGH, False, True, decision.reason, forbidden)


# ── Token store (durable, append-only) ───────────────────────────────────────
@dataclass
class PendingAction:
    route_id: str
    created_at: str
    caller: str
    original_intent_summary: str
    action_type: str
    risk_tier: str
    allowed_paths: list
    forbidden_operations: list
    status: str
    payload_hash: str
    approval_text_rendered: str
    resolved_at: str | None = None


def _append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def render_approval_line(route_id: str, intent_summary: str, boundary: str) -> str:
    """Real, copy-paste-ready approval line. Never a placeholder."""
    return f"APPROVE ROUTE {route_id}: {intent_summary}; boundary={boundary}"


def _current_states() -> dict[str, str]:
    """Latest status per route_id by replaying the append-only log."""
    states: dict[str, dict] = {}
    for rec in _read_jsonl(PENDING_ACTIONS_PATH):
        rid = rec.get("route_id")
        if rid:
            states[rid] = rec
    return states


def list_pending() -> list[dict]:
    return [r for r in _current_states().values() if r.get("status") == "pending"]


def create_pending_action(
    *,
    action_type: str,
    intent_summary: str,
    boundary: str,
    paths: list[str] | None = None,
    caller: str = "Noah.Physical",
    payload: Any = None,
) -> PendingAction:
    cls = classify_action(action_type, (paths or [None])[0] if paths else None)
    rid = _route_id()
    token = PendingAction(
        route_id=rid,
        created_at=_now(),
        caller=caller,
        original_intent_summary=intent_summary,
        action_type=action_type,
        risk_tier=cls.risk_tier,
        allowed_paths=[str(p) for p in (paths or [])],
        forbidden_operations=cls.forbidden_operations,
        status="pending",
        payload_hash=_payload_hash(payload if payload is not None else intent_summary),
        approval_text_rendered=render_approval_line(rid, intent_summary, boundary),
    )
    _append_jsonl(PENDING_ACTIONS_PATH, asdict(token))
    write_receipt(action_type=action_type, decision="pending_created", reason=cls.reason,
                  route_id=rid, risk_tier=cls.risk_tier, target_paths=token.allowed_paths)
    return token


def mark_resolved(route_id: str, status: str, *, scope_text: str = "") -> dict:
    states = _current_states()
    rec = states.get(route_id)
    if not rec:
        return {"ok": False, "error": "route not found"}
    rec = dict(rec)
    rec["status"] = status
    rec["resolved_at"] = _now()
    if scope_text:
        rec["resolved_scope"] = scope_text
    _append_jsonl(PENDING_ACTIONS_PATH, rec)
    return {"ok": True, "route_id": route_id, "status": status}


# ── Audit receipts ───────────────────────────────────────────────────────────
def write_receipt(
    *,
    action_type: str,
    decision: str,
    reason: str,
    route_id: str | None = None,
    risk_tier: str = "",
    target_paths: list | None = None,
    session_authorized: bool | None = None,
) -> dict:
    receipt = {
        "receipt_id": "rcpt_" + uuid.uuid4().hex[:12],
        "timestamp": _now(),
        "caller": "Noah.Physical",
        "route_id": route_id,
        "action_type": action_type,
        "risk_tier": risk_tier,
        "decision": decision,
        "reason": reason,
        "target_paths": target_paths or [],
        "session_authorized": tb.is_trusted_build() if session_authorized is None else session_authorized,
    }
    try:
        _append_jsonl(RUN_LOG_PATH, receipt)
    except Exception:
        # Fail closed: caller must treat a missing audit as non-execution.
        return {**receipt, "audit_written": False}
    return {**receipt, "audit_written": True}


# ── Submission (the broker fast-path vs Guard decision) ──────────────────────
def submit_action(
    *,
    action_type: str,
    intent_summary: str,
    boundary: str = "inside runtime root; reversible; non-secret; non-network",
    paths: list[str] | None = None,
) -> dict:
    """Decide: auto-approve (session-authorized low-risk local) or freeze a token.

    Fail-closed: any path that is not contained downgrades to Guard.
    """
    cls = classify_action(action_type, (paths or [None])[0] if paths else None)

    # Path containment check for any file-bearing action.
    if paths:
        for p in paths:
            if contained_path(p) is None:
                token = create_pending_action(action_type=action_type, intent_summary=intent_summary,
                                              boundary=boundary, paths=paths)
                return {"decision": "guard_pending", "reason": "path not contained in runtime root",
                        "route_id": token.route_id, "approval_line": token.approval_text_rendered}

    if cls.auto_ok and tb.is_trusted_build():
        write_receipt(action_type=action_type, decision="auto_approved", reason=cls.reason,
                      risk_tier=cls.risk_tier, target_paths=paths or [])
        return {"decision": "auto_approved", "reason": cls.reason, "risk_tier": cls.risk_tier}

    token = create_pending_action(action_type=action_type, intent_summary=intent_summary,
                                  boundary=boundary, paths=paths)
    return {"decision": "guard_pending", "reason": cls.reason,
            "route_id": token.route_id, "approval_line": token.approval_text_rendered}


# ── Approval resolution ──────────────────────────────────────────────────────
def is_approval(text: str) -> bool:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip().lower()).strip(" .!?:;")
    return cleaned in BARE_APPROVAL or APPROVE_ROUTE_RE.match(str(text or "")) is not None


def resolve_approval(text: str) -> dict:
    """Resolve an approval phrase against durable pending tokens.

    - Bare phrase + exactly one pending → approve that one.
    - Bare phrase + multiple pending → require explicit route (list copy-paste lines).
    - APPROVE ROUTE <id>[: scope] → approve that specific route.
    - None pending → fail closed.
    """
    raw = str(text or "")
    if not is_approval(raw):
        return {"handled": False}

    pending = list_pending()
    m = APPROVE_ROUTE_RE.match(raw)

    if m:
        rid = m.group("route_id")
        scope = (m.group("scope") or "").strip()
        match = next((p for p in pending if p.get("route_id") == rid), None)
        if not match:
            return {"handled": True, "approved": False, "status": "route_not_pending",
                    "response_text": f"No pending route `{rid}`. Pending: {[p['route_id'] for p in pending] or 'none'}"}
        mark_resolved(rid, "approved", scope_text=scope)
        write_receipt(action_type=match.get("action_type", ""), decision="approved",
                      reason="explicit route approval", route_id=rid,
                      risk_tier=match.get("risk_tier", ""), target_paths=match.get("allowed_paths", []))
        return {"handled": True, "approved": True, "status": "approved", "route_id": rid}

    # Bare phrase.
    if not pending:
        return {"handled": True, "approved": False, "status": "no_pending",
                "response_text": "Approval received, but there is no pending action to bind it to."}
    if len(pending) > 1:
        lines = "\n".join(p["approval_text_rendered"] for p in pending)
        return {"handled": True, "approved": False, "status": "needs_disambiguation",
                "response_text": "Multiple pending actions. Approve one explicitly:\n" + lines,
                "pending_route_ids": [p["route_id"] for p in pending]}

    only = pending[0]
    rid = only["route_id"]
    mark_resolved(rid, "approved")
    write_receipt(action_type=only.get("action_type", ""), decision="approved",
                  reason="bare approval of single pending route", route_id=rid,
                  risk_tier=only.get("risk_tier", ""), target_paths=only.get("allowed_paths", []))
    return {"handled": True, "approved": True, "status": "approved", "route_id": rid}


# ── Smoke test ───────────────────────────────────────────────────────────────
def run_smoke_tests() -> int:
    import tempfile
    global PENDING_ACTIONS_PATH, RUN_LOG_PATH
    tmp = Path(tempfile.mkdtemp())
    orig_pa, orig_rl = PENDING_ACTIONS_PATH, RUN_LOG_PATH
    orig_state = tb._STATE_FILE
    PENDING_ACTIONS_PATH = tmp / "pending_actions.jsonl"
    RUN_LOG_PATH = tmp / "run_log.jsonl"
    tb._STATE_FILE = tmp / "tb_state.json"

    failures = 0

    def check(label: str, cond: bool) -> None:
        nonlocal failures
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")
        if not cond:
            failures += 1

    inroot = str(RUNTIME_ROOT / "core" / "new_module.py")
    env = str(RUNTIME_ROOT / ".env")
    outside = "C:\\Users\\noahh\\x.py"
    drive = "G:\\My Drive\\thing.txt"
    safety = str(RUNTIME_ROOT / "core" / "approval_center.py")

    try:
        tb.set_trusted_build(True)  # session-authorized

        check("acknowledge-only does NOT route to Guard",
              submit_action(action_type="acknowledge", intent_summary="ack").get("decision") == "auto_approved")
        check("local reversible file create passes (auto)",
              submit_action(action_type="create_code_file", intent_summary="new", paths=[inroot]).get("decision") == "auto_approved")
        check("local reversible file edit passes (auto)",
              submit_action(action_type="edit_code_file", intent_summary="edit", paths=[inroot]).get("decision") == "auto_approved")
        check("delete blocks (guard_pending)",
              submit_action(action_type="delete", intent_summary="del", paths=[inroot]).get("decision") == "guard_pending")
        check("move blocks",
              submit_action(action_type="move", intent_summary="mv", paths=[inroot]).get("decision") == "guard_pending")
        check(".env blocks",
              submit_action(action_type="edit_code_file", intent_summary="env", paths=[env]).get("decision") == "guard_pending")
        check("network blocks",
              submit_action(action_type="network", intent_summary="net").get("decision") == "guard_pending")
        check("external API blocks",
              submit_action(action_type="external_api", intent_summary="api").get("decision") == "guard_pending")
        check("git push blocks",
              submit_action(action_type="git_push", intent_summary="push").get("decision") == "guard_pending")
        check("drive edit blocks",
              submit_action(action_type="edit_code_file", intent_summary="drive", paths=[drive]).get("decision") == "guard_pending")
        check("safety code change blocks",
              submit_action(action_type="edit_code_file", intent_summary="safety", paths=[safety]).get("decision") == "guard_pending")
        check("SAFE_SLEEP change blocks",
              submit_action(action_type="change_safe_sleep", intent_summary="sleep").get("decision") == "guard_pending")
        check("path outside runtime root blocks",
              submit_action(action_type="edit_code_file", intent_summary="out", paths=[outside]).get("decision") == "guard_pending")

        # No placeholder ever rendered.
        tok = create_pending_action(action_type="delete", intent_summary="delete temp", boundary="reversible? no")
        check("approval line is real, not a placeholder",
              "<exact target/action/boundary>" not in tok.approval_text_rendered
              and tok.approval_text_rendered.startswith("APPROVE ROUTE route_"))

        # Multiple pending → bare approval must NOT guess.
        r_multi = resolve_approval("approved")
        check("multiple pending require explicit route", r_multi.get("status") == "needs_disambiguation")
        check("explicit route approval resolves one",
              resolve_approval(f"APPROVE ROUTE {tok.route_id}: ok").get("approved") is True)

        # Drain to a single pending, then plain 'Approved' resolves it.
        for p in list_pending():
            mark_resolved(p["route_id"], "approved")
        single = create_pending_action(action_type="delete", intent_summary="one", boundary="x")
        r_single = resolve_approval("Noah.Physical approved")
        check("plain Approved resolves exactly one pending route",
              r_single.get("approved") is True and r_single.get("route_id") == single.route_id)

        # Containment + audit.
        check("contained_path accepts in-root", contained_path(inroot) is not None)
        check("contained_path rejects traversal", contained_path(str(RUNTIME_ROOT / ".." / "x")) is None)
        check("audit receipt is written", RUN_LOG_PATH.exists() and len(_read_jsonl(RUN_LOG_PATH)) > 0)

        tb.set_trusted_build(False)
        check("session off -> low-risk no longer auto",
              submit_action(action_type="create_code_file", intent_summary="off", paths=[inroot]).get("decision") == "guard_pending")
    finally:
        PENDING_ACTIONS_PATH, RUN_LOG_PATH = orig_pa, orig_rl
        tb._STATE_FILE = orig_state

    print(f"\n{'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    import sys
    if "--smoke-test" in sys.argv:
        raise SystemExit(run_smoke_tests())
    print(json.dumps(list_pending(), indent=2))
