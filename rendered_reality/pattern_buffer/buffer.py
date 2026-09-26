"""
rendered_reality/pattern_buffer/buffer.py — PatternBuffer (approved continuity record)

Federation replicator metaphor, kept technical (NEW GROUND 13):
  Pattern Buffer = approved continuity record. It is NOT a style imitator and
  NOT a loose list. It stores only Noah-approved canon, with authorship and
  provenance metadata intact. The system replicates from lived pattern, not
  from a prompt.
"""
from __future__ import annotations

from ..receipts.receipt import Receipt, ApprovalStatus, CanonStatus


class PatternBuffer:
    def __init__(self) -> None:
        self._records: list[Receipt] = []

    def add(self, receipt: Receipt) -> Receipt:
        if receipt.canon_status != CanonStatus.NOAH_APPROVED_CANON:
            raise ValueError("PatternBuffer only stores Noah-approved canon")
        if receipt.approval_status != ApprovalStatus.APPROVED:
            raise ValueError("PatternBuffer requires approved receipts")
        self._records.append(receipt)
        return receipt

    def records(self) -> list[Receipt]:
        return list(self._records)

    def __len__(self) -> int:
        return len(self._records)
