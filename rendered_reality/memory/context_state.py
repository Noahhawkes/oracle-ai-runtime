"""Current local Rendered Reality state derived without tool calls."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ContextState:
    total: int = 0
    by_canon: dict[str, int] = field(default_factory=dict)
    by_authorship: dict[str, int] = field(default_factory=dict)
    holes: int = 0
    contradictions: int = 0
    approved: int = 0
    pending_approvals: int = 0
    canon: int = 0

    @classmethod
    def from_memory(cls, memory) -> "ContextState":
        records = memory.all()
        by_canon: dict[str, int] = {}
        by_authorship: dict[str, int] = {}
        for record in records:
            canon = record.canon_status.value
            authorship = record.authorship_status.value
            by_canon[canon] = by_canon.get(canon, 0) + 1
            by_authorship[authorship] = by_authorship.get(authorship, 0) + 1
        return cls(
            total=len(records),
            by_canon=by_canon,
            by_authorship=by_authorship,
            holes=len(memory.holes()),
            contradictions=len(memory.contradictions()),
            approved=len(memory.approved()),
            pending_approvals=len(memory.pending_approvals()),
            canon=len(memory.canon()),
        )

    def render(self) -> str:
        return "\n".join(
            [
                "CURRENT LOCAL STATE",
                f"  records: {self.total}",
                f"  canon (Noah-approved): {self.canon}",
                f"  approved: {self.approved}   pending approval: {self.pending_approvals}",
                f"  open holes: {self.holes}   contradictions: {self.contradictions}",
                f"  by canon status: {self.by_canon}",
                f"  by authorship: {self.by_authorship}",
            ]
        )
