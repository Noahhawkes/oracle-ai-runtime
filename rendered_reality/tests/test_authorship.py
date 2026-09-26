from rendered_reality import Authorship, classify_authorship
from rendered_reality.samples import ai_authored_thread_pass, noah_authored_note


def test_classify_known_authors():
    assert classify_authorship("Noah.Physical") == Authorship.NOAH_AUTHORED
    assert classify_authorship("claude") == Authorship.AI_AUTHORED
    assert classify_authorship("grok") == Authorship.AI_AUTHORED
    assert classify_authorship("unknown") == Authorship.UNKNOWN


def test_adoption_overrides_ai():
    assert classify_authorship("claude", adopted_by_noah=True) == Authorship.ADOPTED_BY_NOAH


def test_pasted_ai_first_person_is_not_noah_authored():
    r = ai_authored_thread_pass()
    # first-person content + submitted by Noah, but written by Claude
    assert r.submitted_by == "Noah.Physical"
    assert r.authorship_status == Authorship.AI_AUTHORED
    assert r.is_noah_authored() is False


def test_explicit_adoption_flips_authorship():
    r = ai_authored_thread_pass()
    r.adopt_by_noah()
    assert r.authorship_status == Authorship.ADOPTED_BY_NOAH
    assert r.is_noah_authored() is True


def test_noah_note_is_noah_authored():
    assert noah_authored_note().is_noah_authored() is True


def test_drive_chatgpt_doc_is_noah_authorized_ai_assisted():
    from rendered_reality.samples import drive_chatgpt_return_from_dark_doc
    r = drive_chatgpt_return_from_dark_doc()
    # AI assistance is NOT an authorship demotion: Noah supplied intent + review + approval
    assert r.authorship_status == Authorship.NOAH_AUTHORIZED_AI_ASSISTED
    assert r.is_noah_authored() is True
    assert r.produced_with == "chatgpt" and r.token_origin == "ai"
    assert r.authorial_authority == "Noah.Physical"
    # authored under Noah's authority, but still a candidate until HE promotes it
    assert r.canon_status.value != "noah_approved_canon"
