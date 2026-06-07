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

# Ensure tools/ and core/ are importable for Phase 2 module imports
for _p in (str(ROOT), str(ROOT / "core"), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

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
        elif tool_name == "run_shell":
            return _run_shell(tool_input, log)
        elif tool_name == "install_package":
            return _install_package(tool_input, log)
        elif tool_name == "browser_navigate":
            return _browser_navigate(tool_input, log)
        elif tool_name == "browser_search":
            return _browser_search(tool_input, log)
        elif tool_name == "browser_session":
            return _browser_session(tool_input, log)
        elif tool_name == "filesystem_scan":
            return _filesystem_scan(tool_input, log)
        elif tool_name == "filesystem_search":
            return _filesystem_search(tool_input, log)
        elif tool_name == "filesystem_summary":
            return _filesystem_summary(tool_input, log)
        elif tool_name == "create_project":
            return _create_project(tool_input, log)
        elif tool_name == "build_exe":
            return _build_exe(tool_input, log)
        elif tool_name == "scheduler_control":
            return _scheduler_control(tool_input, log)
        elif tool_name == "ask_chatgpt":
            return _ask_chatgpt(tool_input, log)
        elif tool_name == "daemon_cycle":
            return _daemon_cycle(tool_input, log)
        elif tool_name == "source_map_scan":
            return _source_map_scan(tool_input, log)
        elif tool_name == "source_map_search":
            return _source_map_search(tool_input, log)
        elif tool_name == "source_map_ingest":
            return _source_map_ingest(tool_input, log)
        elif tool_name == "computer_operator":
            return _computer_operator(tool_input, log)
        elif tool_name == "terminal_run":
            return _terminal_run(tool_input, log)
        elif tool_name == "terminal_cd":
            return _terminal_cd(tool_input, log)
        elif tool_name == "terminal_status":
            return _terminal_status(tool_input, log)
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


def _run_shell(inp: dict, log) -> str:
    command = inp["command"]
    cwd = inp.get("cwd", str(ROOT))
    timeout = inp.get("timeout", 120)

    log("ACTION", f"run_shell: {command[:100]}", approved=True)
    try:
        result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-Command", command],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout.strip()
        if result.returncode != 0 and result.stderr.strip():
            output += f"\nSTDERR: {result.stderr.strip()}"
        return output or "(command completed, no output)"
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s"
    except Exception as e:
        return f"Shell error: {e}"


def _install_package(inp: dict, log) -> str:
    package = inp["package"]
    manager = inp.get("manager", "pip")
    cmd_map = {
        "pip": f"pip install {package}",
        "npm": f"npm install -g {package}",
        "choco": f"choco install {package} -y",
        "winget": f"winget install {package}",
    }
    command = cmd_map.get(manager, f"pip install {package}")
    log("ACTION", f"install_package:{manager}:{package}", approved=True)
    result = subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True, text=True, timeout=180,
    )
    return result.stdout.strip() or result.stderr.strip() or "(install completed)"


# ── Phase 2: Browser ──────────────────────────────────────────────────────────

def _browser_navigate(inp: dict, log) -> str:
    from browser_agent import browser_navigate
    log("ACTION", f"browser_navigate:{inp['url']}", approved=True)
    return browser_navigate(inp["url"], inp.get("headless", False))


def _browser_search(inp: dict, log) -> str:
    from browser_agent import browser_search
    log("ACTION", f"browser_search:{inp['query']}", approved=True)
    return browser_search(inp["query"], inp.get("engine", "google"))


def _browser_session(inp: dict, log) -> str:
    import browser_agent as ba
    action = inp["action"]
    log("ACTION", f"browser_session:{action}", approved=True)
    if action == "start":
        return ba.session_start(inp.get("headless", False))
    elif action == "stop":
        return ba.session_stop()
    elif action == "navigate":
        return ba.session_navigate(inp["url"])
    elif action == "get_text":
        return ba.session_get_text()
    elif action == "click":
        return ba.session_click(inp["selector"])
    elif action == "type":
        return ba.session_type(inp["selector"], inp.get("text", ""))
    elif action == "screenshot":
        return ba.session_screenshot()
    return f"Unknown browser action: {action}"


# ── Phase 2: Filesystem Mapper ────────────────────────────────────────────────

def _filesystem_scan(inp: dict, log) -> str:
    from filesystem_mapper import build_index, save_index, get_summary
    paths = inp.get("paths")
    label = f"filesystem_scan paths={paths or 'default (ORACLE.AI repo + Projects/)'}"
    if not _confirm(f"Scan and index filesystem? {label}\nThis may take a moment."):
        log("ACTION", label, approved=False)
        return "Cancelled: filesystem scan not run."
    log("ACTION", label, approved=True)
    index = build_index(paths, inp.get("max_depth", 4))
    save_index(index)
    return get_summary(index)


def _filesystem_search(inp: dict, log) -> str:
    from filesystem_mapper import search_index
    log("ACTION", f"filesystem_search:{inp['query']}", approved=True)
    results = search_index(inp["query"])
    if not results:
        return f"No files found matching '{inp['query']}'. (Run filesystem_scan first if index is empty.)"
    lines = [f"{r['path']} ({r.get('size_kb', '?')} KB)" for r in results]
    return f"{len(results)} match(es):\n" + "\n".join(lines)


def _filesystem_summary(inp: dict, log) -> str:
    from filesystem_mapper import get_summary
    log("ACTION", "filesystem_summary", approved=True)
    return get_summary()


# ── Phase 2: Build Agent ──────────────────────────────────────────────────────

def _create_project(inp: dict, log) -> str:
    from build_agent import create_project
    log("ACTION", f"create_project:{inp['name']}", approved=True)
    return create_project(
        name=inp["name"],
        template=inp.get("template", "python_cli"),
        description=inp.get("description", ""),
        location=inp.get("location"),
        install_deps=inp.get("install_deps", True),
    )


def _build_exe(inp: dict, log) -> str:
    from build_agent import build_python_exe
    log("ACTION", f"build_exe:{inp['project_path']}", approved=True)
    return build_python_exe(
        inp["project_path"],
        inp.get("entry_file", "main.py"),
        inp.get("name"),
    )


# ── Phase 2: Scheduler ────────────────────────────────────────────────────────

def _scheduler_control(inp: dict, log) -> str:
    import scheduler as sch
    action = inp["action"]
    log("ACTION", f"scheduler_control:{action}", approved=True)
    if action == "start":
        return sch.start_autonomous_mode()
    elif action == "stop":
        return sch.stop_autonomous_mode()
    elif action == "status":
        return sch.scheduler_status()
    elif action == "add_task":
        return sch.add_custom_task(
            inp["task_name"],
            inp["command"],
            inp.get("interval_minutes", 60),
        )
    return f"Unknown scheduler action: {action}"


# ── ChatGPT Bridge ────────────────────────────────────────────────────────────

_ASK_CHATGPT_GOAL = """Focus the ChatGPT tab in Chrome (open chatgpt.com if it isn't open already).

TYPE THIS EXACT MESSAGE into the ChatGPT message input box at the bottom of the page, then send it:

---
{message}
---

After sending, WAIT for ChatGPT to finish its complete response — the response is done when the send button re-appears and there is no more text streaming in. Then read the FULL response text carefully from the screen. Call task_done with the complete response text as the summary. Do not summarize or shorten it — copy the full response."""

def _ask_chatgpt(inp: dict, log) -> str:
    try:
        import computer_control as cc
        if not cc.HANDS_AVAILABLE:
            return "ask_chatgpt unavailable: pyautogui/PIL not installed."
    except ImportError:
        return "ask_chatgpt unavailable: computer_control module not found."
    import sov1
    from llm import is_local, make_client, get_model

    question = inp["question"].strip()
    context = inp.get("context", "").strip()
    message = f"{context}\n\n{question}".strip() if context else question

    log("BRIDGE", f"Asking ChatGPT: {question[:100]}")
    goal = _ASK_CHATGPT_GOAL.format(message=message)

    try:
        client = make_client()
    except RuntimeError as e:
        return f"ask_chatgpt unavailable: {e}"

    if is_local():
        model = get_model(vision=True)
        result = sov1.operate_local(client, goal, model)
    else:
        model = get_model(vision=True)
        result = sov1.operate(client, goal, model)

    if result:
        log("BRIDGE", f"ChatGPT response received ({len(result)} chars)")
        return f"ChatGPT says:\n\n{result}"
    return "ChatGPT did not return a response (step limit reached or task_done not called)."


# ── Daemon ────────────────────────────────────────────────────────────────────

def _daemon_cycle(inp: dict, log) -> str:
    sys.path.insert(0, str(ROOT / "core"))
    from daemon import run_autonomous_cycle, _preflight, _daemon_prompt
    from memory import new_session, get_facts
    from context_loader import build_system_prompt
    from llm import is_local, make_client, get_model
    log("ACTION", "daemon_cycle", approved=True)
    try:
        client = make_client()
    except RuntimeError as e:
        return f"Daemon cycle unavailable: {e}"
    local = is_local()
    model = get_model(vision=False)
    system_prompt = build_system_prompt()
    session_id = new_session()
    proposal_path = run_autonomous_cycle(client, session_id, system_prompt, local, model)
    return f"Daemon cycle complete. Proposal written to: {proposal_path}"


# ── Source Map ────────────────────────────────────────────────────────────────

def _source_map_scan(inp: dict, log) -> str:
    sys.path.insert(0, str(ROOT / "core"))
    from source_map import build_index, save_index, get_index_summary
    log("ACTION", "source_map_scan", approved=True)
    paths = inp.get("paths") or None
    include_excerpts = inp.get("include_excerpts", True)
    print("[Source Map] Scanning — this may take a minute on first run...")
    index = build_index(scan_paths=paths, include_excerpts=include_excerpts)
    save_index(index)
    return get_index_summary()


def _source_map_search(inp: dict, log) -> str:
    sys.path.insert(0, str(ROOT / "core"))
    from source_map import search_index, load_index
    query = inp["query"]
    max_results = inp.get("max_results", 20)
    log("ACTION", f"source_map_search:{query}", approved=True)
    index = load_index()
    if not index:
        return "No source map found. Run source_map_scan first."
    results = search_index(query, max_results=max_results)
    if not results:
        return f"No files found matching '{query}'."
    lines = [f"{r['path']}  [{r['ext']} | {r['size_kb']} KB | {r['modified']}]" for r in results]
    return f"{len(results)} file(s) matching '{query}':\n" + "\n".join(lines)


def _source_map_ingest(inp: dict, log) -> str:
    sys.path.insert(0, str(ROOT / "core"))
    from source_map import ingest_file_to_memory
    path = inp["path"]
    summary = inp["summary"]
    category = inp.get("category", "source_map")
    log("ACTION", f"source_map_ingest:{path}", approved=True)
    ingest_file_to_memory(path, summary, category)
    return f"Ingested into memory [{category}]: {Path(path).name}"


# ── Computer Operator (SOV1) ──────────────────────────────────────────────────

def _computer_operator(inp: dict, log) -> str:
    try:
        import computer_control as cc
        if not cc.HANDS_AVAILABLE:
            return "Computer operator unavailable: pyautogui/PIL not installed. Run: pip install pyautogui pillow"
    except ImportError:
        return "Computer operator unavailable: computer_control module not found."
    import sov1
    from llm import is_local, make_client, get_model
    goal = inp["goal"]
    log("SOV1", f"Delegating to computer operator: {goal}")
    try:
        client = make_client()
    except RuntimeError as e:
        return f"Computer operator unavailable: {e}"
    if is_local():
        model = get_model(vision=True)
        result = sov1.operate_local(client, goal, model)
    else:
        model = get_model(vision=True)
        result = sov1.operate(client, goal, model)
    if result:
        return result
    return f"Computer operator finished: {goal}"


def _terminal_run(inp: dict, log) -> str:
    sys.path.insert(0, str(ROOT / "core"))
    from terminal import get_terminal
    command = inp["command"]
    timeout = float(inp.get("timeout", 60))
    log("TERMINAL", f"run: {command[:120]}")
    term = get_terminal()
    output = term.run(command, timeout=timeout)
    return f"[Terminal @ {term.get_cwd()}]\n{output}"


def _terminal_cd(inp: dict, log) -> str:
    sys.path.insert(0, str(ROOT / "core"))
    from terminal import get_terminal
    path = inp["path"]
    log("TERMINAL", f"cd: {path}")
    term = get_terminal()
    output = term.run(f"Set-Location '{path}'")
    cwd = term.get_cwd()
    return f"Changed directory to: {cwd}" + (f"\n{output}" if output and "ERROR" in output else "")


def _terminal_status(inp: dict, log) -> str:
    sys.path.insert(0, str(ROOT / "core"))
    from terminal import get_terminal
    term = get_terminal()
    cwd = term.get_cwd()
    alive = term.alive
    return f"Terminal alive: {alive}\nCurrent directory: {cwd}"


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
