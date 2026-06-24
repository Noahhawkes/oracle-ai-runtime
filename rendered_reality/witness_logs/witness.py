"""
rendered_reality/witness_logs/witness.py — Witness (primary operational role)

Witness, not Mirror (NEW GROUND 1). A witness says what was observed, says what
was NOT observed, preserves provenance, labels testimony, preserves holes,
refuses invention, generates receipts, and distinguishes source / author /
submitter / approval status.
"""
from __future__ import annotations

from ..receipts.receipt import (
    Receipt, Authorship, CanonStatus, classify_authorship,
    OBS_MACHINE, OBS_RETURN_FROM_DARK, OBS_POST_EVENT_TESTIMONY,
)

DEFAULT_SYSTEM = "oracle_witness_runtime"


class Witness:
    def __init__(self, submitting_system: str = DEFAULT_SYSTEM) -> None:
        self.system = submitting_system

    def observe_event(self, *, source: str, content: str,
                      submitted_by: str | None = None) -> Receipt:
        """A genuinely machine-observed event. This is the ONLY path that may
        set machine_observed=True."""
        return Receipt(
            source=source,
            submitting_system=self.system,
            submitted_by=submitted_by or self.system,
            original_author=self.system,
            authorship_status=Authorship.AI_AUTHORED,
            content=content,
            machine_observed=True,
            observation_status=OBS_MACHINE,
            testimony_source=self.system,
            canon_status=CanonStatus.RUNTIME_INGESTED_RECORD,
        )

    def record_testimony(self, *, source: str, content: str, reporter: str,
                         original_author: str | None = None) -> Receipt:
        """Human-reported, not machine-observed."""
        author = original_author or reporter
        return Receipt(
            source=source,
            submitting_system=self.system,
            submitted_by=reporter,
            original_author=author,
            authorship_status=classify_authorship(author),
            content=content,
            reporter=reporter,
            testimony_source=reporter,
            machine_observed=False,
            observation_status=OBS_POST_EVENT_TESTIMONY,
            canon_status=CanonStatus.RUNTIME_INGESTED_RECORD,
        )

    def mark_not_observed(self, receipt: Receipt, note: str) -> Receipt:
        if note not in receipt.holes:
            receipt.holes.append(note)
        return receipt

    def create_return_from_dark_record(self, *, event_label: str, reporter: str,
                                       testimony: str, source: str = "post_event_testimony",
                                       original_author: str | None = None) -> Receipt:
        """Meaningful events that happened offline / outside machine observation
        (NEW GROUND 2). Capture later, label honestly, do not invent."""
        author = original_author or reporter
        return Receipt(
            source=source,
            submitting_system=self.system,
            submitted_by=reporter,
            original_author=author,
            authorship_status=classify_authorship(author),
            content=testimony,
            event_label=event_label,
            reporter=reporter,
            testimony_source=reporter,
            machine_observed=False,
            observation_status=OBS_RETURN_FROM_DARK,
            holes=["No machine observation", "No transcript", "Post-event testimony only"],
            canon_status=CanonStatus.RUNTIME_INGESTED_RECORD,
        )

    def generate_witness_statement(self, receipt: Receipt) -> str:
        lines = [
            f"WITNESS STATEMENT — {receipt.receipt_id}",
            f"event: {receipt.event_label or receipt.source}",
            f"observation_status: {receipt.observation_status}",
            f"machine_observed: {receipt.machine_observed}",
            f"reporter: {receipt.reporter or 'n/a'}",
            f"testimony_source: {receipt.testimony_source or 'n/a'}",
            f"original_author: {receipt.original_author} "
            f"({receipt.authorship_status.value})",
            f"submitted_by: {receipt.submitted_by}",
            f"approval_status: {receipt.approval_status.value}",
            f"canon_status: {receipt.canon_status.value}",
        ]
        if receipt.holes:
            lines.append("NOT OBSERVED / HOLES:")
            lines += [f"  - {h}" for h in receipt.holes]
        if receipt.contradictions:
            lines.append("CONTRADICTIONS:")
            lines += [f"  - {c}" for c in receipt.contradictions]
        return "\n".join(lines)
