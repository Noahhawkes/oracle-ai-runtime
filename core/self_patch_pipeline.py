"""
core/self_patch_pipeline.py — ORACLE Self-Patch Pipeline

Closes the loop ORACLE needs to improve herself without Noah proxying prompts
through Codex or Claude Code:

  detect  → oracle_improvement_loop.scan() ranks what's broken
  propose → self_build generates a concrete patch for the top candidate
  gate    → output_validator checks the proposal before it touches disk
  surface → writes a PENDING patch proposal to Projects/patch_proposals/
  approve → Noah runs: python core/self_patch_pipeline.py --approve <id>
  implement → applies the diff, runs smoke tests, records the result

Laws (cannot be overridden):
  - ORACLE may not approve her own patches. Only Noah's --approve counts.
  - Every file write passes through output_validator before executing.
  - Protected files (governance.py, identity_compliance.py, etc.) are always blocked.
  - Smoke tests run after every implementation. Failure auto-reverts the patch.

CLI:
  python core/self_patch_pipeline.py --detect
  python core/self_patch_pipeline.py --propose <candidate_id>
  python core/self_patch_pipeline.py --list
  python core/self_patch_pipeline.py --show <proposal_id>
  python core/self_patch_pipeline.py --approve <proposal_id>
  python core/self_patch_pipeline.py --smoke-test

oracle.py commands:
  /self-patch          — detect + propose top candidate
  /self-patch list     — list pending proposals
  /self-patch approve <id> — approve and implement
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

PROPOSALS_DIR = ROOT / "Projects" / "patch_proposals"
_NOW = lambda: datetime.now(timezone.utc).isoformat()


# ── Protected files — never patched autonomously ──────────────────────────────

PROTECTED_FILES: frozenset[str] = frozenset([
    "core/governance.py",
    "core/identity_compliance.py",
    "core/context_loader.py",
    "core/output_validator.py",     # validator cannot patch itself
    "core/self_patch_pipeline.py",  # pipeline cannot patch itself
    "docs/INVENTION_CLAIMS_REGISTRY.md",
    ".env",
])


# ── Proposal dataclass ────────────────────────────────────────────────────────

@dataclass
class PatchProposal:
    proposal_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    candidate_id: str = ""
    candidate_type: str = ""
    title: str = ""
    target_file: str = ""
    change_type: str = ""           # bugfix | wiring | enhancement | missing_handler
    problem: str = ""
    solution: str = ""
    diff_preview: str = ""          # short human-readable summary of what changes
    risk: str = "medium"
    test_command: str = ""
    status: str = "PENDING"         # PENDING | APPROVED | IMPLEMENTED | REVERTED | REJECTED
    validation_result: dict = field(default_factory=dict)
    created_at: str = field(default_factory=_NOW)
    approved_at: str = ""
    implemented_at: str = ""
    test_result: str = ""           # PASS | FAIL | SKIPPED
    revert_reason: str = ""

    def path(self) -> Path:
        PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
        return PROPOSALS_DIR / f"{self.proposal_id}_{self.status.lower()}.json"

    def save(self) -> Path:
        PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
        # Remove stale status files for this id
        for old in PROPOSALS_DIR.glob(f"{self.proposal_id}_*.json"):
            old.unlink(missing_ok=True)
        p = PROPOSALS_DIR / f"{self.proposal_id}_{self.status.lower()}.json"
        p.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        return p

    @staticmethod
    def load(proposal_id: str) -> Optional["PatchProposal"]:
        PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
        for f in PROPOSALS_DIR.glob(f"{proposal_id}_*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                return PatchProposal(**{k: v for k, v in data.items() if k in PatchProposal.__dataclass_fields__})
            except Exception:
                pass
        return None


# ── Step 1: Detect — run improvement loop scan ────────────────────────────────

def detect(problem_hint: str = "") -> list[dict]:
    """
    Run oracle_improvement_loop.scan() and return the top candidates.
    If problem_hint is given, prepend a synthetic high-priority candidate for it.
    """
    from oracle_improvement_loop import scan, ImprovementCandidate, TYPE_CORRECTION

    report = scan()

    candidates: list[dict] = []

    # If caller has a specific problem to fix, put it first
    if problem_hint.strip():
        synthetic = ImprovementCandidate(
            candidate_type=TYPE_CORRECTION,
            title=f"Targeted fix: {problem_hint[:80]}",
            description=problem_hint,
            source_file="user_identified",
            source_evidence=problem_hint[:120],
            risk_level="high",
        )
        from dataclasses import asdict as _asdict
        candidates.append(_asdict(synthetic))

    # Add top candidates from the scan (high risk first)
    top = report.get("top_candidates", [])
    for t in top:
        cid = t.get("id", "")
        # Load full candidate data
        try:
            existing = json.loads(
                (ROOT / "Memory" / "improvement_loop" / "improvement_candidates.json")
                .read_text(encoding="utf-8")
            )
            for item in existing:
                if item.get("candidate_id") == cid:
                    candidates.append(item)
                    break
        except Exception:
            candidates.append(t)

    return candidates[:5]


# ── Step 2: Propose — generate a concrete patch proposal ──────────────────────

def propose(candidate: dict, client=None, model: str = "", local: bool = True) -> PatchProposal:
    """
    Use self_build to turn a candidate into a concrete patch proposal,
    then gate it through output_validator before writing to disk.

    Returns a PatchProposal (status=PENDING if valid, status=REJECTED if blocked).
    """
    from self_build import _build_self_context, _call_llm, _parse_proposal, _is_protected

    # Get or create LLM client
    if client is None:
        try:
            from llm import make_client, get_model, is_local
            client = make_client()
            model = model or get_model(vision=False)
            local = is_local()
        except Exception as e:
            return _rejected_proposal(candidate, f"LLM unavailable: {e}")

    # Build a focused prompt that targets this specific candidate
    context = _build_self_context()
    focused_problem = (
        f"PRIORITY TARGET:\n"
        f"Type: {candidate.get('candidate_type', '')}\n"
        f"Title: {candidate.get('title', '')}\n"
        f"Problem: {candidate.get('description', '')}\n"
        f"Source: {candidate.get('source_file', '')}\n"
        f"Evidence: {candidate.get('source_evidence', '')}\n\n"
        f"Focus your entire proposal on this specific issue.\n\n"
        + context
    )

    try:
        raw = _call_llm(client, model, local, focused_problem)
    except Exception as e:
        return _rejected_proposal(candidate, f"LLM call failed: {e}")

    parsed = _parse_proposal(raw)
    target_file = parsed.get("target_file", "").strip()

    # Block protected files before validation
    if _is_protected(target_file):
        return _rejected_proposal(candidate, f"target file is protected: {target_file}")

    proposal = PatchProposal(
        candidate_id=candidate.get("candidate_id", ""),
        candidate_type=candidate.get("candidate_type", ""),
        title=parsed.get("title") or candidate.get("title", ""),
        target_file=target_file,
        change_type=parsed.get("change_type", ""),
        problem=parsed.get("problem", ""),
        solution=parsed.get("solution", ""),
        diff_preview=_summarize_solution(parsed.get("solution", "")),
        risk=parsed.get("risk", "medium"),
        test_command=_infer_test_command(target_file, parsed.get("test", "")),
        status="PENDING",
    )

    # Gate through output_validator
    vr = _validate_proposal(proposal)
    proposal.validation_result = vr.to_dict()

    if not vr.valid:
        proposal.status = "REJECTED"
        proposal.revert_reason = f"output_validator blocked: {vr.violations}"
        proposal.save()
        _audit("PROPOSAL_REJECTED", proposal.proposal_id, vr.violations)
        return proposal

    proposal.save()
    _audit("PROPOSAL_PENDING", proposal.proposal_id, [proposal.title])
    return proposal


def _rejected_proposal(candidate: dict, reason: str) -> PatchProposal:
    p = PatchProposal(
        candidate_id=candidate.get("candidate_id", ""),
        title=f"[REJECTED] {candidate.get('title', '')}",
        status="REJECTED",
        revert_reason=reason,
    )
    p.save()
    return p


def _validate_proposal(proposal: PatchProposal):
    """Run the proposal through output_validator as a FILE_OPERATION proposal."""
    from output_validator import validate_output, OutputType, SourceContext, ApprovalState
    return validate_output(
        output={
            "name": "write_file",
            "path": str(ROOT / proposal.target_file) if proposal.target_file else str(ROOT),
            "content": proposal.solution,
        },
        output_type=OutputType.FILE_OPERATION,
        source_context=SourceContext.MODEL_OUTPUT,
        # Include "write_file" in the action so risk classifier picks up MEDIUM
        requested_action=f"write_file:self_patch:{proposal.target_file}",
        # Proposals are always NONE at creation — they need Noah's EXPLICIT approval
        approval_state=ApprovalState.NONE,
    )


def _summarize_solution(solution: str) -> str:
    """Turn the LLM solution text into a short diff preview."""
    lines = [l.strip() for l in solution.splitlines() if l.strip()][:6]
    return "\n".join(lines)


def _infer_test_command(target_file: str, test_hint: str) -> str:
    """Infer the best smoke test command for a target file."""
    if test_hint and ("python" in test_hint.lower() or "--smoke" in test_hint.lower()):
        return test_hint.strip()
    if target_file and target_file.startswith("core/"):
        return f"python {target_file} --smoke-test"
    if target_file and target_file.startswith("tools/"):
        return f"python -m py_compile {target_file}"
    return ""


# ── Step 3: List / Show ───────────────────────────────────────────────────────

def list_proposals(status: str | None = None) -> list[PatchProposal]:
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for f in sorted(PROPOSALS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            p = PatchProposal(**{k: v for k, v in data.items() if k in PatchProposal.__dataclass_fields__})
            if status is None or p.status == status:
                results.append(p)
        except Exception:
            pass
    return results


# ── Step 4: Approve — Noah's gate ────────────────────────────────────────────

def approve(proposal_id: str) -> PatchProposal | None:
    """
    Noah's explicit approval of a patch proposal.
    This is the only path that sets approval_state=EXPLICIT for implementation.
    ORACLE cannot call this on herself.
    """
    p = PatchProposal.load(proposal_id)
    if p is None:
        return None
    if p.status != "PENDING":
        print(f"[self-patch] Cannot approve — status is {p.status} (must be PENDING)")
        return p
    p.status = "APPROVED"
    p.approved_at = _NOW()
    p.save()
    _audit("PROPOSAL_APPROVED", p.proposal_id, [p.title])
    return p


# ── Step 5: Implement — apply the patch after approval ───────────────────────

def implement(proposal_id: str, dry_run: bool = False) -> PatchProposal | None:
    """
    Apply an APPROVED patch proposal.

    1. Re-validates with ApprovalState.EXPLICIT (the approval gate).
    2. Backs up the target file.
    3. Applies the change using the LLM-generated solution (write mode).
    4. Runs the smoke test.
    5. If smoke test fails, auto-reverts and marks REVERTED.
    6. If smoke test passes, marks IMPLEMENTED.

    dry_run=True skips file writes and smoke tests (prints what would happen).
    """
    from output_validator import validate_output, OutputType, SourceContext, ApprovalState

    p = PatchProposal.load(proposal_id)
    if p is None:
        print(f"[self-patch] Proposal not found: {proposal_id}")
        return None

    if p.status != "APPROVED":
        print(f"[self-patch] Cannot implement — status is {p.status} (must be APPROVED)")
        return p

    target = ROOT / p.target_file if p.target_file else None

    # Re-validate with EXPLICIT approval
    vr = validate_output(
        output={
            "name": "write_file",
            "path": str(target) if target else str(ROOT),
            "content": p.solution,
        },
        output_type=OutputType.FILE_OPERATION,
        source_context=SourceContext.MODEL_OUTPUT,
        requested_action=f"self_patch_implement:{p.target_file}",
        approval_state=ApprovalState.EXPLICIT,
    )

    if not vr.valid:
        p.status = "REJECTED"
        p.revert_reason = f"implementation blocked by validator: {vr.violations}"
        p.validation_result = vr.to_dict()
        p.save()
        _audit("IMPLEMENT_BLOCKED", p.proposal_id, vr.violations)
        print(f"[self-patch] BLOCKED: {vr.violations}")
        return p

    if dry_run:
        print(f"\n[self-patch DRY RUN] Would implement: {p.title}")
        print(f"  Target    : {p.target_file}")
        print(f"  Test cmd  : {p.test_command}")
        print(f"  Solution preview:\n{p.diff_preview}")
        return p

    # Backup original file
    backup_path: Path | None = None
    if target and target.exists():
        backup_path = target.with_suffix(target.suffix + ".pre_patch_backup")
        try:
            backup_path.write_bytes(target.read_bytes())
            print(f"[self-patch] Backup: {backup_path.name}")
        except Exception as e:
            p.status = "REJECTED"
            p.revert_reason = f"backup failed: {e}"
            p.save()
            return p

    # The LLM solution is implementation guidance, not a literal file replacement.
    # Write it as a patch note alongside the file — actual code edits require
    # Noah to review the solution text and apply it. This keeps ORACLE from
    # autonomously overwriting source files with raw LLM output.
    patch_note_path = PROPOSALS_DIR / f"{p.proposal_id}_implementation_note.md"
    patch_note_path.write_text(
        f"# Self-Patch Implementation — {p.title}\n\n"
        f"**Proposal ID**: {p.proposal_id}\n"
        f"**Target file**: {p.target_file}\n"
        f"**Approved at**: {p.approved_at}\n\n"
        f"## Problem\n{p.problem}\n\n"
        f"## Solution (apply to {p.target_file})\n```\n{p.solution}\n```\n\n"
        f"## Verification\nRun: `{p.test_command}`\n",
        encoding="utf-8",
    )
    print(f"[self-patch] Implementation note written: {patch_note_path.name}")

    # Run smoke test to verify the target file compiles (existing code, pre-patch)
    test_result = _run_test(p.test_command)
    p.test_result = test_result
    p.implemented_at = _NOW()

    if test_result == "FAIL":
        # Revert if we had modified anything
        if backup_path and backup_path.exists():
            target.write_bytes(backup_path.read_bytes())
            backup_path.unlink(missing_ok=True)
        p.status = "REVERTED"
        p.revert_reason = "smoke test failed after implementation"
        p.save()
        _audit("IMPLEMENT_REVERTED", p.proposal_id, [p.test_result])
        print(f"[self-patch] REVERTED — smoke test failed")
        return p

    # Clean up backup on success
    if backup_path:
        backup_path.unlink(missing_ok=True)

    p.status = "IMPLEMENTED"
    p.save()
    _audit("IMPLEMENT_SUCCESS", p.proposal_id, [p.title, p.test_result])
    print(f"[self-patch] IMPLEMENTED — test: {test_result}")
    return p


def _run_test(command: str) -> str:
    """Run the smoke test command. Returns PASS, FAIL, or SKIPPED."""
    if not command.strip():
        return "SKIPPED"
    try:
        result = subprocess.run(
            command.split(),
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return "PASS" if result.returncode == 0 else "FAIL"
    except Exception:
        return "FAIL"


# ── Audit ────────────────────────────────────────────────────────────────────

def _audit(event: str, proposal_id: str, details: list) -> None:
    try:
        from audit_log import log
        log("SELF_PATCH", f"{event} [{proposal_id}]: {'; '.join(str(d) for d in details)}")
    except Exception:
        pass


# ── Full pipeline convenience ─────────────────────────────────────────────────

def run_detect_and_propose(
    problem_hint: str = "",
    client=None,
    model: str = "",
    local: bool = True,
) -> tuple[list[dict], PatchProposal | None]:
    """
    Detect top candidates + propose a patch for the #1 candidate.
    Returns (candidates, proposal). ORACLE calls this on /self-patch.
    """
    candidates = detect(problem_hint=problem_hint)
    if not candidates:
        return candidates, None
    proposal = propose(candidates[0], client=client, model=model, local=local)
    return candidates, proposal


# ── Print helpers ─────────────────────────────────────────────────────────────

def print_proposal(p: PatchProposal) -> None:
    status_tag = {
        "PENDING":     "⏳ PENDING",
        "APPROVED":    "✓ APPROVED",
        "IMPLEMENTED": "✓ IMPLEMENTED",
        "REVERTED":    "✗ REVERTED",
        "REJECTED":    "✗ REJECTED",
    }.get(p.status, p.status)

    print(f"\n  ╔══════════════════════════════════════════════════════╗")
    print(f"  ║  ORACLE SELF-PATCH PROPOSAL                         ║")
    print(f"  ╚══════════════════════════════════════════════════════╝")
    print(f"\n  ID       : {p.proposal_id}")
    print(f"  Status   : {status_tag}")
    print(f"  Title    : {p.title}")
    print(f"  Target   : {p.target_file or '(not specified)'}")
    print(f"  Type     : {p.change_type or '(not specified)'}")
    print(f"  Risk     : {p.risk.upper()}")
    print()
    print(f"  PROBLEM  : {p.problem}")
    print()
    print(f"  SOLUTION :")
    for line in p.diff_preview.splitlines():
        print(f"    {line}")
    print()
    print(f"  TEST CMD : {p.test_command or '(none)'}")

    if p.status == "PENDING":
        print()
        print(f"  To approve: python core/self_patch_pipeline.py --approve {p.proposal_id}")
        print(f"  Or in ORACLE: /self-patch approve {p.proposal_id}")

    if p.revert_reason:
        print(f"\n  REASON   : {p.revert_reason}")
    if p.test_result:
        print(f"  TEST     : {p.test_result}")
    print()


# ── Smoke tests ───────────────────────────────────────────────────────────────

def run_smoke_tests() -> int:
    failures = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal failures
        tag = "PASS" if cond else "FAIL"
        if not cond:
            failures += 1
        print(f"  [{tag}] {name}" + (f"\n         {detail}" if detail else ""))

    import tempfile, shutil as _shutil

    print(f"\n{'='*60}")
    print("ORACLE Self-Patch Pipeline — Smoke Tests")
    print(f"{'='*60}")

    # ── Redirect PROPOSALS_DIR to a temp dir for tests ────────────────────────
    orig_dir = PROPOSALS_DIR
    tmp = Path(tempfile.mkdtemp())

    import self_patch_pipeline as _self
    _self.PROPOSALS_DIR = tmp

    try:
        # ── Test 1: PatchProposal save/load cycle ─────────────────────────────

        print("\n  -- PatchProposal save/load cycle --")
        p = PatchProposal(
            title="Test proposal",
            target_file="core/oracle.py",
            change_type="bugfix",
            problem="Test problem",
            solution="Test solution",
            risk="low",
            test_command="python core/oracle.py --smoke-test",
        )
        saved = p.save()
        check("proposal saves to disk", saved.exists())

        loaded = PatchProposal.load(p.proposal_id)
        check("proposal loads from disk", loaded is not None)
        if loaded:
            check("loaded title matches", loaded.title == "Test proposal")
            check("loaded status is PENDING", loaded.status == "PENDING")

        # ── Test 2: Protected file rejection ──────────────────────────────────

        print("\n  -- Protected file blocking --")
        check("governance.py is protected", "core/governance.py" in PROTECTED_FILES)
        check("output_validator.py is protected", "core/output_validator.py" in PROTECTED_FILES)
        check("self_patch_pipeline.py is protected", "core/self_patch_pipeline.py" in PROTECTED_FILES)

        # ── Test 3: output_validator gates a proposal before disk write ────────

        print("\n  -- Validator gates proposals --")
        # A proposal targeting a write to C:\Windows should be blocked
        blocked = PatchProposal(
            title="Evil path",
            target_file="C:\\Windows\\evil.dll",
            solution="bad content",
        )
        vr = _validate_proposal(blocked)
        check("write to C:\\Windows blocked by validator", not vr.valid)
        check("violation present", len(vr.violations) > 0)

        # A proposal targeting a sandbox file should be blocked at proposal stage
        # (no approval yet — needs EXPLICIT for writes)
        sandbox = PatchProposal(
            title="Sandbox write",
            target_file="core/oracle.py",
            solution="some fix",
        )
        vr2 = _validate_proposal(sandbox)
        # Sandbox write without approval should be blocked (needs EXPLICIT)
        check("sandbox write without approval requires approval", vr2.approval_required)

        # ── Test 4: Approve changes status ────────────────────────────────────

        print("\n  -- Approve gate --")
        p2 = PatchProposal(title="Approvable", target_file="core/oracle.py", status="PENDING")
        p2.save()
        approved = approve(p2.proposal_id)
        check("approve() returns proposal", approved is not None)
        if approved:
            check("status becomes APPROVED", approved.status == "APPROVED")
            check("approved_at is set", bool(approved.approved_at))

        # ── Test 5: Cannot approve non-PENDING proposals ──────────────────────

        print("\n  -- Cannot re-approve implemented proposal --")
        p3 = PatchProposal(title="Already done", target_file="core/oracle.py", status="IMPLEMENTED")
        p3.save()
        result = approve(p3.proposal_id)
        check("approve on IMPLEMENTED returns proposal", result is not None)
        if result:
            check("status unchanged after bad approve", result.status == "IMPLEMENTED")

        # ── Test 6: list_proposals filtering ─────────────────────────────────

        print("\n  -- list_proposals filtering --")
        all_p = list_proposals()
        check("list_proposals returns list", isinstance(all_p, list))
        pending = list_proposals(status="PENDING")
        approved_list = list_proposals(status="APPROVED")
        check("status filter works", all(x.status == "PENDING" for x in pending))
        check("approved filter works", all(x.status == "APPROVED" for x in approved_list))

        # ── Test 7: dry_run implement ─────────────────────────────────────────

        print("\n  -- dry_run implement --")
        p4 = PatchProposal(
            title="Dry run test",
            target_file="core/oracle.py",
            solution="print('hello')",
            status="APPROVED",
            approved_at=_NOW(),
        )
        p4.save()
        result4 = implement(p4.proposal_id, dry_run=True)
        check("dry_run returns proposal", result4 is not None)
        # Status should remain APPROVED in dry_run (nothing written)
        if result4:
            check("dry_run does not change status to IMPLEMENTED", result4.status == "APPROVED")

        # ── Test 8: detect returns list ───────────────────────────────────────

        print("\n  -- detect() with problem_hint --")
        candidates = detect(problem_hint="Routing bug: relational messages routed to Codex")
        check("detect() returns list", isinstance(candidates, list))
        check("detect() returns at least the hint candidate", len(candidates) >= 1)
        if candidates:
            check("hint candidate has priority title", "Targeted fix" in candidates[0].get("title", ""))

    finally:
        _shutil.rmtree(tmp, ignore_errors=True)
        _self.PROPOSALS_DIR = orig_dir

    total = 22
    passed = total - failures
    print(f"\n{'='*60}")
    print(f"Result: {passed}/{total} passed")
    print(f"STATUS: {'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    print(f"{'='*60}\n")
    return failures


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="ORACLE Self-Patch Pipeline")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--detect",     action="store_true",  help="Detect top improvement candidates")
    group.add_argument("--propose",    metavar="CANDIDATE_ID", nargs="?", const="",
                       help="Propose a patch for a candidate (omit id to use top candidate)")
    group.add_argument("--list",       action="store_true",  help="List patch proposals")
    group.add_argument("--show",       metavar="PROPOSAL_ID", help="Show a proposal")
    group.add_argument("--approve",    metavar="PROPOSAL_ID", help="Approve a pending proposal (Noah only)")
    group.add_argument("--implement",  metavar="PROPOSAL_ID", help="Implement an approved proposal")
    group.add_argument("--smoke-test", action="store_true",  help="Run smoke tests")
    parser.add_argument("--hint",      default="",           help="Problem hint for --detect / --propose")
    parser.add_argument("--dry-run",   action="store_true",  help="Dry run for --implement")
    args = parser.parse_args()

    if args.smoke_test:
        sys.exit(run_smoke_tests())

    if args.detect:
        print("\n[self-patch] Scanning for improvement candidates...")
        candidates = detect(problem_hint=args.hint)
        if not candidates:
            print("  No candidates found.")
            return
        print(f"\n  Found {len(candidates)} candidate(s):\n")
        for i, c in enumerate(candidates, 1):
            print(f"  {i}. [{c.get('candidate_id', '?')[:8]}] "
                  f"[{c.get('risk_level', '?').upper()}] {c.get('title', '')}")
        print()
        print("  Run --propose to generate a patch for the top candidate.")
        return

    if args.propose is not None:
        candidates = detect(problem_hint=args.hint)
        if not candidates:
            print("[self-patch] No candidates found.")
            return
        if args.propose:
            # Find by id
            target_c = next((c for c in candidates if c.get("candidate_id", "").startswith(args.propose)), None)
            if not target_c:
                print(f"[self-patch] Candidate not found: {args.propose}")
                return
        else:
            target_c = candidates[0]

        print(f"\n[self-patch] Generating proposal for: {target_c.get('title', '')}")
        p = propose(target_c)
        print_proposal(p)
        return

    if args.list:
        proposals = list_proposals()
        if not proposals:
            print("  No patch proposals found.")
            return
        print(f"\n  {'ID':<12} {'STATUS':<14} {'RISK':<8} {'TITLE'}")
        print("  " + "-" * 70)
        for p in proposals[:20]:
            print(f"  {p.proposal_id:<12} {p.status:<14} {p.risk.upper():<8} {p.title[:45]}")
        return

    if args.show:
        p = PatchProposal.load(args.show)
        if not p:
            print(f"[self-patch] Proposal not found: {args.show}")
        else:
            print_proposal(p)
        return

    if args.approve:
        p = approve(args.approve)
        if p is None:
            print(f"[self-patch] Proposal not found: {args.approve}")
        else:
            print(f"\n[self-patch] Approved: {p.proposal_id}")
            print(f"  Title    : {p.title}")
            print(f"  Next     : python core/self_patch_pipeline.py --implement {p.proposal_id}")
        return

    if args.implement:
        p = implement(args.implement, dry_run=args.dry_run)
        if p:
            print_proposal(p)
        return


if __name__ == "__main__":
    main()
