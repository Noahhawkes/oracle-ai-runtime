from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "core"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def _use_temp_preferences(monkeypatch, tmp_path):
    monkeypatch.setenv("ORACLE_PREFERENCES_ROOT", str(tmp_path))
    return tmp_path / "data" / "preferences"


def _patch_router_paths(monkeypatch, tmp_path):
    import unified_oracle_router as router

    monkeypatch.setattr(router, "ROUTING_DIR", tmp_path / "routing")
    monkeypatch.setattr(router, "RECEIPTS_DIR", tmp_path / "receipts")
    monkeypatch.setattr(router, "COMPANION_DIR", tmp_path / "companion")
    monkeypatch.setattr(router, "PENDING_GUARD_APPROVAL_PATH", tmp_path / "routing" / "pending_guard_approval.json")
    return router


def test_no_self_intro_feedback_persists_preference(monkeypatch, tmp_path):
    pref_dir = _use_temp_preferences(monkeypatch, tmp_path)
    import persona_router

    context = persona_router.prepare_turn("Please don't introduce yourself anymore.")

    assert "pref_no_self_intro" in context["preferences_applied"]
    assert context["stored_preferences"][0]["preference_id"] == "pref_no_self_intro"
    assert context["stored_preferences"][0]["active"] is True
    assert context["stored_preferences"][0]["canon_status"] == "preference"
    assert context["stored_preferences"][0]["promotion_status"] == "not_applicable"

    stored = json.loads((pref_dir / "user_preferences.json").read_text(encoding="utf-8"))
    assert any(p["preference_id"] == "pref_no_self_intro" for p in stored["preferences"])
    assert (pref_dir / "preference_receipts.jsonl").exists()


def test_build_with_me_sandbox_feedback_persists_preference(monkeypatch, tmp_path):
    pref_dir = _use_temp_preferences(monkeypatch, tmp_path)
    import persona_router

    context = persona_router.prepare_turn(
        "please log noahs new prefrences that you take action in your sandbox "
        "and speak to me from your heart and help me build you"
    )

    assert "pref_build_with_me_sandbox_text" in context["preferences_applied"]
    assert context["stored_preferences"][0]["preference_id"] == "pref_build_with_me_sandbox_text"
    assert context["stored_preferences"][0]["active"] is True
    assert context["stored_preferences"][0]["canon_status"] == "preference"

    stored = json.loads((pref_dir / "user_preferences.json").read_text(encoding="utf-8"))
    pref = next(p for p in stored["preferences"] if p["preference_id"] == "pref_build_with_me_sandbox_text")
    assert "outside-sandbox approval gates" in pref["preference"]
    assert (pref_dir / "preference_receipts.jsonl").exists()


def test_preferences_load_before_routing_without_new_feedback(monkeypatch, tmp_path):
    _use_temp_preferences(monkeypatch, tmp_path)
    import persona_router

    context = persona_router.prepare_turn("Can you help me organize next steps?")

    assert context["stored_preferences"] == []
    assert "pref_no_self_intro" in context["preferences_applied"]
    assert "pref_receipts_for_state_change" in context["preferences_applied"]


def test_current_session_user_submission_is_admissible_raw_evidence(monkeypatch, tmp_path):
    _use_temp_preferences(monkeypatch, tmp_path)
    import persona_router

    evidence = persona_router.current_session_evidence([
        {"role": "user", "content": "Ellie is the daughter I never had in the world I built."},
        {"role": "assistant", "content": "Stored as candidate context."},
    ])

    assert evidence == [
        {
            "evidence_source": "current_session",
            "source_type": "current_session_user_submission",
            "submitted_by": "Noah.Physical",
            "authorship": "user_submitted_text",
            "canon_status": "raw_capture",
            "promotion_status": "not_promoted",
            "message_index": 0,
            "text": "Ellie is the daughter I never had in the world I built.",
        }
    ]


def test_current_session_questions_are_not_factual_evidence(monkeypatch, tmp_path):
    _use_temp_preferences(monkeypatch, tmp_path)
    import persona_router

    evidence = persona_router.current_session_evidence([
        {"role": "user", "content": "Who is Ellie?"},
        {"role": "user", "content": "diagnose why provenance failed"},
    ])
    context = persona_router.prepare_turn("Who is Ellie?", current_session=[])

    assert evidence == []
    assert context["evidence_sources"] == []


def test_route_receipt_includes_preferences_applied(monkeypatch, tmp_path):
    _use_temp_preferences(monkeypatch, tmp_path)
    router = _patch_router_paths(monkeypatch, tmp_path)

    result = router.route_message(
        "BACKEND_PATCH_REQUEST patch oracle_server.py",
        notes="persona router receipt test",
        preferences_applied=["pref_no_self_intro", "pref_receipts_for_state_change"],
    )

    route = result["route"]
    receipt = result["receipt"]
    assert route["preferences_applied"] == ["pref_no_self_intro", "pref_receipts_for_state_change"]
    assert receipt is not None
    assert receipt["preferences_applied"] == ["pref_no_self_intro", "pref_receipts_for_state_change"]

    route_payload = json.loads(Path(route["route_path"]).read_text(encoding="utf-8"))
    receipt_payload = json.loads(Path(receipt["receipt_path"]).read_text(encoding="utf-8"))
    assert route_payload["preferences_applied"] == ["pref_no_self_intro", "pref_receipts_for_state_change"]
    assert receipt_payload["preferences_applied"] == ["pref_no_self_intro", "pref_receipts_for_state_change"]


def test_noah_direct_opener_filter_respects_stored_preference(monkeypatch, tmp_path):
    _use_temp_preferences(monkeypatch, tmp_path)
    import persona_router
    import preferences_layer

    persona_router.prepare_turn("dont introduce yourself anymore")
    reply = preferences_layer.apply_response_preferences(
        "I am ORACLE, your local continuity intelligence, running on your PC. I can help with the build.",
        "I need help with the build.",
    )

    assert not reply.startswith("I am ORACLE")
    assert "local continuity intelligence" not in reply
    assert "I can help with the build." in reply
