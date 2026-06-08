"""
core/voice.py — ORACLE voice output via pyttsx3 (Windows built-in TTS)

Usage:
    from voice import speak, speak_prompt, set_voice_enabled, is_voice_enabled

    speak("Hello Noah.")          # speaks if voice is on and not SAFE_SLEEP
    speak_prompt("Boot complete") # named hook for presence/boot announcements
    set_voice_enabled(False)      # mute — persists across restarts
    set_voice_enabled(True)       # unmute

Voice runs in a background thread so it never blocks the REPL.
Toggle with /voice on | /voice off at the prompt.

SAFE_SLEEP silences all speech automatically.
Mute state persists to Memory/voice_state.json.
"""

import json
import threading
import queue
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    _ROOT = Path(sys.executable).parent
else:
    _ROOT = Path(__file__).parent.parent

_STATE_FILE = _ROOT / "Memory" / "voice_state.json"

_q: queue.Queue = queue.Queue()
_engine = None
_worker: threading.Thread | None = None


# ── Persistent state ───────────────────────────────────────────────────────────

def _load_state() -> dict:
    try:
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"enabled": True}


def _save_state(enabled: bool) -> None:
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(
            json.dumps({"enabled": enabled}, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


_enabled: bool = _load_state().get("enabled", True)


# ── SAFE_SLEEP gate ────────────────────────────────────────────────────────────

def _is_safe_sleep() -> bool:
    """Return True if SAFE_SLEEP is active — all voice is silenced."""
    try:
        from governance import load_runtime_config
        cfg = load_runtime_config()
        return bool(cfg.get("safe_sleep_active", False))
    except Exception:
        return False


# ── Engine ─────────────────────────────────────────────────────────────────────

def _init_engine():
    global _engine
    try:
        import pyttsx3
        _engine = pyttsx3.init()
        _engine.setProperty("rate", 165)
        _engine.setProperty("volume", 1.0)
        voices = _engine.getProperty("voices")
        if len(voices) > 1:
            _engine.setProperty("voice", voices[1].id)
        return True
    except Exception as e:
        print(f"[Voice] Could not init pyttsx3: {e}", file=sys.stderr)
        return False


def _run_worker():
    """Background thread: drain the queue and speak each item."""
    if not _init_engine():
        return
    while True:
        text = _q.get()
        if text is None:
            break
        try:
            _engine.say(text)
            _engine.runAndWait()
        except Exception:
            pass
        finally:
            _q.task_done()


def _ensure_worker():
    global _worker
    if _worker is None or not _worker.is_alive():
        _worker = threading.Thread(target=_run_worker, daemon=True, name="oracle-voice")
        _worker.start()


def _clean(text: str) -> str:
    """Strip markdown symbols that sound bad when read aloud."""
    return (text
            .replace("**", "").replace("*", "").replace("`", "")
            .replace("#", "").replace("─", "").replace("═", "")
            .replace("█", "").strip())


# ── Public API ─────────────────────────────────────────────────────────────────

def speak(text: str) -> None:
    """Queue text for speech. Silent if voice disabled or SAFE_SLEEP active."""
    if not _enabled or not text or not text.strip():
        return
    if _is_safe_sleep():
        return
    _ensure_worker()
    clean = _clean(text)
    if clean:
        _q.put(clean)


def speak_prompt(text: str) -> None:
    """Named hook for presence/boot-time announcements. Same rules as speak()."""
    speak(text)


def set_voice_enabled(on: bool) -> None:
    global _enabled
    _enabled = on
    _save_state(on)


def is_voice_enabled() -> bool:
    return _enabled


def shutdown() -> None:
    """Clean shutdown — drain queue and stop the worker."""
    _q.put(None)
    if _worker:
        _worker.join(timeout=3)
