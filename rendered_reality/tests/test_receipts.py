from rendered_reality import Receipt, ApprovalStatus, CanonStatus


def test_receipt_gets_id_and_content_hash():
    r = Receipt(source="s", submitting_system="x", submitted_by="Noah.Physical",
                content="hello")
    assert r.receipt_id.startswith("rcpt_")
    assert r.content_hash and r.content_hash.startswith("sha256:")


def test_pending_receipt_cannot_promote():
    r = Receipt(source="s", submitting_system="x", submitted_by="Noah.Physical")
    ok, why = r.can_promote_to_canon()
    assert ok is False and "approved" in why


def test_approved_receipt_can_promote():
    r = Receipt(source="s", submitting_system="x", submitted_by="Noah.Physical",
                approval_status=ApprovalStatus.APPROVED)
    ok, _ = r.can_promote_to_canon()
    assert ok is True


def test_to_json_serializes_enums():
    r = Receipt(source="s", submitting_system="x", submitted_by="Noah.Physical")
    js = r.to_json()
    assert "candidate_idea" in js and "pending" in js
