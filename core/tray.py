"""
ORACLE.AI System Tray — runs Oracle as a background process with a tray icon.
Right-click the tray icon to chat, view status, or quit.
"""

import os
import sys
import threading
import subprocess
from pathlib import Path

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

try:
    import pystray
    from pystray import MenuItem as item
    from PIL import Image, ImageDraw
except ImportError:
    print("Installing tray dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pystray", "Pillow"], check=True)
    import pystray
    from pystray import MenuItem as item
    from PIL import Image, ImageDraw

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

try:
    from autostart import install as _autostart_install, remove as _autostart_remove, status as _autostart_status
    _AUTOSTART_AVAILABLE = True
except Exception:
    _AUTOSTART_AVAILABLE = False

try:
    from updater import show_patch_notes_window
    _UPDATER_AVAILABLE = True
except Exception:
    _UPDATER_AVAILABLE = False


def create_icon():
    img = Image.new("RGB", (64, 64), color=(10, 10, 20))
    draw = ImageDraw.Draw(img)
    # Simple O shape for Oracle
    draw.ellipse([8, 8, 56, 56], outline=(0, 200, 255), width=5)
    draw.ellipse([20, 20, 44, 44], fill=(0, 200, 255))
    return img


_daemon_thread = None
_daemon_running = False
_chat_window = None


def start_daemon():
    global _daemon_thread, _daemon_running
    if _daemon_running:
        return
    _daemon_running = True

    def run():
        os.chdir(ROOT / "core")
        import importlib.util
        spec = importlib.util.spec_from_file_location("daemon", ROOT / "core" / "daemon.py")
        daemon = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(daemon)
        daemon.main()

    _daemon_thread = threading.Thread(target=run, daemon=True)
    _daemon_thread.start()


def open_chat(icon, item):
    subprocess.Popen(
        ["cmd", "/c", "start", "ORACLE.AI Chat", str(ROOT / "oracle.bat")],
        shell=False,
    )


def show_status(icon, item):
    from memory import get_facts
    facts = get_facts()
    recent = [f for f in facts if "autonomous_action" in f["key"]][-5:]
    if recent:
        msg = "Recent Oracle actions:\n" + "\n".join(
            f"  {f['value'][:80]}" for f in recent
        )
    else:
        msg = "Oracle is running. No autonomous actions logged yet."

    import ctypes
    ctypes.windll.user32.MessageBoxW(0, msg, "ORACLE.AI Status", 0x40)


def quit_oracle(icon, item):
    global _daemon_running
    _daemon_running = False
    icon.stop()


def _install_autostart(icon, menu_item):
    if _AUTOSTART_AVAILABLE:
        _autostart_install()
    import ctypes
    ctypes.windll.user32.MessageBoxW(0, "ORACLE auto-start enabled. She will run at every login.", "ORACLE.AI", 0x40)


def open_patch_notes(icon, menu_item):
    if _UPDATER_AVAILABLE:
        import threading
        threading.Thread(target=show_patch_notes_window, daemon=True).start()
    else:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, "Updater not available.", "ORACLE.AI", 0x10)


def _remove_autostart(icon, menu_item):
    if _AUTOSTART_AVAILABLE:
        _autostart_remove()
    import ctypes
    ctypes.windll.user32.MessageBoxW(0, "ORACLE auto-start disabled.", "ORACLE.AI", 0x40)


def _ensure_autostart_registered():
    """Silently register auto-start on first launch if not already set up."""
    if not _AUTOSTART_AVAILABLE:
        return
    try:
        import subprocess
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-Command",
             "Get-ScheduledTask -TaskName 'ORACLE.AI Autostart' -ErrorAction SilentlyContinue | Select-Object TaskName"],
            capture_output=True, text=True
        )
        if "ORACLE.AI Autostart" not in result.stdout:
            _autostart_install()
    except Exception:
        pass


def main():
    icon_image = create_icon()

    autostart_menu = pystray.Menu(
        item("Enable Auto-Start", _install_autostart),
        item("Disable Auto-Start", _remove_autostart),
    )

    menu = pystray.Menu(
        item("Open Chat", open_chat),
        item("View Status", show_status),
        item("Patch Notes / Update", open_patch_notes),
        pystray.Menu.SEPARATOR,
        item("Auto-Start", autostart_menu),
        pystray.Menu.SEPARATOR,
        item("Quit Oracle", quit_oracle),
    )

    tray = pystray.Icon("ORACLE.AI", icon_image, "ORACLE.AI", menu)

    # Register auto-start in Task Scheduler if not already done
    threading.Thread(target=_ensure_autostart_registered, daemon=True).start()

    # Start daemon in background
    threading.Thread(target=start_daemon, daemon=True).start()

    tray.run()


if __name__ == "__main__":
    main()
