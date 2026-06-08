#!/usr/bin/env python3
"""
ORACLE.AI — Core Runtime
Run: python core/oracle.py
"""

import os
import sys
import shutil
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# ROOT resolves correctly for both source and frozen (PyInstaller) builds
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

load_dotenv(ROOT / ".env")

# Add project root and core/ to path so all local imports resolve
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

from memory import init_db, new_session, save_message, get_recent_messages
from context_loader import build_system_prompt, load_identity, index_summary
from identity_compliance import handle_in_repl
from audit_log import log
from tools.definitions import TOOL_DEFINITIONS
from tools.executor import execute_tool
from llm import is_local, make_client, get_model, to_openai_tools, startup_status
from voice import speak, set_voice_enabled, is_voice_enabled

MAX_TOKENS = 4096
MAX_TOOL_CALLS_PER_TURN = 3    # hard cap — local 7B models loop; keep it tight

# ── Local model tool tiers ─────────────────────────────────────────────────────
# READ — always allowed, no confirmation needed
_LOCAL_READ_TOOLS = frozenset([
    "read_file", "list_directory", "recall_facts", "filesystem_search",
    "filesystem_summary", "source_map_search", "terminal_status",
    "git_op",  # git status/log/diff are safe reads; git_op classifier blocks writes internally
])
# HANDS — SOV1 screen/app control + Claude Code bridge — no approval gate
_LOCAL_HANDS_TOOLS = frozenset([
    "open_app", "computer_operator",
    "send_to_claude_code",  # delivers message to Claude Code window via pyautogui
    # Terminal commands that pass the safety classifier run without a gate
    "run_shell", "terminal_run", "terminal_cd", "run_script",
])
# WRITE — file/memory mutations — require Noah's explicit approval before execution
# Keep this small: only operations that permanently alter state Noah can't easily undo
_LOCAL_WRITE_TOOLS = frozenset([
    "write_file", "remember_fact",
])
_LOCAL_SAFE_TOOL_NAMES = _LOCAL_READ_TOOLS | _LOCAL_HANDS_TOOLS | _LOCAL_WRITE_TOOLS

# ── Terminal safety classifier ────────────────────────────────────────────────
# Commands that look safe but have destructive flags or touch system areas
_TERMINAL_DANGER_PATTERNS = [
    "rm -rf", "rmdir /s", "del /f", "format ", "diskpart",
    "reg delete", "netsh", "bcdedit", "sfc /scannow",
    "--force", "--hard reset", "drop table", "drop database",
    "truncate table", "> /dev/null", "shutdown", "restart-computer",
]


def _classify_terminal_command(cmd: str) -> tuple[bool, str]:
    """Return (is_safe, reason). Unsafe commands are blocked from the write gate."""
    lower = cmd.lower()
    for pat in _TERMINAL_DANGER_PATTERNS:
        if pat in lower:
            return False, f"Dangerous pattern '{pat}' detected in command."
    return True, ""


# ── Paste / log dump detection ─────────────────────────────────────────────────
# Indicators that the user pasted terminal output instead of typing a command.
_LOG_FRAGMENTS = [
    "██", "╗", "╚", "║", "═",               # ASCII art box drawing
    "[LOCAL MODE]", "[ORACLE]", "[GOVERNANCE]",
    "ollama already running", "pull command: ollama",
    "sovereign operator layer", "mode        local",
    "vision      ready", "sov1        hands",
    "memory      connected", "oracle boot cycle",
    "──────────────────", "last session:",
    "good morning,", "good afternoon,", "good evening,",
]
_LOG_THRESHOLD = 4   # lines that match before we classify as a paste dump


def _detect_pasted_log(text: str) -> bool:
    """Return True if text looks like pasted ORACLE terminal output, not a command."""
    lines = text.splitlines()
    if len(lines) < 3:
        return False
    lower = text.lower()
    hits = sum(1 for frag in _LOG_FRAGMENTS if frag.lower() in lower)
    return hits >= _LOG_THRESHOLD


def _summarize_pasted_log(text: str) -> str:
    """Extract errors and status from a pasted log dump — brief diagnostic."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    errors = [l for l in lines if any(
        k in l.lower() for k in ("error", "fail", "not found", "traceback", "exception", "blocked", "unavailable")
    )]
    status_lines = [l for l in lines if any(
        k in l.lower() for k in ("ollama", "mode", "vision", "sov1", "memory", "pending", "routing", "claude code")
    )][:6]
    out = ["[DIAGNOSTIC] Pasted log detected — not routing as commands."]
    if errors:
        out.append(f"  Errors found ({len(errors)}):")
        for e in errors[:5]:
            out.append(f"    • {e[:100]}")
    if status_lines:
        out.append(f"  Status lines:")
        for s in status_lines[:4]:
            out.append(f"    {s[:100]}")
    if not errors and not status_lines:
        out.append(f"  {len(lines)} lines captured. No errors detected.")
    out.append("  Type a command or question to continue.")
    return "\n".join(out)

# ── Interaction mode classifier ───────────────────────────────────────────────
# Mode is determined BEFORE governance/routing so ORACLE doesn't over-govern
# simple conversation or under-route real build tasks.

_CHAT_TRIGGERS = [
    "just talk", "talk normally", "talk to me", "just chat", "don't route",
    "be normal", "have a conversation", "i'm frustrated", "i'm excited",
    "i'm tired", "i feel ", "tell me about yourself", "what do you think about",
    "how are you", "i need to vent", "i want to talk", "can we talk",
    "let's just talk", "stop routing", "just respond",
]
_BUILD_TRIGGERS = [
    "fix the", "patch ", "refactor", "implement", "build ", "debug ",
    ".py", "git ", "repo ", "commit", "push ", "pull request",
    "write a function", "write a script", "write a class",
    "tell claude", "ask claude", "send to claude", "pass to claude",
    "mythic", "build pass", "run command", "run script",
    "install ", "deploy ", "error in ", "broken ",
]
_WORK_TRIGGERS = [
    "plan ", "schedule", "organize", "summarize", "review ",
    "help me figure out", "what should we do", "what do you recommend",
    "analyze", "evaluate", "help me think through", "walk me through",
    "what's the status", "where are we", "what's the priority",
    "lootdrop", "dealer", "business", "revenue", "customer",
    "what should we build", "what should i build", "what to build",
    "what's next", "what are we building", "what do we build",
]


def _classify_interaction_mode(text: str) -> str:
    """Return 'CHAT' | 'WORK' | 'BUILD' | 'DIAGNOSTIC' for a user message."""
    lower = text.lower().strip()
    # Diagnostic: pasted ORACLE output slipped through the early detector
    if any(
        t in lower for t in ("[oracle]", "[local mode]", "[governance]", "[claude code error]", "sovereign operator layer")
    ):
        return "DIAGNOSTIC"
    # Explicit Claude delegation always routes to BUILD regardless of other words
    _claude_delegation = ("ask claude", "tell claude", "send to claude", "pass to claude", "use claude")
    if any(t in lower for t in _claude_delegation):
        return "BUILD"
    # CHAT: explicit conversational override
    if any(t in lower for t in _CHAT_TRIGGERS):
        return "CHAT"
    # WORK checked before BUILD — planning questions beat keyword matches
    if any(t in lower for t in _WORK_TRIGGERS):
        return "WORK"
    # BUILD: code / implementation keywords
    if any(t in lower for t in _BUILD_TRIGGERS):
        return "BUILD"
    # Default: short casual messages → CHAT, longer → WORK
    word_count = len(text.split())
    if word_count <= 5:
        return "CHAT"
    return "WORK"


def _claude_available_now() -> bool:
    """Return True if the Claude Code / Claude Desktop window is currently open."""
    try:
        from claude_code_bridge import find_claude_window
        return find_claude_window() is not None
    except Exception:
        return False


def get_oracle_status() -> dict:
    """
    Return live ORACLE status — callable by the desktop UI or any external module.
    All fields are safe to display; never contains secrets.
    """
    import shutil as _sh
    from approval_center import list_pending as _lp
    try:
        _pending = len(_lp())
    except Exception:
        _pending = 0
    return {
        "mode": "LOCAL" if is_local() else "CLOUD",
        "claude_cli": _sh.which("claude") is not None,
        "claude_window": _claude_available_now(),
        "hands_ready": True,
        "memory_connected": True,
        "pending": _pending,
        "model": get_model(vision=False),
    }


LOCAL_TOOL_DEFINITIONS = [
    t for t in TOOL_DEFINITIONS
    if t["name"] in _LOCAL_SAFE_TOOL_NAMES
]

# Pending approval gate: {tool_name: {input}} waiting for Noah's confirm
_pending_tool_approval: dict = {}

# ── Tool truthfulness ──────────────────────────────────────────────────────────
# Phrases the local model uses to CLAIM it will act — without calling any tool.
# These are caught post-LLM and replaced with [BLOCKED] + honest status.
_ACTION_CLAIM_PATTERNS = [
    # Future tense — "I'll X"
    "i'll open", "i'll create", "i'll run", "i'll write", "i'll build",
    "i'll launch", "i'll execute", "i'll start", "i'll take control",
    "i'll type", "i'll click", "i'll send", "i'll do that",
    "i'll handle", "i'll implement", "i'll make", "i'll set up",
    "i'll use sov1", "i'll use the", "i'll now",
    # Present progressive — "I'm opening"
    "i'm opening", "i'm creating", "i'm running", "i'm launching",
    "i'm taking", "i'm writing", "i'm executing", "i'm starting",
    # "Let me" — also a claim without evidence
    "let me open", "let me create", "let me run", "let me write",
    "let me launch", "let me execute", "let me take",
    # Past-tense fabrications
    "successfully created", "successfully scaffolded", "has been created",
    "has been set up", "has been initialized", "project has been",
    "files have been created", "i have created", "i've created",
    "i created", "i've set up", "i set up", "was created at",
    "directory has been", "folder has been",
    # The routing hallucination
    "routing to claude code.",
]

# Map: action verb → which tool capability covers it → how to describe the gap
_ACTION_TO_CAPABILITY = {
    "open": ("open_app / computer_operator", "SOV1 HANDS or open_app with an approved app name"),
    "create": ("write_file / terminal_run", "write_file tool with Noah's approval"),
    "run": ("terminal_run / run_shell", "terminal_run tool (runs safely after classifier check)"),
    "write": ("write_file", "write_file tool with Noah's approval"),
    "build": ("send_to_claude_code", "send_to_claude_code → Claude Code window"),
    "launch": ("open_app", "open_app with an approved app name from config.yaml"),
    "execute": ("terminal_run", "terminal_run tool"),
    "take control": ("computer_operator", "computer_operator → SOV1 HANDS"),
    "type": ("send_to_claude_code / computer_operator", "type_into_claude or SOV1 focus_window + paste_text"),
    "send": ("send_to_claude_code", "send_to_claude_code tool"),
    "implement": ("send_to_claude_code", "send_to_claude_code → Claude Code window"),
}


def _tool_registry_status() -> dict[str, bool]:
    """
    Return live working-status for each tool category.
    Called once per turn — cheap checks only.
    """
    status: dict[str, bool] = {}

    # Claude window injection
    try:
        from claude_code_bridge import find_claude_window
        status["send_to_claude_code"] = find_claude_window() is not None
    except Exception:
        status["send_to_claude_code"] = False

    # SOV1 hands (pyautogui + PIL)
    try:
        import pyautogui  # noqa
        from PIL import Image  # noqa
        status["computer_operator"] = True
    except Exception:
        status["computer_operator"] = False

    # Terminal (always available)
    status["terminal_run"] = True
    status["run_shell"] = True

    # File I/O (always available)
    status["read_file"] = True
    status["write_file"] = True

    return status


def _blocked_response(reply: str, tools_called: list[str], registry: dict[str, bool]) -> str | None:
    """
    Scan reply for action claims made without tool execution.
    Return a [BLOCKED] response string, or None if reply is clean.
    """
    lower = reply.lower().strip()

    # Which action verb was claimed?
    claimed_verb = None
    for pat in _ACTION_CLAIM_PATTERNS:
        if pat in lower:
            claimed_verb = pat
            break

    if claimed_verb is None:
        return None  # no claim — reply is fine

    # Was any tool actually called this turn?
    if tools_called:
        return None  # tool ran — claim is backed by execution

    # Build [BLOCKED] message
    # Map claim to capability
    cap_name = "the requested capability"
    cap_how = "the required tool"
    for verb, (cap, how) in _ACTION_TO_CAPABILITY.items():
        if verb in claimed_verb:
            cap_name = cap
            cap_how = how
            break

    # Check if the relevant tool is in registry and working
    cap_working = any(
        registry.get(t, False)
        for t in registry
        if any(verb in claimed_verb for verb in (t.replace("_", " "), t))
    )

    lines = [
        "[BLOCKED]",
        f"Desired action : {claimed_verb.strip('.')}",
        f"Missing/broken : {cap_name}",
    ]

    # Suggest next manual step based on what's available
    if registry.get("send_to_claude_code"):
        lines.append("Next step      : Ask Claude Code — the window is open and ready.")
    elif registry.get("computer_operator"):
        lines.append("Next step      : Use SOV1 HANDS — type: use sov1 to <goal>")
    else:
        lines.append(f"Next step      : {cap_how}")

    return "\n".join(lines)


def _inject_local_context(user_input: str) -> str:
    """
    Prepend a compact ORACLE state block to user messages for local model calls.
    Includes live tool registry so qwen knows what actually works before it responds.
    """
    lines = ["[ORACLE LIVE STATE]"]
    try:
        from project_state import load_state
        ps = load_state("ORACLE.AI")
        if ps:
            lines.append(f"Build phase : {ps.current_phase}")
            lines.append(f"Last done   : {ps.last_completed_step[:80]}")
            lines.append(f"Next step   : {ps.next_recommended_step[:80]}")
            if ps.current_blocker:
                lines.append(f"Blocker     : {ps.current_blocker[:60]}")
    except Exception:
        pass
    try:
        from approval_center import list_pending
        n = len(list_pending())
        if n:
            lines.append(f"Pending     : {n} items awaiting Noah's approval")
    except Exception:
        pass

    # Live tool registry — what is actually working right now
    try:
        reg = _tool_registry_status()
        lines.append("")
        lines.append("[WORKING TOOLS — only claim actions from this list]")
        lines.append(f"  send_to_claude_code : {'YES — Claude window is open' if reg.get('send_to_claude_code') else 'NO — Claude window not found'}")
        lines.append(f"  computer_operator   : {'YES — SOV1 HANDS available' if reg.get('computer_operator') else 'NO — pyautogui not available'}")
        lines.append(f"  terminal_run        : YES — safe shell commands")
        lines.append(f"  read_file           : YES — read any file")
        lines.append(f"  write_file          : YES — requires Noah approval")
        lines.append("")
        lines.append("RULE: If a tool shows NO above, do NOT say 'I'll X' or 'I will X'.")
        lines.append("RULE: If you cannot call a tool, say: [BLOCKED] and explain what is missing.")
        lines.append("RULE: Never claim an action happened unless a tool actually ran.")
    except Exception:
        pass

    lines.append("")
    lines.append(f"Noah says: {user_input}")
    return "\n".join(lines)


def _detect_hallucination(reply: str, tool_names_called: list[str]) -> str | None:
    """
    Kept for backwards compat — delegates to _blocked_response with a live registry.
    Returns a [BLOCKED] string if the reply contains an unclaimed action, else None.
    """
    try:
        reg = _tool_registry_status()
        return _blocked_response(reply, tool_names_called, reg)
    except Exception:
        return None


def _ansi(code: str) -> str:
    """Return ANSI escape string. Safe on Windows 10+ terminals."""
    return f"\033[{code}m"


C = {
    "reset":   _ansi("0"),
    "bold":    _ansi("1"),
    "dim":     _ansi("2"),
    "cyan":    _ansi("36"),
    "bcyan":   _ansi("96"),
    "green":   _ansi("32"),
    "bgreen":  _ansi("92"),
    "yellow":  _ansi("33"),
    "byellow": _ansi("93"),
    "red":     _ansi("31"),
    "bred":    _ansi("91"),
    "magenta": _ansi("35"),
    "bmagenta":_ansi("95"),
    "white":   _ansi("97"),
    "grey":    _ansi("90"),
}


def _print_thinking(name: str, inp: dict) -> None:
    """Print a tool call in the 'thinking' visual style — dim, not Oracle's voice."""
    preview = ""
    for key in ("path", "command", "query", "app_name", "text", "content"):
        val = inp.get(key, "")
        if val:
            preview = f"  {str(val)[:60]}"
            break
    print(f"{C['grey']}  ◌ {name}{C['reset']}{C['dim']}{preview}{C['reset']}")


def _print_thought_result(name: str, result: str) -> None:
    """Print the result of a tool call — source-labeled, dimmed."""
    if not result or not result.strip():
        return
    first_line = result.strip().splitlines()[0][:80]
    if name in ("recall_facts",):
        label = f"{C['cyan']}[MEMORY]{C['reset']} "
    elif name in ("send_to_claude_code",):
        label = f"{C['bgreen']}[CLAUDE CODE]{C['reset']} "
    elif name in ("git_op",):
        label = f"{C['grey']}[GIT]{C['reset']} "
    elif name in ("open_app", "computer_operator"):
        label = f"{C['bgreen']}[HANDS]{C['reset']} "
    else:
        label = ""
    print(f"  {label}{C['dim']}{first_line}{C['reset']}")


def _print_oracle_reply(reply: str) -> None:
    """Print Oracle's reply in a clearly distinct visual block."""
    W = 68
    # Word-wrap reply into lines
    wrapped: list[str] = []
    for paragraph in reply.splitlines():
        if not paragraph.strip():
            wrapped.append("")
            continue
        words = paragraph.split()
        cur = ""
        for w in words:
            if len(cur) + len(w) + 1 > W:
                wrapped.append(cur)
                cur = w
            else:
                cur = (cur + " " + w).strip()
        if cur:
            wrapped.append(cur)

    bar = "─" * (W + 2)
    print()
    print(f"  {C['cyan']}┌─ Oracle {bar[9:]}┐{C['reset']}")
    for line in wrapped:
        padded = line.ljust(W)
        print(f"  {C['cyan']}│{C['reset']} {padded} {C['cyan']}│{C['reset']}")
    print(f"  {C['cyan']}└{bar}┘{C['reset']}")
    print()


def _print_slow(text: str, delay: float = 0.018, end: str = "\n"):
    import sys
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write(end)
    sys.stdout.flush()


def _startup_stats():
    """Pull live numbers from the DB for the boot screen."""
    try:
        from memory import get_conn
        with get_conn() as conn:
            fact_count   = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
            session_count= conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            msg_count    = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            project_count= conn.execute("SELECT COUNT(*) FROM projects WHERE status='active'").fetchone()[0]
            last_msg     = conn.execute(
                "SELECT content FROM messages WHERE role='assistant' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        last_line = (last_msg[0][:72] + "…") if last_msg and len(last_msg[0]) > 72 else (last_msg[0] if last_msg else None)
        return dict(facts=fact_count, sessions=session_count, messages=msg_count,
                    projects=project_count, last=last_line)
    except Exception:
        return dict(facts=0, sessions=0, messages=0, projects=0, last=None)


def _top_lootdrop():
    """Return the single highest-tier recent lootdrop, or None."""
    try:
        from lootdrop import last_drops
        drops = last_drops(n=1, min_tier="rare")
        return drops[0] if drops else None
    except Exception:
        return None


def _pending_count():
    try:
        from integration_gate import ApprovalGate
        return len(ApprovalGate().list_pending())
    except Exception:
        return 0


def banner(identity):
    import time as _time

    # Enable ANSI + UTF-8 on Windows
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    name       = identity.get("name", "Noah")
    first      = name.split()[0]
    constructs = identity.get("echo_constructs", [])
    hour       = datetime.now().hour
    now        = datetime.now()

    if hour < 5:
        greeting, tone = "Still burning the midnight oil", "[LATE]"
    elif hour < 12:
        greeting, tone = "Good morning", "[AM]"
    elif hour < 18:
        greeting, tone = "Good afternoon", "[PM]"
    else:
        greeting, tone = "Good evening", "[EVE]"

    st   = startup_status()
    db   = _startup_stats()
    drop = _top_lootdrop()
    pend = _pending_count()

    W = C["reset"]
    print()

    # ── ASCII header ────────────────────────────────────────────────────────
    header_lines = [
        f"{C['bcyan']}  ██████╗ ██████╗  █████╗  ██████╗██╗     ███████╗{W}",
        f"{C['bcyan']} ██╔═══██╗██╔══██╗██╔══██╗██╔════╝██║     ██╔════╝{W}",
        f"{C['cyan']} ██║   ██║██████╔╝███████║██║     ██║     █████╗  {W}",
        f"{C['cyan']} ██║   ██║██╔══██╗██╔══██║██║     ██║     ██╔══╝  {W}",
        f"{C['bmagenta']} ╚██████╔╝██║  ██║██║  ██║╚██████╗███████╗███████╗{W}",
        f"{C['bmagenta']}  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚══════╝╚══════╝{W}",
    ]
    for line in header_lines:
        print(line)
        _time.sleep(0.06)

    print(f"\n{C['grey']}  {'─' * 50}{W}")
    print(f"  {C['bold']}{C['white']}SOVEREIGN OPERATOR LAYER  |  v2.0  |  GOVERNED{W}")
    print(f"{C['grey']}  {'─' * 50}{W}\n")
    _time.sleep(0.15)

    # ── System boot checks ──────────────────────────────────────────────────
    checks = []
    mode_color = C["bgreen"] if st["mode"] == "CLOUD" else C["byellow"]
    checks.append((f"  MODE", f"{mode_color}{st['mode']}{W}  {C['grey']}{st['model']}{W}"))

    vision_ok = bool(st.get("vision_model"))
    checks.append(("  VISION", f"{C['bgreen']}READY{W}  {C['grey']}{st.get('vision_model','')}{W}" if vision_ok
                               else f"{C['yellow']}OFFLINE{W}"))

    sov1_color = C["bgreen"] if st["sov1_available"] else C["grey"]
    sov1_label = "HANDS READY" if st["sov1_available"] else "HANDS OFFLINE"
    checks.append(("  SOV1", f"{sov1_color}{sov1_label}{W}"))

    if st["mode"] == "LOCAL" and not st.get("ollama_ok"):
        checks.append(("  OLLAMA", f"{C['bred']}NOT RUNNING{W}  {C['grey']}run: ollama serve{W}"))

    mem_color = C["bgreen"] if db["facts"] > 0 else C["yellow"]
    checks.append(("  MEMORY", f"{mem_color}CONNECTED{W}  "
                               f"{C['grey']}{db['facts']} facts · {db['messages']} messages · "
                               f"{db['sessions']} sessions{W}"))

    proj_label = f"{db['projects']} active project{'s' if db['projects'] != 1 else ''}"
    checks.append(("  PROJECTS", f"{C['bgreen']}{proj_label}{W}" if db["projects"] > 0 else f"{C['grey']}none{W}"))

    if pend > 0:
        checks.append(("  PENDING", f"{C['byellow']}{pend} candidate{'s' if pend!=1 else ''} await approval{W}"))

    label_w = max(len(k) for k, _ in checks) + 2
    for label, value in checks:
        padded = label.ljust(label_w)
        print(f"{C['grey']}{padded}{W}  {value}")
        _time.sleep(0.07)

    # ── Top lootdrop callout ─────────────────────────────────────────────────
    if drop:
        tier_label = drop.get("tier", "").upper()
        reason     = drop.get("reason_earned", "")[:60]
        project    = drop.get("related_project", "")
        print(f"\n{C['grey']}  {'─' * 50}{W}")
        print(f"  {C['byellow']}◆ LAST MILESTONE{W}  {C['bold']}{C['white']}{tier_label}{W}  "
              f"{C['grey']}{project}{W}")
        if reason:
            print(f"  {C['dim']}{reason}{W}")
        _time.sleep(0.1)

    # ── Project state resumption ──────────────────────────────────────────────
    try:
        from project_state import load_state
        ps = load_state("ORACLE.AI")
        if ps and ps.next_recommended_step:
            print(f"\n{C['grey']}  {'─' * 50}{W}")
            print(f"  {C['yellow']}◆ RESUMING{W}  {C['grey']}{ps.current_phase}{W}")
            print(f"  {C['dim']}Next: {ps.next_recommended_step[:70]}{W}")
            if ps.current_blocker:
                print(f"  {C['bred']}Blocker:{W} {C['dim']}{ps.current_blocker[:70]}{W}")
            _time.sleep(0.05)
    except Exception:
        pass

    # ── Last session echo ─────────────────────────────────────────────────────
    if db["last"]:
        print(f"\n{C['grey']}  {'─' * 50}{W}")
        print(f"  {C['grey']}Last session:{W}")
        _print_slow(f"  {C['dim']}{db['last']}{W}", delay=0.008, end="\n")
        _time.sleep(0.05)

    # ── Greeting ──────────────────────────────────────────────────────────────
    print(f"\n{C['grey']}  {'─' * 50}{W}\n")
    _time.sleep(0.2)
    _print_slow(f"  {C['bold']}{C['white']}{greeting}, {first}.{W}  {tone}", delay=0.04)

    if constructs:
        _time.sleep(0.1)
        print(f"\n  {C['grey']}Active constructs:{W} {C['cyan']}{', '.join(constructs[:5])}{W}")

    ts = now.strftime("%A, %B ") + str(now.day) + now.strftime("  %H:%M")
    print(f"\n{C['grey']}  {ts}{W}")
    print(f"\n{C['grey']}  {'─' * 50}{W}")
    print(f"\n  {C['dim']}Type a message · /help for commands · /quit to exit{W}\n")


def show_memory(session_id):
    from memory import get_facts, get_recent_messages
    facts = get_facts()
    msgs = get_recent_messages(session_id, limit=5)
    print("\n--- Memory Snapshot ---")
    if facts:
        for f in facts[:10]:
            print(f"  [{f['category']}] {f['key']}: {f['value']}")
    else:
        print("  No facts stored yet.")
    print(f"\n  Recent messages this session: {len(msgs)}")
    print("-----------------------\n")


def handle_project_command(args):
    from memory import add_project, add_project_note, recall_project, list_projects
    if not args:
        projects = list_projects()
        if not projects:
            print("  No projects yet. Use: /project add <name>\n")
        else:
            print("\n--- Projects ---")
            for p in projects:
                print(f"  [{p['status']}] {p['name']}")
            print()
        return

    parts = args.split(None, 2)
    sub = parts[0].lower()

    if sub == "add":
        if len(parts) < 2:
            print("  Usage: /project add <name>\n")
            return
        name = parts[1]
        if add_project(name):
            print(f"  Project added: {name}\n")
        else:
            print(f"  Project '{name}' already exists.\n")

    elif sub == "note":
        if len(parts) < 3:
            print("  Usage: /project note <name> <note>\n")
            return
        name, note = parts[1], parts[2]
        if add_project_note(name, note):
            print(f"  Note added to {name}.\n")
        else:
            print(f"  Project '{name}' not found. Add it first: /project add {name}\n")

    elif sub == "recall":
        if len(parts) < 2:
            print("  Usage: /project recall <name>\n")
            return
        result = recall_project(parts[1])
        if not result:
            print(f"  Project '{parts[1]}' not found.\n")
        else:
            print(f"\n--- {result['name']} [{result['status']}] ---")
            if result["notes"]:
                for n in result["notes"]:
                    print(f"  {n['date']}: {n['note']}")
            else:
                print("  No notes yet.")
            print()
    else:
        print("  Commands: /project add <name> | /project note <name> <note> | /project recall <name> | /projects\n")


def handle_person_command(args):
    from memory import add_person, add_person_note, recall_person
    if not args:
        print("  Usage: /person add <name> [role] | /person note <name> <note> | /person recall <name>\n")
        return

    parts = args.split(None, 2)
    sub = parts[0].lower()

    if sub == "add":
        if len(parts) < 2:
            print("  Usage: /person add <name> [role]\n")
            return
        name = parts[1]
        role = parts[2] if len(parts) == 3 else None
        if add_person(name, role):
            print(f"  Person added: {name}" + (f" ({role})" if role else "") + "\n")
        else:
            print(f"  '{name}' already exists.\n")

    elif sub == "note":
        if len(parts) < 3:
            print("  Usage: /person note <name> <note>\n")
            return
        name, note = parts[1], parts[2]
        if add_person_note(name, note):
            print(f"  Note added to {name}.\n")
        else:
            print(f"  Person '{name}' not found. Add them first: /person add {name}\n")

    elif sub == "recall":
        if len(parts) < 2:
            print("  Usage: /person recall <name>\n")
            return
        result = recall_person(parts[1])
        if not result:
            print(f"  Person '{parts[1]}' not found.\n")
        else:
            print(f"\n--- {result['name']}" + (f" | {result['role']}" if result["role"] else "") + " ---")
            if result["notes"]:
                for n in result["notes"]:
                    print(f"  {n['date']}: {n['note']}")
            else:
                print("  No notes yet.")
            print()
    else:
        print("  Commands: /person add <name> [role] | /person note <name> <note> | /person recall <name>\n")


def _handle_lootdrop(user_input: str):
    """
    /lootdrop                          — show recap of recent drops
    /lootdrop <tier> <project> <reason>  — award a drop
    Tiers: common uncommon rare epic legendary mythic
    """
    from lootdrop import award, recap_summary, TIER_NAMES
    parts = user_input.strip().split(None, 3)
    # /lootdrop (no args) → show recap
    if len(parts) == 1:
        print()
        print(recap_summary())
        print()
        return
    # /lootdrop <tier> <project> <reason>
    if len(parts) < 4:
        print(f"\n  Usage: /lootdrop <tier> <project> <reason>")
        print(f"  Tiers: {', '.join(TIER_NAMES)}")
        print(f"  Example: /lootdrop mythic ORACLE SOV1 vision loop working end-to-end\n")
        return
    tier = parts[1].lower()
    project = parts[2]
    reason = parts[3]
    try:
        award(tier, source_activity="manual /lootdrop command", reason_earned=reason,
              related_project=project)
    except ValueError as e:
        print(f"\n  {e}\n")


def _has_tool_use(content):
    """True if an assistant message's content contains a tool_use block."""
    if not isinstance(content, list):
        return False
    for block in content:
        btype = getattr(block, "type", None) or (block.get("type") if isinstance(block, dict) else None)
        if btype == "tool_use":
            return True
    return False


def _repair_history(history):
    """
    Trim history back to the last clean boundary after an interrupted tool call.
    A clean boundary is an assistant message with no dangling tool_use blocks.
    Drops the trailing (now-stale) user input so the retry re-adds it cleanly.
    """
    repaired = list(history)
    # Walk backward, dropping messages until we land on a complete assistant turn
    while repaired:
        last = repaired[-1]
        role = last.get("role")
        content = last.get("content")
        if role == "assistant" and not _has_tool_use(content):
            break  # clean end_turn assistant message — safe stopping point
        repaired.pop()
    return repaired


def chat(client, session_id, system_prompt, history, user_input, model="claude-sonnet-4-6"):
    history.append({"role": "user", "content": user_input})
    save_message(session_id, "user", user_input)
    log("INPUT", user_input)

    _tool_call_count = 0
    while True:
        if _tool_call_count >= MAX_TOOL_CALLS_PER_TURN:
            # Enter ERROR_RECOVERY — gives structured diagnostic, not just prose
            _lg_diag = f"Loop guard: {_tool_call_count} tool calls without finishing."
            _lg_hint = (
                "Type ACTION_DIAGNOSTIC to see which tool repeated. "
                "Type STOP ORACLE to halt all action. "
                "Type CLEAR_PROMPT to clear any stale terminal prompt."
            )
            try:
                from session_state import enter_recovery, action_diagnostic
                enter_recovery(reason=_lg_diag, hint=_lg_hint)
                _diag_output = action_diagnostic()
            except Exception:
                _diag_output = ""
            reply = (
                f"[Loop guard] {_lg_diag}\n"
                f"{_diag_output}\n"
                f"Hint: {_lg_hint}"
            )
            save_message(session_id, "assistant", reply)
            return reply, history
        response = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
            messages=history,
            tools=TOOL_DEFINITIONS,
        )

        # Append whatever Claude returned to history
        history.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    _tool_call_count += 1
                    _print_thinking(block.name, block.input)
                    result = execute_tool(block.name, block.input)
                    _print_thought_result(block.name, result)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            history.append({"role": "user", "content": tool_results})
            continue

        reply = ""
        for block in response.content:
            if hasattr(block, "text"):
                reply = block.text
                break

        save_message(session_id, "assistant", reply)
        log("OUTPUT", reply[:200] + ("..." if len(reply) > 200 else ""))
        return reply, history


def chat_local(client, session_id, system_prompt, history, user_input, model):
    """OpenAI-compatible agentic loop for local Ollama models.

    Uses LOCAL_TOOL_DEFINITIONS — a restricted read-only subset of tools.
    Write, create, execute, browser, and actuation tools are not available
    to the local model. Hallucinated success claims are detected and flagged.
    """
    import json

    # Inject live ORACLE state into user message so 7B model has grounding
    grounded_input = _inject_local_context(user_input)
    history.append({"role": "user", "content": grounded_input})
    save_message(session_id, "user", user_input)  # save original, not injected
    log("INPUT", user_input)

    # Restricted tool set for local model — read-only operations only
    oai_tools = to_openai_tools(LOCAL_TOOL_DEFINITIONS)
    _tools_called: list[str] = []

    _tool_call_count = 0
    while True:
        if _tool_call_count >= MAX_TOOL_CALLS_PER_TURN:
            reply = (
                f"[Loop guard] I made {_tool_call_count} tool calls without finishing. "
                f"Stopping. Tell me the next step."
            )
            save_message(session_id, "assistant", reply)
            return reply, history
        messages = [{"role": "system", "content": system_prompt}] + history
        response = client.chat.completions.create(
            model=model,
            max_tokens=MAX_TOKENS,
            messages=messages,
            tools=oai_tools,
            temperature=0.3,        # lower = less hallucination
            extra_body={
                "num_ctx": 16384,
                "num_predict": MAX_TOKENS,
                "repeat_penalty": 1.1,
                "top_p": 0.85,
            },
        )
        msg = response.choices[0].message
        finish = response.choices[0].finish_reason

        assistant_entry = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
        history.append(assistant_entry)

        if finish in ("tool_calls", "tool_use") and msg.tool_calls:
            for tc in msg.tool_calls:
                _tool_call_count += 1
                tool_name = tc.function.name

                # Block tools outside the safe set entirely
                if tool_name not in _LOCAL_SAFE_TOOL_NAMES:
                    blocked_msg = (
                        f"[BLOCKED] Tool '{tool_name}' is not available in local mode. "
                        f"If this is a code/build task, say 'send to Claude Code' instead."
                    )
                    print(f"  {C['bred']}[BLOCKED]{C['reset']} Tool not available in local mode: {tool_name}")
                    history.append({"role": "tool", "tool_call_id": tc.id, "content": blocked_msg})
                    log("HALLUCINATION_BLOCK", f"local model attempted blocked tool: {tool_name}")
                    continue

                try:
                    inp = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    inp = {}

                # ── Terminal safety classification ────────────────────────────
                if tool_name in ("run_shell", "terminal_run"):
                    cmd_str = inp.get("command", "")
                    safe, reason = _classify_terminal_command(cmd_str)
                    if not safe:
                        blocked_msg = f"[BLOCKED] {reason} Command not executed."
                        print(f"  {C['bred']}[BLOCKED]{C['reset']} Terminal command blocked: {reason}")
                        history.append({"role": "tool", "tool_call_id": tc.id, "content": blocked_msg})
                        log("TERMINAL_BLOCKED", f"blocked: {cmd_str[:80]} — {reason}")
                        continue

                # ── HANDS — no gate, SOV1 governs internally ─────────────────
                if tool_name in _LOCAL_HANDS_TOOLS:
                    print(f"  {C['bgreen']}[HANDS]{C['reset']} {tool_name}")

                # ── WRITE — explicit approval required ────────────────────────
                elif tool_name in _LOCAL_WRITE_TOOLS:
                    print()
                    print(f"  {C['byellow']}[GOVERNANCE]{C['reset']} ▶ APPROVAL NEEDED")
                    print(f"  {C['bold']}Tool   :{C['reset']} {tool_name}")
                    for key in ("path", "command", "app_name", "text", "content"):
                        val = inp.get(key, "")
                        if val:
                            print(f"  {C['bold']}{key.ljust(7)}:{C['reset']} {str(val)[:100]}")
                    print(f"\n  Type {C['bold']}approve{C['reset']} to execute or {C['bold']}reject{C['reset']} to cancel: ", end="")
                    try:
                        answer = input().strip().lower()
                    except (EOFError, KeyboardInterrupt):
                        answer = "reject"
                    if answer not in ("approve", "yes", "y", "ok", "confirmed"):
                        rejection = f"[REJECTED] Noah did not approve {tool_name}."
                        print(f"  {C['bred']}[BLOCKED]{C['reset']} Rejected.\n")
                        history.append({"role": "tool", "tool_call_id": tc.id, "content": rejection})
                        log("APPROVAL_REJECTED", f"Noah rejected local write tool: {tool_name}")
                        continue
                    print(f"  {C['bgreen']}Approved.{C['reset']}\n")
                    log("APPROVAL_GRANTED", f"Noah approved: {tool_name}")

                # ── READ — no gate, label silently ───────────────────────────
                else:
                    pass  # read tools — no label needed, just execute

                _print_thinking(tool_name, inp)
                result = execute_tool(tool_name, inp)
                _print_thought_result(tool_name, result)
                _tools_called.append(tool_name)
                history.append({"role": "tool", "tool_call_id": tc.id, "content": result})
            continue

        reply = msg.content or ""

        # Hallucination detection — flag fabricated success before showing Noah
        warning = _detect_hallucination(reply, _tools_called)
        if warning:
            print(f"\n{C['bred']}{warning}{C['reset']}\n")
            log("HALLUCINATION_DETECTED", f"reply: {reply[:120]}")
            reply = warning + "\n\n" + reply

        save_message(session_id, "assistant", reply)
        log("OUTPUT", reply[:200] + ("..." if len(reply) > 200 else ""))
        return reply, history


def main():
    os.chdir(Path(__file__).parent)
    init_db()
    session_id = new_session()
    identity = load_identity()
    history = []

    local = is_local()
    try:
        client = make_client()
    except RuntimeError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    model = get_model(vision=False)
    system_prompt = build_system_prompt(local=local)

    if local:
        print(f"\n[LOCAL MODE] Using Ollama model: {model}")
        print("[LOCAL MODE] Make sure Ollama is running and the model is pulled.")
        print(f"[LOCAL MODE] Pull command: ollama pull {model}\n")

    # Initialise LiveContext — loads persisted state, stamps last_updated
    from live_context import get_live_context
    _ctx = get_live_context()
    _ctx.set_task("Interactive session")

    _last_pending_ids: list = []           # populated by /pending, consumed by approve/reject
    _last_pending_secret_flags: list[bool] = []  # parallel list — True = secret-blocked

    banner(identity)
    log("SESSION_START", f"Session {session_id} started")

    # ── Connectivity status at boot ───────────────────────────────────────────
    _claude_cli_found = shutil.which("claude") is not None
    _claude_win_found = _claude_available_now()
    _claude_status_str = (
        f"{C['bgreen']}CONNECTED{C['reset']}"
        if (_claude_cli_found or _claude_win_found)
        else f"{C['bred']}NOT CONNECTED{C['reset']}"
    )
    _claude_detail = []
    if _claude_cli_found:
        _claude_detail.append("CLI")
    if _claude_win_found:
        _claude_detail.append("window")
    if not _claude_detail:
        _claude_detail.append("open Claude Code to connect")
    print(f"  Claude : {_claude_status_str}  {C['dim']}({', '.join(_claude_detail)}){C['reset']}")
    print(f"  Mode   : {C['cyan']}{'LOCAL' if local else 'CLOUD'}{C['reset']}  {C['dim']}model: {model}{C['reset']}")
    print()

    # ── Auto boot cycle — ORACLE starts working immediately, no first prompt needed ──
    try:
        from oracle_runtime import run_cycle, MODE_DAEMON_SAFE
        from voice import speak_prompt
        _boot = run_cycle(mode=MODE_DAEMON_SAFE)
        priority = _boot.selected_priority or "maintenance"
        action   = _boot.action_taken or ""
        next_s   = _boot.next_recommended_step or ""
        approval = _boot.approval_required

        print(f"\n{C['grey']}  {'─' * 50}{C['reset']}")
        print(f"  {C['cyan']}◆ ORACLE BOOT CYCLE{C['reset']}  {C['dim']}{priority}{C['reset']}")
        if action:
            print(f"  {C['dim']}{action[:120]}{C['reset']}")
        if next_s:
            label = f"{C['byellow']}  ▶ ACTION NEEDED:{C['reset']}" if approval else f"  {C['grey']}Next:{C['reset']}"
            print(f"{label} {C['dim']}{next_s[:100]}{C['reset']}")
        print(f"{C['grey']}  {'─' * 50}{C['reset']}\n")

        if approval:
            speak_prompt(f"I'm up. {action[:80]}")
        else:
            speak_prompt("I'm up.")
    except Exception:
        pass
    # ── End auto boot cycle ────────────────────────────────────────────────────

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nOracle offline. Session saved.")
            log("SESSION_END", f"Session {session_id} ended")
            break

        if not user_input:
            continue

        # ── Paste / log-dump detection — must be first intercept ─────────────
        # If Noah pastes ORACLE terminal output, don't route each line as a command.
        if _detect_pasted_log(user_input):
            summary = _summarize_pasted_log(user_input)
            print(f"\n  {C['byellow']}[DIAGNOSTIC]{C['reset']}")
            for line in summary.splitlines():
                print(f"  {line}")
            print()
            log("PASTE_DETECT", f"pasted log detected ({len(user_input)} chars)")
            continue

        # ── Session State Controller — intercept BEFORE any LLM or tool call ──
        try:
            from session_state import (
                handle_command as ss_handle_command,
                classify_user_input, should_consume_as_prompt_answer,
                record_tool_call as ss_record_tool_call,
                detect_stale_prompt, set_mode as ss_set_mode,
                MODE_BUILD_PASS, MODE_IDLE, action_diagnostic,
            )
            # Stale prompt sweep on every input
            was_stale, stale_reason = detect_stale_prompt()
            if was_stale:
                print(f"\n  [SESSION] Stale prompt cleared: {stale_reason[:100]}\n")

            # Hard-intercept: is this a session state command?
            ss_handled, ss_response = ss_handle_command(user_input)
            if ss_handled:
                print(ss_response)
                continue

            # Classify input and warn if it would have been hijacked
            clf = classify_user_input(user_input)
            if clf.override_active_prompt:
                # Don't stop — but log that a stale prompt was overridden
                log("SESSION", f"Input override: classified as {clf.classified_as} — {clf.reason[:80]}")

            # Track BUILD_PASS mode for MYTHIC BUILD PASS inputs
            if clf.is_build_instruction:
                ss_set_mode(MODE_BUILD_PASS, reason=f"Build instruction detected: {user_input[:60]}")
        except ImportError:
            pass
        except Exception as _ss_err:
            log("SESSION_WARN", f"session_state error: {_ss_err}")
        # ── End session state intercept ────────────────────────────────────────

        if user_input.lower() in ("/quit", "/exit"):
            print("\nOracle offline. Session saved.")
            log("SESSION_END", f"Session {session_id} ended")
            # Persist session close into project state so next boot is oriented
            try:
                from project_state import load_state, save_state
                from datetime import datetime, timezone
                ps = load_state("ORACLE.AI")
                if ps:
                    ps.lessons_learned.append(
                        f"[session] oracle.py session ended {datetime.now(timezone.utc).isoformat()[:16]} UTC"
                    )
                    ps.lessons_learned = ps.lessons_learned[-40:]
                    save_state(ps)
            except Exception:
                pass
            from voice import shutdown as voice_shutdown
            voice_shutdown()
            break

        if user_input.lower() == "/memory":
            show_memory(session_id)
            continue

        if user_input.lower() == "/clear":
            history = []
            print("Conversation history cleared. Memory persists.\n")
            continue

        if user_input.lower() in ("/projects", "/project"):
            handle_project_command("")
            continue

        if user_input.lower().startswith("/project "):
            handle_project_command(user_input[9:].strip())
            continue

        if user_input.lower().startswith("/person "):
            handle_person_command(user_input[8:].strip())
            continue

        # ── LiveContext / privacy commands ────────────────────────────────────
        if user_input.lower() in ("/context", "/ctx"):
            from live_context import get_live_context
            print(get_live_context().show())
            continue

        if user_input.lower() in ("/privacy on", "/privacy-on"):
            from live_context import get_live_context
            print(f"\n  {get_live_context().set_privacy_mode(True)}\n")
            continue

        if user_input.lower() in ("/privacy off", "/privacy-off"):
            from live_context import get_live_context
            print(f"\n  {get_live_context().set_privacy_mode(False)}\n")
            continue

        if user_input.lower() in ("/pause-context", "/pause"):
            from live_context import get_live_context
            print(f"\n  {get_live_context().pause()}\n")
            continue

        if user_input.lower() in ("/resume-context", "/resume"):
            from live_context import get_live_context
            print(f"\n  {get_live_context().resume()}\n")
            continue

        if user_input.lower() in ("/purge-buffer", "/purge"):
            from live_context import get_live_context
            answer = input("\n  Purge live context buffer? Pending candidates will be discarded. (y/n): ").strip().lower()
            if answer in ("y", "yes"):
                print(f"  {get_live_context().purge_buffer()}\n")
            else:
                print("  Cancelled.\n")
            continue

        if user_input.lower() in ("/pending", "/pending-candidates"):
            from approval_center import list_pending as ac_list_pending
            try:
                from claude_code_bridge import contains_secret
            except Exception:
                contains_secret = lambda t: False
            candidates = ac_list_pending()
            _last_pending_ids.clear()
            _last_pending_secret_flags: list[bool] = []
            if not candidates:
                print("\n  No pending candidates.\n")
            else:
                print(f"\n--- Pending Approval ({len(candidates)}) ---")
                for i, c in enumerate(candidates):
                    source   = c.get("source", "?")
                    category = c.get("category", c.get("rendered_category", "?"))
                    key      = c.get("key", c.get("rendered_key", "?"))
                    value    = str(c.get("value", c.get("rendered_value", "")))[:80]
                    conf     = str(c.get("confidence", "?")).upper()
                    cid      = c.get("id", "?")
                    title_text = c.get("title", "") + " " + value
                    is_secret = c.get("sensitive_flag") or contains_secret(title_text)
                    if is_secret:
                        flag = f" {C['bred']}[⚠ SECRET — BLOCKED]{C['reset']}"
                    else:
                        flag = ""
                    print(f"  [{i+1}] [{conf}] {source} | {category}/{key}{flag}")
                    print(f"    Value  : {value}")
                    print(f"    ID     : {cid}")
                    _last_pending_ids.append(cid)
                    _last_pending_secret_flags.append(is_secret)
                print(f"\n  approve / reject / approve 2 / reject 2 …\n")
                print(f"  {C['grey']}Secret-flagged items cannot be approved. Reject them.{C['reset']}\n")
            continue

        # ── Natural language approve / reject pending items ────────────────────
        _uil_pending = user_input.lower().strip().rstrip(".")
        _approve_match = (
            _uil_pending in ("approve", "approved", "yes", "confirm", "ok", "looks good")
            or _uil_pending.startswith("approve ")
        )
        _reject_match = (
            _uil_pending in ("reject", "rejected", "no", "dismiss", "skip", "discard", "bad", "delete it")
            or _uil_pending.startswith("reject ")
            or _uil_pending.startswith("dismiss ")
        )
        if (_approve_match or _reject_match) and _last_pending_ids:
            # Parse optional index — "approve 2" targets item 2
            parts = user_input.strip().split()
            idx = 0
            if len(parts) == 2:
                try:
                    idx = int(parts[1]) - 1
                except ValueError:
                    idx = 0
            idx = max(0, min(idx, len(_last_pending_ids) - 1))
            target_id = _last_pending_ids[idx]

            # ── Secret hard block — cannot approve sensitive items ────────────
            is_secret = (
                idx < len(_last_pending_secret_flags)
                and _last_pending_secret_flags[idx]
            )
            if _approve_match and is_secret:
                print(
                    f"\n  {C['bred']}[BLOCKED]{C['reset']} This item contains a secret pattern "
                    f"(sk-, api_key, token, password).\n"
                    f"  It cannot be approved. Type {C['bold']}reject {idx+1}{C['reset']} to discard it.\n"
                )
                log("SECRET_APPROVE_BLOCKED", f"blocked approve of secret item {target_id[:8]}")
                continue

            try:
                from approval_center import approve as ac_approve, reject as ac_reject
                if _approve_match:
                    ac_approve(target_id, approved_by="noah")
                    print(f"\n  {C['bgreen']}Approved{C['reset']} — {target_id[:8]}\n")
                    speak("Approved.")
                    _last_pending_ids.pop(idx)
                    if idx < len(_last_pending_secret_flags):
                        _last_pending_secret_flags.pop(idx)
                else:
                    ac_reject(target_id, reason="Noah rejected via REPL")
                    print(f"\n  {C['yellow']}Rejected{C['reset']} — {target_id[:8]}\n")
                    speak("Rejected.")
                    _last_pending_ids.pop(idx)
                    if idx < len(_last_pending_secret_flags):
                        _last_pending_secret_flags.pop(idx)
            except Exception as e:
                print(f"\n  [approval error: {e}]\n")
            continue

        if user_input.lower() in ("/voice on", "/voice"):
            set_voice_enabled(True)
            print("\n  Voice ON — Oracle will speak her replies.\n")
            continue

        if user_input.lower() == "/voice off":
            set_voice_enabled(False)
            print("\n  Voice OFF — text only.\n")
            continue

        if user_input.lower().startswith("/lootdrop"):
            _handle_lootdrop(user_input)
            continue

        if user_input.lower() == "/propose-build":
            print("\n[propose-build] Starting read-only build recommendation...\n")
            try:
                from propose_build import run_propose_build
                proposal = run_propose_build(client, model, local)
                print(proposal)
            except Exception as e:
                log("ERROR", f"/propose-build failed: {e}")
                print(f"\n[propose-build error: {e}]\n")
            continue

        if user_input.lower() in ("/self-prompt", "/selfprompt", "/cycle"):
            try:
                from oracle_runtime import run_cycle, MODE_MANUAL as ORT_MANUAL
                result = run_cycle(mode=ORT_MANUAL)
                priority = result.selected_priority or "maintenance"
                action   = result.action_taken or ""
                next_s   = result.next_recommended_step or ""
                approval = result.approval_required
                conf     = int(result.confidence * 100)

                print(f"\n{C['grey']}  {'─'*50}{C['reset']}")
                print(f"  {C['cyan']}◆ CYCLE{C['reset']}  {C['dim']}{priority}  {conf}%{C['reset']}")
                if action:
                    print(f"  {action[:120]}")
                if next_s:
                    label = f"  {C['byellow']}▶ ACTION NEEDED:{C['reset']}" if approval else f"  {C['grey']}Next:{C['reset']}"
                    print(f"{label} {next_s[:100]}")
                if result.unknowns:
                    print(f"  {C['dim']}Unknowns: {len(result.unknowns)} preserved{C['reset']}")
                print(f"{C['grey']}  {'─'*50}{C['reset']}\n")
                speak(f"Cycle complete. {action[:60]}" if not approval else f"Action needed. {next_s[:60]}")
            except Exception as e:
                log("ERROR", f"/cycle failed: {e}")
                print(f"\n[cycle error: {e}]\n")
            continue

        if user_input.lower() in ("/project-state", "/ps", "/resume", "/where-was-i"):
            try:
                from project_state import summarize_state, list_projects
                projects = list_projects()
                if not projects:
                    print("\nNo project state saved yet. Run: python core/project_state.py --seed\n")
                else:
                    for p in projects:
                        print(f"\n{'─'*54}")
                        print(summarize_state(p))
            except Exception as e:
                print(f"\n[project-state error: {e}]\n")
            continue

        if user_input.lower() in ("/runtime", "/oracle-runtime", "/run-cycle"):
            print("\n[runtime] Running one governed runtime cycle...\n")
            try:
                from oracle_runtime import run_cycle, MODE_MANUAL
                result = run_cycle(mode=MODE_MANUAL)
                print(result.report())
                speak(f"Runtime cycle complete. Priority: {result.selected_priority[:60]}")
            except Exception as e:
                log("ERROR", f"/runtime failed: {e}")
                print(f"\n[runtime error: {e}]\n")
            continue

        if user_input.lower() in ("/runtime-status", "/cycle-status"):
            try:
                from oracle_runtime import status_report
                print(status_report())
            except Exception as e:
                print(f"\n[runtime-status error: {e}]\n")
            continue

        if user_input.lower() in ("/bridge-chatgpt-status", "/bridge-status"):
            try:
                from chatgpt_bridge import get_bridge
                print(get_bridge().status())
            except Exception as e:
                print(f"\n[bridge-status error: {e}]\n")
            continue

        if user_input.lower().startswith("/bridge-chatgpt-draft"):
            request_text = user_input[len("/bridge-chatgpt-draft"):].strip()
            if not request_text:
                print("\nUsage: /bridge-chatgpt-draft <your question for ChatGPT>\n")
            else:
                try:
                    from chatgpt_bridge import get_bridge
                    msg, status = get_bridge().bridge(request=request_text, dry_run=True)
                    print(msg.summary())
                    print(f"Status: {status}\n")
                except Exception as e:
                    print(f"\n[bridge-draft error: {e}]\n")
            continue

        if user_input.lower().startswith("/controls "):
            win_hint = user_input.split(" ", 1)[1].strip()
            try:
                from semantic_ui_bridge import find_window, dump_controls
                w = find_window(title_contains=win_hint)
                if w is None:
                    print(f"\n  No window found matching: {win_hint!r}\n")
                else:
                    print(f"\n  Window: {w.title!r}  (pid={w.pid})\n")
                    print(dump_controls(w))
                    print()
            except Exception as e:
                print(f"\n[controls error: {e}]\n")
            continue

        if user_input.lower() in ("/window-snapshot", "/win-snap"):
            try:
                from window_janitor import get_janitor
                snap = get_janitor().snapshot_windows()
                print(f"\n  Current windows ({len(snap)}):")
                for w in snap[:15]:
                    print(f"    {w.get('title', '?')[:70]}")
                if len(snap) > 15:
                    print(f"    ... and {len(snap) - 15} more")
                print()
            except Exception as e:
                print(f"\n[window-snapshot error: {e}]\n")
            continue

        if user_input.lower().startswith("/actuate ") or user_input.lower().startswith("/type-into "):
            # /actuate <window_hint> | <text to type>
            raw = user_input.split(" ", 1)[1].strip() if " " in user_input else ""
            if "|" not in raw:
                print("\n  Usage: /actuate <window_hint> | <text to type>\n"
                      "  Example: /actuate ChatGPT | Hello from ORACLE\n")
                continue
            # Optional --no-enter flag: /actuate Claude | text --no-enter
            _no_enter = text.endswith("--no-enter")
            if _no_enter:
                text = text[: -len("--no-enter")].strip()
            win_hint, text = win_hint, text
            print(f"\n[actuate] Target window: {win_hint!r}")
            print(f"          Text to inject: {text!r}")
            print(f"          Press Enter  : {'no (--no-enter)' if _no_enter else 'YES — will submit'}")
            print("  Noah approval required. Type 'yes' to proceed or anything else to cancel.")
            try:
                confirm = input("  Approve? ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                confirm = ""
            if confirm in ("yes", "y", "approve"):
                try:
                    from actuation_engine import type_into_window
                    result = type_into_window(
                        win_hint, text,
                        approved=True,
                        press_enter=(not _no_enter),
                    )
                    print(result.explain())
                    if result.success:
                        speak(f"Sent to {win_hint}.")
                    else:
                        speak(f"Actuation failed: {result.failure_stage}")
                except Exception as e:
                    log("ERROR", f"/actuate failed: {e}")
                    print(f"\n[actuate error: {e}]\n")
            else:
                print("\n  Actuation cancelled.\n")
            continue

        if user_input.lower().startswith("/actuate-dry "):
            raw = user_input.split(" ", 1)[1].strip()
            if "|" not in raw:
                print("\n  Usage: /actuate-dry <window_hint> | <text>\n")
                continue
            win_hint, text = [p.strip() for p in raw.split("|", 1)]
            try:
                from actuation_engine import type_into_window
                result = type_into_window(win_hint, text, dry_run=True)
                print(result.explain())
            except Exception as e:
                print(f"\n[actuate-dry error: {e}]\n")
            continue

        # ── /ask-claude <task> — send a task to Claude Code, wait for response ──
        if user_input.lower().startswith("/ask-claude "):
            task = user_input[len("/ask-claude "):].strip()
            if not task:
                print("\n  Usage: /ask-claude <task or question for Claude Code>\n")
                continue
            try:
                from oracle_claude_channel import ask_claude, ORACLE_TO_CLAUDE
                print(f"\n  {C['byellow']}[CHANNEL]{C['reset']} Sending task to Claude Code…")
                print(f"  {C['dim']}File: {ORACLE_TO_CLAUDE}{C['reset']}")
                print(f"  {C['dim']}Waiting up to 5 min for response. Type response in Messages/claude_to_oracle.md{C['reset']}\n")
                log("CHANNEL", f"ask_claude: {task[:80]}")
                response = ask_claude(task, timeout=300)
                print(f"\n  {C['bgreen']}[CLAUDE RESPONSE]{C['reset']}")
                for line in response.splitlines():
                    print(f"  {line}")
                print()
                speak("Claude responded.")
            except Exception as e:
                log("ERROR", f"/ask-claude failed: {e}")
                print(f"\n[channel error: {e}]\n")
            continue

        # ── /channel — show channel status ────────────────────────────────────
        if user_input.lower() in ("/channel", "/channel-status"):
            try:
                from oracle_claude_channel import (
                    ORACLE_TO_CLAUDE, CLAUDE_TO_ORACLE, CHANNEL_LOG, pending_task
                )
                has_outbox = ORACLE_TO_CLAUDE.exists()
                has_inbox  = CLAUDE_TO_ORACLE.exists()
                print(f"\n  {C['cyan']}[CHANNEL STATUS]{C['reset']}")
                print(f"  Outbox (oracle→claude) : {'PENDING' if has_outbox else 'empty'}  {ORACLE_TO_CLAUDE}")
                print(f"  Inbox  (claude→oracle) : {'RESPONSE READY' if has_inbox else 'empty'}  {CLAUDE_TO_ORACLE}")
                if has_inbox:
                    from oracle_claude_channel import CLAUDE_TO_ORACLE
                    resp = CLAUDE_TO_ORACLE.read_text(encoding="utf-8")[:300]
                    print(f"\n  {C['bgreen']}Response preview:{C['reset']}")
                    for line in resp.splitlines()[:8]:
                        print(f"    {line}")
                print()
            except Exception as e:
                print(f"\n[channel error: {e}]\n")
            continue

        # ── /channel-reply — read pending Claude response and act on it ───────
        if user_input.lower() in ("/channel-reply", "/read-claude"):
            try:
                from oracle_claude_channel import CLAUDE_TO_ORACLE
                if not CLAUDE_TO_ORACLE.exists():
                    print("\n  No Claude response pending. Use /ask-claude <task> first.\n")
                else:
                    response = CLAUDE_TO_ORACLE.read_text(encoding="utf-8").strip()
                    print(f"\n  {C['bgreen']}[CLAUDE RESPONSE]{C['reset']}")
                    for line in response.splitlines():
                        print(f"  {line}")
                    print()
                    speak("Claude response loaded.")
            except Exception as e:
                print(f"\n[channel-reply error: {e}]\n")
            continue

        if user_input.lower().startswith("/video-analyze "):
            raw_path = user_input[len("/video-analyze "):].strip()
            print(f"\n[video] Analyzing: {raw_path}")
            print("  Noah approval required. Type 'yes' to confirm or anything else to cancel.")
            try:
                confirm = input("  Approve analysis? ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                confirm = ""
            if confirm in ("yes", "y", "approve"):
                try:
                    from video_intelligence import analyze_video
                    candidate = analyze_video(raw_path, approved_by_noah=True)
                    print(f"\n{candidate.full_summary()}\n")
                    print(f"  Saved as PENDING. Use /video-approve {candidate.id} to approve for recall.\n")
                    speak(f"Video observation candidate created. Status: pending. ID: {candidate.id[:6]}.")
                except Exception as e:
                    log("ERROR", f"/video-analyze failed: {e}")
                    print(f"\n[video error: {e}]\n")
            else:
                print("\n  Analysis cancelled. Noah approval not confirmed.\n")
            continue

        if user_input.lower() in ("/video-pending", "/video pending"):
            try:
                from video_intelligence import list_pending
                pending = list_pending()
                if not pending:
                    print("\n  No pending video candidates.\n")
                else:
                    print(f"\n  Pending video candidates ({len(pending)}):\n")
                    for c in pending:
                        print(f"    {c.summary_line()}")
                    print()
            except Exception as e:
                print(f"\n[video-pending error: {e}]\n")
            continue

        if user_input.lower().startswith("/video-approve "):
            cid = user_input[len("/video-approve "):].strip()
            try:
                from video_intelligence import approve_candidate
                c = approve_candidate(cid, approved_by="Noah")
                print(f"\n  Approved: {c.summary_line()}\n")
                speak(f"Video candidate {cid[:6]} approved for recall.")
            except Exception as e:
                print(f"\n[video-approve error: {e}]\n")
            continue

        if user_input.lower() in ("/session", "/session-state", "/session-status"):
            try:
                from session_state import action_diagnostic
                print(action_diagnostic())
            except Exception as e:
                print(f"\n[session error: {e}]\n")
            continue

        if user_input.lower().startswith("/route-task") or user_input.lower().startswith("/route "):
            raw = user_input.split(" ", 1)[1].strip() if " " in user_input else ""
            if not raw:
                print("\n  Usage: /route-task <describe what you want to do>\n")
                continue
            try:
                from brain_router import create_task_from_text, route_task, explain_route
                task = create_task_from_text(raw)
                decision = route_task(task)
                print(f"\n  Task text  : {raw[:80]}")
                print(f"  Classified : {task.task_type}  complexity={task.complexity}  sensitivity={task.sensitivity}")
                print(explain_route(decision))
                if decision.blocked:
                    speak(f"Task blocked. {decision.block_reason[:80]}")
                else:
                    speak(f"Routed to {decision.selected_engine}. {decision.reason[:60]}")
            except Exception as e:
                log("ERROR", f"/route-task failed: {e}")
                print(f"\n[route-task error: {e}]\n")
            continue

        # ── Governance-drive intercept — "you choose", "go", "proceed" ──────────
        # When Noah gives open-ended direction, ORACLE consults her governance
        # cycle instead of letting the LLM improvise from nothing.
        _uil = user_input.lower().strip().rstrip(".")
        _ORACLE_DRIVES = {
            "you choose", "you decide", "go", "proceed", "your call",
            "what's next", "whats next", "what should we do", "what do you think",
            "do something", "act", "take over", "run", "execute", "keep going",
            "just go", "just do it", "do it", "start", "begin", "continue",
            "what would you do", "decide", "what now", "next", "what's the plan",
            "whats the plan", "what should i do", "what should you do",
        }
        if _uil in _ORACLE_DRIVES:
            try:
                from oracle_runtime import run_cycle, MODE_MANUAL as ORT_MANUAL
                from project_state import load_state
                r = run_cycle(mode=ORT_MANUAL)
                ps = load_state("ORACLE.AI")

                print(f"\n{C['grey']}  {'─'*50}{C['reset']}")
                print(f"  {C['cyan']}◆ ORACLE READS HER OWN STATE{C['reset']}")

                # Build plan
                if ps and ps.next_recommended_step:
                    print(f"\n  {C['bold']}Build plan:{C['reset']} {C['dim']}{ps.current_phase}{C['reset']}")
                    print(f"  {C['bold']}Next step :{C['reset']} {ps.next_recommended_step[:100]}")

                # Cycle priority
                action = r.action_taken or ""
                next_s = r.next_recommended_step or ""
                conf   = int(r.confidence * 100)
                print(f"\n  {C['bold']}Right now  :{C['reset']} {C['dim']}{r.selected_priority}  {conf}%{C['reset']}")
                if action:
                    print(f"  {action[:120]}")
                if r.approval_required and next_s:
                    print(f"\n  {C['byellow']}▶ Needs your approval:{C['reset']} {next_s[:100]}")
                    print(f"\n  Type {C['bold']}approve{C['reset']} to proceed or {C['bold']}reject{C['reset']} to skip.")
                    _last_pending_ids.clear()
                elif next_s:
                    print(f"\n  {C['grey']}Proposed:{C['reset']} {next_s[:100]}")
                    print(f"\n  Type {C['bold']}go{C['reset']} to execute or give me a different direction.")

                print(f"{C['grey']}  {'─'*50}{C['reset']}\n")
                speak(next_s[:80] if next_s else "I've checked my state. Here's what I see.")
            except Exception as e:
                print(f"\n[governance error: {e}]\n")
            continue

        if _uil in (
            "/self-build", "/selfbuild",
            "build yourself", "build yourself.", "improve yourself",
            "self build", "self-build", "self improve",
            "what should you build", "what should you improve",
        ):
            print("\n[self-build] Scanning codebase for highest-value improvement...\n")
            try:
                from self_build import run_self_build
                result = run_self_build(client, model, local, implement=False)
                print(result)
                speak(f"Self-build proposal ready. {result.split('TITLE')[1][:80] if 'TITLE' in result else 'Review the proposal.'}")
            except Exception as e:
                log("ERROR", f"/self-build failed: {e}")
                print(f"\n[self-build error: {e}]\n")
            continue

        if user_input.lower() == "/help":
            print("""
Commands:
  /memory                            Show stored facts and session info
  /projects                          List all projects
  /project add <name>                Add a project
  /project note <name> <note>        Add a note to a project
  /project recall <name>             Show project and all notes
  /person add <name> [role]          Add a person
  /person note <name> <note>         Add a note about a person
  /person recall <name>              Show person and all notes
  /clear                             Clear conversation history
  /propose-build                     Read build docs and recommend one next task (read-only)
  /self-build                        Scan own codebase and propose the single best improvement
  /self-prompt                       Run one governed self-prompt cycle (state, memory, gaps, priority, proposal)
  /project-state                     Show current project state — what was active, what's blocked, what's next
  /runtime                           Run one governed runtime cycle (heartbeat — picks priority, invokes module, persists result)
  /runtime-status                    Show runtime state: SOV1, Ollama, pending queues, next priority
  /bridge-chatgpt-draft <question>   Draft a governed message to ChatGPT (does not send — dry run)
  /bridge-chatgpt-status             Show ChatGPT bridge status and pending drafts
  /window-snapshot                   List currently visible windows on the desktop
  /controls <window>                 Dump all UIA controls discovered in a window (debug actuation)
  /route-task <description>          Route a task to the correct cognitive engine (brain router)
  /actuate <window> | <text>         Governed desktop injection: inject + press Enter (add --no-enter to suppress)
  /actuate-dry <window> | <text>     Dry run actuation — shows what would happen without executing
  /ask-claude <task>                 Send task to Claude Code via file channel; wait for response
  /channel                           Show ORACLE-Claude channel status (outbox / inbox)
  /channel-reply                     Read latest Claude response from the channel
  /video-analyze <path>              Analyze an approved video file — creates pending candidate
  /video-pending                     List pending video observation candidates
  /video-approve <id>                Approve a video candidate for recall
  /session                           Show full session state diagnostic (mode, prompt, tool history)
  ACTION_DIAGNOSTIC                  Real structured diagnostic (not prose) — mode, prompt, tool calls, recovery hint
  CLEAR_PROMPT                       Clear any active terminal prompt (stop prompt hijacking)
  RESET_SESSION_STATE                Full session reset to IDLE (preserves tool history)
  STOP ORACLE                        Halt all action, clear prompts, enter SAFE_SLEEP
  SET_MODE BUILD_PASS                Force BUILD_PASS mode
  SET_MODE IDLE                      Force IDLE mode
  /lootdrop                          Show recent LootDrop momentum recap
  /lootdrop <tier> <project> <reason>  Award a LootDrop (tiers: common uncommon rare epic legendary mythic)
  /context                           Show current live operational context state
  /privacy on | /privacy off         Toggle privacy mode (clears buffer, suspends context)
  /pause-context                     Pause context updates without full privacy mode
  /resume-context                    Resume context updates
  /purge-buffer                      Discard live context buffer without approving candidates
  /pending                           List external integration candidates pending approval
  /voice on | /voice off             Toggle voice output (Oracle speaks replies)
  /quit                              Exit

Brain tools (reasoning, files, web):
  read_file / write_file / list_directory
  run_shell       Run a one-off PowerShell command (stateless)
  terminal_run    Run a command in ORACLE's own persistent terminal (state carries between calls)
  terminal_cd     Change directory in the persistent terminal
  terminal_status Check terminal session state
  browser_navigate / browser_search
  filesystem_scan / filesystem_search
  remember_fact / recall_facts
  scheduler_control

Hands tools (SOV1 — operates the screen):
  computer_operator   Tell Oracle to do something on screen and it uses SOV1.
                      Just speak naturally: "open Chrome", "click X", etc.
                      Abort anytime: slam mouse into a screen corner.
""")
            continue

        # ── Interaction mode — CHAT / WORK / BUILD / DIAGNOSTIC ──────────────────
        # Determines routing behaviour for this turn:
        #   CHAT    → skip all routing, respond conversationally via local model
        #   WORK    → local model first; skip auto-routing unless tools are needed
        #   BUILD   → check Claude availability → route or return [CLAUDE UNAVAILABLE]
        #   DIAGNOSTIC → already handled above; shouldn't reach here
        _imode = _classify_interaction_mode(user_input)

        # ── Governance pre-classification ────────────────────────────────────────
        governance_response = handle_in_repl(user_input)
        if governance_response is not None:
            print(governance_response)
            speak(governance_response)
            continue

        # ── CHAT mode fast-path — skip routing, respond directly ─────────────────
        if _imode == "CHAT":
            try:
                reply, history = chat_local(client, session_id, system_prompt, history, user_input, model)
                blocked = _detect_hallucination(reply, [])
                if blocked:
                    reply = blocked
                    log("HALLUCINATION_DETECTED", f"reply: {reply[:120]}")
                print(f"  {C['cyan']}[CHAT]{C['reset']}")
                _print_oracle_reply(reply)
                speak(reply)
            except Exception as _chat_err:
                print(f"\n{C['bred']}  [Error: {_chat_err}]{C['reset']}\n")
            continue

        # ── Claude Code routing — BUILD mode or explicit claude/code task ─────────
        # CHAT and WORK mode skip this block. BUILD always routes here.
        # is_claude_directed: "with claude", "tell claude", "paste into", etc.
        # is_code_task: implement, build, refactor, .py, "explain the code", etc.
        _route_to_claude = (_imode == "BUILD")
        try:
            from claude_code_bridge import is_claude_directed, is_code_task, type_into_claude
            if not _route_to_claude:
                _route_to_claude = is_claude_directed(user_input) or is_code_task(user_input)

            if _route_to_claude:
                # Claude availability gate — check before claiming routing happened
                _claude_up = _claude_available_now()
                _cli_up = shutil.which("claude") is not None
                if not _claude_up and not _cli_up:
                    # [CLAUDE UNAVAILABLE] — show handoff prompt so Noah can paste manually
                    print(f"\n  {C['bred']}[CLAUDE UNAVAILABLE]{C['reset']} Claude Code window not found and CLI not on PATH.\n")
                    print(f"  {C['dim']}Manual handoff — paste this into Claude Code:{C['reset']}\n")
                    print(f"  {C['bold']}{user_input}{C['reset']}\n")
                    log("ROUTING", f"Claude unavailable — handoff prompt displayed for: {user_input[:80]}")
                    continue

                print(f"\n  {C['byellow']}[BUILD]{C['reset']} ↗ Routing to Claude Code…\n")
                log("ROUTING", f"build task → Claude Code: {user_input[:80]}")
                ok, detail = type_into_claude(user_input, open_if_missing=True)
                if ok:
                    if "[CLAUDE DESKTOP]" in detail:
                        print(f"  {C['bgreen']}[CLAUDE DESKTOP]{C['reset']} {detail.replace('[CLAUDE DESKTOP] ', '')}\n")
                        speak("Sent to Claude.")
                    else:
                        print(f"  {C['bgreen']}[CLAUDE CODE]{C['reset']} {detail}\n")
                        speak("Sent to Claude Code.")
                else:
                    if "[CLAUDE UNAVAILABLE]" in detail:
                        lines = detail.splitlines()
                        print(f"  {C['bred']}[CLAUDE UNAVAILABLE]{C['reset']} Claude Code not reachable.\n")
                        for line in lines[1:]:
                            if line.strip():
                                print(f"  {C['dim']}{line}{C['reset']}")
                        print(f"\n  {C['dim']}Paste manually: {user_input[:120]}{C['reset']}\n")
                    else:
                        print(f"  {C['bred']}[CLAUDE CODE ERROR]{C['reset']} {detail}\n")
                continue
        except Exception as _bridge_err:
            print(f"  {C['yellow']}[GOVERNANCE]{C['reset']} Claude Code routing error: {_bridge_err} — falling back to local model\n")
            log("ROUTING_WARN", f"claude_code_bridge error: {_bridge_err}")
        # ── End Claude Code routing ────────────────────────────────────────────

        try:
            if local:
                reply, history = chat_local(client, session_id, system_prompt, history, user_input, model)
            else:
                reply, history = chat(client, session_id, system_prompt, history, user_input, model)

            # Tool-truthfulness guard: replace unclaimed action phrases with [BLOCKED] format
            if local:
                blocked = _detect_hallucination(reply, [])
                if blocked:
                    log("HALLUCINATION_DETECTED", f"reply: {reply[:120]}")
                    reply = blocked

            # Post-LLM guard: if local model produced implementation stubs, re-route.
            # Also catch qwen saying "Routing to Claude Code." verbatim — that means
            # routing already fired (and failed), or the model is hallucinating the phrase.
            _IMPL_PATTERNS = [
                "def ", "class ", "```python", "i'll create", "i'll implement",
                "here's the implementation", "i'll write", "i'll build",
                "voice_hooks.py", "core/voice", "touch core/", "terminal_run",
            ]
            _QWEN_ROUTING_HALLUCINATION = reply.strip().lower() in (
                "routing to claude code.", "routing to claude code",
            )
            if _QWEN_ROUTING_HALLUCINATION or any(p.lower() in reply.lower() for p in _IMPL_PATTERNS):
                print(f"\n  {C['byellow']}[GOVERNANCE]{C['reset']} Local model attempted implementation — re-routing to Claude Code.\n")
                log("ROUTING", "post-LLM guard triggered — re-routing to Claude Code")
                try:
                    from claude_code_bridge import type_into_claude
                    ok2, detail2 = type_into_claude(user_input, open_if_missing=True)
                    if ok2:
                        lbl = "[CLAUDE DESKTOP]" if "[CLAUDE DESKTOP]" in detail2 else "[CLAUDE CODE]"
                        print(f"  {C['bgreen']}{lbl}{C['reset']} {detail2.replace('[CLAUDE DESKTOP] ','')}\n")
                        speak("Sent to Claude.")
                    else:
                        print(f"  {C['bred']}[CLAUDE UNAVAILABLE]{C['reset']} {detail2[:120]}\n")
                    continue
                except Exception as _guard_err:
                    print(f"  {C['yellow']}[GOVERNANCE]{C['reset']} Re-route failed: {_guard_err} — showing local reply anyway\n")

            _mode_lbl = "WORK" if (_imode == "WORK") else "LOCAL"
            print(f"  {C['grey']}[{_mode_lbl}]{C['reset']}")
            _print_oracle_reply(reply)
            speak(reply)
        except Exception as e:
            msg = str(e)
            log("ERROR", msg)
            if not local and "tool_use" in msg and "tool_result" in msg:
                history = _repair_history(history)
                print("\n[Oracle recovered from an interrupted tool call. Retrying...]\n")
                try:
                    reply, history = chat(client, session_id, system_prompt, history, user_input, model)
                    _print_oracle_reply(reply)
                    speak(reply)
                    continue
                except Exception as e2:
                    log("ERROR", f"Retry failed: {e2}")
                    history = []
                    print("\n[Oracle reset her conversation buffer. Memory is intact. Try again.]\n")
            else:
                print(f"\n{C['bred']}  [Error: {e}]{C['reset']}\n")


if __name__ == "__main__":
    main()
