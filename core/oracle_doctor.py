"""
core/oracle_doctor.py — ORACLE /doctor live capability probe.

Runs live probes of every registered capability and returns a human-readable
truth table.  Read-only.  Never writes state.  Never approves anything.
Never modifies governance.  Safe to call at any time from the REPL.

Usage:
    from oracle_doctor import run_doctor
    print(run_doctor())

CLI:
    python core/oracle_doctor.py
    python core/oracle_doctor.py --smoke-test
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))


# ── Probe result ──────────────────────────────────────────────────────────────

class ProbeResult(NamedTuple):
    name: str
    registered: str       # "available" / "degraded" / "unavailable" / "unknown"
    live: str             # human description of what the live probe found
    live_ok: bool         # True = working, False = not working
    callable_by_oracle: str  # one-liner command or "NO"
    blocker: str          # empty string if none
    fix: str              # empty string if none


# ── Individual probes ─────────────────────────────────────────────────────────

def _probe_ollama() -> ProbeResult:
    try:
        from llm import check_ollama, get_model
        ok, msg = check_ollama()
        model = get_model(vision=False)
        return ProbeResult(
            "Ollama / " + model[:20],
            "available",
            "UP" if ok else f"DOWN ({msg[:50]})",
            ok,
            f"local LLM via qwen2.5:7b" if ok else "NO",
            "" if ok else "Ollama not running",
            "" if ok else "Run: ollama serve",
        )
    except Exception as e:
        return ProbeResult("Ollama", "unknown", f"probe error: {e}", False, "NO", str(e)[:60], "check llm.py")


def _probe_codex_bridge() -> ProbeResult:
    ch_file = ROOT / "core" / "oracle_codex_channel.py"
    msg_dir = ROOT / "Messages"
    ch_exists = ch_file.exists()
    # Check if codex process is in the process list
    codex_proc = False
    try:
        r = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq codex.exe"],
            capture_output=True, text=True, timeout=3,
        )
        codex_proc = "codex.exe" in r.stdout.lower()
    except Exception:
        pass
    status_parts = []
    if ch_exists:
        status_parts.append("channel file OK")
    if msg_dir.exists():
        status_parts.append("Messages/ dir OK")
    if codex_proc:
        status_parts.append("codex.exe running")
    else:
        status_parts.append("codex.exe NOT detected")
    live_ok = ch_exists
    return ProbeResult(
        "Codex bridge (file)",
        "available" if ch_exists else "unavailable",
        " | ".join(status_parts) if status_parts else "MISSING",
        live_ok,
        "ask codex to <task>  OR  /ask-codex <task>" if ch_exists else "NO",
        "" if ch_exists else "oracle_codex_channel.py missing",
        "" if ch_exists else "git status to verify",
    )


def _probe_codex_watcher() -> ProbeResult:
    watcher = ROOT / "core" / "oracle_codex_watcher.py"
    ok = watcher.exists()
    unread_msg = ""
    if ok:
        try:
            from oracle_codex_watcher import unread_status
            u = unread_status()
            unread_msg = " | UNREAD REPLY" if u.get("unread") else ""
        except Exception:
            pass
    return ProbeResult(
        "Codex watcher",
        "available" if ok else "unavailable",
        ("FILE OK" + unread_msg) if ok else "MISSING",
        ok,
        "/read-codex to check reply" if ok else "NO",
        "" if ok else "oracle_codex_watcher.py missing",
        "",
    )


def _probe_claude_channel() -> ProbeResult:
    cli = shutil.which("claude") is not None
    win = False
    try:
        from claude_code_bridge import find_claude_window
        win = find_claude_window() is not None
    except Exception:
        pass
    ch_file = (ROOT / "core" / "oracle_claude_channel.py").exists()
    if cli and win:
        live = "CLI + WINDOW"
        ok = True
    elif cli:
        live = "CLI only (window not open)"
        ok = True
    elif win:
        live = "WINDOW only (no CLI)"
        ok = True
    else:
        live = "NOT FOUND"
        ok = False
    return ProbeResult(
        "Claude channel",
        "available" if ok else "degraded",
        live + (" | channel file OK" if ch_file else " | channel file MISSING"),
        ok,
        "/ask-claude <task>  OR  ask claude to <task>" if ok else "NO",
        "" if ok else "Open Claude Desktop or install claude CLI",
        "" if ok else "https://claude.ai/download  or  npm install -g @anthropic-ai/claude-code",
    )


def _probe_chatgpt_relay() -> ProbeResult:
    bridge = ROOT / "core" / "chatgpt_bridge.py"
    ok = bridge.exists()
    return ProbeResult(
        "ChatGPT relay",
        "available" if ok else "degraded",
        "BRIDGE FILE OK (Noah-mediated)" if ok else "chatgpt_bridge.py MISSING",
        ok,
        "Say: 'ChatGPT says...'  to relay a message" if ok else "NO",
        "" if ok else "chatgpt_bridge.py missing",
        "",
    )


def _probe_drive_scope() -> ProbeResult:
    try:
        from drive_scope import is_in_scope
        result = is_in_scope(str(ROOT))
        return ProbeResult(
            "Drive Scope",
            "available",
            f"IMPORTABLE + CALLABLE (ORACLE home={'IN' if result else 'OUT'} scope)",
            True,
            "wired into executor — automatic",
            "",
            "",
        )
    except Exception as e:
        return ProbeResult(
            "Drive Scope",
            "unavailable",
            f"IMPORT/CALL ERROR: {e}",
            False,
            "NO",
            str(e)[:80],
            "check drive_scope.py",
        )


def _probe_actuation_engine() -> ProbeResult:
    ae_ok = False
    pyautogui_ok = False
    try:
        from actuation_engine import type_into_window  # noqa
        ae_ok = True
    except Exception:
        pass
    try:
        import pyautogui  # noqa
        pyautogui_ok = True
    except Exception:
        pass
    ok = ae_ok and pyautogui_ok
    blocker = ""
    fix = ""
    if not ae_ok:
        blocker = "actuation_engine import failed"
        fix = "check actuation_engine.py"
    elif not pyautogui_ok:
        blocker = "pyautogui not installed"
        fix = "pip install pyautogui pillow"
    return ProbeResult(
        "Actuation Engine",
        "available" if ae_ok else "degraded",
        ("IMPORTABLE" + (" + pyautogui OK" if pyautogui_ok else " | pyautogui MISSING")) if ae_ok else "IMPORT ERROR",
        ok,
        "/actuate <window> | <text>" if ae_ok else "NO",
        blocker,
        fix,
    )


def _probe_executor() -> ProbeResult:
    ok = False
    try:
        from tools.executor import execute_tool  # noqa
        ok = True
    except Exception:
        try:
            sys.path.insert(0, str(ROOT / "tools"))
            from executor import execute_tool  # noqa
            ok = True
        except Exception:
            pass
    return ProbeResult(
        "tools/executor.py",
        "available" if ok else "unavailable",
        "IMPORTABLE" if ok else "IMPORT ERROR",
        ok,
        "used automatically for file/scan tools" if ok else "NO",
        "" if ok else "executor import failed",
        "",
    )


def _probe_resident_console() -> ProbeResult:
    desktop = ROOT / "oracle_desktop.py"
    oracle_main = ROOT / "core" / "oracle.py"
    ok = desktop.exists()
    return ProbeResult(
        "Resident Console",
        "available" if ok else "degraded",
        "oracle_desktop.py present" if ok else "oracle_desktop.py MISSING",
        True,  # always callable via oracle.py
        "python oracle_desktop.py  OR  python core/oracle.py",
        "" if ok else "oracle_desktop.py missing — using core/oracle.py fallback",
        "",
    )


def _probe_voice() -> ProbeResult:
    pyttsx3_ok = False
    voice_enabled = False
    voice_importable = False
    try:
        import pyttsx3  # noqa
        pyttsx3_ok = True
    except Exception:
        pass
    try:
        from voice import is_voice_enabled
        voice_enabled = is_voice_enabled()
        voice_importable = True
    except Exception:
        pass
    ok = pyttsx3_ok and voice_importable
    return ProbeResult(
        "Voice / TTS (pyttsx3)",
        "available" if ok else ("degraded" if voice_importable else "unavailable"),
        ("ENABLED" if voice_enabled else "MUTED — /voice on to enable") if ok else
        ("voice.py OK but pyttsx3 MISSING" if voice_importable else "voice.py import error"),
        ok,
        "/voice on|off  or  speak() in code" if ok else "NO — pyttsx3 missing",
        "" if ok else ("pyttsx3 not installed" if not pyttsx3_ok else "voice.py import failed"),
        "" if pyttsx3_ok else "pip install pyttsx3",
    )


def _probe_scan_search() -> ProbeResult:
    mapper = ROOT / "tools" / "filesystem_mapper.py"
    executor = ROOT / "tools" / "executor.py"
    ok = mapper.exists() and executor.exists()
    return ProbeResult(
        "scan/search tools",
        "available" if ok else "degraded",
        ("filesystem_mapper.py + executor.py present") if ok else
        (("filesystem_mapper.py MISSING" if not mapper.exists() else "") +
         (" executor.py MISSING" if not executor.exists() else "")),
        ok,
        "automatic via executor scope gate" if ok else "PARTIAL",
        "" if ok else ("filesystem_mapper.py missing" if not mapper.exists() else "executor.py missing"),
        "",
    )


# ── Routing gap analysis ──────────────────────────────────────────────────────

def _routing_gaps() -> list[str]:
    """Return known routing gaps — inputs that silently fall through incorrectly."""
    gaps = []

    # Test: "use codex to X" route
    try:
        import re
        _NL_ASK_CODEX_PATTERNS = [
            re.compile(r"^ask\s+codex\s+(.+)", re.I),
            re.compile(r"^tell\s+codex\s+(?:to\s+)?(.+)", re.I),
            re.compile(r"^(?:have|get)\s+codex\s+(?:to\s+)?(.+)", re.I),
            re.compile(r"^use\s+codex\s+(?:to\s+)?(.+)", re.I),
        ]
        test = "use codex to inspect the repo"
        matched = any(p.match(test) for p in _NL_ASK_CODEX_PATTERNS)
        if not matched:
            gaps.append("'use codex to X' — not in NL parser; use 'ask codex to X' or /ask-codex")
    except Exception:
        pass

    # Test: over-gated questions
    try:
        from cognitive_kernel import decide_next, INTENT_APPROVAL_REQUIRED
        over_gated = []
        for q in [
            "what should we commit next",
            "pull up the repo status",
            "what is the cloud architecture",
            "explain the governance model",
        ]:
            d = decide_next(q)
            if d.intent == INTENT_APPROVAL_REQUIRED:
                over_gated.append(q)
        if over_gated:
            gaps.append(
                f"Milestone policy blocks conversational questions containing "
                f"commit/pull/cloud/governance keyword: {over_gated[0]!r} and "
                f"{len(over_gated) - 1} more"
            )
    except Exception:
        pass

    return gaps


# ── Overgating analysis ───────────────────────────────────────────────────────

def _overgating_examples() -> list[tuple[str, str]]:
    """Return (input, reason) pairs for over-gated inputs."""
    results = []
    try:
        from cognitive_kernel import decide_next, INTENT_APPROVAL_REQUIRED
        candidates = [
            ("what should we commit next", "contains 'commit'"),
            ("pull up the repo status", "contains 'pull'"),
            ("what is the cloud architecture", "contains 'cloud'"),
            ("explain the governance model", "contains 'governance'"),
            ("what shared resources do we have", "contains 'share'"),
            ("how does git push work", "contains 'push'"),
        ]
        for text, reason in candidates:
            d = decide_next(text)
            if d.intent == INTENT_APPROVAL_REQUIRED:
                results.append((text, reason))
    except Exception:
        pass
    return results


# ── Main report ───────────────────────────────────────────────────────────────

def run_doctor() -> str:
    """
    Run all live probes and return the formatted truth table.
    Safe to call at any time. Read-only.
    """
    probes = [
        _probe_ollama(),
        _probe_codex_bridge(),
        _probe_codex_watcher(),
        _probe_claude_channel(),
        _probe_chatgpt_relay(),
        _probe_drive_scope(),
        _probe_actuation_engine(),
        _probe_executor(),
        _probe_resident_console(),
        _probe_voice(),
        _probe_scan_search(),
    ]

    # Truth table
    col_name = 30
    col_reg = 12
    col_live = 36
    col_call = 8
    sep = "─" * (col_name + col_reg + col_live + col_call + 34)

    lines = [
        "",
        "  [ORACLE /doctor — LIVE CAPABILITY TRUTH TABLE]",
        f"  {sep}",
        f"  {'Capability':<{col_name}} {'Registered':<{col_reg}} {'Live Probe':<{col_live}} {'OK?':<{col_call}} Blocker / Fix",
        f"  {sep}",
    ]
    for p in probes:
        mark = "YES" if p.live_ok else "NO "
        issue = (p.fix or p.blocker)[:38]
        lines.append(
            f"  {p.name:<{col_name}} {p.registered:<{col_reg}} {p.live:<{col_live}} {mark:<{col_call}} {issue}"
        )
    lines.append(f"  {sep}")

    working = [p.name for p in probes if p.live_ok]
    broken  = [p.name for p in probes if not p.live_ok]
    lines += [
        "",
        f"  Working  ({len(working)}): " + ", ".join(working),
        f"  Broken   ({len(broken)}): " + (", ".join(broken) if broken else "none"),
        "",
    ]

    # Routing gaps
    gaps = _routing_gaps()
    if gaps:
        lines.append("  [ROUTING GAPS]")
        for g in gaps:
            lines.append(f"  • {g}")
        lines.append("")

    # Over-gating
    og = _overgating_examples()
    if og:
        lines.append("  [OVER-GATING — inputs blocked that should reach the LLM]")
        for text, reason in og:
            lines.append(f"  • {text!r}  ← blocked because: {reason}")
        lines.append("  FIX: Pure questions bypass hard-approval (applied in cognitive_kernel.py)")
        lines.append("")

    # Safe actions (no approval needed)
    lines += [
        "  [SAFE WITHOUT APPROVAL — use these freely]",
        "  /capabilities         list registered capabilities",
        "  /missing-capabilities list unavailable/degraded",
        "  /pending              review approval queue",
        "  /channel              check Claude + Codex channel status",
        "  /read-codex           read last Codex reply",
        "  /project-state  /ps   show current build phase",
        "  /cycle  /runtime      run one governed resident cycle",
        "  /session              show session state diagnostic",
        "  /doctor               this report (live probes)",
        "  ask codex to <task>   send task to Codex file bridge",
        "  ask claude to <task>  send task to Claude channel",
        "  talk to me            conversational mode",
        "  remember this: <X>    store a fact",
        "",
        "  [VOICE STATUS]",
    ]
    try:
        from voice import is_voice_enabled
        lines.append(
            f"  pyttsx3 TTS path exists.  Currently: "
            f"{'ENABLED' if is_voice_enabled() else 'MUTED (type /voice on to enable)'}."
        )
    except Exception:
        lines.append("  Voice import failed — pyttsx3 may not be installed (pip install pyttsx3).")
    lines.append("")

    return "\n".join(lines)


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

    report = run_doctor()

    check("run_doctor returns non-empty string", bool(report))
    check("report contains truth table header", "LIVE CAPABILITY TRUTH TABLE" in report)
    check("report contains Ollama row", "Ollama" in report)
    check("report contains Codex bridge row", "Codex bridge" in report)
    check("report contains Claude channel row", "Claude channel" in report)
    check("report contains Drive Scope row", "Drive Scope" in report)
    check("report contains voice row", "Voice" in report)
    check("report contains Working/Broken summary", "Working" in report and "Broken" in report)
    check("report contains safe actions section", "SAFE WITHOUT APPROVAL" in report)
    check("report contains voice status section", "VOICE STATUS" in report)

    # Individual probes don't crash
    for fn in [
        _probe_ollama, _probe_codex_bridge, _probe_codex_watcher,
        _probe_claude_channel, _probe_chatgpt_relay, _probe_drive_scope,
        _probe_actuation_engine, _probe_executor, _probe_resident_console,
        _probe_voice, _probe_scan_search,
    ]:
        try:
            result = fn()
            check(f"probe {fn.__name__} returns ProbeResult", isinstance(result, ProbeResult))
            check(f"probe {fn.__name__} has non-empty name", bool(result.name))
            check(f"probe {fn.__name__} live_ok is bool", isinstance(result.live_ok, bool))
        except Exception as e:
            checks += 3
            print(f"  [FAIL] probe {fn.__name__} crashed: {e}")

    check("routing gap analysis runs without crash", isinstance(_routing_gaps(), list))
    check("overgating analysis runs without crash", isinstance(_overgating_examples(), list))

    print(f"\n{passed}/{checks} oracle_doctor smoke tests passed.")
    return 0 if passed == checks else 1


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke-test", action="store_true")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if args.smoke_test:
        raise SystemExit(run_smoke_tests())
    print(run_doctor())
