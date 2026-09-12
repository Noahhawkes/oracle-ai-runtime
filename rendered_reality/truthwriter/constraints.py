"""
rendered_reality/truthwriter/constraints.py — Truthwriter (constrained renderer)

Rendering must never precede approval (NEW GROUND 7). Three distinct operations:
  - preview_candidate(): always allowed, clearly labeled, never canon
  - render_draft():      allowed if a receipt exists, labeled DRAFT
  - promote_to_canon():  requires a receipt AND Noah.Physical approval

Core rule: Write from truth. Do not manufacture truth.
"""
from __future__ import annotations

from ..receipts.receipt import Receipt, ApprovalStatus, CanonStatus


class TruthwriterError(Exception):
    pass


class Truthwriter:
    def preview_candidate(self, receipt: Receipt) -> str:
        return (
            f"[CANDIDATE PREVIEW — not approved, not canon — {receipt.receipt_id}]\n"
            f"{receipt.content}"
        )

    def render_draft(self, receipt: Receipt | None) -> str:
        if receipt is None:
            raise TruthwriterError("render_draft requires a receipt")
        return (
            f"[DRAFT — receipt {receipt.receipt_id}, "
            f"approval={receipt.approval_status.value}, NOT canon]\n{receipt.content}"
        )

    def promote_to_canon(self, receipt: Receipt | None) -> str:
        # The gate: no receipt, no canon.
        if receipt is None:
            raise TruthwriterError("No canon without a receipt")
        ok, why = receipt.can_promote_to_canon()
        if not ok:
            raise TruthwriterError(f"No canon: {why}")
        receipt.canon_status = CanonStatus.NOAH_APPROVED_CANON
        return (
            f"[CANON — {receipt.receipt_id} — approved by Noah.Physical]\n"
            f"{receipt.content}"
        )
