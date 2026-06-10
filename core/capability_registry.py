"""
core/capability_registry.py - ORACLE Capability Registry v0.1.

Tracks what ORACLE can actually use, what is degraded or unavailable, and what
approval is required. This is a registry and need detector, not a new tool.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
STATE_FILE = ROOT / "Memory" / "capability_registry_state.json"

STATUS_AVAILABLE = "available"
STATUS_UNAVAILABLE = "unavailable"
STATUS_DEGRADED = "degraded"
STATUS_UNKNOWN = "unknown"

NEED_CODEX = "Codex local file backed bridge"
NEED_CHATGPT = "ChatGPT relay"
NEED_CLAUDE = "Claude channel"
NEED_NOAH = "Noah approval"
NEED_EXECUTOR = "tools/executor.py with Drive Scope"
NEED_LOCAL = "local tools"


@dataclass(frozen=True)
class Capability:
    tool_name: str
    status: str
    purpose: str
    can_do: list[str]
    cannot_do: list[str]
    requires_approval_for: list[str]
    last_checked: str
    fallback_option: str = ""
    blocker: str = ""


@dataclass(frozen=True)
class NeedDecision:
    need: str
    reason: str
    target: str
    blocked: bool = False
    missing_capability: str = ""
    exact_request: str = ""
    safest_next_step: str = "wait"


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _exists(path: Path) -> bool:
    try:
        return path.exists()
    except Exception:
        return False


def _cap(
    tool_name: str,
    status: str,
    purpose: str,
    can_do: list[str],
    cannot_do: list[str],
    requires_approval_for: list[str],
    fallback_option: str = "",
    blocker: str = "",
) -> Capability:
    return Capability(
        tool_name=tool_name,
        status=status,
        purpose=purpose,
        can_do=can_do,
        cannot_do=cannot_do,
        requires_approval_for=requires_approval_for,
        last_checked=_stamp(),
        fallback_option=fallback_option,
        blocker=blocker,
    )


def build_registry(*, simulate_claude_unavailable: bool = False, simulate_codex_available: bool | None = None) -> dict[str, Capability]:
    core = ROOT / "core"
    tools = ROOT / "tools"

    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11434", timeout=0.3)
        ollama_status = STATUS_AVAILABLE
        ollama_blocker = ""
    except Exception:
        ollama_status = STATUS_DEGRADED
        ollama_blocker = "Ollama endpoint not confirmed"

    codex_channel_exists = _exists(core / "oracle_codex_channel.py")
    codex_status = STATUS_AVAILABLE if codex_channel_exists else STATUS_UNAVAILABLE
    if simulate_codex_available is not None:
        codex_status = STATUS_AVAILABLE if simulate_codex_available else STATUS_UNAVAILABLE

    watcher_status = STATUS_AVAILABLE if _exists(core / "oracle_codex_watcher.py") else STATUS_UNAVAILABLE
    claude_file_channel = _exists(core / "oracle_claude_channel.py")
    claude_window_or_cli = False
    if not simulate_claude_unavailable:
        try:
            from claude_code_bridge import find_claude_window
            claude_window_or_cli = find_claude_window() is not None or shutil.which("claude") is not None
        except Exception:
            claude_window_or_cli = shutil.which("claude") is not None
    claude_status = STATUS_AVAILABLE if claude_window_or_cli else (STATUS_DEGRADED if claude_file_channel else STATUS_UNAVAILABLE)

    registry = {
        "ollama": _cap(
            "Ollama local model",
            ollama_status,
            "local conversation and light reasoning",
            ["local chat", "summarize", "classify"],
            ["guarantee architecture quality", "approve governance"],
            ["external calls", "actuation"],
            fallback_option="ChatGPT relay or Codex depending on task",
            blocker=ollama_blocker,
        ),
        "codex_bridge": _cap(
            "Codex local file backed bridge",
            codex_status,
            "local repo implementation",
            ["read repo", "edit files", "run tests", "report changes"],
            ["make governance decisions", "approve commits"],
            ["commit", "delete files", "scope expansion"],
            fallback_option="Claude channel for long-context reasoning; ChatGPT relay for strategy",
            blocker="" if codex_status == STATUS_AVAILABLE else "core/oracle_codex_channel.py missing",
        ),
        "codex_watcher": _cap(
            "Codex unread watcher",
            watcher_status,
            "detect unread Codex replies",
            ["check reply hash", "report unread yes/no"],
            ["execute replies", "approve memory"],
            [],
            fallback_option="manual /read-codex",
        ),
        "claude_channel": _cap(
            "Claude channel",
            claude_status,
            "long-context code reasoning",
            ["architecture review", "long-context reasoning", "handoff via file/window"],
            ["guarantee delivery when desktop input is blocked", "approve governance"],
            ["commits", "file deletion", "scope expansion"],
            fallback_option="Codex local implementation plus ChatGPT relay",
            blocker="" if claude_status == STATUS_AVAILABLE else "Claude window/CLI not confirmed",
        ),
        "chatgpt_relay": _cap(
            "ChatGPT relay",
            STATUS_AVAILABLE if _exists(core / "chatgpt_bridge.py") else STATUS_DEGRADED,
            "strategy, architecture, prompt design via Noah-mediated relay",
            ["strategy", "prompt design", "architecture discussion"],
            ["act directly", "approve scope", "edit local files"],
            ["build handoff", "approval decisions"],
            fallback_option="local model for conversation",
        ),
        "drive_scope": _cap(
            "Drive Scope",
            STATUS_AVAILABLE if _exists(core / "drive_scope.py") else STATUS_UNAVAILABLE,
            "approved path enforcement",
            ["validate paths", "block unknown/proposed paths"],
            ["approve its own scope", "read arbitrary personal files"],
            ["scope expansion"],
            fallback_option="Freedom to Ask request",
        ),
        "actuation_engine": _cap(
            "Actuation Engine",
            STATUS_AVAILABLE if _exists(core / "actuation_engine.py") else STATUS_UNAVAILABLE,
            "governed desktop actuation",
            ["type after approval", "dry run", "report approval_required"],
            ["press enter without approval", "bypass governance"],
            ["press enter", "desktop actuation", "external send"],
            fallback_option="manual handoff",
        ),
        "executor": _cap(
            "tools/executor.py",
            STATUS_AVAILABLE if _exists(tools / "executor.py") else STATUS_UNAVAILABLE,
            "local tool dispatch under scope gates",
            ["read approved files", "run safe smoke tests", "dispatch non-file tools"],
            ["bypass Drive Scope", "approve destructive actions"],
            ["write", "commit", "delete", "move", "rename", "cloud sync"],
            fallback_option="ask Noah for exact approval",
        ),
        "resident_console": _cap(
            "Resident Console",
            STATUS_AVAILABLE if _exists(ROOT / "oracle_desktop.py") else STATUS_DEGRADED,
            "primary local UI",
            ["show status", "accept commands", "display channel state"],
            ["operate without runtime", "approve major actions"],
            [],
            fallback_option="python core/oracle.py",
        ),
        "vision": _cap(
            "Vision",
            STATUS_UNKNOWN,
            "local visual understanding when model/runtime is available",
            ["describe screenshots when configured"],
            ["raw surveillance", "store raw video as memory"],
            ["video analysis", "memory approval"],
            fallback_option="manual description from Noah",
            blocker="runtime availability not checked by registry",
        ),
        "scan_search": _cap(
            "scan/search tools",
            STATUS_AVAILABLE if _exists(tools / "filesystem_mapper.py") and _exists(tools / "executor.py") else STATUS_DEGRADED,
            "scoped local scan and search",
            ["scan approved paths", "search approved paths", "summarize approved paths"],
            ["crawl outside approved scope", "read personal files without scope"],
            ["new path", "write", "delete"],
            fallback_option="Drive Scope request",
        ),
    }
    return registry


def registry_as_jsonable(registry: dict[str, Capability]) -> list[dict]:
    return [asdict(cap) for cap in registry.values()]


def save_registry_snapshot(registry: dict[str, Capability]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"updated_at": _stamp(), "capabilities": registry_as_jsonable(registry)}, indent=2) + "\n", encoding="utf-8")


def capability_status(*, simulate_claude_unavailable: bool = False, simulate_codex_available: bool | None = None) -> dict:
    registry = build_registry(
        simulate_claude_unavailable=simulate_claude_unavailable,
        simulate_codex_available=simulate_codex_available,
    )
    save_registry_snapshot(registry)
    available = [c.tool_name for c in registry.values() if c.status == STATUS_AVAILABLE]
    unavailable = [c.tool_name for c in registry.values() if c.status == STATUS_UNAVAILABLE]
    degraded = [c.tool_name for c in registry.values() if c.status == STATUS_DEGRADED]
    blockers = [f"{c.tool_name}: {c.blocker}" for c in registry.values() if c.blocker]
    return {
        "available": available,
        "unavailable": unavailable,
        "degraded": degraded,
        "unknown": [c.tool_name for c in registry.values() if c.status == STATUS_UNKNOWN],
        "blockers": blockers,
        "registry": registry,
    }


def detect_need(
    text: str,
    *,
    simulate_claude_unavailable: bool = False,
    simulate_codex_available: bool | None = None,
) -> NeedDecision:
    lower = text.strip().lower()
    status = capability_status(
        simulate_claude_unavailable=simulate_claude_unavailable,
        simulate_codex_available=simulate_codex_available,
    )
    registry = status["registry"]

    try:
        from milestone_policy import requires_hard_approval, hard_approval_category
        if requires_hard_approval(text):
            cat = hard_approval_category(text) or "hard approval"
            return NeedDecision(
                NEED_NOAH,
                f"This crosses {cat}.",
                "Noah",
                True,
                cat,
                "Please approve the specific action or tell ORACLE to hold.",
                "hold and report the approval boundary",
            )
    except Exception:
        return NeedDecision(NEED_NOAH, "Policy unavailable; fail closed.", "Noah", True, "policy", "Restore policy or approve manually.", "hold")

    if any(word in lower for word in ("build", "implement", "patch", "edit repo", "fix code", "write code")):
        cap = registry["codex_bridge"]
        return NeedDecision(
            NEED_CODEX,
            "This requires local repo edits or tests.",
            cap.tool_name,
            cap.status != STATUS_AVAILABLE,
            cap.tool_name if cap.status != STATUS_AVAILABLE else "",
            "Open/activate Codex or use the Codex file bridge." if cap.status != STATUS_AVAILABLE else "",
            "route through Codex local file-backed bridge",
        )

    if any(word in lower for word in ("architecture", "strategy", "prompt design", "roadmap", "plan")):
        return NeedDecision(
            NEED_CHATGPT,
            "This is strategy, architecture, or prompt design.",
            "ChatGPT relay",
            False,
            "",
            "Ask Noah to approve an explicit build handoff if action is needed.",
            "treat as conversation/strategy unless Noah approves build",
        )

    if any(word in lower for word in ("long context", "deep code reasoning", "large refactor", "whole repo reasoning")):
        cap = registry["claude_channel"]
        if cap.status == STATUS_AVAILABLE:
            return NeedDecision(NEED_CLAUDE, "This benefits from long-context code reasoning.", cap.tool_name, False, safest_next_step="route to Claude channel")
        return NeedDecision(
            NEED_CLAUDE,
            "Long-context reasoning requested, but Claude is unavailable or degraded.",
            cap.tool_name,
            True,
            cap.tool_name,
            "Use Codex for local implementation and ChatGPT relay for architecture, or open Claude.",
            "Codex plus ChatGPT fallback",
        )

    if any(word in lower for word in ("file", "scan", "search", "read path", "write file")):
        return NeedDecision(NEED_EXECUTOR, "This is a file action and must pass Drive Scope.", "tools/executor.py", False, safest_next_step="executor with Drive Scope")

    return NeedDecision(NEED_LOCAL, "No special capability escalation detected.", "local router", False, safest_next_step="continue through cognitive kernel/router")


def format_need_block(attempted: str, need: NeedDecision) -> str:
    lines = [
        "[NEED]",
        f"Tried        : {attempted}",
        f"Needed       : {need.target}",
        f"Reason       : {need.reason}",
    ]
    if need.blocked:
        lines.append(f"Missing/block : {need.missing_capability or 'approval'}")
        lines.append(f"Ask Noah     : {need.exact_request or 'Provide explicit approval or direction.'}")
    lines.append(f"Safest next  : {need.safest_next_step}")
    return "\n".join(lines)


def format_registry_status() -> str:
    status = capability_status()
    lines = ["[CAPABILITY REGISTRY]"]
    lines.append("Available:")
    for name in status["available"]:
        lines.append(f"  - {name}")
    lines.append("Unavailable:")
    for name in status["unavailable"]:
        lines.append(f"  - {name}")
    lines.append("Degraded:")
    for name in status["degraded"]:
        lines.append(f"  - {name}")
    if status["unknown"]:
        lines.append("Unknown:")
        for name in status["unknown"]:
            lines.append(f"  - {name}")
    if status["blockers"]:
        lines.append("Blockers:")
        for blocker in status["blockers"][:6]:
            lines.append(f"  - {blocker}")
    return "\n".join(lines)


def format_missing_status() -> str:
    status = capability_status()
    missing = status["unavailable"] + status["degraded"] + status["unknown"]
    lines = ["[MISSING OR DEGRADED CAPABILITIES]"]
    if not missing:
        lines.append("  none")
    else:
        for item in missing:
            lines.append(f"  - {item}")
    if status["blockers"]:
        lines.append("Current blockers:")
        for blocker in status["blockers"][:6]:
            lines.append(f"  - {blocker}")
    return "\n".join(lines)


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

    status = capability_status(simulate_claude_unavailable=True, simulate_codex_available=True)
    check("registry has Codex", "Codex local file backed bridge" in [c.tool_name for c in status["registry"].values()])
    check("what tools status lists available", "Available:" in format_registry_status())
    check("missing status lists unavailable/degraded", "MISSING" in format_missing_status())
    check("build routes to Codex", detect_need("build this", simulate_codex_available=True).target == "Codex local file backed bridge")
    check("Claude unavailable reports blocked", detect_need("need long context code reasoning", simulate_claude_unavailable=True).blocked)
    check("file delete requires Noah", detect_need("delete a file").target == "Noah")
    check("architecture routes to ChatGPT relay", detect_need("architecture strategy").target == "ChatGPT relay")
    check("file action routes to executor", detect_need("scan this file").target == "tools/executor.py")

    print(f"\n{passed}/{checks} capability registry smoke tests passed.")
    return 0 if passed == checks else 1


if __name__ == "__main__":
    raise SystemExit(run_smoke_tests())
