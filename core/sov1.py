"""
SOV1.AI — The Operator
You type what you want. SOV1 looks at your screen, decides the steps,
and operates the mouse/keyboard to do it.

Noah's rule, enforced here:
  - Acts on its own when it's confident what you want.
  - Asks you only when it's unsure.
  - ALWAYS confirms before anything irreversible (send/delete/buy/post).

Run: python core/sov1.py   (or double-click SOV1.bat)
Abort anytime: slam the mouse into a screen corner.
"""

import os
import sys
import io
import time
import base64
from pathlib import Path

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import computer_control as cc
from audit_log import log
from llm import is_local, is_api_independent, require_local, make_client, get_model, to_openai_tools, image_block
MAX_TOKENS = 2048
MAX_STEPS = 25  # safety cap on actions per goal
BROWSER_OPEN_WAIT = 3.0    # seconds to wait after opening Chrome/Edge/Firefox
TYPE_SETTLE_WAIT  = 0.5    # seconds to wait after type_text before screenshot

# ── Overnight / unattended safety ─────────────────────────────────────────────
# Set SAFE_SLEEP_MODE = True to disable all physical desktop actions.
# ORACLE can still think and propose — it just cannot move the mouse or keyboard.
SAFE_SLEEP_MODE = False

_BROWSER_NAMES = {"chrome", "msedge", "firefox", "brave", "opera"}

# ── Loop guard — stop repeated same-action loops ──────────────────────────────
from collections import deque
_recent_actions: deque = deque(maxlen=6)   # (tool_name, key_arg) pairs
_LOOP_GUARD_THRESHOLD = 3                  # same call 3 times in last 6 → stop

# ── Batch controller — extended action batches with progress verification ─────
from action_batch import (
    get_batch_controller, reset_batch_controller, DEFAULT_BATCH_LIMIT,
    BatchController,
)
# Module-level controller so main() can send commands to a running task
_active_bc: BatchController = reset_batch_controller()

# ── Targeted input — Notepad gate + typing loop guard ─────────────────────────
from targeted_input import (
    check_notepad_fallback, get_typing_guard, reset_typing_guard,
    inject_text, action_diagnostic, TypingLoopGuard,
)
_typing_guard: TypingLoopGuard = get_typing_guard()

# Current task goal — used by Notepad gate and ACTION_DIAGNOSTIC
_current_goal: str = ""

SYSTEM = """You are SOV1.AI, operating Noah Hawkes' Windows 11 PC directly.
You see the screen through screenshots and control the real mouse and keyboard.

YOUR OPERATING RULES (Noah set these):
1. When you are confident what Noah wants, ACT — don't ask permission for ordinary
   things (opening apps, clicking, typing, navigating, organizing files).
2. Ask Noah a question ONLY when you genuinely cannot tell what he wants, or you're
   stuck and need direction.
3. ALWAYS use ask_confirmation before anything irreversible or that leaves the
   machine: sending a message/email, posting publicly, deleting files, making a
   purchase, submitting a form, changing account settings.
4. Work in small visible steps. After acting, look at a fresh screenshot to confirm
   it worked before continuing.
5. When the goal is achieved, call task_done with a short summary.
6. Screenshots may be scaled down to save space. Give click coordinates exactly
   as they appear ON THE SCREENSHOT you see — the system scales them to the real
   screen for you. Don't try to compensate for resolution yourself.
7. SENDING MESSAGES: After you type text into a chat box, search bar, or message
   field, you MUST actually send/submit it — press the 'enter' key, or click the
   send button (often a small arrow/paper-plane icon to the right of or below the
   box). Typing without sending does nothing. After sending, take a screenshot to
   CONFIRM the message actually posted. If it didn't send, click directly on the
   send button. Never assume it sent — verify.
8. FINDING WINDOWS: To get to an app (ChatGPT, Chrome, etc.), use focus_window
   with a word from its title FIRST — don't hunt the taskbar. It's reliable.
9. LEARN AND SPEED UP: The instant something fails and you find what works, call
   remember_lesson with a short, concrete note (e.g. what to click, what to
   avoid). Those lessons load on every future run so you get faster. Also record
   a lesson when you discover a faster path.
10. AUTONOMOUS DECISION MAKING:
    - You have an ask_oracle tool. Use it when you need context about what ORACLE knows,
      what the active project is, what is blocked, or what the next recommended step is.
    - If Noah says "what should I do" or "auto" or gives a vague goal, call ask_oracle
      first, then act on the recommendation it returns.
    - ask_oracle never moves the mouse — it only reads ORACLE's state files.
    - If ask_oracle returns "APPROVAL REQUIRED", stop and tell Noah. Do not act.
11. TYPING RULES — READ CAREFULLY:
    - NEVER open Notepad as a workaround for typing into Claude, ChatGPT, or any browser.
      If you can't type into an app, stop and report — do not fall back to Notepad.
    - To type into ChatGPT or Claude:  focus_window("ChatGPT") → paste_text("your text")
    - To type into a terminal:         focus_window("PowerShell") → paste_text("command")
    - To write a file:                 use write_file() directly, never via Notepad
    - Only open Notepad if Noah says "open Notepad" or "use Notepad" explicitly.
    - After paste_text(), check the screenshot to verify the text appeared before continuing.
    - If text did not appear after 2 tries, call ask_noah — do NOT keep clicking.

You are decisive and competent. You are Noah's operator, acting as him, for him."""

# Used in operate_local() for the text-model decision step only.
# Screenshot instructions are removed because the two-stage loop provides a
# text observation before each decision — the text model never takes screenshots.
_LOCAL_DECISION_SYSTEM = """You are SOV1.AI's action planner for Noah Hawkes' Windows 11 PC.

You will receive a text description of the current screen state and a goal.
Your job: decide the single next action using the available tools.

RULES:
1. If the goal is already answered by the screen observation, call task_done with a clear summary.
2. If you need to interact with the screen (click, type, open, focus), call the appropriate tool.
3. ALWAYS use ask_confirmation before anything irreversible: sending, deleting, buying, posting.
4. Use ask_noah only when you genuinely cannot determine what Noah wants.
5. After each action the screen will be re-observed automatically — do NOT call take_screenshot.
6. When the goal is complete, call task_done.
7. If the goal is vague (e.g. "what should I do", "auto", "next step"), call ask_oracle first
   to get ORACLE's current state and recommendation, then act on the recommendation.
8. If ask_oracle returns APPROVAL REQUIRED, stop and report — do not act autonomously.

You are decisive and competent. Act on the screen description you are given."""

TOOLS = [
    {"name": "take_screenshot", "description": "Capture the current screen to see what's on it. Do this first and after actions.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "move_and_click", "description": "Move the mouse to (x,y) and click. Use screen coordinates from the screenshot.",
     "input_schema": {"type": "object", "properties": {
         "x": {"type": "integer"}, "y": {"type": "integer"},
         "button": {"type": "string", "enum": ["left", "right"]},
         "double": {"type": "boolean", "description": "Double-click if true"}},
         "required": ["x", "y"]}},
    {"name": "type_text", "description": "Type text on the keyboard wherever the cursor/focus currently is.",
     "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    {"name": "press_key", "description": "Press a single key like enter, tab, esc, backspace, win, down, up.",
     "input_schema": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}},
    {"name": "hotkey", "description": "Press a key combo, e.g. ['ctrl','c'] or ['win','r'] or ['alt','tab'].",
     "input_schema": {"type": "object", "properties": {"keys": {"type": "array", "items": {"type": "string"}}}, "required": ["keys"]}},
    {"name": "open_program", "description": "Open a program by name via the Run dialog, e.g. 'notepad', 'chrome', 'explorer'.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "focus_window", "description": "Jump straight to a window by a word in its title, e.g. 'ChatGPT' or 'Chrome'. Use this instead of hunting the taskbar — it's far more reliable.",
     "input_schema": {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]}},
    {"name": "remember_lesson", "description": "Save a lesson the moment you learn what works or what failed, so you're faster next time. e.g. 'ChatGPT input box is bottom-center — click there to focus.'",
     "input_schema": {"type": "object", "properties": {"lesson": {"type": "string"}}, "required": ["lesson"]}},
    {"name": "scroll", "description": "Scroll the screen. Positive scrolls up, negative scrolls down.",
     "input_schema": {"type": "object", "properties": {"amount": {"type": "integer"}}, "required": ["amount"]}},
    {"name": "ask_confirmation", "description": "REQUIRED before any irreversible action (send/delete/buy/post/submit). Ask Noah yes/no.",
     "input_schema": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}},
    {"name": "ask_noah", "description": "Ask Noah for direction when you genuinely can't tell what he wants.",
     "input_schema": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}},
    {"name": "task_done", "description": "Call when the goal is complete.",
     "input_schema": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}},
    {"name": "paste_text", "description": "Paste text via clipboard — use this instead of type_text for long text, special characters, URLs, or code. Much faster and more reliable.",
     "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    {"name": "right_click", "description": "Right-click at (x,y) to open a context menu.",
     "input_schema": {"type": "object", "properties": {
         "x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]}},
    {"name": "drag", "description": "Click and drag from one point to another. Use for moving files, sliders, or UI elements.",
     "input_schema": {"type": "object", "properties": {
         "x1": {"type": "integer"}, "y1": {"type": "integer"},
         "x2": {"type": "integer"}, "y2": {"type": "integer"},
         "duration": {"type": "number", "description": "Seconds for the drag (default 0.5)"}},
         "required": ["x1", "y1", "x2", "y2"]}},
    {"name": "maximize_window", "description": "Maximize a window by a word in its title, or the active window if no title given.",
     "input_schema": {"type": "object", "properties": {"title_fragment": {"type": "string"}}}},
    {"name": "minimize_window", "description": "Minimize a window by a word in its title.",
     "input_schema": {"type": "object", "properties": {"title_fragment": {"type": "string"}}}},
    {"name": "resize_window", "description": "Resize a window to exact pixel dimensions.",
     "input_schema": {"type": "object", "properties": {
         "title_fragment": {"type": "string"},
         "width": {"type": "integer"}, "height": {"type": "integer"}},
         "required": ["title_fragment", "width", "height"]}},
    {"name": "move_window", "description": "Move a window to a specific screen position.",
     "input_schema": {"type": "object", "properties": {
         "title_fragment": {"type": "string"},
         "x": {"type": "integer"}, "y": {"type": "integer"}},
         "required": ["title_fragment", "x", "y"]}},
    {"name": "select_all", "description": "Select all text/items in the current focus (Ctrl+A).",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "copy_selection", "description": "Copy the current selection to clipboard (Ctrl+C). Returns what was copied.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "wait_for_screen_change", "description": "Wait up to N seconds for the screen to visually change after an action. Use after clicking buttons to confirm something happened.",
     "input_schema": {"type": "object", "properties": {
         "timeout": {"type": "number", "description": "Max seconds to wait (default 5)"},
         "interval": {"type": "number", "description": "Poll interval in seconds (default 0.5)"}}}},
    {"name": "write_file", "description": "Write text content to a file on disk. Use this instead of opening Notepad to write files. Creates parent directories automatically. Returns confirmation with the absolute path.",
     "input_schema": {"type": "object", "properties": {
         "path": {"type": "string", "description": "Absolute or relative path to write (e.g. C:/Users/noahh/Desktop/note.txt)"},
         "content": {"type": "string", "description": "Text content to write"},
         "append": {"type": "boolean", "description": "If true, append to existing file instead of overwriting"}},
         "required": ["path", "content"]}},
    {"name": "read_file", "description": "Read the text content of a file on disk. Returns the content (up to 8000 chars). Use this to check file contents without opening an app.",
     "input_schema": {"type": "object", "properties": {
         "path": {"type": "string", "description": "Absolute or relative path to read"},
         "lines": {"type": "integer", "description": "Max number of lines to read (default: all)"}},
         "required": ["path"]}},
    {"name": "ask_oracle", "description": "Ask ORACLE for its current state and recommended next action. Returns mode, active project, blocker, pending approvals, and exactly one next-step recommendation. Use this to decide what to do autonomously without waiting for Noah.",
     "input_schema": {"type": "object", "properties": {
         "question": {"type": "string", "description": "Optional: specific question about state (e.g. 'what is blocked?', 'what should I build next?'). If omitted, returns full state summary."}}}},
]


# Scale factor between the downscaled screenshot SOV1 sees and the real screen.
# Click coordinates come back in screenshot-space and are multiplied by this.
_scale = 1.0
MAX_SHOT_WIDTH = 1280


import re

# ── Lessons: SOV1 learns from failures and gets faster across runs ─────────────
LESSONS_FILE = ROOT / "Memory" / "sov1_lessons.txt"


def _save_lesson(text: str):
    LESSONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    line = text.strip().replace("\n", " ")
    # Avoid duplicates
    existing = load_lessons(limit=500)
    if line and line not in existing:
        with open(LESSONS_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    log("LESSON", line[:120])


def load_lessons(limit=25):
    if not LESSONS_FILE.exists():
        return []
    lines = [l.strip() for l in LESSONS_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    return lines[-limit:]


# Code-level rail: never type these, no matter who asks (including ChatGPT).
_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,16}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def _hard_block_text(text: str):
    """Return a label if the text contains secrets that must never be typed."""
    if _CARD_RE.search(text):
        return "a credit/debit card number"
    if _SSN_RE.search(text):
        return "a Social Security number"
    return None


def _screenshot_block():
    """
    Screenshot the screen, shrink to cut token cost, return image block in correct format.
    Records scale factor so click coords map back to the real screen.
    """
    global _scale
    import pyautogui
    from PIL import Image  # noqa
    img = pyautogui.screenshot()
    real_w, real_h = img.size
    if real_w > MAX_SHOT_WIDTH:
        ratio = MAX_SHOT_WIDTH / real_w
        img = img.resize((MAX_SHOT_WIDTH, int(real_h * ratio)))
        _scale = real_w / MAX_SHOT_WIDTH
    else:
        _scale = 1.0
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.standard_b64encode(buf.getvalue()).decode()
    return image_block(b64, "image/png")


def _prune_images(history, keep_last=2):
    """
    Strip screenshots from all but the most recent `keep_last` tool results.
    SOV1 only needs to see the current screen — old screenshots just burn tokens
    and trip the rate limit. Replaces stripped images with a short text note.
    """
    image_blocks = []
    for msg in history:
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "image":
                image_blocks.append(("msg", msg, block))
            elif block.get("type") == "tool_result" and isinstance(block.get("content"), list):
                for c in block["content"]:
                    if isinstance(c, dict) and c.get("type") == "image":
                        image_blocks.append(("tr", block, c))
    strip = image_blocks[:-keep_last] if keep_last else image_blocks
    for kind, parent, blk in strip:
        parent["content"] = [b for b in parent["content"] if b is not blk]
        parent["content"].append({"type": "text", "text": "[earlier screenshot omitted]"})


def _is_safe_sleep_blocked(name: str) -> str | None:
    """Return a refusal message if SAFE_SLEEP_MODE blocks this action, else None."""
    if not SAFE_SLEEP_MODE:
        return None
    PASSIVE_OK = {"take_screenshot", "remember_lesson", "ask_noah", "task_done", "ask_confirmation"}
    if name not in PASSIVE_OK:
        return (f"SAFE_SLEEP_MODE is active — desktop action '{name}' is blocked. "
                f"ORACLE is in observe-only mode. No mouse, keyboard, or browser actions "
                f"are permitted while Noah is away.")
    return None


def _loop_guard_check(name: str, key_arg: str) -> bool:
    """Return True if this action is looping (same call repeated too many times)."""
    _recent_actions.append((name, key_arg))
    count = sum(1 for n, k in _recent_actions if n == name and k == key_arg)
    return count >= _LOOP_GUARD_THRESHOLD


def _browser_already_open() -> str | None:
    """Return the window title of an open browser window, or None if none found."""
    try:
        import pygetwindow as gw
        for w in gw.getAllWindows():
            t = w.title.lower()
            if any(b in t for b in ["chrome", "edge", "firefox", "brave", "google"]):
                return w.title
    except Exception:
        pass
    return None


def _navigate_address_bar(url: str) -> tuple[str, object]:
    """Focus address bar via Ctrl+L, type URL, press Enter. Returns (result, screenshot)."""
    cc.hotkey("ctrl", "l")
    time.sleep(0.4)
    cc.type_text(url)
    time.sleep(0.2)
    cc.press("enter")
    time.sleep(2.5)   # wait for page to start loading
    return f"Navigated to {url}", _screenshot_block()


def _ask_oracle(question: str = "") -> str:
    """
    Query ORACLE's live state and return a structured answer SOV1 can act on.
    Reads Memory JSON files directly — no subprocess, no model call.
    Returns a plain-text block with mode, project, blocker, queue, and one next action.
    """
    import json as _json
    from pathlib import Path as _Path

    mem = ROOT / "Memory"

    def _rj(p: _Path):
        try:
            return _json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    # --- Resident Runtime live state (primary) ---
    rt_live = False
    rt_mode = None
    rt_next_step = None
    try:
        import sys as _sys
        _core = str(ROOT / "core")
        if _core not in _sys.path:
            _sys.path.insert(0, _core)
        from resident_runtime import _load_runtime_state
        rs = _load_runtime_state()
        if rs.get("status") == "running":
            rt_live = True
            rt_mode = rs.get("last_priority") or None
            rt_next_step = rs.get("last_action") or None
    except Exception:
        pass

    # Session
    sess = _rj(mem / "session_state.json") or {}
    mode = rt_mode or sess.get("mode", "UNKNOWN")

    # Project
    proj_raw = _rj(mem / "project_states.json") or {}
    if isinstance(proj_raw, dict):
        states = list(proj_raw.values())
    elif isinstance(proj_raw, list):
        states = proj_raw
    else:
        states = []
    states = [s for s in states if isinstance(s, dict)]
    if states:
        p = max(states, key=lambda x: x.get("updated_at", ""))
        project_name   = p.get("project_name", "UNKNOWN")
        blocker        = p.get("current_blocker", "") or ""
        next_step      = p.get("next_recommended_step", "") or ""
        next_reason    = p.get("next_step_reason", "") or ""
        confidence     = int(p.get("confidence", 0.5) * 100)
        last_step      = p.get("last_completed_step", "") or ""
    else:
        project_name = blocker = next_step = next_reason = last_step = "UNKNOWN"
        confidence = 0

    # Queue
    rm_idx = _rj(mem / "remember_me" / "index.json") or {}
    mem_pending = sum(1 for v in rm_idx.values() if isinstance(v, dict) and v.get("status") == "pending") \
                  if isinstance(rm_idx, dict) else 0
    vid_raw = _rj(mem / "video_observation_candidates.json") or []
    vid_pending = sum(1 for c in vid_raw if isinstance(c, dict) and c.get("status") == "pending")
    mc_raw = _rj(mem / "mindcoin_ledger.json") or {}
    mc_events = mc_raw.get("events", [])
    mc_pending = sum(1 for e in mc_events if isinstance(e, dict) and e.get("approval_status") == "pending")

    # Ollama
    try:
        from llm import check_ollama
        ollama_ok, _ = check_ollama()
    except Exception:
        ollama_ok = False

    total_pending = mem_pending + vid_pending

    # Prefer runtime next_step when resident_runtime is live
    if rt_live and rt_next_step:
        next_step = rt_next_step

    # One next action (mirror of dashboard logic)
    if not ollama_ok:
        action = "ORACLE cannot reason: Ollama is offline. Start Ollama first."
        approval = False
    elif mode in ("BLOCKED", "ERROR_RECOVERY"):
        action = f"Session is in {mode}. Run ACTION_DIAGNOSTIC before anything else."
        approval = False
    elif blocker and blocker != "UNKNOWN":
        action = f"Resolve blocker: {blocker}"
        approval = False
    elif total_pending > 0:
        action = f"Review {total_pending} pending memory/video approval(s) — Noah must approve."
        approval = True
    elif next_step and next_step != "UNKNOWN":
        action = next_step
        approval = False
    else:
        action = "Run continuity export: python core/continuity_export.py --export"
        approval = False

    q = question.lower().strip()
    live_tag = "  [RUNTIME LIVE]" if rt_live else ""
    lines = [
        f"ORACLE STATE — {mode}{live_tag}",
        f"  Project      : {project_name} (confidence {confidence}%)",
        f"  Last step    : {last_step[:80]}",
        f"  Blocker      : {blocker or 'none'}",
        f"  Pending queue: {mem_pending} memory  {vid_pending} video  {mc_pending} MindCoin",
        f"  Ollama       : {'running' if ollama_ok else 'OFFLINE'}",
        "",
        f"ONE NEXT ACTION{'  [APPROVAL REQUIRED]' if approval else ''}:",
        f"  {action}",
    ]
    if next_reason and not approval and not blocker:
        lines.append(f"  Reason: {next_reason[:100]}")

    # If a specific question was asked, filter/augment
    if "block" in q:
        lines.insert(0, f"[Question: blockers] Blocker = '{blocker or 'none'}'")
    elif "next" in q or "build" in q:
        lines.insert(0, f"[Question: next step] → {next_step or 'none recorded'}")
    elif "pend" in q or "approv" in q:
        lines.insert(0, f"[Question: pending] {total_pending} items need Noah's approval.")

    return "\n".join(lines)


def _run_tool(name, inp):
    """Execute a hands tool. Returns (result_text, screenshot_block_or_None, control_flag)."""

    # ── Overnight safety gate ─────────────────────────────────────────────────
    blocked_msg = _is_safe_sleep_blocked(name)
    if blocked_msg:
        return blocked_msg, None, None

    if name == "take_screenshot":
        return "Screenshot taken.", _screenshot_block(), None

    if name == "move_and_click":
        try:
            x, y = int(inp["x"]), int(inp["y"])
        except (KeyError, ValueError, TypeError):
            return (f"Bad coordinates {inp!r}. Pass x and y as separate integers, "
                    f"e.g. {{'x': 186, 'y': 45}}."), _screenshot_block(), None
        # Map screenshot-space coordinates back to the real (full-res) screen
        x, y = int(round(x * _scale)), int(round(y * _scale))
        btn = inp.get("button", "left")
        if inp.get("double"):
            r = cc.double_click(x, y)
        else:
            r = cc.click(x, y, button=btn)
        time.sleep(0.4)
        return r, _screenshot_block(), None

    if name == "type_text":
        blocked = _hard_block_text(inp["text"])
        if blocked:
            log("BLOCKED", f"refused to type: {blocked}")
            return (f"REFUSED to type that — it looks like {blocked}. "
                    f"I never type passwords, card numbers, or SSNs. Skipping."), _screenshot_block(), None

        # Typing loop guard — check unverified count
        typing_stop = _typing_guard.check(current_goal=_current_goal)
        if typing_stop:
            return (f"{typing_stop}\n\n"
                    f"{action_diagnostic(intended_target=_current_goal, guard=_typing_guard)}"), \
                   _screenshot_block(), None

        # Legacy loop guard
        if _loop_guard_check("type_text", inp["text"][:30]):
            return ("Loop guard: type_text repeated 3 times without confirmed progress. "
                    "Stopping browser input chain. No further typing attempted."), _screenshot_block(), None

        from targeted_input import _screen_hash as _sh
        h_before = _sh()
        r = cc.type_text(inp["text"])
        time.sleep(TYPE_SETTLE_WAIT)
        h_after = _sh()
        verified = h_before != h_after
        _typing_guard.record("type_text", inp["text"][:30], verified=verified)
        shot = _screenshot_block()
        r += f" | {'Text verified — screen changed.' if verified else 'UNVERIFIED — screen hash unchanged. Check that the input field has focus before typing.'}"
        return r, shot, None

    if name == "press_key":
        r = cc.press(inp["key"])
        time.sleep(0.3)
        return r, _screenshot_block(), None

    if name == "hotkey":
        r = cc.hotkey(*inp["keys"])
        time.sleep(0.4)
        return r, _screenshot_block(), None

    if name == "open_program":
        prog = inp["name"].lower().strip()

        # ── Notepad gate — block Notepad unless Noah explicitly requested it ──
        notepad_block = check_notepad_fallback(prog, current_goal=_current_goal)
        if notepad_block:
            _typing_guard.record("open_program", prog, verified=False)
            return notepad_block, _screenshot_block(), None

        # ── Record for typing loop guard ──────────────────────────────────────
        _typing_guard.record("open_program", prog, verified=False)
        typing_stop = _typing_guard.check(current_goal=_current_goal)
        if typing_stop:
            return (f"{typing_stop}\n\n"
                    f"{action_diagnostic(intended_target=_current_goal, guard=_typing_guard)}"), \
                   _screenshot_block(), None

        # ── Browser state check: focus existing instead of opening another ────
        if any(b in prog for b in _BROWSER_NAMES) or prog == "chrome":
            existing = _browser_already_open()
            if existing:
                focus_r = cc.focus_window(existing.split(" - ")[0])
                time.sleep(0.8)
                shot = _screenshot_block()
                return (f"Browser already open ({existing[:60]}). Focused existing window — "
                        f"no new Chrome opened. Use Ctrl+L to navigate if needed. | {focus_r}"), shot, None

            # No browser found — actually open it
            if _loop_guard_check("open_program", prog):
                return (f"Loop guard: open_program('{prog}') called 3 times in a row "
                        f"without progress. Stopping. Check if Chrome is opening off-screen "
                        f"or taking longer than expected."), _screenshot_block(), None

            r = cc.open_program(prog)
            time.sleep(BROWSER_OPEN_WAIT)    # longer wait for browser cold start
            shot = _screenshot_block()
            return (f"{r} | Browser opened. Waiting complete. "
                    f"Use Ctrl+L to focus the address bar and navigate."), shot, None

        # Non-browser program — standard open
        if _loop_guard_check("open_program", prog):
            return (f"Loop guard: open_program('{prog}') repeated 3 times. Stopping."), _screenshot_block(), None
        r = cc.open_program(prog)
        time.sleep(1.5)
        return r, _screenshot_block(), None

    if name == "focus_window":
        title = inp["title"]
        _typing_guard.record("focus_window", title.lower()[:30], verified=False)
        typing_stop = _typing_guard.check(current_goal=_current_goal)
        if typing_stop:
            return (f"{typing_stop}\n\n"
                    f"{action_diagnostic(intended_target=title, guard=_typing_guard)}"), \
                   _screenshot_block(), None
        if _loop_guard_check("focus_window", title.lower()[:20]):
            return (f"Loop guard: focus_window('{title}') repeated 3 times without confirmed "
                    f"focus. Try open_program instead, or check if window title changed."), _screenshot_block(), None
        r = cc.focus_window(title)
        time.sleep(0.6)
        return r, _screenshot_block(), None

    if name == "remember_lesson":
        _save_lesson(inp["lesson"])
        return f"Lesson saved — I'll remember this next time: {inp['lesson']}", None, None

    if name == "scroll":
        r = cc.scroll(inp["amount"])
        return r, _screenshot_block(), None

    if name == "ask_confirmation":
        print(f"\n*** SOV1 needs your OK: {inp['question']}")
        ans = input("    Type 'yes' to proceed, anything else to skip: ").strip().lower()
        ok = ans in ("y", "yes")
        return ("Noah approved." if ok else "Noah declined — do not do it."), None, None

    if name == "ask_noah":
        print(f"\n*** SOV1 asks: {inp['question']}")
        ans = input("    You: ").strip()
        return f"Noah says: {ans}", None, None

    if name == "task_done":
        return inp["summary"], None, "DONE"

    # ── New hands ─────────────────────────────────────────────────────────────

    if name == "paste_text":
        # Typing loop guard
        typing_stop = _typing_guard.check(current_goal=_current_goal)
        if typing_stop:
            return (f"{typing_stop}\n\n"
                    f"{action_diagnostic(intended_target=_current_goal, guard=_typing_guard)}"), \
                   _screenshot_block(), None
        if _loop_guard_check("paste_text", inp["text"][:30]):
            return "Loop guard: paste_text repeated 3 times. Stopping.", _screenshot_block(), None

        from targeted_input import _screen_hash as _sh
        h_before = _sh()
        r = cc.paste_text(inp["text"])
        time.sleep(TYPE_SETTLE_WAIT)
        h_after = _sh()
        verified = h_before != h_after
        _typing_guard.record("paste_text", inp["text"][:30], verified=verified)
        shot = _screenshot_block()
        r += f" | {'Text verified — screen changed.' if verified else 'UNVERIFIED — screen unchanged. Focus the input field first, then paste again.'}"
        return r, shot, None

    if name == "right_click":
        x, y = int(inp.get("x", 0) * _scale), int(inp.get("y", 0) * _scale)
        r = cc.right_click(x, y)
        time.sleep(0.4)
        return r, _screenshot_block(), None

    if name == "drag":
        x1 = int(inp["x1"] * _scale); y1 = int(inp["y1"] * _scale)
        x2 = int(inp["x2"] * _scale); y2 = int(inp["y2"] * _scale)
        dur = float(inp.get("duration", 0.5))
        r = cc.drag(x1, y1, x2, y2, dur)
        time.sleep(0.5)
        return r, _screenshot_block(), None

    if name == "maximize_window":
        r = cc.maximize_window(inp.get("title_fragment"))
        time.sleep(0.4)
        return r, _screenshot_block(), None

    if name == "minimize_window":
        r = cc.minimize_window(inp.get("title_fragment"))
        time.sleep(0.3)
        return r, None, None

    if name == "resize_window":
        r = cc.resize_window(inp["title_fragment"], inp["width"], inp["height"])
        time.sleep(0.4)
        return r, _screenshot_block(), None

    if name == "move_window":
        r = cc.move_window(inp["title_fragment"], inp["x"], inp["y"])
        time.sleep(0.3)
        return r, _screenshot_block(), None

    if name == "select_all":
        r = cc.select_all()
        time.sleep(0.2)
        return r, _screenshot_block(), None

    if name == "copy_selection":
        r = cc.copy_selection()
        return r, None, None

    if name == "wait_for_screen_change":
        timeout = float(inp.get("timeout", 5.0))
        interval = float(inp.get("interval", 0.5))
        r = cc.wait_for_screen_change(timeout, interval)
        shot = _screenshot_block()
        return r, shot, None

    if name == "write_file":
        raw_path = inp.get("path", "")
        content  = inp.get("content", "")
        append   = bool(inp.get("append", False))
        if not raw_path:
            return "write_file: path is required.", None, None
        try:
            p = Path(raw_path).expanduser()
            p.parent.mkdir(parents=True, exist_ok=True)
            mode = "a" if append else "w"
            p.write_text(content, encoding="utf-8") if not append else \
                p.open("a", encoding="utf-8").write(content)
            log("WRITE_FILE", f"{'appended' if append else 'wrote'} {len(content)} chars -> {p}")
            return (f"{'Appended' if append else 'Wrote'} {len(content)} chars to {p}. "
                    f"File now exists: {p.exists()}."), None, None
        except Exception as e:
            return f"write_file failed: {e}", None, None

    if name == "read_file":
        raw_path = inp.get("path", "")
        max_lines = int(inp.get("lines", 0)) or None
        if not raw_path:
            return "read_file: path is required.", None, None
        try:
            p = Path(raw_path).expanduser()
            if not p.exists():
                return f"read_file: file not found: {p}", None, None
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            if max_lines:
                lines = lines[:max_lines]
            content = "\n".join(lines)
            if len(content) > 8000:
                content = content[:8000] + f"\n...[truncated at 8000 chars, file has {p.stat().st_size} bytes]"
            log("READ_FILE", f"read {len(lines)} lines from {p}")
            return f"Contents of {p}:\n{content}", None, None
        except Exception as e:
            return f"read_file failed: {e}", None, None

    if name == "ask_oracle":
        return _ask_oracle(inp.get("question", "")), None, None

    return f"Unknown tool: {name}", None, None


def operate(client, goal, model=None, system=None, batch_limit=None):
    global _active_bc, _current_goal
    _current_goal = goal
    reset_typing_guard()
    if model is None:
        model = get_model(vision=True)
    system = system or SYSTEM
    lessons = load_lessons()
    if lessons:
        system += ("\n\nLESSONS YOU'VE ALREADY LEARNED (apply these to move fast and "
                   "avoid repeating mistakes):\n" + "\n".join(f"- {l}" for l in lessons))
    log("SOV1", f"Goal: {goal}")

    # Set up batch controller — preserves AUTORUN SAFE / DRY RUN flags from main()
    _active_bc = reset_batch_controller(
        batch_limit=batch_limit or DEFAULT_BATCH_LIMIT,
        autorun_safe=_active_bc.autorun_safe,
        dry_run=_active_bc.dry_run,
        safe_sleep=SAFE_SLEEP_MODE or _active_bc.safe_sleep,
    )
    bc = _active_bc
    bc.start_task(goal)

    history = [{"role": "user", "content": [
        {"type": "text", "text": f"Goal: {goal}\n\nLook at the screen and do it."},
        _screenshot_block(),
    ]}]
    done_text = None

    for step in range(MAX_STEPS):
        if bc.halted:
            print("\n[STOP ORACLE — action loop halted.]")
            break

        _prune_images(history)  # keep only the latest screenshots — saves tokens
        resp = client.messages.create(
            model=model, max_tokens=MAX_TOKENS,
            system=system, messages=history, tools=TOOLS,
        )
        history.append({"role": "assistant", "content": resp.content})

        # Print any narration
        for b in resp.content:
            if getattr(b, "type", None) == "text" and b.text.strip():
                print(f"\nSOV1: {b.text.strip()}")

        if resp.stop_reason != "tool_use":
            return  # Claude stopped without a tool — end

        results = []
        done = False
        for b in resp.content:
            if getattr(b, "type", None) == "tool_use":
                print(f"  [SOV1 action: {b.name}]")

                # ── Batch safety gates ────────────────────────────────────────
                blocked = (
                    bc.is_safe_sleep_blocked(b.name)
                    or bc.is_mouse_disabled(b.name)
                )
                if blocked:
                    text = blocked
                    shot = None
                    flag = None
                elif bc.dry_run:
                    text = bc.is_dry_run(b.name, b.input) or f"[DRY RUN] {b.name}"
                    shot = None
                    flag = None
                else:
                    approval_msg = bc.requires_approval(b.name, b.input)
                    loop_msg = bc.loop_guard_check(b.name, str(b.input)[:60])
                    if approval_msg:
                        text = approval_msg
                        shot = None
                        flag = None
                        done = True
                    elif loop_msg:
                        text = loop_msg
                        shot = None
                        flag = None
                        done = True
                    else:
                        h_before = bc.screen_hash()
                        try:
                            text, shot, flag = _run_tool(b.name, b.input)
                            bc.record_success(b.name, str(b.input)[:60])
                        except Exception as e:
                            log("ERROR", f"action {b.name} failed: {e}")
                            text = (f"That action errored: {e}. Take a fresh screenshot and "
                                    f"try a different approach.")
                            shot, flag = _screenshot_block(), None
                            bc.record_failure(b.name, str(b.input)[:60])
                        h_after = bc.screen_hash()
                        bc.record_action(b.name, str(b.input)[:60], text, h_before, h_after)

                content = [{"type": "text", "text": text}]
                if shot:
                    content.append(shot)
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": content})
                if flag == "DONE":
                    print(f"\n=== DONE: {text} ===")
                    done = True
                    done_text = text

        history.append({"role": "user", "content": results})
        if done:
            return done_text

        # ── Batch checkpoint after each step ─────────────────────────────────
        if bc.batch_full():
            cp = bc.checkpoint(goal)
            print(bc.checkpoint_report(cp))
            if not cp.should_continue:
                print("[Batch complete. Say 'CONTINUE ORACLE' to run the next batch.]")
                return None

    print("\n[Reached step limit. Tell me to continue if it's not finished.]")
    return None


def _observe(client, vision_model: str, goal: str, shot_block: dict) -> str:
    """
    Stage 1 of two-stage local loop.
    Sends the screenshot to the vision model with NO tools argument.
    Returns a plain-text description of what is on the screen.
    qwen2.5-vl does not support tools — this call never passes them.
    """
    messages = [{"role": "user", "content": [
        {"type": "text", "text": (
            f"Goal context: {goal}\n\n"
            "Describe exactly what you see on the screen right now. "
            "List windows, text, buttons, and layout. Be specific. "
            "Do not take any action — observation only."
        )},
        shot_block,
    ]}]
    resp = client.chat.completions.create(
        model=vision_model,
        max_tokens=1024,
        messages=messages,
        # No tools= — vision model does not support tool calling
    )
    return resp.choices[0].message.content or "(no observation returned)"


def operate_local(client, goal, model, system=None, text_model=None, batch_limit=None):
    """
    Two-stage local operate loop with batch controller.

    Stage 1 — vision model (model): receives screenshot, no tools, returns plain-text observation.
    Stage 2 — text model (text_model, default qwen2.5:7b): receives observation + goal + tools,
               decides next action. No images are ever sent to the text model.

    This split exists because qwen2.5-vl does not support the tools= parameter.
    """
    import json
    global _active_bc, _current_goal
    _current_goal = goal
    reset_typing_guard()

    if text_model is None:
        text_model = get_model(vision=False)

    # Vision model uses the full SYSTEM prompt; text decision model gets a stripped
    # version that removes all screenshot instructions (the loop handles that via _observe).
    vision_system = system or SYSTEM
    decision_system = _LOCAL_DECISION_SYSTEM
    lessons = load_lessons()
    if lessons:
        lesson_block = "\n\nLESSONS YOU'VE ALREADY LEARNED:\n" + "\n".join(f"- {l}" for l in lessons)
        vision_system += lesson_block
        decision_system += lesson_block

    # take_screenshot is excluded: the two-stage loop handles screenshots via _observe()
    # before each decision step — the text model must not call it
    oai_tools = [t for t in to_openai_tools(TOOLS) if t["function"]["name"] != "take_screenshot"]
    log("SOV1", f"Goal (local): {goal}")

    # Set up batch controller — preserves AUTORUN SAFE / DRY RUN flags from main()
    _active_bc = reset_batch_controller(
        batch_limit=batch_limit or DEFAULT_BATCH_LIMIT,
        autorun_safe=_active_bc.autorun_safe,
        dry_run=_active_bc.dry_run,
        safe_sleep=SAFE_SLEEP_MODE or _active_bc.safe_sleep,
    )
    bc = _active_bc
    bc.start_task(goal)

    # Stage 1: get initial screen observation from vision model (no tools)
    shot = _screenshot_block()
    observation = _observe(client, model, goal, shot)
    log("SOV1", f"Observation: {observation[:200]}")
    print(f"\n[SOV1 observation]: {observation[:300]}{'...' if len(observation) > 300 else ''}")

    # decision_history accumulates tool-call turns for the text model only (no images)
    decision_history = []
    done_text = None

    for step in range(MAX_STEPS):
        if bc.halted:
            print("\n[STOP ORACLE — action loop halted.]")
            break

        # Stage 2: text model receives current observation + goal, decides tool or done
        user_content = f"Goal: {goal}\n\nCurrent screen observation:\n{observation}"
        decision_history.append({"role": "user", "content": user_content})

        messages = [{"role": "system", "content": decision_system}] + decision_history
        resp = client.chat.completions.create(
            model=text_model, max_tokens=MAX_TOKENS,
            messages=messages, tools=oai_tools,
        )
        msg = resp.choices[0].message
        finish = resp.choices[0].finish_reason

        if msg.content and msg.content.strip():
            print(f"\nSOV1: {msg.content.strip()}")

        # No tool calls — goal answered by observation alone, or model chose to stop
        if finish not in ("tool_calls", "tool_use") or not msg.tool_calls:
            return msg.content or observation

        # Store assistant tool-call turn (text only, no images)
        assistant_entry = {"role": "assistant", "content": msg.content or ""}
        assistant_entry["tool_calls"] = [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls
        ]
        decision_history.append(assistant_entry)

        done = False
        for tc in msg.tool_calls:
            print(f"  [SOV1 action: {tc.function.name}]")
            try:
                inp = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, TypeError):
                inp = {}

            # ── Batch safety gates ────────────────────────────────────────────
            tool_key = str(inp)[:60]
            blocked = (
                bc.is_safe_sleep_blocked(tc.function.name)
                or bc.is_mouse_disabled(tc.function.name)
            )
            if blocked:
                text = blocked
                flag = None
            elif bc.dry_run:
                text = bc.is_dry_run(tc.function.name, inp) or f"[DRY RUN] {tc.function.name}"
                flag = None
            else:
                approval_msg = bc.requires_approval(tc.function.name, inp)
                loop_msg = bc.loop_guard_check(tc.function.name, tool_key)
                if approval_msg:
                    text = approval_msg
                    flag = None
                    done = True
                elif loop_msg:
                    text = loop_msg
                    flag = None
                    done = True
                else:
                    h_before = bc.screen_hash()
                    try:
                        text, _shot, flag = _run_tool(tc.function.name, inp)
                        bc.record_success(tc.function.name, tool_key)
                    except Exception as e:
                        log("ERROR", f"action {tc.function.name} failed: {e}")
                        text = f"That action errored: {e}. Try a different approach."
                        _shot, flag = None, None
                        bc.record_failure(tc.function.name, tool_key)
                    h_after = bc.screen_hash()
                    bc.record_action(tc.function.name, tool_key, text, h_before, h_after)

            # Tool result is always text — screenshots go to vision model, not text model
            decision_history.append({"role": "tool", "tool_call_id": tc.id, "content": text})

            if flag == "DONE":
                print(f"\n=== DONE: {text} ===")
                done = True
                done_text = text

        if done:
            return done_text

        # ── Batch checkpoint after each step ─────────────────────────────────
        if bc.batch_full():
            cp = bc.checkpoint(goal)
            print(bc.checkpoint_report(cp))
            if not cp.should_continue:
                print("[Batch complete. Say 'CONTINUE ORACLE' to run the next batch.]")
                return None

        # Stage 1 again: fresh screenshot → fresh observation for next decision step
        shot = _screenshot_block()
        observation = _observe(client, model, goal, shot)
        log("SOV1", f"Observation step {step + 1}: {observation[:200]}")

    print("\n[Reached step limit. Tell me to continue if it's not finished.]")
    return None


# ── Smoke test ────────────────────────────────────────────────────────────────

def _smoke_test():
    """
    Dry-run verification of browser state check, loop guard, and safe sleep mode.
    Does NOT move the mouse or open any programs.
    """
    global SAFE_SLEEP_MODE
    print("=" * 56)
    print("sov1.py — Browser Fix Smoke Test (dry run)")
    print("=" * 56)

    passed = 0
    failed = 0

    def check(label, result, expected_fragment):
        nonlocal passed, failed
        if isinstance(expected_fragment, bool):
            ok = bool(result) == expected_fragment
        else:
            ok = expected_fragment.lower() in str(result).lower()
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        if not ok:
            print(f"         Expected: '{expected_fragment}'  Got: '{str(result)[:120]}'")
            failed += 1
        else:
            passed += 1

    # 1. SAFE_SLEEP_MODE blocks desktop actions
    SAFE_SLEEP_MODE = True
    r, _, _ = _run_tool("type_text", {"text": "hello"})
    check("SAFE_SLEEP_MODE blocks type_text", r, "safe_sleep_mode")
    r, _, _ = _run_tool("open_program", {"name": "chrome"})
    check("SAFE_SLEEP_MODE blocks open_program", r, "safe_sleep_mode")
    r, _, _ = _run_tool("move_and_click", {"x": 100, "y": 100})
    check("SAFE_SLEEP_MODE blocks move_and_click", r, "safe_sleep_mode")

    # Passive tools allowed
    r, _, _ = _run_tool("remember_lesson", {"lesson": "test lesson"})
    check("SAFE_SLEEP_MODE allows remember_lesson", r, "lesson saved")
    SAFE_SLEEP_MODE = False

    # 2. Loop guard triggers after 3 identical open_program calls
    # Directly test the loop guard logic — do NOT call _run_tool (would fire Win+R for real)
    _recent_actions.clear()
    reset_typing_guard()
    for _ in range(3):
        _recent_actions.append(("open_program", "fakeprog_smoke_test"))
    triggered = _loop_guard_check("open_program", "fakeprog_smoke_test")
    check("Loop guard triggers on 3rd identical open_program", triggered, True)

    # 3. Loop guard triggers on repeated focus_window — same approach, no pyautogui
    _recent_actions.clear()
    reset_typing_guard()
    for _ in range(3):
        _recent_actions.append(("focus_window", "fakewindowtitletest"))
    triggered = _loop_guard_check("focus_window", "fakewindowtitletest")
    check("Loop guard triggers on 3rd identical focus_window", triggered, True)

    # 4. Hard block still works (SSN)
    _recent_actions.clear()
    reset_typing_guard()
    r, _, _ = _run_tool("type_text", {"text": "my SSN is 123-45-6789"})
    check("Hard block refuses SSN", r, "refused")

    # 5. Loop guard resets between goals — test logic only, no pyautogui
    _recent_actions.clear()
    reset_typing_guard()
    # After clear, one append should NOT trigger guard (needs 3 same)
    _recent_actions.append(("focus_window", "somewindow"))
    triggered = _loop_guard_check("focus_window", "somewindow")
    # count is now 2 (one appended + one from _loop_guard_check) — still below threshold of 3
    check("Loop guard does not trigger after reset (1 call)", not triggered, True)

    # 6. write_file and read_file tools
    import tempfile, os as _os
    tmp = Path(tempfile.gettempdir()) / "sov1_smoke_test_rw.txt"
    try:
        r, _, _ = _run_tool("write_file", {"path": str(tmp), "content": "hello SOV1"})
        check("write_file: success message", r, "wrote")
        check("write_file: file exists", tmp.exists(), True)
        r, _, _ = _run_tool("read_file", {"path": str(tmp)})
        check("read_file: returns content", r, "hello SOV1")
        # Append mode
        r, _, _ = _run_tool("write_file", {"path": str(tmp), "content": " world", "append": True})
        check("write_file append: success", r, "appended")
        r, _, _ = _run_tool("read_file", {"path": str(tmp)})
        check("read_file: append worked", r, "world")
    finally:
        if tmp.exists():
            _os.unlink(tmp)
    r, _, _ = _run_tool("read_file", {"path": str(tmp)})
    check("read_file: missing file returns not found", r, "not found")
    r, _, _ = _run_tool("write_file", {"path": "", "content": "x"})
    check("write_file: empty path returns error", r, "required")

    # 7. API independence — is_local defaults to True
    import importlib, sys as _sys
    orig_local = _os.environ.get("LOCAL_MODE")
    try:
        _os.environ.pop("LOCAL_MODE", None)
        import llm as _llm
        importlib.reload(_llm)
        check("is_local defaults to True when LOCAL_MODE unset", _llm.is_local(), True)
        check("is_api_independent returns True when local", _llm.is_api_independent(), True)
        _os.environ["LOCAL_MODE"] = "false"
        importlib.reload(_llm)
        check("is_local returns False when LOCAL_MODE=false", _llm.is_local(), False)
        check("is_api_independent returns False when cloud", _llm.is_api_independent(), False)
        # require_local raises when cloud
        try:
            _llm.require_local("smoke_test")
            check("require_local raises when cloud", False, True)
        except RuntimeError:
            check("require_local raises when cloud", True, True)
        _os.environ["LOCAL_MODE"] = "true"
        importlib.reload(_llm)
        # require_local passes when local
        try:
            _llm.require_local("smoke_test")
            check("require_local passes when local", True, True)
        except RuntimeError:
            check("require_local passes when local", False, True)
    finally:
        if orig_local is None:
            _os.environ.pop("LOCAL_MODE", None)
        else:
            _os.environ["LOCAL_MODE"] = orig_local
        importlib.reload(_llm)

    # 8. _api_status_report returns string
    report = _api_status_report()
    check("_api_status_report: returns string", isinstance(report, str), True)
    check("_api_status_report: contains independence label", "API Independent" in report, True)

    # 9. ask_oracle tool
    r, _, _ = _run_tool("ask_oracle", {})
    check("ask_oracle: returns string", isinstance(r, str), True)
    check("ask_oracle: contains ORACLE STATE", "ORACLE STATE" in r, True)
    check("ask_oracle: contains ONE NEXT ACTION", "ONE NEXT ACTION" in r, True)
    check("ask_oracle: contains Project line", "Project" in r, True)

    # ask_oracle with question filter
    r2, _, _ = _run_tool("ask_oracle", {"question": "what is blocked?"})
    check("ask_oracle: question 'blocked' adds filter header", "block" in r2.lower(), True)

    r3, _, _ = _run_tool("ask_oracle", {"question": "what should I build next?"})
    check("ask_oracle: question 'next' adds filter header", "next" in r3.lower() or "build" in r3.lower(), True)

    print(f"\n{passed}/{passed+failed} smoke tests passed.")
    if failed:
        print("SOME TESTS FAILED — check output above.")
    else:
        print("All smoke tests passed.")
    return failed == 0


def _api_status_report() -> str:
    """Return a one-screen API independence status string."""
    from llm import is_api_independent, is_local, check_ollama, get_model, DEFAULT_OLLAMA_BASE
    import os
    lines = []
    lines.append("=" * 56)
    lines.append("  SOV1.AI — API Independence Status")
    lines.append("=" * 56)
    indep = is_api_independent()
    lines.append(f"  API Independent : {'YES — no cloud API required' if indep else 'NO — cloud API in use'}")
    lines.append(f"  LOCAL_MODE      : {os.getenv('LOCAL_MODE', '(unset → defaults to true)')}")
    lines.append(f"  Text model      : {get_model(vision=False)}")
    lines.append(f"  Vision model    : {get_model(vision=True)}")
    lines.append(f"  Ollama base     : {os.getenv('OLLAMA_BASE', DEFAULT_OLLAMA_BASE)}")
    if indep:
        ok, msg = check_ollama()
        lines.append(f"  Ollama health   : {'OK' if ok else 'OFFLINE'} — {msg}")
    else:
        lines.append(f"  Cloud model     : {os.getenv('CLOUD_MODEL', 'claude-sonnet-4-6')}")
        has_key = bool(os.getenv("ANTHROPIC_API_KEY"))
        lines.append(f"  API key set     : {'yes' if has_key else 'NO — will fail'}")
    lines.append("=" * 56)
    if not indep:
        lines.append("  To restore independence: set LOCAL_MODE=true in .env")
    return "\n".join(lines)


def main():
    if not cc.HANDS_AVAILABLE:
        print(cc._require_hands())
        sys.exit(1)

    local = is_local()

    # API independence check — warn if cloud mode is active
    if not local:
        print("\n[WARNING] LOCAL_MODE is not true — SOV1 will call the Anthropic cloud API.")
        print("          Set LOCAL_MODE=true in .env to run fully locally (no API key needed).\n")

    try:
        client = make_client()
    except RuntimeError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    model = get_model(vision=True)

    print("=" * 56)
    print("  SOV1.AI — OPERATOR ONLINE")
    print("=" * 56)
    if local:
        from llm import check_ollama
        ok, msg = check_ollama()
        print(f"  LOCAL MODE — {msg}")
        print(f"  Vision: {model}  |  Text: {get_model(vision=False)}")
    else:
        print(f"  CLOUD MODE — model: {model}")
    print("  Type what you want done. I'll operate the screen.")
    print("  Abort anytime: slam the mouse into a screen corner.")
    print("  /api-status to check independence. /quit to exit.\n")

    while True:
        try:
            goal = input("What do you want done? ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not goal:
            continue
        if goal.lower() in ("/quit", "/exit", "quit", "exit"):
            break

        # ── API independence status ───────────────────────────────────────────
        if goal.lower() in ("/api-status", "/api", "api status", "api-status"):
            print(_api_status_report())
            continue

        # ── Auto: resident_runtime tick → candidate → act or stop ────────────
        if goal.lower() in ("/auto", "auto", "what should i do", "what next", "/oracle"):
            oracle_state = _ask_oracle()
            print(f"\n{oracle_state}\n")

            # Extract the one next action
            state_lines = oracle_state.splitlines()
            action_line = next((l for l in state_lines if l.strip().startswith("  ") and
                                not l.strip().startswith("Project") and
                                not l.strip().startswith("Last") and
                                not l.strip().startswith("Blocker") and
                                not l.strip().startswith("Pending") and
                                not l.strip().startswith("Ollama") and
                                not l.strip().startswith("Reason") and
                                "ORACLE STATE" not in l and
                                "NEXT ACTION" not in l and
                                "[Question" not in l), "")
            action = action_line.strip()
            if not action:
                print("[AUTO] No actionable step found in ORACLE state.")
                continue

            needs_approval = "APPROVAL REQUIRED" in oracle_state

            # Wrap in ActionCandidate — never execute raw string directly
            try:
                import action_candidates as _ac
                risk = "high" if needs_approval else "low"
                cand = _ac.new_candidate(
                    title="AUTO next action",
                    description=action,
                    risk_level=risk,
                    target_module="sov1_operate",
                    proposed_steps=[action],
                    reversibility="unknown",
                    required_approval=needs_approval,
                )
                cand = _ac.submit(cand)
                cand_id = cand["id"]
            except Exception as _ce:
                cand = None
                cand_id = None
                log("WARN", f"action_candidates unavailable: {_ce}")

            if needs_approval:
                print(f"[AUTO] Approval required — candidate created, not executing.")
                print(f"       Action : {action}")
                if cand_id:
                    print(f"       ID     : {cand_id[:8]}")
                print(f"       Approve via: python core/action_candidates.py --list")
                continue

            # Auto-approve low-risk candidate and execute
            if cand and _ac.is_executable(_ac.approve(cand_id, approved_by="oracle_auto")):
                pass  # approved inline

            print(f"[AUTO] ORACLE recommends: {action}")
            print(f"[AUTO] Executing as goal...\n")
            goal = action
            _recent_actions.clear()
            reset_typing_guard()
            try:
                if local:
                    operate_local(client, goal, model)
                else:
                    operate(client, goal, model)
            except Exception as e:
                log("ERROR", f"SOV1 auto operate failed: {e}")
                print(f"\n[SOV1 auto hit an error: {e}]\n")
            continue

        # ── Safety mode commands ──────────────────────────────────────────────
        if goal.lower() in ("safe_sleep_mode", "/safe", "safe mode", "sleep mode"):
            import sov1 as _self
            _self.SAFE_SLEEP_MODE = True
            _active_bc.enable_safe_sleep()
            print("\n[SAFE_SLEEP_MODE ACTIVE] Desktop actions disabled. "
                  "ORACLE can observe and propose but cannot move the mouse, keyboard, "
                  "or browser. Type 'wake' to re-enable.\n")
            continue
        if goal.lower() in ("wake", "/wake", "wake up", "disable safe mode"):
            import sov1 as _self
            _self.SAFE_SLEEP_MODE = False
            _active_bc.disable_safe_sleep()
            print("\n[SAFE_SLEEP_MODE OFF] Desktop actions re-enabled.\n")
            continue

        # ── Batch controller commands ─────────────────────────────────────────
        if goal.lower() in ("stop oracle", "stop_oracle", "/stop"):
            msg = _active_bc.stop_oracle()
            print(f"\n{msg}\n")
            continue

        if goal.lower() in ("continue oracle", "continue_oracle", "/continue"):
            _active_bc.reset_for_continuation()
            print(f"\n[CONTINUE ORACLE] Starting next batch (limit {_active_bc.batch_limit} actions). "
                  f"Total actions so far: {_active_bc.total_actions()}.\n")
            # Re-run the current goal if we have one
            if _active_bc.goal:
                goal = _active_bc.goal
            else:
                print("No active goal. Type what you want done.\n")
                continue

        elif goal.lower() in ("autorun safe", "autorun_safe", "/autorun"):
            print("\n" + _active_bc.enable_autorun_safe() + "\n")
            continue

        elif goal.lower() in ("action_dry_run", "dry run", "/dryrun", "/dry"):
            print("\n" + _active_bc.enable_dry_run() + "\n")
            continue

        elif goal.lower() in ("batch status", "/batch"):
            print(f"\n{_active_bc.status()}\n")
            continue

        # ── ACTION_DIAGNOSTIC command ─────────────────────────────────────────
        if goal.lower() in ("action_diagnostic", "/diagnostic", "/diag", "action diagnostic"):
            from targeted_input import action_diagnostic, get_active_window_title, get_typing_guard
            diag = action_diagnostic(
                intended_target=_current_goal,
                last_actions=[f"{a}({b})[{'ok' if v else 'unverified'}]"
                              for a, b, v in get_typing_guard().history()],
                guard=get_typing_guard(),
            )
            print(diag)
            continue

        # Reset loop guard and typing guard between goals — fresh start each task
        _recent_actions.clear()
        reset_typing_guard()

        try:
            if local:
                operate_local(client, goal, model)
            else:
                operate(client, goal, model)
        except Exception as e:
            log("ERROR", f"SOV1 operate failed: {e}")
            print(f"\n[SOV1 hit an error: {e}]\n")
        print()

    print("\nSOV1 offline.")


if __name__ == "__main__":
    if "--smoke" in sys.argv or "smoke" in sys.argv:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
        ok = _smoke_test()
        sys.exit(0 if ok else 1)
    else:
        main()
