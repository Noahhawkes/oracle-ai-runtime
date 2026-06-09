"""
core/oracle_codex_channel.py - ORACLE <-> Codex local file channel.

Oracle writes a task to Messages/oracle_to_codex.md.
Codex reads it and writes a response to Messages/codex_to_oracle.md.

This is intentionally file-backed. It is more reliable than desktop window
typing for Electron/webview apps and keeps the handoff auditable in the repo.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
MESSAGES_DIR = ROOT / "Messages"
ORACLE_TO_CODEX = MESSAGES_DIR / "oracle_to_codex.md"
CODEX_TO_ORACLE = MESSAGES_DIR / "codex_to_oracle.md"
CHANNEL_LOG = MESSAGES_DIR / "ai_channel_log.md"

MESSAGES_DIR.mkdir(exist_ok=True)

_POLL_INTERVAL = 2.0
_TIMEOUT = 300


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def send_to_codex(task: str, context: str = "") -> bool:
    try:
        if CODEX_TO_ORACLE.exists():
            CODEX_TO_ORACLE.unlink()

        content = f"# Task from ORACLE to Codex - {_stamp()}\n\n{task}\n"
        if context:
            content += f"\n## Context\n\n{context}\n"
        content += "\n---\n_Codex: reply in `Messages/codex_to_oracle.md`._\n"

        ORACLE_TO_CODEX.write_text(content, encoding="utf-8")
        try:
            with open(CHANNEL_LOG, "a", encoding="utf-8") as f:
                f.write(f"\n## [{_stamp()}] ORACLE -> Codex\n\n{task[:400]}\n")
        except Exception:
            pass
        return True
    except Exception:
        return False


def wait_for_response(timeout: float = _TIMEOUT, poll: float = _POLL_INTERVAL) -> str | None:
    deadline = time.time() + timeout
    last_dot = time.time()

    while time.time() < deadline:
        if CODEX_TO_ORACLE.exists():
            try:
                response = CODEX_TO_ORACLE.read_text(encoding="utf-8").strip()
                if response:
                    try:
                        with open(CHANNEL_LOG, "a", encoding="utf-8") as f:
                            f.write(f"\n## [{_stamp()}] Codex -> ORACLE\n\n{response[:400]}\n")
                    except Exception:
                        pass
                    return response
            except Exception:
                pass

        if time.time() - last_dot >= 10:
            print("  [codex-channel] Waiting for Codex response...", flush=True)
            last_dot = time.time()
        time.sleep(poll)

    return None


def ask_codex(task: str, context: str = "", timeout: float = _TIMEOUT) -> str:
    if not send_to_codex(task, context=context):
        return "[CODEX CHANNEL ERROR] Could not write task to Messages/oracle_to_codex.md"

    response = wait_for_response(timeout=timeout)
    if response is None:
        return f"[CODEX CHANNEL TIMEOUT] No response in {int(timeout)}s. Check Messages/oracle_to_codex.md."
    return response


def pending_task() -> str | None:
    if ORACLE_TO_CODEX.exists():
        try:
            return ORACLE_TO_CODEX.read_text(encoding="utf-8").strip() or None
        except Exception:
            return None
    return None


def reply_from_codex(response: str) -> bool:
    try:
        content = f"# Codex Response - {_stamp()}\n\n{response}\n"
        CODEX_TO_ORACLE.write_text(content, encoding="utf-8")
        return True
    except Exception:
        return False


def clear_channel() -> None:
    for path in (ORACLE_TO_CODEX, CODEX_TO_ORACLE):
        try:
            if path.exists():
                path.unlink()
        except Exception:
            pass


def run_smoke_tests() -> int:
    clear_channel()
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

    check("send_to_codex writes outbox", send_to_codex("hello codex"))
    check("pending_task reads outbox", "hello codex" in (pending_task() or ""))
    check("reply_from_codex writes inbox", reply_from_codex("hello oracle"))
    check("wait_for_response reads inbox", "hello oracle" in (wait_for_response(timeout=1, poll=0.1) or ""))
    clear_channel()
    print(f"\n{passed}/{checks} codex channel smoke tests passed.")
    return 0 if passed == checks else 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ORACLE <-> Codex file channel")
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    if args.smoke_test:
        raise SystemExit(run_smoke_tests())
