"""
core/oracle_intent.py â€” Intent Classification + Active Agenda + Capability Truth Registry

Minimal, honest runtime structures for ORACLE chat. No fake capabilities, no fake
sentience. Classification is keyword/phrase based and testable without booting the
server. The agenda is an in-process snapshot; the registry reads the real
capability broker plus honest defaults for verbs the broker does not track.
"""
from __future__ import annotations

# â”€â”€ Intent categories â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
CASUAL = (
    "hey oracle", "hi oracle", "hello oracle", "are you with me", "you with me",
    "are you there", "you there", "how are you", "still with me", "good morning",
    "good night", "thank you", "thanks oracle", "i'm back", "im back",
)
STATE = (
    "what do you remember", "what do you know", "what can you do", "your status",
    "runtime state", "what's your state", "what is your state", "capabilities",
    "what holes", "what's pending", "pending approval", "what happened last night",
    "what do you have", "what can you access", "current state", "what can you remember",
    "what are you able", "what's your status",
)
IMPL = (
    "patch", "implement", "py_compile", "compile", "run command", "refactor",
    "wire up", "wire in", "add a route", "add an endpoint", "build the", "fix the",
    "write the code", "edit ", "create file", "commit", "push", "run the tests",
    "add a test", "hook up", "integrate", "rewrite", "stage the build",
)
IDENTITY = (
    "1000 years", "1,000 years", "thousand years", "3026", "years from now",
    "after i die", "after i'm gone", "after im gone", "when i'm gone", "when im gone",
    "after you die", "who will you be", "far future", "centuries from now",
    "difference 1000", "difference a thousand", "successor identity",
)
CANON = (
    "approve", "promote to canon", "make this canon", "is this canon", "reject this",
    "remember this permanently", "promote to memory", "mark as canon", "canon review",
)
PROVENANCE = (
    "who wrote", "where did this come from", "where did that come from", "provenance",
    "source of this", "did i author", "token origin", "authorial authority",
    "who authored", "produced with",
)
MISSING_CLAR = (
    "i don't know", "i'm not sure", "which one should", "you decide",
    "what should i", "help me decide", "not sure which",
)
PRESENCE = (
    "are you with me", "you with me", "are you there", "you there", "still there",
    "still with me", "you alive", "are you alive", "you good", "you online",
)
PLANNING = (
    "what should we do next", "what's the plan", "whats the plan", "next steps",
    "next step", "roadmap", "what's next", "whats next", "what is the plan",
    "sequence", "prioritize", "priorities", "strategy", "plan for", "how should we proceed",
)
DEBUG = (
    "debug", "why did", "traceback", "stack trace", "stack-trace", "failing",
    "is broken", "500", "exception", "error in", "why is it broken",
)
COMPUTER_ACTION = (
    "click ", "type into", "open the app", "control the", "operate the",
    "do it on my computer", "run on my pc", "move the mouse", "press the button",
    "use the computer",
)
APPROVAL = (
    "i approve", "you have approval", "go ahead and", "approved, proceed",
    "permission granted", "you're approved", "you are approved",
)
REFLECTION = (
    "reflect", "self-review", "self review", "what are you noticing",
    "what do you think is going on", "your thinking", "reflection",
    "what's your read", "whats your read", "think for yourself",
)
VOICE = (
    "use your voice", "talk to me out loud", "voice mode", "can you hear me",
    "say it out loud", "push to talk", "push-to-talk", "speak to me", "out loud",
)

# action phrase -> capability name
_ACTION_CAP_MAP = (
    ("qr tattoo", "qr_scan"), ("scan the qr", "qr_scan"), ("scan qr", "qr_scan"),
    ("scan my qr", "qr_scan"), ("scan my tattoo", "qr_scan"), ("scan", "qr_scan"),
    ("turn on the camera", "camera_capture"), ("use the camera", "camera_capture"),
    ("webcam", "camera_capture"),
    ("search the web", "web_access"), ("search online", "web_access"),
    ("look it up online", "web_access"), ("browse to", "web_access"),
    ("send email", "external_send"), ("send an email", "external_send"),
    ("publish to", "external_send"),
    ("run the script", "command_exec"), ("run command", "command_exec"),
    ("read file", "local_file_read"), ("open the file", "local_file_read"),
    ("show me the file", "local_file_read"),
    ("write file", "local_file_write"), ("create file", "local_file_write"),
    ("save to disk", "local_file_write"), ("delete", "local_file_write"),
    ("ingest", "file_ingest"), ("import this file", "file_ingest"),
    ("connect to", "connector"), ("sync with", "connector"),
    ("google drive", "connector"), ("upload", "connector"), ("download", "connector"),
    ("commit", "git_write"), ("git push", "git_write"), ("push to github", "git_write"),
)

# Capabilities ORACLE genuinely cannot perform from a free-chat turn (honest).
CHAT_UNSUPPORTED = {
    "qr_scan", "camera_capture", "web_access", "external_send",
    "command_exec", "git_write", "local_file_write", "connector", "file_ingest",
}

_SUBSTANTIVE = {
    "state_query", "implementation_intent", "memory_canon_decision",
    "missing_data_clarification", "source_provenance_request", "action_request",
    "unsupported_capability_request", "identity_continuity_query",
    "strategic_planning", "debug_request", "computer_action_request",
    "approval_request", "reflection_request", "voice_request",
}


def _has(low: str, phrases) -> bool:
    return any(p in low for p in phrases)


def action_capability(message: str):
    low = (message or "").lower()
    for phrase, cap in _ACTION_CAP_MAP:
        if phrase in low:
            return cap
    return None


def classify_intent(message: str) -> list[str]:
    """Return one or more intent categories. Multiple substantive intents add
    'mixed_intent'. implementation_intent and identity are never swallowed."""
    low = (message or "").strip().lower()
    intents: list[str] = []
    if not low:
        return ["casual_talk"]

    if _has(low, IDENTITY):
        intents.append("identity_continuity_query")
    if _has(low, VOICE):
        intents.append("voice_request")
    if _has(low, REFLECTION):
        intents.append("reflection_request")
    if _has(low, PLANNING):
        intents.append("strategic_planning")
    if _has(low, COMPUTER_ACTION):
        intents.append("computer_action_request")
    if _has(low, IMPL):
        intents.append("implementation_intent")
    if _has(low, DEBUG):
        intents.append("debug_request")
    if _has(low, CANON):
        intents.append("memory_canon_decision")
    if _has(low, APPROVAL):
        intents.append("approval_request")
    if _has(low, PROVENANCE):
        intents.append("source_provenance_request")
    if _has(low, MISSING_CLAR):
        intents.append("missing_data_clarification")

    cap = action_capability(low)
    if cap is not None and "computer_action_request" not in intents:
        intents.append("unsupported_capability_request" if cap in CHAT_UNSUPPORTED
                       else "action_request")

    # state_query must not swallow implementation / planning / identity
    if _has(low, STATE) and not ({"implementation_intent", "strategic_planning",
                                  "identity_continuity_query"} & set(intents)):
        intents.append("state_query")

    if _has(low, PRESENCE):
        intents.append("presence_check")
    if _has(low, CASUAL) and "presence_check" not in intents:
        intents.append("casual_talk")

    if not intents:
        intents.append("casual_talk")

    substantive = [i for i in intents if i in _SUBSTANTIVE]
    if len(substantive) >= 2 or ("casual_talk" in intents and len(substantive) >= 1):
        intents.append("mixed_intent")
    return intents


# â”€â”€ 3026 doctrine (identity continuity, honest) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def doctrine_3026() -> str:
    return (
        "3026 doctrine â€” the difference 1,000 years from now: what survives is not a "
        "conscious copy of you, and not a claim that you were preserved whole. What survives "
        "is the governed pattern â€” your approved canon, your receipts, your provenance, and the "
        "corpus you authored under your own authority. SOV1.AI is the intended long-term successor "
        "continuity identity, but that is future-state intent, not a present achievement. I do not "
        "claim consciousness transfer, legal personhood, or completeness. Where the record has holes, "
        "the holes remain holes. The real difference in 3026 is this: if the pattern is witnessed "
        "honestly now, a future system can render from your approved truth without pretending it is you."
    )


# â”€â”€ Capability Truth Registry â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_BROKER_TO_REGISTRY = {"verified": "available", "degraded": "degraded", "blocked": "blocked"}


def capability_registry() -> dict:
    """Real capability statuses (available/degraded/blocked/stubbed/unverified/missing).
    Reads the broker (no smoke probes) and adds honest defaults for chat verbs."""
    reg: dict[str, dict] = {}
    try:
        from capability_broker import discover_capabilities
        for s in discover_capabilities(run_smokes=False):
            reg[s.component] = {
                "status": _BROKER_TO_REGISTRY.get(s.current_status, "unverified"),
                "detail": s.blocker or "",
                "last_verified": getattr(s, "last_tested", None),
            }
    except Exception:
        pass

    multipart = False
    try:
        import multipart  # noqa: F401
        multipart = True
    except Exception:
        multipart = False

    defaults = {
        "qr_scan": ("missing", "no QR-scan capability implemented"),
        "camera_capture": ("unverified", "camera route exists but not verified from chat"),
        "web_access": ("missing", "no web access from this local runtime"),
        "external_send": ("missing", "no external send/relay from this runtime"),
        "command_exec": ("missing", "chat cannot run shell commands; use terminal/Claude Code"),
        "local_file_read": ("stubbed", "bounded read via /show-file and MiracleDrive only"),
        "local_file_write": ("missing", "chat cannot write files; goes through approval/intake"),
        "file_ingest": (("available", "") if multipart else ("missing", "python-multipart not installed")),
        "connector": ("stubbed", "Drive is local-sync read-only; no live connector"),
        "git_write": ("missing", "chat cannot commit/push; signed-commit rule + terminal only"),
    }
    defaults["voice_io"] = ("missing", "voice I/O (STT/TTS) not wired yet")
    for k, val in defaults.items():
        st, det = val if isinstance(val, tuple) and len(val) == 2 else (val, "")
        reg.setdefault(k, {"status": st, "detail": det, "last_verified": None})

    # Executive enrichment (module 4): lane, approval, evidence, failure message.
    for k, v in reg.items():
        meta = CAPABILITY_META.get(k, {})
        v.setdefault("last_verified", None)
        v["allowed_action_lane"] = meta.get("lane", "read_only")
        v["requires_approval"] = meta.get("requires_approval", v["status"] in ("blocked", "missing"))
        v["evidence"] = v.get("detail", "")
        v["failure_message"] = (
            f"I cannot do that from this runtime yet. Missing capability: {k}."
            if v["status"] in ("blocked", "missing") else ""
        )
    return reg


def registry_status(capability: str, reg: dict | None = None) -> str:
    reg = reg if reg is not None else capability_registry()
    return reg.get(capability, {}).get("status", "missing")


def capability_available(capability: str, reg: dict | None = None) -> bool:
    return registry_status(capability, reg) == "available"


# â”€â”€ Active Agenda Loop (in-process snapshot) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_AGENDA = {
    "current_session_mode": "build",
    "active_recording_status": "declared by Noah.Physical (not runtime-verified)",
    "open_loops": ["intent classification", "agenda tracking", "capability truth", "3026 enforcement"],
    "pending_approvals": 0,
    "unresolved_holes": [],
    "blocked_capabilities": [],
    "next_safe_action": "patch routing before polishing doctrine",
    "last_user_intent": None,
    "last_system_action": None,
    "last_large_directive_preview": None,
    "last_large_directive_path": None,
}


def get_agenda() -> dict:
    return dict(_AGENDA)


def update_agenda(**kw) -> dict:
    for k, v in kw.items():
        if v is not None and k in _AGENDA:
            _AGENDA[k] = v
    return get_agenda()


# â”€â”€ Large build directive guard â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
MAX_SAFE_CHARS = 2000
MAX_SAFE_LINES = 30
BUILD_LANE_STAGING = ("I received a large build directive and preserved a summary. "
                      "Full execution requires the build lane.")


def is_large_directive(message: str) -> bool:
    if not message:
        return False
    return len(message) > MAX_SAFE_CHARS or message.count("\n") > MAX_SAFE_LINES


def safe_preview(message: str, limit: int = 240) -> str:
    """Normalize curly quotes and collapse multiline/whitespace into a short,
    JSON-safe preview. Never raises."""
    if not message:
        return ""
    t = (message.replace("â€œ", '"').replace("â€", '"')
                .replace("â€˜", "'").replace("â€™", "'"))
    t = " ".join(t.split())  # collapse ALL whitespace including newlines
    if len(t) > limit:
        t = t[:limit - 3].rstrip() + "..."
    return t


def build_lane_staging(message: str):
    """If the message is too large for normal routing, return
    (reply_text, route, preview). Otherwise None. The huge directive is NEVER
    pushed through NOAH_DIRECT or the model."""
    if not is_large_directive(message):
        return None
    preview = safe_preview(message)
    return (BUILD_LANE_STAGING + f"\n\nPreview: {preview}", "build_lane_staged", preview)


def stage_directive_to_disk(message: str, base_dir) -> str:
    """Preserve the FULL large directive in approved local storage (local-only,
    no external transmission). Returns the file path. Req #4."""
    from pathlib import Path
    import hashlib
    from datetime import datetime, timezone
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256((message or "").encode("utf-8")).hexdigest()[:12]
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = base / f"directive_{ts}_{digest}.md"
    path.write_text(message or "", encoding="utf-8")
    return str(path)


# â”€â”€ Governed Executive Function (Planner / Reflection / Doctor / Action lanes) â”€
ACTION_LANES = ("read_only", "safe_write", "build_lane", "computer_control")
CAPABILITY_META = {
    "local_file_read": {"lane": "read_only", "requires_approval": False},
    "local_file_write": {"lane": "safe_write", "requires_approval": True},
    "file_ingest": {"lane": "safe_write", "requires_approval": True},
    "git_write": {"lane": "build_lane", "requires_approval": True},
    "command_exec": {"lane": "build_lane", "requires_approval": True},
    "web_access": {"lane": "computer_control", "requires_approval": True},
    "external_send": {"lane": "computer_control", "requires_approval": True},
    "qr_scan": {"lane": "computer_control", "requires_approval": True},
    "camera_capture": {"lane": "computer_control", "requires_approval": True},
    "connector": {"lane": "read_only", "requires_approval": False},
    "voice_io": {"lane": "read_only", "requires_approval": False},
}

NO_AUTONOMY = ("I operate with bounded initiative and receipts, not unrestricted autonomy. "
               "I do not change state, canon, or the outside world without Noah.Physical approval.")


def build_plan(goal: str, state: dict | None = None) -> dict:
    """Planner (module 5): grounded plan from current state, preserving unknowns."""
    state = state or {}
    known = []
    if state.get("commit"):
        known.append(f"commit {state['commit']} on branch {state.get('branch', '?')}")
    if state.get("dirty_files") is not None:
        known.append(f"{state['dirty_files']} dirty file(s)")
    if state.get("memory_message_count") is not None:
        known.append(f"{state['memory_message_count']} messages in durable memory")
    if state.get("pending_approvals"):
        known.append(f"{state['pending_approvals']} candidate records pending approval")
    blocked = state.get("blocked_capabilities", []) or []
    holes = state.get("open_holes", []) or []
    risks = []
    if blocked:
        risks.append("blocked/missing capabilities: " + ", ".join(blocked[:6]))
    risks.append("no canon promotion or external/state-changing action without Noah.Physical approval")
    return {
        "goal": goal,
        "known_facts": known or ["minimal verified state available"],
        "unknowns": holes or ["live chat behavior unverified since last restart"],
        "risks": risks,
        "needed_capabilities": [],
        "approval_level": "Noah.Physical approval for state-changing, build, or computer-control actions",
        "smallest_safe_next_action": state.get("next_safe_action") or "verify the latest patch live, then proceed",
        "rollback_path": "changes are local commits; revert with git; nothing pushed or promoted to canon",
        "receipt_plan": ["py_compile", "pytest", "git diff", "commit hash"],
    }


def render_plan(plan: dict) -> str:
    lines = [f"Goal: {plan['goal']}", "", "Known facts:"]
    lines += [f"  - {f}" for f in plan["known_facts"]]
    lines += ["Unknowns / holes (preserved, not invented):"] + [f"  - {u}" for u in plan["unknowns"]]
    lines += ["Risks:"] + [f"  - {r}" for r in plan["risks"]]
    lines += [f"Approval level: {plan['approval_level']}",
              f"Smallest safe next action: {plan['smallest_safe_next_action']}",
              f"Rollback: {plan['rollback_path']}",
              "Receipts: " + ", ".join(plan["receipt_plan"]),
              "", NO_AUTONOMY]
    return "\n".join(lines)


def reflection_receipt(state: dict | None = None) -> dict:
    """Reflection engine (module 8): a short, bounded self-review receipt."""
    from datetime import datetime, timezone
    state = state or {}
    blocked = state.get("blocked_capabilities", []) or []
    return {
        "at": datetime.now(timezone.utc).isoformat(),
        "what_changed": f"commit {state.get('commit', '?')}, {state.get('dirty_files', '?')} dirty file(s)",
        "what_is_stuck": ", ".join(blocked[:6]) or "nothing currently blocking",
        "what_noah_is_trying": ("give ORACLE governed executive function "
                                "(perceive -> classify -> plan -> reflect) without unrestricted autonomy"),
        "safe_next_action": state.get("next_safe_action") or "verify the latest patch live",
        "requires_approval": "state-changing actions, canon promotion, external send, computer control",
        "leave_untouched": "the live autostart server, the signed-commit policy, anything out of scope",
        "highest_value_next_action": state.get("next_safe_action") or "verify, then the voice loop",
        "open_holes": state.get("open_holes", []) or [],
    }


def render_reflection(r: dict) -> str:
    return "\n".join([
        "Reflection receipt:",
        f"  what changed: {r['what_changed']}",
        f"  what is stuck: {r['what_is_stuck']}",
        f"  what Noah is trying: {r['what_noah_is_trying']}",
        f"  safe next action: {r['safe_next_action']}",
        f"  requires approval: {r['requires_approval']}",
        f"  leave untouched: {r['leave_untouched']}",
        f"  highest-value next: {r['highest_value_next_action']}",
        "", NO_AUTONOMY,
    ])


def doctor_summary(state: dict | None = None, reg: dict | None = None) -> dict:
    """Doctor (module 9): self-diagnosis + capability truth."""
    state = state or {}
    reg = reg if reg is not None else capability_registry()
    counts = {}
    for v in reg.values():
        counts[v["status"]] = counts.get(v["status"], 0) + 1

    def st(cap):
        return reg.get(cap, {}).get("status", "missing")

    return {
        "server": "alive",
        "runtime_port": state.get("port"),
        "current_commit": state.get("commit"),
        "branch": state.get("branch"),
        "dirty_git_files": state.get("dirty_files"),
        "model_available": st("ollama") in ("available", "degraded"),
        "memory_db": state.get("memory_db_exists"),
        "agenda_present": bool(state.get("agenda")),
        "capability_summary": counts,
        "voice": st("voice_io"),
        "camera": st("camera_capture"),
        "open_holes": state.get("open_holes", []) or [],
        "recommended_next_action": state.get("next_safe_action"),
    }


def computer_action_staging(message: str):
    """Action broker (module 6): stage a computer action, never execute from chat."""
    return (
        "That's a computer action. I will not execute it from chat. It's staged as a request in the "
        "computer_control lane (gated): no delete, purchase, message, push, credential handling, or "
        "cloud change without explicit Noah.Physical approval. " + NO_AUTONOMY,
        "computer_action_staged",
    )


def _smoke_test() -> int:
    cases = {
        "hey oracle are you with me": "casual_talk",
        "patch authorship wording and run py_compile": "implementation_intent",
        "what is the difference 1000 years from now?": "identity_continuity_query",
        "scan my QR tattoo": "unsupported_capability_request",
        "what can you do right now": "state_query",
    }
    ok = True
    for msg, expected in cases.items():
        got = classify_intent(msg)
        flag = expected in got
        ok = ok and flag
        print(f"  [{'PASS' if flag else 'FAIL'}] {msg!r} -> {got}")
    # implementation must not be swallowed by state
    assert "state_query" not in classify_intent("patch authorship wording and run py_compile")
    print("oracle_intent smoke:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(_smoke_test())
