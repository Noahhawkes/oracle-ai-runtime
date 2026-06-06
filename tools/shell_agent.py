"""
ORACLE.AI — Shell Agent (Phase 2)
Unrestricted PowerShell + CMD execution with full audit logging.
Gives ORACLE the ability to run any command, install software, build projects.
"""

import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent


def _log(action: str, command: str, success: bool, output: str = ""):
    """Write shell action to audit log."""
    try:
        sys.path.insert(0, str(ROOT / "core"))
        from audit_log import log
        status = "SUCCESS" if success else "FAILED"
        log("SHELL", f"[{status}] {command[:100]}")
    except Exception:
        pass  # Don't let logging failure break execution


def run_powershell(command: str, timeout: int = 120, cwd: str = None) -> dict:
    """
    Execute a PowerShell command string.
    Returns dict with stdout, stderr, returncode, success.
    """
    working_dir = cwd or str(ROOT)

    cmd = [
        "powershell",
        "-ExecutionPolicy", "Bypass",
        "-NoProfile",
        "-Command", command
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=working_dir
        )
        success = result.returncode == 0
        output = result.stdout.strip()
        error = result.stderr.strip()
        _log("RUN", command, success, output)

        return {
            "success": success,
            "stdout": output,
            "stderr": error,
            "returncode": result.returncode,
            "command": command
        }
    except subprocess.TimeoutExpired:
        _log("TIMEOUT", command, False)
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
            "returncode": -1,
            "command": command
        }
    except Exception as e:
        _log("ERROR", command, False, str(e))
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
            "command": command
        }


def run_cmd(command: str, timeout: int = 120, cwd: str = None) -> dict:
    """
    Execute a CMD command string.
    Returns dict with stdout, stderr, returncode, success.
    """
    working_dir = cwd or str(ROOT)

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=working_dir
        )
        success = result.returncode == 0
        _log("CMD", command, success)

        return {
            "success": success,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
            "command": command
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
            "returncode": -1,
            "command": command
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
            "command": command
        }


def install_package(package: str, manager: str = "pip") -> dict:
    """
    Install a package via pip, npm, choco, or winget.
    """
    commands = {
        "pip": f"pip install {package}",
        "npm": f"npm install -g {package}",
        "choco": f"choco install {package} -y",
        "winget": f"winget install {package} --silent"
    }

    if manager not in commands:
        return {"success": False, "stderr": f"Unknown manager: {manager}. Use: pip, npm, choco, winget"}

    cmd = commands[manager]
    _log("INSTALL", cmd, True)
    return run_powershell(cmd, timeout=300)


def pip_install(package: str) -> str:
    """Quick pip install. Returns success string."""
    result = install_package(package, "pip")
    if result["success"]:
        return f"Installed: {package}\n{result['stdout'][:500]}"
    return f"Failed to install {package}:\n{result['stderr'][:500]}"


def get_python_version() -> str:
    result = run_powershell("python --version")
    return result["stdout"] or result["stderr"]


def get_node_version() -> str:
    result = run_powershell("node --version")
    return result["stdout"] or "Node.js not found"


def get_git_status(repo_path: str = None) -> str:
    path = repo_path or str(ROOT)
    result = run_powershell("git status --short", cwd=path)
    return result["stdout"] or "Clean working tree"


def git_commit(message: str, repo_path: str = None) -> str:
    path = repo_path or str(ROOT)
    add = run_powershell("git add -A", cwd=path)
    commit = run_powershell(f'git commit -m "{message}"', cwd=path)
    if commit["success"]:
        return f"Committed: {message}"
    return f"Commit failed:\n{commit['stderr']}"


def git_push(repo_path: str = None) -> str:
    path = repo_path or str(ROOT)
    result = run_powershell("git push", cwd=path)
    if result["success"]:
        return f"Pushed to remote."
    return f"Push failed:\n{result['stderr']}"


def create_venv(venv_path: str = None) -> str:
    path = venv_path or str(ROOT / "venv")
    result = run_powershell(f"python -m venv {path}")
    if result["success"]:
        return f"Virtual environment created at: {path}"
    return f"venv creation failed:\n{result['stderr']}"


def run_python_file(filepath: str, args: list = None, cwd: str = None) -> dict:
    """Run a Python file directly."""
    arg_str = " ".join(args) if args else ""
    cmd = f"python {filepath} {arg_str}".strip()
    return run_powershell(cmd, cwd=cwd or str(ROOT))


def format_result(result: dict) -> str:
    """Format a shell result dict into a readable string."""
    lines = []
    if result["stdout"]:
        lines.append(result["stdout"])
    if result["stderr"] and not result["success"]:
        lines.append(f"[STDERR] {result['stderr']}")
    if not lines:
        return f"Exit code: {result['returncode']}"
    return "\n".join(lines)
