"""
Hotkey Handler for ORACLE — Global keyboard shortcuts.

Hotkeys:
  Win+O               → Focus ORACLE UI (open browser or bring to foreground)
  Ctrl+Shift+A        → Approve pending action
  Ctrl+Shift+M        → Open memory/dashboard
  Ctrl+Shift+X        → Emergency stop (pause all automation)

Requires keyboard monitoring library (pynput or pyautogui).
"""

import sys
import time
import subprocess
import webbrowser
from pathlib import Path
from typing import Callable, Dict, Optional

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


class HotkeyHandler:
    """Global hotkey detection and callback dispatch."""
    
    def __init__(self):
        self.hotkeys: Dict[str, Callable] = {}
        self.running = False
        self.listener = None
        
        # Try to import keyboard library
        try:
            import keyboard
            self.keyboard = keyboard
            self.use_keyboard = True
        except ImportError:
            self.use_keyboard = False
            print("[HotkeyHandler] 'keyboard' library not available. Install with: pip install keyboard")

    def register(self, hotkey: str, callback: Callable):
        """Register a hotkey -> callback mapping.
        
        Hotkey format: "ctrl+shift+a", "win+o", etc.
        """
        self.hotkeys[hotkey.lower()] = callback

    def start(self):
        """Start listening for hotkeys."""
        if not self.use_keyboard or self.running:
            return
        
        self.running = True
        
        # Register all hotkeys
        for hotkey, callback in self.hotkeys.items():
            try:
                self.keyboard.add_hotkey(hotkey, callback)
            except Exception as e:
                print(f"[HotkeyHandler] Failed to register '{hotkey}': {e}")
        
        print(f"[HotkeyHandler] Listening for {len(self.hotkeys)} hotkeys...")

    def stop(self):
        """Stop listening for hotkeys."""
        if not self.use_keyboard or not self.running:
            return
        
        self.keyboard.unhook_all()
        self.running = False
        print("[HotkeyHandler] Stopped")

    def wait(self):
        """Block until interrupted."""
        if self.use_keyboard:
            self.keyboard.wait()


class OracleHotkeyManager:
    """ORACLE-specific hotkey bindings and callbacks."""
    
    def __init__(self, ui_url: str = "http://localhost:7777"):
        self.ui_url = ui_url
        self.handler = HotkeyHandler()
        self._setup_hotkeys()

    def _setup_hotkeys(self):
        """Register all ORACLE hotkeys."""
        self.handler.register("win+o", self._focus_ui)
        self.handler.register("ctrl+shift+a", self._approve_pending)
        self.handler.register("ctrl+shift+m", self._open_memory)
        self.handler.register("ctrl+shift+x", self._emergency_stop)

    def _focus_ui(self):
        """Win+O: Open or focus ORACLE UI."""
        print("[Hotkey] Win+O: Opening ORACLE UI...")
        try:
            webbrowser.open(self.ui_url)
        except Exception as e:
            print(f"[Hotkey error] Failed to open browser: {e}")

    def _approve_pending(self):
        """Ctrl+Shift+A: Send approval to ORACLE."""
        print("[Hotkey] Ctrl+Shift+A: Approving pending action...")
        try:
            import urllib.request
            import json
            
            payload = json.dumps({"action": "approve_pending"}).encode('utf-8')
            req = urllib.request.Request(
                f"{self.ui_url}/api/approve",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=2) as r:
                result = json.loads(r.read().decode())
                print(f"[Hotkey] Approval sent: {result}")
        except Exception as e:
            print(f"[Hotkey error] Approval failed: {e}")

    def _open_memory(self):
        """Ctrl+Shift+M: Open memory dashboard."""
        print("[Hotkey] Ctrl+Shift+M: Opening memory dashboard...")
        try:
            webbrowser.open(f"{self.ui_url}#memory")
        except Exception as e:
            print(f"[Hotkey error] Failed to open memory: {e}")

    def _emergency_stop(self):
        """Ctrl+Shift+X: Emergency stop (pause ORACLE)."""
        print("[Hotkey] Ctrl+Shift+X: EMERGENCY STOP - pausing ORACLE...")
        try:
            import urllib.request
            
            req = urllib.request.Request(
                f"{self.ui_url}/api/pause",
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=2) as r:
                print(f"[Hotkey] ORACLE paused (status {r.status})")
        except Exception as e:
            print(f"[Hotkey error] Stop failed: {e}")

    def start(self):
        """Start listening for hotkeys."""
        self.handler.start()

    def stop(self):
        """Stop listening."""
        self.handler.stop()

    def wait(self):
        """Block until interrupted (Ctrl+C)."""
        try:
            self.handler.wait()
        except KeyboardInterrupt:
            print("\n[HotkeyManager] Interrupted by user")
            self.stop()


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n[HotkeyManager smoke test]\n")
    
    manager = OracleHotkeyManager()
    
    if not manager.handler.use_keyboard:
        print("  [SKIP] 'keyboard' library not installed (required for hotkey detection)")
        print("  Install with: pip install keyboard\n")
    else:
        print("  Starting hotkey listener (press Ctrl+C to stop)...")
        print("  Try pressing:")
        print("    Win+O             → Open UI")
        print("    Ctrl+Shift+A      → Approve")
        print("    Ctrl+Shift+M      → Memory")
        print("    Ctrl+Shift+X      → Emergency stop\n")
        
        manager.start()
        try:
            manager.wait()
        except KeyboardInterrupt:
            print("\n  Stopped")
        manager.stop()
    
    print("\n[PASS] HotkeyManager structural test complete\n")
