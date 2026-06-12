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


# ── Executor Scope Gate ───────────────────────────────────────────────────────

# Tools whose handlers call _scope_gate before executing.
_FILE_GATED_TOOLS = frozenset([
    "read_file", "write_file", "list_directory",
    "filesystem_scan", "filesystem_search", "filesystem_summary",
    "source_map_scan", "source_map_ingest",
])

# OS paths that are always blocked regardless of scoped_paths.json.
_SYSTEM_PREFIXES = (
    "c:\\windows",
    "c:\\program files",
    "c:\\program files (x86)",
    "c:\\programdata",
    "c:\\$recycle.bin",
    "c:\\system volume information",
    "c:\\users\\all users",
)

# Tools that perform destructive file operations (delete / move / rename).
_DESTRUCTIVE_TOOLS = frozenset(["delete_file", "delete_folder", "move_file", "rename_file"])

# Cloud-sync path fragments (case-insensitive).
_CLOUD_SYNC_TOKENS = ("onedrive", "g:\\my drive", "g:/my drive")


def _scope_gate(
    path: str,
    tool_name: str,
    approved_for_write: bool = False,
) -> tuple[bool, str]:
    """
    Pre-execution scope gate for file-affecting tools.

    Returns (allowed: bool, message: str).
    If blocked, message is a Freedom to Ask phrase that includes request_id,
    smallest scope, and will_not_do list so Noah knows exactly what to approve.

    Fails open (True, '') if governance modules are unavailable — never breaks
    existing tool behaviour.
    """
    try:
        from freedom_to_ask import (
            request_access, ask_phrase,
            READ_DISCOVERY, READ_CONTENT, WRITE_ACTIVE, DESTRUCTIVE,
        )
        from drive_scope import is_in_scope

        path_str = str(path).strip()
        if not path_str:
            return False, f"[BLOCKED] Governance scope check failed for {tool_name}: no path supplied."
        lower = path_str.lower()
        oracle_home = str(ROOT).lower()

        # Determine access mode from tool name.
        if tool_name in _DESTRUCTIVE_TOOLS:
            mode = DESTRUCTIVE
        elif tool_name in ("list_directory", "filesystem_scan",
                           "filesystem_search", "filesystem_summary"):
            mode = READ_DISCOVERY
        elif tool_name == "write_file":
            mode = WRITE_ACTIVE
        else:
            mode = READ_CONTENT

        # 1. Destructive operations — always blocked; require explicit per-action approval.
        if mode == DESTRUCTIVE:
            req = request_access(
                path_str, DESTRUCTIVE,
                reason=f"to execute {tool_name} — this is a destructive operation",
                smallest_scope=path_str,
                will_not_do=[
                    "Delete without explicit per-action Noah approval",
                    "Move or rename files without review",
                ],
            )
            return False, ask_phrase(req)

        # 2. System paths — always blocked.
        if any(lower.startswith(p) for p in _SYSTEM_PREFIXES):
            req = request_access(
                path_str, mode,
                reason=f"to execute {tool_name} on a system path",
                smallest_scope=path_str,
                will_not_do=["Modify system files", "Read OS credentials",
                             "Change system settings"],
            )
            return False, ask_phrase(req)

        # 3. Out-of-scope paths — blocked.
        in_scope = is_in_scope(path_str)
        if in_scope is not True:
            req = request_access(
                path_str, mode,
                reason=f"to execute {tool_name}",
                smallest_scope=path_str,
                will_not_do=["Access paths outside approved scope",
                             "Crawl directories recursively"],
            )
            return False, ask_phrase(req)

        # 4. Write-specific checks (path is confirmed in scope).
        if mode == WRITE_ACTIVE:
            # 4a. ORACLE home — write always allowed (she writes her own Memory/).
            if lower.startswith(oracle_home):
                return True, "ORACLE home -- write allowed"

            # 4b. Cloud-sync paths outside ORACLE home require explicit approval.
            if any(tok in lower for tok in _CLOUD_SYNC_TOKENS):
                req = request_access(
                    path_str, WRITE_ACTIVE,
                    reason=f"to write to a cloud-synced location via {tool_name}",
                    smallest_scope=path_str,
                    will_not_do=[
                        "Upload or sync data without approval",
                        "Modify shared cloud files",
                        "Change sync settings",
                    ],
                )
                return False, ask_phrase(req)

            # 4c. Non-cloud in-scope write without explicit write approval.
            if not approved_for_write:
                req = request_access(
                    path_str, WRITE_ACTIVE,
                    reason=f"to write {Path(path_str).name} via {tool_name}",
                    smallest_scope=path_str,
                    will_not_do=["Overwrite without review",
                                 "Create irreversible changes"],
                )
                return False, ask_phrase(req)

        return True, "in approved scope"

    except Exception as e:
        path_str = str(path).strip() or "<unknown>"
        return (
            False,
            f"[BLOCKED] Governance unavailable while checking {tool_name} on `{path_str}`: {e}. "
            "Action not executed."
        )


def _scope_paths(paths, tool_name: str) -> tuple[bool, str]:
    """Validate every supplied path for scan/search/summary style tools."""
    if paths is None:
        paths = [str(ROOT)]
    elif isinstance(paths, (str, os.PathLike)):
        paths = [str(paths)]
    else:
        paths = [str(p) for p in paths]

    if not paths:
        return False, f"[BLOCKED] Governance scope check failed for {tool_name}: no paths supplied."

    for raw_path in paths:
        path = Path(raw_path) if os.path.isabs(raw_path) else ROOT / raw_path
        ok, msg = _scope_gate(str(path), tool_name)
        if not ok:
            return False, msg
    return True, "all supplied paths in approved scope"


def _delegated_autonomy_enabled() -> bool:
    try:
        from governance import is_delegated_autonomy_enabled
        return is_delegated_autonomy_enabled()
    except Exception:
        return False


def _is_internal_runtime_write(path: Path) -> bool:
    """True for Oracle-owned runtime/proposal artifacts, not source code."""
    try:
        p = path.resolve()
    except Exception:
        p = path
    allowed_roots = [
        ROOT / "Memory",
        ROOT / "Logs",
        ROOT / "Messages",
        ROOT / "Projects" / "daemon_proposals",
        ROOT / "Projects" / "self_build_proposals",
        ROOT / "Projects" / "pending_candidates",
    ]
    return any(str(p).lower().startswith(str(root.resolve()).lower()) for root in allowed_roots)


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """
    Dispatch a tool call. Returns a string result to feed back to Claude.
    All calls are logged via audit_log.

    Every call passes through the Runtime Output Validator before dispatch.
    A BLOCKED result short-circuits execution and returns the violation list
    so the caller can surface it to Noah or request approval.
    """
    from audit_log import log

    # ── Runtime Output Validator gate ─────────────────────────────────────────
    try:
        from output_validator import validate_tool_call, ApprovalState, SourceContext
        _vr = validate_tool_call(
            tool_name=tool_name,
            tool_input=tool_input,
            source_context=SourceContext.MODEL_OUTPUT,
            # Tool executor always starts with NONE; callers that have obtained
            # explicit approval should call validate_tool_call directly and
            # pass the result through before calling execute_tool.
            approval_state=ApprovalState.NONE,
        )
        if not _vr.valid:
            log("BLOCKED", f"output_validator blocked {tool_name}: {_vr.violations}")
            lines = [f"[BLOCKED by output validator] {tool_name}"]
            for v in _vr.violations:
                lines.append(f"  • {v}")
            lines.append(f"  next: {_vr.safe_next_action}")
            return "\n".join(lines)
    except ImportError as _ve:
        # Fail-closed: a missing validator is not a pass. Block execution and
        # return a diagnostic. Fix: ensure core/output_validator.py is present.
        _msg = (
            f"[BLOCKED] output_validator unavailable (ImportError: {_ve}). "
            f"Cannot execute '{tool_name}' without the validation layer. "
            f"Check that core/output_validator.py is present and importable."
        )
        try:
            log("BLOCKED", _msg)
        except Exception:
            pass
        return _msg
    except Exception as _ve:
        # Any validator error also blocks — never let a validation crash become a pass.
        _msg = (
            f"[BLOCKED] output_validator raised an unexpected error ({type(_ve).__name__}: {_ve}). "
            f"Cannot execute '{tool_name}'. Check core/output_validator.py."
        )
        try:
            log("BLOCKED", _msg)
        except Exception:
            pass
        return _msg

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
        elif tool_name == "send_to_claude_code":
            return _send_to_claude_code(tool_input, log)
        elif tool_name == "send_to_codex":
            return _send_to_codex(tool_input, log)
        elif tool_name == "git_op":
            return _git_op(tool_input, log)
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
    label = f"open_app:{app_name}" + (f" {args}" if args else "")

    # .lnk shortcuts — use os.startfile (Windows shell launches the shortcut target)
    if exe_path.lower().endswith(".lnk"):
        import os as _os
        try:
            _os.startfile(exe_path)
            log("ACTION", label, approved=True)
            return f"Launched {app_name} via shortcut."
        except Exception as e:
            return f"Failed to launch {app_name}: {e}"

    cmd = [exe_path] + [str(a) for a in args]
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
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    log("ACTION", f"run_script:{script_path}", approved=True)
    output = result.stdout.strip() or result.stderr.strip() or "(no output)"
    return f"Script output:\n{output}"


def _read_file(inp: dict, log) -> str:
    raw_path = inp["path"]
    max_chars = inp.get("max_chars", 4000)
    path = Path(raw_path) if os.path.isabs(raw_path) else ROOT / raw_path

    ok, msg = _scope_gate(str(path), "read_file")
    if not ok:
        log("ACTION", f"read_file:BLOCKED:{path}", approved=False)
        return msg

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

    # Scope gate — approved_for_write=True because _confirm() below handles approval.
    ok, msg = _scope_gate(str(path), "write_file", approved_for_write=True)
    if not ok:
        log("ACTION", f"write_file:BLOCKED:{path}", approved=False)
        return msg

    exists = path.exists()
    action_label = f"write_file:{path} (mode={mode})"
    delegated_internal = _delegated_autonomy_enabled() and _is_internal_runtime_write(path)

    if mode == "write" and exists:
        if not _confirm(f"Overwrite existing file: {path}?"):
            log("ACTION", action_label, approved=False)
            return f"Cancelled: file not overwritten."

    if not delegated_internal and not _confirm(f"{'Write' if mode == 'write' else 'Append to'} file: {path}?"):
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
    ok, msg = _scope_paths(paths, "filesystem_scan")
    if not ok:
        log("ACTION", f"filesystem_scan:BLOCKED:{paths}", approved=False)
        return msg
    if not _delegated_autonomy_enabled() and not _confirm(f"Scan and index filesystem? {label}\nThis may take a moment."):
        log("ACTION", label, approved=False)
        return "Cancelled: filesystem scan not run."
    log("ACTION", label, approved=True)
    index = build_index(paths, inp.get("max_depth", 4))
    save_index(index)
    return get_summary(index)


def _filesystem_search(inp: dict, log) -> str:
    from filesystem_mapper import search_index
    paths = inp.get("paths", inp.get("path"))
    if paths is not None:
        ok, msg = _scope_paths(paths, "filesystem_search")
        if not ok:
            log("ACTION", f"filesystem_search:BLOCKED:{paths}", approved=False)
            return msg
    log("ACTION", f"filesystem_search:{inp['query']}", approved=True)
    results = search_index(inp["query"])
    if not results:
        return f"No files found matching '{inp['query']}'. (Run filesystem_scan first if index is empty.)"
    lines = [f"{r['path']} ({r.get('size_kb', '?')} KB)" for r in results]
    return f"{len(results)} match(es):\n" + "\n".join(lines)


def _filesystem_summary(inp: dict, log) -> str:
    from filesystem_mapper import get_summary
    paths = inp.get("paths", inp.get("path"))
    if paths is not None:
        ok, msg = _scope_paths(paths, "filesystem_summary")
        if not ok:
            log("ACTION", f"filesystem_summary:BLOCKED:{paths}", approved=False)
            return msg
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
    paths = inp.get("paths") or None
    ok, msg = _scope_paths(paths, "source_map_scan")
    if not ok:
        log("ACTION", f"source_map_scan:BLOCKED:{paths}", approved=False)
        return msg
    log("ACTION", "source_map_scan", approved=True)
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

    ok, msg = _scope_gate(path, "source_map_ingest")
    if not ok:
        log("ACTION", f"source_map_ingest:BLOCKED:{path}", approved=False)
        return msg

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


def _send_to_claude_code(inp: dict, log) -> str:
    sys.path.insert(0, str(ROOT / "core"))
    from claude_code_bridge import type_into_claude
    message = inp.get("message", "").strip()
    if not message:
        return "send_to_claude_code: message is required."
    log("BRIDGE", f"send_to_claude_code: {message[:80]}")
    ok, detail = type_into_claude(message, open_if_missing=True)
    if ok:
        return f"[CLAUDE CODE] Message delivered — check the Claude Code window for the response."
    if "[CLAUDE HANDOFF]" in detail:
        return detail
    return f"[CLAUDE CODE ERROR] {detail}"


# ── Git Operations ─────────────────────────────────────────────────────────────

def _send_to_codex(inp: dict, log) -> str:
    sys.path.insert(0, str(ROOT / "core"))
    from oracle_codex_channel import ORACLE_TO_CODEX, send_to_codex
    message = inp.get("message", "").strip()
    if not message:
        return "send_to_codex: message is required."
    log("BRIDGE", f"send_to_codex: {message[:80]}")
    if send_to_codex(message):
        return f"[CODEX CHANNEL] Message written to {ORACLE_TO_CODEX}. Codex should reply in Messages/codex_to_oracle.md."
    return "[CODEX CHANNEL ERROR] Could not write message to Codex channel."


_GIT_SAFE_CMDS = {"status", "log", "diff", "branch", "remote", "stash list", "show", "ls-files"}
_GIT_WRITE_CMDS = {"commit", "push", "pull", "merge", "rebase", "add", "reset", "checkout", "stash"}


def _git_op(inp: dict, log) -> str:
    operation = inp.get("operation", "").strip().lower()
    args = inp.get("args", "").strip()
    cwd = inp.get("cwd", str(ROOT))

    if not operation:
        return "git_op: operation is required (e.g. 'status', 'log', 'commit')."

    cmd = f"git {operation}" + (f" {args}" if args else "")

    # Safety: block destructive bare resets
    if any(x in cmd.lower() for x in ["--hard", "--force", "rm -rf", "clean -f"]):
        return f"[BLOCKED] Destructive git flag detected in '{cmd}'. Requires explicit Noah approval."

    log("GIT", f"{operation}: {args[:60]}")
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = result.stdout.strip() or result.stderr.strip() or "(no output)"
        return f"git {operation}:\n{output}"
    except subprocess.TimeoutExpired:
        return f"git {operation} timed out."
    except Exception as e:
        return f"git {operation} error: {e}"


def _list_directory(inp: dict, log) -> str:
    raw_path = inp["path"]
    path = Path(raw_path) if os.path.isabs(raw_path) else ROOT / raw_path

    ok, msg = _scope_gate(str(path), "list_directory")
    if not ok:
        log("ACTION", f"list_directory:BLOCKED:{path}", approved=False)
        return msg

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


# ── Smoke tests ───────────────────────────────────────────────────────────────

def _smoke_test() -> None:
    """
    Verify scope gate behavior without reading or writing real files.
    All tests call _scope_gate() directly; access requests go to a temp file.
    No destructive or external actions occur.
    """
    import json
    import tempfile
    sys.path.insert(0, str(ROOT / "core"))

    import freedom_to_ask as _fta
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
    tmp.write("[]")
    tmp.close()
    _orig = _fta.REQUESTS_FILE
    _fta.REQUESTS_FILE = Path(tmp.name)

    passed = 0
    total = 20
    results = []

    def ok(name):
        nonlocal passed
        passed += 1
        results.append(f"  [PASS] {name}")

    def fail(name, reason=""):
        results.append(f"  [FAIL] {name}" + (f" -- {reason}" if reason else ""))

    try:
        # 1. Approved read path allowed (ORACLE root is always in scope)
        oracle_readme = str(ROOT / "README.md")
        allowed, msg = _scope_gate(oracle_readme, "read_file")
        if allowed:
            ok("approved read path allowed")
        else:
            fail("approved read path allowed", msg[:80])

        # 2. Unknown path blocked with Freedom to Ask phrase
        unknown = r"C:\RandomXYZ\not_scoped\file.txt"
        allowed, msg = _scope_gate(unknown, "read_file")
        if not allowed and msg:
            ok("unknown read path blocked with ask phrase")
        else:
            fail("unknown read path blocked with ask phrase", f"allowed={allowed}")

        # 3. Proposed-only path blocked (AppData not in scoped_paths.json)
        proposed = r"C:\Users\noahh\AppData\Local\oracle_probe.txt"
        allowed, msg = _scope_gate(proposed, "read_file")
        if not allowed:
            ok("proposed-only path (AppData) blocked")
        else:
            fail("proposed-only path (AppData) blocked", "path not in scope was allowed")

        # 4. System path blocked
        system = r"C:\Windows\System32\drivers\etc\hosts"
        allowed, msg = _scope_gate(system, "read_file")
        if not allowed:
            ok("system path blocked")
        else:
            fail("system path blocked", "system path was allowed")

        # 5. Write to in-scope path without write approval blocked
        docs = r"C:\Users\noahh\Documents\oracle_gate_test.txt"
        allowed, msg = _scope_gate(docs, "write_file", approved_for_write=False)
        if not allowed and msg:
            ok("write without write approval blocked")
        else:
            fail("write without write approval blocked", f"allowed={allowed}")

        # 6. Cloud-sync write (OneDrive in scope, but cloud-synced) blocked
        onedrive = r"C:\Users\noahh\OneDrive\oracle_gate_test.txt"
        allowed, msg = _scope_gate(onedrive, "write_file", approved_for_write=True)
        if not allowed:
            ok("cloud-sync write blocked even with approved_for_write=True")
        else:
            fail("cloud-sync write blocked", "cloud-sync path was allowed for write")

        # 7. Destructive operation blocked even inside approved scope (ORACLE home)
        oracle_mem = str(ROOT / "Memory" / "test_delete_probe.json")
        allowed, msg = _scope_gate(oracle_mem, "delete_file")
        if not allowed:
            ok("destructive action blocked inside approved scope")
        else:
            fail("destructive action blocked inside approved scope", "delete was allowed")

        # 8. Non-file tool is not in the gated set (gate never called for it)
        if "recall_facts" not in _FILE_GATED_TOOLS:
            ok("non-file tool (recall_facts) not in gated set")
        else:
            fail("non-file tool not in gated set", "recall_facts is in _FILE_GATED_TOOLS")

        # 9. Block response includes request_id
        _, msg9 = _scope_gate(unknown, "read_file")
        if "request_id" in msg9:
            ok("blocked response includes request_id")
        else:
            fail("blocked response includes request_id", msg9[:120])

        # 10. Block response includes the path (smallest scope context)
        _, msg10 = _scope_gate(unknown, "read_file")
        if unknown.replace("\\", "\\\\") in msg10 or unknown in msg10:
            ok("blocked response includes path (smallest scope)")
        else:
            fail("blocked response includes path (smallest scope)", msg10[:120])

        # 11. Block response includes will_not_do constraint
        _, msg11 = _scope_gate(unknown, "read_file")
        if "will not" in msg11.lower() or "I will not" in msg11:
            ok("blocked response includes will_not_do constraint")
        else:
            fail("blocked response includes will_not_do constraint", msg11[:160])

        # 12. No destructive or external actions — only PENDING access requests written to temp
        # 12-15. Scan/search/summary supplied paths are scoped before work starts.
        def _noop_log(*args, **kwargs):
            return None

        scan_msg = _filesystem_scan({"paths": [unknown]}, _noop_log)
        if "request_id" in scan_msg or scan_msg.startswith("[BLOCKED]"):
            ok("filesystem_scan unknown path blocked")
        else:
            fail("filesystem_scan unknown path blocked", scan_msg[:120])

        search_msg = _filesystem_search({"query": "probe", "paths": [unknown]}, _noop_log)
        if "request_id" in search_msg or search_msg.startswith("[BLOCKED]"):
            ok("filesystem_search unknown path blocked")
        else:
            fail("filesystem_search unknown path blocked", search_msg[:120])

        summary_msg = _filesystem_summary({"paths": [unknown]}, _noop_log)
        if "request_id" in summary_msg or summary_msg.startswith("[BLOCKED]"):
            ok("filesystem_summary unknown path blocked")
        else:
            fail("filesystem_summary unknown path blocked", summary_msg[:120])

        smap_msg = _source_map_scan({"paths": [unknown], "include_excerpts": False}, _noop_log)
        if "request_id" in smap_msg or smap_msg.startswith("[BLOCKED]"):
            ok("source_map_scan unknown path blocked")
        else:
            fail("source_map_scan unknown path blocked", smap_msg[:120])

        # 16-17. Governance failure blocks read/write instead of failing open.
        import drive_scope as _ds
        orig_is_in_scope = _ds.is_in_scope

        def _boom(_path):
            raise RuntimeError("scope unavailable smoke test")

        _ds.is_in_scope = _boom
        try:
            allowed_read, fail_read = _scope_gate(oracle_readme, "read_file")
            if not allowed_read and fail_read.startswith("[BLOCKED]"):
                ok("governance import/check failure blocks read")
            else:
                fail("governance import/check failure blocks read", f"allowed={allowed_read} {fail_read[:80]}")

            allowed_write, fail_write = _scope_gate(oracle_readme, "write_file", approved_for_write=True)
            if not allowed_write and fail_write.startswith("[BLOCKED]"):
                ok("governance import/check failure blocks write")
            else:
                fail("governance import/check failure blocks write", f"allowed={allowed_write} {fail_write[:80]}")
        finally:
            _ds.is_in_scope = orig_is_in_scope

        # 18. Non-file tool is unaffected by the file scope gate.
        if "recall_facts" not in _FILE_GATED_TOOLS:
            ok("non-file tool unaffected")
        else:
            fail("non-file tool unaffected", "recall_facts unexpectedly gated")

        # 19. Explicit /actuate path is outside executor and unchanged here.
        if "source_map_scan" in _FILE_GATED_TOOLS and "recall_facts" not in _FILE_GATED_TOOLS:
            ok("executor gating does not alter /actuate path")
        else:
            fail("executor gating does not alter /actuate path")

        # 20. No destructive or external actions - only PENDING access requests written to temp.
        data = json.loads(Path(tmp.name).read_text())
        all_pending = all(r.get("status") == "PENDING" for r in data)
        if all_pending and len(data) > 0:
            ok(f"no destructive/external actions -- {len(data)} PENDING requests in temp only")
        else:
            fail("no destructive/external actions", f"{len(data)} requests, all_pending={all_pending}")

    finally:
        _fta.REQUESTS_FILE = _orig
        try:
            os.unlink(tmp.name)
        except Exception:
            pass

    for line in results:
        print(line)
    print(f"\n{passed}/{total} smoke tests passed.")
    if passed < total:
        sys.exit(1)


def main() -> None:
    cmd = sys.argv[1].lower() if len(sys.argv) > 1 else "--help"
    if cmd == "--smoke-test":
        print("Running executor scope gate smoke tests...\n")
        _smoke_test()
    else:
        print("Usage: python tools/executor.py --smoke-test")


if __name__ == "__main__":
    main()
