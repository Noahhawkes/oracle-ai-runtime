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


def main():
    icon_image = create_icon()

    menu = pystray.Menu(
        item("Open Chat", open_chat),
        item("View Status", show_status),
        pystray.Menu.SEPARATOR,
        item("Quit Oracle", quit_oracle),
    )

    tray = pystray.Icon("ORACLE.AI", icon_image, "ORACLE.AI", menu)

    # Start daemon in background
    threading.Thread(target=start_daemon, daemon=True).start()

    tray.run()


if __name__ == "__main__":
    main()
