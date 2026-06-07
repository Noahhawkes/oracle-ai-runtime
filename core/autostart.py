"""
core/autostart.py — ORACLE Auto-Start Manager

Registers ORACLE tray in Windows Task Scheduler so she starts
automatically at every login — silent, no terminal window, tray icon
appears in the bottom right corner of the taskbar.

Usage:
    python core/autostart.py install    — register auto-start
    python core/autostart.py remove     — unregister auto-start
    python core/autostart.py status     — check if registered
    python core/autostart.py            — same as install

Noah owns this machine. This only writes to the current user's
Task Scheduler (no admin rights required).
"""

import sys
import subprocess
import shlex
from pathlib import Path

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

TASK_NAME  = "ORACLE.AI Autostart"
TRAY_SCRIPT = ROOT / "core" / "tray.py"
PYTHONW    = Path(sys.executable).parent / "pythonw.exe"

# Fallback: find pythonw next to python
if not PYTHONW.exists():
    import shutil
    pw = shutil.which("pythonw")
    PYTHONW = Path(pw) if pw else Path(sys.executable)


def _run_ps(command: str) -> tuple[int, str, str]:
    """Run a PowerShell command. Returns (returncode, stdout, stderr)."""
    result = subprocess.run(
        ["powershell", "-NonInteractive", "-Command", command],
        capture_output=True, text=True
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def install() -> bool:
    """Register ORACLE tray in Task Scheduler. Returns True on success."""

    # Build the XML action — pythonw runs tray.py with no window
    pythonw_path = str(PYTHONW).replace("'", "''")
    script_path  = str(TRAY_SCRIPT).replace("'", "''")
    work_dir     = str(ROOT).replace("'", "''")

    ps = f"""
$action  = New-ScheduledTaskAction `
    -Execute '{pythonw_path}' `
    -Argument '"{script_path}"' `
    -WorkingDirectory '{work_dir}'

$trigger = New-ScheduledTaskTrigger -AtLogOn

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit 0 `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable

$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

$task = New-ScheduledTask `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description 'ORACLE.AI sovereign context engine — starts at login'

Register-ScheduledTask `
    -TaskName '{TASK_NAME}' `
    -InputObject $task `
    -Force | Out-Null

Write-Output 'OK'
"""
    code, out, err = _run_ps(ps)
    if code == 0 and "OK" in out:
        print(f"[autostart] ORACLE registered in Task Scheduler.")
        print(f"[autostart] Task: '{TASK_NAME}'")
        print(f"[autostart] Launches: {PYTHONW}")
        print(f"[autostart] Script:   {TRAY_SCRIPT}")
        print(f"[autostart] She will start automatically at every login.")
        return True
    else:
        print(f"[autostart] Registration failed.")
        if err:
            print(f"[autostart] Error: {err}")
        return False


def remove() -> bool:
    """Unregister ORACLE from Task Scheduler. Returns True on success."""
    ps = f"Unregister-ScheduledTask -TaskName '{TASK_NAME}' -Confirm:$false"
    code, out, err = _run_ps(ps)
    if code == 0:
        print(f"[autostart] ORACLE removed from Task Scheduler. She will no longer auto-start.")
        return True
    else:
        print(f"[autostart] Could not remove task (may not exist): {err}")
        return False


def status() -> bool:
    """Check if ORACLE is registered. Returns True if found."""
    ps = f"Get-ScheduledTask -TaskName '{TASK_NAME}' -ErrorAction SilentlyContinue | Select-Object TaskName, State | Format-List"
    code, out, err = _run_ps(ps)
    if out and "TaskName" in out:
        print(f"[autostart] ORACLE auto-start is ACTIVE.")
        print(out)
        return True
    else:
        print(f"[autostart] ORACLE auto-start is NOT registered.")
        return False


def main():
    cmd = sys.argv[1].lower() if len(sys.argv) > 1 else "install"

    if cmd in ("install", "register", "enable"):
        success = install()
        sys.exit(0 if success else 1)
    elif cmd in ("remove", "unregister", "disable"):
        remove()
    elif cmd == "status":
        status()
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python core/autostart.py [install|remove|status]")
        sys.exit(1)


if __name__ == "__main__":
    main()
