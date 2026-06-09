"""
core/voice_hooks.py — ORACLE Voice Hooks v0.1

Named lifecycle event hooks for ORACLE's voice layer.

Other modules fire these hooks without knowing about voice.py internals.
Each hook speaks an appropriate phrase if voice is enabled and SAFE_SLEEP
is not active. All hooks are no-ops if voice is unavailable or muted.

Usage:
    from voice_hooks import on_boot, on_prompt_start, on_error, on_safe_sleep_enter

    on_boot()                   # "ORACLE online."
    on_prompt_start("Write...")  # silent — prompts don't announce themselves
    on_error("Memory write failed")
    on_safe_sleep_enter()       # silent — SAFE_SLEEP suppresses speech
    on_safe_sleep_exit()        # "ORACLE resumed."

Hook catalogue:
    on_boot()               — spoken at startup
    on_shutdown()           — spoken before exit
    on_prompt_start(text)   — no-op (prompts are silent by design)
    on_prompt_end()         — no-op
    on_error(msg)           — speaks a brief error signal
    on_approval_needed()    — spoken when a candidate awaits review
    on_safe_sleep_enter()   — no-op (SAFE_SLEEP silences everything)
    on_safe_sleep_exit()    — "ORACLE resumed." when SAFE_SLEEP lifts
    on_build_complete(name) — spoken when a self-build step finishes

All hooks are safe to call even if voice.py fails to import.
"""

from __future__ import annotations

import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    _ROOT = Path(sys.executable).parent
else:
    _ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(_ROOT / "core"))


def _speak(text: str) -> None:
    try:
        from voice import speak
        speak(text)
    except Exception:
        pass


# ── Lifecycle hooks ────────────────────────────────────────────────────────────

def on_boot() -> None:
    """Spoken once at ORACLE startup."""
    _speak("ORACLE online.")


def on_shutdown() -> None:
    """Spoken before clean exit."""
    _speak("ORACLE shutting down.")


def on_prompt_start(text: str = "") -> None:
    """No-op. Prompts are silent — don't interrupt Noah's flow."""


def on_prompt_end() -> None:
    """No-op."""


def on_error(msg: str = "") -> None:
    """Brief spoken signal on error. Does not read the full message aloud."""
    _speak("Error.")


def on_approval_needed() -> None:
    """Spoken when a candidate is waiting for Noah's review."""
    _speak("Approval needed.")


def on_safe_sleep_enter() -> None:
    """No-op. SAFE_SLEEP gate in voice.py already silences speech."""


def on_safe_sleep_exit() -> None:
    """Spoken when SAFE_SLEEP lifts and ORACLE resumes normal operation."""
    _speak("ORACLE resumed.")


def on_build_complete(step_name: str = "") -> None:
    """Spoken when a self-build step finishes successfully."""
    label = step_name.strip() if step_name else "step"
    _speak(f"Build complete. {label}")


# ── Smoke test ────────────────────────────────────────────────────────────────

def _smoke_test() -> None:
    """Verify all hooks are callable and don't raise. Voice output not required."""
    hooks = [
        ("on_boot",             lambda: on_boot()),
        ("on_shutdown",         lambda: on_shutdown()),
        ("on_prompt_start",     lambda: on_prompt_start("test prompt")),
        ("on_prompt_end",       lambda: on_prompt_end()),
        ("on_error",            lambda: on_error("test error")),
        ("on_approval_needed",  lambda: on_approval_needed()),
        ("on_safe_sleep_enter", lambda: on_safe_sleep_enter()),
        ("on_safe_sleep_exit",  lambda: on_safe_sleep_exit()),
        ("on_build_complete",   lambda: on_build_complete("voice_hooks v0.1")),
    ]
    passed = 0
    for name, fn in hooks:
        try:
            fn()
            print(f"  [PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name} — {e}")
    print(f"\n{passed}/{len(hooks)} smoke tests passed.")
    if passed < len(hooks):
        sys.exit(1)


if __name__ == "__main__":
    print("Running voice_hooks smoke tests...\n")
    _smoke_test()
