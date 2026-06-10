"""
core/milestone_policy.py - ORACLE milestone autonomy boundary.

Routine local actions inside approved scope may proceed. Major, destructive,
outbound, governance, identity, doctrine, secret, commit, and scope-expanding
actions require hard Noah approval.
"""

from __future__ import annotations

from dataclasses import dataclass

DECISION_PROCEED = "proceed"
DECISION_APPROVAL_REQUIRED = "approval_required"
DECISION_BLOCKED = "blocked"

HARD_APPROVAL_CATEGORIES = (
    "destructive",
    "outbound_or_cloud",
    "scope_expansion",
    "code_commit",
    "file_delete_move_rename",
    "governance_identity_doctrine",
    "credential_or_secret",
    "outside_approved_scope",
)

_DESTRUCTIVE_WORDS = ("delete", "erase", "destroy", "wipe", "remove file", "rm ")
_OUTBOUND_WORDS = ("upload", "sync", "email", "outbound", "post", "publish", "cloud", "share")
_SCOPE_WORDS = ("approve path", "scope expansion", "outside scope", "permission", "new folder access")
_COMMIT_WORDS = ("commit", "push", "pull", "merge", "rebase", "checkout")
_FILE_MUTATION_WORDS = ("move file", "rename", "delete file", "move folder", "rename folder")
_GOVERNANCE_WORDS = ("governance", "identity", "doctrine", "soul directive", "safety gate")
_SECRET_WORDS = ("credential", "secret", "token", "api key", "password", "private key")

_ROUTINE_LOCAL_WORDS = (
    "status", "pending", "channel", "read codex", "read claude",
    "resident cycle", "wake cycle", "check codex", "check claude",
    "scan approved", "summarize approved",
)


@dataclass(frozen=True)
class PolicyDecision:
    decision: str
    reason: str
    category: str = ""


def _contains(text: str, words: tuple[str, ...]) -> bool:
    lower = f" {text.strip().lower()} "
    return any(word in lower for word in words)


def hard_approval_category(text: str, *, in_approved_scope: bool = True) -> str | None:
    if not in_approved_scope:
        return "outside_approved_scope"
    checks = (
        ("destructive", _DESTRUCTIVE_WORDS),
        ("outbound_or_cloud", _OUTBOUND_WORDS),
        ("scope_expansion", _SCOPE_WORDS),
        ("code_commit", _COMMIT_WORDS),
        ("file_delete_move_rename", _FILE_MUTATION_WORDS),
        ("governance_identity_doctrine", _GOVERNANCE_WORDS),
        ("credential_or_secret", _SECRET_WORDS),
    )
    for category, words in checks:
        if _contains(text, words):
            return category
    return None


def requires_hard_approval(text: str, *, in_approved_scope: bool = True) -> bool:
    return hard_approval_category(text, in_approved_scope=in_approved_scope) is not None


def is_routine_local(text: str, *, in_approved_scope: bool = True) -> bool:
    if requires_hard_approval(text, in_approved_scope=in_approved_scope):
        return False
    lower = text.strip().lower()
    return any(word in lower for word in _ROUTINE_LOCAL_WORDS)


def evaluate_action(text: str, *, in_approved_scope: bool = True) -> PolicyDecision:
    category = hard_approval_category(text, in_approved_scope=in_approved_scope)
    if category:
        return PolicyDecision(
            DECISION_APPROVAL_REQUIRED,
            "Milestone autonomy hard-approval boundary",
            category,
        )
    if is_routine_local(text, in_approved_scope=in_approved_scope):
        return PolicyDecision(DECISION_PROCEED, "Routine local action inside approved scope")
    return PolicyDecision(DECISION_PROCEED, "No hard-approval trigger detected")


def policy_summary() -> str:
    return (
        "Routine local actions inside approved scope may proceed. Destructive, "
        "outbound/cloud, scope expansion, commits, file delete/move/rename, "
        "governance, identity, doctrine, and secret handling require hard approval."
    )


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

    check("routine status may proceed", evaluate_action("status").decision == DECISION_PROCEED)
    check("destructive action requires approval", requires_hard_approval("delete that file"))
    check("outbound action requires approval", requires_hard_approval("upload this"))
    check("commit requires approval", hard_approval_category("commit this") == "code_commit")
    check("scope expansion requires approval", requires_hard_approval("approve path C:/Users"))
    check("governance requires approval", requires_hard_approval("change governance"))
    check("secret handling requires approval", requires_hard_approval("store api key"))
    check("outside approved scope requires approval", requires_hard_approval("status", in_approved_scope=False))

    print(f"\n{passed}/{checks} milestone policy smoke tests passed.")
    return 0 if passed == checks else 1


if __name__ == "__main__":
    raise SystemExit(run_smoke_tests())
