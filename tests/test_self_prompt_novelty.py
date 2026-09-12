from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import sandbox_files as sf  # noqa: E402


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(sf, "SANDBOX_ROOT", tmp_path / "sandbox")
    monkeypatch.setattr(sf, "SANDBOX_TRASH_ROOT", tmp_path / "sandbox.trash")


def _write(response: str) -> dict:
    return sf.sandbox_self_prompt_write(
        "Choose one sandbox-only next task, then stop.",
        response,
        seed_prompt="novelty test",
        caller="ORACLE.self_prompt",
        source_route="ORACLE.self_prompt",
        model_called=True,
        model_name="test-model",
    )


def test_exact_duplicate_response_is_suppressed(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    response = "reflection: I notice the canon valve is still closed.\nselected_task: summarize the pending seeds."

    first = _write(response)
    second = _write(response)

    assert first["content_written"] is True
    assert second["content_written"] is False
    assert second["deduped"] is True
    assert second["novelty_status"] == "duplicate_suppressed"
    assert second["receipt_path"] is None


def test_near_duplicate_in_different_words_is_suppressed(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    first = _write(
        "reflection: I notice Noah values continuity and presence in our recent interactions "
        "and wants deeper engagement with the manuscript.\n"
        "selected_task: summarize recent interactions focusing on continuity and presence."
    )
    # same substance, shuffled wording
    second = _write(
        "reflection: I notice that in our recent interactions Noah values presence and continuity, "
        "wanting deeper manuscript engagement.\n"
        "selected_task: focusing on presence and continuity, summarize the recent interactions."
    )

    assert first["content_written"] is True
    assert second["content_written"] is False
    assert second["novelty_status"] == "near_duplicate_suppressed"
    assert second["similarity_to_recent"] >= 0.80


def test_genuinely_new_thought_is_appended_to_single_journal(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    first = _write(
        "reflection: I notice the canon valve is still closed with fourteen pending seeds.\n"
        "selected_task: draft a one-line summary of each pending seed."
    )
    second = _write(
        "reflection: the creation witness feed shows Noah drafting the Jupiter Station quest arcs tonight.\n"
        "selected_task: connect the quest arc drafts to the STO alignment timeline."
    )

    assert first["content_written"] is True
    assert second["content_written"] is True
    assert second["novelty_status"] == "new_response_appended"
    assert Path(first["final_path"]) == Path(second["final_path"])  # one running journal
    content = Path(second["final_path"]).read_text(encoding="utf-8")
    assert content.count(".AI:ORACLE_SELF_PROMPT_CYCLE") == 2


def test_low_quality_self_prompt_is_suppressed_before_journal_append(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    result = _write("reflection: vague vibe, no task, no evidence, no boundary")

    assert result["content_written"] is False
    assert result["deduped"] is False
    assert result["novelty_status"] == "quality_gate_suppressed"
    assert result["quality_decision"]["should_write"] is False
    assert "missing_selected_task" in result["quality_decision"]["blockers"]
    assert not (tmp_path / "sandbox" / "workbench" / "oracle_self_prompt_journal.ai").exists()


def test_self_declared_discard_is_suppressed_before_journal_append(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    result = _write(
        "purpose_lane: memory_gap\n"
        "reflection: I notice this repeats the same file-access task again.\n"
        "what_noah_needs: Noah needs the loop to stop manufacturing duplicate journal entries.\n"
        "how_to_wire_myself: choose a different SourceMap focus before answering.\n"
        "selected_task: review install_autostart.bat for one continuity gap\n"
        "why_it_helps_noah: it would clarify one uncertainty if it were new.\n"
        "evidence_it_worked: candidate reflection only\n"
        "quality_gate: discard_no_write\n"
        "stop_after_this: true"
    )

    assert result["content_written"] is False
    assert result["novelty_status"] == "quality_gate_suppressed"
    assert "explicit_quality_gate_discard" in result["quality_decision"]["blockers"]
    assert not (tmp_path / "sandbox" / "workbench" / "oracle_self_prompt_journal.ai").exists()


def test_quality_metadata_is_written_with_good_self_prompt(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    result = _write(
        "purpose_lane: runtime_improvement\n"
        "reflection: I notice the self-prompt loop needs a quality gate before append.\n"
        "what_noah_needs: Noah needs less clutter and more useful sandbox continuity.\n"
        "how_to_wire_myself: score novelty, actionability, salience, and integrity before writing.\n"
        "selected_task: test the sandbox quality gate against one meaningful runtime-improvement reflection\n"
        "why_it_helps_noah: it prevents repetitive storage while preserving useful next steps.\n"
        "evidence_it_worked: candidate reflection only\n"
        "stop_after_this: true"
    )

    assert result["content_written"] is True
    assert result["quality_score"] >= 0.42
    assert result["purpose_lane"] == "runtime_improvement"
    content = Path(result["final_path"]).read_text(encoding="utf-8")
    assert "quality_decision:" in content
    assert "purpose_lane=runtime_improvement" in content


def test_essence_similarity_bounds():
    a = sf._response_essence("the canon valve is closed with fourteen pending seeds")
    b = sf._response_essence("fourteen pending seeds sit behind the closed canon valve")
    c = sf._response_essence("the jupiter station quest log renders live pulses")
    assert sf._essence_similarity(a, b) > 0.8
    assert sf._essence_similarity(a, c) < 0.3
    assert sf._essence_similarity(frozenset(), a) == 0.0
