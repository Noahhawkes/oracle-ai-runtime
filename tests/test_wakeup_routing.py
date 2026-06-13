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
    assert "local model took too long" in reply.text.lower()
    assert "routing this to claude" not in reply.text.lower()
    assert "routing this to codex" not in reply.text.lower()


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
