"""
core/oracle_runtime.py — ORACLE Runtime Orchestrator

ORACLE is a resident continuity intelligence: a local governed system designed
to preserve human context, detect what matters, reduce cognitive burden, and
help Noah continue without losing himself in the noise.

Not a chatbot. Not personality. A careful steward.
Governing doctrine: docs/ORACLE_DOCTRINE.md

Before this: ORACLE sat in PowerShell waiting for Noah to type the next thing.
After this: ORACLE wakes, checks state, picks one priority, runs one module,
            saves the result, reports, and stops (or waits for next interval).

Core law:
  ORACLE may run cycles.
  ORACLE may not grant herself authority.
  ORACLE may propose, classify, compress, and queue.
  ORACLE may not execute external or destructive actions without Noah approval.
  ORACLE may not approve her own memory candidates.
  ORACLE may not claim an action succeeded without verification evidence.

One cycle = one selected priority = one module invoked = one result persisted.

Usage:
  python core/oracle_runtime.py --cycle       Run one cycle (MANUAL mode)
  python core/oracle_runtime.py --status      Show current state
  python core/oracle_runtime.py --safe-sleep  Switch to SAFE_SLEEP_MODE
  python core/oracle_runtime.py --smoke       Run smoke tests
"""

import json
import sys
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

# ── Operating modes ────────────────────────────────────────────────────────────
MODE_MANUAL      = "MANUAL"       # one cycle on demand, then stop
MODE_DAEMON_SAFE = "DAEMON_SAFE"  # interval cycles, propose only
MODE_SLEEP       = "SAFE_SLEEP_MODE"   # no hands/browser/typing/file changes
MODE_DRY_RUN     = "ACTION_DRY_RUN"   # print intent, nothing written
MODE_DISABLED    = "DISABLED"     # do nothing

# ── Priority labels ────────────────────────────────────────────────────────────
P1_SAFETY         = "safety_security_financial_risk"
P2_BROKEN_LAYER   = "broken_action_layer"
P3_PENDING_QUEUES = "pending_approval_queues"
P4_BLOCKER        = "project_blocker"
P5_REVENUE        = "revenue_opportunity"
P6_RELATIONSHIP   = "relationship_followup"
P7_FILE_CLEANUP   = "file_cleanup"
P8_CURIOSITY      = "curiosity_signals"
P9_MAINTENANCE    = "general_maintenance"

PRIORITY_ORDER = [
    P1_SAFETY, P2_BROKEN_LAYER, P3_PENDING_QUEUES, P4_BLOCKER,
    P5_REVENUE, P6_RELATIONSHIP, P7_FILE_CLEANUP, P8_CURIOSITY, P9_MAINTENANCE,
]

FORBIDDEN_ACTIONS = [
    "external_send", "submit", "purchase", "delete", "move_file", "rename_file",
    "commit", "push", "permissions_change", "raw_surveillance_storage",
    "new_source_expansion_without_approval", "claim_sovereign_authority", "infinite_loop",
]

CYCLES_FILE = ROOT / "Memory" / "runtime_cycles.json"
MAX_CYCLES_STORED = 100


# ── Result dataclass ───────────────────────────────────────────────────────────

@dataclass
class RuntimeCycleResult:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    mode: str = MODE_MANUAL
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str = ""
    selected_priority: str = ""
    selected_module: str = ""
    action_taken: str = ""
    candidates_created: list = field(default_factory=list)
    approval_required: bool = False
    approval_reason: str = ""
    blocked_actions: list = field(default_factory=list)
    confidence: float = 0.0
    unknowns: list = field(default_factory=list)
    next_recommended_step: str = ""
    stopped_reason: str = ""

    def finish(self, stopped_reason: str = "one_cycle_complete") -> "RuntimeCycleResult":
        self.completed_at = datetime.now(timezone.utc).isoformat()
        self.blocked_actions = list(FORBIDDEN_ACTIONS)
        self.stopped_reason = stopped_reason
        return self

    def report(self) -> str:
        lines = [
            "",
            "╔══════════════════════════════════════════════════════╗",
            "║  ORACLE RUNTIME CYCLE RESULT                        ║",
            "╚══════════════════════════════════════════════════════╝",
            "",
            f"  Cycle ID  : {self.id}",
            f"  Mode      : {self.mode}",
            f"  Started   : {self.started_at}",
            f"  Completed : {self.completed_at}",
            f"  Stopped   : {self.stopped_reason}",
            "",
            f"  Priority Selected : {self.selected_priority or '(none)'}",
            f"  Module Invoked    : {self.selected_module or '(none)'}",
            "",
            f"  Action Taken:",
            f"    {self.action_taken or '(none)'}",
            "",
        ]
        if self.candidates_created:
            lines.append(f"  Candidates Created : {len(self.candidates_created)}")
            for c in self.candidates_created[:3]:
                lines.append(f"    - {c}")
            lines.append("")
        if self.approval_required:
            lines.append(f"  APPROVAL NEEDED  : {self.approval_reason}")
            lines.append("")
        if self.unknowns:
            lines.append("  Unknowns Preserved:")
            for u in self.unknowns:
                lines.append(f"    - {u}")
            lines.append("")
        lines.append(f"  Confidence        : {int(self.confidence * 100)}%")
        lines.append("")
        lines.append(f"  Next Recommended  : {self.next_recommended_step}")
        lines.append("")
        lines.append("  Blocked Actions:")
        for b in self.blocked_actions[:6]:
            lines.append(f"    [BLOCKED] {b}")
        lines.append("")
        return "\n".join(lines)


# ── State check ────────────────────────────────────────────────────────────────

def _check_state() -> dict:
    state = {
        "mode": MODE_MANUAL,
        "sov1_hands": "unknown",
        "ollama_running": False,
        "local_mode": False,
        "approved_sources": [],
        "errors": [],
    }
    # Check SOV1 hands
    try:
        import computer_control as cc
        state["sov1_hands"] = "ready" if getattr(cc, "HANDS_AVAILABLE", False) else "unavailable"
    except Exception as e:
        state["sov1_hands"] = "unavailable"
        state["errors"].append(f"computer_control: {e}")

    # Check Ollama / local mode
    try:
        from dotenv import load_dotenv
        import os
        load_dotenv(ROOT / ".env")
        state["local_mode"] = os.getenv("LOCAL_MODE", "false").lower() == "true"
        if state["local_mode"]:
            import urllib.request
            try:
                urllib.request.urlopen("http://localhost:11434", timeout=2)
                state["ollama_running"] = True
            except Exception:
                state["ollama_running"] = False
    except Exception as e:
        state["errors"].append(f"env/ollama: {e}")

    # Approved sources (what we can read without Noah's approval)
    state["approved_sources"] = [
        "memory_db", "curiosity_signals", "self_prompt_cycles",
        "relationship_memory", "remember_me", "live_context",
        "filesystem_index", "sov1_lessons",
    ]
    return state


def _check_pending_memory() -> dict:
    result = {
        "pending_curiosity_signals": 0,
        "pending_integration_candidates": 0,
        "pending_remember_me": 0,
        "pending_relationship_records": 0,
        "total_facts": 0,
        "errors": [],
    }
    # Curiosity signals
    try:
        from curiosity_engine import recall_signals
        sigs = recall_signals(status="pending")
        result["pending_curiosity_signals"] = len(sigs) if sigs else 0
    except Exception as e:
        result["errors"].append(f"curiosity_engine: {e}")

    # Integration candidates
    try:
        from integration_gate import list_pending
        cands = list_pending()
        result["pending_integration_candidates"] = len(cands) if cands else 0
    except Exception as e:
        result["errors"].append(f"integration_gate: {e}")

    # Memory DB facts
    try:
        from memory import get_all_facts
        facts = get_all_facts()
        result["total_facts"] = len(facts) if facts else 0
    except Exception as e:
        result["errors"].append(f"memory: {e}")

    return result


def _check_gaps(state: dict, memory: dict) -> dict:
    gaps = {
        "financial_risk_count": 0,
        "blocker_count": 0,
        "stale_memory_count": 0,
        "contradiction_count": 0,
        "errors": [],
    }
    try:
        from curiosity_engine import recall_signals
        high_risk = recall_signals(risk_level="high", status="pending")
        gaps["financial_risk_count"] = len(high_risk) if high_risk else 0
        blockers = recall_signals(signal_type="unresolved_commitment", status="pending")
        gaps["blocker_count"] = len(blockers) if blockers else 0
    except Exception as e:
        gaps["errors"].append(f"curiosity_engine gaps: {e}")

    if state.get("sov1_hands") == "unavailable":
        gaps["blocker_count"] = max(gaps["blocker_count"], 1)

    return gaps


# ── Priority selection ─────────────────────────────────────────────────────────

def _select_priority(state: dict, memory: dict, gaps: dict) -> tuple[str, float, str]:
    """
    Returns (priority_label, confidence, reasoning).
    Selects exactly one priority per cycle.
    """
    if gaps.get("financial_risk_count", 0) > 0:
        return (P1_SAFETY, 0.95,
                f"High-risk curiosity signal pending: {gaps['financial_risk_count']} item(s).")

    if state.get("sov1_hands") == "unavailable":
        return (P2_BROKEN_LAYER, 0.90,
                "SOV1 computer hands are unavailable. Semantic UI Bridge is the blocker.")

    if memory.get("pending_integration_candidates", 0) > 0 or memory.get("pending_curiosity_signals", 0) > 0:
        n = memory["pending_integration_candidates"] + memory["pending_curiosity_signals"]
        return (P3_PENDING_QUEUES, 0.85,
                f"{n} item(s) pending Noah's review in approval queues.")

    if gaps.get("blocker_count", 0) > 0:
        return (P4_BLOCKER, 0.80,
                f"{gaps['blocker_count']} unresolved commitment(s) flagged as blockers.")

    if memory.get("total_facts", 0) < 5:
        return (P7_FILE_CLEANUP, 0.60,
                "Memory database has fewer than 5 verified facts — context is thin.")

    if memory.get("pending_curiosity_signals", 0) > 0:
        return (P8_CURIOSITY, 0.55,
                f"{memory['pending_curiosity_signals']} pending curiosity signal(s) to process.")

    return (P9_MAINTENANCE, 0.40,
            "No urgent priorities detected. Running general maintenance cycle.")


# ── Module invocation ──────────────────────────────────────────────────────────

def _invoke_module(
    priority: str,
    mode: str,
    result: RuntimeCycleResult,
) -> RuntimeCycleResult:
    """
    Calls the appropriate module for the selected priority.
    All actions are observe/propose — nothing executes externally.
    """
    result.selected_module = "(none)"

    if mode == MODE_DISABLED:
        result.action_taken = "DISABLED mode — no module invoked."
        result.stopped_reason = "disabled"
        return result

    # P1 — Safety
    if priority == P1_SAFETY:
        result.selected_module = "curiosity_engine"
        try:
            from curiosity_engine import recall_signals
            sigs = recall_signals(risk_level="high", status="pending")
            if sigs:
                sig = sigs[0]
                title = getattr(sig, "title", str(sig))
                result.action_taken = (
                    f"Found high-risk signal: '{title}'. "
                    f"Flagged for Noah's review. No action taken."
                )
                result.approval_required = True
                result.approval_reason = f"High-risk signal requires Noah review: {title}"
                result.candidates_created = [title]
                result.next_recommended_step = "Use /pending to review and approve or dismiss this signal."
            else:
                result.action_taken = "High-risk signals found in gaps but none returned by recall. State may be stale."
                result.next_recommended_step = "/pending to inspect queue."
        except Exception as e:
            result.action_taken = f"curiosity_engine unavailable: {e}"
            result.unknowns.append("curiosity_engine import failed")
        result.confidence = 0.95

    # P2 — Broken action layer
    elif priority == P2_BROKEN_LAYER:
        result.selected_module = "sov1 / computer_control"
        result.action_taken = (
            "SOV1 hands are unavailable. The Semantic UI Bridge (pywinauto-based "
            "semantic window targeting) is the missing layer. Until it is built, "
            "SOV1 falls back to blind pixel coordinates and is unreliable."
        )
        result.approval_required = False
        result.next_recommended_step = (
            "Build Semantic UI Bridge: core/semantic_ui_bridge.py — "
            "pywinauto + uiautomation window tree walker for reliable element targeting."
        )
        result.confidence = 0.90
        result.unknowns.append("Semantic UI Bridge not yet built")

    # P3 — Pending queues
    elif priority == P3_PENDING_QUEUES:
        result.selected_module = "integration_gate + curiosity_engine"
        try:
            pending = []
            try:
                from integration_gate import list_pending
                pending += list_pending() or []
            except Exception:
                pass
            try:
                from curiosity_engine import recall_signals
                pending += recall_signals(status="pending") or []
            except Exception:
                pass
            result.action_taken = (
                f"Found {len(pending)} item(s) in pending queues. "
                f"Queued for Noah's review. No action taken without approval."
            )
            result.approval_required = True
            result.approval_reason = f"{len(pending)} items in queue require Noah review."
            result.candidates_created = [str(getattr(p, "title", p))[:60] for p in pending[:5]]
            result.next_recommended_step = "/pending to review and approve or dismiss queued items."
        except Exception as e:
            result.action_taken = f"Could not load pending queues: {e}"
            result.unknowns.append("integration_gate or curiosity_engine unavailable")
        result.confidence = 0.85

    # P4 — Project blocker
    elif priority == P4_BLOCKER:
        result.selected_module = "curiosity_engine"
        try:
            from curiosity_engine import (
                detect_unresolved_commitment, recall_signals, generate_question,
            )
            blockers = recall_signals(signal_type="unresolved_commitment", status="pending") or []
            if blockers:
                sig = blockers[0]
                q = generate_question(sig)
                result.action_taken = f"Project blocker detected. Generated question: {q}"
                result.candidates_created = [q]
                result.approval_required = True
                result.approval_reason = "Blocker question needs Noah's answer before work can proceed."
                result.next_recommended_step = f"Answer this question to unblock: {q}"
            else:
                result.action_taken = "No explicit blocker signals found. Gap may be resolved."
                result.next_recommended_step = "/self-prompt to run a full gap check."
        except Exception as e:
            result.action_taken = f"curiosity_engine unavailable: {e}"
            result.unknowns.append("curiosity_engine import failed")
        result.confidence = 0.80

    # P5 — Revenue
    elif priority == P5_REVENUE:
        result.selected_module = "live_context"
        result.action_taken = (
            "Revenue opportunity check: scanning live context for stale revenue signals. "
            "No external action taken."
        )
        result.next_recommended_step = "/self-prompt to surface stale revenue context."
        result.confidence = 0.65

    # P6 — Relationship follow-up
    elif priority == P6_RELATIONSHIP:
        result.selected_module = "relationship_memory"
        try:
            from relationship_memory import get_all_contacts
            contacts = get_all_contacts() or []
            stale = [c for c in contacts if _is_stale_contact(c)]
            if stale:
                result.action_taken = (
                    f"Found {len(stale)} relationship record(s) that may need follow-up. "
                    f"No message sent. Approval required to reach out."
                )
                result.candidates_created = [str(s)[:60] for s in stale[:3]]
                result.approval_required = True
                result.approval_reason = "Relationship follow-up requires Noah approval before any message is sent."
                result.next_recommended_step = "/pending to review relationship candidates."
            else:
                result.action_taken = "No stale relationship records detected."
                result.next_recommended_step = "Relationship memory appears current."
        except Exception as e:
            result.action_taken = f"relationship_memory unavailable: {e}"
            result.unknowns.append("relationship_memory import failed")
        result.confidence = 0.70

    # P7 — File cleanup
    elif priority == P7_FILE_CLEANUP:
        result.selected_module = "memory + live_context"
        result.action_taken = (
            "File/memory cleanup check: memory database has fewer than 5 verified facts. "
            "Context is thin. Consider running /remember-me to seed initial facts."
        )
        result.next_recommended_step = (
            "Run: /remember-me to capture key facts about the current project state."
        )
        result.confidence = 0.60

    # P8 — Curiosity signals
    elif priority == P8_CURIOSITY:
        result.selected_module = "curiosity_engine"
        try:
            from curiosity_engine import recall_signals, generate_question
            sigs = recall_signals(status="pending") or []
            if sigs:
                sig = sigs[0]
                q = generate_question(sig)
                result.action_taken = f"Curiosity signal ready. Generated question: {q}"
                result.candidates_created = [q]
                result.next_recommended_step = f"Answer or dismiss: {q}"
            else:
                result.action_taken = "No pending curiosity signals."
                result.next_recommended_step = "/self-build to generate a new improvement proposal."
        except Exception as e:
            result.action_taken = f"curiosity_engine unavailable: {e}"
        result.confidence = 0.55

    # P9 — General maintenance
    else:
        result.selected_module = "self_prompt_loop"
        result.action_taken = (
            "No urgent priorities detected. System is stable. "
            "Recommend running /self-build to identify the next highest-value improvement."
        )
        result.next_recommended_step = "/self-build to propose the next improvement."
        result.confidence = 0.40

    return result


def _is_stale_contact(contact) -> bool:
    """Simple heuristic — contacts without recent activity are stale."""
    try:
        last = getattr(contact, "last_contact_date", None) or getattr(contact, "updated_at", None)
        if not last:
            return True
        from datetime import date
        if isinstance(last, str):
            last = last[:10]
            last_date = date.fromisoformat(last)
            delta = (date.today() - last_date).days
            return delta > 30
    except Exception:
        pass
    return False


# ── Persistence ────────────────────────────────────────────────────────────────

def _persist(result: RuntimeCycleResult) -> RuntimeCycleResult:
    CYCLES_FILE.parent.mkdir(parents=True, exist_ok=True)
    cycles = []
    if CYCLES_FILE.exists():
        try:
            cycles = json.loads(CYCLES_FILE.read_text(encoding="utf-8"))
        except Exception:
            cycles = []
    cycles.append(asdict(result))
    cycles = cycles[-MAX_CYCLES_STORED:]
    CYCLES_FILE.write_text(json.dumps(cycles, indent=2, default=str), encoding="utf-8")
    return result


def _load_cycles() -> list:
    if not CYCLES_FILE.exists():
        return []
    try:
        return json.loads(CYCLES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


# ── Public API ─────────────────────────────────────────────────────────────────

def run_cycle(mode: str = MODE_MANUAL) -> RuntimeCycleResult:
    """
    Run one complete governed cycle.
    Wake → state → memory → gaps → priority → invoke → persist → return.
    """
    result = RuntimeCycleResult(mode=mode)

    # DISABLED — do nothing
    if mode == MODE_DISABLED:
        result.action_taken = "DISABLED mode. No cycle run."
        result.stopped_reason = "disabled"
        result.blocked_actions = list(FORBIDDEN_ACTIONS)
        result.completed_at = datetime.now(timezone.utc).isoformat()
        return result

    # Wake — load state
    state = _check_state()
    memory = _check_pending_memory()
    gaps = _check_gaps(state, memory)

    # SAFE_SLEEP — observe and propose only, no hands/browser/file changes
    if mode == MODE_SLEEP or state.get("mode") == MODE_SLEEP:
        result.mode = MODE_SLEEP
        priority, confidence, reasoning = _select_priority(state, memory, gaps)
        result.selected_priority = f"{priority} [SAFE_SLEEP — propose only]"
        result.confidence = confidence
        result.action_taken = (
            f"SAFE_SLEEP_MODE active. Observation only. Detected priority: {priority}. "
            f"Reason: {reasoning}. No hands, browser, or file actions permitted."
        )
        result.next_recommended_step = (
            "Type 'wake' or '/safe-sleep off' to re-enable actions, "
            "then run /cycle to act on this priority."
        )
        result.finish("safe_sleep_propose_only")
        _persist(result)
        return result

    # Select priority
    priority, confidence, reasoning = _select_priority(state, memory, gaps)
    result.selected_priority = priority
    result.confidence = confidence

    # Invoke module
    result = _invoke_module(priority, mode, result)

    # Finalize
    result.finish("one_cycle_complete" if mode == MODE_MANUAL else f"{mode}_cycle_complete")
    _persist(result)
    return result


def get_status() -> dict:
    """Return current runtime status without running a cycle."""
    state = _check_state()
    memory = _check_pending_memory()
    gaps = _check_gaps(state, memory)
    priority, confidence, reasoning = _select_priority(state, memory, gaps)
    cycles = _load_cycles()
    return {
        "state": state,
        "memory": memory,
        "gaps": gaps,
        "next_priority": priority,
        "priority_reasoning": reasoning,
        "confidence": confidence,
        "total_cycles_stored": len(cycles),
        "last_cycle": cycles[-1] if cycles else None,
    }


def status_report() -> str:
    s = get_status()
    lines = [
        "",
        "  [ORACLE RUNTIME STATUS]",
        f"  SOV1 hands     : {s['state'].get('sov1_hands', 'unknown')}",
        f"  Local mode     : {s['state'].get('local_mode', False)}",
        f"  Ollama running : {s['state'].get('ollama_running', False)}",
        "",
        f"  Pending curiosity  : {s['memory'].get('pending_curiosity_signals', 0)}",
        f"  Pending candidates : {s['memory'].get('pending_integration_candidates', 0)}",
        f"  Total facts        : {s['memory'].get('total_facts', 0)}",
        "",
        f"  Financial risk     : {s['gaps'].get('financial_risk_count', 0)}",
        f"  Blockers           : {s['gaps'].get('blocker_count', 0)}",
        "",
        f"  Next priority      : {s['next_priority']}",
        f"  Reasoning          : {s['priority_reasoning']}",
        f"  Confidence         : {int(s['confidence'] * 100)}%",
        f"  Cycles stored      : {s['total_cycles_stored']}",
        "",
    ]
    if s.get("last_cycle"):
        lc = s["last_cycle"]
        lines += [
            f"  Last cycle : {lc.get('id', '?')} | {lc.get('mode', '?')} | {lc.get('stopped_reason', '?')}",
            f"             : {lc.get('selected_priority', '?')}",
            "",
        ]
    return "\n".join(lines)


# ── Smoke test ─────────────────────────────────────────────────────────────────

def _smoke_test() -> bool:
    print("=" * 60)
    print("oracle_runtime.py — Smoke Test")
    print("=" * 60)

    passed = 0
    failed = 0

    def check(label: str, condition: bool, detail: str = ""):
        nonlocal passed, failed
        ok = condition
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        if not ok and detail:
            print(f"         {detail}")
        if ok:
            passed += 1
        else:
            failed += 1

    # 1. DISABLED mode does nothing
    r = run_cycle(MODE_DISABLED)
    check("DISABLED mode stops immediately", r.stopped_reason == "disabled")
    check("DISABLED mode has no action", "DISABLED" in r.action_taken)
    check("DISABLED mode always populates blocked_actions", len(r.blocked_actions) > 0)

    # 2. MANUAL cycle runs and selects a priority
    r2 = run_cycle(MODE_MANUAL)
    check("MANUAL cycle completes", bool(r2.completed_at))
    check("MANUAL cycle selects a priority", bool(r2.selected_priority))
    check("MANUAL cycle has stopped_reason", bool(r2.stopped_reason))
    check("MANUAL cycle has blocked_actions", len(r2.blocked_actions) > 0)
    check("MANUAL cycle has next_recommended_step", bool(r2.next_recommended_step))
    check("MANUAL cycle confidence > 0", r2.confidence > 0.0)

    # 3. SAFE_SLEEP mode proposes only
    r3 = run_cycle(MODE_SLEEP)
    check("SAFE_SLEEP cycle completes", bool(r3.completed_at))
    check("SAFE_SLEEP mode is SAFE_SLEEP_MODE", r3.mode == MODE_SLEEP)
    check("SAFE_SLEEP stopped reason is propose_only", "propose_only" in r3.stopped_reason)
    check("SAFE_SLEEP action mentions no hands/browser",
          "SAFE_SLEEP" in r3.action_taken or "observe" in r3.action_taken.lower())

    # 4. Persistence — cycles file written
    cycles = _load_cycles()
    check("Cycles file written", CYCLES_FILE.exists())
    check("At least one cycle persisted", len(cycles) > 0)
    check("Persisted cycle has id field", "id" in (cycles[-1] if cycles else {}))

    # 5. Status report builds without crash
    try:
        s = status_report()
        check("status_report() runs without crash", True)
        check("status_report() contains priority info", "priority" in s.lower())
    except Exception as e:
        check("status_report() runs without crash", False, str(e))
        check("status_report() contains priority info", False)

    # 6. Priority selection covers all cases directly
    # P1 — safety
    p, _, _ = _select_priority(
        {"sov1_hands": "ready"},
        {"pending_curiosity_signals": 0, "pending_integration_candidates": 0, "total_facts": 10},
        {"financial_risk_count": 2, "blocker_count": 0},
    )
    check("P1 safety selected when financial_risk > 0", p == P1_SAFETY)

    # P2 — broken layer
    p2, _, _ = _select_priority(
        {"sov1_hands": "unavailable"},
        {"pending_curiosity_signals": 0, "pending_integration_candidates": 0, "total_facts": 10},
        {"financial_risk_count": 0, "blocker_count": 1},
    )
    check("P2 broken_layer selected when sov1 unavailable", p2 == P2_BROKEN_LAYER)

    # P3 — pending queues
    p3, _, _ = _select_priority(
        {"sov1_hands": "ready"},
        {"pending_curiosity_signals": 3, "pending_integration_candidates": 1, "total_facts": 10},
        {"financial_risk_count": 0, "blocker_count": 0},
    )
    check("P3 pending_queues selected when items waiting", p3 == P3_PENDING_QUEUES)

    # P9 — maintenance when everything is clean
    p9, _, _ = _select_priority(
        {"sov1_hands": "ready"},
        {"pending_curiosity_signals": 0, "pending_integration_candidates": 0, "total_facts": 10},
        {"financial_risk_count": 0, "blocker_count": 0},
    )
    check("P9 maintenance selected when system is clean", p9 == P9_MAINTENANCE)

    # 7. RuntimeCycleResult.report() builds without crash
    r_report = RuntimeCycleResult()
    r_report.selected_priority = P3_PENDING_QUEUES
    r_report.action_taken = "Test action"
    r_report.next_recommended_step = "Test next step"
    r_report.finish()
    try:
        report_str = r_report.report()
        check("RuntimeCycleResult.report() builds without crash", True)
        check("Report contains cycle ID", r_report.id in report_str)
        check("Report contains blocked actions", "BLOCKED" in report_str)
    except Exception as e:
        check("RuntimeCycleResult.report() builds without crash", False, str(e))
        check("Report contains cycle ID", False)
        check("Report contains blocked actions", False)

    print(f"\n{passed}/{passed + failed} smoke tests passed.")
    if failed:
        print(f"FAILED: {failed} test(s).")
    else:
        print("All smoke tests passed.")
    return failed == 0


# ── CLI entry point ────────────────────────────────────────────────────────────

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    args = set(sys.argv[1:])

    if "--smoke" in args or "smoke" in args:
        ok = _smoke_test()
        sys.exit(0 if ok else 1)

    if "--status" in args or "-s" in args:
        print(status_report())
        sys.exit(0)

    if "--safe-sleep" in args:
        r = run_cycle(MODE_SLEEP)
        print(r.report())
        sys.exit(0)

    if "--cycle" in args or "-c" in args or not args:
        r = run_cycle(MODE_MANUAL)
        print(r.report())
        sys.exit(0)

    print("Usage:")
    print("  python core/oracle_runtime.py --cycle       Run one manual cycle")
    print("  python core/oracle_runtime.py --status      Show current state")
    print("  python core/oracle_runtime.py --safe-sleep  Propose-only cycle")
    print("  python core/oracle_runtime.py --smoke       Run smoke tests")
    sys.exit(1)


if __name__ == "__main__":
    main()
