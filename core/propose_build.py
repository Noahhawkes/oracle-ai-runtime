"""
/propose-build — Read-only build recommendation engine.

Reads build documents, repo state, and memory to recommend one safe next
build task.  Writes a timestamped Markdown proposal to Projects/build_proposals/.
Never edits code, never commits, never runs Claude Code.
"""

import subprocess
from datetime import datetime
from pathlib import Path

if __import__("sys").path and str(Path(__file__).parent) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(Path(__file__).parent))

from audit_log import log

ROOT = Path(__file__).parent.parent

# Documents read as build guidance, in priority order
_GUIDE_DOCS = [
    ("docs/ORACLE_SYSTEM_CONSOLIDATION.md", 3000),
    ("docs/GITHUB_SYSTEMS_INDEX.md",         2000),
    ("docs/SELF_BUILD_MODE_PLAN.md",         2000),
    ("objectives.yaml",                      1500),
    ("config.yaml",                          1000),
]

_SYSTEM_PROMPT = """\
You are ORACLE's read-only build planner.

You have been given the ORACLE.AI system inventory, safety plan, objectives,
and recent git history.  Your job is to recommend exactly ONE safe, high-value
next build task that Noah should work on.

Hard rules:
- This is proposal-only.  Do not write code.  Do not describe implementation steps
  in detail.  Write a recommendation document only.
- Recommend only tasks that fit inside the existing repo structure.
- Do not recommend autonomous loops, automatic commits, or self-modification.
- Do not recommend tasks that are already built (check the git log).
- Prefer small, safe, high-value tasks that unblock the next milestone.
- If the most valuable task is a bug fix or test, recommend that over a new feature.

Output exactly this Markdown format — no preamble, no extra text outside it:

## Recommended Task
[one sentence — imperative, specific]

## Why It Matters
[2-3 sentences — what problem it solves, what it unblocks]

## Files Likely Involved
- [path] — [what changes and why]

## Risk Level
[Low / Medium / High] — [one sentence]

## Acceptance Test
[what Noah should verify after implementation to confirm it works]

## Claude Code Prompt Draft
```
[a ready-to-use prompt Noah can paste directly to Claude Code]
```

## Status
PROPOSAL ONLY — Noah must approve before any implementation begins.
"""


def _read(rel_path: str, max_chars: int) -> str:
    path = ROOT / rel_path
    if not path.exists():
        return f"(not found)"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n... [truncated at {max_chars} chars]"
        return text
    except Exception as e:
        return f"(read error: {e})"


def _git_log(n: int = 15) -> str:
    try:
        r = subprocess.run(
            ["git", "log", "--oneline", f"-{n}"],
            cwd=ROOT, capture_output=True, text=True, timeout=10,
        )
        return r.stdout.strip() or "(empty)"
    except Exception as e:
        return f"(error: {e})"


def _git_status() -> str:
    try:
        r = subprocess.run(
            ["git", "status", "--short"],
            cwd=ROOT, capture_output=True, text=True, timeout=10,
        )
        return r.stdout.strip() or "(clean)"
    except Exception as e:
        return f"(error: {e})"


def _build_context() -> str:
    sections = []
    for rel_path, max_chars in _GUIDE_DOCS:
        content = _read(rel_path, max_chars)
        sections.append(f"=== {rel_path} ===\n{content}")

    sections.append(f"=== git log (last 15 commits) ===\n{_git_log()}")
    sections.append(f"=== git status ===\n{_git_status()}")

    try:
        from memory import get_facts
        facts = get_facts()
        if facts:
            lines = [f"[{f['category']}] {f['key']}: {f['value']}" for f in facts[:20]]
            sections.append("=== memory facts ===\n" + "\n".join(lines))
    except Exception:
        pass

    return "\n\n".join(sections)


def _call_llm(client, model: str, local: bool, context: str) -> str:
    user_msg = (
        "Here is the current ORACLE.AI system state and build documentation.\n\n"
        + context
        + "\n\nWrite a build proposal for the single highest-value next task."
    )
    try:
        if local:
            resp = client.chat.completions.create(
                model=model,
                max_tokens=2048,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user",   "content": user_msg},
                ],
            )
            return resp.choices[0].message.content or "(no response)"
        else:
            resp = client.messages.create(
                model=model,
                max_tokens=2048,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
            return resp.content[0].text if resp.content else "(no response)"
    except Exception as e:
        raise RuntimeError(f"LLM call failed: {e}") from e


def run_propose_build(client, model: str, local: bool) -> str:
    """
    Entry point for /propose-build.

    Reads build docs + repo state, calls LLM, writes a timestamped proposal
    to Projects/build_proposals/, and returns the full proposal text for display.
    Never edits source files.  Never commits.  Never runs Claude Code.
    """
    log("PROPOSE", "/propose-build started")
    print("[propose-build] Reading build documents and repo state...")

    context = _build_context()

    print("[propose-build] Calling LLM for recommendation...")
    try:
        proposal_body = _call_llm(client, model, local, context)
    except RuntimeError as e:
        log("ERROR", str(e))
        return f"[propose-build error: {e}]"

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    proposals_dir = ROOT / "Projects" / "build_proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    proposal_path = proposals_dir / f"{timestamp}.md"

    header = (
        f"# Build Proposal — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"Generated by: /propose-build (read-only mode)\n\n"
        f"---\n\n"
    )
    full_doc = header + proposal_body
    proposal_path.write_text(full_doc, encoding="utf-8")

    log("PROPOSE", f"Proposal saved: {proposal_path}")
    print(f"[propose-build] Saved to: {proposal_path}\n")

    return full_doc
