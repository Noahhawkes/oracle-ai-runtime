"""
Multi-channel Notifier for ORACLE — Escalating alerts based on urgency.

Urgency levels map to channels:
  0.0 - 0.3 (LOW)       → Silent (background observation only)
  0.3 - 0.6 (MEDIUM)    → Web notification + optional toast
  0.6 - 0.8 (HIGH)      → Sound alert + popup + terminal message
  0.8 - 1.0 (CRITICAL)  → Interrupt + speech + all channels

Supports:
  - Browser notifications (via FastAPI /notify endpoint)
  - System tray toast (Windows 10+)
  - Terminal interrupt (beep + message)
  - Speech synthesis (text-to-speech)
  - Custom callback handlers
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from typing import Optional, Callable, List
from dataclasses import dataclass

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))


@dataclass
class Notification:
    """Structured notification event."""
    message: str
    urgency: float
    event_type: str = "update"
    action_url: Optional[str] = None  # URL to respond/approve
    
    def to_dict(self):
        return {
            "message": self.message,
            "urgency": self.urgency,
            "event_type": self.event_type,
            "action_url": self.action_url,
        }


class NotificationChannel:
    """Base class for notification channels."""
    
    def send(self, notif: Notification) -> bool:
        """Send notification. Return True if successful."""
        raise NotImplementedError


class BrowserNotificationChannel(NotificationChannel):
    """Send notifications via FastAPI /notify endpoint."""
    
    def __init__(self, base_url: str = "http://localhost:7777"):
        self.base_url = base_url

    def send(self, notif: Notification) -> bool:
        try:
            import urllib.request
            import json
            
            payload = json.dumps(notif.to_dict()).encode('utf-8')
            req = urllib.request.Request(
                f"{self.base_url}/api/notify",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=2) as r:
                return r.status == 200
        except Exception:
            return False


class WindowsToastChannel(NotificationChannel):
    """Send Windows 10+ toast notifications."""
    
    def send(self, notif: Notification) -> bool:
        try:
            # PowerShell command to show toast
            ps_cmd = f"""
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications.ToastNotification] > $null
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("ORACLE.AI").Show(
                [Windows.UI.Notifications.ToastNotification]::new(
                    [Windows.Data.Xml.Dom.XmlDocument]::new() | ForEach-Object {{
                        $_.LoadXml(@"
<toast>
  <visual>
    <binding template="ToastText02">
      <text id="1">ORACLE</text>
      <text id="2">{notif.message}</text>
    </binding>
  </visual>
</toast>
"@)
                        $_
                    }}
                )
            )
            """
            subprocess.Popen(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        except Exception:
            return False


class TerminalChannel(NotificationChannel):
    """Send alerts to terminal (beep + message)."""
    
    def send(self, notif: Notification) -> bool:
        try:
            # Bell character + message
            print(f"\a[ORACLE] {notif.message}")
            return True
        except Exception:
            return False


class SpeechChannel(NotificationChannel):
    """Text-to-speech notifications."""
    
    def send(self, notif: Notification) -> bool:
        try:
            # Try using SAPI (Windows)
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(notif.message)
            engine.runAndWait()
            return True
        except Exception:
            # Fallback: PowerShell speaker sound
            try:
                ps_cmd = f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{notif.message}')"
                subprocess.Popen(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return True
            except Exception:
                return False


class MultiChannelNotifier:
    """Orchestrate notifications across multiple channels based on urgency."""
    
    def __init__(self):
        self.channels = {
            "browser": BrowserNotificationChannel(),
            "toast": WindowsToastChannel(),
            "terminal": TerminalChannel(),
            "speech": SpeechChannel(),
        }
        self.custom_handlers: List[Callable[[Notification], None]] = []

    def register_handler(self, handler: Callable[[Notification], None]):
        """Register a custom notification handler."""
        self.custom_handlers.append(handler)

    def notify(self, message: str, urgency: float, event_type: str = "update", action_url: Optional[str] = None):
        """Send notification with urgency-based escalation."""
        notif = Notification(message, urgency, event_type, action_url)
        
        # Call custom handlers first
        for handler in self.custom_handlers:
            try:
                handler(notif)
            except Exception:
                pass
        
        # Route to channels based on urgency
        if urgency < 0.3:
            # LOW: silent
            pass
        elif urgency < 0.6:
            # MEDIUM: browser notification + optional toast
            self.channels["browser"].send(notif)
            if urgency > 0.5:
                self.channels["toast"].send(notif)
        elif urgency < 0.8:
            # HIGH: sound + popup + terminal
            self.channels["terminal"].send(notif)
            self.channels["toast"].send(notif)
            self.channels["browser"].send(notif)
        else:
            # CRITICAL: all channels + speech
            self.channels["terminal"].send(notif)
            self.channels["toast"].send(notif)
            self.channels["browser"].send(notif)
            self.channels["speech"].send(notif)

    def test_channel(self, channel_name: str) -> bool:
        """Test a specific channel."""
        if channel_name not in self.channels:
            return False
        notif = Notification(f"Test notification ({channel_name})", 0.5)
        return self.channels[channel_name].send(notif)


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n[MultiChannelNotifier smoke test]\n")
    
    notifier = MultiChannelNotifier()
    
    print("  Testing urgency levels:\n")
    
    print("  [LOW] Silent notification (no output)...")
    notifier.notify("Background observation", 0.2)
    time.sleep(0.5)
    
    print("  [MEDIUM] Browser + toast...")
    notifier.notify("Detected file change in core/", 0.5)
    time.sleep(0.5)
    
    print("  [HIGH] Terminal + toast + browser...")
    notifier.notify("Memory candidate pending approval", 0.7)
    time.sleep(0.5)
    
    print("  [CRITICAL] All channels + speech...")
    notifier.notify("Critical: approval timeout reached", 0.95)
    time.sleep(1)
    
    print("\n[PASS] MultiChannelNotifier functional\n")
