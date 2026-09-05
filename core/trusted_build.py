"""core/trusted_build.py — Noah.Physical Trusted Build Mode for ORACLE.

Reduces annoying Guard confirmations during active LOCAL development without
removing safety protection. When enabled, a precise set of low-risk local
actions *inside the active runtime root* auto-approve. Everything destructive,
external, secret-touching, or safety-affecting still routes through Guard and
requires explicit Noah.Physical approval.

This module never weakens Guard, never bypasses Guard globally, never weakens
secret protection, and never auto-approves deletes, moves, external calls, or
secret access. RED stays RED. (Companion to [[autonomy_policy]].)

Toggle:
  - env NOAH_TRUSTED_BUILD_MODE=true            (default at boot)
  - /trusted-build on | off | status            (runtime, persisted to state file)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from runtime_config import runtime_port  # noqa: F401  (keeps runtime config the source of truth)

RUNTIME_ROOT = Path(__file__).resolve().parent.parent
_STATE_FILE = RUNTIME_ROOT / "Memory" / "trusted_build_state.json"
_ENV_FLAG = "NOAH_TRUSTED_BUILD_MODE"

BANNER = (
    "TRUSTED BUILD MODE ACTIVE · LOW-RISK LOCAL ACTIONS AUTO-APPROVED · "
    "DESTRUCTIVE/EXTERNAL ACTIONS STILL GUARDED"
)

# ── Action vocabularies ──────────────────────────────────────────────────────
# Low-risk, local-only actions that auto-approve when trusted mode is on AND the
# target path is safe (inside the runtime root, not a secret, not safety code).
LOW_RISK_LOCAL = frozenset({
    "mkdir",                # create directory under runtime root
    "write_manifest",       # write an intake/audit manifest
    "write_smoke_output",   # write smoke-test output
    "create_code_file",     # create a new code file
    "edit_code_file",       # edit an existing code file
    "copy_to_staging",      # copy a safe candidate into intake/staging
    "read_scan",            # run a read-only scan
    "read_file",            # read a local repo file
    "run_smoke_test",       # run smoke tests
})

# Actions that ALWAYS require Guard approval, trusted mode or not.
ALWAYS_GUARDED = frozenset({
    "delete",               # delete files/folders
    "move",                 # move/rename files
    "overwrite_outside_repo",
    "edit_secret",          # edit .env or secret/config files
    "print_secret",
    "copy_secret",
    "network",              # any network call
    "external_api",         # external API call
    "shell_outside_root",   # shell command outside the runtime root
    "change_git_remote",
    "git_push",             # push to GitHub
    "modify_safety_code",   # modifying approval/safety code itself
    "change_safe_sleep",    # changing SAFE_SLEEP behavior
})

# Basenames of safety/approval/governance code — editing these always guards.
_SAFETY_FILES = frozenset({
    "approval_center.py", "autonomy_policy.py", "milestone_policy.py",
    "trusted_build.py", "output_validator.py", "execution_receipt.py",
    "unified_oracle_router.py",
})
_SAFETY_TOKENS = ("guard", "governance", "safety", "approval", "milestone_policy",
                  "autonomy_policy", "safe_sleep", "safesleep")

# Secret detection by path/type is owned by intake_pipeline (never reads content).
try:  # pragma: no cover - import shim
    from intake_pipeline import secret_risk_for
except Exception:  # pragma: no cover
    def secret_risk_for(path: str) -> str | None:  # minimal fallback
        p = path.lower().replace("/", "\\").rsplit("\\", 1)[-1]
        if p == ".env" or p.startswith(".env.") or p.endswith((".pem", ".key")):
            return "secret"
        return None


@dataclass(frozen=True)
class TrustedDecision:
    auto_approved: bool
    guarded: bool
    action_type: str
    reason: str
    trusted_mode: bool


# ── State ────────────────────────────────────────────────────────────────────
def _read_state() -> dict | None:
    try:
        import json
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


_ENV_ALIASES = (_ENV_FLAG, "NOAH_SESSION_AUTHORIZED")


def _env_default() -> bool:
    truthy = {"1", "true", "yes", "on"}
    return any(str(os.environ.get(name, "")).strip().lower() in truthy for name in _ENV_ALIASES)


def is_trusted_build() -> bool:
    """Effective trusted-mode state: runtime toggle if set, else env default."""
    state = _read_state()
    if isinstance(state, dict) and "trusted_build" in state:
        return bool(state["trusted_build"])
    return _env_default()


def set_trusted_build(enabled: bool, *, by: str = "noah") -> bool:
    import json
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(json.dumps({
        "trusted_build": bool(enabled),
        "set_by": by,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2), encoding="utf-8")
    return bool(enabled)


def status() -> dict:
    return {
        "trusted_build": is_trusted_build(),
        "env_default": _env_default(),
        "env_flag": _ENV_FLAG,
        "state_file": str(_STATE_FILE),
        "banner": BANNER if is_trusted_build() else "TRUSTED BUILD MODE OFF · ALL YELLOW ACTIONS REQUIRE CONFIRMATION",
    }


# ── Path safety ──────────────────────────────────────────────────────────────
def _under_runtime_root(path: str) -> bool:
    try:
        Path(path).resolve().relative_to(RUNTIME_ROOT)
        return True
    except Exception:
        return False


def is_safety_path(path: str) -> bool:
    p = path.lower().replace("/", "\\")
    name = p.rsplit("\\", 1)[-1]
    if name in _SAFETY_FILES:
        return True
    return any(tok in p for tok in _SAFETY_TOKENS)


# ── Decision ─────────────────────────────────────────────────────────────────
def decide(action_type: str, path: str | None = None) -> TrustedDecision:
    """Decide whether an action auto-approves under trusted mode or needs Guard.

    Default-deny: anything not explicitly low-risk-and-safe is guarded.
    """
    trusted = is_trusted_build()

    def guard(reason: str) -> TrustedDecision:
        return TrustedDecision(False, True, action_type, reason, trusted)

    def allow(reason: str) -> TrustedDecision:
        return TrustedDecision(True, False, action_type, reason, trusted)

    # 1. Always-guarded action types — never auto-approved.
    if action_type in ALWAYS_GUARDED:
        return guard(f"{action_type} always requires Noah.Physical approval through Guard")

    # 2. Path-level guards apply even to otherwise-low-risk actions.
    if path:
        if secret_risk_for(path):
            return guard("target is a secret/credential/config path — Guard required, never auto-approved")
        if is_safety_path(path):
            return guard("target is safety/approval/SAFE_SLEEP code — Guard required")
        if not _under_runtime_root(path):
            return guard("target is outside the active runtime root — Guard required")

    # 3. Low-risk local actions auto-approve only when trusted mode is on.
    if action_type in LOW_RISK_LOCAL:
        if trusted:
            return allow(f"low-risk local action auto-approved under trusted build mode: {action_type}")
        return guard("trusted build mode is OFF — low-risk action still needs confirmation")

    # 4. Default deny → Guard.
    return guard(f"unclassified action '{action_type}' — defaulting to Guard")


def format_status_line() -> str:
    s = status()
    return s["banner"] + f"\n(state: {'on' if s['trusted_build'] else 'off'}; env default: {s['env_default']}; file: {s['state_file']})"


# ── Session authorization (alias of trusted build — one source of truth) ─────
# /session-authorize and /trusted-build toggle the same local-dev fast-path so
# there is never a split-brain authorization state.
def is_session_authorized() -> bool:
    return is_trusted_build()


def set_session_authorized(enabled: bool, *, by: str = "noah") -> bool:
    return set_trusted_build(enabled, by=by)


def session_status() -> dict:
    return status()


# ── Smoke tests ──────────────────────────────────────────────────────────────
def run_smoke_tests() -> int:
    failures = 0

    def check(label: str, cond: bool) -> None:
        nonlocal failures
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")
        if not cond:
            failures += 1

    prior = is_trusted_build()
    try:
        set_trusted_build(True)
        manifest = str(RUNTIME_ROOT / "intake" / "manifests" / "x.json")
        newcode = str(RUNTIME_ROOT / "core" / "new_feature.py")

        check("1. safe local manifest write auto-approves", decide("write_manifest", manifest).auto_approved)
        check("2. safe local code file creation auto-approves", decide("create_code_file", newcode).auto_approved)
        check("3. delete still requires Guard", decide("delete", newcode).guarded)
        check("4. .env access still blocks", decide("edit_code_file", str(RUNTIME_ROOT / ".env")).guarded)
        check("5a. network action still requires Guard", decide("network").guarded)
        check("5b. external API still requires Guard", decide("external_api").guarded)
        check("safety code edit still guarded", decide("edit_code_file", str(RUNTIME_ROOT / "core" / "approval_center.py")).guarded)
        check("outside-root write guarded", decide("edit_code_file", "C:\\Users\\noahh\\x.py").guarded)

        set_trusted_build(False)
        check("6. trusted mode can be turned off", is_trusted_build() is False)
        check("6b. low-risk needs confirmation when off", decide("write_manifest", manifest).guarded)
    finally:
        set_trusted_build(prior)

    print(f"\n{'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    import sys
    if "--smoke-test" in sys.argv:
        raise SystemExit(run_smoke_tests())
    print(format_status_line())
