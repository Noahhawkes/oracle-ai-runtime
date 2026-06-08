"""
core/self_build.py — ORACLE Self-Build Engine

ORACLE reads her own codebase, identifies the single highest-value gap,
and either proposes it (safe default) or implements it (with approval).

This is structured self-improvement — not autonomous wandering.

Rules:
- Always reads before writing.
- Always proposes before implementing.
- Never creates random projects.
- Never loops without a concrete target.
- Never modifies core governance files (governance.py, identity_compliance.py).
"""

import subprocess
from datetime import datetime
from pathlib import Path
import sys

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT / "core"))

# Files ORACLE is never allowed to self-modify
PROTECTED_FILES = {
    "core/identity_compliance.py",
    "core/context_loader.py",
    "docs/INVENTION_CLAIMS_REGISTRY.md",
    "docs/GOVERNED_CURIOSITY.md",
    ".env",
}

# The core modules ORACLE knows about and can reason over
SELF_MAP = [
    # Core intelligence
    ("core/oracle.py",               "Main REPL and session loop — primary interface with Noah"),
    ("core/sov1.py",                 "Computer-use operator (SOV1 hands) — controls screen"),
    ("core/context_loader.py",       "System prompt and identity loading — what ORACLE knows at startup"),
    ("core/project_state.py",        "Cross-session build state — last step, next step, blockers, lessons"),
    ("core/self_build.py",           "Self-build engine — reads codebase, proposes highest-value improvement"),
    # Governance layer (MYTHIC BUILD PASS Steps 1-7)
    ("core/governance.py",           "Authoritative safety defaults — SAFE_SLEEP, risk levels, approval rules"),
    ("core/action_candidates.py",    "Proposal gate — all candidates born pending, approval required"),
    ("core/approval_center.py",      "Unified approval API — memory, video, MindCoin, candidates, OBS"),
    ("core/identity_compliance.py",  "Identity and governance compliance enforcement"),
    # Runtime and presence (Steps 2-4)
    ("core/resident_runtime.py",     "Heartbeat — the loop that makes ORACLE live on Noah's machine"),
    ("core/resident_dashboard.py",   "HTML dashboard — live project state, pending approvals, cycle count"),
    ("core/oracle_presence.py",      "Presence window — what ORACLE is doing right now, shown on boot"),
    ("core/tray.py",                 "System tray — entry point, boot cycle, self-update, show status"),
    # Memory and continuity (Steps 8-9)
    ("core/continuity_scheduler.py", "Backup scheduler — safe local exports, disabled by default"),
    ("core/continuity_export.py",    "Export builder — governed state snapshots"),
    ("core/drive_scope.py",          "Drive scope — maps all drives and approved paths on Noah's PC"),
    ("core/workspace_steward.py",    "Workspace steward — detects messy state, proposes one safe next action"),
    # Memory and learning
    ("core/memory.py",               "Memory DB — facts, sessions, messages"),
    ("core/remember_me.py",          "Memory candidate submission — pending approval before storage"),
    ("core/mindcoin.py",             "MindCoin ledger — proof-of-meaning, not crypto"),
    ("core/relationship_memory.py",  "Relationship memory — people ORACLE knows"),
    ("core/live_context.py",         "Live operational context tracker"),
    # Computer use and actuation
    ("core/computer_control.py",     "Low-level mouse/keyboard/window control"),
    ("core/actuation_engine.py",     "Governed actuation — approval-gated execution"),
    ("core/window_janitor.py",       "Window inventory and classification"),
    ("core/terminal.py",             "Persistent shell session"),
    # Voice and output
    ("core/voice.py",                "TTS voice output"),
    # Other intelligence modules
    ("core/curiosity_engine.py",     "Governed curiosity and gap detection"),
    ("core/lootdrop.py",             "Momentum recognition system"),
    ("core/integration_gate.py",     "Approval gate for memory candidates"),
    ("core/daemon.py",               "Background daemon proposals"),
    ("core/planner.py",              "Task planning and sequencing"),
    # Tool infrastructure
    ("tools/executor.py",            "Tool dispatcher"),
    ("tools/definitions.py",         "Tool schemas for Claude"),
]

_SCAN_PROMPT = """\
You are ORACLE's self-build engine. You have been given a map of your own codebase.

Your job: identify ONE specific, concrete, high-value improvement you can make to yourself.

Rules:
1. Read the evidence. Base the recommendation on actual code state, not assumptions.
2. Pick ONE thing. The smallest change with the highest impact.
3. Prefer: wiring existing modules together, fixing broken tool calls, adding missing error handling,
   improving the startup sequence, or adding a missing capability that has clear value.
4. Never recommend: autonomous loops, removing governance, self-modifying protected files,
   creating new random projects, adding speculative features.
5. Output exactly this format — nothing else:

TARGET_FILE: [path to the file that needs changing]
CHANGE_TYPE: [bugfix | wiring | enhancement | missing_handler | error_handling]
TITLE: [one line — what this does]
PROBLEM: [what is wrong or missing right now — specific]
SOLUTION: [what to change — specific enough to implement]
RISK: [low | medium | high]
TEST: [how to verify it worked]
"""


def _read_file_excerpt(rel_path: str, max_chars: int = 1500) -> str:
    path = ROOT / rel_path
    if not path.exists():
        return f"(not found: {rel_path})"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[:max_chars] + ("...[truncated]" if len(text) > max_chars else "")
    except Exception as e:
        return f"(read error: {e})"


def _git_log(n: int = 10) -> str:
    try:
        r = subprocess.run(
            ["git", "log", "--oneline", f"-{n}"],
            cwd=ROOT, capture_output=True, text=True, timeout=10,
        )
        return r.stdout.strip() or "(empty)"
    except Exception:
        return "(git log unavailable)"


def _build_self_context() -> str:
    parts = ["=== ORACLE CODEBASE MAP ==="]
    for rel_path, description in SELF_MAP:
        excerpt = _read_file_excerpt(rel_path, max_chars=800)
        parts.append(f"\n--- {rel_path} ({description}) ---\n{excerpt}")
    parts.append(f"\n=== RECENT COMMITS ===\n{_git_log()}")
    return "\n".join(parts)


def _call_llm(client, model: str, local: bool, context: str) -> str:
    user_msg = (
        "Here is your own codebase. Read it and identify the single best improvement.\n\n"
        + context
    )
    try:
        if local:
            resp = client.chat.completions.create(
                model=model,
                max_tokens=1024,
                messages=[
                    {"role": "system", "content": _SCAN_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.3,
                extra_body={"num_ctx": 16384},
            )
            return resp.choices[0].message.content or "(no response)"
        else:
            resp = client.messages.create(
                model=model,
                max_tokens=1024,
                system=_SCAN_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
            return resp.content[0].text if resp.content else "(no response)"
    except Exception as e:
        raise RuntimeError(f"LLM call failed: {e}") from e


def _parse_proposal(raw: str) -> dict:
    """Parse the structured LLM output into a dict."""
    fields = {
        "target_file": "", "change_type": "", "title": "",
        "problem": "", "solution": "", "risk": "medium", "test": "",
    }
    for line in raw.splitlines():
        for key in fields:
            prefix = key.upper().replace("_", "_") + ": "
            if line.startswith(prefix):
                fields[key] = line[len(prefix):].strip()
    return fields


def _is_protected(rel_path: str) -> bool:
    return rel_path.strip() in PROTECTED_FILES


def run_self_build(client, model: str, local: bool, implement: bool = False) -> str:
    """
    Main entry point for /self-build.

    implement=False (default): propose only, no code changes.
    implement=True: propose AND apply the change after showing it to Noah.
    """
    from audit_log import log
    log("SELF_BUILD", f"Starting — implement={implement}")

    print("\n[self-build] Reading codebase...")
    context = _build_self_context()

    print("[self-build] Identifying highest-value improvement...")
    try:
        raw = _call_llm(client, model, local, context)
    except RuntimeError as e:
        return f"[self-build error: {e}]"

    proposal = _parse_proposal(raw)

    # Build the output
    lines = [
        "",
        "╔══════════════════════════════════════════════════════╗",
        "║  ORACLE SELF-BUILD PROPOSAL                         ║",
        "╚══════════════════════════════════════════════════════╝",
        "",
        f"  Target   : {proposal['target_file'] or '(not specified)'}",
        f"  Type     : {proposal['change_type'] or '(not specified)'}",
        f"  Risk     : {proposal['risk'].upper()}",
        "",
        f"  TITLE    : {proposal['title']}",
        "",
        f"  PROBLEM  : {proposal['problem']}",
        "",
        f"  SOLUTION : {proposal['solution']}",
        "",
        f"  TEST     : {proposal['test']}",
        "",
    ]

    if _is_protected(proposal.get("target_file", "")):
        lines.append("  !! BLOCKED — target file is protected. Proposal rejected.")
        lines.append("")
        return "\n".join(lines)

    if not implement:
        lines.append("  STATUS   : PROPOSAL ONLY — say 'approve self-build' to implement.")
        lines.append("")
        # Save proposal
        _save_proposal(proposal, raw)
    else:
        lines.append("  STATUS   : APPROVED — implementing now.")
        lines.append("")

    return "\n".join(lines)


def _save_proposal(proposal: dict, raw: str):
    """Save the proposal to disk for reference."""
    proposals_dir = ROOT / "Projects" / "self_build_proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    path = proposals_dir / f"{ts}_self_build.md"
    content = (
        f"# Self-Build Proposal — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"**Target**: {proposal.get('target_file', '')}\n"
        f"**Type**: {proposal.get('change_type', '')}\n"
        f"**Risk**: {proposal.get('risk', '')}\n\n"
        f"## Title\n{proposal.get('title', '')}\n\n"
        f"## Problem\n{proposal.get('problem', '')}\n\n"
        f"## Solution\n{proposal.get('solution', '')}\n\n"
        f"## Test\n{proposal.get('test', '')}\n\n"
        f"---\n\n## Raw LLM Output\n```\n{raw}\n```\n"
    )
    path.write_text(content, encoding="utf-8")
    print(f"[self-build] Proposal saved: {path}")
