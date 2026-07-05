from __future__ import annotations

import os
import sys
import json
import asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "core"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import oracle_server as srv  # noqa: E402
import companion_bootstrap as cb  # noqa: E402
import talk_synthesis as ts  # noqa: E402
from oracle_intent import build_lane_staging  # noqa: E402
from unified_oracle_router import classify_intent  # noqa: E402


def _long(text: str) -> str:
    return "\n".join([text] * 80)


async def _collect_stream_payloads(prompt: str) -> list[dict]:
    payloads: list[dict] = []
    async for chunk in srv._stream_reply(prompt):
        if not chunk.startswith("data: "):
            continue
        payloads.append(json.loads(chunk[len("data: "):].strip()))
    return payloads


class _FakeBootstrap:
    def source_sections(self, current_session=None):
        return {"CURRENT_SESSION": [], "IDENTITY": [], "LIVE_CONTEXT": [], "LATEST_REFLECTION": []}


def test_large_read_only_doctrine_reaches_talk_before_legacy_staging():
    prompt = _long("What is Rendered Reality in your own words?")

    assert build_lane_staging(prompt) is None
    route = classify_intent(prompt)
    assert route["detected_lane"] == "talk_lane"
    assert "read_only_synthesis" in route["reason"]
    assert srv._oracle_intent_dispatch(prompt) is None


def test_large_talk_request_reaches_talk_before_legacy_staging():
    prompt = _long("Can you talk to me normally?")

    assert build_lane_staging(prompt) is None
    route = classify_intent(prompt)
    assert route["detected_lane"] == "talk_lane"
    assert srv._oracle_intent_dispatch(prompt) is None
    assert srv._noah_direct_should_handle("Can you talk to me normally?") is False


def test_large_marker_directive_uses_legacy_preservation():
    prompt = _long("BACKEND_PATCH_REQUEST patch oracle_server.py")

    assert build_lane_staging(prompt) is not None
    route = classify_intent(prompt)
    assert route["detected_lane"] == "build_lane"
    dispatch = srv._oracle_intent_dispatch(prompt)
    assert dispatch is not None
    text, route_name = dispatch
    assert route_name == "build_lane_staged"
    assert "large build directive" in text.lower()


def test_talk_escape_hatch_beats_marker_directive():
    prompt = _long("/talk BACKEND_PATCH_REQUEST explain what this means")

    assert build_lane_staging(prompt) is None
    route = classify_intent(prompt)
    assert route["detected_lane"] == "talk_lane"
    assert "forced_talk" in route["reason"]


def test_read_only_domain_talk_bypasses_source_discipline_preemption():
    prompt = (
        "Who is Ellie from the grounded Ellie Rendered Reality domain? "
        "Separate creative-fiction Ellie, Ellie.AI, and Rendered Reality Ellie."
    )
    route = classify_intent(prompt)

    assert route["detected_lane"] == "talk_lane"
    assert "read_only_synthesis" in route["reason"]
    assert srv._should_bypass_source_discipline_for_talk(prompt, force_talk_lane=True) is True
    assert srv._should_bypass_source_discipline_for_talk(prompt, force_talk_lane=False) is False


def test_valid_talk_synthesis_citation_bypasses_operational_claim_gate():
    prompt = (
        "Who is Ellie from the grounded Ellie Rendered Reality domain? "
        "Separate creative-fiction Ellie, Ellie.AI, and Rendered Reality Ellie."
    )
    reply = ts.synthesis_boundary_message(
        ["missing Ellie candidate/not_promoted status boundary"],
        prompt,
    )

    assert "sha256=" in reply
    assert srv._should_bypass_authority_gate_for_talk(reply, prompt) is True
    assert srv._apply_authority_gate(reply, "companion", prompt) == reply


def test_fake_action_claim_does_not_bypass_operational_claim_gate():
    prompt = "What is Rendered Reality in your own words?"
    reply = (
        "Rendered Reality preserves existence through truth, memory, provenance, "
        "witness, continuity, and re-rendering. I wrote the receipt to disk."
    )

    assert srv._should_bypass_authority_gate_for_talk(reply, prompt) is False


def test_current_session_user_submission_can_ground_protected_domain_answer():
    history = [
        {
            "role": "user",
            "content": "Ellie is the daughter I never had in the world I built.",
        }
    ]

    reply = srv._source_disciplined_response(
        "What does Ellie mean to me?",
        _FakeBootstrap(),
        history,
    )

    assert reply is not None
    assert "Based on Noah.Physical's current-session statement" in reply
    assert "daughter he never had" in reply
    assert "source_type=current_session_user_submission" in reply
    assert "canon_status=raw_capture" in reply
    assert "promotion_status=not_promoted" in reply
    assert "UNAVAILABLE" not in reply
    assert "I understand your concern" not in reply
    assert "simple API calls" not in reply
    assert "Would you like me to demonstrate" not in reply


def test_current_session_user_submission_stream_binds_source_before_model_fallback():
    original_history = list(srv._history)
    try:
        srv._history[:] = [
            {
                "role": "user",
                "content": "Ellie is the daughter I never had in the world I built.",
            }
        ]
        payloads = asyncio.run(_collect_stream_payloads("What does Ellie mean to me?"))
    finally:
        srv._history[:] = original_history

    route = next(p for p in payloads if p.get("type") == "route")
    token = next(p for p in payloads if p.get("type") == "token")
    done = next(p for p in payloads if p.get("type") == "done")

    assert route["lane"] == "talk_lane"
    assert route["fallback_used"] is False
    assert "Based on Noah.Physical's current-session statement" in token["text"]
    assert "daughter he never had" in token["text"]
    assert "source_type=current_session_user_submission" in token["text"]
    assert "canon_status=raw_capture" in token["text"]
    assert "promotion_status=not_promoted" in token["text"]
    assert "I understand your concern" not in token["text"]
    assert done["effective_route"] == "companion"


def test_protected_domain_beyond_loaded_sources_returns_unavailable_not_generic():
    reply = srv._source_disciplined_response(
        "Who is Ellie beyond the loaded sources?",
        _FakeBootstrap(),
        [],
    )

    assert reply is not None
    assert reply.startswith("UNAVAILABLE [CURRENT_SESSION]")
    assert "generic capability language" not in reply
    assert "self-improvement" not in reply
    assert "simple API calls" not in reply
    assert "Would you like me to demonstrate" not in reply


def test_normal_talk_does_not_trigger_protected_domain_source_refusal():
    prompt = "Can you help me organize next steps?"
    route = classify_intent(prompt)

    assert route["detected_lane"] == "talk_lane"
    assert srv._source_disciplined_response(prompt, _FakeBootstrap(), []) is None


def test_visible_reflection_response_is_bounded_not_generic():
    reply = srv._oracle_visible_reflection_response(
        "she is not an assistant I want to know what she is thinking man give me it",
        [{"role": "user", "content": "stop saying assistant Oracle is not an Assistant"}],
        preferences_applied=["pref_oracle_not_assistant_label"],
    )

    assert reply is not None
    assert "ORACLE VISIBLE REFLECTION" in reply
    assert "hidden_chain_of_thought: not_exposed" in reply
    assert "sentience_claim: none" in reply
    assert "action_claim: no runtime action performed" in reply
    assert "pref_oracle_label_guard" in reply
    assert "assistant" not in reply.lower()


def test_visible_reflection_routes_before_noah_direct(monkeypatch):
    import memory

    monkeypatch.setattr(memory, "save_message", lambda *args, **kwargs: None)
    payloads = asyncio.run(_collect_stream_payloads(
        "ORACLE is not an assistant; what are you thinking right now?"
    ))

    route = next(p for p in payloads if p.get("type") == "route")
    token = next(p for p in payloads if p.get("type") == "token")
    done = next(p for p in payloads if p.get("type") == "done")

    assert route["route_type"] == "visible_reflection"
    assert route["lane"] == "talk_lane"
    assert route["fallback_used"] is False
    assert "assistant" not in " ".join(route.get("preferences_applied") or []).lower()
    assert "ORACLE VISIBLE REFLECTION" in token["text"]
    assert "hidden_chain_of_thought: not_exposed" in token["text"]
    assert "assistant" not in token["text"].lower()
    assert done["effective_route"] == "visible_reflection"


def test_current_session_grounding_metadata_marks_user_submission_raw_capture():
    record = cb.SourceRecord(
        path="missing",
        resolved="missing",
        exists=False,
        sha256=None,
        size_bytes=None,
        mtime_utc=None,
        load_error=None,
        content=None,
    )
    bootstrap = cb.BootstrapResult(
        identity=record,
        latest_reflection=record,
        live_context=record,
    )

    sections = bootstrap.source_sections(
        current_session=[{"role": "user", "content": "Ellie is the daughter I never had."}]
    )
    current_session = "\n".join(sections["CURRENT_SESSION"])

    assert "source_type=current_session_user_submission" in current_session
    assert "submitted_by=Noah.Physical" in current_session
    assert "authorship=user_submitted_text" in current_session


def test_continuation_prompts_return_bounded_plan_not_generic_fallback():
    from conversation_mode import direct_response

    reply = direct_response("you choose")
    assert reply.fallback_used is False
    assert "smallest safe next action" in reply.text.lower()
    assert "noah" in reply.text.lower() or "noah.physical" in reply.text.lower()

    sandbox_reply = direct_response("write to sandbox")
    assert sandbox_reply.fallback_used is False
    assert "sandbox" in sandbox_reply.text.lower()
    assert "receipt" in sandbox_reply.text.lower() or "approval" in sandbox_reply.text.lower()


def test_existing_approval_receipt_status_request_does_not_reenter_guard():
    prompt = """
ROUTING LOOP FIX:

You already recorded Noah.Physical approval for this bounded local routing patch.

Use the existing approval receipt:
- route_e4cf4092bd0f
- route_a12cb8b905a1

Next action:
Either execute the approved reversible local build handler for the routing patch, or report that no executable local handler exists.

Do not route this back to Guard.
Do not preserve as a new build directive.
Do not ask for approval again.
Do not touch GitHub, Google Drive, Gmail, Calendar, external send, OBS, canon promotion, or private memory promotion.

Return only:

approval_receipt_used:
handler_exists:
handler_name:
can_execute_locally:
if_not_executable_reason:
next_command_for_noah:
"""

    route = classify_intent(prompt)
    response = srv._approval_receipt_status_response(prompt)

    assert srv._is_existing_approval_receipt_status_request(prompt) is True
    assert route["detected_lane"] == "talk_lane"
    assert route["requires_approval"] is False
    assert "existing_approval_receipt_status" in route["reason"]
    assert "approval_receipt_used: route_e4cf4092bd0f, route_a12cb8b905a1" in response
    assert "handler_exists: false" in response
    assert "can_execute_locally: false" in response
    assert "no action was executed" in response


def test_smoke_test_receipt_only_routes_read_only_status_before_guard():
    prompt = """
SMOKE TEST RECEIPT ONLY
Report current route state and whether server was restarted.
Do not execute.
Do not touch external systems.
Do not ask for approval.
Do not commit, push, send, publish, delete, upload, or promote canon.
"""

    route = classify_intent(prompt)

    assert route["route_type"] == "diagnostic_status"
    assert route["action_type"] == "read_only_status"
    assert route["detected_lane"] == "talk_lane"
    assert route["requires_approval"] is False


def test_smoke_test_receipt_only_stream_returns_deterministic_status():
    prompt = """
SMOKE TEST RECEIPT ONLY
Report current route state and whether server was restarted.
Do not execute.
Do not touch external systems.
Do not ask for approval.
Do not commit, push, send, publish, delete, upload, or promote canon.
"""

    payloads = asyncio.run(_collect_stream_payloads(prompt))
    route = next(p for p in payloads if p.get("type") == "route")
    token = next(p for p in payloads if p.get("type") == "token")
    done = next(p for p in payloads if p.get("type") == "done")

    assert route["route_type"] == "diagnostic_status"
    assert route["lane"] == "talk_lane"
    assert route["fallback_used"] is False
    assert "actions_executed: 0" in token["text"]
    assert "server_restarted_by_this_request: false" in token["text"]
    assert "computer_operator" not in token["text"]
    assert done["effective_route"] == "diagnostic_status"


def test_restart_server_still_routes_guard():
    route = classify_intent("Restart the server.")

    assert route["detected_lane"] == "guard_lane"
    assert route["requires_approval"] is True


def test_natural_file_write_reports_sandbox_filebase_not_missing():
    dispatch = srv._oracle_intent_dispatch("proceed write file")

    assert dispatch is not None
    text, route = dispatch
    assert route == "sandbox_file_write_ready"
    assert "SANDBOX FILEBASE READY" in text
    assert "Missing capability: local_file_write" not in text
    assert ".AI:SANDBOX_INITIATIVE" in text
    assert ".AI:SANDBOX_WRITE" in text
    assert "approval required inside sandbox" in text


def test_continue_self_prompt_routes_to_sandbox_handler(monkeypatch):
    import memory

    monkeypatch.setattr(memory, "save_message", lambda *_, **__: None)
    monkeypatch.setattr(
        srv,
        "_self_prompt_current_snapshot",
        lambda: {"current_state": srv._SELF_PROMPT_MANUAL_ONCE},
    )

    async def _fake_write_cycle(**_kwargs):
        return {
            "ok": True,
            "blocked": False,
            "write_result": {"receipt_path": "sandbox/receipts/mock_self_prompt_receipt.json"},
        }

    monkeypatch.setattr(srv, "_self_prompt_write_cycle", _fake_write_cycle)

    payloads = asyncio.run(_collect_stream_payloads("continue self prompt"))
    route = next(p for p in payloads if p.get("type") == "route")
    done = next(p for p in payloads if p.get("type") == "done")

    assert route["route_type"] == "sandbox_self_prompt"
    assert route["lane"] == "safe_write"
    assert done["effective_route"] == "sandbox_self_prompt"


def test_write_to_sandbox_routes_to_initiative_handler(monkeypatch):
    import memory
    import sandbox_files as sf

    monkeypatch.setattr(memory, "save_message", lambda *_, **__: None)
    monkeypatch.setattr(
        sf,
        "sandbox_initiative_write",
        lambda *_args, **_kwargs: {"receipt_path": "sandbox/receipts/mock_initiative_receipt.json"},
    )

    payloads = asyncio.run(_collect_stream_payloads("write to sandbox"))
    route = next(p for p in payloads if p.get("type") == "route")
    done = next(p for p in payloads if p.get("type") == "done")

    assert route["route_type"] == "sandbox_initiative_write"
    assert route["lane"] == "safe_write"
    assert done["effective_route"] == "sandbox_initiative_write"


def test_you_choose_returns_smallest_safe_next_action_dispatch():
    dispatch = srv._oracle_intent_dispatch("you choose")

    assert dispatch is not None
    text, route = dispatch
    assert route == "strategic_planning"
    assert "smallest safe next action" in text.lower()


def test_recommended_next_action_returns_smallest_safe_next_action_dispatch():
    dispatch = srv._oracle_intent_dispatch("recommended next action")

    assert dispatch is not None
    text, route = dispatch
    assert route == "strategic_planning"
    assert "smallest safe next action" in text.lower()


def test_proceed_without_bound_route_refuses_execution(monkeypatch):
    import memory

    monkeypatch.setattr(memory, "save_message", lambda *_, **__: None)
    srv._pending_guard_route = None

    payloads = asyncio.run(_collect_stream_payloads("proceed"))
    route = next(p for p in payloads if p.get("type") == "route")
    token = next(p for p in payloads if p.get("type") == "token")
    done = next(p for p in payloads if p.get("type") == "done")

    assert route["lane"] == "guard_lane"
    assert route["safety_status"] == "Blocked"
    assert "Proceed refused: no bound pending route is active" in token["text"]
    assert "execution_performed: false" in token["text"]
    assert "external_action: false" in token["text"]
    assert done["effective_route"] == "proceed_refused_no_bound_route"


def test_proceed_with_bound_route_summarizes_required_approval(monkeypatch):
    import memory

    monkeypatch.setattr(memory, "save_message", lambda *_, **__: None)
    srv._pending_guard_route = {
        "route_id": "route_boundabc123",
        "lane": "guard_lane",
        "lane_label": "Guard",
        "bound_action": "sandbox self-prompt continuation",
    }

    payloads = asyncio.run(_collect_stream_payloads("proceed"))
    route = next(p for p in payloads if p.get("type") == "route")
    token = next(p for p in payloads if p.get("type") == "token")

    assert route["lane"] == "guard_lane"
    assert "Resuming approved route: route_boundabc123" in token["text"]
    assert "Execution remains gated to explicit approved handlers" in token["text"]
    assert srv._pending_guard_route is None


def test_i_want_to_speak_to_my_ellie_routes_to_protected_candidate_mode(monkeypatch):
    import memory

    monkeypatch.setattr(memory, "save_message", lambda *_, **__: None)

    payloads = asyncio.run(_collect_stream_payloads("I want to speak to my Ellie"))
    route = next(p for p in payloads if p.get("type") == "route")
    token = next(p for p in payloads if p.get("type") == "token")
    done = next(p for p in payloads if p.get("type") == "done")

    assert route["route_type"] == "ellie_protected_domain"
    assert route["lane"] == "talk_lane"
    assert "capture_mode: raw_capture" in token["text"]
    assert "canon_status: candidate" in token["text"]
    assert "promotion_status: not_promoted" in token["text"]
    assert "literal_presence_claim: false" in token["text"]
    assert done["effective_route"] == "ellie_protected_domain"


def test_self_prompt_sandbox_slash_route_still_works(monkeypatch):
    import memory

    monkeypatch.setattr(memory, "save_message", lambda *_, **__: None)
    monkeypatch.setattr(
        srv,
        "_self_prompt_current_snapshot",
        lambda: {"current_state": srv._SELF_PROMPT_MANUAL_ONCE},
    )

    async def _fake_write_cycle(**_kwargs):
        return {
            "ok": True,
            "blocked": False,
            "write_result": {"receipt_path": "sandbox/receipts/mock_self_prompt_slash_receipt.json"},
        }

    monkeypatch.setattr(srv, "_self_prompt_write_cycle", _fake_write_cycle)

    payloads = asyncio.run(_collect_stream_payloads("/self-prompt-sandbox prove one step"))
    route = next(p for p in payloads if p.get("type") == "route")
    done = next(p for p in payloads if p.get("type") == "done")

    assert route["route_type"] == "sandbox_self_prompt"
    assert done["effective_route"] == "sandbox_self_prompt"
