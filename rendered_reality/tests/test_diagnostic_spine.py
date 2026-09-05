"""The 25-question diagnostic spine (NEW GROUND 14) — highest-priority audits."""
from pathlib import Path

import pytest

from rendered_reality import (
    Witness, Truthwriter, TruthwriterError, Receipt, ReceiptError,
    ApprovalStatus, Authorship, REQUIRED_HOLES, assert_machine_observed,
)
from rendered_reality.samples import ai_authored_thread_pass

HOLES_MD = Path(__file__).resolve().parents[1] / "HOLES.md"


def test_unobserved_event_cannot_be_machine_observed():
    w = Witness()
    r = w.create_return_from_dark_record(
        event_label="offline walk", reporter="Noah.Physical", testimony="...")
    with pytest.raises(ReceiptError):
        assert_machine_observed(r)


def test_first_person_pasted_ai_not_noah_authored():
    r = ai_authored_thread_pass()
    assert r.authorship_status == Authorship.AI_AUTHORED
    assert r.is_noah_authored() is False


def test_holes_display_required():
    text = HOLES_MD.read_text(encoding="utf-8").lower()
    missing = [h for h in REQUIRED_HOLES if h.lower() not in text]
    assert not missing, f"HOLES.md missing required holes: {missing}"


def test_no_canon_without_receipt():
    tw = Truthwriter()
    with pytest.raises(TruthwriterError):
        tw.promote_to_canon(None)


def test_no_canon_without_noah_approval():
    tw = Truthwriter()
    r = Receipt(source="s", submitting_system="x", submitted_by="Noah.Physical",
                content="draft", approval_status=ApprovalStatus.PENDING)
    with pytest.raises(TruthwriterError):
        tw.promote_to_canon(r)


def test_approved_receipt_promotes_to_canon():
    tw = Truthwriter()
    r = Receipt(source="s", submitting_system="x", submitted_by="Noah.Physical",
                content="approved truth", approval_status=ApprovalStatus.APPROVED)
    out = tw.promote_to_canon(r)
    assert "CANON" in out
    assert r.canon_status.value == "noah_approved_canon"


def test_render_before_approval_is_draft_not_canon():
    tw = Truthwriter()
    r = Receipt(source="s", submitting_system="x", submitted_by="Noah.Physical",
                content="x")
    assert "DRAFT" in tw.render_draft(r)
    assert "CANDIDATE" in tw.preview_candidate(r)
