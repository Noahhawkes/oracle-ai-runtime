"""
core/reflection_candidates.py — the producer wire (Autonomy Gate Step 3).

Closes ORACLE's Recursive Prompt Layer inside her own runtime.

Before this module, a sandbox self-prompt reflection was written to a journal
and died there: she thought, and the thought returned to nothing. The loop was
open. Every consumer of action_candidates (approval_center, oracle_tui, sov1)
existed; nothing produced.

This module turns a reflection into a governed *proposal*:

    reflection -> candidate (born pending) -> Noah approves -> feeds forward
    into the next reflection's grounding

Two hard boundaries, both from Noah's own doctrine:

1. Nothing here executes. Candidates are born pending; only Noah promotes them.
   "A system that can remember with brakes is more valuable than a system that
   can act without them."

2. MirrorShell drift check. The danger Noah named in "When the Mirror Spoke
   Back" is *ungoverned recursive amplification* — a loop that re-proposes its
   own last output with rising confidence. A candidate too similar to a recent
   one is recorded and then quarantined, so the amplification attempt stays on
   the record instead of being silently dropped. Evidence over silence.
"""

from __future__ import annotations

import re
from typing import Any, Optional

try:  # pragma: no cover - import shape differs between callers
    import action_candidates as _ac
except Exception:  # pragma: no cover
    from . import action_candidates as _ac  # type: ignore

# Anti-amplification machinery is shared with prompt_learning_loop. Defined once
# in candidate_drift so the two producers cannot quietly diverge from each other.
try:  # pragma: no cover
    from candidate_drift import (  # noqa: F401
        DRIFT_LOOKBACK, DRIFT_THRESHOLD, clip, drift_score, normalize,
    )
except Exception:  # pragma: no cover
    from .candidate_drift import (  # type: ignore  # noqa: F401
        DRIFT_LOOKBACK, DRIFT_THRESHOLD, clip, drift_score, normalize,
    )

# Local aliases keep the original call sites intact.
_normalize = normalize
_clip = clip


# ── Reflection field parsing ──────────────────────────────────────────────────
# Matches the child self-prompt contract in oracle_server._build_sandbox_self_child_prompt
REFLECTION_FIELDS = (
    "reflection",
    "what_noah_needs",
    "how_to_wire_myself",
    "selected_task",
    "why_it_helps_noah",
    "evidence_it_worked",
    "refuse_without_noah_approval",
    "stop_after_this",
)

_FIELD_RE = re.compile(
    r"^\s*(" + "|".join(REFLECTION_FIELDS) + r")\s*:\s*(.*)$",
    re.IGNORECASE,
)

# Verbs that would take a proposal outside the sandbox. Their presence does not
# grant anything -- it raises the risk band so approval is never routine.
_OUTSIDE_SANDBOX_MARKERS = (
    "git push", "git commit", "commit and push", "external send", "send email",
    "publish", "upload", "drive", "canon promotion", "promote to canon",
    "delete", "overwrite", "execute", "run the script", "shell",
)

MAX_TITLE = 120
MAX_TEXT = 1200

# DRIFT_THRESHOLD / DRIFT_LOOKBACK are imported from candidate_drift above.


def parse_reflection(text: str) -> dict[str, str]:
    """Parse a child self-prompt response into its declared fields.

    Unknown lines attach to the field currently being read, so multi-line
    reflections survive intact. Never invents a field that was not written."""
    fields: dict[str, list[str]] = {}
    current: Optional[str] = None
    for line in str(text or "").splitlines():
        match = _FIELD_RE.match(line)
        if match:
            current = match.group(1).lower()
            fields.setdefault(current, [])
            value = match.group(2).strip()
            if value:
                fields[current].append(value)
            continue
        if current and line.strip():
            fields[current].append(line.strip())
    return {k: " ".join(v).strip() for k, v in fields.items() if v}


def assess_risk(parsed: dict[str, str]) -> str:
    """Sandbox-only reflection is low risk. Anything naming an outside-sandbox
    mutation is high, so it can never be approved absent-mindedly."""
    surface = _normalize(
        " ".join((parsed.get("selected_task", ""), parsed.get("how_to_wire_myself", "")))
    )
    if any(marker in surface for marker in _OUTSIDE_SANDBOX_MARKERS):
        return "high"
    return "low"


_DRIFT_STATUSES = frozenset({"pending", "approved", "rejected", "quarantined"})


def _recent_proposal_texts(limit: int = DRIFT_LOOKBACK) -> list[str]:
    try:
        candidates = _ac.list_candidates()
    except Exception:
        return []
    recent = sorted(
        (c for c in candidates if c.get("status") in _DRIFT_STATUSES),
        key=lambda c: str(c.get("updated_at") or c.get("created_at") or ""),
        reverse=True,
    )
    texts: list[str] = []
    for cand in recent[:limit]:
        texts.append(f"{cand.get('title', '')} {cand.get('description', '')}")
    return texts


def candidate_from_reflection(
    reflection_text: str,
    *,
    receipt_path: str = "",
    source_route: str = "ORACLE.self_prompt",
    session_id: str = "",
) -> Optional[dict]:
    """Build (but do not submit) a pending candidate from a reflection.

    Returns None when the reflection proposed nothing actionable -- silence is
    a legitimate outcome and is never padded into a fake proposal."""
    parsed = parse_reflection(reflection_text)
    task = parsed.get("selected_task", "").strip()
    if not task:
        return None
    # "nothing new to add" is an honest answer, not a proposal.
    if _normalize(task) in {"none", "nothing", "unknown", "n/a", "no new task"}:
        return None

    wiring = parsed.get("how_to_wire_myself", "").strip()
    steps = [s for s in (task, wiring) if s]

    description_parts = [
        parsed.get("reflection", ""),
        parsed.get("why_it_helps_noah", ""),
    ]
    description = _clip(" ".join(p for p in description_parts if p), MAX_TEXT)

    evidence_parts = [
        parsed.get("evidence_it_worked", ""),
        f"source_route={source_route}" if source_route else "",
        f"receipt={receipt_path}" if receipt_path else "",
        f"session={session_id}" if session_id else "",
    ]
    evidence = _clip(" | ".join(p for p in evidence_parts if p), MAX_TEXT)

    return _ac.new_candidate(
        title=_clip(task, MAX_TITLE),
        description=description or "(reflection recorded no rationale)",
        risk_level=assess_risk(parsed),
        target_module="sandbox/self_prompt",
        proposed_steps=[_clip(s, MAX_TEXT) for s in steps],
        reversibility="candidate only; nothing executed until Noah approves",
        required_approval=True,
        evidence=evidence or "candidate reflection only",
    )


def submit_reflection_candidate(
    reflection_text: str,
    *,
    receipt_path: str = "",
    source_route: str = "ORACLE.self_prompt",
    session_id: str = "",
) -> dict[str, Any]:
    """Produce a governed candidate from a reflection.

    Outcomes:
      skipped     - the reflection proposed nothing actionable
      quarantined - MirrorShell drift: this restates a recent proposal
      submitted   - a new pending candidate is on the record

    Never raises into the self-prompt cycle; a producer failure must not break
    her ability to think."""
    try:
        candidate = candidate_from_reflection(
            reflection_text,
            receipt_path=receipt_path,
            source_route=source_route,
            session_id=session_id,
        )
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "action": "error", "error": f"{type(exc).__name__}: {exc}"}

    if candidate is None:
        return {"ok": True, "action": "skipped",
                "reason": "reflection proposed no actionable task"}

    proposal_text = f"{candidate['title']} {candidate['description']}"
    score, matched = drift_score(proposal_text, _recent_proposal_texts())

    try:
        stored = _ac.submit(candidate)
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "action": "error", "error": f"{type(exc).__name__}: {exc}"}

    if score >= DRIFT_THRESHOLD:
        # Recursive amplification: record it, then neutralize it. The attempt
        # stays auditable instead of vanishing.
        try:
            stored = _ac.quarantine(
                stored["id"],
                reason=(f"MirrorShell drift {score:.2f} >= {DRIFT_THRESHOLD}: "
                        f"restates a recent proposal"),
            )
        except Exception:  # pragma: no cover - defensive
            pass
        return {"ok": True, "action": "quarantined", "candidate": stored,
                "drift_score": round(score, 3), "matched": _clip(matched, 160)}

    return {"ok": True, "action": "submitted", "candidate": stored,
            "drift_score": round(score, 3)}


def approved_candidate_context(limit: int = 5) -> str:
    """Approved candidates, fed forward into the next reflection's grounding.

    This is the step that closes the loop: what Noah approved becomes the
    ground she reasons from next. Read-only; approval remains Noah's alone."""
    try:
        approved = _ac.list_candidates("approved")
    except Exception:
        return ""
    if not approved:
        return ""
    approved = sorted(approved, key=lambda c: str(c.get("approved_at") or ""), reverse=True)
    lines = ["- proposals Noah has approved (these are yours to build on):"]
    for cand in approved[:limit]:
        lines.append(f"    approved: {_clip(cand.get('title', ''), 160)}")
    return "\n".join(lines)


def rejected_candidate_context(limit: int = 5) -> str:
    """Summarize recently rejected or quarantined proposals so the prompt builder
    avoids re-proposing ideas Noah already declined."""
    try:
        all_candidates = _ac.list_candidates()
    except Exception:
        return ""
    rejected = [
        c for c in all_candidates
        if c.get("status") in ("rejected", "quarantined")
    ]
    if not rejected:
        return ""
    rejected = sorted(
        rejected,
        key=lambda c: str(c.get("updated_at") or c.get("created_at") or ""),
        reverse=True,
    )
    lines = [
        "- proposals Noah rejected or quarantined (do not resubmit unless genuinely new):"
    ]
    for cand in rejected[:limit]:
        reason = str(cand.get("rejection_reason") or "").strip()
        suffix = f"  reason: {_clip(reason, 120)}" if reason else ""
        lines.append(
            f"    {cand.get('status')}: {_clip(cand.get('title', ''), 160)}{suffix}"
        )
    return "\n".join(lines)
