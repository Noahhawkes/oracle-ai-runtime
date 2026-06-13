"""
presence_daemon.py — Integration of event daemon, notifier, and hotkeys.

Orchestrates:
  1. Event daemon (file/git/memory monitoring)
  2. Multi-channel notifier (urgency-based alerts)
  3. Hotkey handler (user control: Win+O, Ctrl+Shift+X)
  4. FastAPI endpoints (/api/notify, /api/approve, etc.)

This works alongside oracle_presence.py (which handles the on-screen window).

Usage:
    from presence_daemon import start_daemon, stop_daemon
    
    start_daemon()  # Start monitoring in background
    # ...
    stop_daemon()   # Stop when done
"""

import sys
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

# Import daemon components (installed in platforms/windows/)
try:
    from platforms.windows.event_daemon import EventDaemon, WindowEvent
    from platforms.windows.notifier import MultiChannelNotifier, Notification
    from platforms.windows.hotkey_handler import OracleHotkeyManager
    HAS_DAEMON = True
except ImportError as e:
    print(f"[PresenceDaemon] Daemon components not available: {e}")
    HAS_DAEMON = False


class PresenceDaemonOrchestrator:
    """Master orchestrator for ORACLE's always-on monitoring and proactive presence."""
    
    def __init__(self, ui_url: str = "http://localhost:7777"):
        self.ui_url = ui_url
        self.root = ROOT
        self.running = False
        
        if not HAS_DAEMON:
            print("[PresenceDaemon] Warning: daemon modules not available")
            self.notifier = None
            self.daemon = None
            self.hotkeys = None
            return
        
        # Initialize components
        self.notifier = MultiChannelNotifier()
        self.daemon = EventDaemon(self.root, notifier=self._on_daemon_event)
        self.hotkeys = OracleHotkeyManager(ui_url)
        
        self._initialize_custom_handlers()

    def _initialize_custom_handlers(self):
        """Register custom notification handlers."""
        if not self.notifier:
            return
        
        def on_memory_candidate(notif: Notification):
            """High-priority handler for memory candidates."""
            if "memory" in notif.event_type.lower() or "candidate" in notif.message.lower():
                print(f"[PresenceDaemon] Memory candidate detected: {notif.message}")
                # Could integrate with memory.py to auto-save candidates
                pass
        
        def on_approval_needed(notif: Notification):
            """Handle approval-needed events."""
            if "approval" in notif.event_type.lower():
                print(f"[PresenceDaemon] Approval needed: {notif.message}")
                # Could send direct action link to UI
                pass
        
        self.notifier.register_handler(on_memory_candidate)
        self.notifier.register_handler(on_approval_needed)

    def _on_daemon_event(self, event: WindowEvent):
        """Callback from daemon when an event is detected."""
        if not self.notifier:
            return
        
        # Feed into salience filter
        try:
            from salience_filter import infer_signal, ingest_signal
            signal = infer_signal(event.source, event.detail)
            # Override urgency from daemon if it calculated one
            if event.urgency > signal.urgency:
                signal.urgency = event.urgency
            ingest_signal(signal)
        except Exception as e:
            print(f"[PresenceDaemon] Error ingesting signal: {e}")
        
        # Translate daemon event to notification
        self.notifier.notify(
            message=event.detail,
            urgency=event.urgency,
            event_type=event.event_type,
        )

    def start(self):
        """Start all daemon components."""
        if self.running or not HAS_DAEMON:
            return
        
        self.running = True
        
        # Start event daemon
        if self.daemon:
            self.daemon.start()
        
        # Start hotkey listener
        if self.hotkeys:
            self.hotkeys.start()
        
        print("[PresenceDaemon] All components started (monitoring for changes)")

    def stop(self):
        """Stop all daemon components."""
        if not self.running or not HAS_DAEMON:
            return
        
        self.running = False
        
        # Stop hotkey listener
        if self.hotkeys:
            self.hotkeys.stop()
        
        # Stop daemon
        if self.daemon:
            self.daemon.stop()
        
        print("[PresenceDaemon] All components stopped")

    def get_daemon_events(self, limit: int = 20) -> list[dict]:
        """Retrieve recent daemon events for debugging."""
        if not self.daemon:
            return []
        return self.daemon.get_events(limit)

    def notify(self, message: str, urgency: float):
        """Manually trigger a notification."""
        if not self.notifier:
            return
        self.notifier.notify(message, urgency)


# ── Global daemon instance ────────────────────────────────────────────────────

_daemon: Optional[PresenceDaemonOrchestrator] = None


def init_daemon() -> Optional[PresenceDaemonOrchestrator]:
    """Initialize global daemon instance."""
    global _daemon
    if _daemon is None and HAS_DAEMON:
        _daemon = PresenceDaemonOrchestrator()
    return _daemon


def get_daemon() -> Optional[PresenceDaemonOrchestrator]:
    """Get or create global daemon instance."""
    if _daemon is None:
        return init_daemon()
    return _daemon


def start_daemon():
    """Start ORACLE presence daemon."""
    daemon = get_daemon()
    if daemon:
        daemon.start()


def stop_daemon():
    """Stop ORACLE presence daemon."""
    if _daemon:
        _daemon.stop()


def notify_user(message: str, urgency: float):
    """Send notification to user via daemon."""
    daemon = get_daemon()
    if daemon:
        daemon.notify(message, urgency)


def get_events(limit: int = 20) -> list[dict]:
    """Get recent daemon events."""
    daemon = get_daemon()
    if daemon:
        return daemon.get_daemon_events(limit)
    return []


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n[PresenceDaemon smoke test]\n")
    
    if not HAS_DAEMON:
        print("  [SKIP] Daemon modules not available\n")
    else:
        try:
            daemon = PresenceDaemonOrchestrator()
            daemon.start()
            
            print("  Daemon running for 8 seconds...")
            print("  Monitoring for file changes, git updates, and memory changes\n")
            
            time.sleep(8)
            
            events = daemon.get_daemon_events(10)
            print(f"\n  Captured {len(events)} event(s):")
            for evt in events:
                print(f"    - [{evt['urgency']:.1f}] {evt['event_type']}: {evt['detail']}")
            
            daemon.stop()
            print("\n[PASS] PresenceDaemon functional\n")
        except Exception as e:
            print(f"\n[ERROR] {e}\n")
            import traceback
            traceback.print_exc()
