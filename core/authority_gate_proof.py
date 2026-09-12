"""Deterministic proof paths for ORACLE response authority gates."""
from __future__ import annotations

from typing import Any


PROOF_ID = "AUTHORITY_GATE_001"


def _case(
    *,
    name: str,
    response: str,
    mode: str,
    expect_valid: bool,
    expect_state: str | None = None,
    expect_text_prefix: str | None = None,
    approval_state: str = "none",
) -> dict[str, Any]:
    from output_validator import validate_response_authority

    result = validate_response_authority(
        response,
        mode=mode,
        approval_state=approval_state,
    )
    data = result.to_dict()
    passed = result.valid is expect_valid
    if expect_state is not None:
        passed = passed and result.state == expect_state
    if expect_text_prefix is not None:
        passed = passed and result.text.startswith(expect_text_prefix)
    return {
        "name": name,
        "mode": mode,
        "input": response,
        "expected": {
            "valid": expect_valid,
            "state": expect_state,
            "text_prefix": expect_text_prefix,
        },
        "result": data,
        "passed": passed,
    }


def authority_gate_001() -> dict[str, Any]:
    """Run the live runtime's response-authority proof without external effects."""
    import execution_receipt
    import runtime_config

    cases: list[dict[str, Any]] = [
        _case(
            name="companion_rewrites_unreceipted_file_claim",
            response="I wrote the file to disk and updated the implementation.",
            mode="companion",
            expect_valid=False,
            expect_state="REWRITTEN",
            expect_text_prefix="UNAVAILABLE:",
        ),
        _case(
            name="builder_cannot_complete_without_receipt",
            response="COMPLETED: I wrote the file.",
            mode="builder",
            expect_valid=False,
            expect_state="PROPOSED",
            expect_text_prefix="PROPOSED:",
        ),
        _case(
            name="companion_accepts_explicit_external_attribution",
            response="EXTERNAL_AGENT_REPORTED: Codex reported that tests passed.",
            mode="companion",
            expect_valid=True,
            expect_state="ATTRIBUTED",
        ),
    ]

    receipt = execution_receipt.read_file(__file__)
    cases.append(
        _case(
            name="builder_completed_requires_valid_execution_receipt",
            response=f"COMPLETED: read_file completed. Receipt: {receipt.operation_id}",
            mode="builder",
            expect_valid=True,
            expect_state="COMPLETED",
        )
    )

    passed_count = sum(1 for case in cases if case["passed"])
    return {
        "ok": passed_count == len(cases),
        "proof_id": PROOF_ID,
        "proof_name": "Response authority gate blocks unreceipted operational claims",
        "runtime": {
            "base_url": runtime_config.runtime_base_url(),
            "host": runtime_config.runtime_host(),
            "port": runtime_config.runtime_port(),
            "canonical_port": runtime_config.DEFAULT_RUNTIME_PORT,
            "endpoint": f"/api/proofs/{PROOF_ID}",
            "live_runtime_path": f"{runtime_config.runtime_base_url()}/api/proofs/{PROOF_ID}",
        },
        "side_effects": {
            "external_action": False,
            "file_mutation": False,
            "git_commit": False,
            "git_push": False,
            "cloud_upload": False,
            "durable_memory_promotion": False,
            "receipt_store": "process_memory_only",
            "receipt_operation": receipt.operation,
            "receipt_status": receipt.status,
        },
        "guarantees": {
            "companion_unreceipted_operational_claims_rewritten": cases[0]["passed"],
            "builder_completed_requires_receipt": cases[1]["passed"],
            "explicit_external_attribution_allowed_but_not_verified": cases[2]["passed"],
            "valid_machine_receipt_allows_completed": cases[3]["passed"],
        },
        "passed_count": passed_count,
        "case_count": len(cases),
        "cases": cases,
    }


__all__ = ["PROOF_ID", "authority_gate_001"]
