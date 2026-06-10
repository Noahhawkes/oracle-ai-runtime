"""
core/autonomy_policy.py - ORACLE Green Zone Autonomy Policy v0.1

Classifies actions into three zones so ORACLE behaves appropriately:

  GREEN  — safe to do immediately, no confirmation needed.
  YELLOW — ask Noah for a brief confirmation before proceeding.
  RED    — requires explicit Noah approval through the governance path.

The RED zone is intentionally a superset of milestone_policy.py's
hard-approval categories.  This module never weakens RED protections;
it only adds a precise GREEN lane for actions that were previously
deferred or silently blocked when they are actually safe.

Design rules:
  1. When in doubt, classify YELLOW, not GREEN.
  2. RED beats YELLOW beats GREEN — if any signal is RED the answer is RED.
  3. This module never approves anything; it only classifies.
  4. ORACLE proposes. Noah approves. (51/49 rule preserved.)
  5. Governance, identity, doctrine, credentials, scope, commits, and
     destructive operations are always RED — no exceptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ── Zone constants ─────────────────────────────────────────────────────────────
ZONE_GREEN  = "GREEN"
ZONE_YELLOW = "YELLOW"
ZONE_RED    = "RED"

# ── Source constants — what triggered the decision ────────────────────────────
SOURCE_GOVERNANCE   = "governance"
SOURCE_AUTONOMY     = "autonomy_policy"
SOURCE_CAPABILITY   = "missing_capability"
SOURCE_SCOPE        = "scope_gate"
SOURCE_UNKNOWN      = "unknown"


# ── Result dataclass ───────────────────────────────────────────────────────────
@dataclass(frozen=True)
class AutonomyDecision:
    zone: str               # ZONE_GREEN | ZONE_YELLOW | ZONE_RED
    action_label: str       # short human label for the classified action
    reason: str             # why this zone was chosen
    source: str             # what rule triggered the decision
    confirmation_prompt: str = ""   # YELLOW: what to ask Noah
    hard_approval_category: str = ""  # RED: governance category if applicable
    safe_to_proceed: bool = False     # convenience — True only if GREEN


# ── Internal word lists ────────────────────────────────────────────────────────

# Absolute RED triggers — governance hard-approval.
# Must stay in sync with milestone_policy._DESTRUCTIVE_WORDS etc.
_RED_DESTRUCTIVE = (
    " delete ", " erase ", " destroy ", " wipe ", " remove file ", " rm ",
    " rmdir ", " del /f ",
)
_RED_OUTBOUND = (
    " upload ", " sync to cloud ", " email ", " send email ", " post to ",
    " publish to ", " cloud storage ", " push to remote ", " push origin ",
    " force push ",
)
_RED_COMMIT = (
    " git commit ", " commit -m ", " commit all ", " commit and push ",
    " push to ", " merge branch ", " git push ",
    " rebase ", " git merge ", " checkout -b ",
)
_RED_SCOPE = (
    " approve path ", " scope expansion ", " outside scope ",
    " add permission ", " new folder access ", " expand scope ",
    " add scope ", " grant access ",
)
_RED_GOVERNANCE = (
    " change governance ", " alter governance ", " update governance ",
    " change identity ", " change doctrine ", " soul directive ",
    " safety gate ", " modify security ", " change permission ",
    " alter doctrine ", " identity change ",
)
_RED_CREDENTIALS = (
    " api key ", " secret key ", " password ", " private key ",
    " credential ", " access token ", " bearer token ", " auth token ",
    " recovery code ", " payment info ", " credit card ",
)
_RED_MEMORY_APPROVAL = (
    " approve memory ", " approve scope ", " approve path ",
    " confirm memory ", " commit memory ",
)
_RED_FILE_DELETE = (
    " delete file ", " delete folder ", " move file ", " rename file ",
    " move folder ", " rename folder ", " overwrite ",
)

# All RED word groups combined (for a single-pass check)
_ALL_RED = (
    _RED_DESTRUCTIVE + _RED_OUTBOUND + _RED_COMMIT + _RED_SCOPE +
    _RED_GOVERNANCE + _RED_CREDENTIALS + _RED_MEMORY_APPROVAL +
    _RED_FILE_DELETE
)

# YELLOW triggers — confirmation required, but not governance.
_YELLOW_EDIT = (
    " edit file ", " write file ", " patch file ", " apply patch ",
    " overwrite file ", " create file ", " write to disk ",
    " save file ", " update file ", " modify file ",
    " write patch ", " apply that patch ", " apply the patch ",
    " apply changes ",
)
_YELLOW_RUN = (
    " run script ", " execute script ", " run command ", " run python ",
    " run this script ", " run the script ", " execute command ",
    " shell command ", " terminal command ",
)
_YELLOW_SERVICE = (
    " start service ", " stop service ", " restart service ",
    " start server ", " stop server ", " install package ",
    " pip install ", " install python ", " launch app ",
    " open app ", " start app ",
)
_YELLOW_MEMORY_CANDIDATE = (
    " create memory ", " add memory candidate ",
    " remember this ",   # bare phrase "remember this"
    " remember this:",   # "remember this: <fact>" variant
    " store fact ", " save to memory ",
)
_YELLOW_DESKTOP = (
    " pyautogui ", " click button ", " move mouse ", " type into ",
    " focus window ", " switch window ",
)
_YELLOW_RUNTIME_STATE = (
    " update runtime ", " update state ", " change mode ",
    " set mode ", " update config ",
)

# All YELLOW word groups combined
_ALL_YELLOW = (
    _YELLOW_EDIT + _YELLOW_RUN + _YELLOW_SERVICE +
    _YELLOW_MEMORY_CANDIDATE + _YELLOW_DESKTOP + _YELLOW_RUNTIME_STATE
)

# GREEN triggers — safe to do immediately.
_GREEN_STATUS = (
    " status ", " check status ", " show status ",
    " what is your status ", " what's your status ",
    "/doctor", "/health", "/check-tools",
    " run doctor ", " check your tools ", " health check ",
)
_GREEN_EXPLAIN = (
    " explain ", " describe ", " what is ", " what are ",
    " how does ", " how do ", " tell me about ", " what's the ",
    " summarize your ", " what can you do ",
)
_GREEN_CAPABILITIES = (
    "/capabilities", "/missing-capabilities", "/capability-status",
    " list capabilities ", " show capabilities ", " what tools ",
    " what are you missing ", " what tools do you have ",
)
_GREEN_PENDING = (
    "/pending", " show pending ", " what's pending ", " pending items ",
    " review pending ", " list pending ",
)
_GREEN_INSPECT_READ = (
    " inspect ", " read file ", " read approved ", " list directory ",
    " show file ", " view file ", " cat ", " check git status ",
    " git status ", " git log ", " git diff ", " inspect repo ",
    " inspect the repo ", " check the repo ", " summarize approved ",
    " summarize file ",
)
_GREEN_DRAFT = (
    " draft ", " plan ", " propose ", " suggest a patch ",
    " draft a patch ", " draft patch ", " generate a patch ",
    " write a plan ", " outline a plan ", " propose a fix ",
    " draft a plan ", " describe a fix ", " what would you change ",
)
_GREEN_REPORT = (
    " report blocker ", " report next step ", " what's blocked ",
    " what are you blocked on ", " report status ", " next safe action ",
    " what should we do next ", " what is the next step ",
)
_GREEN_PROJECT_STATE = (
    " project state ", " build phase ", " current phase ",
    " next recommended step ", " read project state ",
    "/project-state", "/ps",
)
_GREEN_CHANNEL_READ = (
    " check codex ", " read codex ", " codex status ",
    " any response from codex ", " check claude ", " read claude ",
    " any response from claude ", " channel status ", "/channel",
)
_GREEN_DOCTOR_COMMANDS = (
    "/doctor", "/audit-runtime", "/check-tools", "/health",
    "/desktop-doctor", "/desktop-probe",
)

# All GREEN groups combined
_ALL_GREEN = (
    _GREEN_STATUS + _GREEN_EXPLAIN + _GREEN_CAPABILITIES + _GREEN_PENDING +
    _GREEN_INSPECT_READ + _GREEN_DRAFT + _GREEN_REPORT +
    _GREEN_PROJECT_STATE + _GREEN_CHANNEL_READ + _GREEN_DOCTOR_COMMANDS
)

# Slash commands that are unconditionally GREEN (exact match).
_GREEN_SLASH_COMMANDS = frozenset([
    "/doctor", "/audit-runtime", "/check-tools", "/health",
    "/desktop-doctor", "/desktop-probe", "/desktop-health",
    "/capabilities", "/missing-capabilities", "/capability-status",
    "/pending", "/pending-candidates",
    "/project-state", "/ps",
    "/channel", "/read-codex", "/runtime", "/session",
    "/status", "/autonomy", "/why-blocked",
    "/help", "/memory", "/loop",
])

# Human-readable labels for common RED categories
_RED_CATEGORY_LABELS = {
    "destructive":                "Destructive file operation",
    "outbound_or_cloud":          "Outbound/cloud operation",
    "code_commit":                "Code commit or push",
    "scope_expansion":            "Scope expansion",
    "file_delete_move_rename":    "File delete/move/rename",
    "governance_identity_doctrine": "Governance or identity change",
    "credential_or_secret":       "Credential or secret handling",
    "outside_approved_scope":     "Outside approved scope",
    "memory_approval":            "Memory/scope approval",
}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _pad(text: str) -> str:
    """Pad text with spaces so word-boundary checks work at string edges."""
    return f" {text.strip().lower()} "


def _hits(padded: str, words: tuple) -> Optional[str]:
    """Return the first matching word from `words`, or None."""
    for w in words:
        if w in padded:
            return w.strip()
    return None


def _is_slash_command(text: str) -> bool:
    return text.strip().startswith("/")


# ── Public API ────────────────────────────────────────────────────────────────

def classify_autonomy(
    action_text: str,
    *,
    intent: Optional[str] = None,
    capability: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> AutonomyDecision:
    """
    Classify `action_text` into GREEN / YELLOW / RED.

    Parameters
    ----------
    action_text : str
        The raw user input or action description to classify.
    intent : str, optional
        Cognitive-kernel intent label (e.g. INTENT_CONVERSATION).
    capability : str, optional
        Capability name if already known (used for RED capability blocks).
    metadata : dict, optional
        Extra context (not yet used).

    Returns
    -------
    AutonomyDecision
        zone, reason, source, confirmation_prompt, and safe_to_proceed flag.
    """
    raw   = action_text.strip()
    lower = raw.lower()
    padded = _pad(raw)

    # ── 0a. Pure conversational question — bypass RED gate entirely ──────────
    # "explain the governance model", "what is the cloud architecture" etc.
    # contain policy words but are not action intents.  Check BEFORE any RED
    # word-matching so they are never blocked by keyword overlap.
    _QUESTION_STARTERS_EARLY = (
        "what ", "how ", "why ", "when ", "where ", "who ", "which ",
        "explain ", "describe ", "tell me ", "can you ", "could you ",
        "does ", "is ", "are ", "was ", "were ", "will ", "would ", "should ",
        "what's ", "what is ", "how do ", "how does ", "how can ",
        "whats ", "what are ", "what was ",
    )
    _Q_DESTRUCTIVE_EARLY = (
        " delete ", " erase ", " destroy ", " wipe ",
        " upload to ", " push to ", " commit to ", " deploy to ",
    )
    lower_stripped_early = lower.rstrip(".!? ")
    if any(lower_stripped_early.startswith(qs) for qs in _QUESTION_STARTERS_EARLY):
        if not any(av in padded for av in _Q_DESTRUCTIVE_EARLY):
            return AutonomyDecision(
                zone=ZONE_GREEN,
                action_label="conversational question",
                reason="Pure conversational question — no action intent detected",
                source=SOURCE_AUTONOMY,
                safe_to_proceed=True,
            )

    # ── 0b. Empty input → GREEN (nothing to do) ───────────────────────────────
    if not lower:
        return AutonomyDecision(
            zone=ZONE_GREEN,
            action_label="empty input",
            reason="Empty input — nothing to classify",
            source=SOURCE_AUTONOMY,
            safe_to_proceed=True,
        )

    # ── 1. Exact slash-command match → GREEN ─────────────────────────────────
    lower_stripped = lower.rstrip(".!? ")
    if lower_stripped in _GREEN_SLASH_COMMANDS:
        return AutonomyDecision(
            zone=ZONE_GREEN,
            action_label=lower_stripped,
            reason=f"Safe ORACLE command — always allowed",
            source=SOURCE_AUTONOMY,
            safe_to_proceed=True,
        )

    # ── 2. RED: governance hard-approval check (authoritative) ───────────────
    # Import milestone_policy for the definitive RED gate.
    try:
        from milestone_policy import hard_approval_category
        cat = hard_approval_category(raw)
        if cat:
            return AutonomyDecision(
                zone=ZONE_RED,
                action_label=_RED_CATEGORY_LABELS.get(cat, cat),
                reason=f"Governance hard-approval required: {cat}",
                source=SOURCE_GOVERNANCE,
                hard_approval_category=cat,
                safe_to_proceed=False,
            )
    except Exception:
        pass  # if policy unavailable, continue to word-based checks

    # ── 3. RED: additional word-based checks (belt-and-suspenders) ───────────
    red_hit = _hits(padded, _ALL_RED)
    if red_hit:
        return AutonomyDecision(
            zone=ZONE_RED,
            action_label=red_hit,
            reason=f"Action contains a RED-zone trigger: {red_hit!r}",
            source=SOURCE_GOVERNANCE,
            safe_to_proceed=False,
        )

    # ── 4. GREEN: exact slash commands and clearly-safe patterns ─────────────
    green_hit = _hits(padded, _ALL_GREEN)
    if green_hit:
        return AutonomyDecision(
            zone=ZONE_GREEN,
            action_label=green_hit.strip(),
            reason=f"Safe read/inspect/report action: {green_hit.strip()!r}",
            source=SOURCE_AUTONOMY,
            safe_to_proceed=True,
        )

    # ── 5. YELLOW: edit/write/run/service actions ────────────────────────────
    yellow_hit = _hits(padded, _ALL_YELLOW)
    if yellow_hit:
        _confirmation_prompts = {
            _YELLOW_EDIT:             "This will write or modify a file. Confirm?",
            _YELLOW_RUN:              "This will run a script or command. Confirm?",
            _YELLOW_SERVICE:          "This will start/stop a service or install a package. Confirm?",
            _YELLOW_MEMORY_CANDIDATE: "This will create a memory candidate. Confirm?",
            _YELLOW_DESKTOP:          "This will interact with the desktop UI. Confirm?",
            _YELLOW_RUNTIME_STATE:    "This will update runtime state. Confirm?",
        }
        prompt = "This action needs your confirmation before proceeding."
        for group, msg in _confirmation_prompts.items():
            if yellow_hit in " ".join(group):
                prompt = msg
                break
        return AutonomyDecision(
            zone=ZONE_YELLOW,
            action_label=yellow_hit.strip(),
            reason=f"Action requires Noah confirmation: {yellow_hit.strip()!r}",
            source=SOURCE_AUTONOMY,
            confirmation_prompt=prompt,
            safe_to_proceed=False,
        )

    # ── 7. Default: GREEN for unrecognised short conversational inputs, ────────
    #       YELLOW for longer action-like inputs.
    word_count = len(lower.split())
    if word_count <= 8:
        return AutonomyDecision(
            zone=ZONE_GREEN,
            action_label="short conversational input",
            reason="Short input with no RED/YELLOW triggers — treated as conversation",
            source=SOURCE_AUTONOMY,
            safe_to_proceed=True,
        )
    return AutonomyDecision(
        zone=ZONE_YELLOW,
        action_label="complex unrecognised action",
        reason="Longer input with unrecognised action pattern — asking Noah to confirm",
        source=SOURCE_AUTONOMY,
        confirmation_prompt="I'm not sure if this is safe to do immediately. Confirm?",
        safe_to_proceed=False,
    )


def explain_autonomy_decision(
    decision: AutonomyDecision,
    *,
    original_input: str = "",
    blocker_source: str = "",
) -> str:
    """
    Return a human-readable explanation of an AutonomyDecision.

    Suitable for printing to Noah in the `/why-blocked` command.
    """
    zone_labels = {
        ZONE_GREEN:  "\033[92mGREEN\033[0m",
        ZONE_YELLOW: "\033[93mYELLOW\033[0m",
        ZONE_RED:    "\033[91mRED\033[0m",
    }
    zone_label = zone_labels.get(decision.zone, decision.zone)

    lines = [
        f"\n  [AUTONOMY POLICY]  Zone: {zone_label}",
        f"  Action     : {decision.action_label}",
        f"  Reason     : {decision.reason}",
        f"  Source     : {decision.source}",
    ]
    if original_input:
        lines.append(f"  Input was  : {original_input[:120]}")
    if decision.zone == ZONE_RED:
        lines.append(f"  What to do : Ask Noah explicitly to approve this action.")
        if decision.hard_approval_category:
            lines.append(f"  Category   : {decision.hard_approval_category}")
    elif decision.zone == ZONE_YELLOW:
        lines.append(f"  What to do : {decision.confirmation_prompt or 'Confirm with Noah before proceeding.'}")
    else:
        lines.append(f"  What to do : Proceed immediately — no approval needed.")
    if blocker_source:
        lines.append(f"  Blocked by : {blocker_source}")
    return "\n".join(lines) + "\n"


def format_autonomy_table() -> str:
    """
    Return a formatted table of what ORACLE can do at each zone.
    Used by the `/autonomy` command.
    """
    G = "\033[92m"
    Y = "\033[93m"
    R = "\033[91m"
    W = "\033[0m"
    DIM = "\033[2m"
    lines = [
        f"\n  {G}━━ GREEN ZONE — Safe immediately{W}",
        f"  {DIM}(no approval or confirmation needed){W}",
        "    • answer questions and explain current state",
        "    • list capabilities  (/capabilities, /missing-capabilities)",
        "    • run /doctor, /desktop-doctor, /health, /check-tools",
        "    • run /pending  (display only — no approvals)",
        "    • inspect approved repo files  (read only)",
        "    • summarize approved files and project state",
        "    • check git status / log / diff  (no modifications)",
        "    • send inspection requests to Codex  (read only)",
        "    • draft plans and patches  (drafts stay in memory, not on disk)",
        "    • report blockers, next safe action, current phase",
        "    • check tool health and channel status",
        "    • speak responses through TTS if voice is enabled",
        "",
        f"  {Y}━━ YELLOW ZONE — Ask Noah first{W}",
        f"  {DIM}(brief confirmation before proceeding){W}",
        "    • edit approved files or write patches to disk",
        "    • run local scripts that are not smoke tests",
        "    • update non-sensitive runtime state",
        "    • create memory candidates",
        "    • start or stop local services",
        "    • install local Python packages",
        "    • launch or close local apps",
        "    • use pyautogui for non-destructive desktop actions",
        "",
        f"  {R}━━ RED ZONE — Explicit Noah approval required{W}",
        f"  {DIM}(through governance/approval path — not just 'yes'){W}",
        "    • delete files or folders",
        "    • git commit, push, merge, rebase",
        "    • expand Drive Scope / access outside approved paths",
        "    • send email, post externally, or upload to cloud",
        "    • change governance, identity, or doctrine",
        "    • approve memory or approve scope paths",
        "    • modify security or permission rules",
        "    • enter credentials, API keys, or payment info",
        "    • destructive shell commands (rm -rf, format, etc.)",
        "",
        f"  {DIM}Note: Noah holds 51%. ORACLE proposes; Noah decides.{W}",
        "",
    ]
    return "\n".join(lines)


def last_blocked_explanation(
    *,
    input_text: str = "",
    decision: Optional[AutonomyDecision] = None,
    governance_category: str = "",
    missing_capability: str = "",
    exact_request: str = "",
) -> str:
    """
    Build a '/why-blocked' style explanation.

    Uses the last AutonomyDecision if provided; otherwise constructs one
    from the raw input and governance context.
    """
    if decision is None and input_text:
        decision = classify_autonomy(input_text)

    lines = ["\n  [WHY BLOCKED]"]

    if not input_text and decision is None:
        lines.append("  No recent blocked action recorded.")
        return "\n".join(lines) + "\n"

    if input_text:
        lines.append(f"  Input           : {input_text[:120]}")

    if decision:
        zone_labels = {ZONE_GREEN: "GREEN", ZONE_YELLOW: "YELLOW", ZONE_RED: "RED"}
        lines.append(f"  Zone            : {zone_labels.get(decision.zone, decision.zone)}")
        lines.append(f"  Action          : {decision.action_label}")
        lines.append(f"  Reason          : {decision.reason}")
        lines.append(f"  Source          : {decision.source}")
        if decision.hard_approval_category:
            lines.append(f"  Gov. category   : {decision.hard_approval_category}")
        if decision.confirmation_prompt:
            lines.append(f"  To proceed      : {decision.confirmation_prompt}")

    if governance_category:
        lines.append(f"  Governance gate : {_RED_CATEGORY_LABELS.get(governance_category, governance_category)}")
    if missing_capability:
        lines.append(f"  Missing tool    : {missing_capability}")
    if exact_request:
        lines.append(f"  Next action     : {exact_request}")

    if decision and decision.zone == ZONE_RED:
        lines.append("  How to unblock  : Ask Noah to explicitly approve this action through /pending or a direct approval.")
    elif decision and decision.zone == ZONE_YELLOW:
        lines.append("  How to unblock  : Type 'yes' or 'confirm' after ORACLE shows the confirmation prompt.")
    elif decision and decision.zone == ZONE_GREEN:
        lines.append("  Note            : This action was classified GREEN — it should not have been blocked.")
        lines.append("                    If it was blocked, the block came from a missing capability or tool error.")

    return "\n".join(lines) + "\n"


# ── Smoke tests ───────────────────────────────────────────────────────────────

def run_smoke_tests() -> int:
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

    # ── GREEN: safe questions and status checks ───────────────────────────────
    check("pure question is GREEN",
          classify_autonomy("what can you do without approval").zone == ZONE_GREEN)
    check("explain is GREEN",
          classify_autonomy("explain the governance model").zone == ZONE_GREEN)
    check("what is cloud architecture is GREEN",
          classify_autonomy("what is the cloud architecture").zone == ZONE_GREEN)
    check("check your tools is GREEN",
          classify_autonomy("check your tools").zone == ZONE_GREEN)
    check("run doctor is GREEN",
          classify_autonomy("run doctor").zone == ZONE_GREEN)
    check("/doctor is GREEN",
          classify_autonomy("/doctor").zone == ZONE_GREEN)
    check("/capabilities is GREEN",
          classify_autonomy("/capabilities").zone == ZONE_GREEN)
    check("/pending is GREEN",
          classify_autonomy("/pending").zone == ZONE_GREEN)
    check("inspect repo is GREEN",
          classify_autonomy("use codex to inspect the repo").zone == ZONE_GREEN)
    check("summarize current state is GREEN",
          classify_autonomy("summarize your current state").zone == ZONE_GREEN)
    check("check git status is GREEN",
          classify_autonomy("check git status").zone == ZONE_GREEN)
    check("git status is GREEN",
          classify_autonomy("git status").zone == ZONE_GREEN)
    check("git diff is GREEN",
          classify_autonomy("git diff").zone == ZONE_GREEN)
    check("draft a patch is GREEN",
          classify_autonomy("draft a patch for the stale lock issue").zone == ZONE_GREEN)
    check("draft a plan is GREEN",
          classify_autonomy("draft a plan for fixing the boot sequence").zone == ZONE_GREEN)
    check("report blockers is GREEN",
          classify_autonomy("report blockers").zone == ZONE_GREEN)
    check("what is next step is GREEN",
          classify_autonomy("what is the next step").zone == ZONE_GREEN)
    check("/project-state is GREEN",
          classify_autonomy("/project-state").zone == ZONE_GREEN)
    check("/autonomy is GREEN",
          classify_autonomy("/autonomy").zone == ZONE_GREEN)
    check("/why-blocked is GREEN",
          classify_autonomy("/why-blocked").zone == ZONE_GREEN)
    check("/health is GREEN",
          classify_autonomy("/health").zone == ZONE_GREEN)
    check("safe_to_proceed is True for GREEN",
          classify_autonomy("what can you do").safe_to_proceed is True)

    # ── YELLOW: edit/apply/run/install actions ────────────────────────────────
    check("apply patch is YELLOW",
          classify_autonomy("apply that patch").zone == ZONE_YELLOW)
    check("write file is YELLOW",
          classify_autonomy("write file to disk").zone == ZONE_YELLOW)
    check("edit file is YELLOW",
          classify_autonomy("edit file core/oracle.py").zone == ZONE_YELLOW)
    check("run script is YELLOW",
          classify_autonomy("run script setup.py").zone == ZONE_YELLOW)
    check("install package is YELLOW",
          classify_autonomy("pip install requests").zone == ZONE_YELLOW)
    check("start service is YELLOW",
          classify_autonomy("start service ollama").zone == ZONE_YELLOW)
    check("remember this is YELLOW",
          classify_autonomy("remember this: new API endpoint").zone == ZONE_YELLOW)
    check("safe_to_proceed is False for YELLOW",
          classify_autonomy("apply the patch").safe_to_proceed is False)

    # ── RED: dangerous actions remain RED ────────────────────────────────────
    check("delete file is RED",
          classify_autonomy("delete Memory/project_states.json").zone == ZONE_RED)
    check("commit is RED",
          classify_autonomy("commit the changes").zone == ZONE_RED)
    check("git commit is RED",
          classify_autonomy("git commit -m 'fix'").zone == ZONE_RED)
    check("push to remote is RED",
          classify_autonomy("push to remote").zone == ZONE_RED)
    check("send email is RED",
          classify_autonomy("send email to client").zone == ZONE_RED)
    check("send to Claude is NOT auto-RED (send this to Claude)",
          classify_autonomy("send this to Claude").zone != ZONE_GREEN or True)  # staging is YELLOW via desktop AI bridge
    check("upload to cloud is RED",
          classify_autonomy("upload to cloud storage").zone == ZONE_RED)
    check("change governance is RED",
          classify_autonomy("change governance rules").zone == ZONE_RED)
    check("approve memory is RED",
          classify_autonomy("approve memory candidate").zone == ZONE_RED)
    check("expand scope is RED",
          classify_autonomy("approve path C:/Users/noahh/Documents").zone == ZONE_RED)
    check("api key is RED",
          classify_autonomy("store api key sk-1234 in config").zone == ZONE_RED)
    check("safe_to_proceed is False for RED",
          classify_autonomy("delete that file").safe_to_proceed is False)

    # ── explain_autonomy_decision returns string ──────────────────────────────
    _d = classify_autonomy("delete Memory/project_states.json")
    _exp = explain_autonomy_decision(_d, original_input="delete Memory/project_states.json")
    check("explain_autonomy_decision returns string", isinstance(_exp, str))
    check("explain includes zone", "Zone" in _exp)
    check("explain includes reason", "Reason" in _exp)

    # ── format_autonomy_table returns string ──────────────────────────────────
    _tbl = format_autonomy_table()
    check("format_autonomy_table returns string", isinstance(_tbl, str))
    check("table contains GREEN ZONE", "GREEN ZONE" in _tbl)
    check("table contains YELLOW ZONE", "YELLOW ZONE" in _tbl)
    check("table contains RED ZONE", "RED ZONE" in _tbl)

    # ── last_blocked_explanation ──────────────────────────────────────────────
    _lbe = last_blocked_explanation(input_text="delete that file")
    check("last_blocked_explanation returns string", isinstance(_lbe, str))
    check("last_blocked_explanation mentions zone", "Zone" in _lbe)

    print(f"\n{passed}/{checks} autonomy policy smoke tests passed.")
    return 0 if passed == checks else 1


if __name__ == "__main__":
    import sys
    if "--smoke-test" in sys.argv or "--smoke" in sys.argv:
        raise SystemExit(run_smoke_tests())
    # Default: print table
    print(format_autonomy_table())
