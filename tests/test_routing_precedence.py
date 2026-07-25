from __future__ import annotations

import os
import sys
import json
import asyncio
import time
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


def test_report_only_runtime_status_beats_noah_direct_model(monkeypatch, tmp_path):
    import unified_oracle_router as router

    monkeypatch.setattr(router, "ROUTING_DIR", tmp_path / "routing")
    monkeypatch.setattr(router, "RECEIPTS_DIR", tmp_path / "receipts")
    monkeypatch.setattr(router, "COMPANION_DIR", tmp_path / "companion")
    monkeypatch.setattr(
        router,
        "PENDING_GUARD_APPROVAL_PATH",
        tmp_path / "routing" / "pending_guard_approval.json",
    )

    prompt = (
        "REPORT ONLY: Report current runtime port, session id, route type, "
        "self prompt status, latest receipt path. Do not execute or mutate."
    )

    def fail_noah_direct(*args, **kwargs):
        raise AssertionError("NOAH_DIRECT model path should not answer runtime status")

    monkeypatch.setattr(srv, "_noah_direct_reply", fail_noah_direct)

    assert srv._noah_direct_should_handle(prompt) is True
    assert srv._unified_live_state_route_type(prompt) == "diagnostic_status"

    payloads = asyncio.run(_collect_stream_payloads(prompt))
    route = next(item for item in payloads if item.get("type") == "route")
    done = payloads[-1]
    text = "".join(item.get("text", "") for item in payloads if item.get("type") == "token")

    assert route["route_type"] == "diagnostic_status"
    assert done["route_type"] == "diagnostic_status"
    assert done["effective_route"] == "diagnostic_status"
    assert "route_type: diagnostic_status" in text


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


def test_plain_english_followup_uses_recent_jupiter_registry_answer():
    jupiter_answer = ts.synthesis_boundary_message(
        ["missing Jupiter Station 2397 active-era lock"],
        "What is Jupiter Station active era and Avalon timeline?",
    )

    reply = srv._plain_english_followup_response(
        "translate to english",
        [{"role": "assistant", "content": jupiter_answer}],
    )

    assert reply is not None
    assert "Avalon's first captain around 2379" in reply
    assert "took command of Jupiter Station in the 2397 active era" in reply
    assert "2371" in reply
    assert "2481" in reply
    assert srv._plain_english_followup_response(
        "translate to english",
        [{"role": "assistant", "content": "Unrelated answer."}],
    ) is None


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


def test_backend_diagnostic_prompt_does_not_return_strategic_boilerplate(monkeypatch):
    import memory

    monkeypatch.setattr(memory, "save_message", lambda *_, **__: None)
    prompt = """
ORACLE BACKEND DIAGNOSTIC TEST 2026-07-23.
No sandbox write. No external action. No canon promotion.
Answer only in six short bullets:
1. What live subsystem state can you verify right now?
2. What do you remember/know from Nexus or Document Atlas?
3. What can you not prove right now?
4. What would make your sandbox writing more intelligent?
5. Should you write to sandbox right now, yes or no, and why?
6. What is the smallest useful next build step?
If unknown, say UNKNOWN. Do not invent.
"""

    dispatch = srv._oracle_intent_dispatch(prompt)
    if dispatch is not None:
        text, route_name = dispatch
        assert route_name != "strategic_planning"
        assert "Goal: advance ORACLE's governed executive function" not in text

    payloads = asyncio.run(_collect_stream_payloads(prompt))
    route = next(p for p in payloads if p.get("type") == "route")
    token = next(p for p in payloads if p.get("type") == "token")
    done = next(p for p in payloads if p.get("type") == "done")

    assert route["route_type"] == "diagnostic_status"
    assert route["lane"] == "talk_lane"
    assert "Goal: advance ORACLE's governed executive function" not in token["text"]
    assert "actions_executed: 0" in token["text"] or "Observation:" in token["text"]
    assert done["effective_route"] == "diagnostic_status"


def test_talk_lane_only_prompt_does_not_return_strategic_boilerplate(monkeypatch):
    import memory

    monkeypatch.setattr(memory, "save_message", lambda *_, **__: None)
    prompt = (
        "Talk lane only. This is a simple question, not a build order and not strategic planning. "
        "No sandbox write. No external action. In your own words, answer Noah briefly."
    )

    dispatch = srv._oracle_intent_dispatch(prompt)
    if dispatch is not None:
        text, route = dispatch
        assert route != "strategic_planning"
        assert "Goal: advance ORACLE's governed executive function" not in text

    payloads = asyncio.run(_collect_stream_payloads(prompt))
    token = next(p for p in payloads if p.get("type") == "token")
    done = next(p for p in payloads if p.get("type") == "done")

    assert "Goal: advance ORACLE's governed executive function" not in token["text"]
    assert done["effective_route"] != "strategic_planning"


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


def test_sandbox_initiative_timeout_fails_closed(monkeypatch):
    import memory
    import sandbox_files as sf

    monkeypatch.setattr(memory, "save_message", lambda *_, **__: None)
    monkeypatch.setattr(srv, "SANDBOX_INITIATIVE_TIMEOUT_SECONDS", 0.01)

    def _stuck_writer(*_args, **_kwargs):
        time.sleep(0.1)
        return {"receipt_path": "sandbox/receipts/late_receipt.json"}

    monkeypatch.setattr(sf, "sandbox_initiative_write", _stuck_writer)

    payloads = asyncio.run(_collect_stream_payloads("write to sandbox"))
    token = next(p for p in payloads if p.get("type") == "token")
    done = next(p for p in payloads if p.get("type") == "done")

    assert "timed out" in token["text"].lower()
    assert done["effective_route"] == "sandbox_initiative_write"


def test_build_with_me_sandbox_language_avoids_voice_lane(monkeypatch, tmp_path):
    import memory
    import sandbox_files as sf

    monkeypatch.setenv("ORACLE_PREFERENCES_ROOT", str(tmp_path))
    monkeypatch.setattr(memory, "save_message", lambda *_, **__: None)
    monkeypatch.setattr(
        sf,
        "sandbox_initiative_write",
        lambda *_args, **_kwargs: {"receipt_path": "sandbox/receipts/mock_build_with_me_receipt.json"},
    )

    payloads = asyncio.run(_collect_stream_payloads(
        "please log noahs new prefrences that you take action in your sandbox "
        "and speak to me from your heart and help me build you"
    ))
    route = next(p for p in payloads if p.get("type") == "route")
    token = next(p for p in payloads if p.get("type") == "token")
    done = next(p for p in payloads if p.get("type") == "done")

    assert route["route_type"] == "sandbox_initiative_write"
    assert route["lane"] == "safe_write"
    assert route["safety_status"] == "Receipt Written"
    assert "not a missing voice feature" in token["text"]
    assert "voice_io" not in token["text"]
    assert "pref_build_with_me_sandbox_text" in route["preferences_applied"]
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


def test_noah_hawkes_approval_given_without_pending_stays_guard(monkeypatch, tmp_path):
    import memory
    import unified_oracle_router as router

    monkeypatch.setattr(memory, "save_message", lambda *_, **__: None)
    monkeypatch.setattr(router, "ROUTING_DIR", tmp_path / "routing")
    monkeypatch.setattr(router, "RECEIPTS_DIR", tmp_path / "receipts")
    monkeypatch.setattr(router, "PENDING_GUARD_APPROVAL_PATH", tmp_path / "routing" / "pending_guard_approval.json")
    monkeypatch.setattr(srv, "_pending_guard_route", None)

    payloads = asyncio.run(_collect_stream_payloads("Noah Hawkes Approval given"))
    route = next(p for p in payloads if p.get("type") == "route")
    token = next(p for p in payloads if p.get("type") == "token")
    done = next(p for p in payloads if p.get("type") == "done")

    assert route["lane"] == "guard_lane"
    assert "no pending executable Guard action is bound" in token["text"]
    assert "Jupiter Station" not in token["text"]
    assert done["effective_route"] == "guard_approval"


def test_noah_hawkes_approval_given_binds_single_pending_guard_route(monkeypatch, tmp_path):
    import memory
    import unified_oracle_router as router

    monkeypatch.setattr(memory, "save_message", lambda *_, **__: None)
    monkeypatch.setattr(router, "ROUTING_DIR", tmp_path / "routing")
    monkeypatch.setattr(router, "RECEIPTS_DIR", tmp_path / "receipts")
    monkeypatch.setattr(router, "PENDING_GUARD_APPROVAL_PATH", tmp_path / "routing" / "pending_guard_approval.json")

    guarded = router.write_route(router.classify_intent("commit all and manage them"))
    pending = router.write_pending_guard_approval(guarded)
    monkeypatch.setattr(srv, "_pending_guard_route", pending)

    payloads = asyncio.run(_collect_stream_payloads("Noah Hawkes Approval given"))
    route = next(p for p in payloads if p.get("type") == "route")
    token = next(p for p in payloads if p.get("type") == "token")
    done = next(p for p in payloads if p.get("type") == "done")

    assert route["lane"] == "guard_lane"
    assert f"Approval recorded for Guard route `{pending['route_id']}`" in token["text"]
    assert "commit all and manage them" in token["text"]
    assert "Jupiter Station" not in token["text"]
    assert done["effective_route"] == "guard_approval"


def test_please_just_talk_to_me_suppresses_repo_and_domain_bleed(monkeypatch):
    import memory

    monkeypatch.setattr(memory, "save_message", lambda *_, **__: None)

    payloads = asyncio.run(_collect_stream_payloads("please just talk to me"))
    route = next(p for p in payloads if p.get("type") == "route")
    token = next(p for p in payloads if p.get("type") == "token")
    done = next(p for p in payloads if p.get("type") == "done")

    assert route["route_type"] == "plain_talk_grounding"
    assert "I'll stay in Talk lane" in token["text"]
    assert "repo status" in token["text"]
    assert "dirty" not in token["text"].lower()
    assert "Jupiter Station" not in token["text"]
    assert done["effective_route"] == "plain_talk_grounding"


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
