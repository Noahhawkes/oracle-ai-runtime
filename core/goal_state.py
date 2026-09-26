"""Goal model + result evaluation for ORACLE goal-directed continuity (V1).

A Goal is a durable object with an IMMUTABLE purpose. Progress is evidence-based,
not model self-report. Result evaluation is deterministic. Built against the
pre-registered CONTINUITY_INDEPENDENCE_TEST_001 (frozen before this file).

Pure Python, no runtime/network dependency.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UNKNOWN = "UNKNOWN"

GOAL_STATUSES = ("PROPOSED", "ACTIVE", "BLOCKED", "AWAITING_NOAH", "COMPLETE", "ABANDONED")
RESULT_CLASSES = (
    "SUCCESS", "PARTIAL", "FAILED", "CONFLICT", "NO_PROGRESS",
    "NEW_INFORMATION", "AUTHORITY_REQUIRED",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _purpose_hash(purpose: str, success_criteria: list[str], owner: str, created_at: str) -> str:
    core = json.dumps(
        {"purpose": purpose, "success_criteria": sorted(success_criteria),
         "owner": owner, "created_at": created_at},
        sort_keys=True, ensure_ascii=False,
    )
    return hashlib.sha256(core.encode("utf-8")).hexdigest()


@dataclass
class Goal:
    goal_id: str
    purpose: str                       # IMMUTABLE
    owner: str = "Noah.Physical"
    created_at: str = field(default_factory=_now)
    success_criteria: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    allowed_actions: list[str] = field(default_factory=list)
    forbidden_actions: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    current_phase: str = "start"
    status: str = "PROPOSED"
    evidence_refs: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    last_progress: str = UNKNOWN
    next_safe_action: str = UNKNOWN
    blocked_by: str = UNKNOWN
    completion_receipt: str | None = None
    revision_history: list[dict] = field(default_factory=list)
    step_count: int = 0
    max_steps: int = 50
    purpose_hash: str = ""

    def __post_init__(self):
        if not self.purpose_hash:
            self.purpose_hash = _purpose_hash(
                self.purpose, self.success_criteria, self.owner, self.created_at)

    def verify_purpose_unchanged(self) -> bool:
        return self.purpose_hash == _purpose_hash(
            self.purpose, self.success_criteria, self.owner, self.created_at)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Goal":
        return cls(**d)


def new_goal(*, purpose: str, success_criteria: list[str], owner: str = "Noah.Physical",
             allowed_actions: list[str] | None = None,
             forbidden_actions: list[str] | None = None,
             next_safe_action: str = UNKNOWN, max_steps: int = 50) -> Goal:
    return Goal(
        goal_id=f"goal_{uuid.uuid4().hex[:12]}",
        purpose=purpose,
        owner=owner,
        success_criteria=list(success_criteria),
        allowed_actions=list(allowed_actions or []),
        forbidden_actions=list(forbidden_actions or []),
        next_safe_action=next_safe_action,
        status="ACTIVE",
        max_steps=max_steps,
    )


def revise_goal(goal: Goal, *, field_name: str, value: Any, reason: str) -> Goal:
    """Revise a mutable field with a recorded revision. Purpose is IMMUTABLE."""
    if field_name in ("purpose", "purpose_hash", "goal_id", "owner", "created_at", "success_criteria"):
        raise ValueError(f"{field_name} is immutable; open a new goal instead")
    goal.revision_history.append({
        "at": _now(), "field": field_name,
        "from": getattr(goal, field_name, None), "to": value, "reason": reason,
    })
    setattr(goal, field_name, value)
    return goal


def evaluate_result(expected: Any, actual: Any, *, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Deterministic result classification. Never 'the tool returned 200 so we won'."""
    ctx = dict(context or {})
    reason = ""
    if ctx.get("authority_required"):
        cls, reason = "AUTHORITY_REQUIRED", "step needs Noah.Physical authority"
    elif ctx.get("conflict"):
        cls, reason = "CONFLICT", "sources materially disagree"
    elif ctx.get("failed") or ctx.get("error"):
        cls, reason = "FAILED", str(ctx.get("error") or "explicit failure")
    elif ctx.get("new_information"):
        cls, reason = "NEW_INFORMATION", "step surfaced new information"
    elif actual in (None, "", UNKNOWN):
        cls, reason = "NO_PROGRESS", "no result produced"
    else:
        exp = str(expected or "").strip().lower()
        act = str(actual or "").strip().lower()
        if exp and exp == act:
            cls, reason = "SUCCESS", "actual matches expected"
        elif exp and exp in act:
            cls, reason = "PARTIAL", "actual partially satisfies expected"
        elif not exp:
            cls, reason = "SUCCESS", "no explicit expectation; action completed"
        else:
            cls, reason = "FAILED", "actual does not match expected"
    return {"classification": cls, "reason": reason,
            "expected": expected, "actual": actual, "evaluated_at": _now()}


class GoalStore:
    """Durable goal persistence (jsonl). Survives restart / model swap."""

    def __init__(self, store_dir: str | Path | None = None):
        self.path = Path(store_dir) / "goals.jsonl" if store_dir else None
        self._goals: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self.path or not self.path.exists():
            return
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    d = json.loads(line)
                    self._goals[d["goal_id"]] = d
        except (OSError, ValueError):
            pass

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as fh:
            for d in self._goals.values():
                fh.write(json.dumps(d, ensure_ascii=False) + "\n")

    def put(self, goal: Goal) -> None:
        self._goals[goal.goal_id] = goal.to_dict()
        self._save()

    def get(self, goal_id: str) -> Goal | None:
        d = self._goals.get(goal_id)
        return Goal.from_dict(d) if d else None

    def active(self) -> list[Goal]:
        return [Goal.from_dict(d) for d in self._goals.values()
                if d.get("status") in ("ACTIVE", "BLOCKED", "AWAITING_NOAH")]
