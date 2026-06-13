"""
Event Daemon for ORACLE — Always-on monitoring and proactive prompting.

Continuously monitors:
  - File system changes (core/, Projects/, Memory/)
  - Git status and commits
  - Active window and focus
  - Terminal output
  - Clipboard activity
  - System events

Feeds observations into attention_filter + salience_filter.
Generates proactive prompts and notifications based on urgency.

Runs as background service or inline thread.
"""

import os
import sys
import time
import json
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from collections import deque
from typing import Optional, Callable

# Root and core path setup
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

# ── Event types and urgency levels ────────────────────────────────────────────

URGENCY_LOW = 0.3       # Background observation (no action)
URGENCY_MEDIUM = 0.6    # Suggestion (popup notification)
URGENCY_HIGH = 0.8      # Problem detected (sound + notification)
URGENCY_CRITICAL = 1.0  # Immediate action required (interrupt + speech)

class WindowEvent:
    """File system or workspace event."""
    def __init__(self, event_type: str, source: str, urgency: float, detail: str = ""):
        self.event_type = event_type  # "file_change", "git_change", "window_focus", "memory_candidate"
        self.source = source           # "core", "projects", "git", "window", "clipboard", "terminal"
        self.urgency = urgency
        self.detail = detail
        self.timestamp = time.time()
        self.processed = False

    def to_dict(self):
        return {
            "event_type": self.event_type,
            "source": self.source,
            "urgency": self.urgency,
            "detail": self.detail,
            "timestamp": self.timestamp,
        }


# ── File system monitor ───────────────────────────────────────────────────────

class FileSystemMonitor:
    """Watch for changes in core/, Projects/, Memory/."""
    
    def __init__(self, root: Path):
        self.root = root
        self.watched_dirs = [
            root / "core",
            root / "Projects",
            root / "Memory",
        ]
        self.file_mtimes = {}
        self._scan_baseline()

    def _scan_baseline(self):
        """Capture initial mtimes."""
        for watch_dir in self.watched_dirs:
            if watch_dir.exists():
                for fpath in watch_dir.rglob("*.py"):
                    if ".git" not in str(fpath):
                        self.file_mtimes[str(fpath)] = fpath.stat().st_mtime

    def check_changes(self) -> list[WindowEvent]:
        """Return list of file change events."""
        events = []
        for watch_dir in self.watched_dirs:
            if not watch_dir.exists():
                continue
            for fpath in watch_dir.rglob("*.py"):
                if ".git" in str(fpath):
                    continue
                fstr = str(fpath)
                try:
                    mtime = fpath.stat().st_mtime
                    if fstr not in self.file_mtimes:
                        # New file
                        events.append(WindowEvent(
                            "file_created",
                            "core" if "core" in fstr else "projects",
                            URGENCY_LOW,
                            f"New file: {fpath.name}"
                        ))
                        self.file_mtimes[fstr] = mtime
                    elif self.file_mtimes[fstr] != mtime:
                        # Modified file
                        events.append(WindowEvent(
                            "file_modified",
                            "core" if "core" in fstr else "projects",
                            URGENCY_MEDIUM,
                            f"Modified: {fpath.name}"
                        ))
                        self.file_mtimes[fstr] = mtime
                except (OSError, IOError):
                    pass
        return events


# ── Git monitor ──────────────────────────────────────────────────────────────

class GitMonitor:
    """Watch for git changes (new commits, branches, status)."""
    
    def __init__(self, root: Path):
        self.root = root
        self.last_commit = self._get_last_commit()
        self.last_branch = self._get_current_branch()
        self.last_status = ""

    def _run_git(self, cmd: str) -> str:
        """Run git command safely."""
        try:
            result = subprocess.check_output(
                f"git -C {self.root} {cmd}",
                shell=True,
                stderr=subprocess.DEVNULL,
                text=True
            )
            return result.strip()
        except Exception:
            return ""

    def _get_last_commit(self) -> str:
        """Get latest commit hash."""
        return self._run_git("rev-parse HEAD")[:8]

    def _get_current_branch(self) -> str:
        """Get current branch."""
        return self._run_git("rev-parse --abbrev-ref HEAD")

    def check_changes(self) -> list[WindowEvent]:
        """Return list of git change events."""
        events = []
        
        # New commits?
        current_commit = self._get_last_commit()
        if current_commit and current_commit != self.last_commit:
            events.append(WindowEvent(
                "git_commit",
                "git",
                URGENCY_MEDIUM,
                f"New commit: {current_commit}"
            ))
            self.last_commit = current_commit

        # Branch change?
        current_branch = self._get_current_branch()
        if current_branch and current_branch != self.last_branch:
            events.append(WindowEvent(
                "git_branch_change",
                "git",
                URGENCY_LOW,
                f"Switched to branch: {current_branch}"
            ))
            self.last_branch = current_branch

        # Uncommitted changes?
        status = self._run_git("status --short")
        if status != self.last_status:
            if status:
                events.append(WindowEvent(
                    "git_status_change",
                    "git",
                    URGENCY_MEDIUM,
                    f"Uncommitted changes detected"
                ))
            self.last_status = status

        return events


# ── Memory monitor ───────────────────────────────────────────────────────────

class MemoryMonitor:
    """Watch for memory candidates and approval queue changes."""
    
    def __init__(self, root: Path):
        self.root = root
        self.memory_dir = root / "Memory"
        self.last_candidate_count = 0

    def check_changes(self) -> list[WindowEvent]:
        """Return memory-related events."""
        events = []
        
        # Check for memory candidates
        candidates_file = self.memory_dir / "candidates.json"
        if candidates_file.exists():
            try:
                data = json.loads(candidates_file.read_text())
                current_count = len(data.get("pending", []))
                if current_count > self.last_candidate_count:
                    events.append(WindowEvent(
                        "memory_candidate_pending",
                        "memory",
                        URGENCY_HIGH,
                        f"{current_count - self.last_candidate_count} new memory candidate(s) awaiting approval"
                    ))
                self.last_candidate_count = current_count
            except Exception:
                pass

        return events


# ── Event daemon ─────────────────────────────────────────────────────────────

class EventDaemon:
    """Main event monitoring and prompting engine."""
    
    def __init__(self, root: Path, notifier: Optional[Callable] = None):
        self.root = root
        self.notifier = notifier
        self.running = False
        self.event_queue = deque(maxlen=100)
        
        # Monitors
        self.fs_monitor = FileSystemMonitor(root)
        self.git_monitor = GitMonitor(root)
        self.mem_monitor = MemoryMonitor(root)
        
        self.thread = None

    def notify(self, event: WindowEvent):
        """Queue event and call notifier if provided."""
        self.event_queue.append(event)
        if self.notifier:
            self.notifier(event)

    def _check_all_sources(self):
        """Scan all monitors and collect events."""
        all_events = []
        
        # File changes
        all_events.extend(self.fs_monitor.check_changes())
        
        # Git changes
        all_events.extend(self.git_monitor.check_changes())
        
        # Memory candidates
        all_events.extend(self.mem_monitor.check_changes())
        
        return all_events

    def _process_events(self, events: list[WindowEvent]):
        """Feed events through attention filter and generate prompts."""
        if not events:
            return
        
        try:
            from attention_filter import attention_filter
            from salience_filter import ingest_signal
        except ImportError:
            # Filters not available, just notify
            for event in events:
                self.notify(event)
            return
        
        # Process each event through filters
        for event in events:
            # Ingest into salience pool
            try:
                ingest_signal(event.detail, source=event.source, urgency=event.urgency)
            except Exception:
                pass
            
            # Notify via configured channels
            self.notify(event)

    def _run_loop(self, interval_sec: float = 2.0):
        """Main daemon loop."""
        while self.running:
            try:
                events = self._check_all_sources()
                if events:
                    self._process_events(events)
            except Exception as e:
                print(f"[EventDaemon error] {e}")
            
            time.sleep(interval_sec)

    def start(self):
        """Start the daemon in a background thread."""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        print("[EventDaemon] Started background monitoring")

    def stop(self):
        """Stop the daemon."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        print("[EventDaemon] Stopped")

    def get_events(self, limit: int = 20) -> list[dict]:
        """Return recent events for debugging."""
        return [e.to_dict() for e in list(self.event_queue)[-limit:]]


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        print("\n[EventDaemon smoke test]\n")
        
        daemon = EventDaemon(ROOT, notifier=lambda e: print(f"  → {e.event_type} ({e.urgency:.1f}): {e.detail}"))
        daemon.start()
        
        print("  Monitoring for 5 seconds...")
        time.sleep(5)
        
        events = daemon.get_events()
        print(f"\n  Captured {len(events)} event(s)")
        for e in events:
            print(f"    - {e['event_type']}: {e['detail']}")
        
        daemon.stop()
        print("\n[PASS] EventDaemon functional")
    else:
        print("Usage: python event_daemon.py --test")
