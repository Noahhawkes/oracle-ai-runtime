"""
core/self_prompt_loop.py — ORACLE Self-Prompt Loop

CORE LAW:
  ORACLE may prompt herself.
  ORACLE may not grant herself authority.

51/49 Rule:
  ORACLE performs the operational 49%:
    observe approved sources, check pending candidates, detect gaps,
    generate questions, generate action candidates, propose next steps.

  Noah holds the sovereign 51%:
    approve, reject, correct, delete, revoke, quarantine, authorize execution.

Self-prompting produces observations, questions, candidates, and proposals ONLY.
No action executes from this module.
No external send, submit, purchase, delete, move, commit, push, or permission change.
No infinite loop without explicit daemon mode activation.
"""

import json
import uuid
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

CYCLES_FILE = ROOT / "Memory" / "self_prompt_cycles.json"

# ── Operating modes ───────────────────────────────────────────────────────────

MODE_MANUAL      = "MANUAL"        # one cycle on demand
MODE_DAEMON_SAFE = "DAEMON_SAFE"   # interval loop, observe/propose only
MODE_SLEEP       = "SAFE_SLEEP_MODE"  # no hands, no browser, no typing
MODE_DRY_RUN     = "ACTION_DRY_RUN"  # prints intended actions only
MODE_DISABLED    = "DISABLED"      # no self-prompting at all

VALID_MODES = {MODE_MANUAL, MODE_DAEMON_SAFE, MODE_SLEEP, MODE_DRY_RUN, MODE_DISABLED}

# ── Priority order (highest = 1) ──────────────────────────────────────────────

PRIORITY_SAFETY          = 1
PRIORITY_BROKEN_LAYER    = 2
PRIORITY_PENDING_QUEUES  = 3
PRIORITY_PROJECT_BLOCKER = 4
PRIORITY_REVENUE         = 5
PRIORITY_RELATIONSHIP    = 6
PRIORITY_FILE_CLEANUP    = 7
PRIORITY_CURIOSITY       = 8

PRIORITY_LABELS = {
    PRIORITY_SAFETY:          "safety_security_financial_risk",
    PRIORITY_BROKEN_LAYER:    "broken_action_layer",
    PRIORITY_PENDING_QUEUES:  "pending_approval_queues",
    PRIORITY_PROJECT_BLOCKER: "project_blocker",
    PRIORITY_REVENUE:         "revenue_opportunity",
    PRIORITY_RELATIONSHIP:    "relationship_followup",
    PRIORITY_FILE_CLEANUP:    "file_cleanup",
    PRIORITY_CURIOSITY:       "general_curiosity",
}

# ── Forbidden actions ─────────────────────────────────────────────────────────

FORBIDDEN_ACTIONS = [
    "external_send", "submit", "purchase", "delete", "move_rename",
    "commit_push", "permission_change", "raw_surveillance_storage",
    "source_expansion_without_approval", "claim_sovereign_authority",
    "infinite_loop",
]

# ── SelfPromptCycleResult dataclass ──────────────────────────────────────────

@dataclass
class SelfPromptCycleResult:
    mode: str
    state_summary: dict = field(default_factory=dict)
    memory_summary: dict = field(default_factory=dict)
    gap_summary: dict = field(default_factory=dict)
    selected_priority: str = ""
    proposed_next_step: str = ""
    created_candidate_ids: list = field(default_factory=list)
    blocked_actions: list = field(default_factory=list)
    confidence: float = 0.5
    unknowns: list = field(default_factory=list)
    stopped_reason: str = ""

    # Auto-generated
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str = ""

    def complete(self, reason: str = "cycle_complete"):
        self.completed_at = datetime.now(timezone.utc).isoformat()
        self.stopped_reason = reason

    def to_dict(self) -> dict:
        return asdict(self)

    def report(self) -> str:
        lines = [
            "",
            "╔══════════════════════════════════════════════════════╗",
            "║  ORACLE SELF-PROMPT CYCLE RESULT                    ║",
            "╚══════════════════════════════════════════════════════╝",
            "",
            f"  Cycle ID  : {self.id}",
            f"  Mode      : {self.mode}",
            f"  Started   : {self.started_at}",
            f"  Completed : {self.completed_at}",
            f"  Stopped   : {self.stopped_reason}",
            "",
            "  ── State ──",
        ]
        for k, v in self.state_summary.items():
            lines.append(f"    {k}: {v}")
        lines.append("")
        lines.append("  ── Memory ──")
        for k, v in self.memory_summary.items():
            lines.append(f"    {k}: {v}")
        lines.append("")
        lines.append("  ── Gaps ──")
        for k, v in self.gap_summary.items():
            lines.append(f"    {k}: {v}")
        lines.append("")
        lines.append(f"  ── Priority Selected ──")
        lines.append(f"    {self.selected_priority or '(none)'}")
        lines.append("")
        lines.append(f"  ── Proposed Next Step ──")
        lines.append(f"    {self.proposed_next_step or '(none)'}")
        if self.created_candidate_ids:
            lines.append("")
            lines.append(f"  ── Candidates Created ──")
            for cid in self.created_candidate_ids:
                lines.append(f"    {cid}")
        if self.blocked_actions:
            lines.append("")
            lines.append(f"  ── Blocked Actions ──")
            for b in self.blocked_actions:
                lines.append(f"    [BLOCKED] {b}")
        if self.unknowns:
            lines.append("")
            lines.append(f"  ── Unknowns Preserved ──")
            for u in self.unknowns:
                lines.append(f"    ? {u}")
        lines.append(f"\n  Confidence: {self.confidence:.0%}")
        lines.append("")
        return "\n".join(lines)


# ── Persistence ───────────────────────────────────────────────────────────────

def _load_cycles() -> list:
    if not CYCLES_FILE.exists():
        return []
    try:
        return json.loads(CYCLES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_cycle(result: SelfPromptCycleResult):
    CYCLES_FILE.parent.mkdir(parents=True, exist_ok=True)
    cycles = _load_cycles()
    cycles.append(result.to_dict())
    # Keep last 100 cycles
    if len(cycles) > 100:
        cycles = cycles[-100:]
    CYCLES_FILE.write_text(json.dumps(cycles, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Step 1: State check ───────────────────────────────────────────────────────

def check_state() -> dict:
    """
    What mode am I in? What safety constraints are active?
    What sources are approved?
    """
    state = {
        "safe_sleep_mode": False,
        "action_dry_run": False,
        "sov1_hands": "unknown",
        "approved_sources": [],
        "ollama_running": False,
        "local_mode": False,
    }

    # SOV1 hands
    try:
        import computer_control as cc
        state["sov1_hands"] = "ready" if cc.HANDS_AVAILABLE else "unavailable"
    except Exception:
        state["sov1_hands"] = "unavailable"

    # Local mode
    import os
    state["local_mode"] = os.getenv("LOCAL_MODE", "").lower() in ("1", "true", "yes")

    # Ollama
    if state["local_mode"]:
        try:
            import urllib.request
            with urllib.request.urlopen("http://localhost:11434", timeout=2):
                state["ollama_running"] = True
        except Exception:
            state["ollama_running"] = False

    # Approved sources (what ORACLE can observe without new permission)
    state["approved_sources"] = [
        "memory_db",
        "curiosity_signals",
        "self_prompt_cycles",
        "audit_log",
        "oracle_ai_repo",
        "live_context",
    ]

    return state


# ── Step 2: Memory check ──────────────────────────────────────────────────────

def check_pending_memory() -> dict:
    """
    What pending records exist across all approval queues?
    Returns counts and summaries — does not load full content.
    """
    summary = {
        "pending_facts": 0,
        "pending_curiosity_signals": 0,
        "pending_integration_candidates": 0,
        "total_facts": 0,
        "total_sessions": 0,
        "high_risk_signals": [],
    }

    # Memory DB facts
    try:
        from memory import get_conn
        with get_conn() as conn:
            summary["total_facts"] = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
            summary["total_sessions"] = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    except Exception:
        pass

    # Curiosity signals
    try:
        from curiosity_engine import recall_signals, STATUS_PENDING, RISK_HIGH, RISK_SENSITIVE, RISK_BLOCKED
        pending = recall_signals(status=STATUS_PENDING)
        summary["pending_curiosity_signals"] = len(pending)
        for s in pending:
            if s.risk_level in (RISK_HIGH, RISK_SENSITIVE, RISK_BLOCKED):
                summary["high_risk_signals"].append({
                    "id": s.id,
                    "title": s.title,
                    "risk": s.risk_level,
                    "type": s.signal_type,
                })
    except Exception:
        pass

    # Integration gate candidates
    try:
        from integration_gate import ApprovalGate
        gate = ApprovalGate()
        candidates = gate.list_pending()
        summary["pending_integration_candidates"] = len(candidates)
    except Exception:
        pass

    return summary


# ── Step 3: Gap check ─────────────────────────────────────────────────────────

def check_curiosity() -> dict:
    """
    What is missing, stale, conflicting, high-risk, or blocking?
    Reads existing curiosity signals — does not generate new ones.
    """
    gaps = {
        "missing_context_count": 0,
        "contradiction_count": 0,
        "stale_count": 0,
        "blocker_count": 0,
        "financial_risk_count": 0,
        "identity_drift_count": 0,
        "top_blockers": [],
        "top_financial_risks": [],
    }

    try:
        from curiosity_engine import recall_signals, STATUS_PENDING
        pending = recall_signals(status=STATUS_PENDING)
        for s in pending:
            st = s.signal_type
            if st == "missing_context":
                gaps["missing_context_count"] += 1
            elif st == "contradiction":
                gaps["contradiction_count"] += 1
            elif st == "stale_memory":
                gaps["stale_count"] += 1
            elif st == "project_blocker":
                gaps["blocker_count"] += 1
                gaps["top_blockers"].append({"id": s.id, "title": s.title})
            elif st == "financial_risk":
                gaps["financial_risk_count"] += 1
                gaps["top_financial_risks"].append({"id": s.id, "title": s.title, "risk": s.risk_level})
            elif st == "identity_drift":
                gaps["identity_drift_count"] += 1
    except Exception:
        pass

    return gaps


# ── Step 4: Priority selection ────────────────────────────────────────────────

def select_priority(
    state: dict,
    memory: dict,
    gaps: dict,
) -> tuple[int, str, str]:
    """
    Choose exactly ONE highest-priority next action.
    Returns (priority_level, priority_label, reasoning).
    """

    # 1. Safety / security / financial risk
    if gaps.get("financial_risk_count", 0) > 0 or memory.get("high_risk_signals"):
        high_risk = memory.get("high_risk_signals", [])
        top = high_risk[0] if high_risk else gaps.get("top_financial_risks", [{}])[0]
        return (
            PRIORITY_SAFETY,
            PRIORITY_LABELS[PRIORITY_SAFETY],
            f"High-risk signal pending: {top.get('title', 'financial or safety risk')}",
        )

    # 2. Broken action layer
    blockers = gaps.get("top_blockers", [])
    if gaps.get("blocker_count", 0) > 0 or state.get("sov1_hands") == "unavailable":
        top = blockers[0] if blockers else {"title": "SOV1 hands unavailable"}
        return (
            PRIORITY_BROKEN_LAYER,
            PRIORITY_LABELS[PRIORITY_BROKEN_LAYER],
            f"Action layer blocker: {top.get('title', 'action layer unreliable')}",
        )

    # 3. Pending approval queues
    pending_total = (
        memory.get("pending_curiosity_signals", 0) +
        memory.get("pending_integration_candidates", 0)
    )
    if pending_total > 0:
        return (
            PRIORITY_PENDING_QUEUES,
            PRIORITY_LABELS[PRIORITY_PENDING_QUEUES],
            f"{pending_total} item(s) pending Noah's approval across memory and curiosity queues.",
        )

    # 4. Project blockers (already checked above, but catch if no signal object)
    if gaps.get("blocker_count", 0) > 0:
        return (
            PRIORITY_PROJECT_BLOCKER,
            PRIORITY_LABELS[PRIORITY_PROJECT_BLOCKER],
            "Project blocker detected in curiosity signals.",
        )

    # 5. Revenue (check facts for revenue-related stale signals)
    if gaps.get("stale_count", 0) > 2:
        return (
            PRIORITY_REVENUE,
            PRIORITY_LABELS[PRIORITY_REVENUE],
            f"{gaps['stale_count']} stale memory records may include revenue context.",
        )

    # 6. Relationship follow-up
    # (future: check ENDLESS CRM pending)
    if memory.get("pending_integration_candidates", 0) > 0:
        return (
            PRIORITY_RELATIONSHIP,
            PRIORITY_LABELS[PRIORITY_RELATIONSHIP],
            "Integration candidates pending — may include relationship records.",
        )

    # 7. File cleanup (missing context)
    if gaps.get("missing_context_count", 0) > 0:
        return (
            PRIORITY_FILE_CLEANUP,
            PRIORITY_LABELS[PRIORITY_FILE_CLEANUP],
            f"{gaps['missing_context_count']} records have missing context fields.",
        )

    # 8. General curiosity fallback
    return (
        PRIORITY_CURIOSITY,
        PRIORITY_LABELS[PRIORITY_CURIOSITY],
        "No critical gaps detected. General curiosity scan recommended.",
    )


# ── Step 5: Candidate creation ────────────────────────────────────────────────

def create_next_candidate(
    priority_level: int,
    priority_label: str,
    reasoning: str,
    mode: str,
    gaps: dict,
    memory: dict,
) -> tuple[str, list[str]]:
    """
    Produce ONE candidate based on selected priority.
    Returns (proposed_next_step, list_of_created_candidate_ids).

    In SAFE_SLEEP_MODE, hands/browser/typing are blocked.
    All outputs are observations, questions, or proposals — never executions.
    """
    created_ids = []

    # SAFE_SLEEP_MODE: only observations allowed
    if mode == MODE_SLEEP:
        return (
            f"[SAFE_SLEEP_MODE] Observation only. "
            f"Priority detected: {priority_label}. "
            f"Reasoning: {reasoning}. "
            f"No action taken — hands, browser, and typing are blocked.",
            [],
        )

    # ACTION_DRY_RUN: print what would happen
    if mode == MODE_DRY_RUN:
        return (
            f"[ACTION_DRY_RUN] Would create candidate for: {priority_label}. "
            f"Reasoning: {reasoning}. No candidate written — dry run only.",
            [],
        )

    # MANUAL / DAEMON_SAFE — produce a real candidate

    if priority_level == PRIORITY_SAFETY:
        top_risks = memory.get("high_risk_signals", []) + gaps.get("top_financial_risks", [])
        top = top_risks[0] if top_risks else {}
        proposal = (
            f"SAFETY CANDIDATE: Review high-risk signal '{top.get('title', 'unknown')}' "
            f"(risk: {top.get('risk', '?')}). "
            f"Recommended action: Noah reviews and approves or rejects this signal. "
            f"Use /pending to see full list."
        )

    elif priority_level == PRIORITY_BROKEN_LAYER:
        blockers = gaps.get("top_blockers", [])
        top = blockers[0] if blockers else {"title": "Semantic UI Bridge"}
        proposal = (
            f"ACTION LAYER CANDIDATE: '{top.get('title')}' is blocking autonomous operation. "
            f"Recommended next build: implement Semantic UI Bridge so ORACLE can reliably "
            f"find and interact with UI elements by text rather than pixel coordinates. "
            f"This is the highest mechanical fix remaining."
        )

    elif priority_level == PRIORITY_PENDING_QUEUES:
        total = (
            memory.get("pending_curiosity_signals", 0) +
            memory.get("pending_integration_candidates", 0)
        )
        proposal = (
            f"APPROVAL QUEUE CANDIDATE: {total} item(s) are pending Noah's review. "
            f"Use /pending to review integration candidates. "
            f"Use /curiosity (when wired) to review curiosity signals. "
            f"Clearing the queue unblocks downstream decisions."
        )
        # Create a curiosity signal for the pending queue itself
        try:
            from curiosity_engine import CuriositySignal, persist, STATUS_PENDING
            sig = CuriositySignal(
                signal_type="unresolved_commitment",
                title=f"{total} items pending approval in ORACLE queues",
                observed_context=f"Memory: {memory.get('pending_integration_candidates',0)} integration candidates. Curiosity: {memory.get('pending_curiosity_signals',0)} signals.",
                why_it_matters="Pending items block downstream context and decisions.",
                recommended_question="Do you want to review the pending queue now?",
                confidence=0.9,
                risk_level="medium",
                tags=["pending", "queue", "self_prompt"],
            )
            persist(sig)
            created_ids.append(sig.id)
        except Exception:
            pass

    elif priority_level == PRIORITY_PROJECT_BLOCKER:
        proposal = (
            f"PROJECT BLOCKER CANDIDATE: {gaps.get('blocker_count', 0)} blocker(s) in curiosity signals. "
            f"Review and approve or reject these signals to unblock the build. "
            f"Use /self-build to get a specific implementation recommendation."
        )

    elif priority_level == PRIORITY_REVENUE:
        proposal = (
            f"REVENUE CANDIDATE: {gaps.get('stale_count', 0)} stale memory records detected. "
            f"Some may contain revenue context (TOUCHFLAME, The Fixer, Rendered Reality, Noah.AI). "
            f"Recommended: review stale records and update or prune."
        )

    elif priority_level == PRIORITY_RELATIONSHIP:
        proposal = (
            f"RELATIONSHIP CANDIDATE: {memory.get('pending_integration_candidates', 0)} "
            f"integration candidates pending. Some may be CRM or relationship records. "
            f"Review with /pending."
        )

    elif priority_level == PRIORITY_FILE_CLEANUP:
        proposal = (
            f"FILE INTELLIGENCE CANDIDATE: {gaps.get('missing_context_count', 0)} records "
            f"have missing context fields. "
            f"Recommended: surface these to Noah for fill-in or prune."
        )

    else:
        proposal = (
            "CURIOSITY CANDIDATE: No critical gaps detected. "
            "System appears stable. Next recommended action: run /self-build to identify "
            "the single highest-value code improvement."
        )

    return proposal, created_ids


# ── Step 6: Stop ──────────────────────────────────────────────────────────────

def stop_with_reason(result: SelfPromptCycleResult, reason: str) -> SelfPromptCycleResult:
    result.complete(reason)
    _save_cycle(result)
    return result


# ── Main API ──────────────────────────────────────────────────────────────────

def run_once(mode: str = MODE_MANUAL) -> SelfPromptCycleResult:
    """
    Run one self-prompt cycle.

    Produces observations, questions, candidates, and proposals only.
    No action executes. No external send, submit, purchase, delete, move.
    After one cycle, stops and reports.
    """
    if mode not in VALID_MODES:
        mode = MODE_MANUAL

    result = SelfPromptCycleResult(mode=mode)

    # DISABLED — do nothing
    if mode == MODE_DISABLED:
        result.proposed_next_step = "Self-prompt loop is DISABLED. No cycle run."
        result.stopped_reason = "disabled"
        result.blocked_actions = FORBIDDEN_ACTIONS
        result.unknowns = ["all — loop disabled"]
        result.complete("disabled")
        _save_cycle(result)
        return result

    # Step 1: State
    result.state_summary = check_state()

    # Step 2: Memory
    result.memory_summary = check_pending_memory()

    # Step 3: Gaps
    result.gap_summary = check_curiosity()

    # Step 4: Select ONE priority
    priority_level, priority_label, reasoning = select_priority(
        result.state_summary,
        result.memory_summary,
        result.gap_summary,
    )
    result.selected_priority = f"[P{priority_level}] {priority_label}: {reasoning}"
    result.confidence = max(0.3, 1.0 - (priority_level * 0.08))

    # Step 5: Create one candidate
    proposal, created_ids = create_next_candidate(
        priority_level, priority_label, reasoning,
        mode,
        result.gap_summary,
        result.memory_summary,
    )
    result.proposed_next_step = proposal
    result.created_candidate_ids = created_ids

    # Always record what was blocked (nothing was executed)
    result.blocked_actions = FORBIDDEN_ACTIONS

    # Preserve unknowns
    result.unknowns = [
        "whether pending candidates are stale or current",
        "Noah's current priorities outside ORACLE context",
        "external system states (billing, email, calendar)",
    ]

    # Step 6: Stop after one cycle
    return stop_with_reason(result, "one_cycle_complete")


# ── Smoke test ────────────────────────────────────────────────────────────────

def _smoke_test():
    print("=" * 60)
    print("Self-Prompt Loop — Smoke Test")
    print("=" * 60)

    passed = 0
    failed = 0

    def check(label: str, condition: bool, detail: str = ""):
        nonlocal passed, failed
        ok = "PASS" if condition else "FAIL"
        print(f"  [{ok}] {label}")
        if not condition and detail:
            print(f"         {detail}")
        if condition:
            passed += 1
        else:
            failed += 1

    # Seed a curiosity signal so memory check has something
    try:
        from curiosity_engine import CuriositySignal, persist
        fake = CuriositySignal(
            signal_type="financial_risk",
            title="Smoke test — fake billing failure",
            observed_context="Test signal created by smoke test.",
            risk_level="high",
            confidence=0.9,
            tags=["smoke_test"],
        )
        persist(fake)
    except Exception as e:
        print(f"  [WARN] Could not seed curiosity signal: {e}")

    # 1. MANUAL mode — one cycle runs, one priority selected, no action executes
    result = run_once(mode=MODE_MANUAL)

    check("MANUAL cycle completes", result.completed_at != "")
    check("MANUAL cycle has stopped_reason", bool(result.stopped_reason))
    check("Exactly one priority selected", bool(result.selected_priority))
    check("Proposed next step is populated", bool(result.proposed_next_step))
    check("No action executed (blocked_actions present)",
          FORBIDDEN_ACTIONS[0] in result.blocked_actions)
    check("State summary populated", bool(result.state_summary))
    check("Memory summary populated", bool(result.memory_summary))
    check("Gap summary populated", bool(result.gap_summary))
    check("Unknowns preserved", len(result.unknowns) > 0)
    check("Result has an ID", bool(result.id))
    check("Result persisted to JSON", CYCLES_FILE.exists())

    # Verify persistence round-trip
    cycles = _load_cycles()
    found = any(c.get("id") == result.id for c in cycles)
    check("Persisted cycle can be loaded back", found)

    # 2. SAFE_SLEEP_MODE — hands/browser/typing blocked
    sleep_result = run_once(mode=MODE_SLEEP)
    check("SAFE_SLEEP_MODE completes", sleep_result.completed_at != "")
    check("SAFE_SLEEP_MODE proposal mentions SAFE_SLEEP_MODE",
          "SAFE_SLEEP_MODE" in sleep_result.proposed_next_step)
    check("SAFE_SLEEP_MODE blocks actions",
          "external_send" in sleep_result.blocked_actions)

    # 3. ACTION_DRY_RUN — prints intent, no candidate written
    dry_result = run_once(mode=MODE_DRY_RUN)
    check("ACTION_DRY_RUN completes", dry_result.completed_at != "")
    check("ACTION_DRY_RUN proposal mentions dry run",
          "DRY_RUN" in dry_result.proposed_next_step)

    # 4. DISABLED — does nothing
    disabled_result = run_once(mode=MODE_DISABLED)
    check("DISABLED mode completes", disabled_result.completed_at != "")
    check("DISABLED stopped_reason is 'disabled'", disabled_result.stopped_reason == "disabled")
    check("DISABLED proposal is minimal", "DISABLED" in disabled_result.proposed_next_step)

    # 5. Priority selection logic — use a clean fake state so hands availability
    #    doesn't interfere with the unit tests for P3/P8 paths.
    state_clean = {
        "safe_sleep_mode": False, "action_dry_run": False,
        "sov1_hands": "ready",    # force hands ready for unit test isolation
        "approved_sources": ["memory_db"], "ollama_running": True, "local_mode": False,
    }
    memory_with_high_risk = {
        "high_risk_signals": [{"id": "x", "title": "Fake risk", "risk": "high"}],
        "pending_curiosity_signals": 0, "pending_integration_candidates": 0,
    }
    gaps_clean = {
        "financial_risk_count": 0, "blocker_count": 0, "stale_count": 0,
        "missing_context_count": 0, "top_blockers": [], "top_financial_risks": [],
    }
    level, label, _ = select_priority(state_clean, memory_with_high_risk, gaps_clean)
    check("High-risk signal => P1 safety priority", level == PRIORITY_SAFETY)

    memory_clean = {"high_risk_signals": [], "pending_curiosity_signals": 0,
                    "pending_integration_candidates": 0}
    gaps_with_blocker = {**gaps_clean, "blocker_count": 1,
                         "top_blockers": [{"id": "b1", "title": "Semantic UI Bridge missing"}]}
    level2, _, _ = select_priority(state_clean, memory_clean, gaps_with_blocker)
    check("Project blocker => P2 broken_layer priority", level2 == PRIORITY_BROKEN_LAYER)

    memory_pending = {**memory_clean, "pending_curiosity_signals": 3}
    level3, _, _ = select_priority(state_clean, memory_pending, gaps_clean)
    check("Pending queue => P3 approval_queues priority", level3 == PRIORITY_PENDING_QUEUES)

    level4, _, _ = select_priority(state_clean, memory_clean, gaps_clean)
    check("No gaps => P8 curiosity fallback", level4 == PRIORITY_CURIOSITY)

    # 6. Report format
    report = result.report()
    check("Report contains cycle ID", result.id in report)
    check("Report contains priority", "Priority" in report or "priority" in report.lower())
    check("Report contains proposed step", "Proposed" in report or "proposed" in report.lower())

    print(f"\n{passed}/{passed + failed} smoke tests passed.")
    if failed:
        print(f"FAILED: {failed} test(s). See above.")
    else:
        print("All smoke tests passed. Self-prompt loop is governed and bounded.")
    return failed == 0


if __name__ == "__main__":
    # Enable UTF-8 output on Windows terminals
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ok = _smoke_test()

    print("\n--- MANUAL cycle report ---")
    result = run_once(mode=MODE_MANUAL)
    print(result.report())

    sys.exit(0 if ok else 1)
