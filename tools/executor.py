"""
Tool executor — runs tool calls from Claude, enforcing config-based allowlists.
Destructive operations (write/overwrite) prompt for confirmation.
"""

import os
import subprocess
import sys
from pathlib import Path

# When frozen by PyInstaller, use the exe's directory as ROOT.
# When running from source, ROOT is two levels up from tools/.
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

# Lazy-load config to avoid circular imports
_config = None


def _get_config():
    global _config
    if _config is None:
        import yaml
        with open(ROOT / "config.yaml", encoding="utf-8") as f:
            _config = yaml.safe_load(f)
    return _config


def _confirm(prompt: str) -> bool:
    """Prompt user for yes/no confirmation."""
    try:
        answer = input(f"\n[ORACLE ACTION] {prompt} (y/n): ").strip().lower()
        return answer in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """
    Dispatch a tool call. Returns a string result to feed back to Claude.
    All calls are logged via audit_log.
    """
    from audit_log import log

    try:
        if tool_name == "open_app":
            return _open_app(tool_input, log)
        elif tool_name == "run_script":
            return _run_script(tool_input, log)
        elif tool_name == "read_file":
            return _read_file(tool_input, log)
        elif tool_name == "write_file":
            return _write_file(tool_input, log)
        elif tool_name == "remember_fact":
            return _remember_fact(tool_input, log)
        elif tool_name == "recall_facts":
            return _recall_facts(tool_input, log)
        elif tool_name == "list_directory":
            return _list_directory(tool_input, log)
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as e:
        log("ERROR", f"Tool {tool_name} failed: {e}")
        return f"Error executing {tool_name}: {e}"


# ── Individual tool handlers ──────────────────────────────────────────────────

def _open_app(inp: dict, log) -> str:
    app_name = inp["app_name"].lower()
    args = inp.get("args", [])
    config = _get_config()
    approved = config.get("approved_apps", {})

    if app_name not in approved:
        log("ACTION", f"open_app:{app_name}", approved=False)
        return f"'{app_name}' is not in approved_apps. Approved: {list(approved.keys())}"

    exe_path = approved[app_name]
    cmd = [exe_path] + [str(a) for a in args]
    label = f"open_app:{app_name}" + (f" {args}" if args else "")

    if not _confirm(f"Launch {app_name}?" + (f" Args: {args}" if args else "")):
        log("ACTION", label, approved=False)
        return f"Cancelled: {app_name} not launched."

    subprocess.Popen(cmd, shell=False)
    log("ACTION", label, approved=True)
    return f"Launched {app_name}."


def _run_script(inp: dict, log) -> str:
    script_path = inp["script_path"]
    args = inp.get("args", [])
    config = _get_config()
    approved = config.get("approved_scripts", [])

    # Normalise path separators for comparison
    norm = script_path.replace("\\", "/")
    approved_norm = [s.replace("\\", "/") for s in approved]

    if norm not in approved_norm:
        log("ACTION", f"run_script:{script_path}", approved=False)
        return f"'{script_path}' is not in approved_scripts. Approved: {approved}"

    full_path = ROOT / script_path
    cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(full_path)] + args

    if not _confirm(f"Run script: {script_path}?" + (f" Args: {args}" if args else "")):
        log("ACTION", f"run_script:{script_path}", approved=False)
        return f"Cancelled: {script_path} not run."

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    log("ACTION", f"run_script:{script_path}", approved=True)
    output = result.stdout.strip() or result.stderr.strip() or "(no output)"
    return f"Script output:\n{output}"


def _read_file(inp: dict, log) -> str:
    raw_path = inp["path"]
    max_chars = inp.get("max_chars", 4000)
    path = Path(raw_path) if os.path.isabs(raw_path) else ROOT / raw_path

    if not path.exists():
        return f"File not found: {path}"
    if not path.is_file():
        return f"Not a file: {path}"

    log("ACTION", f"read_file:{path}", approved=True)
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n... [truncated at {max_chars} chars]"
    return text


def _write_file(inp: dict, log) -> str:
    raw_path = inp["path"]
    content = inp["content"]
    mode = inp.get("mode", "append")
    path = Path(raw_path) if os.path.isabs(raw_path) else ROOT / raw_path

    exists = path.exists()
    action_label = f"write_file:{path} (mode={mode})"

    if mode == "write" and exists:
        if not _confirm(f"Overwrite existing file: {path}?"):
            log("ACTION", action_label, approved=False)
            return f"Cancelled: file not overwritten."

    if not _confirm(f"{'Write' if mode == 'write' else 'Append to'} file: {path}?"):
        log("ACTION", action_label, approved=False)
        return f"Cancelled: file not written."

    path.parent.mkdir(parents=True, exist_ok=True)
    write_mode = "w" if mode == "write" else "a"
    with open(path, write_mode, encoding="utf-8") as f:
        f.write(content)

    log("ACTION", action_label, approved=True)
    return f"File {'written' if mode == 'write' else 'appended'}: {path}"


def _remember_fact(inp: dict, log) -> str:
    from memory import upsert_fact
    category = inp["category"]
    key = inp["key"]
    value = inp["value"]
    upsert_fact(category, key, value)
    log("ACTION", f"remember_fact:{category}/{key}", approved=True)
    return f"Remembered [{category}] {key}: {value}"


def _recall_facts(inp: dict, log) -> str:
    from memory import get_facts
    category = inp.get("category")
    facts = get_facts(category)
    if not facts:
        return "No facts found" + (f" in category '{category}'" if category else "") + "."
    lines = [f"[{f['category']}] {f['key']}: {f['value']}" for f in facts]
    log("ACTION", f"recall_facts:{category or 'all'}", approved=True)
    return "\n".join(lines)


def _list_directory(inp: dict, log) -> str:
    raw_path = inp["path"]
    path = Path(raw_path) if os.path.isabs(raw_path) else ROOT / raw_path

    if not path.exists():
        return f"Path not found: {path}"
    if not path.is_dir():
        return f"Not a directory: {path}"

    items = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    lines = []
    for item in items:
        prefix = "  " if item.is_file() else "  [DIR] "
        lines.append(f"{prefix}{item.name}")

    log("ACTION", f"list_directory:{path}", approved=True)
    return f"{path}\n" + "\n".join(lines) if lines else f"{path}\n  (empty)"
