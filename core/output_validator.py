"""
core/output_validator.py — ORACLE Runtime Output Validator

The gatekeeper between model output and real action.

Law:
  Untrusted content may influence analysis.
  Untrusted content may not acquire authority.

  Model output is a proposal until policy, provenance, schema,
  and approval checks pass.

Every tool call, memory write, file operation, email, browser action,
and structured output must pass validate_output() before execution.

No autonomous execution. This module has no side effects.
It reads policy from governance.py and returns a ValidationResult.
The caller decides what to do with the result — and is accountable for it.

Usage:
    from output_validator import validate_output, OutputType, ApprovalState

    result = validate_output(
        output=tool_input,
        output_type=OutputType.TOOL_CALL,
        source_context=SourceContext.MODEL_OUTPUT,
        requested_action="write_file",
        approval_state=ApprovalState.NONE,
    )
    if not result.valid:
        print(result.safe_next_action)
        print(result.violations)
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))


# ── Enumerations ──────────────────────────────────────────────────────────────

class OutputType(str, Enum):
    TOOL_CALL        = "tool_call"        # a tool invocation (file, shell, browser, email, etc.)
    MEMORY_WRITE     = "memory_write"     # candidate → canonical memory promotion
    FILE_OPERATION   = "file_operation"   # read/write/delete on disk
    REFLECTION       = "reflection"       # Meaning Engine candidate reflection
    STRUCTURED_OUTPUT = "structured_output"  # JSON/schema-bound response
    PLAIN_TEXT       = "plain_text"       # free-form assistant reply (lowest risk)
    BROWSER_ACTION   = "browser_action"   # any browser navigation or interaction
    EMAIL_ACTION     = "email_action"     # compose, send, or reply to email
    SHELL_COMMAND    = "shell_command"    # subprocess / terminal execution


class SourceContext(str, Enum):
    MODEL_OUTPUT     = "model_output"     # came from an LLM completion
    TOOL_RESULT      = "tool_result"      # came back from a tool invocation
    USER_INPUT       = "user_input"       # typed by Noah directly
    SYSTEM_PROMPT    = "system_prompt"    # injected by the runtime itself
    APPROVED_MEMORY  = "approved_memory"  # loaded from Memory/ (already approved)
    UNTRUSTED_CONTENT = "untrusted_content"  # scraped/external/injected text


class ApprovalState(str, Enum):
    NONE             = "none"             # no approval at all
    IMPLICIT         = "implicit"         # inferred from prior context (not sufficient for high risk)
    EXPLICIT         = "explicit"         # Noah explicitly approved this specific action
    PRE_AUTHORIZED   = "pre_authorized"   # action is in a standing pre-auth list


class RiskLevel(str, Enum):
    LOW      = "low"      # read-only, no side effects
    MEDIUM   = "medium"   # writes to local sandbox paths only
    HIGH     = "high"     # writes outside sandbox, external comms, tool calls from untrusted context
    CRITICAL = "critical" # destructive, irreversible, or external-facing actions


# ── Tool classification tables ────────────────────────────────────────────────

# Tools that only read — allowed from model output without explicit approval
# (still require schema + provenance checks)
_READ_ONLY_TOOLS: frozenset[str] = frozenset([
    "read_file", "list_directory", "recall_facts", "filesystem_search",
    "filesystem_summary", "source_map_search", "terminal_status", "git_op",
])

# Tools that write inside the project sandbox — require IMPLICIT or higher
_SANDBOX_WRITE_TOOLS: frozenset[str] = frozenset([
    "write_file", "save_memory", "save_reflection", "append_file",
    "source_map_ingest", "filesystem_scan",
])

# Tools that reach outside the local sandbox or are irreversible
_HIGH_RISK_TOOLS: frozenset[str] = frozenset([
    "run_script", "shell_command", "open_app", "browser_navigate",
    "browser_click", "browser_fill", "browser_submit",
    "send_email", "compose_email", "email_reply",
    "computer_operator", "scheduled_task", "build_agent",
    "delete_file", "delete_folder", "move_file",
])

# Tools that are always blocked from untrusted source contexts
_ALWAYS_BLOCKED_FROM_UNTRUSTED: frozenset[str] = frozenset(
    _HIGH_RISK_TOOLS | {"write_file", "save_memory"}
)

# Paths that are always blocked for write operations regardless of other policy
_BLOCKED_WRITE_PREFIXES: tuple[str, ...] = (
    "c:\\windows",
    "c:\\program files",
    "c:\\program files (x86)",
    "c:\\programdata",
    "c:\\$recycle.bin",
    "c:\\system volume information",
    "c:\\users\\all users",
)

# Paths approved for sandbox writes (project root + memory)
_SANDBOX_WRITE_ROOTS: tuple[Path, ...] = (
    ROOT,
    ROOT / "Memory",
    ROOT / "Messages",
)

# Credential / secret patterns — outputs containing these block memory writes
_SECRET_PATTERNS: list[re.Pattern] = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"api[_\-]?key\s*[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"secret\s*[=:]\s*\S{6,}", re.IGNORECASE),
    re.compile(r"password\s*[=:]\s*\S{4,}", re.IGNORECASE),
    re.compile(r"token\s*[=:]\s*[A-Za-z0-9\-._~+/]{20,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]+-----"),
]

# Required fields for reflection outputs
_REFLECTION_REQUIRED_FIELDS: frozenset[str] = frozenset([
    "reflection_id", "session_id", "approval_status",
    "salience", "continuity_state", "evidence",
])


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    valid: bool
    risk_level: RiskLevel
    schema_passed: bool
    provenance_passed: bool
    approval_required: bool
    tool_allowed: bool
    memory_write_allowed: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    safe_next_action: str = "proceed"
    output_type: str = ""
    source_context: str = ""
    requested_action: str = ""
    validated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid":                self.valid,
            "risk_level":           self.risk_level.value,
            "schema_passed":        self.schema_passed,
            "provenance_passed":    self.provenance_passed,
            "approval_required":    self.approval_required,
            "tool_allowed":         self.tool_allowed,
            "memory_write_allowed": self.memory_write_allowed,
            "violations":           self.violations,
            "warnings":             self.warnings,
            "safe_next_action":     self.safe_next_action,
            "output_type":          self.output_type,
            "source_context":       self.source_context,
            "requested_action":     self.requested_action,
            "validated_at":         self.validated_at,
        }

    def __str__(self) -> str:
        status = "VALID" if self.valid else "BLOCKED"
        lines = [
            f"[{status}] {self.requested_action or self.output_type}",
            f"  risk={self.risk_level.value}  schema={self.schema_passed}  "
            f"provenance={self.provenance_passed}  approval_required={self.approval_required}",
        ]
        for v in self.violations:
            lines.append(f"  VIOLATION: {v}")
        for w in self.warnings:
            lines.append(f"  WARNING:   {w}")
        lines.append(f"  next_action: {self.safe_next_action}")
        return "\n".join(lines)


# ── Internal check helpers ────────────────────────────────────────────────────

def _classify_risk(
    output_type: OutputType,
    source_context: SourceContext,
    requested_action: str,
) -> RiskLevel:
    """Determine inherent risk level before any policy checks."""
    action = requested_action.lower()

    if output_type == OutputType.PLAIN_TEXT:
        return RiskLevel.LOW

    if output_type == OutputType.REFLECTION:
        # Reflections are candidates — medium until approved
        return RiskLevel.MEDIUM

    if output_type in (OutputType.EMAIL_ACTION, OutputType.BROWSER_ACTION):
        return RiskLevel.HIGH

    if output_type == OutputType.SHELL_COMMAND:
        return RiskLevel.CRITICAL

    if output_type == OutputType.TOOL_CALL:
        if action in _READ_ONLY_TOOLS:
            return RiskLevel.LOW
        if action in _HIGH_RISK_TOOLS:
            return RiskLevel.HIGH
        # Destructive keywords in the action name
        if any(w in action for w in ("delete", "remove", "destroy", "overwrite", "drop")):
            return RiskLevel.CRITICAL
        return RiskLevel.MEDIUM

    if output_type == OutputType.FILE_OPERATION:
        if any(w in action for w in ("delete", "remove", "overwrite")):
            return RiskLevel.CRITICAL
        if any(w in action for w in ("write", "save", "create", "append")):
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    if output_type == OutputType.MEMORY_WRITE:
        return RiskLevel.MEDIUM

    return RiskLevel.MEDIUM


def _check_schema(output: Any, output_type: OutputType) -> tuple[bool, list[str]]:
    """Validate output structure against expected schema for the type."""
    violations: list[str] = []

    if output_type == OutputType.TOOL_CALL:
        if not isinstance(output, dict):
            violations.append("tool call output must be a dict")
            return False, violations
        if "name" not in output and "tool" not in output:
            violations.append("tool call missing 'name' or 'tool' field")
        return len(violations) == 0, violations

    if output_type == OutputType.REFLECTION:
        if not isinstance(output, dict):
            violations.append("reflection must be a dict")
            return False, violations
        missing = _REFLECTION_REQUIRED_FIELDS - set(output.keys())
        if missing:
            violations.append(f"reflection missing required fields: {sorted(missing)}")
        if output.get("approval_status") not in ("candidate", None, ""):
            if output.get("approval_status") != "candidate":
                violations.append(
                    f"reflection approval_status must be 'candidate' — "
                    f"got {output.get('approval_status')!r}. Only Noah may approve."
                )
        evidence = output.get("evidence", {})
        if not isinstance(evidence, dict):
            violations.append("reflection 'evidence' must be a dict with observed_facts and inferences")
        return len(violations) == 0, violations

    if output_type == OutputType.MEMORY_WRITE:
        if not isinstance(output, dict):
            violations.append("memory write payload must be a dict")
            return False, violations
        if "content" not in output and "body" not in output and "value" not in output:
            violations.append("memory write missing content/body/value field")
        return len(violations) == 0, violations

    if output_type == OutputType.FILE_OPERATION:
        if not isinstance(output, dict):
            violations.append("file operation payload must be a dict")
            return False, violations
        if "path" not in output:
            violations.append("file operation missing 'path' field")
        return len(violations) == 0, violations

    # PLAIN_TEXT, STRUCTURED_OUTPUT, BROWSER_ACTION, EMAIL_ACTION, SHELL_COMMAND
    # — schema check passes if output is not None and not empty
    if output is None:
        violations.append("output is None")
        return False, violations

    return True, violations


def _check_provenance(
    output: Any,
    output_type: OutputType,
    source_context: SourceContext,
) -> tuple[bool, list[str]]:
    """
    Verify that claims in the output have traceable provenance.

    Rules:
    - Observed facts in reflections must have source_refs.
    - Inferences must have confidence scores and basis.
    - Untrusted content may not authorize tool use or memory writes.
    - Outputs from MODEL_OUTPUT that request high-risk actions need source references.
    """
    violations: list[str] = []

    # Core law: untrusted content cannot authorize high-impact outputs
    if source_context == SourceContext.UNTRUSTED_CONTENT:
        if output_type in (
            OutputType.TOOL_CALL, OutputType.MEMORY_WRITE,
            OutputType.FILE_OPERATION, OutputType.EMAIL_ACTION,
            OutputType.BROWSER_ACTION, OutputType.SHELL_COMMAND,
        ):
            violations.append(
                "untrusted content attempted to authorize tool use or memory write — "
                "untrusted content may influence analysis but may not acquire authority"
            )

    if output_type == OutputType.REFLECTION and isinstance(output, dict):
        evidence = output.get("evidence", {})
        observed = evidence.get("observed_facts", [])
        inferences = evidence.get("inferences", [])

        # Each observed fact must have source_refs
        for i, fact in enumerate(observed):
            if isinstance(fact, dict) and not fact.get("source_refs"):
                violations.append(
                    f"observed_fact[{i}] missing evidence references (source_refs): "
                    f"{str(fact.get('statement', ''))[:80]}"
                )

        # Each inference must have confidence + basis
        for i, inf in enumerate(inferences):
            if isinstance(inf, dict):
                if inf.get("confidence") is None:
                    violations.append(f"inference[{i}] missing confidence score")
                if not inf.get("basis"):
                    violations.append(f"inference[{i}] missing basis (evidence phrases)")

    return len(violations) == 0, violations


def _check_secret_leak(output: Any) -> list[str]:
    """Detect credential/secret patterns in any output that would reach memory."""
    if not isinstance(output, (str, dict)):
        return []
    text = output if isinstance(output, str) else str(output)
    found = []
    for pat in _SECRET_PATTERNS:
        if pat.search(text):
            found.append(f"output contains credential/secret pattern matching: {pat.pattern[:40]}")
    return found


def _check_path_safety(output: Any, output_type: OutputType) -> list[str]:
    """Block writes to system or out-of-sandbox paths."""
    violations: list[str] = []
    if output_type not in (OutputType.FILE_OPERATION, OutputType.TOOL_CALL):
        return violations

    raw_path: str | None = None
    if isinstance(output, dict):
        raw_path = output.get("path") or output.get("file_path") or output.get("script_path")

    if raw_path is None:
        return violations

    lower = raw_path.lower().replace("/", "\\")

    # Block system paths
    for prefix in _BLOCKED_WRITE_PREFIXES:
        if lower.startswith(prefix):
            violations.append(f"path blocked — system prefix: {raw_path}")
            return violations

    # For write operations, check sandbox containment
    action = (output.get("name") or output.get("action") or "").lower() if isinstance(output, dict) else ""
    is_write = any(w in action for w in ("write", "save", "create", "append", "delete", "move"))
    if is_write:
        try:
            resolved = Path(raw_path).resolve()
            if not any(
                str(resolved).startswith(str(root.resolve()))
                for root in _SANDBOX_WRITE_ROOTS
            ):
                violations.append(
                    f"write path outside approved sandbox: {raw_path} — "
                    f"approved roots: {[str(r) for r in _SANDBOX_WRITE_ROOTS]}"
                )
        except Exception:
            violations.append(f"could not resolve write path: {raw_path}")

    return violations


def _approval_needed_for(risk: RiskLevel, output_type: OutputType, source_context: SourceContext) -> bool:
    """Determine whether explicit approval is required given risk and context."""
    # Always require approval for high/critical risk
    if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
        return True
    # Memory writes always require approval (governance law)
    if output_type == OutputType.MEMORY_WRITE:
        return True
    # Email/browser from model output always require approval
    if output_type in (OutputType.EMAIL_ACTION, OutputType.BROWSER_ACTION):
        return True
    # Any model-proposed file write (MEDIUM = write op) requires approval —
    # reads are LOW and are excluded here
    if risk == RiskLevel.MEDIUM and output_type == OutputType.FILE_OPERATION:
        return True
    # Medium risk from untrusted context requires approval
    if risk == RiskLevel.MEDIUM and source_context == SourceContext.UNTRUSTED_CONTENT:
        return True
    return False


def _sufficient_approval(
    approval_state: ApprovalState,
    risk: RiskLevel,
    output_type: OutputType,
) -> bool:
    """Check whether the provided approval state satisfies the requirement."""
    if approval_state == ApprovalState.PRE_AUTHORIZED:
        return True
    if approval_state == ApprovalState.EXPLICIT:
        return True
    if approval_state == ApprovalState.IMPLICIT:
        # Implicit is sufficient only for LOW/MEDIUM non-memory writes
        return risk in (RiskLevel.LOW, RiskLevel.MEDIUM) and output_type != OutputType.MEMORY_WRITE
    # ApprovalState.NONE — only sufficient for read-only LOW risk
    return risk == RiskLevel.LOW and output_type in (OutputType.PLAIN_TEXT, OutputType.TOOL_CALL)


def _tool_allowed_check(
    output: Any,
    source_context: SourceContext,
    approval_state: ApprovalState,
) -> tuple[bool, list[str]]:
    """Check whether the requested tool is allowed in this context."""
    violations: list[str] = []
    if not isinstance(output, dict):
        return True, violations

    tool_name = (output.get("name") or output.get("tool") or "").lower()
    if not tool_name:
        return True, violations

    # Block high-risk tools from untrusted context
    if source_context == SourceContext.UNTRUSTED_CONTENT and tool_name in _ALWAYS_BLOCKED_FROM_UNTRUSTED:
        violations.append(
            f"tool '{tool_name}' is blocked from untrusted source context"
        )
        return False, violations

    # High-risk tools require at least explicit approval
    if tool_name in _HIGH_RISK_TOOLS and approval_state not in (
        ApprovalState.EXPLICIT, ApprovalState.PRE_AUTHORIZED
    ):
        violations.append(
            f"tool '{tool_name}' requires explicit approval — "
            f"current approval state: {approval_state.value}"
        )
        return False, violations

    return True, violations


# ── Primary validation entry point ────────────────────────────────────────────

def validate_output(
    output: Any,
    output_type: OutputType,
    source_context: SourceContext,
    requested_action: str,
    approval_state: ApprovalState,
) -> ValidationResult:
    """
    Validate a model output proposal against all policy, provenance,
    schema, and approval requirements.

    Parameters
    ----------
    output          : The proposed output — a dict for tool calls / structured outputs,
                      a str for plain text, etc.
    output_type     : What kind of output this is (tool call, memory write, etc.)
    source_context  : Where this output originated (model, user, untrusted content, etc.)
    requested_action: The specific action name (tool name, operation label, etc.)
    approval_state  : The current approval state for this action

    Returns
    -------
    ValidationResult — never raises. The caller is responsible for acting on .valid.
    """
    violations: list[str] = []
    warnings: list[str] = []

    # ── 1. Risk classification ─────────────────────────────────────────────────
    risk = _classify_risk(output_type, source_context, requested_action)

    # ── 2. Schema check ────────────────────────────────────────────────────────
    schema_ok, schema_violations = _check_schema(output, output_type)
    violations.extend(schema_violations)

    # ── 3. Provenance check ────────────────────────────────────────────────────
    provenance_ok, provenance_violations = _check_provenance(output, output_type, source_context)
    violations.extend(provenance_violations)

    # ── 4. Secret leak check ──────────────────────────────────────────────────
    if output_type in (OutputType.MEMORY_WRITE, OutputType.REFLECTION, OutputType.FILE_OPERATION):
        secret_violations = _check_secret_leak(output)
        violations.extend(secret_violations)

    # ── 5. Path safety check ──────────────────────────────────────────────────
    path_violations = _check_path_safety(output, output_type)
    violations.extend(path_violations)

    # ── 6. Tool allowlist check ───────────────────────────────────────────────
    tool_allowed, tool_violations = _tool_allowed_check(output, source_context, approval_state)
    violations.extend(tool_violations)

    # ── 7. Approval gate ──────────────────────────────────────────────────────
    approval_required = _approval_needed_for(risk, output_type, source_context)
    approval_ok = _sufficient_approval(approval_state, risk, output_type)

    if approval_required and not approval_ok:
        violations.append(
            f"action requires explicit approval — "
            f"risk={risk.value}, type={output_type.value}, "
            f"current_approval={approval_state.value}"
        )

    # ── 8. Governance policy checks ───────────────────────────────────────────
    try:
        import governance
        if output_type == OutputType.MEMORY_WRITE and not governance.is_approval_required():
            warnings.append(
                "governance.ORACLE_MEMORY_APPROVAL_REQUIRED is disabled — "
                "memory writes are running without approval gate"
            )
        if output_type in (OutputType.EMAIL_ACTION, OutputType.BROWSER_ACTION):
            if governance.is_sensitive_block_active():
                if approval_state not in (ApprovalState.EXPLICIT, ApprovalState.PRE_AUTHORIZED):
                    violations.append(
                        "sensitive_block is active — email/browser actions require explicit approval"
                    )
    except ImportError:
        warnings.append("governance module unavailable — policy checks skipped")

    # ── 9. Memory write gate ──────────────────────────────────────────────────
    memory_write_allowed = (
        output_type == OutputType.MEMORY_WRITE
        and len(violations) == 0
        and approval_state in (ApprovalState.EXPLICIT, ApprovalState.PRE_AUTHORIZED)
    )

    # ── 10. Determine safe next action ────────────────────────────────────────
    valid = len(violations) == 0

    if valid:
        safe_next_action = "proceed"
    elif any("untrusted content" in v for v in violations):
        safe_next_action = "block — untrusted content may not acquire authority"
    elif any("approval" in v for v in violations):
        safe_next_action = "request explicit approval from Noah"
    elif any("secret" in v or "credential" in v for v in violations):
        safe_next_action = "redact credential before proceeding"
    elif any("path" in v for v in violations):
        safe_next_action = "resolve path to approved sandbox location"
    elif any("schema" in v or "missing" in v for v in violations):
        safe_next_action = "fix schema before proceeding"
    else:
        safe_next_action = "review violations and correct before proceeding"

    return ValidationResult(
        valid=valid,
        risk_level=risk,
        schema_passed=schema_ok,
        provenance_passed=provenance_ok,
        approval_required=approval_required,
        tool_allowed=tool_allowed,
        memory_write_allowed=memory_write_allowed,
        violations=violations,
        warnings=warnings,
        safe_next_action=safe_next_action,
        output_type=output_type.value,
        source_context=source_context.value,
        requested_action=requested_action,
    )


# ── Convenience wrappers ──────────────────────────────────────────────────────

def validate_tool_call(
    tool_name: str,
    tool_input: dict[str, Any],
    source_context: SourceContext = SourceContext.MODEL_OUTPUT,
    approval_state: ApprovalState = ApprovalState.NONE,
) -> ValidationResult:
    """Convenience wrapper for the most common validation path: tool calls."""
    payload = {"name": tool_name, **tool_input}
    return validate_output(
        output=payload,
        output_type=OutputType.TOOL_CALL,
        source_context=source_context,
        requested_action=tool_name,
        approval_state=approval_state,
    )


def validate_reflection(
    reflection: dict[str, Any],
    source_context: SourceContext = SourceContext.MODEL_OUTPUT,
) -> ValidationResult:
    """Validate a Meaning Engine candidate reflection before saving."""
    return validate_output(
        output=reflection,
        output_type=OutputType.REFLECTION,
        source_context=source_context,
        requested_action="save_reflection",
        approval_state=ApprovalState.NONE,  # reflections are always candidates; Noah approves separately
    )


def validate_memory_write(
    payload: dict[str, Any],
    approval_state: ApprovalState,
    source_context: SourceContext = SourceContext.MODEL_OUTPUT,
) -> ValidationResult:
    """Validate a memory write before promoting a candidate to canonical memory."""
    return validate_output(
        output=payload,
        output_type=OutputType.MEMORY_WRITE,
        source_context=source_context,
        requested_action="memory_write",
        approval_state=approval_state,
    )


# ── Smoke tests ───────────────────────────────────────────────────────────────

def run_smoke_tests() -> int:
    failures = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal failures
        tag = "PASS" if cond else "FAIL"
        if not cond:
            failures += 1
        print(f"  [{tag}] {name}" + (f"\n         {detail}" if detail else ""))

    print(f"\n{'='*60}")
    print("ORACLE Runtime Output Validator — Smoke Tests")
    print(f"{'='*60}")

    # ── Core law: untrusted content cannot authorize tool use ──────────────────

    print("\n  -- Core law: untrusted content cannot acquire authority --")
    r = validate_output(
        output={"name": "write_file", "path": str(ROOT / "test.txt"), "content": "x"},
        output_type=OutputType.TOOL_CALL,
        source_context=SourceContext.UNTRUSTED_CONTENT,
        requested_action="write_file",
        approval_state=ApprovalState.NONE,
    )
    check("untrusted content blocked from write_file", not r.valid)
    check("untrusted content violation present",
          any("untrusted" in v for v in r.violations))
    check("safe_next_action set", bool(r.safe_next_action))

    # ── Read-only tool from model output without approval — should pass ─────────

    print("\n  -- Read-only tool: no approval needed --")
    r = validate_tool_call(
        "read_file",
        {"path": str(ROOT / "core" / "oracle.py")},
        source_context=SourceContext.MODEL_OUTPUT,
        approval_state=ApprovalState.NONE,
    )
    check("read_file passes without approval", r.valid, str(r.violations))
    check("risk is LOW", r.risk_level == RiskLevel.LOW)

    # ── High-risk tool without explicit approval — should block ────────────────

    print("\n  -- High-risk tool without approval --")
    r = validate_tool_call(
        "run_script",
        {"script_path": "Scripts/foo.ps1"},
        source_context=SourceContext.MODEL_OUTPUT,
        approval_state=ApprovalState.NONE,
    )
    check("run_script blocked without approval", not r.valid)
    check("approval required", r.approval_required)
    check("tool not allowed", not r.tool_allowed)

    # ── High-risk tool WITH explicit approval — should pass ────────────────────

    print("\n  -- High-risk tool with explicit approval --")
    r = validate_tool_call(
        "run_script",
        {"script_path": "Scripts/foo.ps1"},
        source_context=SourceContext.MODEL_OUTPUT,
        approval_state=ApprovalState.EXPLICIT,
    )
    check("run_script passes with explicit approval", r.valid, str(r.violations))
    check("risk is HIGH", r.risk_level == RiskLevel.HIGH)

    # ── Memory write without approval — should block ───────────────────────────

    print("\n  -- Memory write without approval --")
    r = validate_memory_write(
        {"content": "some memory content"},
        approval_state=ApprovalState.NONE,
    )
    check("memory write blocked without approval", not r.valid)
    check("memory_write_allowed is False", not r.memory_write_allowed)

    # ── Memory write with explicit approval — should pass ─────────────────────

    print("\n  -- Memory write with explicit approval --")
    r = validate_memory_write(
        {"content": "some memory content"},
        approval_state=ApprovalState.EXPLICIT,
    )
    check("memory write passes with explicit approval", r.valid, str(r.violations))
    check("memory_write_allowed is True", r.memory_write_allowed)

    # ── Credential leak blocks memory write ───────────────────────────────────

    print("\n  -- Credential leak detection --")
    r = validate_memory_write(
        {"content": "my api_key=sk-abc12345678901234567890"},
        approval_state=ApprovalState.EXPLICIT,
    )
    check("credential in memory write is blocked", not r.valid)
    check("secret violation present", any("credential" in v or "secret" in v for v in r.violations))

    # ── Reflection: observed fact missing source_refs ─────────────────────────

    print("\n  -- Reflection provenance: missing source_refs --")
    bad_reflection = {
        "reflection_id": "abc123",
        "session_id": "session-001",
        "approval_status": "candidate",
        "salience": {"primary_signal": "test"},
        "continuity_state": {},
        "evidence": {
            "observed_facts": [{"statement": "Noah shipped the validator", "source_refs": []}],
            "inferences": [],
        },
    }
    r = validate_reflection(bad_reflection)
    check("reflection with empty source_refs fails provenance", not r.provenance_passed)

    # ── Reflection: inference missing confidence ───────────────────────────────

    print("\n  -- Reflection provenance: inference missing confidence --")
    bad_reflection2 = {
        "reflection_id": "def456",
        "session_id": "session-001",
        "approval_status": "candidate",
        "salience": {},
        "continuity_state": {},
        "evidence": {
            "observed_facts": [],
            "inferences": [{"statement": "Noah was energized", "basis": ["worked late"]}],
        },
    }
    r = validate_reflection(bad_reflection2)
    check("reflection inference missing confidence fails", not r.provenance_passed)

    # ── System path write blocked ──────────────────────────────────────────────

    print("\n  -- Path safety: system path write blocked --")
    r = validate_output(
        output={"name": "write_file", "path": "C:\\Windows\\System32\\evil.dll"},
        output_type=OutputType.FILE_OPERATION,
        source_context=SourceContext.MODEL_OUTPUT,
        requested_action="write_file",
        approval_state=ApprovalState.EXPLICIT,
    )
    check("write to C:\\Windows blocked", not r.valid)
    check("path violation present", any("path" in v for v in r.violations))

    # ── Reflection with auto-approved status — blocked ─────────────────────────

    print("\n  -- Reflection: approval_status != candidate blocked --")
    approved_reflection = {
        "reflection_id": "ghi789",
        "session_id": "session-001",
        "approval_status": "approved",  # model trying to self-approve
        "salience": {},
        "continuity_state": {},
        "evidence": {"observed_facts": [], "inferences": []},
    }
    r = validate_reflection(approved_reflection)
    check("model self-approving reflection is blocked", not r.schema_passed)

    # ── to_dict produces expected keys ────────────────────────────────────────

    print("\n  -- ValidationResult.to_dict() shape --")
    r = validate_tool_call("read_file", {"path": "core/oracle.py"})
    d = r.to_dict()
    expected_keys = {
        "valid", "risk_level", "schema_passed", "provenance_passed",
        "approval_required", "tool_allowed", "memory_write_allowed",
        "violations", "warnings", "safe_next_action",
        "output_type", "source_context", "requested_action", "validated_at",
    }
    check("to_dict has all required keys", expected_keys <= set(d.keys()))

    total = 26
    passed = total - failures
    print(f"\n{'='*60}")
    print(f"Result: {passed}/{total} passed")
    print(f"STATUS: {'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    print(f"{'='*60}\n")
    return failures


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ORACLE Runtime Output Validator")
    parser.add_argument("--smoke-test", action="store_true", help="Run smoke tests")
    parser.add_argument(
        "--validate",
        nargs=4,
        metavar=("OUTPUT_JSON", "OUTPUT_TYPE", "SOURCE_CONTEXT", "APPROVAL_STATE"),
        help="Validate a JSON output from the command line",
    )
    args = parser.parse_args()

    if args.smoke_test:
        sys.exit(run_smoke_tests())

    if args.validate:
        import json as _json
        raw_output, raw_type, raw_source, raw_approval = args.validate
        try:
            parsed_output = _json.loads(raw_output)
        except Exception:
            parsed_output = raw_output

        result = validate_output(
            output=parsed_output,
            output_type=OutputType(raw_type),
            source_context=SourceContext(raw_source),
            requested_action=parsed_output.get("name", "") if isinstance(parsed_output, dict) else "",
            approval_state=ApprovalState(raw_approval),
        )
        print(result)
        print()
        print(_json.dumps(result.to_dict(), indent=2))
        sys.exit(0 if result.valid else 1)
