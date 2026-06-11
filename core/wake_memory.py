"""
core/wake_memory.py  —  ORACLE Wake Memory v0.1

Loads a persistent "who we are, what we're doing, what happened last,
what matters now" file every time ORACLE starts talking.

Rules:
  - No raw transcripts stored.
  - No secrets stored.
  - Short enough to fit every prompt (target < 600 chars injected).
  - If file is missing, a safe default is created automatically.
  - Update is always a human-readable short summary, not raw session data.

Usage:
  from wake_memory import load_wake_memory, format_wake_context

  wake = load_wake_memory()
  context_block = format_wake_context(wake)   # inject into system prompt

CLI:
  python core/wake_memory.py --show
  python core/wake_memory.py --update "short summary of what just happened"
  python core/wake_memory.py --smoke-test
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Paths ─────────────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    _ROOT = Path(sys.executable).parent
else:
    _ROOT = Path(__file__).parent.parent

WAKE_MEMORY_FILE = _ROOT / "Memory" / "wake_memory.json"

# How many chars of the formatted context block we allow into any prompt.
# Keep this small — it's injected on every turn.
MAX_CONTEXT_CHARS = 700

# ── Safe default ──────────────────────────────────────────────────────────────
_DEFAULT_WAKE_MEMORY: dict[str, Any] = {
    "schema_version": "0.1",
    "identity": {
        "noah": "Noah Hawkes is building ORACLE.AI as a local continuity intelligence.",
        "oracle": "ORACLE is a local governed continuity engine, not a chatbot.",
    },
    "machine": {
        "name": "SOV1MSILaptop",
        "type": "laptop",
        "verified": False,
    },
    "active_projects": [
        "ORACLE.AI local resident intelligence",
    ],
    "last_session_summary": "No prior session recorded yet.",
    "open_blockers": [],
    "latest_verified_commits": [],
    "current_emotional_context": "",
    "single_next_action": "Run /wake-memory to review and update the wake context.",
    "updated_at": "",
}


# ── Load ──────────────────────────────────────────────────────────────────────

def load_wake_memory() -> dict[str, Any]:
    """
    Load wake memory from disk. Returns the dict.
    Creates the safe default file if missing or unreadable.
    Never raises.
    """
    if not WAKE_MEMORY_FILE.exists():
        _write_wake_memory(_DEFAULT_WAKE_MEMORY.copy())
        return _DEFAULT_WAKE_MEMORY.copy()
    try:
        data = json.loads(WAKE_MEMORY_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("not a dict")
        # Fill any missing keys with defaults so old files stay compatible
        merged = _DEFAULT_WAKE_MEMORY.copy()
        merged.update(data)
        return merged
    except Exception:
        return _DEFAULT_WAKE_MEMORY.copy()


# ── Format ────────────────────────────────────────────────────────────────────

def format_wake_context(wake: dict[str, Any]) -> str:
    """
    Return a compact context block to prepend to every system prompt.

    Deliberately terse — every token costs something.  The goal is to give
    the model a stable identity, not to reproduce the whole project wiki.
    """
    lines: list[str] = ["[WAKE MEMORY]"]

    # Identity
    noah  = wake.get("identity", {}).get("noah", "")
    oracle = wake.get("identity", {}).get("oracle", "")
    if noah:
        lines.append(f"Noah   : {noah}")
    if oracle:
        lines.append(f"ORACLE : {oracle}")

    # Machine
    machine = wake.get("machine", {})
    if machine.get("name"):
        lines.append(f"Machine: {machine['name']}")

    # Active projects (first two only to save space)
    projects = wake.get("active_projects", [])
    if projects:
        proj_line = " | ".join(str(p) for p in projects[:2])
        lines.append(f"Projects: {proj_line}")

    # Last session
    last = wake.get("last_session_summary", "")
    if last and last != "No prior session recorded yet.":
        lines.append(f"Last: {last[:160]}")

    # Open blockers (top one only)
    blockers = wake.get("open_blockers", [])
    if blockers:
        lines.append(f"Blocker: {str(blockers[0])[:100]}")

    # Next action
    nxt = wake.get("single_next_action", "")
    if nxt:
        lines.append(f"Next: {nxt[:120]}")

    # Emotional context (kept separate — it changes the tone of responses)
    ctx = wake.get("current_emotional_context", "")
    if ctx:
        lines.append(f"Context: {ctx[:120]}")

    block = "\n".join(lines)

    # Hard cap — never let wake memory eat the whole context window
    if len(block) > MAX_CONTEXT_CHARS:
        block = block[:MAX_CONTEXT_CHARS] + "\n[wake_memory truncated]"

    return block


# ── Update ────────────────────────────────────────────────────────────────────

def update_wake_memory(
    *,
    last_session_summary: str | None = None,
    single_next_action: str | None = None,
    current_emotional_context: str | None = None,
    add_blocker: str | None = None,
    remove_blocker: str | None = None,
    add_commit: str | None = None,
    active_projects: list[str] | None = None,
) -> dict[str, Any]:
    """
    Update specific fields in wake memory and write back to disk.

    Never stores raw transcripts.  Never stores secrets.
    Only short human-readable summaries.

    Returns the updated wake memory dict.
    """
    wake = load_wake_memory()

    if last_session_summary is not None:
        # Strip anything that looks like a secret
        safe = _sanitize(last_session_summary)
        wake["last_session_summary"] = safe[:400]

    if single_next_action is not None:
        wake["single_next_action"] = _sanitize(single_next_action)[:200]

    if current_emotional_context is not None:
        wake["current_emotional_context"] = _sanitize(current_emotional_context)[:200]

    if add_blocker is not None:
        blockers: list = list(wake.get("open_blockers", []))
        b = _sanitize(add_blocker)[:120]
        if b not in blockers:
            blockers.insert(0, b)
        wake["open_blockers"] = blockers[:8]   # cap at 8

    if remove_blocker is not None:
        blockers = [b for b in wake.get("open_blockers", []) if remove_blocker.lower() not in b.lower()]
        wake["open_blockers"] = blockers

    if add_commit is not None:
        commits: list = list(wake.get("latest_verified_commits", []))
        c = _sanitize(add_commit)[:100]
        if c not in commits:
            commits.insert(0, c)
        wake["latest_verified_commits"] = commits[:6]  # keep last 6

    if active_projects is not None:
        wake["active_projects"] = [_sanitize(p)[:80] for p in active_projects[:6]]

    wake["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_wake_memory(wake)
    return wake


def save_session_summary(summary: str) -> None:
    """Convenience wrapper — called at session end."""
    update_wake_memory(last_session_summary=summary)


# ── Helpers ───────────────────────────────────────────────────────────────────

_SECRET_PATTERNS = (
    "sk-", "api_key", "apikey", "password", "secret", "token",
    "private_key", "access_key", "bearer", "credential",
)

def _sanitize(text: str) -> str:
    """Strip obvious secret-looking content. Belt-and-suspenders only."""
    lower = text.lower()
    for pat in _SECRET_PATTERNS:
        if pat in lower:
            # Blank out the whole value if it smells like a secret
            return "[redacted — possible secret detected]"
    return text.strip()


def _write_wake_memory(data: dict[str, Any]) -> None:
    WAKE_MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    WAKE_MEMORY_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

def _cli() -> None:
    args = sys.argv[1:]

    if not args or "--show" in args:
        wake = load_wake_memory()
        ctx  = format_wake_context(wake)
        print("\n" + ctx)
        print(f"\n  (full file: {WAKE_MEMORY_FILE})")
        print(f"  Last updated: {wake.get('updated_at', 'unknown')}\n")
        return

    if "--update" in args:
        idx = args.index("--update")
        summary = args[idx + 1] if idx + 1 < len(args) else ""
        if not summary:
            print("  Usage: python core/wake_memory.py --update \"short summary here\"")
            return
        updated = update_wake_memory(last_session_summary=summary)
        print(f"\n  Wake memory updated.")
        print(f"  Last session: {updated['last_session_summary'][:80]}")
        print(f"  Updated at  : {updated['updated_at']}\n")
        return

    if "--smoke-test" in args or "--smoke" in args:
        raise SystemExit(run_smoke_tests())

    print("  Usage:")
    print("    python core/wake_memory.py --show")
    print("    python core/wake_memory.py --update \"summary\"")
    print("    python core/wake_memory.py --smoke-test")


# ── Smoke tests ───────────────────────────────────────────────────────────────

def run_smoke_tests() -> int:
    import tempfile, shutil as _sh

    checks = 0
    passed = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal checks, passed
        checks += 1
        if cond:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))

    # Use a temp dir so tests never touch real Memory/wake_memory.json
    tmp_dir = Path(tempfile.mkdtemp())
    tmp_file = tmp_dir / "wake_memory.json"
    _orig = globals()["WAKE_MEMORY_FILE"]
    globals()["WAKE_MEMORY_FILE"] = tmp_file

    try:
        # 1. Missing file → safe default created
        wake = load_wake_memory()
        check("missing file creates safe default", tmp_file.exists())
        check("default has identity", "identity" in wake)
        check("default has noah key", "noah" in wake.get("identity", {}))
        check("default has oracle key", "oracle" in wake.get("identity", {}))
        check("default has active_projects", isinstance(wake.get("active_projects"), list))
        check("default has single_next_action", bool(wake.get("single_next_action")))

        # 2. format_wake_context returns non-empty string
        ctx = format_wake_context(wake)
        check("format returns string", isinstance(ctx, str))
        check("format contains WAKE MEMORY header", "[WAKE MEMORY]" in ctx)
        check("format is under MAX_CONTEXT_CHARS", len(ctx) <= MAX_CONTEXT_CHARS)

        # 3. update_wake_memory — summary
        update_wake_memory(last_session_summary="We built Wake Memory together.")
        wake2 = load_wake_memory()
        check("update stores session summary", "Wake Memory" in wake2.get("last_session_summary", ""))

        # 4. update_wake_memory — next action
        update_wake_memory(single_next_action="Test wake memory tomorrow.")
        wake3 = load_wake_memory()
        check("update stores next action", "tomorrow" in wake3.get("single_next_action", ""))

        # 5. update_wake_memory — blocker
        update_wake_memory(add_blocker="Ollama model not pulled")
        wake4 = load_wake_memory()
        check("add_blocker inserts at front", wake4.get("open_blockers", [])[0] == "Ollama model not pulled")

        # 6. update_wake_memory — remove_blocker
        update_wake_memory(remove_blocker="Ollama")
        wake5 = load_wake_memory()
        blockers_after = wake5.get("open_blockers", [])
        check("remove_blocker removes matching entry", not any("Ollama" in b for b in blockers_after))

        # 7. update_wake_memory — commit
        update_wake_memory(add_commit="abc1234 add wake memory")
        wake6 = load_wake_memory()
        check("add_commit inserts at front", "abc1234" in wake6.get("latest_verified_commits", [""])[0])

        # 8. Commits capped at 6
        for i in range(10):
            update_wake_memory(add_commit=f"commit{i:02d} filler")
        wake7 = load_wake_memory()
        check("commits capped at 6", len(wake7.get("latest_verified_commits", [])) <= 6)

        # 9. updated_at is set
        check("updated_at is set after update", bool(wake7.get("updated_at")))

        # 10. Secret sanitisation
        update_wake_memory(last_session_summary="used api_key sk-abc123 to call GPT")
        wake8 = load_wake_memory()
        check("secret in summary is redacted", "sk-abc123" not in wake8.get("last_session_summary", ""))
        check("secret triggers redaction message", "redacted" in wake8.get("last_session_summary", ""))

        # 11. save_session_summary convenience wrapper
        save_session_summary("Quick wrap-up note.")
        wake9 = load_wake_memory()
        check("save_session_summary updates summary", "Quick wrap-up" in wake9.get("last_session_summary", ""))

        # 12. Corrupt file → falls back to default
        tmp_file.write_text("NOT VALID JSON ][", encoding="utf-8")
        wake_corrupt = load_wake_memory()
        check("corrupt file returns default", "identity" in wake_corrupt)

        # 13. format_wake_context with full data
        full = {
            "identity": {"noah": "Noah H.", "oracle": "ORACLE"},
            "machine": {"name": "SOV1MSILaptop"},
            "active_projects": ["ORACLE.AI", "Book"],
            "last_session_summary": "Built wake memory.",
            "open_blockers": ["Blocker one"],
            "latest_verified_commits": [],
            "current_emotional_context": "Motivated.",
            "single_next_action": "Ship it.",
        }
        ctx_full = format_wake_context(full)
        check("format includes noah identity", "Noah" in ctx_full)
        check("format includes machine name", "SOV1MSILaptop" in ctx_full)
        check("format includes last session", "wake memory" in ctx_full.lower())
        check("format includes next action", "Ship it" in ctx_full)
        check("format includes blocker", "Blocker one" in ctx_full)

    finally:
        globals()["WAKE_MEMORY_FILE"] = _orig
        _sh.rmtree(tmp_dir, ignore_errors=True)

    print(f"\n{passed}/{checks} wake memory smoke tests passed.")
    return 0 if passed == checks else 1


# ── Entry ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    _cli()
