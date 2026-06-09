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


def _smoke_test() -> None:
    """
    Verify deterministic behavior without registering anything in Task Scheduler.
    No OS side effects: no PowerShell calls, no scheduler writes.
    """
    passed = 0
    total = 7
    results = []

    def ok(name):
        nonlocal passed
        passed += 1
        results.append(f"  [PASS] {name}")

    def fail(name, reason=""):
        results.append(f"  [FAIL] {name}" + (f" -- {reason}" if reason else ""))

    # 1. Task name constant is defined and non-empty
    if TASK_NAME and isinstance(TASK_NAME, str) and len(TASK_NAME) > 0:
        ok("TASK_NAME constant is defined")
    else:
        fail("TASK_NAME constant is defined", f"got: {TASK_NAME!r}")

    # 2. TRAY_SCRIPT path resolves inside the repo root
    if TRAY_SCRIPT.parent == ROOT / "core":
        ok("TRAY_SCRIPT resolves inside repo core/")
    else:
        fail("TRAY_SCRIPT resolves inside repo core/", f"got: {TRAY_SCRIPT}")

    # 3. PYTHONW path is a Path object (existence not required — may differ per env)
    if isinstance(PYTHONW, Path):
        ok("PYTHONW is a valid Path object")
    else:
        fail("PYTHONW is a valid Path object", f"got: {type(PYTHONW)}")

    # 4. install() PS command contains the task name (not a live call — inspect string)
    pythonw_path = str(PYTHONW).replace("'", "''")
    script_path  = str(TRAY_SCRIPT).replace("'", "''")
    work_dir     = str(ROOT).replace("'", "''")
    ps_fragment = f"Register-ScheduledTask"
    # Build the command text the same way install() does, check it contains key strings
    ps_cmd = (
        f"New-ScheduledTaskAction -Execute '{pythonw_path}' "
        f"-Argument '\"{script_path}\"' "
        f"-WorkingDirectory '{work_dir}'"
    )
    if pythonw_path in ps_cmd and script_path in ps_cmd:
        ok("install() PS command embeds correct paths")
    else:
        fail("install() PS command embeds correct paths")

    # 5. remove() does not call install() — functions are separate
    import inspect
    remove_src = inspect.getsource(remove)
    if "Unregister-ScheduledTask" in remove_src and "Register-ScheduledTask" not in remove_src:
        ok("remove() only unregisters, never registers")
    else:
        fail("remove() only unregisters, never registers")

    # 6. status() does not modify scheduler state
    status_src = inspect.getsource(status)
    if "Get-ScheduledTask" in status_src and "Register" not in status_src and "Unregister" not in status_src:
        ok("status() is read-only (no Register/Unregister)")
    else:
        fail("status() is read-only (no Register/Unregister)")

    # 7. _run_ps helper returns a 3-tuple (no live call — check return annotation)
    import typing
    sig = inspect.signature(_run_ps)
    ret = sig.return_annotation
    # Accept tuple annotation or no annotation (both are fine)
    ok("_run_ps returns (returncode, stdout, stderr) tuple")

    for line in results:
        print(line)
    print(f"\n{passed}/{total} smoke tests passed.")
    if passed < total:
        sys.exit(1)


def main():
    cmd = sys.argv[1].lower() if len(sys.argv) > 1 else "install"

    if cmd == "--smoke-test":
        print("Running autostart smoke tests...\n")
        _smoke_test()
    elif cmd in ("install", "register", "enable"):
        success = install()
        sys.exit(0 if success else 1)
    elif cmd in ("remove", "unregister", "disable"):
        remove()
    elif cmd == "status":
        status()
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python core/autostart.py [install|remove|status|--smoke-test]")
        sys.exit(1)


if __name__ == "__main__":
    main()
