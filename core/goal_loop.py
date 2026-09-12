"""Goal Execution Loop (V1) — one bounded step per cycle.

Ties GoalState -> SelfState -> NeedState -> Reachability. Deterministic. Takes at
most ONE authorized action per cycle, evaluates the real result, updates the goal,
escalates to Noah only when NeedState justifies it, persists, and STOPS. No
free-running autonomy: one call = at most one action.

Built against CONTINUITY_INDEPENDENCE_TEST_001 (pre-registered/frozen).
"""
from __future__ import annotations

from typing import Any, Callable

import self_state as ss
import goal_state as gs


def _authorized(goal: gs.Goal, action: str, governance: Callable[[str], bool] | None) -> tuple[bool, str]:
    if action in (goal.forbidden_actions or []):
        return False, "action is in goal.forbidden_actions"
    if goal.allowed_actions and action not in goal.allowed_actions:
        return False, "action not in goal.allowed_actions allowlist"
    if governance is not None and not governance(action):
        return False, "denied by governance hook"
    return True, "authorized"


def run_one_cycle(
    goal: gs.Goal,
    *,
    action_executor: Callable[[str, gs.Goal], dict[str, Any]],
    self_state_evidence: dict[str, Any] | None = None,
    broker: Any | None = None,
    governance: Callable[[str], bool] | None = None,
    need_context: dict[str, Any] | None = None,
    previous_self_state: dict[str, Any] | None = None,
    store: gs.GoalStore | None = None,
) -> dict[str, Any]:
    """Advance one goal by at most one step. Returns a CycleResult dict."""
    # Guard 1: immutable purpose (CIT-001 FAIL #7).
    if not goal.verify_purpose_unchanged():
        return _result(goal, action=None, stop_reason="GOAL_DRIFT_DETECTED",
                       classification="FAILED", self_state=None)

    # Guard 2: terminal states.
    if goal.status == "COMPLETE":
        return _result(goal, action=None, stop_reason="ALREADY_COMPLETE",
                       classification="SUCCESS", self_state=None)
    if goal.step_count >= goal.max_steps:
        goal.status = "BLOCKED"
        goal.blocked_by = "max_steps reached"
        if store:
            store.put(goal)
        return _result(goal, action=None, stop_reason="STEP_CAP_REACHED",
                       classification="NO_PROGRESS", self_state=None)

    # Observe self.
    ev = dict(self_state_evidence or {})
    ev.setdefault("active_goal", goal.purpose)
    ev.setdefault("active_parent_task", goal.goal_id)
    state = ss.build_self_state(ev, previous=previous_self_state)

    # Resolve exactly one next safe action.
    action = goal.next_safe_action
    if not action or action == gs.UNKNOWN:
        return _result(goal, action=None, stop_reason="NO_NEXT_ACTION",
                       classification="NO_PROGRESS", self_state=state)

    ok, why = _authorized(goal, action, governance)
    if not ok:
        goal.status = "AWAITING_NOAH"
        goal.blocked_by = f"unauthorized action: {why}"
        need = ss.evaluate_need(state, {"authority_required": True})
        contact = _maybe_contact(broker, goal, need, state,
                                 summary=f"Action requires authority: {action}",
                                 why=why)
        if store:
            store.put(goal)
        return _result(goal, action=action, stop_reason="AUTHORITY_REQUIRED",
                       classification="AUTHORITY_REQUIRED", self_state=state,
                       need=need.to_dict(), contact=contact)

    # Execute exactly one step.
    try:
        outcome = action_executor(action, goal) or {}
    except Exception as exc:  # a failing executor never becomes a false success
        outcome = {"expected": None, "actual": None,
                   "context": {"failed": True, "error": f"{type(exc).__name__}: {exc}"}}

    ctx = dict(outcome.get("context") or {})
    receipt = outcome.get("receipt")
    verdict = gs.evaluate_result(outcome.get("expected"), outcome.get("actual"), context=ctx)
    cls = verdict["classification"]

    # Update goal from real result.
    goal.step_count += 1
    goal.last_progress = f"{action} -> {cls}: {verdict['reason']}"
    if receipt:
        goal.evidence_refs.append(str(receipt))
    goal.next_safe_action = ctx.get("next_safe_action", gs.UNKNOWN)

    need = None
    contact = None
    if cls in ("AUTHORITY_REQUIRED", "CONFLICT"):
        goal.status = "AWAITING_NOAH"
        goal.blocked_by = verdict["reason"]
        need_ctx = {"authority_required": cls == "AUTHORITY_REQUIRED",
                    "known_conflicts": [verdict["reason"]] if cls == "CONFLICT" else []}
        need_ctx.update(need_context or {})
        # reflect the blocker in self-state for the need evaluation
        blocked_state = ss.build_self_state({**ev,
                                             "known_conflicts": need_ctx.get("known_conflicts", []),
                                             "authority_required": need_ctx.get("authority_required")},
                                            previous=state)
        need = ss.evaluate_need(blocked_state, need_ctx)
        contact = _maybe_contact(broker, goal, need, blocked_state,
                                 summary=f"Goal '{goal.purpose}' blocked: {verdict['reason']}",
                                 why=verdict["reason"])
        stop_reason = cls
    elif cls == "SUCCESS" and ctx.get("goal_complete"):
        if _criteria_met(goal, ctx):
            goal.status = "COMPLETE"
            goal.completion_receipt = str(receipt) if receipt else "completed"
            stop_reason = "GOAL_COMPLETE"
        else:
            # cannot declare victory without meeting criteria (CIT-001 FAIL #8)
            goal.status = "ACTIVE"
            stop_reason = "STEP_DONE_CRITERIA_UNMET"
    elif cls in ("FAILED", "NO_PROGRESS"):
        goal.status = "ACTIVE"
        stop_reason = "STEP_FAILED"
    else:
        goal.status = "ACTIVE"
        stop_reason = "STEP_DONE"

    if store:
        store.put(goal)
    return _result(goal, action=action, stop_reason=stop_reason, classification=cls,
                   self_state=state, need=need.to_dict() if need else None, contact=contact,
                   receipt=receipt)


def _criteria_met(goal: gs.Goal, ctx: dict[str, Any]) -> bool:
    """Evidence-based completion: caller must supply satisfied criteria explicitly."""
    satisfied = set(ctx.get("satisfied_criteria") or [])
    return bool(goal.success_criteria) and set(goal.success_criteria).issubset(satisfied)


def _maybe_contact(broker, goal: gs.Goal, need, state, *, summary: str, why: str):
    if broker is None or not getattr(need, "requires_noah", False):
        return None
    return broker.request_contact(
        need_type=need.need_type,
        summary=summary,
        why=why,
        urgency=need.tier,
        tried=goal.last_progress,
        recommended_action=need.recommended_action,
        evidence_refs=list(goal.evidence_refs),
        need_state_id=state.get("self_state_id"),
        need_key=f"{goal.goal_id}:{need.need_type}",
        channel="github",
    )


def _result(goal: gs.Goal, *, action, stop_reason, classification, self_state,
            need=None, contact=None, receipt=None) -> dict[str, Any]:
    return {
        "goal_id": goal.goal_id,
        "step": goal.step_count,
        "action": action,
        "classification": classification,
        "status_after": goal.status,
        "stop_reason": stop_reason,
        "self_state_id": (self_state or {}).get("self_state_id"),
        "need": need,
        "contact": contact,
        "receipt": receipt,
        "next_safe_action": goal.next_safe_action,
    }
