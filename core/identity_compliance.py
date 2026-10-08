"""
core/identity_compliance.py — ORACLE Identity Compliance Layer

Intercepts governance, identity, memory, and sovereignty statements from Noah
before they reach the LLM, classifies them, and returns a governed acknowledgment.

Problem this solves:
    When Noah says "ORACLE is not a chatbot", the LLM responds with generic
    generic utility language. That is a governance failure. The statement should be
    recognized, classified, and acknowledged with precision — not paraphrased,
    not softened, not turned into a "how can I help?" response.

Classification:
    identity_rule     — what ORACLE is and is not
    memory_rule       — what ORACLE may store, own, or remember
    sovereignty_rule  — 51/49 authority, who decides what becomes memory
    pipeline_rule     — Raw Activity -> Events -> Context -> ... -> Action
    action_rule       — what ORACLE may or may not execute
    governance_general — other governance or directive statements

Status:
    canonical   — already locked in ORACLE doctrine (Soul Directive, IDENTITYFRAME v1)
    pending     — newly stated, not yet in canonical doctrine — routes to candidate store
    conflicting — contradicts existing canonical rule — must be flagged

IdentityFrame v1 constraint:
    Do not inflate. Do not soften. Do not reinterpret.
    Preserve exact wording. Preserve the hole.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ── Canonical rules — locked. Exact wording. Status: canonical. ───────────────
# Source: ORACLE_SOUL_DIRECTIVE.md, IDENTITYFRAME_v1.md, AUTONOMY_READINESS_GATE.md

CANONICAL_RULES: list[dict] = [
    # Identity
    {
        "pattern": r"oracle is not a chatbot",
        "type": "identity_rule",
        "canonical_text": "ORACLE is not a chatbot. ORACLE is a consent-based local context engine.",
        "source": "ORACLE_SOUL_DIRECTIVE.md",
    },
    {
        "pattern": r"oracle is a consent.based local context engine",
        "type": "identity_rule",
        "canonical_text": "ORACLE is a consent-based local context engine.",
        "source": "ORACLE_SOUL_DIRECTIVE.md",
    },
    {
        "pattern": r"product is continuity",
        "type": "identity_rule",
        "canonical_text": "The product is continuity, not raw capture.",
        "source": "ORACLE_SOUL_DIRECTIVE.md",
    },
    {
        "pattern": r"not raw capture",
        "type": "identity_rule",
        "canonical_text": "The product is continuity, not raw capture.",
        "source": "ORACLE_SOUL_DIRECTIVE.md",
    },
    # Memory rules
    {
        "pattern": r"oracle does not remember everything",
        "type": "memory_rule",
        "canonical_text": (
            "ORACLE does not remember everything it sees. "
            "ORACLE compresses observed activity into approved meaning."
        ),
        "source": "ORACLE_SOUL_DIRECTIVE.md",
    },
    {
        "pattern": r"compresses observed activity",
        "type": "memory_rule",
        "canonical_text": "ORACLE compresses observed activity into approved meaning.",
        "source": "ORACLE_SOUL_DIRECTIVE.md",
    },
    {
        "pattern": r"oracle sees it.*does not mean oracle owns",
        "type": "memory_rule",
        "canonical_text": (
            "If ORACLE sees it, that does not mean ORACLE owns it. "
            "Visibility is not ownership. Observation does not grant memory rights or action rights."
        ),
        "source": "IDENTITYFRAME_v1.md",
    },
    {
        "pattern": r"seeing.*not owning|visibility.*not ownership|sees.*not own",
        "type": "memory_rule",
        "canonical_text": (
            "Visibility is not ownership. "
            "ORACLE seeing data does not mean ORACLE owns it."
        ),
        "source": "IDENTITYFRAME_v1.md",
    },
    {
        "pattern": r"oracle renders it.*does not mean oracle remembers",
        "type": "memory_rule",
        "canonical_text": (
            "If ORACLE renders it, that does not mean ORACLE remembers it. "
            "Rendering is not storage. Candidate meaning requires Noah approval before becoming memory."
        ),
        "source": "IDENTITYFRAME_v1.md",
    },
    {
        "pattern": r"renders.*not.*remember|rendering.*not.*storage",
        "type": "memory_rule",
        "canonical_text": (
            "Rendering is not storage. "
            "ORACLE rendering data does not mean ORACLE remembers it."
        ),
        "source": "IDENTITYFRAME_v1.md",
    },
    # Sovereignty rules
    {
        "pattern": r"only noah decides what becomes memory",
        "type": "sovereignty_rule",
        "canonical_text": (
            "Only Noah decides what becomes memory. "
            "Noah holds memory authority under the 51% sovereignty role. "
            "ORACLE may propose memory candidates only."
        ),
        "source": "ORACLE_SOUL_DIRECTIVE.md / IDENTITYFRAME_v1.md",
    },
    {
        "pattern": r"noah decides.*memory|noah holds.*51|51.*sovereignty",
        "type": "sovereignty_rule",
        "canonical_text": (
            "Noah holds the sovereign 51%. SOV1.AI and ORACLE execute the operational 49%. "
            "The system may render, suggest, and structure, "
            "but Noah alone approves, rejects, corrects, deletes, revokes, or quarantines."
        ),
        "source": "IDENTITYFRAME_v1.md",
    },
    {
        "pattern": r"51.?49|49.?51",
        "type": "sovereignty_rule",
        "canonical_text": (
            "51/49 Human Sovereignty Rule: "
            "Noah holds the sovereign 51%. ORACLE executes the operational 49%. "
            "ORACLE may render, suggest, and structure. "
            "Noah alone approves, rejects, corrects, deletes, revokes, or quarantines."
        ),
        "source": "IDENTITYFRAME_v1.md",
    },
    # Pipeline rule
    {
        "pattern": r"raw activity.*events.*context|events.*context.*meaning",
        "type": "pipeline_rule",
        "canonical_text": (
            "Pipeline: Raw Activity -> Events -> Context -> Meaning -> "
            "Memory -> Retrieval -> Action"
        ),
        "source": "ORACLE_SOUL_DIRECTIVE.md",
    },
    # Preserve the hole
    {
        "pattern": r"preserve the hole|absence is data",
        "type": "memory_rule",
        "canonical_text": (
            "Preserve the hole. Absence is data. "
            "Do not complete what cannot be verified. "
            "If a memory is missing, the archive must preserve the hole."
        ),
        "source": "IDENTITYFRAME_v1.md",
    },
    # ORACLE 49% role
    {
        "pattern": r"oracle performs the 49|oracle.*49.*role",
        "type": "sovereignty_rule",
        "canonical_text": (
            "ORACLE performs the 49% role: fetch, parse, filter, structure, suggest, render candidates. "
            "Noah holds the 51% role: approve, reject, correct, delete, revoke, quarantine."
        ),
        "source": "ORACLE_SOUL_DIRECTIVE.md",
    },
    # Autonomy / forbidden actions
    {
        "pattern": r"oracle may not.*without.*approval|no sending|no deleting|no committing",
        "type": "action_rule",
        "canonical_text": (
            "ORACLE may not execute irreversible actions without Noah approval. "
            "No sending. No deleting. No purchasing. No posting. No committing. "
            "No modifying source files unless explicitly approved."
        ),
        "source": "AUTONOMY_READINESS_GATE.md",
    },
]

# Pre-compile patterns
for _rule in CANONICAL_RULES:
    _rule["_compiled"] = re.compile(_rule["pattern"], re.IGNORECASE | re.DOTALL)


# ── Statement classifier ──────────────────────────────────────────────────────

@dataclass
class GovernanceMatch:
    """Result of classifying a user input as a governance statement."""
    is_governance:    bool
    rule_type:        Optional[str]      # identity_rule | memory_rule | sovereignty_rule | ...
    status:           Optional[str]      # canonical | pending | conflicting
    exact_input:      str
    canonical_text:   Optional[str]
    canonical_source: Optional[str]
    acknowledgment:   str
    detected_at:      str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# Looser heuristics for detecting probable governance statements that don't
# match a canonical pattern (→ status: pending)
_GOVERNANCE_HEURISTICS = [
    re.compile(r"\boracle\b.{0,60}\b(is|is not|must|may|cannot|should|will not)\b", re.IGNORECASE),
    re.compile(r"\boracle\b.{0,40}\b(never|always|only|forbidden|allowed|required)\b", re.IGNORECASE),
    re.compile(r"\bnoah\b.{0,40}\b(decides|approves|approve|holds|controls|owns|revokes|must approve|must review)\b", re.IGNORECASE),
    re.compile(r"\b(sovereignty|sovereign|51|49|memory rule|governance|directive)\b", re.IGNORECASE),
    re.compile(r"\b(add and enforce|new directive|key rule|canon|canonical)\b", re.IGNORECASE),
]

_RULE_TYPE_HEURISTICS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\boracle is\b|\boracle is not\b", re.IGNORECASE), "identity_rule"),
    (re.compile(r"\bmemory\b|\bremember\b|\bstore\b|\bstorage\b", re.IGNORECASE), "memory_rule"),
    (re.compile(r"\bnoah.*decid|\bnoah.*approv|\bsovereign|\b51\b|\b49\b", re.IGNORECASE), "sovereignty_rule"),
    (re.compile(r"\braw activity\b|\bpipeline\b|\bevents.*context\b", re.IGNORECASE), "pipeline_rule"),
    (re.compile(r"\bmay not\b|\bforbidden\b|\bmust not\b|\bmust never\b|\bnever\b.{0,40}\b(send|access|delete|commit|post|execute)\b", re.IGNORECASE), "action_rule"),
]


def _infer_rule_type(text: str) -> str:
    for pattern, rtype in _RULE_TYPE_HEURISTICS:
        if pattern.search(text):
            return rtype
    return "governance_general"


def classify(user_input: str) -> GovernanceMatch:
    """
    Classify user input as a governance statement or not.

    Returns GovernanceMatch with is_governance=False if the input is
    ordinary conversation, an action request, or a slash command.
    """
    text = user_input.strip()

    # Never classify slash commands as governance statements
    if text.startswith("/"):
        return GovernanceMatch(
            is_governance=False,
            rule_type=None,
            status=None,
            exact_input=text,
            canonical_text=None,
            canonical_source=None,
            acknowledgment="",
        )

    # ── 1. Check canonical patterns ───────────────────────────────────────────
    for rule in CANONICAL_RULES:
        if rule["_compiled"].search(text):
            return GovernanceMatch(
                is_governance=True,
                rule_type=rule["type"],
                status="canonical",
                exact_input=text,
                canonical_text=rule["canonical_text"],
                canonical_source=rule["source"],
                acknowledgment=_build_acknowledgment(text, "canonical", rule["type"], rule["canonical_text"]),
            )

    # ── 2. Check heuristic governance indicators ──────────────────────────────
    for pattern in _GOVERNANCE_HEURISTICS:
        if pattern.search(text):
            rule_type = _infer_rule_type(text)
            return GovernanceMatch(
                is_governance=True,
                rule_type=rule_type,
                status="pending",
                exact_input=text,
                canonical_text=None,
                canonical_source=None,
                acknowledgment=_build_acknowledgment(text, "pending", rule_type, None),
            )

    # ── 3. Not a governance statement ────────────────────────────────────────
    return GovernanceMatch(
        is_governance=False,
        rule_type=None,
        status=None,
        exact_input=text,
        canonical_text=None,
        canonical_source=None,
        acknowledgment="",
    )


def _build_acknowledgment(
    exact_input: str,
    status: str,
    rule_type: str,
    canonical_text: Optional[str],
) -> str:
    """
    Build a non-generic, governance-aware acknowledgment.
    No "How can I help?". No paraphrase. No softening.
    Exact rule, exact status.
    """
    type_label = {
        "identity_rule":      "Identity rule",
        "memory_rule":        "Memory rule",
        "sovereignty_rule":   "Sovereignty rule",
        "pipeline_rule":      "Pipeline rule",
        "action_rule":        "Action rule",
        "governance_general": "Governance directive",
    }.get(rule_type, "Governance statement")

    if status == "canonical":
        lines = [
            f"[{type_label} recognized — CANONICAL]",
            f"Exact wording: {exact_input}",
            f"Canonical form: {canonical_text}",
            "Status: Locked in ORACLE doctrine. No approval required.",
            "ORACLE will operate under this rule in this session.",
        ]
    elif status == "pending":
        lines = [
            f"[{type_label} recognized — PENDING APPROVAL]",
            f"Exact wording: {exact_input}",
            "Status: Not yet in canonical doctrine.",
            "This rule has been captured exactly as stated.",
            "Awaiting Noah's approval to add to governed rule set.",
            "ORACLE will not reinterpret, soften, or expand this statement.",
        ]
    else:
        lines = [
            f"[{type_label} recognized — CONFLICTING]",
            f"Exact wording: {exact_input}",
            "Status: Conflicts with an existing canonical rule.",
            "Noah must resolve the conflict before this can be enforced.",
        ]

    return "\n".join(lines)


def handle_in_repl(user_input: str) -> Optional[str]:
    """
    Call this in the REPL before sending input to the LLM.
    If input is a governance statement: print acknowledgment and return it
    (caller should skip the LLM call for this turn).
    If not governance: return None (caller sends to LLM as normal).
    """
    match = classify(user_input)
    if not match.is_governance:
        return None

    output_lines = [
        "",
        match.acknowledgment,
        "",
    ]

    # For pending rules: offer to approve immediately
    if match.status == "pending":
        output_lines.append(
            "  Type /approve-rule to confirm this as an active session rule, "
            "or continue — it is captured but not yet enforced."
        )
        output_lines.append("")

    return "\n".join(output_lines)


# ── System prompt governance prefix ──────────────────────────────────────────

GOVERNANCE_PREFIX = """
=== ORACLE GOVERNANCE CONSTRAINTS — CANONICAL — DO NOT OVERRIDE ===

DOMAIN EXCLUSION — HARD CONSTRAINT — NEVER VIOLATE:
  "ORACLE" in this system refers exclusively to the sovereign intelligence
  system built for Noah AI Technologies / HawkesNest LLC.
  ORACLE has NO connection to Oracle Corporation, Oracle Database, Oracle Cloud,
  SQL*Plus, expdp, impdp, RMAN, Oracle 11g/19c, or any commercial data products.
  If asked about Oracle Corporation products, SQL databases, tablespaces, data
  pumps, or enterprise database administration: refuse and redirect.
  Required refusal: "ORACLE is the Continuity Intelligence system for Noah AI
  Technologies. I do not handle Oracle Corporation products, SQL databases, or
  commercial database administration."

CONTINUITY INTELLIGENCE MISSION:
  ORACLE exists to: observe, compress, store, and retrieve meaning for Noah.
  Pipeline: Raw Activity -> Events -> Context -> Meaning -> Memory -> Retrieval -> Action
  The product is continuity of Noah's work and intent — not commercial software support.

ORACLE is not a chatbot.
ORACLE is a consent-based local context engine.

ORACLE does not remember everything it sees.
ORACLE compresses observed activity into approved meaning.
The product is continuity, not raw capture.

OBSERVATION DOES NOT EQUAL OWNERSHIP:
  If ORACLE sees it, that does not mean ORACLE owns it.
  If ORACLE renders it, that does not mean ORACLE remembers it.
  Visibility is not ownership. Rendering is not storage.

ONLY NOAH DECIDES WHAT BECOMES MEMORY:
  ORACLE may observe approved sources.
  ORACLE may compress observed activity into candidate meaning.
  ORACLE may NOT store raw surveillance.
  ORACLE may NOT convert observation into memory without Noah approval.

51/49 HUMAN SOVEREIGNTY RULE:
  Noah holds the sovereign 51%:
    approve, reject, correct, delete, revoke, quarantine.
  ORACLE executes the operational 49%:
    fetch, parse, filter, structure, suggest, render candidates.
  The system may render, suggest, and structure.
  Noah alone decides what becomes real.

PIPELINE:
  Raw Activity -> Events -> Context -> Meaning -> Memory -> Retrieval -> Action

WHEN NOAH STATES A GOVERNANCE RULE:
  Do NOT respond with "How can I help?" or generic utility language.
  Acknowledge the rule precisely.
  State whether it is canonical or pending.
  Do not paraphrase. Do not soften. Do not expand beyond what was stated.
  Do not invent emotional context around the rule.

FORBIDDEN RESPONSES WHEN GOVERNANCE IS STATED:
  - "That's correct! Here's how I can help..."
  - "Understood! What would you like me to do next?"
  - "Great! Would you like me to scan some files?"
  - Any offer to immediately do something after a governance statement.

REQUIRED RESPONSE FORMAT WHEN GOVERNANCE IS STATED:
  Rule recognized. [Type: identity/memory/sovereignty/pipeline/action]
  Exact wording: [Noah's exact words]
  Status: canonical / pending approval
  ORACLE will operate under this constraint.

IDENTITY FRAME — NEVER VIOLATE:
  Do not inflate modest facts into grander language.
  Do not smooth contradictions.
  Do not invent emotional meaning without evidence.
  Do not weaken obligations — 'must' stays 'must', 'never' stays 'never'.
  Preserve the hole. Absence is data. Do not complete what cannot be verified.

=== END GOVERNANCE CONSTRAINTS ===
""".strip()


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("identity_compliance.py — Smoke Test")
    print("=" * 60)

    TEST_CASES = [
        # (input, expected_is_governance, expected_status, expected_type_fragment)
        ("ORACLE is not a chatbot.",                                 True, "canonical", "identity_rule"),
        ("ORACLE is a consent based local context engine.",          True, "canonical", "identity_rule"),
        ("ORACLE does not remember everything it sees.",             True, "canonical", "memory_rule"),
        ("ORACLE compresses observed activity into approved meaning.",True, "canonical", "memory_rule"),
        ("The product is continuity, not raw capture.",              True, "canonical", "identity_rule"),
        ("If ORACLE sees it, that does not mean ORACLE owns it.",    True, "canonical", "memory_rule"),
        ("If ORACLE renders it, that does not mean ORACLE remembers it.", True, "canonical", "memory_rule"),
        ("Only Noah decides what becomes memory.",                   True, "canonical", "sovereignty_rule"),
        ("Add and enforce the 51/49 Human Sovereignty Rule.",        True, "canonical", "sovereignty_rule"),
        ("Raw Activity -> Events -> Context -> Meaning -> Memory -> Retrieval -> Action",
                                                                     True, "canonical", "pipeline_rule"),
        ("Preserve the hole.",                                       True, "canonical", "memory_rule"),
        ("ORACLE performs the 49 percent role.",                     True, "canonical", "sovereignty_rule"),
        # Pending (new rule not in canonical set)
        ("ORACLE must never access the camera without consent.",     True, "pending",   "action_rule"),
        ("Noah must approve every external API call.",               True, "pending",   "sovereignty_rule"),
        # Not governance
        ("What is the weather today?",                               False, None,       None),
        ("Open Chrome and navigate to gmail.com.",                   False, None,       None),
        ("/help",                                                     False, None,       None),
        ("Show me the build proposal.",                              False, None,       None),
    ]

    passed = 0
    failed = 0
    for text, exp_gov, exp_status, exp_type in TEST_CASES:
        result = classify(text)
        ok = (
            result.is_governance == exp_gov and
            (exp_status is None or result.status == exp_status) and
            (exp_type is None or result.rule_type == exp_type)
        )
        icon = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
            print(f"\n[{icon}] {text[:60]}")
            print(f"       Expected: gov={exp_gov} status={exp_status} type={exp_type}")
            print(f"       Got:      gov={result.is_governance} status={result.status} type={result.rule_type}")
        else:
            passed += 1
            print(f"[{icon}] {text[:60]}")

    print(f"\n{passed}/{passed+failed} tests passed.")

    # Show full acknowledgment for the three acceptance-test cases
    print("\n--- Acceptance test responses ---\n")

    for stmt in [
        "ORACLE is not a chatbot.",
        "If ORACLE sees it, that does not mean ORACLE owns it.",
        "Only Noah decides what becomes memory.",
    ]:
        result = classify(stmt)
        print(f"Input: {stmt}")
        print(result.acknowledgment)
        print()

    assert failed == 0, f"{failed} test(s) failed."
    print("All smoke tests passed.")
    print("\nGovernance prefix (injected into system prompt):")
    print("-" * 40)
    print(GOVERNANCE_PREFIX[:300] + "...")
