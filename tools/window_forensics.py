"""
tools/window_forensics.py — catch the phantom keystrokes in the act.

Noah has two symptoms that have been happening since before the runtime existed:
keys repeating in bursts across many different letters, and PowerShell windows
opening while he types.

Forensic evidence found 2026-07-19:

    pid 68124  powershell.exe  parent 14416 (explorer.exe)  cmd: "powershell.exe"

A bare PowerShell launched by the Windows shell, not by a script. That is the
signature of the shell UI being driven, which is what a stuck Windows key does:
Win+X opens the power user menu, Win+R opens Run, and ordinary typing becomes
shortcuts.

This watcher records the evidence needed to confirm or kill that theory. It runs
ORACLE's own live window reader on a tight loop and logs:

  - every foreground window change, with timestamp
  - the state of the Windows / Ctrl / Alt / Shift keys at that moment
  - any new shell-spawned terminal, with its parent process

If a PowerShell appears while the Win key reads as DOWN and Noah is typing, the
theory is proven and the fix is hardware. If it appears with no modifier held,
something is driving the shell and we hunt that instead.

READ ONLY. Observes and records. Sends no input, kills nothing, touches no
external system. This is witness work, which is the job she was built for.

Usage:
    python tools/window_forensics.py            # watch until Ctrl+C
    python tools/window_forensics.py --seconds 600
"""

from __future__ import annotations

import argparse
import ctypes
import json
import sys
import time
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "Memory" / "window_forensics.jsonl"

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Virtual key codes for the modifiers that turn typing into shortcuts.
VK = {
    "LWIN": 0x5B,
    "RWIN": 0x5C,
    "CONTROL": 0x11,
    "MENU": 0x12,   # Alt
    "SHIFT": 0x10,
}

SHELL_PROCESSES = {"powershell.exe", "pwsh.exe", "cmd.exe",
                   "WindowsTerminal.exe", "conhost.exe"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _key_down(vk: int) -> bool:
    """True if the key is physically down right now.

    GetAsyncKeyState high bit means currently pressed. A modifier that reads
    down while Noah is not holding it is the smoking gun."""
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def modifier_state() -> dict[str, bool]:
    return {name: _key_down(code) for name, code in VK.items()}


def foreground() -> dict[str, object]:
    """Read the live foreground window: process name, title, pid."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return {"hwnd": 0, "app": None, "title": None, "pid": None}

    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    title = (buf.value or "").strip() or None

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    app = None
    try:
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if handle:
            size = wintypes.DWORD(260)
            pbuf = ctypes.create_unicode_buffer(size.value)
            if kernel32.QueryFullProcessImageNameW(handle, 0, pbuf, ctypes.byref(size)):
                app = Path(pbuf.value).name
            kernel32.CloseHandle(handle)
    except Exception:
        pass

    return {"hwnd": int(hwnd), "app": app, "title": title, "pid": int(pid.value)}


def _log(record: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def watch(seconds: int | None, interval: float = 0.25) -> int:
    print(f"  watching foreground windows, logging to {LOG_PATH}")
    print("  type normally. if a PowerShell appears, the modifier state at that")
    print("  instant is recorded. Ctrl+C to stop.\n")

    start = time.time()
    last_hwnd = None
    events = 0
    stuck_observations = 0

    try:
        while True:
            if seconds is not None and (time.time() - start) > seconds:
                break

            mods = modifier_state()
            win_down = mods["LWIN"] or mods["RWIN"]

            # A Windows key reading down for many consecutive samples while no
            # deliberate shortcut is happening is exactly the fault we suspect.
            if win_down:
                stuck_observations += 1
                if stuck_observations in (4, 20, 80):
                    held = stuck_observations * interval
                    print(f"  [!] WIN key has read DOWN for ~{held:.1f}s continuously")
                    _log({"ts": _now(), "event": "win_key_held",
                          "held_seconds": round(held, 2),
                          "foreground": foreground()})
            else:
                stuck_observations = 0

            fg = foreground()
            if fg["hwnd"] != last_hwnd:
                last_hwnd = fg["hwnd"]
                is_shell = (fg.get("app") or "") in SHELL_PROCESSES
                record = {
                    "ts": _now(),
                    "event": "shell_window_appeared" if is_shell else "focus_change",
                    "app": fg.get("app"),
                    "title": fg.get("title"),
                    "pid": fg.get("pid"),
                    "modifiers_at_that_instant": mods,
                    "win_key_down": win_down,
                }
                _log(record)
                events += 1

                if is_shell:
                    verdict = ("WIN KEY WAS DOWN -> stuck-modifier theory CONFIRMED"
                               if win_down else
                               "no modifier held -> something else opened this")
                    print(f"  [{datetime.now():%H:%M:%S}] SHELL WINDOW: {fg.get('app')}")
                    print(f"      title      : {fg.get('title')}")
                    print(f"      modifiers  : {mods}")
                    print(f"      >>> {verdict}\n")

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n  stopped by user")

    print(f"\n  {events} focus events recorded -> {LOG_PATH}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Window/keystroke forensics (read-only)")
    parser.add_argument("--seconds", type=int, default=None,
                        help="stop after N seconds (default: run until Ctrl+C)")
    parser.add_argument("--check", action="store_true",
                        help="one-shot: print current modifier and window state")
    args = parser.parse_args(argv)

    if args.check:
        print(f"  foreground : {foreground()}")
        print(f"  modifiers  : {modifier_state()}")
        return 0

    return watch(args.seconds)


if __name__ == "__main__":
    raise SystemExit(main())
