"""Bounded Subagent Dispatcher (V1).

When a goal is blocked by a code failure, ORACLE packages it into a precise,
self-contained .AI:CLAUDE_CODE_BUILD directive that a coding agent (Claude Code /
Codex) can execute, and records the dispatch to a rolling ledger. This is the
"formulate the ask + record it" step, NOT autonomous execution: ORACLE does not
run the agent or apply patches herself. Humans/agents pick the directive up.

Honors the storage compaction rule: directives append to ONE jsonl ledger, not a
file per directive. Pure stdlib.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DIRECTIVES_LEDGER = ROOT / "data" / "ledger" / "build_directives.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


def formulate_directive(*, title: str, mission: str,
                        files_to_inspect: list[str] | None = None,
                        failure: str = "",
                        tests_to_run: list[str] | None = None,
                        repo_root: str = r"C:\Oracle\ORACLE.AI-runtime",
                        authority: str = "Noah.Physical") -> str:
    """Build a bounded, deterministic .AI:CLAUDE_CODE_BUILD directive string."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    inspect = "\n".join(f"  - {f}" for f in (files_to_inspect or [])) or "  - (agent determines)"
    tests = "\n".join(f"  - {t}" for t in (tests_to_run or [])) or "  - pytest tests/ -q"
    return (
        f".AI:CLAUDE_CODE_BUILD/{_slug(title)}/{stamp}\n"
        f"AUTHORITY={authority}\n"
        f"REPO_ROOT={repo_root}\n"
        f"MODE=BOUNDED_FIX_TEST_RECEIPT\n\n"
        f"MISSION\n{mission.strip()}\n\n"
        f"OBSERVED_FAILURE\n{failure.strip() or 'see MISSION'}\n\n"
        f"FILES_TO_INSPECT\n{inspect}\n\n"
        f"RULES\n"
        f"  - Smallest safe change. Add/So update focused tests. Preserve provenance.\n"
        f"  - Do not mutate the sandbox. Do not commit/push without Noah approval.\n"
        f"  - If authority is required, stop and report; do not exceed scope.\n\n"
        f"TESTS_TO_RUN\n{tests}\n\n"
        f"RETURN\n  ROOT_CAUSE= FILES_CHANGED= TESTS_ADDED= TEST_RESULT= KNOWN_GAPS= NEXT_STEP=\n"
        f".AI:END_CLAUDE_CODE_BUILD\n"
    )


def dispatch(*, title: str, mission: str, failure: str = "",
             files_to_inspect: list[str] | None = None,
             tests_to_run: list[str] | None = None,
             goal_id: str | None = None,
             ledger: str | Path = DIRECTIVES_LEDGER) -> dict[str, Any]:
    """Formulate + record a directive to the rolling ledger. Returns a receipt."""
    directive = formulate_directive(title=title, mission=mission, failure=failure,
                                    files_to_inspect=files_to_inspect, tests_to_run=tests_to_run)
    record = {
        "dispatch_id": f"dispatch_{_sha(directive)[:12]}",
        "created_at": _now(),
        "title": title,
        "goal_id": goal_id or "UNKNOWN",
        "directive_sha256": _sha(directive),
        "directive": directive,
        "status": "PENDING_AGENT",
    }
    p = Path(ledger)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"ok": True, "dispatch_id": record["dispatch_id"],
            "directive_sha256": record["directive_sha256"], "directive": directive,
            "ledger": str(p)}


def from_goal_block(goal: Any, *, ledger: str | Path = DIRECTIVES_LEDGER) -> dict[str, Any]:
    """Convenience: dispatch a directive for a goal that is blocked/failed."""
    purpose = getattr(goal, "purpose", "UNKNOWN")
    blocked = getattr(goal, "blocked_by", "UNKNOWN")
    last = getattr(goal, "last_progress", "UNKNOWN")
    return dispatch(
        title=f"unblock {purpose}",
        mission=f"Advance the goal: {purpose}. It is currently blocked/failed.",
        failure=f"blocked_by={blocked}; last_progress={last}",
        goal_id=getattr(goal, "goal_id", None),
        ledger=ledger,
    )


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in (text or "task")).strip("_").upper()[:48] or "TASK"
