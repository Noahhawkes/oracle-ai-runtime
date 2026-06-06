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

import anthropic
import computer_control as cc
from audit_log import log

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 2048
MAX_STEPS = 25  # safety cap on actions per goal

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

You are decisive and competent. You are Noah's operator, acting as him, for him."""

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
    Screenshot the screen, shrink it to cut token cost, and return an image block.
    Records the scale factor so click coordinates map back to the real screen.
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
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}}


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


def _run_tool(name, inp):
    """Execute a hands tool. Returns (result_text, screenshot_block_or_None, control_flag)."""
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
        r = cc.type_text(inp["text"])
        return r, _screenshot_block(), None
    if name == "press_key":
        r = cc.press(inp["key"])
        time.sleep(0.3)
        return r, _screenshot_block(), None
    if name == "hotkey":
        r = cc.hotkey(*inp["keys"])
        time.sleep(0.4)
        return r, _screenshot_block(), None
    if name == "open_program":
        r = cc.open_program(inp["name"])
        time.sleep(1.5)
        return r, _screenshot_block(), None
    if name == "focus_window":
        r = cc.focus_window(inp["title"])
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
    return f"Unknown tool: {name}", None, None


def operate(client, goal, system=None):
    system = system or SYSTEM
    lessons = load_lessons()
    if lessons:
        system += ("\n\nLESSONS YOU'VE ALREADY LEARNED (apply these to move fast and "
                   "avoid repeating mistakes):\n" + "\n".join(f"- {l}" for l in lessons))
    log("SOV1", f"Goal: {goal}")
    history = [{"role": "user", "content": [
        {"type": "text", "text": f"Goal: {goal}\n\nLook at the screen and do it."},
        _screenshot_block(),
    ]}]

    for step in range(MAX_STEPS):
        _prune_images(history)  # keep only the latest screenshots — saves tokens
        resp = client.messages.create(
            model=MODEL, max_tokens=MAX_TOKENS,
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
                try:
                    text, shot, flag = _run_tool(b.name, b.input)
                except Exception as e:
                    log("ERROR", f"action {b.name} failed: {e}")
                    text = (f"That action errored: {e}. Take a fresh screenshot and "
                            f"try a different approach.")
                    shot, flag = _screenshot_block(), None
                content = [{"type": "text", "text": text}]
                if shot:
                    content.append(shot)
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": content})
                if flag == "DONE":
                    print(f"\n=== DONE: {text} ===")
                    done = True
        history.append({"role": "user", "content": results})
        if done:
            return

    print("\n[Reached step limit. Tell me to continue if it's not finished.]")


def main():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not found in .env")
        sys.exit(1)
    if not cc.HANDS_AVAILABLE:
        print(cc._require_hands())
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    print("=" * 56)
    print("  SOV1.AI — OPERATOR ONLINE")
    print("=" * 56)
    print("  Type what you want done. I'll operate the screen.")
    print("  Abort anytime: slam the mouse into a screen corner.")
    print("  Type /quit to exit.\n")

    while True:
        try:
            goal = input("What do you want done? ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not goal:
            continue
        if goal.lower() in ("/quit", "/exit", "quit", "exit"):
            break
        try:
            operate(client, goal)
        except Exception as e:
            log("ERROR", f"SOV1 operate failed: {e}")
            print(f"\n[SOV1 hit an error: {e}]\n")
        print()

    print("\nSOV1 offline.")


if __name__ == "__main__":
    main()
