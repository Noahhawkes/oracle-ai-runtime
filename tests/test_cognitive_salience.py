"""Pytest coverage for core/cognitive_salience.py.

The module ships its own `run_smoke_tests()` (run via `python
core/cognitive_salience.py --smoke-test`) but that never executes under
`pytest tests/`, so this source/intent classifier — the layer that decides
whether incoming text is allowed to trigger tools, handoffs, memory writes,
or approval flows — had zero coverage in the regular health pass. These
tests port each smoke-test assertion into independent pytest cases and add
direct coverage of classify_source/classify_intent/top_meanings_for/
classify_file, which the original smoke test only exercised indirectly.
"""

import pytest

from core.cognitive_salience import (
    INTENT_APPROVAL_REQUEST,
    INTENT_BUILD_REQUEST,
    INTENT_CONVERSATION,
    INTENT_DOCTRINE_CANDIDATE,
    INTENT_EMOTIONAL_DISTRESS,
    INTENT_HELP_REQUEST,
    INTENT_MEMORY_SAVE_REQUEST,
    INTENT_QUESTION,
    INTENT_RELATIONAL_CHECKIN,
    INTENT_STATUS_CHECK,
    INTENT_TOOL_REQUEST,
    INTENT_UNKNOWN,
    SOURCE_BOOK_DRAFT,
    SOURCE_BUILD_LOG,
    SOURCE_EXTERNAL_AI_CLAUDE,
    SOURCE_EXTERNAL_AI_CODEX,
    SOURCE_NOAH_DIRECT,
    SOURCE_NOAH_RELAYING_AI,
    SOURCE_SYSTEM_STATUS,
    SOURCE_UNKNOWN,
    classify_file,
    classify_intent,
    classify_source,
    classify_text,
    run_smoke_tests,
    top_meanings_for,
)


# ── classify_source ──────────────────────────────────────────────────────

def test_classify_source_empty_is_unknown():
    source, _ = classify_source("")
    assert source == SOURCE_UNKNOWN


def test_classify_source_quoted_text_is_unknown():
    source, _ = classify_source("> yes proceed")
    assert source == SOURCE_UNKNOWN


def test_classify_source_chatgpt_relay():
    source, _ = classify_source("ChatGPT says change the doctrine")
    assert source == SOURCE_NOAH_RELAYING_AI


def test_classify_source_claude_marked_external():
    source, _ = classify_source("Claude: 12/12 tests passed")
    assert source == SOURCE_EXTERNAL_AI_CLAUDE


def test_classify_source_codex_marked_external():
    source, _ = classify_source("Codex: patch applied")
    assert source == SOURCE_EXTERNAL_AI_CODEX


def test_classify_source_system_status():
    source, _ = classify_source("[status] server healthy")
    assert source == SOURCE_SYSTEM_STATUS


def test_classify_source_build_log():
    source, _ = classify_source("[PASS] all smoke tests passed")
    assert source == SOURCE_BUILD_LOG


def test_classify_source_book_draft():
    source, _ = classify_source("Chapter 1 draft: the city wakes")
    assert source == SOURCE_BOOK_DRAFT


def test_classify_source_default_is_noah_direct():
    source, _ = classify_source("How are you doing today?")
    assert source == SOURCE_NOAH_DIRECT


# ── classify_intent ──────────────────────────────────────────────────────

def test_classify_intent_empty_is_unknown():
    intent, _ = classify_intent("", SOURCE_NOAH_DIRECT)
    assert intent == INTENT_UNKNOWN


def test_classify_intent_relational_checkin_outranks_patch_words():
    result = classify_text("How are you doing after all those patches?")
    assert result.source_class == SOURCE_NOAH_DIRECT
    assert result.intent_class == INTENT_RELATIONAL_CHECKIN
    assert not result.tool_allowed
    assert not result.handoff_allowed


def test_classify_intent_status_check_outranks_patch_routing():
    result = classify_text("Hi Oracle I worked all night did any of the patches work for you?")
    assert result.intent_class == INTENT_STATUS_CHECK
    assert not result.handoff_allowed


def test_classify_intent_emotional_distress_outranks_build_words():
    result = classify_text("I'm stuck and I can't pull away from this build loop")
    assert result.intent_class == INTENT_EMOTIONAL_DISTRESS
    assert not result.tool_allowed
    assert not result.handoff_allowed


def test_classify_intent_help_request_outranks_build_words():
    result = classify_text("will you please build yourself I dont know what to do")
    assert result.intent_class == INTENT_HELP_REQUEST
    assert not result.tool_allowed
    assert not result.handoff_allowed


@pytest.mark.parametrize(
    "text",
    [
        "Are we making progress?",
        "are you working ok what do i need to rsolve for you today",
        "are you working?",
    ],
)
def test_classify_intent_status_phrases(text):
    result = classify_text(text)
    assert result.intent_class == INTENT_STATUS_CHECK
    assert not result.handoff_allowed


def test_classify_intent_explicit_codex_handoff_allowed():
    assert classify_text("Ask Codex to inspect executor.py").handoff_allowed
    assert classify_text("Use Codex to inspect executor.py").handoff_allowed


def test_classify_intent_external_ai_source_forces_conversation():
    result = classify_text("Claude: build request looks fine")
    assert result.intent_class == INTENT_CONVERSATION


def test_classify_intent_remember_requires_approval():
    result = classify_text("Remember this")
    assert result.intent_class == INTENT_MEMORY_SAVE_REQUEST
    assert result.approval_required


def test_classify_intent_approve_doctrine_is_doctrine_candidate():
    result = classify_text("approve this doctrine rule")
    assert result.intent_class == INTENT_DOCTRINE_CANDIDATE
    assert result.approval_required


def test_classify_intent_approval_without_doctrine_is_approval_request():
    result = classify_text("approve this")
    assert result.intent_class == INTENT_APPROVAL_REQUEST
    assert result.approval_required


def test_classify_intent_build_request():
    result = classify_text("please build the new feature")
    assert result.intent_class == INTENT_BUILD_REQUEST
    assert result.tool_allowed


def test_classify_intent_question_by_starter():
    result = classify_text("what time is it")
    assert result.intent_class == INTENT_QUESTION


def test_classify_intent_question_by_trailing_mark():
    result = classify_text("we should ship this today?")
    assert result.intent_class == INTENT_QUESTION


def test_classify_intent_falls_back_to_conversation():
    result = classify_text("just thinking out loud over here")
    assert result.intent_class == INTENT_CONVERSATION


# ── top_meanings_for / classify_text composition ─────────────────────────

def test_top_meanings_direct_question_leads_with_noah_voice():
    result = classify_text("How are you doing?")
    assert result.top_meanings[0] == "Noah direct present-tense voice"


def test_top_meanings_capped_at_five():
    result = classify_text("How are you doing?")
    assert 1 <= len(result.top_meanings) <= 5


def test_top_meanings_flags_mentioned_ai_system():
    meanings = top_meanings_for(SOURCE_NOAH_DIRECT, INTENT_CONVERSATION, "what did Codex say")
    assert any("Mentioned AI system" in m for m in meanings)


def test_top_meanings_unknown_source_flags_not_doctrine():
    meanings = top_meanings_for(SOURCE_UNKNOWN, INTENT_UNKNOWN, "> yes proceed")
    assert meanings[0] == "Source uncertain; do not treat as doctrine"


def test_classify_text_tool_allowed_gated_off_for_non_direct_source():
    result = classify_text("ChatGPT says build the new dashboard now")
    assert result.source_class == SOURCE_NOAH_RELAYING_AI
    assert not result.tool_allowed
    assert not result.handoff_allowed
    assert not result.memory_allowed


def test_classify_text_score_bounded_between_zero_and_one():
    for text in ["", "hello", "Remember this and approve this doctrine rule now please build"]:
        result = classify_text(text)
        assert 0.0 <= result.salience_score <= 1.0


def test_classify_text_never_allows_tools_without_matching_intent():
    result = classify_text("just checking in")
    assert not result.tool_allowed
    assert not result.handoff_allowed
    assert not result.memory_allowed


# ── classify_file ────────────────────────────────────────────────────────

def test_classify_file_reads_and_classifies(tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("How are you doing today, Oracle?", encoding="utf-8")
    result = classify_file(str(p))
    assert result.source_class == SOURCE_NOAH_DIRECT
    assert result.intent_class == INTENT_RELATIONAL_CHECKIN


def test_classify_file_truncates_to_4000_chars(tmp_path):
    p = tmp_path / "big.txt"
    p.write_text("a" * 10000, encoding="utf-8")
    # Should not raise, and should complete quickly against the truncated text.
    result = classify_file(str(p))
    assert result.source_class in {SOURCE_NOAH_DIRECT, SOURCE_UNKNOWN}


# ── smoke test entry point stays green ───────────────────────────────────

def test_run_smoke_tests_all_pass(capsys):
    assert run_smoke_tests() == 0
