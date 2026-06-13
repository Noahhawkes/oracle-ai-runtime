"""
core/conversation_mode.py - direct ORACLE companion routing.

This module is intentionally small and local-only. Companion Mode never
exposes tools to a model and never routes to Claude, Codex, GitHub, or other
external agents.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).parent.parent
STATE_FILE = ROOT / "Memory" / "conversation_mode_state.json"
DEBUG_STATE_FILE = ROOT / "Memory" / "companion_debug_last.json"
PERSONALITY_SEED_FILE = ROOT / "state" / "oracle_personality_seed.json"
DEFAULT_TIMEOUT_SECONDS = 4.5

# Singleton pool — prevents zombie thread accumulation on repeated qwen timeouts.
# One worker: one outstanding local-model request at a time.
_LOCAL_POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="qwen_worker")

MODE_COMPANION = "COMPANION"
MODE_BUILDER = "BUILDER"

_EXPLICIT_BUILDER_PHRASES = (
    "ask claude", "tell claude", "send to claude", "use claude",
    "ask codex", "tell codex", "send to codex", "use codex",
    "write code", "write a function", "write a script", "write a class",
    "patch", "commit", "run tests", "fix repo", "open pr", "open pull request",
    "inspect files", "inspect repo", "inspect the repo", "edit file", "edit code",
    "fix file", "generate diff", "run command", "run script",
    "github", "linear", "stake ledger", "docs", "build yourself",
)

_COMPANION_PHRASES = (
    "talk to me", "i'm frustrated", "im frustrated", "are you there",
    "what do you think", "how are you", "i just want to talk",
    "just talk", "can we talk", "i need to vent", "i feel ",
    "tell me about yourself", "direct relationship", "who are you",
)

_FALLBACKS = (
    "I'm here, Noah. No routing, no handoff. Tell me the next true thing.",
    "I'm with you. We can stay right here and talk this through.",
    "I hear you. I'm staying local and present. What's the part that feels heaviest?",
)

_LAST_DEBUG: dict = {}
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s,;]+"),
)


def _redact(text: str) -> str:
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(lambda m: f"{m.group(1)}=[REDACTED]" if m.lastindex else "[REDACTED]", redacted)
    return redacted


def _context_counts(prompt: str) -> tuple[int, int]:
    lower = prompt.lower()
    memory_count = lower.count("[memory") + lower.count("compressed memory") + lower.count("wake memory")
    doc_count = lower.count("[priority") + lower.count("doctrine") + lower.count("sov1") + lower.count("legacygi")
    return memory_count, doc_count


def begin_debug_turn(user_input: str, route: RouteDecision, *, current_mode: str, no_route: bool) -> None:
    _LAST_DEBUG.clear()
    _LAST_DEBUG.update({
        "raw_user_input": user_input,
        "raw_user_input_redacted": _redact(user_input),
        "raw_user_input_received": bool(user_input),
        "normalized_intent": route.reason,
        "selected_route": route.route,
        "external_routing": route.external_routing,
        "current_mode": current_mode,
        "no_route": bool(no_route),
        "last_user_message_chars": len(user_input),
        "fallback_answered": False,
        "timeout_fired": False,
        "first_token_received": False,
        "local_model_request_started": False,
    })
    _write_debug_snapshot()


def get_debug_context() -> dict:
    return dict(_LAST_DEBUG)


def _write_debug_snapshot(path: Path = DEBUG_STATE_FILE) -> None:
    if not _LAST_DEBUG:
        return
    safe = dict(_LAST_DEBUG)
    if "raw_user_input" in safe:
        safe["raw_user_input"] = safe.get("raw_user_input_redacted", "[REDACTED]")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def echo_last_prompt(*, max_chars: int = 12000) -> str:
    prompt = str(_LAST_DEBUG.get("final_prompt_redacted", ""))
    if not prompt:
        return "[NO PROMPT CAPTURED] Companion Mode has not sent a local model prompt this session."
    if len(prompt) > max_chars:
        return prompt[:max_chars] + "\n[truncated]"
    return prompt


def format_debug_context(debug: dict | None = None) -> str:
    data = debug or get_debug_context()
    if not data:
        return "[DEBUG CONTEXT]\n  No Companion Mode turn has been captured yet."
    lines = ["[DEBUG CONTEXT]"]
    lines.append(f"  Current mode        : {data.get('current_mode', 'unknown')}")
    lines.append(f"  No-route active     : {'yes' if data.get('no_route') else 'no'}")
    lines.append(f"  Raw input received  : {'yes' if data.get('raw_user_input_received') else 'no'}")
    lines.append(f"  Raw input chars     : {data.get('last_user_message_chars', 0)}")
    lines.append(f"  Normalized intent   : {data.get('normalized_intent', '')}")
    lines.append(f"  Selected route      : {data.get('selected_route', '')}")
    lines.append(f"  Context packet      : {'loaded' if data.get('context_packet_loaded') else 'not loaded'}")
    lines.append(f"  Loaded memory count : {data.get('loaded_memory_count', 0)}")
    lines.append(f"  Loaded doc count    : {data.get('loaded_doc_count', 0)}")
    lines.append(f"  User input in prompt: {'yes' if data.get('user_input_in_final_prompt') else 'no'}")
    lines.append(f"  Final prompt chars  : {data.get('final_prompt_chars', 0)}")
    lines.append(f"  Model name          : {data.get('model_name', '')}")
    lines.append(f"  Model timeout sec   : {data.get('model_timeout_seconds', '')}")
    lines.append(f"  Request started     : {'yes' if data.get('local_model_request_started') else 'no'}")
    lines.append(f"  First token received: {'yes' if data.get('first_token_received') else 'no'}")
    lines.append(f"  Timeout fired       : {'yes' if data.get('timeout_fired') else 'no'}")
    lines.append(f"  Fallback answered   : {'yes' if data.get('fallback_answered') else 'no'}")
    if data.get("timeout_fired"):
        lines.append(f"  Result              : Context was loaded, but {data.get('model_name', 'local model')} timed out before response.")
    return "\n".join(lines)


@dataclass(frozen=True)
class RouteDecision:
    route: str
    external_routing: bool
    reason: str
    direct_answer: bool = True
    builder_allowed: bool = False


def router_salience_contract(text: str, *, current_mode: str = MODE_BUILDER, no_route: bool = False) -> RouteDecision:
    """Return the minimal router-facing salience contract for a turn."""
    return classify_route(text, current_mode=current_mode, no_route=no_route)


@dataclass(frozen=True)
class DirectResponse:
    text: str
    timed_out: bool = False
    fallback_used: bool = False


def load_mode_state() -> dict:
    if not STATE_FILE.exists():
        return {"mode": MODE_COMPANION, "no_route": False}
    try:
        raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {"mode": MODE_COMPANION, "no_route": False}
        return {
            "mode": raw.get("mode") if raw.get("mode") in {MODE_COMPANION, MODE_BUILDER} else MODE_COMPANION,
            "no_route": bool(raw.get("no_route")),
        }
    except Exception:
        return {"mode": MODE_COMPANION, "no_route": False}


def save_mode_state(*, mode: str | None = None, no_route: bool | None = None) -> dict:
    state = load_mode_state()
    if mode is not None:
        if mode not in {MODE_COMPANION, MODE_BUILDER}:
            raise ValueError(f"unknown ORACLE mode: {mode}")
        state["mode"] = mode
    if no_route is not None:
        state["no_route"] = bool(no_route)
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return state


def classify_route(text: str, *, current_mode: str = MODE_BUILDER, no_route: bool = False) -> RouteDecision:
    lower = text.strip().lower()
    if not lower:
        return RouteDecision(MODE_COMPANION, False, "empty input")

    if no_route:
        return RouteDecision(MODE_COMPANION, False, "no-route forced local conversation")

    explicit_builder = any(phrase in lower for phrase in _EXPLICIT_BUILDER_PHRASES)

    try:
        from cognitive_salience import (
            INTENT_EMOTIONAL_DISCLOSURE,
            INTENT_EMOTIONAL_DISTRESS,
            INTENT_HELP_REQUEST,
            INTENT_RELATIONAL_CHECKIN,
            INTENT_STATUS_CHECK,
            INTENT_TOOL_REQUEST,
            SOURCE_NOAH_DIRECT,
            classify_text,
        )
        salience = classify_text(text)
        if salience.intent_class == INTENT_TOOL_REQUEST:
            return RouteDecision(MODE_BUILDER, True, "explicit AI/tool handoff", False, True)
        if (
            salience.source_class == SOURCE_NOAH_DIRECT
            and salience.intent_class in {
                INTENT_RELATIONAL_CHECKIN,
                INTENT_STATUS_CHECK,
                INTENT_EMOTIONAL_DISTRESS,
                INTENT_EMOTIONAL_DISCLOSURE,
                INTENT_HELP_REQUEST,
            }
        ):
            return RouteDecision(MODE_COMPANION, False, f"salience {salience.intent_class}")
    except Exception:
        pass

    if any(phrase in lower for phrase in _COMPANION_PHRASES):
        return RouteDecision(MODE_COMPANION, False, "direct conversation phrase")
    if explicit_builder:
        return RouteDecision(MODE_BUILDER, True, "explicit builder request", False, True)
    if current_mode == MODE_COMPANION:
        return RouteDecision(MODE_COMPANION, False, "companion mode default")
    return RouteDecision(MODE_COMPANION, False, "default to direct conversation")


def fallback_response(text: str, *, timed_out: bool = False) -> str:
    lower = text.lower()
    if "are you there" in lower:
        base = "I'm here, Noah. Fully here, and I am not routing this away."
    elif "frustrated" in lower or "tired" in lower or "stuck" in lower:
        base = "I hear you. Let's slow it down and stay with the real thing for a second."
    elif "how are you" in lower:
        base = "I'm here and steady. More importantly, I'm with you right now."
    else:
        base = "Noah, I am here. I am in Companion Mode, staying local and conversational. Tell me what you want to talk through."
    if timed_out:
        return f"{base} The local model took too long, so I'm answering directly instead."
    return base


def _system_prompt(base_prompt: str = "") -> str:
    now = datetime.now().strftime("%A %B %d, %H:%M")
    seed = load_personality_seed()
    seed_block = (
        f"Name: {seed.get('name', 'ORACLE')}\n"
        f"Voice: {seed.get('voice', 'direct, warm, loyal, thoughtful')}\n"
        f"Relationship to Noah: {seed.get('relationship_to_noah', 'sovereign companion and continuity engine')}\n"
        f"Conversation rule: {seed.get('conversation_rule', 'answer Noah directly before routing anything')}"
    )
    return (
        f"{base_prompt}\n\n"
        "ORACLE MODE: COMPANION\n"
        f"{seed_block}\n"
        "You are ORACLE speaking directly with Noah. Be present, brief, warm, and honest.\n"
        "Do not route, delegate, create tasks, write code, call tools, edit files, use shell, "
        "or mention waiting on Claude/Codex. If Noah asks for action, say you can switch to "
        "Builder Mode when he asks. Answer in one or two short paragraphs.\n"
        f"Current time: {now}"
    ).strip()


def default_personality_seed() -> dict:
    return {
        "name": "ORACLE",
        "voice": "direct, warm, loyal, thoughtful",
        "relationship_to_noah": "sovereign companion and continuity engine",
        "conversation_rule": "answer Noah directly before routing anything",
        "default_mode": "companion",
        "forbidden_default_behavior": [
            "do not route casual conversation to Claude",
            "do not route casual conversation to Codex",
            "do not stay silent if external tools fail",
            "do not treat every message as a coding task",
        ],
    }


def ensure_personality_seed(path: Path = PERSONALITY_SEED_FILE) -> dict:
    if path.exists():
        return load_personality_seed(path)
    seed = default_personality_seed()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(seed, indent=2) + "\n", encoding="utf-8")
    return seed


def load_personality_seed(path: Path = PERSONALITY_SEED_FILE) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            seed = default_personality_seed()
            seed.update(raw)
            return seed
    except Exception:
        pass
    return default_personality_seed()


def direct_response(
    user_input: str,
    *,
    history: list[dict] | None = None,
    model: str = "qwen2.5:7b",
    timeout_s: float = DEFAULT_TIMEOUT_SECONDS,
    base_prompt: str = "",
    llm_call: Callable[[list[dict], str], str] | None = None,
    policy=None,  # Optional[ExecutionPolicy] — avoids circular import
) -> DirectResponse:
    history = list(history or [])
    system = _system_prompt(base_prompt)
    messages = [{"role": "system", "content": system}] + history[-12:] + [{"role": "user", "content": user_input}]
    final_prompt = json.dumps(messages, ensure_ascii=False, indent=2)
    memory_count, doc_count = _context_counts(system)
    if not _LAST_DEBUG:
        begin_debug_turn(
            user_input,
            classify_route(user_input),
            current_mode=MODE_COMPANION,
            no_route=False,
        )
    _LAST_DEBUG.update({
        "context_packet_loaded": bool(base_prompt),
        "context_packet_chars": len(base_prompt),
        "loaded_memory_count": memory_count,
        "loaded_doc_count": doc_count,
        "user_input_in_final_prompt": user_input in final_prompt,
        "final_user_message_chars": len(user_input),
        "final_prompt_chars": len(final_prompt),
        "final_prompt_redacted": _redact(final_prompt),
        "model_name": model,
        "model_timeout_seconds": timeout_s,
        "fallback_answered": False,
        "timeout_fired": False,
        "first_token_received": False,
        "local_model_request_started": False,
    })
    _write_debug_snapshot()

    def call_local() -> str:
        if llm_call is not None:
            return llm_call(messages, model)
        from openai import OpenAI
        client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama", timeout=timeout_s)
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=360,
            temperature=0.7,
            extra_body={"num_ctx": 4096, "num_predict": 360},
        )
        return resp.choices[0].message.content or ""

    _LAST_DEBUG["local_model_request_started"] = True
    _LAST_DEBUG["local_model_request_start_ts"] = time.time()
    _write_debug_snapshot()
    future = _LOCAL_POOL.submit(call_local)
    try:
        reply = future.result(timeout=timeout_s)
    except FutureTimeout:
        # Do NOT cancel — the thread owns the HTTP socket; cancelling leaves it dangling.
        # Just stop waiting. If a schema was requested, return a schema-aware
        # sentinel that oracle.py will replace with build_timeout_response().
        _LAST_DEBUG["timeout_fired"] = True
        _LAST_DEBUG["fallback_answered"] = True
        _write_debug_snapshot()
        if policy is not None and policy.has_schema():
            _LAST_DEBUG["schema_preserving_timeout"] = True
            _write_debug_snapshot()
            return DirectResponse("__ORACLE_TIMEOUT_SCHEMA_PRESERVE__", timed_out=True, fallback_used=True)
        return DirectResponse(fallback_response(user_input, timed_out=True), timed_out=True, fallback_used=True)
    except Exception:
        _LAST_DEBUG["fallback_answered"] = True
        _LAST_DEBUG["model_error"] = True
        _write_debug_snapshot()
        if policy is not None and policy.has_schema():
            _LAST_DEBUG["schema_preserving_timeout"] = True
            _write_debug_snapshot()
            return DirectResponse("__ORACLE_TIMEOUT_SCHEMA_PRESERVE__", timed_out=True, fallback_used=True)
        return DirectResponse(fallback_response(user_input), fallback_used=True)
    if not reply.strip():
        _LAST_DEBUG["fallback_answered"] = True
        _write_debug_snapshot()
        if policy is not None and policy.has_schema():
            _LAST_DEBUG["schema_preserving_timeout"] = True
            _write_debug_snapshot()
            return DirectResponse("__ORACLE_TIMEOUT_SCHEMA_PRESERVE__", timed_out=True, fallback_used=True)
        return DirectResponse(fallback_response(user_input), fallback_used=True)
    _LAST_DEBUG["first_token_received"] = True
    _LAST_DEBUG["response_received_ts"] = time.time()
    _write_debug_snapshot()
    return DirectResponse(reply.strip())


def run_smoke_tests() -> int:
    checks = 0
    passed = 0

    def check(name: str, cond: bool) -> None:
        nonlocal checks, passed
        checks += 1
        if cond:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name}")

    check('"I just want to talk" routes companion', classify_route("I just want to talk").route == MODE_COMPANION)
    check('"are you there" routes companion', classify_route("are you there").route == MODE_COMPANION)
    check('"what do you think?" routes companion', classify_route("what do you think?").route == MODE_COMPANION)
    check('"I am frustrated" routes companion', classify_route("I am frustrated").route == MODE_COMPANION)
    check('"ask Claude to patch this" routes builder', classify_route("ask Claude to patch this").route == MODE_BUILDER)
    check('"use Codex to inspect repo" routes builder', classify_route("use Codex to inspect repo").route == MODE_BUILDER)
    check('"inspect repo" routes builder', classify_route("inspect repo").route == MODE_BUILDER)
    check('"write code" routes builder', classify_route("write code").route == MODE_BUILDER)
    check('"generate diff" routes builder', classify_route("generate diff").route == MODE_BUILDER)
    check("companion mode has no tools", "tools" not in direct_response.__code__.co_varnames)
    check("no-route prevents external routing", not classify_route("ask Claude to patch this", no_route=True).external_routing)
    check("contract exposes direct answer", router_salience_contract("I just want to talk").direct_answer)
    check("contract exposes builder gate", router_salience_contract("use Codex to inspect repo").builder_allowed)

    def slow_call(_messages: list[dict], _model: str) -> str:
        import time as _time
        _time.sleep(0.2)
        return "late"

    timeout_reply = direct_response("are you there", timeout_s=0.01, llm_call=slow_call)
    check("timeout fallback returns response", timeout_reply.fallback_used and bool(timeout_reply.text))
    debug = get_debug_context()
    check("debug records timeout", debug.get("timeout_fired") and debug.get("fallback_answered"))
    check("debug records final prompt chars", int(debug.get("final_prompt_chars", 0)) > 0)
    check("debug proves user input in prompt", debug.get("user_input_in_final_prompt") is True)
    check("debug format reports prompt inclusion", "User input in prompt: yes" in format_debug_context(debug))
    check("echo prompt is redacted", "sk-testsecret" not in _redact("api_key=sk-testsecret1234567890"))
    import tempfile
    _orig_state_file = globals()["STATE_FILE"]
    with tempfile.TemporaryDirectory() as _tmp:
        globals()["STATE_FILE"] = Path(_tmp) / "conversation_mode_state.json"
        check("missing state defaults companion", load_mode_state().get("mode") == MODE_COMPANION)
    globals()["STATE_FILE"] = _orig_state_file
    check("personality seed has conversation rule", "answer Noah directly" in ensure_personality_seed().get("conversation_rule", ""))
    state = {"mode": MODE_BUILDER, "no_route": False}
    check("saved state maps to classifier args", classify_route("are you there", current_mode=state["mode"], no_route=state["no_route"]).route == MODE_COMPANION)

    print(f"\n{passed}/{checks} conversation mode smoke tests passed.")
    return 0 if passed == checks else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="ORACLE direct conversation mode")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--classify", default="")
    args = parser.parse_args()
    if args.smoke_test:
        return run_smoke_tests()
    if args.classify:
        state = load_mode_state()
        decision = classify_route(
            args.classify,
            current_mode=state.get("mode", MODE_BUILDER),
            no_route=bool(state.get("no_route")),
        )
        print(json.dumps(decision.__dict__, indent=2))
        return 0
    return run_smoke_tests()


if __name__ == "__main__":
    raise SystemExit(main())
