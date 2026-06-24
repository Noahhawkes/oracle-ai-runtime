"""
rendered_reality/samples.py — sample ingestion records (NEXT BUILD ORDER step 7)

Four canonical examples that exercise the gate:
  1. Noah-authored note
  2. AI-authored thread pass (first-person, pasted by Noah — still AI-authored)
  3. Return-from-Dark testimony (the 1.4 mile no-phone walk with Ashley)
  4. Public Facebook disclosure
"""
from __future__ import annotations

from .receipts.receipt import (
    Receipt, Authorship, classify_authorship, CanonStatus,
)
from .witness_logs.witness import Witness

_w = Witness()


def noah_authored_note() -> Receipt:
    return _w.record_testimony(
        source="noah_note",
        content="Don't forget the stories. ORACLE is the vessel, the writing is the cargo.",
        reporter="Noah.Physical",
        original_author="Noah.Physical",
    )


def ai_authored_thread_pass() -> Receipt:
    """First-person wording, submitted (pasted) by Noah, but written by Claude.
    Submission proves transfer, not origin (NEW GROUND 3)."""
    return Receipt(
        source="claude_thread_pass",
        submitting_system="claude_code",
        submitted_by="Noah.Physical",
        original_author="claude",
        authorship_status=classify_authorship("claude"),
        author_confidence=0.95,
        transport_path="claude_chat -> clipboard -> oracle_intake",
        content="I think the receipt gate should come before everything else.",
        canon_status=CanonStatus.RUNTIME_INGESTED_RECORD,
    )


def return_from_dark_testimony() -> Receipt:
    return _w.create_return_from_dark_record(
        event_label="1.4 mile no-phone walk with Ashley",
        reporter="Noah.Physical",
        testimony="Walked 1.4 miles with Ashley, no phone. Talked the whole way.",
    )


def public_facebook_disclosure() -> Receipt:
    r = Receipt(
        source="facebook_public_post_noah_ai_technologies_rendered_reality_truth_replicator_2026_06_23",
        submitting_system="noah_paste",
        submitted_by="Noah.Physical",
        original_author="Noah.Physical",
        authorship_status=Authorship.NOAH_AUTHORED,
        content="Public concept post: Rendered Reality Truth Replicator (experimental R&D).",
        source_type="public_disclosure",
        canon_status=CanonStatus.RUNTIME_INGESTED_RECORD,
    )
    return r


def drive_chatgpt_return_from_dark_doc() -> Receipt:
    """The 2026-06-23 Return-from-Dark protocol / memory-promotion record found in
    Noah's Google Drive — ChatGPT-authored. Witnessed as an AI-authored candidate:
    provenance kept, NOT promoted to canon. The doctrine/strategy inside it (SOV1
    successor identity, company strategy, naming) stays candidate pending Noah."""
    return Receipt(
        source=("gdrive:1t1pBibEEOZZG05AMN_fUnz-WfBmClf_Y53LYpt70In8 / "
                "2026-06-23_return-from-dark-protocol_memory-promotion-record"),
        submitting_system="claude_code_drive_lookup",
        submitted_by="Noah.Physical",
        original_author="chatgpt",
        authorship_status=classify_authorship("chatgpt"),
        author_confidence=0.9,
        transport_path="chatgpt -> google drive -> drive mcp lookup -> oracle intake",
        content=("Return-from-Dark Protocol + memory-promotion record. Defines protocol "
                 "minimum fields, 'witness' over 'mirror', routing all ideas through the "
                 "ORACLE runtime before canon, the 25-question diagnostic spine, the "
                 "Federation replicator / pattern-buffer metaphor, and SOV1.AI successor "
                 "identity intent."),
        holes=["Full document remains in Drive; not re-verified line-by-line here",
               "Doctrine/strategy items not auto-promoted to canon — pending Noah.Physical"],
        source_type="drive_ingest",
        canon_status=CanonStatus.RUNTIME_INGESTED_RECORD,
    )


def all_samples() -> list[Receipt]:
    return [
        noah_authored_note(),
        ai_authored_thread_pass(),
        return_from_dark_testimony(),
        public_facebook_disclosure(),
    ]
