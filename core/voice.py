"""
core/voice.py — ORACLE voice output via pyttsx3 (Windows built-in TTS)

Usage:
    from voice import speak, set_voice_enabled, is_voice_enabled

    speak("Hello Noah.")          # speaks if voice is on
    set_voice_enabled(False)      # mute
    set_voice_enabled(True)       # unmute

Voice runs in a background thread so it never blocks the REPL.
Toggle with /voice on | /voice off at the prompt.
"""

import threading
import queue
import sys

_enabled = True
_q: queue.Queue = queue.Queue()
_engine = None
_worker: threading.Thread | None = None


def _init_engine():
    global _engine
    try:
        import pyttsx3
        _engine = pyttsx3.init()
        # Slightly slower than default — easier to understand
        _engine.setProperty("rate", 165)
        # Volume full
        _engine.setProperty("volume", 1.0)
        # Prefer a female voice if available (index 1 on most Windows installs)
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


def speak(text: str) -> None:
    """Queue text for speech. No-op if voice is disabled or text is empty."""
    if not _enabled or not text or not text.strip():
        return
    _ensure_worker()
    # Strip markdown-style symbols that sound weird when read aloud
    clean = (text
             .replace("**", "")
             .replace("*", "")
             .replace("`", "")
             .replace("#", "")
             .replace("─", "")
             .replace("═", "")
             .replace("█", "")
             .strip())
    if clean:
        _q.put(clean)


def set_voice_enabled(on: bool) -> None:
    global _enabled
    _enabled = on


def is_voice_enabled() -> bool:
    return _enabled


def shutdown() -> None:
    """Clean shutdown — drain queue and stop the worker."""
    _q.put(None)
    if _worker:
        _worker.join(timeout=3)
