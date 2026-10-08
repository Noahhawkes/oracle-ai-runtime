from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import recall_orchestrator as ro  # noqa: E402


def test_recall_test_prefix_still_triggers_backend_grounding():
    prompt = (
        "RECALL TEST 02: Search backend recall for Jupiter Station and Avalon. "
        "What records exist? Cite exact source paths/titles only."
    )

    context = ro.build_context(prompt)

    assert ro.should_answer_deterministically(prompt) is True
    assert context["active"] is True
    assert context["record_count"] > 0
    assert "[RECALL_ORCHESTRATOR" in context["block"]
    assert "Jupiter Station" in context["block"] or "Avalon" in context["block"]
    assert all("\\sandbox\\" not in str(item.get("path", "")).lower() for item in context["records"])


def test_ai_compliance_core_recall_has_citable_records():
    context = ro.build_context("What is AI Compliance Core as a product? Cite documents.")

    paths = [str(item.get("path") or "") for item in context["records"]]

    assert context["active"] is True
    assert any("AI_COMPLIANCE_CORE_DOCTRINE" in path for path in paths)


def test_recall_formatter_returns_records_without_model_synthesis():
    prompt = "RECALL TEST 05: What is AI Compliance Core as a product? Cite documents."
    context = ro.build_context(prompt)
    answer = ro.format_recall_answer(prompt, context)

    assert "RECALL CHECK" in answer
    assert "records_found:" in answer
    assert "Citable records:" in answer
    assert "UNKNOWN" in answer


def test_guard_flags_unverified_paths_without_touching_existing_paths():
    existing = str((ROOT / "docs" / "AI_COMPLIANCE_CORE_DOCTRINE.md").resolve())
    missing = r"G:\Noah.AI Technologies\All_Writings"
    guarded, findings = ro.guard_unverified_paths(
        f"Existing: `{existing}`. Missing: `{missing}`."
    )

    assert "CITATION_GUARD" in guarded
    assert any(item["path"] == missing for item in findings)
    assert all(item["path"] != existing for item in findings)


def test_exact_missing_path_request_does_not_expand_to_keyword_search():
    missing = r"G:\Noah.AI Technologies\All_Writings"
    prompt = f"RECALL TEST GUARD: What is in `{missing}`? Cite it only if verified."

    context = ro.build_context(prompt)
    answer = ro.format_recall_answer(prompt, context)

    assert ro.should_answer_deterministically(prompt) is True
    assert context["record_count"] == 0
    assert any(item["path"] == missing for item in context["unverified_paths"])
    assert "Answer: UNKNOWN" in answer


def test_durable_memory_is_a_recall_surface(monkeypatch):
    monkeypatch.setattr(
        ro,
        "_durable_memory_records",
        lambda query, limit=4: [{
            "surface": "durable_memory",
            "title": "event-123",
            "path": r"C:\Pictures\clip.mov",
            "source_system": "oracle_obs_media_thread_v1",
            "preview": "Media metadata observed clip.mov.",
        }],
    )
    monkeypatch.setattr(ro, "_runtime_doc_records", lambda query, limit=2: [])
    monkeypatch.setattr(ro, "_document_atlas_records", lambda query, limit=4: [])
    monkeypatch.setattr(ro, "_file_recall_records", lambda query, limit=3: [])
    monkeypatch.setattr(ro, "_quote_corpus_records", lambda query, limit=3: [])
    monkeypatch.setattr(ro, "_lockbox_records", lambda query, limit=3: [])
    monkeypatch.setattr(ro, "_thread_records", lambda query, limit=3: [])

    context = ro.build_context("Recall OBS media metadata for clip.mov")

    assert context["record_count"] > 0
    assert "durable_memory" in context["sources"]
    assert "clip.mov" in context["block"]


def test_functional_brain_terms_trigger_backend_grounding():
    prompt = "Search backend recall for ORACLE functional brain self-prompt executive loop."

    context = ro.build_context(prompt)

    assert ro.should_ground(prompt) is True
    assert context["active"] is True
    assert "ORACLE Brain Router" in context["block"] or "self-prompt" in context["block"]


def test_corpus_retrieval_surface_questions_prefer_scope_docs():
    prompt = (
        "What corpus retrieval surfaces are available and why are entire corpus "
        "answers not reliable yet?"
    )

    context = ro.build_context(prompt)

    assert ro.should_ground(prompt) is True
    assert ro.should_answer_deterministically(prompt) is True
    assert context["active"] is True
    assert any(
        name in context["block"]
        for name in (
            "AI_SOURCE_SURFACE_MAP",
            "DOCUMENT_ATLAS_STATUS",
            "ORACLE_DATA_SCOPE_ANSWER",
            "RENDERED_REALITY_MASTER_LITERATURE_SPINE",
        )
    )
    answer = ro.format_recall_answer(prompt, context)
    assert "Available corpus surfaces" in answer
    assert "indexed metadata is not the same as complete semantic ingestion" in answer
    assert "Corpus Ingestion Control Plane" in answer


def test_human_baseline_question_gets_natural_deterministic_answer():
    prompt = "Who am I?"

    context = ro.build_context(prompt)
    answer = ro.format_recall_answer(prompt, context)

    assert ro.should_ground(prompt) is True
    assert ro.should_answer_deterministically(prompt) is True
    assert context["active"] is True
    assert "human_baseline" in context["sources"]
    assert "Noah Alexander Hawkes Sr." in answer
    assert "The archive is evidence about you; it is not you." in answer
    assert "RECALL CHECK" not in answer


def test_human_baseline_age_question_gets_natural_deterministic_answer():
    prompt = "How old am I?"

    context = ro.build_context(prompt)
    answer = ro.format_recall_answer(prompt, context)

    assert ro.should_ground(prompt) is True
    assert ro.should_answer_deterministically(prompt) is True
    assert context["active"] is True
    assert "human_baseline" in context["sources"]
    assert answer == "You're 44."
