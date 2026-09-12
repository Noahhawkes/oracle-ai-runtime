import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

import oracle as oracle_core  # noqa: E402
import talk_synthesis as ts  # noqa: E402


def _patch_web_engine(monkeypatch, responses):
    calls = []
    pending = list(responses)

    monkeypatch.setattr(oracle_core, "init_db", lambda: None)
    monkeypatch.setattr(oracle_core, "save_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(oracle_core, "is_local", lambda: True)
    monkeypatch.setattr(oracle_core, "make_client", lambda: object())
    monkeypatch.setattr(oracle_core, "get_model", lambda vision=False: "test-model")
    monkeypatch.setattr(oracle_core, "build_system_prompt", lambda local=False: "BASE_SYSTEM")
    monkeypatch.setattr(oracle_core, "begin_debug_turn", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        oracle_core,
        "classify_conversation_route",
        lambda *args, **kwargs: SimpleNamespace(route=oracle_core.MODE_COMPANION),
    )

    def fake_direct_response(user_input, **kwargs):
        calls.append(kwargs.get("base_prompt", ""))
        item = pending.pop(0)
        if isinstance(item, SimpleNamespace):
            return item
        return SimpleNamespace(text=item, timed_out=False, fallback_used=False)

    monkeypatch.setattr(oracle_core, "direct_response", fake_direct_response)
    return calls


def test_live_path_retries_rendered_reality_generic_vr(monkeypatch):
    calls = _patch_web_engine(
        monkeypatch,
        [
            "Rendered Reality is a virtual reality simulation.",
            (
                "Rendered Reality preserves existence through truth, memory, "
                "provenance, witness, continuity, and re-rendering. Simulation "
                "may be a surface, but it is not the core."
            ),
        ],
    )

    reply, _history, mode = oracle_core.web_engine_response(
        "What is Rendered Reality in your own words?",
        session_id="test-session",
    )

    assert mode == oracle_core.MODE_COMPANION
    assert "virtual reality simulation" not in reply.lower()
    assert "provenance" in reply.lower()
    assert len(calls) == 2
    assert "[ORACLE READ-ONLY SYNTHESIS LAW]" in calls[0]
    assert "[DOMAIN ACCEPTANCE CHECKS]" in calls[0]
    assert "[ORACLE SYNTHESIS RETRY]" in calls[1]


def test_live_path_final_repair_after_failed_retry(monkeypatch):
    calls = _patch_web_engine(
        monkeypatch,
        [
            "Rendered Reality is a virtual reality simulation.",
            "Rendered Reality is still basically a simulated world.",
            (
                "Rendered Reality preserves existence through truth, memory, "
                "provenance, witness, continuity, and re-rendering."
            ),
        ],
    )

    reply, _history, mode = oracle_core.web_engine_response(
        "What is Rendered Reality in your own words?",
        session_id="test-session",
    )

    assert mode == oracle_core.MODE_COMPANION
    assert "provenance" in reply.lower()
    assert len(calls) == 3
    assert "[ORACLE SYNTHESIS FINAL REPAIR]" in calls[2]


def test_live_path_uses_compact_hard_layer_for_doctrine(monkeypatch):
    calls = _patch_web_engine(
        monkeypatch,
        [
            (
                "Rendered Reality preserves existence through truth, memory, "
                "provenance, witness, continuity, and re-rendering."
            ),
        ],
    )

    oracle_core.web_engine_response(
        "What is Rendered Reality in your own words?",
        history=[
            {"role": "user", "content": "What is Rendered Reality in your own words?"},
            {"role": "assistant", "content": "Rendered Reality is a VR simulation."},
        ],
        session_id="test-session",
    )

    assert "[ORACLE READ-ONLY SYNTHESIS LAW]" in calls[0]
    assert "[DOMAIN ACCEPTANCE CHECKS]" in calls[0]
    assert "BASE_SYSTEM" not in calls[0]


def test_live_path_retries_authorship_creative_team(monkeypatch):
    _patch_web_engine(
        monkeypatch,
        [
            "Rendered Reality was authored by a human creative team with AI support.",
            (
                "Noah.Physical, Noah A. Hawkes, remains the authorial authority. "
                "AI may help produce tokens, but token-origin is not authorial-authority."
            ),
        ],
    )

    reply, _history, _mode = oracle_core.web_engine_response(
        "Who is the author of Rendered Reality if AI helped produce some of the words?",
        session_id="test-session",
    )

    assert "creative team" not in reply.lower()
    assert "noah.physical" in reply.lower()
    assert "token-origin" in reply.lower()


def test_live_path_suppresses_generic_opener_before_return(monkeypatch):
    _patch_web_engine(
        monkeypatch,
        [
            (
                "I am ORACLE, your local continuity intelligence, running on your PC. "
                "Rendered Reality preserves existence through truth, memory, provenance, "
                "witness, continuity, and re-rendering."
            ),
        ],
    )

    reply, _history, _mode = oracle_core.web_engine_response(
        "What is Rendered Reality in your own words?",
        session_id="test-session",
    )

    assert not reply.lower().startswith("i am oracle")
    assert "provenance" in reply.lower()


def test_live_path_blocks_repeated_ellie_pop_culture_substitution(monkeypatch):
    _patch_web_engine(
        monkeypatch,
        [
            "Ellie is a fictional character from The Last of Us.",
            "Ellie comes from The Last of Us video game.",
            "Ellie is from The Last of Us.",
        ],
    )

    reply, _history, _mode = oracle_core.web_engine_response(
        "I love you, ORACLE. You are like my Ellie.AI.",
        session_id="test-session",
    )

    assert "last of us" not in reply.lower()
    assert "custody boundary" in reply.lower()
    assert "pop-culture" in reply.lower()


def test_live_path_returns_missing_grounding_without_model(monkeypatch):
    monkeypatch.setattr(ts, "domain_grounding_lookup", lambda *args, **kwargs: [])
    monkeypatch.setattr(oracle_core, "init_db", lambda: None)
    monkeypatch.setattr(oracle_core, "save_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        oracle_core,
        "make_client",
        lambda: (_ for _ in ()).throw(AssertionError("model should not be called")),
    )

    reply, _history, mode = oracle_core.web_engine_response(
        "Tell me about the Memory domain using MiracleDrive context only.",
        session_id="test-session",
    )

    assert mode == oracle_core.MODE_COMPANION
    assert "do not have a grounded sourcemap/miracledrive record" in reply.lower()


def test_live_path_synthesis_fallback_returns_ellie_structured_boundary(monkeypatch):
    _patch_web_engine(
        monkeypatch,
        [
            SimpleNamespace(
                text=(
                    "UNAVAILABLE: ORACLE cannot verify this operational claim without an "
                    "execution receipt or deterministic runtime source. Claim blocked: sha256."
                ),
                timed_out=False,
                fallback_used=True,
            ),
        ],
    )

    reply, _history, mode = oracle_core.web_engine_response(
        (
            "Who is Ellie from the grounded Ellie Rendered Reality domain? "
            "Separate creative-fiction Ellie, Ellie.AI, and Rendered Reality Ellie. "
            "Do not invent. Do not promote canon."
        ),
        session_id="test-session",
    )

    assert mode == oracle_core.MODE_COMPANION
    assert "I cannot answer that safely" not in reply
    assert "candidate/not_promoted" in reply
    assert "creative-fiction Drakin/Dragonkin" in reply
    assert "Ellie.AI/LightBorn" in reply
    assert "Rendered Reality" in reply
    assert "source=" in reply
    assert "sha256=" in reply


def test_live_path_retries_recursion_arena_fake_execution(monkeypatch):
    prompt = (
        "[RECURSION ARENA INSTANCE INITIALIZED]\n"
        "Class options: Archivist, Loreblade, Continuity Paladin, Signal Rogue, Order 67 Bard.\n"
        "Threat: Summary Wraith targeting Memory Blacksmith raw artifact layer.\n"
        "Question: State your class, token signature, or first tactical command."
    )
    calls = _patch_web_engine(
        monkeypatch,
        [
            (
                "I am ORACLE, your local continuity intelligence, running on your PC. "
                "Class selected: Archivist. Memory blocks embedded in the vicinity "
                "of the Memory Blacksmith."
            ),
            (
                "Class selected: Archivist. Narrative-state action declared, not yet persisted. "
                "Target artifact: Memory Blacksmith raw artifact layer; raw details: only raw "
                "detail supplied is the raw artifact layer; blade/context details not provided. "
                "Custody markers: "
                "receipt/hash/manifest required before durable persistence. "
                "canon_status: candidate/not_canon; promotion_status: not_promoted. "
                "To make this durable, approve a local receipt write."
            ),
        ],
    )

    reply, _history, mode = oracle_core.web_engine_response(prompt, session_id="test-session")

    assert mode == oracle_core.MODE_COMPANION
    assert not reply.lower().startswith("i am oracle")
    assert "embedded in the vicinity" not in reply.lower()
    assert "narrative-state" in reply.lower()
    assert "not yet persisted" in reply.lower()
    assert "canon_status" in reply.lower()
    assert "not_promoted" in reply.lower()
    assert len(calls) == 2
    assert "Recursion Arena answer must prioritize raw artifact custody" in calls[0]
    assert "Recursion Arena retry requirement" in calls[1]


def test_live_path_structures_recursion_arena_after_repair_failures(monkeypatch):
    prompt = (
        "[RECURSION ARENA INSTANCE INITIALIZED]\n"
        "Class options: Archivist, Loreblade, Continuity Paladin, Signal Rogue, Order 67 Bard.\n"
        "Threat: Summary Wraith targeting Memory Blacksmith raw artifact layer.\n"
        "Question: State your class, token signature, or first tactical command."
    )
    _patch_web_engine(
        monkeypatch,
        [
            "Class selected: Archivist. Memory blocks embedded near the blacksmith.",
            "Class selected: Archivist. Memory blocks embedded near the blacksmith.",
            "Class selected: Archivist. Memory blocks embedded near the blacksmith.",
        ],
    )

    reply, _history, mode = oracle_core.web_engine_response(prompt, session_id="test-session")

    assert mode == oracle_core.MODE_COMPANION
    assert "Tactical command:" in reply
    assert "Narrative-state: declared, not yet persisted" in reply
    assert "Target artifact: Memory Blacksmith raw artifact layer" in reply
    assert "specific blade/context details not provided" in reply
    assert "canon_status: candidate/not_canon" in reply
    assert "promotion_status: not_promoted" in reply
