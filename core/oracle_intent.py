"""
core/oracle_intent.py â€” Intent Classification + Active Agenda + Capability Truth Registry

Minimal, honest runtime structures for ORACLE chat. No fake capabilities, no fake
sentience. Classification is keyword/phrase based and testable without booting the
server. The agenda is an in-process snapshot; the registry reads the real
capability broker plus honest defaults for verbs the broker does not track.
"""
from __future__ import annotations

import re

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
    "create module",
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
    "promote to canon", "make this canon", "is this canon", "reject this",
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
    "you choose", "recommended next step", "recommended next action", "what should i do next", "what should you do next",
    "continue self prompt", "continue the self prompt", "self prompt", "self-prompt",
    "write to sandbox", "sandbox write", "sandbox-only write",
)
TALK_ONLY_MARKERS = (
    "talk lane only",
    "simple question",
    "not a build order",
    "not strategic planning",
    "not a build request",
)
DIAGNOSTIC_TALK_MARKERS = (
    "diagnostic test",
    "backend diagnostic test",
    "oracle backend diagnostic test",
    "answer only from current runtime",
    "read-only diagnostic",
    "diagnostic only",
    "report only",
    "status only",
)
READ_ONLY_BOUNDARY_MARKERS = (
    "no sandbox write",
    "no sandbox mutation",
    "no external action",
    "no canon promotion",
    "do not execute",
    "do not write",
    "do not mutate",
    "do not touch external systems",
)
DIAGNOSTIC_QUESTION_MARKERS = (
    "what live subsystem state",
    "what can you not prove",
    "what can you not verify",
    "what do you remember",
    "what do you know",
    "from receipts",
    "did a sandbox write occur",
    "answer only",
    "if unknown",
    "do not invent",
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
    "approval given", "approval granted", "noah approval given",
    "noah hawkes approval given", "noah.physical approval given",
    "noah physical approval given",
)
REFLECTION = (
    "reflect", "self-review", "self review", "what are you noticing",
    "what do you think is going on", "your thinking", "reflection",
    "what's your read", "whats your read", "think for yourself",
)
VOICE = (
    "use your voice", "talk to me out loud", "voice mode", "can you hear me",
    "say it out loud", "push to talk", "push-to-talk", "out loud",
)

# Read-only file operations. Verified read access is not ingest authority, but
# it is also never "missing": these lanes list, search, inspect, and cite.
FILE_READONLY_CAPS = {
    "local_file_read", "file_search", "file_index_read",
    "file_metadata_read", "file_manifest_read", "file_receipt_read",
}
# Mutation / execution file operations. These require an explicit imperative;
# naming one is never enough to route here.
FILE_MUTATION_CAPS = {
    "file_ingest_stage", "local_file_write", "file_delete", "file_execute",
}

# action phrase -> capability name
_ACTION_CAP_MAP = (
    ("qr tattoo", "qr_scan"), ("scan the qr", "qr_scan"), ("scan qr", "qr_scan"),
    ("scan my qr", "qr_scan"), ("scan my tattoo", "qr_scan"),
    ("scan my documents", "local_file_read"), ("scan my files", "local_file_read"),
    ("scan all drives", "local_file_read"), ("scan the drive", "local_file_read"),
    ("turn on the camera", "camera_capture"), ("use the camera", "camera_capture"),
    ("webcam", "camera_capture"),
    ("search the web", "web_access"), ("search online", "web_access"),
    ("look it up online", "web_access"), ("browse to", "web_access"),
    ("send email", "external_send"), ("send an email", "external_send"),
    ("publish to", "external_send"),
    ("run the script", "command_exec"), ("run command", "command_exec"),
    ("read file", "local_file_read"), ("open the file", "local_file_read"),
    ("show me the file", "local_file_read"),
    # Read-only file lanes: search / index / manifest / receipt lookups.
    ("search my files", "file_search"), ("search the index", "file_index_read"),
    ("search the corpus", "file_search"),
    ("manifest lookup", "file_manifest_read"), ("look up the manifest", "file_manifest_read"),
    ("receipt lookup", "file_receipt_read"), ("look up the receipt", "file_receipt_read"),
    ("write file", "local_file_write"), ("create file", "local_file_write"),
    ("save to disk", "local_file_write"),
    # Mutation verbs need an explicit object; bare "delete"/"ingest" are words
    # that appear constantly in status text, prohibitions, and quoted panels.
    ("delete this file", "file_delete"), ("delete the file", "file_delete"),
    ("delete that file", "file_delete"),
    ("ingest this folder", "file_ingest_stage"), ("ingest that folder", "file_ingest_stage"),
    ("ingest this file", "file_ingest_stage"), ("ingest these files", "file_ingest_stage"),
    ("import this file", "file_ingest_stage"), ("ingest this directory", "file_ingest_stage"),
    ("execute this script", "file_execute"),
    ("connect to", "connector"), ("sync with", "connector"),
    ("google drive", "connector"), ("upload", "connector"), ("download", "connector"),
    ("git commit", "git_write"), ("git push", "git_write"), ("push to github", "git_write"),
    ("commit this", "git_write"), ("commit and push", "git_write"),
)

# Capabilities ORACLE genuinely cannot perform from a free-chat turn (honest).
# Note: file_ingest_stage is NOT here — an explicit ingest request routes to the
# staging/build lane under approval, it is not a missing capability.
CHAT_UNSUPPORTED = {
    "camera_capture", "external_send",
    "command_exec", "git_write", "connector",
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


def _has_phrase(low: str, phrase: str) -> bool:
    needle = str(phrase or "").strip()
    if not needle:
        return False
    if re.fullmatch(r"[\w+-]+", needle):
        return re.search(rf"\b{re.escape(needle)}\b", low) is not None
    return needle in low


def _has_any_phrase(low: str, phrases) -> bool:
    return any(_has_phrase(low, phrase) for phrase in phrases)


# â”€â”€ Capability mention vs. capability request â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Naming a capability is not requesting its execution. Status panels, quoted
# diagnostics, snapshot blocks, and directive prose all *mention* capabilities
# ("Missing capability: file_ingest", "summarize this ingest status"). Only text
# that survives as a plausible imperative may route to a mutation lane. Same bug
# class as the Guard prohibition-list fix in unified_oracle_router.
_QUOTED_SPAN_RE = re.compile(r"\"[^\"]*\"|'[^']*'|`[^`]*`")
_DIRECTIVE_OPEN_RE = re.compile(r"^\s*(?:@[A-Z_]+\[|\.AI:)")

# Lines that report, quote, or ask *about* capability state rather than ask for it.
_MENTION_LINE_MARKERS = (
    "missing capability", "capability:", "capability panel", "capability status",
    "capabilities:", "capability broker", "the broker", "broker says",
    "broker reports", "is missing", "is available", "not available",
    "read_only_status", "status:", "snapshot", "frontend_", "backend_",
    "supplied_by", "unverified", "summarize", "compare", "explain",
    "what does", "what do you", "can you read", "why did", "why does",
    "diagnostic", "does not include", "reported a missing",
)

# Snapshot/status lines: "- visible_mode: Talk" or "api_history_session_id: 335".
# Deliberately narrow so a real request ("Task: ingest this folder now") survives.
_SNAPSHOT_LINE_RE = re.compile(
    r"^\s*[-â€¢*]\s*[\w.]+\s*:\s*\S|^\s*[a-z0-9]+_[a-z0-9_]*\s*:\s*\S", re.IGNORECASE
)


def capability_request_surface(text: str) -> str:
    """Return only the text that can plausibly be an execution *request*.

    Quoted spans, directive blocks, and status/diagnostic lines are dropped:
    mentioning a capability there is reporting on it, not asking for it."""
    raw = str(text or "")
    if not raw.strip():
        return ""
    body = _QUOTED_SPAN_RE.sub(" ", raw)
    kept: list[str] = []
    in_directive = False
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _DIRECTIVE_OPEN_RE.match(stripped):
            in_directive = True
            continue
        if in_directive:
            if stripped.startswith("]"):
                in_directive = False
            continue
        low = stripped.lower()
        if any(marker in low for marker in _MENTION_LINE_MARKERS):
            continue
        if _SNAPSHOT_LINE_RE.match(stripped):
            continue
        kept.append(stripped)
    return "\n".join(kept)


def action_capability(message: str, *, respect_mentions: bool = True):
    """Map a message to the capability it actually *requests*.

    Mutation capabilities require an explicit imperative on the request surface;
    read-only capabilities may still match the raw text, because reading is not
    gated and a read intent is safe to detect generously."""
    raw_low = (message or "").lower()
    surface_low = (capability_request_surface(message).lower()
                   if respect_mentions else raw_low)
    for phrase, cap in _ACTION_CAP_MAP:
        # Read-only lanes: generous matching (detecting a read is harmless).
        # Everything else must appear on the request surface, word-bounded.
        haystack = raw_low if cap in FILE_READONLY_CAPS else surface_low
        if _has_phrase(haystack, phrase):
            return cap
    return None


_STATUS_ONLY_MARKERS = (
    "report exactly",
    "answer on screen only from your current runtime",
    "current runtime/status/receipts",
    "if you cannot verify",
    "match_test_done",
    "no execution",
    "no write",
    "no sandbox mutation",
    "read-only match test",
)

_STATUS_FIELD_MARKERS = (
    "current_mode",
    "file_read_scope_or_roots",
    "ai_lockbox_capsule_count",
    "sandbox_self_prompt_journal_path",
    "latest_self_prompt_novelty_status",
)


def _is_read_only_status_request(message: str, low: str) -> bool:
    """True for receipt/status readbacks that mention action words as facts."""
    surface = capability_request_surface(message).strip()
    if surface:
        return False
    norm = low.replace("-", "_")
    marker_hits = sum(1 for marker in _STATUS_ONLY_MARKERS if marker in low)
    field_hits = sum(1 for marker in _STATUS_FIELD_MARKERS if marker in norm)
    return marker_hits >= 2 or field_hits >= 2


def _is_talk_only_override(low: str) -> bool:
    return any(marker in low for marker in TALK_ONLY_MARKERS)


def _is_diagnostic_talk_request(low: str) -> bool:
    has_diagnostic = any(marker in low for marker in DIAGNOSTIC_TALK_MARKERS)
    boundary_hits = sum(1 for marker in READ_ONLY_BOUNDARY_MARKERS if marker in low)
    question_hits = sum(1 for marker in DIAGNOSTIC_QUESTION_MARKERS if marker in low)
    return bool(has_diagnostic and (boundary_hits >= 1 or question_hits >= 1))


def classify_intent(message: str) -> list[str]:
    """Return one or more intent categories. Multiple substantive intents add
    'mixed_intent'. implementation_intent and identity are never swallowed."""
    low = (message or "").strip().lower()
    intents: list[str] = []
    if not low:
        return ["casual_talk"]

    status_only = _is_read_only_status_request(message, low)
    talk_only = _is_talk_only_override(low)
    diagnostic_talk = _is_diagnostic_talk_request(low)
    suppress_planning = status_only or talk_only or diagnostic_talk

    if _has(low, IDENTITY):
        intents.append("identity_continuity_query")
    if _has(low, VOICE):
        intents.append("voice_request")
    if _has(low, REFLECTION):
        intents.append("reflection_request")
    if _has(low, PLANNING) and not suppress_planning:
        intents.append("strategic_planning")
    if _has(low, COMPUTER_ACTION):
        intents.append("computer_action_request")
    if _has_any_phrase(low, IMPL) and not status_only:
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

    if (status_only or diagnostic_talk) and "state_query" not in intents:
        intents.append("state_query")

    # state_query must not swallow implementation / planning / identity
    if _has(low, STATE) and not ({"implementation_intent", "strategic_planning",
                                  "identity_continuity_query"} & set(intents)):
        intents.append("state_query")

    if talk_only and "casual_talk" not in intents and "presence_check" not in intents:
        intents.append("casual_talk")

    if _has(low, PRESENCE):
        intents.append("presence_check")
    if _has(low, CASUAL) and "presence_check" not in intents:
        intents.append("casual_talk")

    if not intents:
        # Unmatched text is NOT presence/casual — let it fall through to the
        # existing pending / approval / guard / companion routing.
        intents.append("unclassified")

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
        "qr_scan": (
            "available",
            "local image QR decode is available for supplied PNG/JPG/BMP/WEBP/TIFF files; no live camera or physical-arm scan from chat",
        ),
        "camera_capture": ("unverified", "camera route exists but not verified from chat"),
        "web_access": ("available", "read-only internet_recall lane; no browser control, login, forms, send, or canon promotion"),
        "external_send": ("missing", "no external send/relay from this runtime"),
        "command_exec": ("missing", "chat cannot run shell commands; use terminal/Claude Code"),
        "full_pc_readonly": (
            "available",
            "Noah.Physical granted full-PC read-only search/list/metadata/supported text-docx preview; sensitive paths can be inventoried by metadata; no approval required for ordinary reads",
        ),
        "local_file_read": (
            "available",
            "full-PC read-only file_recall lane; no approval required for search/list/read previews; raw credential values are never auto-ingested or receipted",
        ),
        "local_file_write": (
            "available",
            "sandbox-only filebase write lane; sandbox initiative does not require Noah approval; "
            "hard wall outside sandbox; receipts required; no execution, external send, git push, or canon promotion",
        ),
        "sandbox_file_write": (
            "available",
            "native sandbox/filebase capability for .AI and /sandbox commands; includes no-approval sandbox initiative; hard wall outside sandbox",
        ),
        "file_ingest": (("available", "") if multipart else ("missing", "python-multipart not installed")),
        # Read-only file operations: verified read access, never ingest authority.
        "file_search": ("available", "read-only indexed/direct search over broker-permitted roots; cites source; no mutation"),
        "file_index_read": ("available", "read-only index lookup; no reindex, no write"),
        "file_metadata_read": ("available", "read-only path/size/mtime metadata; sensitive paths inventoried by metadata only"),
        "file_manifest_read": ("available", "read-only manifest retrieval; no manifest mutation"),
        "file_receipt_read": ("available", "read-only receipt retrieval; no receipt forging or promotion"),
        # Staged mutation: allowed to be *requested*, gated on approval.
        "file_ingest_stage": (
            ("available", "explicit ingest requests stage a candidate under Noah.Physical approval; staging is not execution")
            if multipart else ("missing", "python-multipart not installed")
        ),
        "file_delete": ("missing", "chat cannot delete files; no delete authority from this runtime"),
        "file_execute": ("missing", "chat cannot execute files or scripts; use terminal/Claude Code"),
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
BUILD_DIRECTIVE_MARKERS = (
    "backend_patch_request",
    "self_patch_staging_request",
    "thread_pass",
    ".ai build pass",
    ".ai:thread_pass",
)
BUILD_DIRECTIVE_TERMS = (
    "patch", "build", "implement", "write code", "write the code",
    "save directive", "stage plan", "stage the plan", "stage the build",
    "backend patch", "self patch", "add endpoint", "add test", "run tests",
)
TALK_EXPLANATION_TERMS = (
    "?", "what is", "who is", "why", "how", "can you talk", "talk to me",
    "speak to me", "explain", "in your own words", "tell me about",
    "recall", "what do you remember",
)


def is_large_directive(message: str) -> bool:
    if not message:
        return False
    return len(message) > MAX_SAFE_CHARS or message.count("\n") > MAX_SAFE_LINES


def is_build_directive_preservation_candidate(message: str) -> bool:
    """True only for explicit or oversized implementation directives.

    Size protects the model context, but size alone must not steal normal Talk.
    Explicit build markers are custody directives even when short.
    """
    low = (message or "").strip().lower()
    if low.startswith("/talk"):
        return False
    if low.startswith("/learn"):
        return True
    if any(low.startswith(marker) for marker in BUILD_DIRECTIVE_MARKERS):
        return True
    if not is_large_directive(message):
        return False
    if any(term in low for term in TALK_EXPLANATION_TERMS) and not any(
        term in low for term in BUILD_DIRECTIVE_TERMS
    ):
        return False
    return any(term in low for term in BUILD_DIRECTIVE_TERMS)


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
    if not is_build_directive_preservation_candidate(message):
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
    "local_file_write": {"lane": "safe_write", "requires_approval": False},
    "sandbox_file_write": {"lane": "safe_write", "requires_approval": False},
    "file_ingest": {"lane": "safe_write", "requires_approval": True},
    # Read-only file lanes never require approval; they cannot mutate.
    "file_search": {"lane": "read_only", "requires_approval": False},
    "file_index_read": {"lane": "read_only", "requires_approval": False},
    "file_metadata_read": {"lane": "read_only", "requires_approval": False},
    "file_manifest_read": {"lane": "read_only", "requires_approval": False},
    "file_receipt_read": {"lane": "read_only", "requires_approval": False},
    # Staged/blocked mutation lanes.
    "file_ingest_stage": {"lane": "safe_write", "requires_approval": True},
    "file_delete": {"lane": "build_lane", "requires_approval": True},
    "file_execute": {"lane": "build_lane", "requires_approval": True},
    "git_write": {"lane": "build_lane", "requires_approval": True},
    "command_exec": {"lane": "build_lane", "requires_approval": True},
    "web_access": {"lane": "read_only", "requires_approval": False},
    "external_send": {"lane": "computer_control", "requires_approval": True},
    "qr_scan": {"lane": "read_only", "requires_approval": False},
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
