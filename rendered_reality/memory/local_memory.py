"""Governed, in-process memory over Rendered Reality receipt records."""

from __future__ import annotations

from ..receipts.receipt import ApprovalStatus, Authorship, CanonStatus, Receipt
from .retrieval import Hit, keyword_search


class LocalMemory:
    def __init__(self, records: list[Receipt] | None = None) -> None:
        self._records: list[Receipt] = list(records or [])

    def add(self, record: Receipt) -> Receipt:
        self._records.append(record)
        return record

    def extend(self, records) -> None:
        self._records.extend(records)

    def all(self) -> list[Receipt]:
        return list(self._records)

    def __len__(self) -> int:
        return len(self._records)

    def remember_about(self, topic: str, limit: int = 5) -> list[Hit]:
        return keyword_search(self._records, topic, limit=limit)

    def holes(self) -> list[tuple[str, str]]:
        return [(record.receipt_id, hole) for record in self._records for hole in record.holes]

    def contradictions(self) -> list[tuple[str, str]]:
        return [
            (record.receipt_id, contradiction)
            for record in self._records
            for contradiction in record.contradictions
        ]

    def approved(self) -> list[Receipt]:
        return [record for record in self._records if record.approval_status == ApprovalStatus.APPROVED]

    def pending_approvals(self) -> list[Receipt]:
        return [record for record in self._records if record.approval_status == ApprovalStatus.PENDING]

    def canon(self) -> list[Receipt]:
        return [record for record in self._records if record.canon_status == CanonStatus.NOAH_APPROVED_CANON]

    def cite(self, record: Receipt) -> str:
        return (
            f"[{record.receipt_id}] source={record.source} "
            f"author={record.original_author}/{record.authorship_status.value} "
            f"approval={record.approval_status.value}"
        )

    def project_summary(self) -> str:
        total = len(self._records)
        if total == 0:
            return "I am not holding any records yet. There is nothing local to remember."
        by_author: dict[str, int] = {}
        for record in self._records:
            status = record.authorship_status.value
            by_author[status] = by_author.get(status, 0) + 1
        noah = by_author.get(Authorship.NOAH_AUTHORED.value, 0) + by_author.get(
            Authorship.ADOPTED_BY_NOAH.value, 0
        )
        ai = by_author.get(Authorship.AI_AUTHORED.value, 0)
        sources = sorted({record.source for record in self._records})[:6]
        return "\n".join(
            [
                f"I am holding {total} record(s) in local memory.",
                f"Authorship: {noah} yours, {ai} AI-authored, {total - noah - ai} other/unknown.",
                f"Approved canon: {len(self.canon())}. Pending approval: {len(self.pending_approvals())}.",
                f"Open holes: {len(self.holes())}. Contradictions: {len(self.contradictions())}.",
                f"Sources I remember: {', '.join(sources)}" + ("..." if len(sources) >= 6 else ""),
            ]
        )
