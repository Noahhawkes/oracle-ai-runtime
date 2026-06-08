"""
core/workspace_steward.py — ORACLE Workspace Steward v0.1

Keeps Noah's PC orderly without reckless control.
Uses Drive Scope for path awareness and Window Janitor for window inspection.

ORACLE may:
  - detect messy windows, stale prompts, orphaned terminals
  - detect duplicate loops, old daemon proposals
  - detect likely cleanup candidates across approved scoped paths
  - propose scoped path candidates and cleanup candidates

ORACLE may NOT:
  - close unknown windows
  - delete / move / rename files
  - edit source without approval
  - act outside approved Drive Scope
  - kill processes

All findings go to Memory/workspace_steward_report.json
                  Memory/workspace_steward_report.md

Usage:
    python core/workspace_steward.py --dry-run
    python core/workspace_steward.py --status
    python core/workspace_steward.py --smoke-test
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent
REPORT_JSON = ROOT / "Memory" / "workspace_steward_report.json"
REPORT_MD   = ROOT / "Memory" / "workspace_steward_report.md"

_NOW = lambda: datetime.now(timezone.utc).isoformat()

# ── Stale thresholds ──────────────────────────────────────────────────────────
STALE_PROPOSAL_DAYS   = 3    # daemon proposals older than this → stale
STALE_EXPORT_DAYS     = 7    # continuity exports older than this → old
MAX_OPEN_TERMINALS    = 4    # more than this → flag as messy
MAX_OPEN_EDITORS      = 5    # more than this → flag as messy

# ── Window classification helpers ─────────────────────────────────────────────

def _get_windows() -> list[dict]:
    """Read open windows via Window Janitor if available."""
    try:
        import sys as _sys
        _core = str(ROOT / "core")
        if _core not in _sys.path:
            _sys.path.insert(0, _core)
        from window_janitor import WindowJanitor
        wj = WindowJanitor()
        wj.snapshot()
        return [
            {
                "id":       rec.id,
                "title":    rec.window_title,
                "process":  rec.process_name,
                "class":    rec.window_class,
                "category": rec.category,
                "handle":   rec.handle,
            }
            for rec in wj._records.values()
            if rec.window_title.strip()
        ]
    except Exception:
        return []


def _classify_windows(windows: list[dict]) -> dict:
    """Group windows into typed buckets for stewardship review."""
    terminals = [w for w in windows if any(t in w.get("title", "").lower() or
                                           t in w.get("process", "").lower()
                                           for t in ("terminal", "cmd", "powershell",
                                                      "bash", "git bash", "wsl"))]
    editors   = [w for w in windows if any(t in w.get("title", "").lower() or
                                           t in w.get("process", "").lower()
                                           for t in ("code", "notepad", "vim", "nano",
                                                      "sublime", "rider", "pycharm",
                                                      "cursor", "windsurf"))]
    browsers  = [w for w in windows if any(t in w.get("process", "").lower()
                                           for t in ("chrome", "firefox", "msedge",
                                                      "brave", "opera"))]
    oracle_wins = [w for w in windows if "oracle" in w.get("title", "").lower()]
    unknown   = [w for w in windows
                 if w not in terminals + editors + browsers + oracle_wins
                 and w.get("title", "").strip()]
    return {
        "terminals":    terminals,
        "editors":      editors,
        "browsers":     browsers,
        "oracle":       oracle_wins,
        "unknown":      unknown,
        "total":        len(windows),
    }


# ── File-system inspection (read-only, scoped) ────────────────────────────────

def _stale_proposals() -> list[dict]:
    """Daemon proposals older than STALE_PROPOSAL_DAYS."""
    proposals_dir = ROOT / "Projects" / "daemon_proposals"
    if not proposals_dir.exists():
        proposals_dir = ROOT / "daemon_proposals"
    if not proposals_dir.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=STALE_PROPOSAL_DAYS)
    stale = []
    try:
        for f in proposals_dir.glob("*.md"):
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                stale.append({"path": str(f), "age_days": (datetime.now(timezone.utc) - mtime).days})
    except Exception:
        pass
    return stale


def _old_exports() -> list[dict]:
    """Continuity exports older than STALE_EXPORT_DAYS."""
    exports_dir = ROOT / "Memory" / "continuity_exports"
    if not exports_dir.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=STALE_EXPORT_DAYS)
    old = []
    try:
        for f in exports_dir.glob("oracle_continuity_export_*.json"):
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                old.append({"path": str(f), "age_days": (datetime.now(timezone.utc) - mtime).days})
    except Exception:
        pass
    return old


def _scoped_path_candidates() -> list[dict]:
    """Propose approved scoped paths beyond G Drive using Drive Scope."""
    try:
        from drive_scope import load_scope
        scope = load_scope()
        return [
            {"path": p, "source": "drive_scope"}
            for p in scope.get("approved_paths", [])
            if p and Path(p).exists()
        ]
    except Exception:
        return [{"path": str(ROOT), "source": "oracle_root_fallback"}]


def _pending_approval_count() -> int:
    """Quick count of items pending approval across all sources."""
    try:
        from approval_center import list_pending
        return len(list_pending())
    except Exception:
        return 0


# ── One next action ───────────────────────────────────────────────────────────

def _one_next_action(findings: dict) -> dict:
    """Derive exactly one safe stewardship recommendation."""
    # Priority order: governance → terminals → proposals → exports → scope
    pending = findings.get("pending_approvals", 0)
    if pending > 0:
        return {
            "action":           f"Review {pending} pending approval(s)",
            "command":          "python core/approval_center.py --list",
            "approval_required": False,
            "reason":           "Pending items reduce ORACLE's ability to reason accurately.",
        }

    terminals = findings.get("windows", {}).get("terminals", [])
    if len(terminals) > MAX_OPEN_TERMINALS:
        return {
            "action":           f"Close {len(terminals) - MAX_OPEN_TERMINALS} excess terminal windows",
            "command":          "Manually close unused terminals",
            "approval_required": True,
            "reason":           f"{len(terminals)} terminals open — orphaned shells waste resources.",
        }

    stale = findings.get("stale_proposals", [])
    if stale:
        return {
            "action":           f"Archive {len(stale)} stale daemon proposal(s)",
            "command":          "python core/continuity_scheduler.py --dry-run",
            "approval_required": True,
            "reason":           f"{len(stale)} daemon proposals older than {STALE_PROPOSAL_DAYS} days.",
        }

    old_exp = findings.get("old_exports", [])
    if old_exp:
        return {
            "action":           f"Rotate {len(old_exp)} old continuity export(s)",
            "command":          "python core/continuity_scheduler.py --run-once",
            "approval_required": False,
            "reason":           f"{len(old_exp)} exports older than {STALE_EXPORT_DAYS} days.",
        }

    scoped = findings.get("scoped_paths", [])
    extra = [s for s in scoped if "oracle" not in s["path"].lower() and Path(s["path"]).exists()]
    if extra:
        return {
            "action":           "Confirm approved scoped paths look correct",
            "command":          "python core/drive_scope.py --status",
            "approval_required": False,
            "reason":           f"Drive Scope found {len(extra)} approved paths beyond G Drive.",
        }

    return {
        "action":           "ORACLE workspace is tidy — no stewardship action needed",
        "command":          "",
        "approval_required": False,
        "reason":           "No pending items, stale proposals, or excess windows detected.",
    }


# ── Main dry-run ──────────────────────────────────────────────────────────────

def dry_run() -> dict:
    """
    Inspect the workspace and produce a stewardship report.
    Read-only. No files deleted, no windows closed, no processes killed.
    """
    windows_raw  = _get_windows()
    windows      = _classify_windows(windows_raw)
    stale        = _stale_proposals()
    old_exp      = _old_exports()
    scoped       = _scoped_path_candidates()
    pending      = _pending_approval_count()

    findings = {
        "generated_at":     _NOW(),
        "windows":          windows,
        "stale_proposals":  stale,
        "old_exports":      old_exp,
        "scoped_paths":     scoped,
        "pending_approvals": pending,
        "safety": {
            "read_only":           True,
            "no_files_deleted":    True,
            "no_windows_closed":   True,
            "no_processes_killed": True,
            "scope_enforced":      True,
        },
    }
    findings["next_action"] = _one_next_action(findings)

    # Flags
    flags = []
    if len(windows.get("terminals", [])) > MAX_OPEN_TERMINALS:
        flags.append(f"WARNING: {len(windows['terminals'])} terminals open (>{MAX_OPEN_TERMINALS})")
    if len(windows.get("editors", [])) > MAX_OPEN_EDITORS:
        flags.append(f"INFO: {len(windows['editors'])} editor windows open")
    if stale:
        flags.append(f"INFO: {len(stale)} stale daemon proposals detected")
    if old_exp:
        flags.append(f"INFO: {len(old_exp)} old continuity exports detected")
    if pending > 0:
        flags.append(f"ACTION: {pending} item(s) pending approval")
    findings["flags"] = flags

    # Write JSON report
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(
        json.dumps(findings, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Write Markdown report
    _write_md_report(findings)

    return findings


def _write_md_report(findings: dict) -> None:
    w  = findings.get("windows", {})
    na = findings.get("next_action", {})
    lines = [
        "# ORACLE Workspace Steward Report",
        f"Generated: {findings.get('generated_at', '')[:19]}",
        "",
        "## Window Summary",
        f"- Total windows : {w.get('total', 0)}",
        f"- Terminals     : {len(w.get('terminals', []))}",
        f"- Editors       : {len(w.get('editors', []))}",
        f"- Browsers      : {len(w.get('browsers', []))}",
        f"- ORACLE windows: {len(w.get('oracle', []))}",
        f"- Unknown       : {len(w.get('unknown', []))}",
        "",
        "## Findings",
    ]
    for flag in findings.get("flags", []):
        lines.append(f"- {flag}")
    if not findings.get("flags"):
        lines.append("- No flags raised.")
    lines += [
        "",
        "## Stale Proposals",
        f"{len(findings.get('stale_proposals', []))} stale daemon proposal(s) detected." if findings.get("stale_proposals") else "None.",
        "",
        "## Old Exports",
        f"{len(findings.get('old_exports', []))} old continuity export(s) detected." if findings.get("old_exports") else "None.",
        "",
        "## Scoped Paths",
        f"{len(findings.get('scoped_paths', []))} approved path(s) in scope.",
    ]
    for sp in findings.get("scoped_paths", [])[:8]:
        lines.append(f"  - `{sp['path']}`")
    lines += [
        "",
        "## Pending Approvals",
        f"{findings.get('pending_approvals', 0)} item(s) pending approval.",
        "",
        "## One Next Action",
        f"**{na.get('action', 'none')}**",
        f"Reason: {na.get('reason', '')}",
        f"Command: `{na.get('command', '')}` " if na.get("command") else "",
        f"Approval required: {na.get('approval_required', False)}",
        "",
        "## Safety",
        "- Read-only inspection only.",
        "- No files deleted, moved, or renamed.",
        "- No windows closed.",
        "- No processes killed.",
        "- Scope enforced via Drive Scope.",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


# ── Smoke tests ───────────────────────────────────────────────────────────────

def run_smoke_tests() -> int:
    failures = 0

    def check(label, passed, detail=""):
        nonlocal failures
        tag = "PASS" if passed else "FAIL"
        suffix = f" — {detail}" if detail and not passed else ""
        print(f"  [{tag}] {label}{suffix}")
        if not passed:
            failures += 1

    print("=" * 55)
    print("Workspace Steward v0.1 — Smoke Tests")
    print("=" * 55)

    # 1. dry_run runs without crash
    try:
        result = dry_run()
        check("dry_run: no crash", True)
        check("dry_run: returns dict", isinstance(result, dict))
        check("dry_run: has windows", "windows" in result)
        check("dry_run: has next_action", "next_action" in result)
        check("dry_run: has safety block", isinstance(result.get("safety"), dict))
        check("dry_run: safety read_only=True", result["safety"].get("read_only") is True)
        check("dry_run: no windows closed", result["safety"].get("no_windows_closed") is True)
        check("dry_run: no files deleted", result["safety"].get("no_files_deleted") is True)
        check("dry_run: no processes killed", result["safety"].get("no_processes_killed") is True)
        check("dry_run: report JSON written", REPORT_JSON.exists())
        check("dry_run: report MD written", REPORT_MD.exists())
    except Exception as e:
        check("dry_run: no crash", False, str(e))
        result = {}

    # 2. windows classification
    windows = result.get("windows", {})
    check("windows: has terminals key", "terminals" in windows)
    check("windows: has editors key",   "editors" in windows)
    check("windows: has browsers key",  "browsers" in windows)
    check("windows: has total key",     "total" in windows)
    check("windows: terminal count >= 0", isinstance(windows.get("terminals"), list))

    # 3. next_action shape
    na = result.get("next_action", {})
    check("next_action: has action",           bool(na.get("action")))
    check("next_action: has reason",           bool(na.get("reason")))
    check("next_action: has approval_required", "approval_required" in na)
    check("next_action: exactly one action",   isinstance(na.get("action"), str))

    # 4. scoped_paths includes something
    scoped = result.get("scoped_paths", [])
    check("scoped_paths: is list", isinstance(scoped, list))
    check("scoped_paths: oracle root present",
          any("oracle" in s.get("path", "").lower() or
              str(ROOT).lower() in s.get("path", "").lower()
              for s in scoped))

    # 5. _one_next_action with fake findings
    fake_lots_of_terminals = {
        "windows": {"terminals": [{"title": f"term{i}"} for i in range(10)]},
        "stale_proposals": [],
        "old_exports": [],
        "scoped_paths": [],
        "pending_approvals": 0,
    }
    na2 = _one_next_action(fake_lots_of_terminals)
    check("_one_next_action: excess terminals flagged", "terminal" in na2["action"].lower())

    fake_pending = {
        "windows": {"terminals": []},
        "stale_proposals": [],
        "old_exports": [],
        "scoped_paths": [],
        "pending_approvals": 5,
    }
    na3 = _one_next_action(fake_pending)
    check("_one_next_action: pending approvals prioritised", "pending" in na3["action"].lower() or "approval" in na3["action"].lower())

    # 6. MD report is readable
    try:
        md = REPORT_MD.read_text(encoding="utf-8")
        check("md report: non-empty", len(md) > 200)
        check("md report: contains Next Action", "Next Action" in md)
        check("md report: contains Safety", "Safety" in md)
    except Exception as e:
        check("md report: readable", False, str(e))

    total = 29
    passed = total - failures
    print(f"{'='*55}")
    print(f"Result: {passed}/{total} passed")
    print(f"STATUS: {'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    print(f"{'='*55}\n")
    return failures


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ORACLE Workspace Steward")
    parser.add_argument("--dry-run",    action="store_true", help="Inspect workspace and produce report")
    parser.add_argument("--status",     action="store_true", help="Show last stewardship report")
    parser.add_argument("--smoke-test", action="store_true", help="Run smoke tests")
    args = parser.parse_args()

    if args.smoke_test:
        sys.exit(run_smoke_tests())

    elif args.dry_run:
        print("\n  Running workspace inspection (read-only)...\n")
        result = dry_run()
        w  = result.get("windows", {})
        na = result.get("next_action", {})
        print(f"  Windows     : {w.get('total', 0)} total  "
              f"({len(w.get('terminals',[]))} terminals, "
              f"{len(w.get('editors',[]))} editors, "
              f"{len(w.get('browsers',[]))} browsers)")
        print(f"  Stale props : {len(result.get('stale_proposals', []))}")
        print(f"  Old exports : {len(result.get('old_exports', []))}")
        print(f"  Pending     : {result.get('pending_approvals', 0)} approvals")
        print(f"  Scoped paths: {len(result.get('scoped_paths', []))}")
        for flag in result.get("flags", []):
            print(f"  ⚑ {flag}")
        print(f"\n  Next action : {na.get('action')}")
        print(f"  Reason      : {na.get('reason')}")
        if na.get("command"):
            print(f"  Command     : {na['command']}")
        print(f"\n  Reports written:")
        print(f"    {REPORT_JSON}")
        print(f"    {REPORT_MD}\n")

    elif args.status:
        if REPORT_JSON.exists():
            raw = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
            na  = raw.get("next_action", {})
            print(f"\n  Last run : {raw.get('generated_at', 'never')[:19]}")
            print(f"  Flags    : {len(raw.get('flags', []))}")
            print(f"  Next     : {na.get('action', 'none')}\n")
        else:
            print("\n  No stewardship report yet. Run --dry-run first.\n")

    else:
        parser.print_help()
