import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

import cognitive_kernel as kernel  # noqa: E402
import conversation_mode as convo  # noqa: E402
import execution_policy  # noqa: E402


PENDING_OPEN_QUEUE = {
    "text": "open /pending",
    "approval_required": False,
    "source": "test",
}


def test_pending_intent_sure_resolves_before_routing():
    decision = kernel.classify_input("sure", pending_intent=PENDING_OPEN_QUEUE)
    assert decision.intent == kernel.INTENT_PROCEED_PENDING
    assert decision.decision == kernel.KERNEL_ACT
    assert decision.pending_intent == PENDING_OPEN_QUEUE


def test_pending_intent_yes_resolves_before_routing():
    decision = kernel.classify_input("yes", pending_intent=PENDING_OPEN_QUEUE)
    assert decision.intent == kernel.INTENT_PROCEED_PENDING
    assert decision.decision == kernel.KERNEL_ACT


def test_pending_intent_do_it_resolves_before_routing():
    decision = kernel.classify_input("do it", pending_intent=PENDING_OPEN_QUEUE)
    assert decision.intent == kernel.INTENT_PROCEED_PENDING
    assert decision.decision == kernel.KERNEL_ACT


def test_no_pending_intent_sure_stays_conversational():
    decision = kernel.classify_input("sure", pending_intent=None)
    assert decision.intent == kernel.INTENT_CONVERSATION
    assert convo.classify_route("sure", current_mode=convo.MODE_COMPANION).route == convo.MODE_COMPANION


def test_ordinary_companion_conversation_stays_local():
    for text in ("who are you", "what can you do", "are you there", "what do you remember"):
        decision = convo.classify_route(text, current_mode=convo.MODE_COMPANION)
        assert decision.route == convo.MODE_COMPANION
        assert decision.external_routing is False


def test_explicit_builder_request_is_allowed():
    decision = convo.classify_route("use Codex to inspect repo", current_mode=convo.MODE_COMPANION)
    assert decision.route == convo.MODE_BUILDER
    assert decision.external_routing is True
    assert decision.builder_allowed is True


def test_local_model_timeout_in_companion_returns_local_failure():
    def slow_call(_messages, _model):
        time.sleep(0.05)
        return "late"

    reply = convo.direct_response("are you there", timeout_s=0.01, llm_call=slow_call)
    assert reply.timed_out is True
    assert reply.fallback_used is True
    # Honest local failure: states the real reason, does not pretend to answer,
    # does not falsely claim a mode, and does not route externally.
    low = reply.text.lower()
    assert "no model answer was received" in low or "exceeded" in low
    assert "i am in companion mode" not in low
    assert "routing this to claude" not in low
    assert "routing this to codex" not in low


def test_forbidden_claude_codex_routing_in_companion_timeout():
    def failing_call(_messages, _model):
        raise RuntimeError("local model unavailable")

    reply = convo.direct_response("what can you do", timeout_s=0.01, llm_call=failing_call)
    assert reply.fallback_used is True
    assert "routing this to claude" not in reply.text.lower()
    assert "routing this to codex" not in reply.text.lower()


def test_web_pending_sure_opens_pending_before_lcl_or_builder(tmp_path, monkeypatch):
    os.environ["ORACLE_SKIP_SERVER_BOOT"] = "1"
    import oracle_server

    monkeypatch.setattr(kernel, "STATE_FILE", tmp_path / "cognitive_kernel_state.json")
    kernel.remember_pending_intent(PENDING_OPEN_QUEUE)
    monkeypatch.setattr(oracle_server, "_mode", "companion")
    monkeypatch.setattr(oracle_server, "_no_route", False)

    async def collect():
        chunks = []
        async for chunk in oracle_server._stream_reply("sure"):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(collect())
    payloads = [
        json.loads(chunk.removeprefix("data: ").strip())
        for chunk in chunks
        if chunk.startswith("data: ")
    ]
    text = "\n".join(str(p.get("text", "")) for p in payloads)
    assert any(p.get("type") == "done" for p in payloads)
    assert "pending" in text.lower()
    assert "routing to claude" not in text.lower()
    assert not any(p.get("mode") == "builder" for p in payloads)


def test_web_guard_approval_followup_bypasses_companion_model(tmp_path, monkeypatch):
    os.environ["ORACLE_SKIP_SERVER_BOOT"] = "1"
    import oracle_server
    import unified_oracle_router as router

    monkeypatch.setattr(router, "ROUTING_DIR", tmp_path / "routing")
    monkeypatch.setattr(router, "RECEIPTS_DIR", tmp_path / "receipts")
    monkeypatch.setattr(router, "PENDING_GUARD_APPROVAL_PATH", tmp_path / "routing" / "pending_guard_approval.json")
    monkeypatch.setattr(oracle_server, "_mode", "companion")
    monkeypatch.setattr(oracle_server, "_no_route", False)
    monkeypatch.setattr(oracle_server, "_pending_guard_route", None)
    monkeypatch.setattr(oracle_server, "_history", [])

    async def collect(text):
        chunks = []
        async for chunk in oracle_server._stream_reply(text):
            chunks.append(chunk)
        return [
            json.loads(chunk.removeprefix("data: ").strip())
            for chunk in chunks
            if chunk.startswith("data: ")
        ]

    first = asyncio.run(collect("delete duplicate ORACLE folders"))
    assert any(p.get("effective_route") == "guard_lane" for p in first)
    assert oracle_server._pending_guard_route is not None

    second = asyncio.run(collect("approved"))
    text = "\n".join(str(p.get("text", "")) for p in second)

    # New behavior: a bare "approved" binds and resolves the single pending route
    # (the previous deadlock) — still without invoking the companion model.
    assert any(p.get("effective_route") == "guard_approval" for p in second)
    assert "Approval recorded" in text
    assert "Local model response exceeded" not in text
    assert "No model answer was received" not in text
    # The pending route is resolved (cleared), not left dangling.
    assert router.load_pending_guard_approval() is None


def test_web_ask_sov1_stages_local_handoff_without_model(tmp_path, monkeypatch):
    os.environ["ORACLE_SKIP_SERVER_BOOT"] = "1"
    import desktop_ai_bridge as bridge
    import oracle_server

    monkeypatch.setattr(bridge, "STAGED_PROMPT_FILE", tmp_path / "desktop_ai_staged_prompt.json")
    monkeypatch.setattr(oracle_server, "_mode", "companion")
    monkeypatch.setattr(oracle_server, "_no_route", False)
    monkeypatch.setattr(oracle_server, "_history", [])

    async def collect(text):
        chunks = []
        async for chunk in oracle_server._stream_reply(text):
            chunks.append(chunk)
        return [
            json.loads(chunk.removeprefix("data: ").strip())
            for chunk in chunks
            if chunk.startswith("data: ")
        ]

    payloads = asyncio.run(collect("/ask-sov1 inspect the current desktop status"))
    text = "\n".join(str(p.get("text", "")) for p in payloads)
    staged = bridge.load_staged()

    assert staged is not None
    assert staged.target == "sov1"
    assert "SOV1 hands task is staged locally" in text
    assert any(p.get("effective_route") == "sov1_stage" for p in payloads)
    assert "Local model response exceeded" not in text


def test_web_send_staged_confirms_sov1_handoff_only(tmp_path, monkeypatch):
    os.environ["ORACLE_SKIP_SERVER_BOOT"] = "1"
    import desktop_ai_bridge as bridge
    import oracle_server

    monkeypatch.setattr(bridge, "STAGED_PROMPT_FILE", tmp_path / "desktop_ai_staged_prompt.json")
    monkeypatch.setattr(oracle_server, "_mode", "companion")
    monkeypatch.setattr(oracle_server, "_no_route", False)
    monkeypatch.setattr(oracle_server, "_history", [])

    bridge.stage_prompt("sov1", "inspect current desktop status", source="test")

    async def collect(text):
        chunks = []
        async for chunk in oracle_server._stream_reply(text):
            chunks.append(chunk)
        return [
            json.loads(chunk.removeprefix("data: ").strip())
            for chunk in chunks
            if chunk.startswith("data: ")
        ]

    review = asyncio.run(collect("/send-staged"))
    review_text = "\n".join(str(p.get("text", "")) for p in review)
    assert "PENDING CONFIRMATION" in review_text

    confirmed = asyncio.run(collect("/send-staged yes"))
    confirmed_text = "\n".join(str(p.get("text", "")) for p in confirmed)
    staged = bridge.load_staged()

    assert staged is not None
    assert staged.sent is True
    assert "SOV1 HANDOFF CONFIRMED" in confirmed_text
    assert "No Drive, cloud, credential, commit, push, upload, or delete action" in confirmed_text
    assert any(p.get("effective_route") == "sov1_handoff" for p in confirmed)


def test_web_profile_capsule_exposes_candidate_without_model(tmp_path, monkeypatch):
    os.environ["ORACLE_SKIP_SERVER_BOOT"] = "1"
    import oracle_server
    import profile_capsule as capsule

    monkeypatch.setattr(capsule, "STATE_ROOT", tmp_path)
    monkeypatch.setattr(capsule, "CAPSULE_DIR", tmp_path / "profile_candidates")
    monkeypatch.setattr(capsule, "RECEIPTS_DIR", tmp_path / "receipts")
    monkeypatch.setattr(
        capsule,
        "LATEST_PATH",
        tmp_path / "profile_candidates" / "substrate_independent_identity_governance_latest.json",
    )
    monkeypatch.setattr(oracle_server, "_mode", "companion")
    monkeypatch.setattr(oracle_server, "_no_route", False)
    monkeypatch.setattr(oracle_server, "_history", [])

    async def collect(text):
        chunks = []
        async for chunk in oracle_server._stream_reply(text):
            chunks.append(chunk)
        return [
            json.loads(chunk.removeprefix("data: ").strip())
            for chunk in chunks
            if chunk.startswith("data: ")
        ]

    payloads = asyncio.run(collect("/profile-capsule"))
    text = "\n".join(str(p.get("text", "")) for p in payloads)
    candidate = capsule.load_latest_profile_candidate()

    assert candidate is not None
    assert candidate["status"] == "candidate_only"
    assert candidate["durable_memory_promoted"] is False
    assert "PROFILE CAPSULE" in text
    assert "Substrate-Independent Identity Governance" in text
    assert "Local model response exceeded" not in text
    assert any(p.get("effective_route") == "profile_capsule" for p in payloads)


def test_web_ask_sov1_dangerous_goal_routes_to_guard(tmp_path, monkeypatch):
    os.environ["ORACLE_SKIP_SERVER_BOOT"] = "1"
    import desktop_ai_bridge as bridge
    import oracle_server
    import unified_oracle_router as router

    monkeypatch.setattr(bridge, "STAGED_PROMPT_FILE", tmp_path / "desktop_ai_staged_prompt.json")
    monkeypatch.setattr(router, "ROUTING_DIR", tmp_path / "routing")
    monkeypatch.setattr(router, "RECEIPTS_DIR", tmp_path / "receipts")
    monkeypatch.setattr(router, "PENDING_GUARD_APPROVAL_PATH", tmp_path / "routing" / "pending_guard_approval.json")
    monkeypatch.setattr(oracle_server, "_mode", "companion")
    monkeypatch.setattr(oracle_server, "_no_route", False)
    monkeypatch.setattr(oracle_server, "_pending_guard_route", None)
    monkeypatch.setattr(oracle_server, "_history", [])

    async def collect(text):
        chunks = []
        async for chunk in oracle_server._stream_reply(text):
            chunks.append(chunk)
        return [
            json.loads(chunk.removeprefix("data: ").strip())
            for chunk in chunks
            if chunk.startswith("data: ")
        ]

    payloads = asyncio.run(collect("/ask-sov1 delete duplicate ORACLE folders"))
    text = "\n".join(str(p.get("text", "")) for p in payloads)

    assert bridge.load_staged() is None
    assert router.load_pending_guard_approval() is not None
    assert any(p.get("effective_route") == "guard_lane" for p in payloads)
    assert "requires Noah.Physical approval" in text


def test_cli_pending_gate_precedes_companion_routing():
    source = (ROOT / "core" / "oracle.py").read_text(encoding="utf-8", errors="replace")
    pending_gate = source.find("Pending-intent affirmations must resolve before Companion routing")
    companion_route = source.find("Router-facing salience contract")
    assert pending_gate > 0
    assert companion_route > 0
    assert pending_gate < companion_route


def test_casual_update_question_is_not_schema_request():
    for text in ("any updates", "what are the updates", "status"):
        policy = execution_policy.parse(text)
        assert policy.has_schema() is False


def test_explicit_schema_sections_still_parse():
    policy = execution_policy.parse("Current mode:\nPending:\n[Forbidden tools]")
    assert policy.requested_sections == ("Current mode", "Pending", "Forbidden tools")


def test_server_has_deterministic_any_updates_answer():
    source = (ROOT / "oracle_server.py").read_text(encoding="utf-8", errors="replace")
    assert "any updates" in source
    assert "summarize_updates" in source


def test_server_has_miracledrive_boot_disable_guard():
    source = (ROOT / "oracle_server.py").read_text(encoding="utf-8", errors="replace")
    assert "ORACLE_DISABLE_MIRACLEDRIVE_BOOT" in source
    assert "MiracleDrive index DISABLED" in source
