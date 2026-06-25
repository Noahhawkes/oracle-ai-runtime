"""
core/oracle_intent.py — Intent Classification + Active Agenda + Capability Truth Registry

Minimal, honest runtime structures for ORACLE chat. No fake capabilities, no fake
sentience. Classification is keyword/phrase based and testable without booting the
server. The agenda is an in-process snapshot; the registry reads the real
capability broker plus honest defaults for verbs the broker does not track.
"""
from __future__ import annotations

# ── Intent categories ────────────────────────────────────────────────────────
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
    if _has(low, IMPL):
        intents.append("implementation_intent")
    if _has(low, CANON):
        intents.append("memory_canon_decision")
    if _has(low, PROVENANCE):
        intents.append("source_provenance_request")
    if _has(low, MISSING_CLAR):
        intents.append("missing_data_clarification")

    cap = action_capability(low)
    if cap is not None:
        intents.append("unsupported_capability_request" if cap in CHAT_UNSUPPORTED
                       else "action_request")

    # state_query, but do NOT let it swallow an implementation_intent
    if _has(low, STATE) and "implementation_intent" not in intents:
        intents.append("state_query")

    if _has(low, CASUAL):
        intents.append("casual_talk")

    if not intents:
        intents.append("casual_talk")

    substantive = [i for i in intents if i in _SUBSTANTIVE]
    if len(substantive) >= 2 or ("casual_talk" in intents and len(substantive) >= 1):
        intents.append("mixed_intent")
    return intents


# ── 3026 doctrine (identity continuity, honest) ──────────────────────────────
def doctrine_3026() -> str:
    return (
        "3026 doctrine — the difference 1,000 years from now: what survives is not a "
        "conscious copy of you, and not a claim that you were preserved whole. What survives "
        "is the governed pattern — your approved canon, your receipts, your provenance, and the "
        "corpus you authored under your own authority. SOV1.AI is the intended long-term successor "
        "continuity identity, but that is future-state intent, not a present achievement. I do not "
        "claim consciousness transfer, legal personhood, or completeness. Where the record has holes, "
        "the holes remain holes. The real difference in 3026 is this: if the pattern is witnessed "
        "honestly now, a future system can render from your approved truth without pretending it is you."
    )


# ── Capability Truth Registry ────────────────────────────────────────────────
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
    for k, val in defaults.items():
        st, det = val if isinstance(val, tuple) and len(val) == 2 else (val, "")
        reg.setdefault(k, {"status": st, "detail": det})
    return reg


def registry_status(capability: str, reg: dict | None = None) -> str:
    reg = reg if reg is not None else capability_registry()
    return reg.get(capability, {}).get("status", "missing")


def capability_available(capability: str, reg: dict | None = None) -> bool:
    return registry_status(capability, reg) == "available"


# ── Active Agenda Loop (in-process snapshot) ─────────────────────────────────
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


# ── Large build directive guard ──────────────────────────────────────────────
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
    t = (message.replace("“", '"').replace("”", '"')
                .replace("‘", "'").replace("’", "'"))
    t = " ".join(t.split())  # collapse ALL whitespace including newlines
    if len(t) > limit:
        t = t[:limit] + "…"
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
