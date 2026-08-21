from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "core"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from core.thread_engine import ThreadEngine, ContinuityThread  # noqa: E402


def test_thread_state_persistence(tmp_path: Path):
    engine = ThreadEngine(threads_dir=tmp_path)

    event_packet = {
        "event_id": "evt_test123",
        "user_intent": "Build step 3 thread state",
        "claims_extracted": ["Thread engine isolates state from log sweeps"],
        "uncertainties": ["How should aliases merge across sessions?"],
        "evidence_used": [{"path": "core/thread_engine.py"}],
    }

    thread = engine.update_from_event("th_20260820_alpha", event_packet)
    assert thread.thread_id == "th_20260820_alpha"
    assert len(thread.timeline) == 1
    assert "Thread engine isolates state from log sweeps" in thread.facts

    summary = engine.get_summary("th_20260820_alpha")
    assert summary["event_count"] == 1
    assert summary["open_questions"] == ["How should aliases merge across sessions?"]
    assert summary["linked_documents"] == ["core/thread_engine.py"]


def test_real_cep_v1_shape_projects_into_thread_state(tmp_path: Path):
    engine = ThreadEngine(threads_dir=tmp_path)
    event_packet = {
        "event_id": "cep_20260820T120000Z_abc123",
        "user_intent": {
            "summary": "recall_orchestrator",
            "route_type": "recall_orchestrator",
            "user_text_preview": "How old am I?",
        },
        "claims_extracted": [{
            "claim_type": "source_resolution",
            "status": "RESOLVED",
            "field": "date_of_birth",
            "selected_source_class": "governed_verified_identity_record",
        }],
        "uncertainties": ["visible UI state not captured"],
        "corrections": {"detected_correction_request": False, "status": "none_detected"},
        "evidence_used": {
            "records_used_count": 1,
            "sources_proven_used": ["human_baseline"],
            "records_used": [{
                "surface": "human_baseline",
                "title": "verified identity record",
                "path": "",
            }],
        },
        "return_pointer": {
            "effective_route": "recall_orchestrator",
        },
    }

    thread = engine.update_from_event("human_baseline", event_packet)
    summary = engine.where_were_we("human_baseline")

    assert thread.title == "recall_orchestrator"
    assert thread.corrections == []
    assert thread.evidence_refs[0]["surface"] == "human_baseline"
    assert summary["status"] == "FOUND"
    assert summary["latest_event_id"] == "cep_20260820T120000Z_abc123"
    assert summary["next_action"] == "Resume via recall_orchestrator"
    assert summary["boundary"] == "candidate thread projection from continuity event packets; no canon promotion"


def test_duplicate_event_update_does_not_duplicate_thread_lists(tmp_path: Path):
    engine = ThreadEngine(threads_dir=tmp_path)
    event_packet = {
        "event_id": "evt_duplicate",
        "user_intent": "duplicate test",
        "claims_extracted": ["same fact"],
        "uncertainties": ["same question"],
        "evidence_used": [{"path": "same.md"}],
    }

    engine.update_from_event("dupe", event_packet)
    thread = engine.update_from_event("dupe", event_packet)

    assert thread.timeline == ["evt_duplicate"]
    assert thread.facts == ["same fact"]
    assert thread.open_questions == ["same question"]
    assert thread.evidence_refs == [{"path": "same.md"}]


def test_update_from_latest_event_reads_continuity_event_file(tmp_path: Path):
    threads_dir = tmp_path / "threads"
    events_dir = tmp_path / "events"
    events_dir.mkdir()
    latest = {
        "event_id": "cep_latest",
        "user_intent": {"summary": "Rendered Reality"},
        "claims_extracted": ["latest packet claim"],
    }
    (events_dir / "latest.json").write_text(json.dumps(latest), encoding="utf-8")

    engine = ThreadEngine(threads_dir=threads_dir)
    thread = engine.update_from_latest_event("rendered_reality", events_dir=events_dir)

    assert thread is not None
    assert thread.thread_id == "rendered_reality"
    assert thread.timeline == ["cep_latest"]
    assert thread.facts == ["latest packet claim"]


def test_thread_id_is_sanitized_without_escaping_threads_dir(tmp_path: Path):
    engine = ThreadEngine(threads_dir=tmp_path)
    thread = ContinuityThread(thread_id="../unsafe id", title="Unsafe")

    path = engine.save_thread(thread)

    assert path.parent == tmp_path
    assert path.name == "unsafe_id.json"
    assert engine.load_thread("../unsafe id") is not None
