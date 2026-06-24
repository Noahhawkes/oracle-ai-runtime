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
