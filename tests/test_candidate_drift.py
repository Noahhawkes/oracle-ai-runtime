"""Pytest coverage for core/candidate_drift.py.

Shared anti-amplification machinery used by both reflection_candidates.py and
prompt_learning_loop.py. It never writes, approves, or promotes anything — it
only measures text similarity and strips credential-shaped material before a
candidate is persisted. It had zero dedicated test file even though it is the
single place both candidate producers depend on for drift protection, so a
regression here (e.g. a secret pattern silently stopping matching) would go
undetected by the rest of the suite.
"""

from core.candidate_drift import (
    DRIFT_LOOKBACK,
    DRIFT_THRESHOLD,
    REDACTION,
    clip,
    contains_secret,
    drift_score,
    is_amplification,
    normalize,
    redact,
)


def test_normalize_lowercases_and_collapses_whitespace():
    assert normalize("  Hello   WORLD\n\tagain ") == "hello world again"


def test_normalize_handles_none_and_non_string():
    assert normalize(None) == ""
    assert normalize(123) == "123"


def test_clip_leaves_short_text_untouched():
    assert clip("short text", 50) == "short text"


def test_clip_truncates_and_adds_ellipsis():
    body = "a" * 100
    clipped = clip(body, 20)
    assert len(clipped) == 20
    assert clipped.endswith("…")


def test_clip_collapses_whitespace_before_measuring_length():
    assert clip("a   b   c", 5) == "a b c"


def test_contains_secret_detects_common_key_shapes():
    assert contains_secret("sk-abcdefghijklmnopqrstuvwx")
    assert contains_secret("AKIAABCDEFGHIJKLMNOP")
    assert contains_secret("api_key: abcdef1234567890")
    assert contains_secret("Bearer abcdefghijklmnopqrstuvwx")
    assert contains_secret("-----BEGIN RSA PRIVATE KEY-----")
    assert contains_secret("seed phrase: apple banana cherry")


def test_contains_secret_false_for_ordinary_text():
    assert not contains_secret("just an ordinary reflection about the day")
    assert not contains_secret("")
    assert not contains_secret(None)


def test_redact_removes_matched_material():
    text = "here is my key api_key: abcdef1234567890 keep this"
    redacted = redact(text)
    assert "abcdef1234567890" not in redacted
    assert REDACTION in redacted
    assert "keep this" in redacted


def test_redact_leaves_clean_text_unchanged():
    text = "nothing secret about this sentence"
    assert redact(text) == text


def test_redact_handles_none():
    assert redact(None) == ""


def test_drift_score_empty_text_returns_zero():
    score, matched = drift_score("", ["something prior"])
    assert score == 0.0
    assert matched == ""


def test_drift_score_no_prior_texts_returns_zero():
    score, matched = drift_score("new idea entirely", [])
    assert score == 0.0
    assert matched == ""


def test_drift_score_identical_text_is_full_match():
    score, matched = drift_score("the exact same sentence", ["the exact same sentence"])
    assert score == 1.0
    assert matched == "the exact same sentence"


def test_drift_score_picks_closest_of_several_priors():
    priors = [
        "a completely unrelated thought about weather",
        "reflecting on the build today, same as before",
        "reflecting on the build today same as before exactly",
    ]
    score, matched = drift_score("reflecting on the build today same as before exactly", priors)
    assert matched == priors[2]
    assert score == 1.0


def test_drift_score_ignores_blank_prior_entries():
    score, matched = drift_score("some new text", ["", "   "])
    assert score == 0.0
    assert matched == ""


def test_is_amplification_threshold_boundary():
    assert is_amplification(DRIFT_THRESHOLD)
    assert is_amplification(1.0)
    assert not is_amplification(DRIFT_THRESHOLD - 0.01)
    assert not is_amplification(0.0)


def test_drift_lookback_and_threshold_are_sane_constants():
    assert 0.0 < DRIFT_THRESHOLD <= 1.0
    assert DRIFT_LOOKBACK > 0
