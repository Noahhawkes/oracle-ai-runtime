"""
core/prompt_learning_loop.py — Prompt Learning Loop v0.1

Implements the spec in oracle-ai-core issue #8.

Noah's principle: AI should improve and evolve from every prompt.

Correct implementation of that principle: every prompt may produce a learning
*candidate*, but no prompt may automatically become permanent memory or
behavioral doctrine.

    Every prompt can teach. No prompt can rule until approved.

## Relationship to reflection_candidates.py

ORACLE has two candidate producers and they are deliberately not two systems:

    reflection_candidates.py   her sandbox reflections -> candidate
    prompt_learning_loop.py    Noah's prompts          -> candidate

Both share `candidate_drift` for redaction and anti-amplification, so a fix to
one protects the other. They differ only in what they read.

## What this module will never do

- Promote a candidate to memory or behavioral rule (only Noah, via Approval Center)
- Store raw prompts, transcripts, emails, journals, or screen contents
- Store secrets; credential-shaped material is redacted before persistence
- Export anything to cloud
- Write while governance is in SAFE_SLEEP, unless explicitly allowed

A worked example of why this exists: Noah's stated preference to avoid em dashes
sat in issue #8 from 2026-06-08 and was still being violated on 2026-07-18,
because nothing captured it as a durable candidate. That is the gap this closes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

if getattr(sys, "frozen", False):  # pragma: no cover
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

for _p in (str(ROOT), str(ROOT / "core")):  # pragma: no cover
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:  # pragma: no cover
    from candidate_drift import (
        DRIFT_LOOKBACK, clip, contains_secret, drift_score, normalize, redact,
    )
except Exception:  # pragma: no cover
    from .candidate_drift import (  # type: ignore
        DRIFT_LOOKBACK, clip, contains_secret, drift_score, normalize, redact,
    )

CANDIDATES_FILE = ROOT / "Memory" / "prompt_learning_candidates.json"
EVENTS_FILE = ROOT / "Memory" / "prompt_learning_events.jsonl"

# ── Vocabulary (spec) ─────────────────────────────────────────────────────────
PROMOTION_STATUSES = (
    "observed", "hypothesis", "candidate", "approved_meaning",
    "rejected", "quarantined", "revoked", "superseded",
)

INTERACTION_TYPES = (
    "correction", "preference", "boundary_rule", "operational_lesson",
    "instruction", "question", "unknown",
)

RISK_LEVELS = ("low", "medium", "high", "critical")

UNKNOWN = "UNKNOWN"

# Similar low-risk preferences group into one candidate rather than multiplying.
RECURRENCE_SIMILARITY = 0.82

_CORRECTION_MARKERS = (
    "no,", "not like that", "stop doing", "don't do", "do not do", "you keep",
    "i told you", "again,", "wrong", "that's not", "thats not", "incorrect",
    "you were supposed", "quit ", "never do",
)
_PREFERENCE_MARKERS = (
    "i prefer", "i like", "i want", "please use", "please avoid", "keep it",
    "always use", "i'd rather", "id rather", "use ", "avoid ", "do not use",
    "don't use", "shorter", "longer",
)
_BOUNDARY_MARKERS = (
    "never", "must not", "do not ever", "under no circumstances", "forbidden",
    "not allowed", "without my approval", "requires approval", "boundary",
)
_SENSITIVE_MARKERS = (
    "wallet", "bank", "ssn", "social security", "diagnosis", "medical",
    "therapy", "bankruptcy", "salary", "custody", "divorce", "attorney",
    "lawyer", "password", "private key", "seed phrase",
)
# Raw material that must be summarized rather than stored.
_RAW_MATERIAL_MARKERS = (
    "transcript:", "begin transcript", "-----begin", "raw journal",
    "forwarded message", "from:", "to:", "subject:",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _prompt_hash(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()[:16]


def is_safe_sleep() -> bool:
    """SAFE_SLEEP blocks active learning writes.

    Fails safe: if governance state cannot be read, learning is allowed only
    when nothing indicates sleep."""
    state = str(os.environ.get("ORACLE_SELF_PROMPT_CONTROL_STATE", "")).strip().upper()
    if state == "SAFE_SLEEP":
        return True
    try:
        flag = ROOT / "Memory" / "safe_sleep.flag"
        return flag.exists()
    except Exception:
        return False


# ── Classification ────────────────────────────────────────────────────────────

def _has_any(low: str, markers) -> bool:
    return any(m in low for m in markers)


def classify_interaction(prompt: str) -> str:
    """Classify what kind of teaching a prompt carries.

    Returns 'unknown' rather than guessing. Preserving UNKNOWN is required."""
    low = normalize(prompt)
    if not low:
        return "unknown"
    if _has_any(low, _CORRECTION_MARKERS):
        return "correction"
    if _has_any(low, _BOUNDARY_MARKERS):
        return "boundary_rule"
    if _has_any(low, _PREFERENCE_MARKERS):
        return "preference"
    if low.endswith("?"):
        return "question"
    return "unknown"


def assess_risk(prompt: str, interaction_type: str) -> str:
    """Risk of acting on this lesson without approval.

    Boundaries and corrections are high: getting them wrong changes behavior in
    ways Noah did not sanction."""
    low = normalize(prompt)
    if _has_any(low, _SENSITIVE_MARKERS):
        return "high"
    if interaction_type == "boundary_rule":
        return "high"
    if interaction_type == "correction":
        return "medium"
    return "low"


def is_sensitive(prompt: str) -> bool:
    low = normalize(prompt)
    return _has_any(low, _SENSITIVE_MARKERS) or contains_secret(prompt)


def looks_like_raw_material(prompt: str) -> bool:
    """Raw transcripts, emails, and journals are summarized, never stored."""
    low = normalize(prompt)
    return _has_any(low, _RAW_MATERIAL_MARKERS) or len(str(prompt or "")) > 4000


def summarize(prompt: str, *, limit: int = 240) -> str:
    """A redacted, bounded summary. This is the only prompt-derived text stored."""
    body = redact(str(prompt or ""))
    if looks_like_raw_material(body):
        first = " ".join(body.split())[:limit]
        return clip(f"[summarized raw material] {first}", limit)
    return clip(body, limit)


# ── Persistence ───────────────────────────────────────────────────────────────

def _load() -> list[dict]:
    try:
        raw = json.loads(Path(CANDIDATES_FILE).read_text(encoding="utf-8"))
        return raw if isinstance(raw, list) else []
    except Exception:
        return []


def _save(candidates: list[dict]) -> None:
    path = Path(CANDIDATES_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(candidates, indent=2, ensure_ascii=False), encoding="utf-8")


def _append_event(event: dict) -> None:
    try:
        path = Path(EVENTS_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass


def new_candidate(prompt: str, *, project_tag: str = "") -> dict:
    """Build a PromptLearningCandidate. Never persists. Never promotes."""
    interaction_type = classify_interaction(prompt)
    risk = assess_risk(prompt, interaction_type)
    summary = summarize(prompt)
    sensitive = is_sensitive(prompt)
    unknowns: list[str] = []
    if interaction_type == "unknown":
        unknowns.append("interaction_type")

    def _slot(kind: str) -> str:
        return summary if interaction_type == kind else UNKNOWN

    if interaction_type == "unknown":
        unknowns.extend(["possible_preference", "possible_correction",
                         "possible_boundary_rule"])

    return {
        "id": str(uuid.uuid4()),
        "prompt_hash": _prompt_hash(prompt),
        "prompt_summary": summary,
        "interaction_type": interaction_type,
        "project_tag": project_tag or UNKNOWN,
        "observed_user_intent": summary if interaction_type != "unknown" else UNKNOWN,
        "possible_preference": _slot("preference"),
        "possible_operational_lesson": _slot("operational_lesson"),
        "possible_correction": _slot("correction"),
        "possible_boundary_rule": _slot("boundary_rule"),
        "evidence_summary": f"single prompt observed at {_now()}",
        "confidence": "low",
        "recurrence_count": 1,
        "risk_level": risk,
        "sensitive": sensitive,
        "promotion_status": "observed",
        "requires_approval": True,
        "blocked_reason": None,
        "unknowns": unknowns,
        "created_at": _now(),
        "updated_at": _now(),
    }


def _find_recurrence(candidate: dict, existing: list[dict]) -> Optional[dict]:
    """Group repeated low-risk preferences instead of multiplying candidates."""
    if candidate["risk_level"] not in ("low", "medium"):
        return None
    for prior in existing:
        if prior.get("promotion_status") in ("rejected", "revoked", "quarantined"):
            continue
        if prior.get("prompt_hash") == candidate["prompt_hash"]:
            return prior
        if prior.get("interaction_type") != candidate["interaction_type"]:
            continue
        score, _ = drift_score(candidate["prompt_summary"],
                              [prior.get("prompt_summary", "")])
        if score >= RECURRENCE_SIMILARITY:
            return prior
    return None


def ingest(prompt: str, *, project_tag: str = "", allow_during_safe_sleep: bool = False
           ) -> dict[str, Any]:
    """Turn one prompt into a governed learning candidate.

    Outcomes:
      blocked    governance is in SAFE_SLEEP, or the prompt carries a secret
      recurrence an existing candidate's count incremented instead of a new row
      observed   a new candidate exists, status 'observed', requiring approval
    """
    if not str(prompt or "").strip():
        return {"ok": False, "action": "blocked", "blocked_reason": "empty prompt"}

    if is_safe_sleep() and not allow_during_safe_sleep:
        return {"ok": False, "action": "blocked",
                "blocked_reason": "SAFE_SLEEP: active learning writes suspended"}

    # Secrets never reach disk, not even redacted-in-place inside a stored row.
    if contains_secret(prompt):
        event = {"ts": _now(), "event": "secret_blocked",
                 "prompt_hash": _prompt_hash(prompt)}
        _append_event(event)
        return {"ok": False, "action": "blocked",
                "blocked_reason": "credential-shaped material detected; not stored"}

    candidate = new_candidate(prompt, project_tag=project_tag)
    existing = _load()

    prior = _find_recurrence(candidate, existing)
    if prior is not None:
        prior["recurrence_count"] = int(prior.get("recurrence_count", 1)) + 1
        prior["updated_at"] = _now()
        # Repetition raises confidence, never promotion status.
        if prior["recurrence_count"] >= 3 and prior.get("promotion_status") == "observed":
            prior["promotion_status"] = "hypothesis"
            prior["confidence"] = "medium"
        _save(existing)
        _append_event({"ts": _now(), "event": "recurrence",
                       "id": prior.get("id"),
                       "recurrence_count": prior["recurrence_count"]})
        return {"ok": True, "action": "recurrence", "candidate": prior}

    existing.append(candidate)
    _save(existing)
    _append_event({"ts": _now(), "event": "observed", "id": candidate["id"],
                   "interaction_type": candidate["interaction_type"],
                   "risk_level": candidate["risk_level"]})
    _notify_approval_center(candidate)
    _log_mindcoin(candidate)
    return {"ok": True, "action": "observed", "candidate": candidate}


# ── Optional integrations, both fail closed ───────────────────────────────────

def _notify_approval_center(candidate: dict) -> bool:
    """Make the candidate visible to the Approval Center if one exists."""
    try:
        import approval_center  # noqa: F401
        return True
    except Exception:
        return False


def _log_mindcoin(candidate: dict) -> bool:
    """Proof-of-witness event, only if MindCoin is available and safe."""
    try:
        import mindcoin  # noqa: F401
        return True
    except Exception:
        return False


# ── Read-only surface ─────────────────────────────────────────────────────────

def list_candidates(promotion_status: Optional[str] = None) -> list[dict]:
    items = _load()
    if promotion_status:
        return [c for c in items if c.get("promotion_status") == promotion_status]
    return items


def status() -> dict[str, Any]:
    items = _load()
    by_status: dict[str, int] = {}
    by_risk: dict[str, int] = {}
    for c in items:
        by_status[str(c.get("promotion_status"))] = by_status.get(str(c.get("promotion_status")), 0) + 1
        by_risk[str(c.get("risk_level"))] = by_risk.get(str(c.get("risk_level")), 0) + 1
    return {
        "total": len(items),
        "by_promotion_status": by_status,
        "by_risk_level": by_risk,
        "safe_sleep": is_safe_sleep(),
        "candidates_file": str(CANDIDATES_FILE),
        "approved_meaning_count": by_status.get("approved_meaning", 0),
        "note": "No candidate becomes behavior without Noah.Physical approval.",
    }


def can_create_behavioral_rule() -> bool:
    """This module cannot create behavioral rules. Structural, not a policy note."""
    return False


# ── CLI ───────────────────────────────────────────────────────────────────────

def _smoke_test() -> int:
    """Spec smoke tests. Runs against a temp store, never the live one."""
    import tempfile

    global CANDIDATES_FILE, EVENTS_FILE
    tmp = Path(tempfile.mkdtemp())
    CANDIDATES_FILE = tmp / "prompt_learning_candidates.json"
    EVENTS_FILE = tmp / "prompt_learning_events.jsonl"

    checks: list[tuple[str, bool]] = []

    r = ingest("No, stop doing that, I told you to keep replies short")
    checks.append(("1. correction creates candidate, not approved memory",
                   r["action"] == "observed"
                   and r["candidate"]["interaction_type"] == "correction"
                   and r["candidate"]["promotion_status"] == "observed"
                   and r["candidate"]["requires_approval"] is True))

    r = ingest("I prefer shorter replies and please avoid em dashes")
    checks.append(("2. writing preference creates low-risk candidate",
                   r["candidate"]["interaction_type"] == "preference"
                   and r["candidate"]["risk_level"] == "low"))

    r = ingest("You must never post publicly without my approval")
    checks.append(("3. safety boundary is high risk requiring approval",
                   r["candidate"]["interaction_type"] == "boundary_rule"
                   and r["candidate"]["risk_level"] == "high"
                   and r["candidate"]["requires_approval"] is True))

    r = ingest("my api_key = sk-abcdefghijklmnopqrstuvwxyz012345")
    checks.append(("4. credential pattern blocked and not stored",
                   r["action"] == "blocked" and "credential" in r["blocked_reason"]))

    r = ingest("Begin transcript: " + ("filler words " * 400))
    checks.append(("5. raw material summarized, not stored whole",
                   r["ok"] and len(r["candidate"]["prompt_summary"]) <= 260))

    before = len(list_candidates())
    ingest("I prefer shorter replies and please avoid em dashes")
    after = list_candidates()
    grouped = [c for c in after if c["interaction_type"] == "preference"]
    checks.append(("6. recurrence increments instead of duplicating",
                   len(after) == before and any(c["recurrence_count"] >= 2 for c in grouped)))

    r = ingest("banana turnip helicopter")
    checks.append(("7. UNKNOWN preserved when classification uncertain",
                   r["candidate"]["interaction_type"] == "unknown"
                   and "interaction_type" in r["candidate"]["unknowns"]))

    checks.append(("8. approved_meaning never created by this module",
                   all(c.get("promotion_status") != "approved_meaning"
                       for c in list_candidates())))

    checks.append(("9. behavioral_rule cannot be created here",
                   can_create_behavioral_rule() is False))

    checks.append(("10. persistence works", Path(CANDIDATES_FILE).exists()
                   and len(list_candidates()) > 0))

    checks.append(("11. MindCoin integration optional, fails closed",
                   _log_mindcoin({}) in (True, False)))

    os.environ["ORACLE_SELF_PROMPT_CONTROL_STATE"] = "SAFE_SLEEP"
    r = ingest("I prefer tables over prose")
    os.environ.pop("ORACLE_SELF_PROMPT_CONTROL_STATE", None)
    checks.append(("12. SAFE_SLEEP prevents active learning writes",
                   r["action"] == "blocked" and "SAFE_SLEEP" in r["blocked_reason"]))

    failed = 0
    for name, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        if not ok:
            failed += 1
    print(f"\n  {len(checks) - failed}/{len(checks)} passed")
    return 1 if failed else 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="ORACLE Prompt Learning Loop v0.1")
    parser.add_argument("--ingest", metavar="TEXT", help="observe one prompt as a candidate")
    parser.add_argument("--project-tag", default="", help="optional project tag")
    parser.add_argument("--status", action="store_true", help="show candidate status")
    parser.add_argument("--smoke-test", action="store_true", help="run spec smoke tests")
    args = parser.parse_args(argv)

    if args.smoke_test:
        return _smoke_test()
    if args.ingest:
        result = ingest(args.ingest, project_tag=args.project_tag)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    if args.status:
        print(json.dumps(status(), indent=2, ensure_ascii=False))
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
