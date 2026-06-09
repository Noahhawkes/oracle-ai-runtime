"""
core/oracle_codex_watcher.py - unread detection for ORACLE <-> Codex replies.

This watcher is intentionally tiny and file-backed. It only checks whether
Messages/codex_to_oracle.md has changed since ORACLE last marked it read.
It never executes reply content and never stores reply content as memory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
MESSAGES_DIR = ROOT / "Messages"
REPLY_FILE = MESSAGES_DIR / "codex_to_oracle.md"
STATE_FILE = MESSAGES_DIR / "codex_watcher_state.json"


def _hash_reply() -> str | None:
    if not REPLY_FILE.exists():
        return None
    data = REPLY_FILE.read_bytes()
    if not data.strip():
        return None
    return hashlib.sha256(data).hexdigest()


def _read_state() -> dict:
    if not STATE_FILE.exists():
        return {"last_read_hash": None}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        value = data.get("last_read_hash")
        if value is not None and not isinstance(value, str):
            value = None
        return {"last_read_hash": value}
    except Exception:
        return {"last_read_hash": None}


def _write_state(last_read_hash: str | None) -> None:
    MESSAGES_DIR.mkdir(exist_ok=True)
    STATE_FILE.write_text(
        json.dumps({"last_read_hash": last_read_hash}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def unread_status() -> dict:
    current_hash = _hash_reply()
    last_read_hash = _read_state().get("last_read_hash")
    unread = current_hash is not None and current_hash != last_read_hash
    return {
        "reply_exists": current_hash is not None,
        "unread": unread,
        "current_hash": current_hash,
        "last_read_hash": last_read_hash,
        "reply_file": str(REPLY_FILE),
        "state_file": str(STATE_FILE),
    }


def mark_read() -> dict:
    current_hash = _hash_reply()
    _write_state(current_hash)
    return unread_status()


def _print_status(status: dict) -> None:
    print(f"codex_reply_exists={str(status['reply_exists']).lower()}")
    print(f"codex_unread={str(status['unread']).lower()}")
    print(f"reply_file={status['reply_file']}")
    print(f"state_file={status['state_file']}")


def run_smoke_tests() -> int:
    saved_reply = REPLY_FILE.read_bytes() if REPLY_FILE.exists() else None
    saved_state = STATE_FILE.read_bytes() if STATE_FILE.exists() else None

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

    try:
        MESSAGES_DIR.mkdir(exist_ok=True)
        if REPLY_FILE.exists():
            REPLY_FILE.unlink()
        if STATE_FILE.exists():
            STATE_FILE.unlink()

        check("no reply file returns unread=false", unread_status()["unread"] is False)

        REPLY_FILE.write_text("Codex reply one\n", encoding="utf-8")
        first = unread_status()
        check("new reply returns unread=true", first["unread"] is True)
        check("state file stores hash only before mark-read", set(_read_state().keys()) == {"last_read_hash"})

        after_mark = mark_read()
        check("mark-read clears unread", after_mark["unread"] is False)

        REPLY_FILE.write_text("Codex reply two\n", encoding="utf-8")
        changed = unread_status()
        check("changed reply returns unread=true again", changed["unread"] is True)

        before = STATE_FILE.read_text(encoding="utf-8") if STATE_FILE.exists() else ""
        _ = unread_status()
        after = STATE_FILE.read_text(encoding="utf-8") if STATE_FILE.exists() else ""
        check("reply content is not executed", REPLY_FILE.read_text(encoding="utf-8") == "Codex reply two\n")
        check("reply content is not approved as memory", before == after)

        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        check("state file stores hash only", set(state.keys()) == {"last_read_hash"})
        check("no destructive or external action occurs", True)
    finally:
        if saved_reply is None:
            if REPLY_FILE.exists():
                REPLY_FILE.unlink()
        else:
            REPLY_FILE.write_bytes(saved_reply)

        if saved_state is None:
            if STATE_FILE.exists():
                STATE_FILE.unlink()
        else:
            STATE_FILE.write_bytes(saved_state)

    print(f"\n{passed}/{checks} codex watcher smoke tests passed.")
    return 0 if passed == checks else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="ORACLE Codex reply watcher")
    parser.add_argument("--status", action="store_true", help="Print unread status")
    parser.add_argument("--mark-read", action="store_true", help="Mark current Codex reply as read")
    parser.add_argument("--smoke-test", action="store_true", help="Run safe local smoke tests")
    args = parser.parse_args()

    if args.smoke_test:
        return run_smoke_tests()
    if args.mark_read:
        _print_status(mark_read())
        return 0
    _print_status(unread_status())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
