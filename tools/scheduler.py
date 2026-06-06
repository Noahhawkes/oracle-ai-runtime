"""
ORACLE.AI — Scheduler (Phase 2)
Background agent mode — run ORACLE tasks on timers, triggers, or schedules.
Gives ORACLE the ability to operate autonomously without Noah typing.
"""

import sys
import os
import json
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Callable, Optional

ROOT = Path(__file__).parent.parent
SCHEDULE_FILE = ROOT / "Memory" / "scheduled_tasks.json"


class Task:
    def __init__(
        self,
        name: str,
        action: Callable,
        interval_minutes: int = None,
        run_at: str = None,       # "HH:MM" for daily time
        run_once: bool = False,
        args: list = None,
        kwargs: dict = None
    ):
        self.name = name
        self.action = action
        self.interval_minutes = interval_minutes
        self.run_at = run_at
        self.run_once = run_once
        self.args = args or []
        self.kwargs = kwargs or {}
        self.last_run: Optional[datetime] = None
        self.next_run: datetime = self._calc_next_run()
        self.run_count = 0
        self.active = True

    def _calc_next_run(self) -> datetime:
        now = datetime.now()
        if self.run_at:
            h, m = map(int, self.run_at.split(":"))
            target = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            return target
        elif self.interval_minutes:
            return now + timedelta(minutes=self.interval_minutes)
        return now

    def is_due(self) -> bool:
        return self.active and datetime.now() >= self.next_run

    def execute(self) -> str:
        try:
            result = self.action(*self.args, **self.kwargs)
            self.last_run = datetime.now()
            self.run_count += 1
            if self.run_once:
                self.active = False
            else:
                self.next_run = self._calc_next_run()
            return str(result) if result else "OK"
        except Exception as e:
            return f"ERROR: {e}"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "interval_minutes": self.interval_minutes,
            "run_at": self.run_at,
            "run_once": self.run_once,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat(),
            "run_count": self.run_count,
            "active": self.active
        }


class Scheduler:
    def __init__(self):
        self.tasks: list[Task] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def add_task(self, task: Task) -> str:
        with self._lock:
            self.tasks.append(task)
        return f"Task scheduled: {task.name} (next run: {task.next_run.strftime('%Y-%m-%d %H:%M')})"

    def remove_task(self, name: str) -> str:
        with self._lock:
            before = len(self.tasks)
            self.tasks = [t for t in self.tasks if t.name != name]
        removed = before - len(self.tasks)
        return f"Removed {removed} task(s) named '{name}'"

    def start(self, background: bool = True) -> str:
        if self._running:
            return "Scheduler already running."
        self._running = True

        if background:
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
            return f"Scheduler started (background). {len(self.tasks)} task(s) loaded."
        else:
            self._loop()
            return "Scheduler finished."

    def stop(self) -> str:
        self._running = False
        return "Scheduler stopped."

    def _loop(self):
        while self._running:
            with self._lock:
                due_tasks = [t for t in self.tasks if t.is_due()]

            for task in due_tasks:
                self._run_task(task)

            # Clean up completed one-time tasks
            with self._lock:
                self.tasks = [t for t in self.tasks if t.active]

            time.sleep(30)  # Check every 30 seconds

    def _run_task(self, task: Task):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[ORACLE Scheduler] Running: {task.name} @ {timestamp}")
        result = task.execute()
        print(f"[ORACLE Scheduler] {task.name} result: {result[:200]}")
        self._log_task(task.name, result)

    def _log_task(self, name: str, result: str):
        log_file = ROOT / "Logs" / "scheduler.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {name}: {result[:500]}\n")

    def status(self) -> str:
        lines = [
            f"Scheduler: {'RUNNING' if self._running else 'STOPPED'}",
            f"Tasks: {len(self.tasks)}",
            ""
        ]
        for task in self.tasks:
            status = "ACTIVE" if task.active else "DONE"
            next_r = task.next_run.strftime("%H:%M") if task.next_run else "N/A"
            lines.append(f"  [{status}] {task.name} — next: {next_r} — runs: {task.run_count}")
        return "\n".join(lines)

    def save_schedule(self) -> str:
        SCHEDULE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = [t.to_dict() for t in self.tasks]
        with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return f"Schedule saved: {SCHEDULE_FILE}"


# ── Global scheduler instance ─────────────────────────────────────────────────
_scheduler: Optional[Scheduler] = None


def get_scheduler() -> Scheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler()
    return _scheduler


# ── Pre-built ORACLE autonomous tasks ─────────────────────────────────────────

def task_filesystem_scan():
    """Scheduled filesystem scan — keeps ORACLE's map current."""
    sys.path.insert(0, str(ROOT / "tools"))
    from filesystem_mapper import run_full_scan
    return run_full_scan()


def task_memory_backup():
    """Backup ORACLE's memory database."""
    import shutil
    from datetime import datetime
    db = ROOT / "Memory" / "oracle_memory.db"
    if db.exists():
        backup = ROOT / "Memory" / f"oracle_memory_backup_{datetime.now().strftime('%Y%m%d')}.db"
        shutil.copy2(db, backup)
        return f"Memory backed up: {backup}"
    return "No memory DB found."


def task_git_commit():
    """Auto-commit ORACLE project changes."""
    sys.path.insert(0, str(ROOT / "tools"))
    from shell_agent import run_powershell
    r = run_powershell('git add -A && git commit -m "Auto-commit by ORACLE Scheduler"', cwd=str(ROOT))
    return r["stdout"] or r["stderr"]


def task_log_summary():
    """Write a daily activity summary to logs."""
    log_file = ROOT / "Logs" / "daily_summary.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    summary = f"[{datetime.now().strftime('%Y-%m-%d')}] ORACLE daily check-in. System operational.\n"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(summary)
    return "Daily summary logged."


# ── Convenience launchers ─────────────────────────────────────────────────────

def start_autonomous_mode() -> str:
    """
    Start ORACLE's full autonomous background mode.
    Schedules all core maintenance tasks and begins running.
    """
    s = get_scheduler()

    # Filesystem scan every 6 hours
    s.add_task(Task(
        name="filesystem_scan",
        action=task_filesystem_scan,
        interval_minutes=360
    ))

    # Memory backup daily at 3 AM
    s.add_task(Task(
        name="memory_backup",
        action=task_memory_backup,
        run_at="03:00"
    ))

    # Auto-commit every hour
    s.add_task(Task(
        name="git_auto_commit",
        action=task_git_commit,
        interval_minutes=60
    ))

    # Daily log at 9 AM
    s.add_task(Task(
        name="daily_log",
        action=task_log_summary,
        run_at="09:00"
    ))

    result = s.start(background=True)
    return f"ORACLE Autonomous Mode: ONLINE\n{result}\n\n{s.status()}"


def scheduler_status() -> str:
    return get_scheduler().status()


def stop_autonomous_mode() -> str:
    return get_scheduler().stop()


def add_custom_task(name: str, command: str, interval_minutes: int = 60) -> str:
    """Add a custom shell command as a scheduled task."""
    sys.path.insert(0, str(ROOT / "tools"))
    from shell_agent import run_powershell

    def run_cmd():
        r = run_powershell(command)
        return r["stdout"] or r["stderr"]

    s = get_scheduler()
    task = Task(name=name, action=run_cmd, interval_minutes=interval_minutes)
    return s.add_task(task)
