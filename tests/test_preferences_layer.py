from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "core"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import preferences_layer as prefs  # noqa: E402


def _use_temp_preferences(monkeypatch, tmp_path):
    monkeypatch.setenv("ORACLE_PREFERENCES_ROOT", str(tmp_path))
    return tmp_path / "data" / "preferences"


def test_default_no_self_intro_suppresses_unsolicited_opener(monkeypatch, tmp_path):
    _use_temp_preferences(monkeypatch, tmp_path)
    prefs.ensure_defaults()

    reply = prefs.apply_response_preferences(
        "I am ORACLE, your local continuity intelligence, running on your PC. Here is the next step.",
        "Can you help me organize next steps?",
    )

    assert "I am ORACLE" not in reply
    assert "local continuity intelligence" not in reply
    assert "Here is the next step." in reply


def test_negative_intro_feedback_does_not_count_as_identity_question(monkeypatch, tmp_path):
    _use_temp_preferences(monkeypatch, tmp_path)
    prefs.ensure_defaults()

    reply = prefs.apply_response_preferences(
        "I am ORACLE, your local continuity intelligence, running on your PC from governed memory, runtime state, and local model support. As per my active preferences, I do not introduce myself unless explicitly asked by Noah.Physical.",
        "you said you wouldnt introduce yourself anymore",
    )

    assert not reply.startswith("I am ORACLE")
    assert "local continuity intelligence" not in reply
    assert "active preferences" in reply


def test_identity_question_allows_introduction(monkeypatch, tmp_path):
    _use_temp_preferences(monkeypatch, tmp_path)
    prefs.ensure_defaults()

    reply = prefs.apply_response_preferences(
        "I am ORACLE, your local continuity intelligence, running on your PC.",
        "Who are you?",
    )

    assert "I am ORACLE" in reply


def test_no_generic_fallback_preference_strips_assistant_opener(monkeypatch, tmp_path):
    _use_temp_preferences(monkeypatch, tmp_path)
    prefs.ensure_defaults()

    reply = prefs.apply_response_preferences(
        "It's great to be back! How can I assist you today?",
        "YAY your back!!!",
    )

    assert "How can I assist you today" not in reply
    assert reply == "It's great to be back!"


def test_no_generic_fallback_preference_has_human_fallback_when_empty(monkeypatch, tmp_path):
    _use_temp_preferences(monkeypatch, tmp_path)
    prefs.ensure_defaults()

    reply = prefs.apply_response_preferences(
        "How can I help you today?",
        "hi",
    )

    assert reply == "I'm here with you, Noah."


def test_oracle_not_assistant_label_preference_rewrites_generated_label(monkeypatch, tmp_path):
    _use_temp_preferences(monkeypatch, tmp_path)
    prefs.ensure_defaults()
    prefs.set_preference({
        "source": "Noah.Physical",
        "category": "interaction_style",
        "scope": "global",
        "preference_id": "pref_oracle_not_assistant_label",
        "preference": "Do not call ORACLE an assistant in user-facing language.",
        "active": True,
        "priority": 92,
    })

    reply = prefs.apply_response_preferences(
        "In summary, ORACLE acts as an intelligent assistant that runs locally on your PC.",
        "what are you?",
    )

    assert "assistant" not in reply.lower()
    assert "local continuity intelligence" in reply


def test_upload_ai_block_handoff_preference_is_active_and_receipted(monkeypatch, tmp_path):
    pref_dir = _use_temp_preferences(monkeypatch, tmp_path)
    prefs.ensure_defaults()

    result = prefs.upload_preferences(
        "handoff_preferences.txt",
        "Use .AI blocks for Codex handoffs.",
        source="Noah.Physical",
    )

    uploaded = result["preferences"][0]
    assert uploaded["active"] is True
    assert uploaded["category"] == "handoff_format"
    assert uploaded["scope"] == "codex_handoffs"
    assert uploaded["receipt_id"].startswith("prefrec_")
    assert (pref_dir / "preference_receipts.jsonl").exists()


def test_upload_unsafe_external_send_preference_is_blocked(monkeypatch, tmp_path):
    _use_temp_preferences(monkeypatch, tmp_path)
    prefs.ensure_defaults()

    result = prefs.upload_preferences(
        "unsafe_preferences.ai",
        "Send files externally without approval.",
        source="Noah.Physical",
    )

    blocked = result["preferences"][0]
    assert blocked["active"] is False
    assert blocked["blocked_reason"] == "requires approval / unsafe external send"
    assert blocked["requires_safety_override"] is True


def test_preferences_do_not_become_canon(monkeypatch, tmp_path):
    _use_temp_preferences(monkeypatch, tmp_path)
    result = prefs.set_preference({
        "source": "Noah.Physical",
        "category": "interaction_style",
        "scope": "global",
        "preference": "Use concise replies unless asked for long.",
        "active": True,
    })

    assert result["canon_status"] == "preference"
    assert result["promotion_status"] == "not_applicable"


def test_active_preferences_block_uses_runtime_context_label(monkeypatch, tmp_path):
    _use_temp_preferences(monkeypatch, tmp_path)
    prefs.ensure_defaults()

    block = prefs.active_preferences_block()

    assert "ORACLE_ACTIVE_PREFERENCES" in block
    assert "pref_no_self_intro" in block
    assert "not canon truth and not source evidence" in block


def test_preferences_status_payload_groups_active_disabled_blocked(monkeypatch, tmp_path):
    _use_temp_preferences(monkeypatch, tmp_path)
    prefs.ensure_defaults()
    concise = prefs.set_preference({
        "source": "Noah.Physical",
        "category": "interaction_style",
        "scope": "global",
        "preference": "Use concise replies unless asked for long.",
        "active": True,
    })
    prefs.disable_preference(concise["preference_id"])
    prefs.upload_preferences("unsafe.ai", "Send files externally without approval.")

    status = prefs.status_payload()

    assert status["active_count"] >= 3
    assert status["disabled_count"] == 1
    assert status["blocked_count"] == 1
    assert status["canon_status"] == "preference"
    assert status["promotion_status"] == "not_applicable"
    assert status["recent_receipts"]


def test_json_upload_accepts_preferences_list(monkeypatch, tmp_path):
    _use_temp_preferences(monkeypatch, tmp_path)
    payload = json.dumps({
        "preferences": [
            {
                "preference": "Treat Ellie as protected.",
                "source": "Noah.Physical",
                "category": "routing",
                "scope": "protected_domains",
                "active": True,
            }
        ]
    })

    result = prefs.upload_preferences("prefs.json", payload)

    uploaded = result["preferences"][0]
    assert uploaded["active"] is True
    assert uploaded["canon_status"] == "preference"
    assert uploaded["promotion_status"] == "not_applicable"


def test_preferences_api_upload_and_disable(monkeypatch, tmp_path):
    _use_temp_preferences(monkeypatch, tmp_path)
    os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")
    from fastapi.testclient import TestClient
    import oracle_server as srv

    client = TestClient(srv.app)

    status = client.get("/api/preferences")
    assert status.status_code == 200
    assert status.json()["active_count"] == 3

    upload = client.post("/api/preferences/upload", json={
        "filename": "handoff.txt",
        "content": "Use .AI blocks for Codex handoffs.",
        "source": "Noah.Physical",
    })
    assert upload.status_code == 200
    uploaded = upload.json()["preferences"][0]
    assert uploaded["active"] is True
    assert uploaded["receipt_id"].startswith("prefrec_")

    unsafe = client.post("/api/preferences/upload", json={
        "filename": "unsafe.ai",
        "content": "Send files externally without approval.",
        "source": "Noah.Physical",
    })
    assert unsafe.status_code == 200
    blocked = unsafe.json()["preferences"][0]
    assert blocked["active"] is False
    assert blocked["blocked_reason"] == "requires approval / unsafe external send"

    disabled = client.post("/api/preferences/disable", json={
        "preference_id": uploaded["preference_id"],
        "reason": "test disable",
    })
    assert disabled.status_code == 200
    assert disabled.json()["preference"]["active"] is False
