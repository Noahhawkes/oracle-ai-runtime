"""
core/window_janitor.py — ORACLE Window Janitor

Doctrine:
  If ORACLE opens it, ORACLE is responsible for cleaning it.
  If Noah opened it, ORACLE must not assume ownership.
  Visibility is not ownership.

Core safety:
  dry_run=True by default — nothing closes without explicit approval.
  Unknown ownership = skip and preserve.
  Prefer minimize over close when uncertain.
  Protected windows are NEVER closed.

Persistence:
  Memory/window_janitor_records.json

Usage:
  python core/window_janitor.py --smoke
"""

import json
import os
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

RECORDS_FILE = ROOT / "Memory" / "window_janitor_records.json"

# ── Status values ──────────────────────────────────────────────────────────────
STATUS_OBSERVED          = "observed"
STATUS_CLAIMED           = "claimed"
STATUS_PROTECTED         = "protected"
STATUS_CLEANUP_PENDING   = "cleanup_pending"
STATUS_CLOSED            = "closed"
STATUS_SKIPPED           = "skipped"
STATUS_FAILED            = "failed"
STATUS_APPROVAL_REQUIRED = "approval_required"

# ── Windows ORACLE must NEVER close ───────────────────────────────────────────
PROTECTED_TITLE_FRAGMENTS = [
    "oracle", "claude", "claude code", "codex", "openai codex",
    "powershell", "cmd", "command prompt",  # only protected if they're ORACLE's shells
    "1password", "bitwarden", "keepass",     # password managers
    "banking", "chase", "wells fargo", "paypal",  # financial
]
PROTECTED_PROCESS_NAMES = {
    "1password.exe", "bitwarden.exe", "keepass.exe",
}
# Titles that are always protected regardless of oracle ownership
ALWAYS_PROTECTED_FRAGMENTS = [
    "1password", "bitwarden", "keepass", "chase", "paypal", "bank",
]

# ── Process names ORACLE may open (can be safely claimed) ─────────────────────
ORACLE_OPENABLE_PROCESSES = {
    "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe",
    "notepad.exe", "notepad++.exe", "cmd.exe", "powershell.exe",
    "python.exe", "pythonw.exe",
}


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class WindowRecord:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    task_id: str = ""
    window_title: str = ""
    process_name: str = ""
    pid: int = 0
    handle: int = 0
    opened_by_oracle: bool = False
    touched_by_oracle: bool = False
    safe_to_close: bool = False
    requires_approval_to_close: bool = True
    reason: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = STATUS_OBSERVED
    unknowns: list = field(default_factory=list)

    def touch(self):
        self.updated_at = datetime.now(timezone.utc).isoformat()


@dataclass
class CleanupReport:
    task_id: str
    dry_run: bool
    closed: list = field(default_factory=list)
    minimized: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    approval_required: list = field(default_factory=list)
    protected: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "",
            f"  [WINDOW JANITOR CLEANUP{'  DRY RUN' if self.dry_run else ''}]",
            f"  Task       : {self.task_id}",
            f"  Closed     : {len(self.closed)}",
            f"  Minimized  : {len(self.minimized)}",
            f"  Skipped    : {len(self.skipped)}",
            f"  Need Approval: {len(self.approval_required)}",
            f"  Protected  : {len(self.protected)}",
        ]
        for t in self.closed:
            lines.append(f"    [CLOSED]    {t}")
        for t in self.minimized:
            lines.append(f"    [MINIMIZED] {t}")
        for t in self.skipped:
            lines.append(f"    [SKIPPED]   {t}")
        for t in self.approval_required:
            lines.append(f"    [APPROVAL]  {t}")
        for t in self.protected:
            lines.append(f"    [PROTECTED] {t}")
        if self.errors:
            for e in self.errors:
                lines.append(f"    [ERROR]     {e}")
        if self.dry_run:
            lines.append("")
            lines.append("  DRY RUN — no windows were actually closed.")
            lines.append("  Run cleanup_task_windows(task_id, dry_run=False) after Noah approves.")
        lines.append("")
        return "\n".join(lines)


# ── Window Janitor ─────────────────────────────────────────────────────────────

class WindowJanitor:
    """
    Tracks task-owned windows and restores the desktop cleanly.

    Usage:
        wj = WindowJanitor()
        snap = wj.snapshot_windows()           # before task starts
        wj.register_task_window(task_id, ...)  # as ORACLE opens windows
        report = wj.cleanup_task_windows(task_id, dry_run=True)
        print(report.summary())
    """

    def __init__(self):
        self._records: dict[str, WindowRecord] = {}  # id -> record
        self._snapshots: dict[str, list] = {}        # task_id -> list of handles at task start
        self.load_records()

    # ── Snapshot ──────────────────────────────────────────────────────────────

    def snapshot_windows(self) -> list[dict]:
        """Capture current visible windows. Returns list of window dicts."""
        windows = []
        try:
            import pygetwindow as gw
            for w in gw.getAllWindows():
                if not w.title.strip():
                    continue
                windows.append({
                    "title": w.title,
                    "handle": getattr(w, "_hWnd", 0),
                    "visible": True,
                })
        except ImportError:
            pass
        except Exception:
            pass
        return windows

    def snapshot_task_start(self, task_id: str):
        """Record window state at task start — used to detect new windows later."""
        snap = self.snapshot_windows()
        self._snapshots[task_id] = [w.get("handle", 0) for w in snap]

    # ── Registration ─────────────────────────────────────────────────────────

    def register_task_window(
        self,
        task_id: str,
        window_title: str = "",
        process_name: str = "",
        pid: int = 0,
        handle: int = 0,
        reason: str = "oracle_opened",
    ) -> WindowRecord:
        """Register a window that ORACLE opened — it becomes ORACLE's responsibility."""
        rec = WindowRecord(
            task_id=task_id,
            window_title=window_title,
            process_name=process_name.lower(),
            pid=pid,
            handle=handle,
            opened_by_oracle=True,
            touched_by_oracle=True,
            reason=reason,
            status=STATUS_CLAIMED,
        )
        rec = self.classify_window(rec)
        self._records[rec.id] = rec
        self.save_records()
        return rec

    def mark_touched(
        self,
        task_id: str,
        window_title: str = "",
        handle: int = 0,
        reason: str = "oracle_interacted",
    ) -> Optional[WindowRecord]:
        """Mark an existing window as touched by ORACLE (but not necessarily opened by it)."""
        rec = self._find_by_handle_or_title(handle, window_title)
        if not rec:
            # Create an observed record
            rec = WindowRecord(
                task_id=task_id,
                window_title=window_title,
                handle=handle,
                opened_by_oracle=False,
                touched_by_oracle=True,
                reason=reason,
                status=STATUS_OBSERVED,
            )
            rec = self.classify_window(rec)
            self._records[rec.id] = rec
        else:
            rec.touched_by_oracle = True
            rec.reason = reason
            rec.touch()
        self.save_records()
        return rec

    # ── Classification ────────────────────────────────────────────────────────

    def classify_window(self, rec: WindowRecord) -> WindowRecord:
        """
        Determine whether a window is safe to close, needs approval, or is protected.
        """
        title_lower = rec.window_title.lower()
        proc_lower = rec.process_name.lower()

        # Always protected — never close regardless
        for frag in ALWAYS_PROTECTED_FRAGMENTS:
            if frag in title_lower:
                rec.safe_to_close = False
                rec.requires_approval_to_close = False  # not even ask — just never
                rec.status = STATUS_PROTECTED
                rec.reason = f"Always-protected: contains '{frag}'"
                return rec

        if proc_lower in PROTECTED_PROCESS_NAMES:
            rec.safe_to_close = False
            rec.requires_approval_to_close = False
            rec.status = STATUS_PROTECTED
            rec.reason = f"Protected process: {proc_lower}"
            return rec

        # ORACLE's own terminal — never close
        if any(f in title_lower for f in ("oracle", "claude code", "codex")):
            rec.safe_to_close = False
            rec.requires_approval_to_close = False
            rec.status = STATUS_PROTECTED
            rec.reason = "ORACLE/Claude Code terminal — never close"
            return rec

        # If ORACLE opened it and it's a known safe process
        if rec.opened_by_oracle and proc_lower in ORACLE_OPENABLE_PROCESSES:
            # Still check for unsaved-work indicators in title
            unsaved_indicators = ["unsaved", "modified", "•", "*", "—", "untitled"]
            if any(ind in title_lower for ind in unsaved_indicators):
                rec.safe_to_close = False
                rec.requires_approval_to_close = True
                rec.status = STATUS_APPROVAL_REQUIRED
                rec.reason = "Possible unsaved work detected in title"
                return rec
            rec.safe_to_close = True
            rec.requires_approval_to_close = False
            rec.status = STATUS_CLEANUP_PENDING
            rec.reason = "ORACLE opened this window; safe process; no unsaved-work indicator"
            return rec

        # If ORACLE opened it but process is unknown
        if rec.opened_by_oracle:
            rec.safe_to_close = False
            rec.requires_approval_to_close = True
            rec.status = STATUS_APPROVAL_REQUIRED
            rec.reason = "ORACLE opened but process is not in safe-to-close list"
            rec.unknowns.append(f"process '{proc_lower}' not in ORACLE_OPENABLE_PROCESSES")
            return rec

        # ORACLE touched but didn't open — do not close
        if rec.touched_by_oracle and not rec.opened_by_oracle:
            rec.safe_to_close = False
            rec.requires_approval_to_close = True
            rec.status = STATUS_APPROVAL_REQUIRED
            rec.reason = "ORACLE touched this window but did not open it — ownership ambiguous"
            return rec

        # Unknown ownership — skip
        rec.safe_to_close = False
        rec.requires_approval_to_close = False
        rec.status = STATUS_SKIPPED
        rec.reason = "Unknown ownership — preserved"
        rec.unknowns.append("window ownership not established")
        return rec

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def cleanup_task_windows(self, task_id: str, dry_run: bool = True) -> CleanupReport:
        """
        Propose or execute cleanup for all windows registered to task_id.
        dry_run=True (default) — proposes only, nothing closed.
        """
        report = CleanupReport(task_id=task_id, dry_run=dry_run)
        task_records = [r for r in self._records.values() if r.task_id == task_id]

        for rec in task_records:
            if rec.status == STATUS_PROTECTED:
                report.protected.append(rec.window_title or f"(handle:{rec.handle})")
                continue

            if rec.status == STATUS_APPROVAL_REQUIRED or rec.requires_approval_to_close:
                report.approval_required.append(
                    f"{rec.window_title or '?'} — {rec.reason}"
                )
                continue

            if rec.status == STATUS_CLEANUP_PENDING and rec.safe_to_close:
                result = self.close_window_safe(rec, dry_run=dry_run)
                if result:
                    report.closed.append(rec.window_title or f"(handle:{rec.handle})")
                    if not dry_run:
                        rec.status = STATUS_CLOSED
                        rec.touch()
                else:
                    report.errors.append(f"Could not close: {rec.window_title}")
                    report.skipped.append(rec.window_title or "?")
                continue

            # Skip everything else
            report.skipped.append(
                f"{rec.window_title or '?'} [{rec.status}]"
            )

        if not dry_run:
            self.save_records()
        return report

    def close_window_safe(self, rec: WindowRecord, dry_run: bool = True) -> bool:
        """
        Close a single window safely. Returns True if closed (or dry-run success).
        """
        if dry_run:
            return True  # dry-run always succeeds in simulation

        if rec.status == STATUS_PROTECTED:
            return False

        try:
            if rec.handle:
                import ctypes
                WM_CLOSE = 0x0010
                ctypes.windll.user32.PostMessageW(rec.handle, WM_CLOSE, 0, 0)
                return True
        except Exception:
            pass

        # Fallback: pygetwindow
        try:
            import pygetwindow as gw
            wins = gw.getWindowsWithTitle(rec.window_title)
            if wins:
                wins[0].close()
                return True
        except Exception:
            pass

        return False

    def minimize_window_safe(self, rec: WindowRecord, dry_run: bool = True) -> bool:
        """Minimize instead of close when ownership is uncertain."""
        if dry_run:
            return True

        if rec.status == STATUS_PROTECTED:
            return False

        try:
            if rec.handle:
                import ctypes
                SW_MINIMIZE = 6
                ctypes.windll.user32.ShowWindow(rec.handle, SW_MINIMIZE)
                return True
        except Exception:
            pass

        try:
            import pygetwindow as gw
            wins = gw.getWindowsWithTitle(rec.window_title)
            if wins:
                wins[0].minimize()
                return True
        except Exception:
            pass

        return False

    def restore_desktop(self, task_id: str, dry_run: bool = True) -> CleanupReport:
        """
        Full desktop restore: cleanup task windows and minimize leftover unknowns.
        Use after ORACLE completes or abandons a task.
        """
        return self.cleanup_task_windows(task_id, dry_run=dry_run)

    # ── Persistence ───────────────────────────────────────────────────────────

    def save_records(self):
        RECORDS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {k: asdict(v) for k, v in self._records.items()}
        RECORDS_FILE.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def load_records(self):
        if not RECORDS_FILE.exists():
            return
        try:
            raw = json.loads(RECORDS_FILE.read_text(encoding="utf-8"))
            for rec_id, rec_data in raw.items():
                try:
                    rec = WindowRecord(**{k: v for k, v in rec_data.items()
                                         if k in WindowRecord.__dataclass_fields__})
                    self._records[rec_id] = rec
                except Exception:
                    pass
        except Exception:
            pass

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _find_by_handle_or_title(
        self, handle: int, title: str
    ) -> Optional[WindowRecord]:
        for rec in self._records.values():
            if handle and rec.handle == handle:
                return rec
            if title and rec.window_title == title:
                return rec
        return None

    def get_task_records(self, task_id: str) -> list[WindowRecord]:
        return [r for r in self._records.values() if r.task_id == task_id]

    def clear_task_records(self, task_id: str):
        self._records = {k: v for k, v in self._records.items() if v.task_id != task_id}
        self.save_records()


# ── Module-level singleton ─────────────────────────────────────────────────────

_janitor: Optional[WindowJanitor] = None


def get_janitor() -> WindowJanitor:
    global _janitor
    if _janitor is None:
        _janitor = WindowJanitor()
    return _janitor


# ── Smoke test ────────────────────────────────────────────────────────────────

def _smoke_test() -> bool:
    print("=" * 60)
    print("window_janitor.py — Smoke Test (no real windows closed)")
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

    wj = WindowJanitor()
    task_id = "smoke_test_task_001"

    # 1. Register a Chrome window ORACLE opened
    chrome_rec = wj.register_task_window(
        task_id=task_id,
        window_title="ChatGPT - Google Chrome",
        process_name="chrome.exe",
        pid=1234,
        handle=9999,
        reason="oracle_navigated_chrome",
    )
    check("Chrome window registered as ORACLE-owned", chrome_rec.opened_by_oracle)
    check("Chrome window is safe to close", chrome_rec.safe_to_close)
    check("Chrome window status is cleanup_pending", chrome_rec.status == STATUS_CLEANUP_PENDING)

    # 2. Register a Notepad ORACLE opened — with unsaved indicator
    notepad_rec = wj.register_task_window(
        task_id=task_id,
        window_title="*Untitled - Notepad",
        process_name="notepad.exe",
        pid=5678,
        handle=8888,
        reason="oracle_opened_for_editing",
    )
    check("Notepad with unsaved indicator requires approval",
          notepad_rec.status == STATUS_APPROVAL_REQUIRED,
          f"got status={notepad_rec.status}")
    check("Unsaved notepad is NOT safe to close", not notepad_rec.safe_to_close)

    # 3. ORACLE main terminal is protected
    oracle_rec = wj.register_task_window(
        task_id=task_id,
        window_title="ORACLE.AI — PowerShell",
        process_name="powershell.exe",
        pid=1111,
        handle=7777,
        reason="test_protection",
    )
    check("ORACLE terminal is protected", oracle_rec.status == STATUS_PROTECTED)
    check("ORACLE terminal cannot be closed", not oracle_rec.safe_to_close)

    # 4. 1Password is always protected
    pw_rec = wj.register_task_window(
        task_id=task_id,
        window_title="1Password",
        process_name="1password.exe",
        pid=2222,
        handle=6666,
        reason="test_protection",
    )
    check("1Password is always protected", pw_rec.status == STATUS_PROTECTED)

    # 5. Unknown window is skipped
    unknown_rec = wj.register_task_window(
        task_id=task_id,
        window_title="Some Random App",
        process_name="unknownapp.exe",
        pid=3333,
        handle=5555,
        reason="test_unknown",
    )
    # opened_by_oracle=True but not in ORACLE_OPENABLE_PROCESSES
    check("Unknown process requires approval",
          unknown_rec.status == STATUS_APPROVAL_REQUIRED,
          f"got status={unknown_rec.status}")

    # 6. Window ORACLE touched but didn't open
    touched_rec = wj.mark_touched(
        task_id=task_id,
        window_title="Noah's VS Code Project",
        handle=4444,
        reason="oracle_read_file",
    )
    check("Touched-not-opened window requires approval",
          touched_rec is not None and touched_rec.status == STATUS_APPROVAL_REQUIRED)

    # 7. Dry-run cleanup proposes correctly
    report = wj.cleanup_task_windows(task_id, dry_run=True)
    check("Dry run report created", report is not None)
    check("Chrome proposed for close in dry run", len(report.closed) >= 1)
    check("Protected windows not in closed list",
          all("oracle" not in t.lower() for t in report.closed))
    check("Approval items present", len(report.approval_required) >= 1)
    check("Dry run report says no real close happened", report.dry_run)

    # 8. Summary builds without crash
    try:
        summary = report.summary()
        check("CleanupReport.summary() builds without crash", True)
        check("Summary mentions DRY RUN", "DRY RUN" in summary)
    except Exception as e:
        check("CleanupReport.summary() builds without crash", False, str(e))
        check("Summary mentions DRY RUN", False)

    # 9. Persistence
    wj.save_records()
    check("Records file written", RECORDS_FILE.exists())
    wj2 = WindowJanitor()
    loaded = wj2.get_task_records(task_id)
    check("Records loaded back from disk", len(loaded) > 0)

    # 10. classify_window on a bank window
    bank_rec = WindowRecord(
        task_id=task_id,
        window_title="Chase Bank - Secure Sign In",
        process_name="chrome.exe",
        opened_by_oracle=True,
    )
    classified = wj.classify_window(bank_rec)
    check("Bank window is always protected", classified.status == STATUS_PROTECTED)

    # Cleanup test records
    wj.clear_task_records(task_id)

    print(f"\n{passed}/{passed + failed} smoke tests passed.")
    if failed:
        print(f"FAILED: {failed} test(s).")
    else:
        print("All smoke tests passed.")
    return failed == 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if "--smoke" in sys.argv or "smoke" in sys.argv:
        ok = _smoke_test()
        sys.exit(0 if ok else 1)
    else:
        print("window_janitor.py — run with --smoke to test")
        wj = get_janitor()
        snap = wj.snapshot_windows()
        print(f"Current windows visible: {len(snap)}")
        for w in snap[:10]:
            print(f"  {w.get('title', '?')[:60]}")
