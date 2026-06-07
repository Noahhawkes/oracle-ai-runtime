"""
core/project_state.py — Project State Continuity

The problem it solves:
  ORACLE knows what she knows (facts, sessions, messages).
  She does not know what she was doing, what failed, what's next, or why she stopped.

This module gives ORACLE durable cross-session goal continuity.
She loads project state at startup, updates it after every build/cycle/failure,
and can generate a resume prompt so Noah never has to re-explain the context.

Core law:
  Do not invent progress.
  Do not mark done unless verified by test, commit, or user confirmation.
  Preserve blockers. Preserve unknowns. Preserve failures.
  One active project at a time.

Persistence:
  Memory/project_states.json
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

STATES_FILE = ROOT / "Memory" / "project_states.json"


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class ProjectState:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    project_name: str = ""
    current_goal: str = ""
    current_phase: str = ""
    last_completed_step: str = ""
    last_completed_evidence: str = ""   # test result, commit hash, user confirmation
    current_blocker: str = ""
    blocker_evidence: str = ""
    next_recommended_step: str = ""
    next_step_reason: str = ""
    active_files: list = field(default_factory=list)
    relevant_commits: list = field(default_factory=list)
    pending_candidates: list = field(default_factory=list)
    failed_attempts: list = field(default_factory=list)  # list of {step, failure, evidence, at}
    lessons_learned: list = field(default_factory=list)
    open_questions: list = field(default_factory=list)
    approval_required: bool = False
    approval_reason: str = ""
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    confidence: float = 0.5
    unknowns: list = field(default_factory=list)

    def touch(self):
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def resume_prompt(self) -> str:
        """
        Generate a plain-English resume prompt ORACLE can speak at startup.
        This is what she says instead of waiting for Noah to re-explain.
        """
        lines = [
            f"Project: {self.project_name}",
            f"Phase  : {self.current_phase}",
            f"Goal   : {self.current_goal}",
            "",
        ]
        if self.last_completed_step:
            lines += [
                f"Last verified step:",
                f"  {self.last_completed_step}",
            ]
            if self.last_completed_evidence:
                lines.append(f"  Evidence: {self.last_completed_evidence}")
            lines.append("")
        if self.current_blocker:
            lines += [
                f"Current blocker:",
                f"  {self.current_blocker}",
            ]
            if self.blocker_evidence:
                lines.append(f"  Evidence: {self.blocker_evidence}")
            lines.append("")
        if self.next_recommended_step:
            lines += [
                f"Next step:",
                f"  {self.next_recommended_step}",
            ]
            if self.next_step_reason:
                lines.append(f"  Why: {self.next_step_reason}")
            lines.append("")
        if self.failed_attempts:
            lines.append(f"Failed attempts this phase ({len(self.failed_attempts)}):")
            for f_a in self.failed_attempts[-3:]:
                lines.append(f"  - {f_a.get('step', '?')}: {f_a.get('failure', '?')}")
            lines.append("")
        if self.open_questions:
            lines.append("Open questions:")
            for q in self.open_questions[:3]:
                lines.append(f"  ? {q}")
            lines.append("")
        if self.unknowns:
            lines.append("Preserved unknowns (not inferred):")
            for u in self.unknowns[:3]:
                lines.append(f"  [UNKNOWN] {u}")
            lines.append("")
        if self.approval_required:
            lines += [
                f"APPROVAL NEEDED: {self.approval_reason}",
                "",
            ]
        lines.append(f"Confidence: {int(self.confidence * 100)}%")
        lines.append(f"Updated   : {self.updated_at[:19].replace('T', ' ')} UTC")
        return "\n".join(lines)

    def summary(self) -> str:
        """One-line summary for banner display."""
        blocker = f" | BLOCKER: {self.current_blocker[:50]}" if self.current_blocker else ""
        return (
            f"{self.project_name} | {self.current_phase} | "
            f"Next: {self.next_recommended_step[:60]}{blocker}"
        )


# ── Persistence ────────────────────────────────────────────────────────────────

def _load_all() -> dict:
    """Load all project states from disk. Returns {project_name: dict}."""
    if not STATES_FILE.exists():
        return {}
    try:
        return json.loads(STATES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_all(states: dict):
    STATES_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATES_FILE.write_text(json.dumps(states, indent=2, default=str), encoding="utf-8")


def _from_dict(d: dict) -> ProjectState:
    valid = {k: v for k, v in d.items() if k in ProjectState.__dataclass_fields__}
    return ProjectState(**valid)


# ── Public API ─────────────────────────────────────────────────────────────────

def load_state(project_name: str) -> Optional[ProjectState]:
    """Load project state by name. Returns None if not found."""
    all_states = _load_all()
    data = all_states.get(project_name)
    if not data:
        return None
    return _from_dict(data)


def save_state(state: ProjectState) -> ProjectState:
    """Persist project state to disk."""
    state.touch()
    all_states = _load_all()
    all_states[state.project_name] = asdict(state)
    _save_all(all_states)
    return state


def get_or_create(project_name: str, **defaults) -> ProjectState:
    """Load existing state or create a new one with defaults."""
    state = load_state(project_name)
    if state is None:
        state = ProjectState(project_name=project_name, **defaults)
        save_state(state)
    return state


def list_projects() -> list[str]:
    """Return all known project names."""
    return list(_load_all().keys())


def update_goal(project_name: str, goal: str, phase: str = "") -> ProjectState:
    """Set the current goal (and optionally phase) for a project."""
    state = get_or_create(project_name)
    state.current_goal = goal
    if phase:
        state.current_phase = phase
    return save_state(state)


def record_completed_step(
    project_name: str,
    step: str,
    evidence: str = "",
) -> ProjectState:
    """
    Mark a step as verified complete.
    Evidence must be concrete: commit hash, test pass count, or 'user confirmed'.
    Never call this without real evidence.
    """
    state = get_or_create(project_name)
    state.last_completed_step = step
    state.last_completed_evidence = evidence or "[no evidence provided — treat as unverified]"
    # Clear the blocker if one was set for this step
    if state.current_blocker and step.lower() in state.current_blocker.lower():
        state.current_blocker = ""
        state.blocker_evidence = ""
    return save_state(state)


def record_blocker(
    project_name: str,
    blocker: str,
    evidence: str = "",
) -> ProjectState:
    """Record what is blocking progress. Preserved until explicitly cleared."""
    state = get_or_create(project_name)
    state.current_blocker = blocker
    state.blocker_evidence = evidence
    state.confidence = max(0.1, state.confidence - 0.1)
    return save_state(state)


def clear_blocker(project_name: str, resolution: str = "") -> ProjectState:
    """Clear the current blocker when it is resolved."""
    state = get_or_create(project_name)
    if resolution:
        state.lessons_learned.append(f"Blocker resolved: {state.current_blocker} → {resolution}")
    state.current_blocker = ""
    state.blocker_evidence = ""
    return save_state(state)


def record_failed_attempt(
    project_name: str,
    step: str,
    failure: str,
    evidence: str = "",
) -> ProjectState:
    """
    Record a failed attempt. Failures are never deleted — they inform future decisions.
    """
    state = get_or_create(project_name)
    state.failed_attempts.append({
        "step": step,
        "failure": failure,
        "evidence": evidence,
        "at": datetime.now(timezone.utc).isoformat(),
    })
    # Keep last 20 failures
    state.failed_attempts = state.failed_attempts[-20:]
    state.confidence = max(0.1, state.confidence - 0.05)
    return save_state(state)


def set_next_step(
    project_name: str,
    next_step: str,
    reason: str = "",
) -> ProjectState:
    """Set the next recommended step and why."""
    state = get_or_create(project_name)
    state.next_recommended_step = next_step
    state.next_step_reason = reason
    return save_state(state)


def add_lesson(project_name: str, lesson: str) -> ProjectState:
    """Add a lesson learned. These load on every future session."""
    state = get_or_create(project_name)
    if lesson not in state.lessons_learned:
        state.lessons_learned.append(lesson)
    return save_state(state)


def add_open_question(project_name: str, question: str) -> ProjectState:
    """Add an open question that requires Noah's answer."""
    state = get_or_create(project_name)
    if question not in state.open_questions:
        state.open_questions.append(question)
        state.approval_required = True
        state.approval_reason = f"Open question requires Noah: {question[:80]}"
    return save_state(state)


def add_unknown(project_name: str, unknown: str) -> ProjectState:
    """Add a preserved unknown. Never infer — preserve and label."""
    state = get_or_create(project_name)
    if unknown not in state.unknowns:
        state.unknowns.append(unknown)
    return save_state(state)


def summarize_state(project_name: str) -> str:
    """Return the full resume prompt for a project."""
    state = load_state(project_name)
    if not state:
        return f"No state found for project '{project_name}'."
    return state.resume_prompt()


def resume_prompt(project_name: str) -> str:
    """Alias for summarize_state — used at ORACLE startup."""
    return summarize_state(project_name)


# ── Seed current ORACLE.AI state ───────────────────────────────────────────────

def _seed_oracle_ai_state():
    """
    Seed the canonical ORACLE.AI project state.
    Only runs if state doesn't exist or is missing key fields.
    Never overwrites verified progress.
    """
    existing = load_state("ORACLE.AI")
    if existing and existing.last_completed_step:
        return existing   # already seeded — don't overwrite

    state = ProjectState(
        project_name="ORACLE.AI",
        current_goal=(
            "Build a governed local AI operating system: ORACLE (memory/continuity) + "
            "SOV1 (operator layer) + governed autonomy architecture."
        ),
        current_phase="governed local system build",
        last_completed_step="Notepad fallback fix and targeted input guard committed",
        last_completed_evidence="commit 6e56ffa — 30/30 smoke tests, 8/8 sov1 smoke tests",
        current_blocker=(
            "qwen2.5:7b is unreliable for desktop computer use. "
            "It hallucinates success without verifying screen state. "
            "Action layer needs Semantic UI Bridge / deterministic Actuation Engine."
        ),
        blocker_evidence=(
            "Live test: 'open chrome and go to chatgpt' — model reported success, "
            "nothing happened on screen. focus_window called 3x, type_text fired into "
            "wrong window, model hallucinated completion."
        ),
        next_recommended_step="Build core/semantic_ui_bridge.py — deterministic Windows UI element targeting via pywinauto",
        next_step_reason=(
            "Without semantic element targeting, SOV1 falls back to blind pixel coordinates. "
            "7B model cannot reliably maintain multi-step visual state. "
            "Deterministic UIAutomation targeting removes model judgment from input field location."
        ),
        active_files=[
            "core/oracle.py", "core/sov1.py", "core/oracle_runtime.py",
            "core/targeted_input.py", "core/action_batch.py",
            "core/curiosity_engine.py", "core/self_prompt_loop.py",
            "core/computer_control.py", "core/window_janitor.py",
            "core/chatgpt_bridge.py", "core/project_state.py",
        ],
        relevant_commits=[
            "6e56ffa — Notepad fix + targeted input guard (30/30 smoke tests)",
            "c52abb5 — Runtime orchestrator + window janitor + ChatGPT bridge",
            "ee91b01 — Extended action batches with progress verification (30/30)",
        ],
        failed_attempts=[
            {
                "step": "Desktop computer use via qwen2.5:7b",
                "failure": "Model hallucinates success without verifying screen state",
                "evidence": "focus_window x3, type_text into wrong window, reported 'navigating to chatgpt.com' — nothing happened",
                "at": datetime.now(timezone.utc).isoformat(),
            },
            {
                "step": "Notepad fallback",
                "failure": "SOV1 was opening Notepad as typing fallback for ChatGPT/Claude goals",
                "evidence": "Multiple sessions showed open_program(notepad) when goal was ChatGPT interaction",
                "at": datetime.now(timezone.utc).isoformat(),
            },
        ],
        lessons_learned=[
            "qwen2.5:7b can summarize and classify but cannot reliably execute multi-step computer use",
            "Use clipboard paste (Ctrl+V) not type_text for text injection — more reliable",
            "focus_window + paste_text is the correct path for ChatGPT/Claude input, not open_program + Notepad",
            "Screen hash verification needed after every type/paste to confirm text appeared",
            "Semantic UI Bridge (pywinauto UIAutomation) required for deterministic element targeting",
        ],
        open_questions=[
            "Will Noah fund API access for cloud Claude to enable reliable computer use?",
            "Should SOV1 be disabled entirely in local-only mode to prevent hallucinated actions?",
            "Is Semantic UI Bridge the next build or Action Candidates queue?",
        ],
        approval_required=True,
        approval_reason="Open questions require Noah's direction before next major build decision",
        confidence=0.72,
        unknowns=[
            "Whether pywinauto/uiautomation can reliably find ChatGPT input field in Chrome",
            "Whether qwen2.5:7b can maintain state if given a smaller, more constrained tool set",
            "Timeline for API budget to enable cloud-based computer use",
        ],
    )
    return save_state(state)


# ── Smoke test ────────────────────────────────────────────────────────────────

def _smoke_test() -> bool:
    print("=" * 60)
    print("project_state.py — Smoke Test")
    print("=" * 60)

    import tempfile, os
    # Use a temp file so smoke tests don't pollute real state
    global STATES_FILE
    original_file = STATES_FILE
    tmp = Path(tempfile.mktemp(suffix=".json"))
    STATES_FILE = tmp

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

    try:
        # 1. Create and load state
        state = get_or_create("TestProject", current_goal="Build the test module")
        check("get_or_create creates new state", state is not None)
        check("project_name is set", state.project_name == "TestProject")
        check("current_goal is set", "test module" in state.current_goal)

        # 2. Save and reload
        save_state(state)
        loaded = load_state("TestProject")
        check("load_state retrieves saved state", loaded is not None)
        check("Loaded project_name matches", loaded.project_name == "TestProject")
        check("Loaded goal matches", loaded.current_goal == state.current_goal)

        # 3. Record completed step with evidence
        s2 = record_completed_step("TestProject", "Built smoke test", evidence="30/30 tests passing")
        check("record_completed_step sets last_completed_step", s2.last_completed_step == "Built smoke test")
        check("Evidence is stored", "30/30" in s2.last_completed_evidence)

        # 4. Record blocker
        s3 = record_blocker("TestProject", "Missing dependency X", evidence="ImportError on startup")
        check("record_blocker sets current_blocker", "Missing dependency X" in s3.current_blocker)
        check("Blocker evidence stored", "ImportError" in s3.blocker_evidence)
        check("Confidence reduced after blocker", s3.confidence < 0.5)

        # 5. Record failed attempt
        s4 = record_failed_attempt("TestProject", "Deploy step", "Port 8080 already in use", "log output")
        check("Failed attempt recorded", len(s4.failed_attempts) >= 1)
        check("Failure details preserved", s4.failed_attempts[-1]["failure"] == "Port 8080 already in use")

        # 6. Set next step
        s5 = set_next_step("TestProject", "Fix port conflict", reason="Port 8080 is occupied by another service")
        check("next_recommended_step set", s5.next_recommended_step == "Fix port conflict")
        check("next_step_reason set", "port 8080" in s5.next_step_reason.lower())

        # 7. Add lesson and unknown
        s6 = add_lesson("TestProject", "Always check port availability before deploy")
        check("Lesson added", any("Always check port" in l for l in s6.lessons_learned))
        s7 = add_unknown("TestProject", "Whether service auto-restarts on reboot")
        check("Unknown preserved", any("auto-restarts" in u for u in s7.unknowns))

        # 8. Add open question
        s8 = add_open_question("TestProject", "Should we use port 9090 instead?")
        check("Open question added", any("9090" in q for q in s8.open_questions))
        check("approval_required set when question added", s8.approval_required)

        # 9. Reload from disk — all fields survive
        final = load_state("TestProject")
        check("Failed attempts survive reload", len(final.failed_attempts) >= 1)
        check("Lessons survive reload", len(final.lessons_learned) >= 1)
        check("Unknowns survive reload", len(final.unknowns) >= 1)
        check("Open questions survive reload", len(final.open_questions) >= 1)
        check("Blocker survives reload", bool(final.current_blocker))
        check("next_step survives reload", bool(final.next_recommended_step))

        # 10. Resume prompt
        prompt = final.resume_prompt()
        check("resume_prompt() builds without crash", bool(prompt))
        check("Resume prompt contains project name", "TestProject" in prompt)
        check("Resume prompt contains current goal", "test module" in prompt)
        check("Resume prompt contains blocker", "Missing dependency" in prompt)
        check("Resume prompt contains next step", "Fix port" in prompt)
        check("Resume prompt contains unknowns section", "UNKNOWN" in prompt)
        check("Resume prompt contains confidence", "Confidence" in prompt)

        # 11. summarize_state alias works
        summary = summarize_state("TestProject")
        check("summarize_state() works", bool(summary))

        # 12. No invented progress
        blank = get_or_create("BlankProject")
        check("New project has no invented last_completed_step", not blank.last_completed_step)
        check("New project has no invented blocker", not blank.current_blocker)
        check("New project has empty failed_attempts", len(blank.failed_attempts) == 0)

        # 13. list_projects
        projects = list_projects()
        check("list_projects returns known projects", "TestProject" in projects)

        # 14. clear_blocker
        s9 = clear_blocker("TestProject", resolution="Found correct port in config")
        check("clear_blocker removes blocker", not s9.current_blocker)
        check("Resolution added to lessons", any("correct port" in l for l in s9.lessons_learned))

        # 15. state.summary() one-liner
        sm = final.summary()
        check("summary() one-liner builds", bool(sm))
        check("summary() contains project name", "TestProject" in sm)

    finally:
        STATES_FILE = original_file
        try:
            tmp.unlink()
        except Exception:
            pass

    print(f"\n{passed}/{passed + failed} smoke tests passed.")
    if failed:
        print(f"FAILED: {failed} test(s).")
    else:
        print("All smoke tests passed.")
    return failed == 0


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    args = sys.argv[1:]

    if "--smoke" in args or "smoke" in args:
        ok = _smoke_test()
        sys.exit(0 if ok else 1)

    if "--seed" in args:
        state = _seed_oracle_ai_state()
        print(f"\nSeeded project state: {state.project_name}")
        print(state.resume_prompt())
        sys.exit(0)

    if "--resume" in args:
        name = "ORACLE.AI"
        for i, a in enumerate(args):
            if a == "--project" and i + 1 < len(args):
                name = args[i + 1]
        print(summarize_state(name))
        sys.exit(0)

    if "--status" in args:
        projects = list_projects()
        if not projects:
            print("No project states saved yet. Run --seed to initialize ORACLE.AI.")
        for p in projects:
            state = load_state(p)
            if state:
                print(f"\n{state.summary()}")
        sys.exit(0)

    print("Usage:")
    print("  python core/project_state.py --smoke         Run smoke tests")
    print("  python core/project_state.py --seed          Seed ORACLE.AI current state")
    print("  python core/project_state.py --resume        Print ORACLE.AI resume prompt")
    print("  python core/project_state.py --status        List all project states")
    sys.exit(0)


if __name__ == "__main__":
    main()
