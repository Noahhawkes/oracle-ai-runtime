import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

import execution_policy  # noqa: E402


def test_bare_diagnostic_word_does_not_force_bypass():
    # Acceptance test from BUG REPORT 2026-07-11 (talk-lane UNKNOWN echo).
    prompt = (
        "CUSTODY_BLOCKER_DIAGNOSTIC\n"
        "Explain why ORACLE is returning missing token-origin vs "
        "authorial-authority boundary."
    )
    policy = execution_policy.parse(prompt)
    assert policy.is_diagnostic is False
    assert policy.routing_policy == "normal"
    assert policy.model_policy == "any"


def test_explicit_deterministic_instructions_still_bypass():
    for prompt in (
        "deterministic only. Current mode:",
        "do not use the local model. report state",
        "diagnostic only\nCurrent mode:",
        "no llm. version:",
    ):
        policy = execution_policy.parse(prompt)
        assert policy.is_diagnostic is True, prompt


def test_zero_coverage_schema_refuses_unknown_echo():
    prompt = (
        "deterministic only\n"
        "Task:\n"
        "blocker_type:\n"
        "smallest_safe_fix:\n"
        "Rules:\n"
    )
    policy = execution_policy.parse(prompt)
    text = execution_policy.build_deterministic_response(policy)
    # Must not echo each prompt heading with UNKNOWN.
    assert "blocker_type:\nUNKNOWN" not in text
    assert "Rules:\nUNKNOWN" not in text
    # Must say which lookup failed and what fields exist.
    assert "failed_lookup" in text
    assert "available_fields" in text


def test_partial_coverage_fills_known_and_lists_unmapped_once():
    prompt = (
        "deterministic only\n"
        "Current mode:\n"
        "blocker_type:\n"
    )
    policy = execution_policy.parse(prompt)
    text = execution_policy.build_deterministic_response(policy)
    assert "Current mode:" in text
    # Unmapped heading reported once, not echoed as its own UNKNOWN block.
    assert "blocker_type:\nUNKNOWN" not in text
    assert "unmapped_headings" in text
    assert "blocker_type" in text
