"""
rendered_reality/provenance_graph/query.py — provenance queries (v0.1)

Answer "where did this come from / who wrote it" from local records. The whole
point of the project: separate what Noah wrote from what AI wrote, and keep the
transport path. Queries are read-only over the held records.
"""
from __future__ import annotations

from ..receipts.receipt import Authorship


class ProvenanceQuery:
    def __init__(self, records) -> None:
        self._records = list(records)

    def by_author(self, authorship: Authorship) -> list:
        return [r for r in self._records if r.authorship_status == authorship]

    def by_source(self, needle: str) -> list:
        n = needle.lower()
        return [r for r in self._records if n in (r.source or "").lower()]

    def authorship_breakdown(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in self._records:
            out[r.authorship_status.value] = out.get(r.authorship_status.value, 0) + 1
        return out

    def trace(self, receipt_id: str) -> str | None:
        for r in self._records:
            if r.receipt_id == receipt_id:
                return (f"{r.receipt_id}: {r.original_author} "
                        f"({r.authorship_status.value}) -> submitted_by {r.submitted_by} "
                        f"via {r.transport_path} -> source {r.source}")
        return None
