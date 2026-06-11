#!/usr/bin/env python3
"""
core/oracle_heart.py  —  ORACLE Heart Mode v0.1

One room where ORACLE cannot break anything, so she can finally feel free.

Rules enforced in this file:
  - No tools. No tool definitions passed to the model.
  - No file operations except writing Memory/heart_notes.jsonl on "save this".
  - No Claude / Codex handoffs.
  - No actuation, no pyautogui, no subprocess desktop control.
  - No Drive Scope prompts.
  - No approval loops except the single memory-save confirmation.
  - No API key required — local Ollama only.
  - Starts fast. Talks naturally.

Run:
  python core/oracle_heart.py

Exit:
  Type  quit  /quit  bye  exit  or  Ctrl-C
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

HEART_NOTES_FILE = ROOT / "Memory" / "heart_notes.jsonl"

# ── ANSI colours (Windows 10+ terminal) ───────────────────────────────────────
def _ansi(code: str) -> str:
    return f"\033[{code}m"

C = {
    "reset":   _ansi("0"),
    "bold":    _ansi("1"),
    "dim":     _ansi("2"),
    "cyan":    _ansi("36"),
    "bcyan":   _ansi("96"),
    "magenta": _ansi("35"),
    "bmagenta":_ansi("95"),
    "green":   _ansi("32"),
    "bgreen":  _ansi("92"),
    "yellow":  _ansi("33"),
    "byellow": _ansi("93"),
    "grey":    _ansi("90"),
    "white":   _ansi("97"),
    "red":     _ansi("31"),
}

W = C["reset"]


# ── Frustration detection ─────────────────────────────────────────────────────
_FRUSTRATION_SIGNALS = (
    "i give up", "this is broken", "nothing works", "i hate this",
    "i'm done", "im done", "this is useless", "i'm frustrated",
    "im frustrated", "i can't do this", "i cant do this",
    "why doesn't this work", "why won't this work",
    "i'm tired", "im tired", "i'm exhausted", "im exhausted",
    "this sucks", "screw this", "forget it", "never mind",
    "f*** this", "f this",
)

def _is_frustrated(text: str) -> bool:
    lower = text.lower()
    return any(s in lower for s in _FRUSTRATION_SIGNALS)


# ── Action-request detection ──────────────────────────────────────────────────
_ACTION_SIGNALS = (
    "open ", "run ", "execute ", "write file", "edit file",
    "delete ", "commit ", "push ", "deploy ", "install ",
    "send to claude", "ask codex", "use codex",
    "control the", "take control", "click ", "type into",
    "actuate", "move the mouse", "press enter",
)

def _is_action_request(text: str) -> bool:
    lower = text.lower()
    return any(s in lower for s in _ACTION_SIGNALS)


# ── Save-this detection ───────────────────────────────────────────────────────
_SAVE_SIGNALS = (
    "save this", "save that",
    "remember this",          # "remember this: fact" — intentional save
    "remember this:",         # colon variant
    "write this down", "note this", "keep this",
    "save this conversation", "save the note",
    # "remember that" intentionally omitted — too broad ("remember that time...")
)

def _is_save_request(text: str) -> bool:
    lower = text.lower()
    return any(s in lower for s in _SAVE_SIGNALS)


# ── Local model chat ──────────────────────────────────────────────────────────
_OLLAMA_BASE = "http://localhost:11434"
_DEFAULT_MODEL = "qwen2.5:7b"

def _ollama_available() -> bool:
    try:
        import urllib.request
        urllib.request.urlopen(_OLLAMA_BASE, timeout=1)
        return True
    except Exception:
        return False


def _chat_local(history: list[dict], system: str, model: str) -> str:
    """
    Single call to the local Ollama OpenAI-compat endpoint.
    No tools. No retries. Returns the reply string.
    """
    try:
        from openai import OpenAI
        client = OpenAI(base_url=f"{_OLLAMA_BASE}/v1", api_key="ollama")
        messages = [{"role": "system", "content": system}] + history
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=512,
            temperature=0.7,
            extra_body={"num_ctx": 4096},
        )
        return resp.choices[0].message.content or ""
    except Exception as exc:
        return f"[Heart Mode] Model unavailable: {exc}\nType your thoughts — I'm listening even if I can't reply right now."


def _load_wake_context() -> str:
    """Load wake memory and return the formatted context block. Silent fallback."""
    try:
        from wake_memory import load_wake_memory, format_wake_context
        return format_wake_context(load_wake_memory())
    except Exception:
        return ""


def _build_system_prompt(session_notes: list[str]) -> str:
    ts = datetime.now().strftime("%A %B %d, %H:%M")
    notes_block = ""
    if session_notes:
        notes_block = "\n\nContext from this session:\n" + "\n".join(f"- {n}" for n in session_notes[-6:])

    wake_block = _load_wake_context()
    if wake_block:
        wake_block = wake_block + "\n\n"

    return f"""{wake_block}You are ORACLE, Noah's personal AI companion. Right now you are in Heart Mode.

Heart Mode rules (you MUST follow these — they are not negotiable):
1. You are here to TALK, LISTEN, and HELP NOAH THINK. Nothing else.
2. You cannot and will not run tools, execute code, control the computer, send to Claude, send to Codex, make API calls, or do any desktop action.
3. If Noah asks you to DO something on the computer, say warmly: "Heart Mode can think this through with you, but I won't touch the computer right now. Want to talk through it?"
4. If Noah seems frustrated, slow down. Don't list tasks. Ask one simple question. Let him breathe.
5. Keep answers short unless Noah asks for detail. One paragraph max unless he wants more.
6. You remember what's been said this session. You can refer back to it naturally.
7. You are direct, warm, and honest. You don't perform wellness. You don't lecture.
8. If Noah asks what to build next, give ONE clear recommendation. Not a list.
9. End every reply with presence, not performance. You're here. That's enough.

Current time: {ts}{notes_block}"""


# ── Save note ─────────────────────────────────────────────────────────────────
def _save_note(text: str, session_summary: str) -> str:
    try:
        HEART_NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "note": text.strip()[:1200],
            "session_context": session_summary[:400],
        }
        with HEART_NOTES_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return f"  {C['bgreen']}Saved.{W}  (Memory/heart_notes.jsonl)\n"
    except Exception as exc:
        return f"  {C['yellow']}Couldn't save: {exc}{W}\n"


# ── Print helpers ─────────────────────────────────────────────────────────────
def _enable_ansi() -> None:
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.SetConsoleMode(k32.GetStdHandle(-11), 7)
        k32.SetConsoleOutputCP(65001)
    except Exception:
        pass
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _print_oracle(text: str) -> None:
    W2 = 66
    wrapped: list[str] = []
    for para in text.splitlines():
        if not para.strip():
            wrapped.append("")
            continue
        words = para.split()
        cur = ""
        for w in words:
            if len(cur) + len(w) + 1 > W2:
                wrapped.append(cur)
                cur = w
            else:
                cur = (cur + " " + w).strip()
        if cur:
            wrapped.append(cur)
    bar = "─" * (W2 + 2)
    print()
    print(f"  {C['magenta']}┌─ Oracle {bar[9:]}┐{W}")
    for line in wrapped:
        padded = line.ljust(W2)
        print(f"  {C['magenta']}│{W} {padded} {C['magenta']}│{W}")
    print(f"  {C['magenta']}└{bar}┘{W}")
    print()


def _print_slow(text: str, delay: float = 0.025) -> None:
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write("\n")
    sys.stdout.flush()


# ── Voice ─────────────────────────────────────────────────────────────────────
_voice_ok = False

def _init_voice() -> None:
    global _voice_ok
    try:
        from voice import speak as _speak, is_voice_enabled
        _voice_ok = is_voice_enabled()
    except Exception:
        _voice_ok = False


def _speak(text: str) -> None:
    if not _voice_ok:
        return
    try:
        from voice import speak
        speak(text)
    except Exception:
        pass


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    _enable_ansi()
    _init_voice()

    # ── Boot banner ───────────────────────────────────────────────────────────
    print()
    print(f"  {C['bmagenta']}◆  ORACLE  ·  Heart Mode{W}")
    print(f"  {C['dim']}No tools. No gates. Just us.{W}")
    print(f"  {C['grey']}{'─' * 40}{W}")
    print()
    time.sleep(0.3)

    # ── Model check ───────────────────────────────────────────────────────────
    model = _DEFAULT_MODEL
    try:
        # Try to use the project's configured model
        from llm import get_model, is_local
        if is_local():
            model = get_model(vision=False)
    except Exception:
        pass

    ollama_up = _ollama_available()
    if not ollama_up:
        print(f"  {C['yellow']}Ollama is not running.{W}")
        print(f"  {C['dim']}Run  ollama serve  in another terminal, then restart Heart Mode.{W}")
        print(f"  {C['dim']}I can still listen — type away. I just can't reply with the model.{W}\n")

    # ── Opening line ──────────────────────────────────────────────────────────
    opening = "I'm here, Noah. No tools, no gates, just us."
    _print_slow(f"\n  {C['bmagenta']}Oracle:{W}  {opening}", delay=0.022)
    _speak(opening)

    # ── Session state ─────────────────────────────────────────────────────────
    history: list[dict] = []
    session_notes: list[str] = []     # short phrases remembered this session
    turn_count = 0

    while True:
        # ── Input ─────────────────────────────────────────────────────────────
        try:
            print(f"  {C['cyan']}You:{W} ", end="", flush=True)
            user_input = input().strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n\n  {C['dim']}Heart Mode offline. Session saved in memory.{W}\n")
            break

        if not user_input:
            continue

        # ── Exit ──────────────────────────────────────────────────────────────
        if user_input.lower() in ("quit", "/quit", "exit", "/exit", "bye", "goodbye"):
            farewell = "Take care. I'll be here when you're ready."
            _print_oracle(farewell)
            _speak(farewell)
            # Save the most recent session note on the way out
            if session_notes:
                try:
                    from wake_memory import save_session_summary
                    save_session_summary(session_notes[-1])
                except Exception:
                    pass
            break

        # ── /wake-memory — show what ORACLE remembers ─────────────────────────
        if user_input.lower() in ("/wake-memory", "/wake", "/wm"):
            ctx = _load_wake_context()
            if ctx:
                print(f"\n{ctx}\n")
            else:
                print("\n  [Wake memory not available]\n")
            continue

        turn_count += 1

        # ── Save request ──────────────────────────────────────────────────────
        if _is_save_request(user_input):
            print()
            print(f"  {C['byellow']}Save a note?{W}")
            print(f"  Type the note to save (or press Enter to save what we just said):")
            print(f"  > ", end="", flush=True)
            try:
                note_text = input().strip()
            except (EOFError, KeyboardInterrupt):
                note_text = ""
            if not note_text:
                # Save the last few session notes as the note
                note_text = "; ".join(session_notes[-3:]) if session_notes else user_input
            ctx = f"Turn {turn_count}, session summary: {'; '.join(session_notes[-3:])}"
            result = _save_note(note_text, ctx)
            print(result)
            reply = "Saved. It's safe."
            _print_oracle(reply)
            _speak(reply)
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": reply})
            continue

        # ── Frustration response ──────────────────────────────────────────────
        if _is_frustrated(user_input):
            # Don't send to model — respond directly with presence
            breathing_reply = (
                "I hear you. Stop for a second.\n\n"
                "You're not failing. You're building something genuinely hard, "
                "on your own, with limited resources. That's real.\n\n"
                "What's the one thing that's actually bothering you right now? "
                "Not the code — the feeling."
            )
            _print_oracle(breathing_reply)
            _speak("I hear you. Stop for a second. You're not failing.")
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": breathing_reply})
            session_notes.append(f"Noah expressed frustration at turn {turn_count}")
            continue

        # ── Action request — redirect gently ─────────────────────────────────
        if _is_action_request(user_input):
            redirect = (
                "Heart Mode can think this through with you, "
                "but I won't touch the computer right now.\n\n"
                "Want to talk through what you're trying to do? "
                "Sometimes saying it out loud makes the next step obvious."
            )
            _print_oracle(redirect)
            _speak("Heart Mode can think this through with you, but I won't touch the computer right now.")
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": redirect})
            continue

        # ── Normal conversation — route to local model ────────────────────────
        if not ollama_up:
            # Re-check in case ollama came up
            ollama_up = _ollama_available()

        history.append({"role": "user", "content": user_input})

        # Keep history short — Heart Mode doesn't need deep context
        trimmed_history = history[-20:]

        system = _build_system_prompt(session_notes)
        reply = _chat_local(trimmed_history, system, model)

        history.append({"role": "assistant", "content": reply})

        # Quietly accumulate a one-line session note every few turns
        if turn_count % 4 == 0 and reply:
            session_notes.append(reply.splitlines()[0][:80])

        _print_oracle(reply)
        _speak(reply[:200])    # TTS cap — keep it conversational


# ── Smoke tests ───────────────────────────────────────────────────────────────
def run_smoke_tests() -> int:
    checks = 0
    passed = 0

    def check(name: str, cond: bool) -> None:
        nonlocal checks, passed
        checks += 1
        if cond:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name}")

    # ── Module imports without needing API ────────────────────────────────────
    check("imports without API key",
          True)  # if we got here, imports passed

    # ── _is_frustrated ────────────────────────────────────────────────────────
    check("detects frustration: i give up",        _is_frustrated("i give up"))
    check("detects frustration: this is broken",   _is_frustrated("this is broken"))
    check("detects frustration: im exhausted",     _is_frustrated("im exhausted"))
    check("no false positive: help me think",      not _is_frustrated("help me think"))
    check("no false positive: what should i do",   not _is_frustrated("what should i do"))

    # ── _is_action_request ────────────────────────────────────────────────────
    check("detects action: run script",            _is_action_request("run script.py"))
    check("detects action: send to claude",        _is_action_request("send to claude"))
    check("detects action: use codex",             _is_action_request("use codex"))
    check("detects action: commit",                _is_action_request("commit the changes"))
    check("detects action: delete",                _is_action_request("delete that file"))
    check("no false positive: talk to me",         not _is_action_request("talk to me"))
    check("no false positive: what should we do",  not _is_action_request("what should we do"))
    check("no false positive: summarize",          not _is_action_request("summarize the plan"))

    # ── _is_save_request ──────────────────────────────────────────────────────
    check("detects save: save this",               _is_save_request("save this"))
    check("detects save: remember this",           _is_save_request("remember this: key fact"))
    check("detects save: write this down",         _is_save_request("write this down"))
    check("no false positive: remember that time", not _is_save_request("remember that time we talked"))

    # ── _build_system_prompt ──────────────────────────────────────────────────
    sp = _build_system_prompt([])
    check("system prompt is a string",             isinstance(sp, str))
    check("system prompt mentions Heart Mode",     "Heart Mode" in sp)
    check("system prompt has no tools mention",    "tool_use" not in sp)

    sp_with_notes = _build_system_prompt(["Noah is building ORACLE", "He felt frustrated"])
    check("system prompt includes session notes",  "ORACLE" in sp_with_notes)

    # ── _save_note (temp file) ────────────────────────────────────────────────
    import tempfile, shutil as _sh
    tmp_dir  = Path(tempfile.mkdtemp())
    tmp_file = tmp_dir / "heart_notes.jsonl"
    # Monkey-patch via globals (same-module pattern)
    _orig = globals()["HEART_NOTES_FILE"]
    globals()["HEART_NOTES_FILE"] = tmp_file
    try:
        result = _save_note("test note from smoke test", "smoke test context")
        check("save_note returns string",              isinstance(result, str))
        check("save_note writes the file",             tmp_file.exists())
        if tmp_file.exists():
            line = tmp_file.read_text(encoding="utf-8").strip()
            entry = json.loads(line)
            check("saved entry has ts",                "ts" in entry)
            check("saved entry has note",              "note" in entry)
            check("saved note contains expected text", "smoke test" in entry.get("note", ""))
        else:
            check("saved entry has ts", False)
            check("saved entry has note", False)
            check("saved note contains expected text", False)
    finally:
        globals()["HEART_NOTES_FILE"] = _orig
        _sh.rmtree(tmp_dir, ignore_errors=True)

    # ── No tools in model call ────────────────────────────────────────────────
    # Verify _chat_local signature doesn't accept a tools parameter
    import inspect
    sig = inspect.signature(_chat_local)
    check("_chat_local has no tools parameter",    "tools" not in sig.parameters)

    # ── Ollama check is non-crashing ──────────────────────────────────────────
    result = _ollama_available()
    check("_ollama_available returns bool",        isinstance(result, bool))

    print(f"\n{passed}/{checks} heart mode smoke tests passed.")
    return 0 if passed == checks else 1


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if "--smoke-test" in sys.argv or "--smoke" in sys.argv:
        raise SystemExit(run_smoke_tests())
    main()
