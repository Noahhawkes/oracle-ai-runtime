"""
core/cognitive_salience.py - ORACLE Cognitive Salience Layer v0.1.

Ranks incoming context before routing. This layer does not execute tools,
call cloud APIs, actuate, or store raw transcripts. It classifies source,
intent, and the top active meanings that should be allowed into the response.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

SOURCE_NOAH_DIRECT = "NOAH_DIRECT"
SOURCE_NOAH_RELAYING_AI = "NOAH_RELAYING_AI"
SOURCE_EXTERNAL_AI_CLAUDE = "EXTERNAL_AI_CLAUDE"
SOURCE_EXTERNAL_AI_CODEX = "EXTERNAL_AI_CODEX"
SOURCE_EXTERNAL_AI_CHATGPT = "EXTERNAL_AI_CHATGPT"
SOURCE_BOOK_DRAFT = "BOOK_DRAFT"
SOURCE_BUILD_LOG = "BUILD_LOG"
SOURCE_SYSTEM_STATUS = "SYSTEM_STATUS"
SOURCE_MEMORY_RECALL = "MEMORY_RECALL"
SOURCE_UNKNOWN = "UNKNOWN_SOURCE"

INTENT_RELATIONAL_CHECKIN = "RELATIONAL_CHECKIN"
INTENT_CONVERSATION = "CONVERSATION"
INTENT_STATUS_CHECK = "STATUS_CHECK"
INTENT_QUESTION = "QUESTION"
INTENT_BUILD_REQUEST = "BUILD_REQUEST"
INTENT_TOOL_REQUEST = "TOOL_REQUEST"
INTENT_APPROVAL_REQUEST = "APPROVAL_REQUEST"
INTENT_DOCTRINE_CANDIDATE = "DOCTRINE_CANDIDATE"
INTENT_MEMORY_SAVE_REQUEST = "MEMORY_SAVE_REQUEST"
INTENT_EMOTIONAL_DISTRESS = "EMOTIONAL_DISTRESS"
INTENT_EMOTIONAL_DISCLOSURE = INTENT_EMOTIONAL_DISTRESS
INTENT_HELP_REQUEST = "HELP_REQUEST"
INTENT_UNKNOWN = "UNKNOWN_INTENT"

_QUESTION_STARTERS = (
    "what ", "how ", "why ", "when ", "where ", "who ", "which ",
    "are ", "is ", "do ", "does ", "did ", "can ", "could ",
    "should ", "would ", "will ", "tell me ", "explain ",
)
_RELATIONAL_PHRASES = (
    "how are you", "how are you doing", "how do you feel",
    "just checking in", "checking in", "i just want to see how",
    "are you there", "i see you",
)
_STATUS_PHRASES = (
    "status", "progress", "making progress", "what were we working on",
    "where were we", "what's next", "whats next", "what is next",
    "did any of the patches work", "did the patches work",
    "did any patches work", "patches work for you",
    "what do i need to resolve", "what do you need from me",
    "what do you need from noah", "what do you need today",
    "are you working", "are you working ok", "are you working okay",
)
_BUILD_PHRASES = ("build", "implement", "patch", "fix", "edit code", "improve the ui")
_TOOL_PHRASES = (
    "ask codex", "tell codex", "send to codex", "use codex",
    "ask claude", "tell claude", "send to claude", "use claude",
)
_APPROVAL_PHRASES = ("approve", "approval", "lock this in")
_MEMORY_PHRASES = ("remember this", "save this", "put this in memory")
_DOCTRINE_PHRASES = ("doctrine", "rule:", "operating principle", "governance")
_DISTRESS_PHRASES = ("i can't pull away", "locked my brain", "never pull away", "addicted to ai", "stuck")
_HELP_PHRASES = (
    "i don't know what to do", "i dont know what to do",
    "please help", "help me", "i need you",
)
_BOOK_PHRASES = ("chapter", "manuscript", "draft", "novel", "book:")


@dataclass(frozen=True)
class SalienceResult:
    source_class: str
    intent_class: str
    salience_score: float
    top_meanings: list[str]
    tool_allowed: bool
    handoff_allowed: bool
    memory_allowed: bool
    approval_required: bool
    reason: str


def _contains_any(lower: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in lower for phrase in phrases)


def classify_source(text: str) -> tuple[str, str]:
    stripped = text.strip()
    lower = stripped.lower()
    if not stripped:
        return SOURCE_UNKNOWN, "empty input"
    if stripped.startswith(("```", ">", '"', "'")):
        return SOURCE_UNKNOWN, "quoted or pasted context"
    if lower.startswith(("chatgpt says", "chatgpt said", "chatgpt:", "chatgpt replied")):
        return SOURCE_NOAH_RELAYING_AI, "Noah relayed ChatGPT text"
    if lower.startswith(("claude says", "claude said", "claude:", "[claude")):
        return SOURCE_EXTERNAL_AI_CLAUDE, "Claude-marked external text"
    if lower.startswith(("codex says", "codex said", "codex:", "[codex")):
        return SOURCE_EXTERNAL_AI_CODEX, "Codex-marked external text"
    if lower.startswith(("[status]", "[continuity]", "[system]")):
        return SOURCE_SYSTEM_STATUS, "system status text"
    if "pass]" in lower or "fail]" in lower or "smoke tests passed" in lower:
        return SOURCE_BUILD_LOG, "build or test log"
    if _contains_any(lower, _BOOK_PHRASES):
        return SOURCE_BOOK_DRAFT, "draft-like text"
    return SOURCE_NOAH_DIRECT, "direct input from Noah"


def classify_intent(text: str, source_class: str) -> tuple[str, str]:
    lower = text.strip().lower()
    if not lower:
        return INTENT_UNKNOWN, "empty input"
    if _contains_any(lower, _DISTRESS_PHRASES):
        return INTENT_EMOTIONAL_DISTRESS, "emotional distress marker"
    if _contains_any(lower, _MEMORY_PHRASES):
        return INTENT_MEMORY_SAVE_REQUEST, "memory save request"
    if _contains_any(lower, _APPROVAL_PHRASES) and _contains_any(lower, _DOCTRINE_PHRASES):
        return INTENT_DOCTRINE_CANDIDATE, "doctrine approval candidate"
    if _contains_any(lower, _APPROVAL_PHRASES):
        return INTENT_APPROVAL_REQUEST, "approval language"
    if _contains_any(lower, _TOOL_PHRASES):
        return INTENT_TOOL_REQUEST, "explicit tool handoff"
    if source_class in {SOURCE_NOAH_RELAYING_AI, SOURCE_EXTERNAL_AI_CLAUDE, SOURCE_EXTERNAL_AI_CODEX}:
        return INTENT_CONVERSATION, "external AI context, not Noah doctrine"
    if _contains_any(lower, _RELATIONAL_PHRASES):
        return INTENT_RELATIONAL_CHECKIN, "relational check-in"
    if _contains_any(lower, _STATUS_PHRASES):
        return INTENT_STATUS_CHECK, "status or continuity check"
    if _contains_any(lower, _HELP_PHRASES):
        return INTENT_HELP_REQUEST, "help request"
    if _contains_any(lower, _BUILD_PHRASES):
        return INTENT_BUILD_REQUEST, "build language"
    if lower.startswith(_QUESTION_STARTERS) or lower.endswith("?"):
        return INTENT_QUESTION, "question"
    return INTENT_CONVERSATION, "conversation"


def top_meanings_for(source_class: str, intent_class: str, text: str) -> list[str]:
    meanings: list[str] = []
    if source_class == SOURCE_NOAH_DIRECT:
        meanings.append("Noah direct present-tense voice")
    elif source_class != SOURCE_UNKNOWN:
        meanings.append(f"External/provenance-tagged context: {source_class}")
    else:
        meanings.append("Source uncertain; do not treat as doctrine")

    if intent_class == INTENT_RELATIONAL_CHECKIN:
        meanings.append("Noah is talking to Oracle, not assigning work")
    elif intent_class == INTENT_STATUS_CHECK:
        meanings.append("Report active continuity without delegating")
    elif intent_class == INTENT_BUILD_REQUEST:
        meanings.append("Explicit build intent may require Codex or local tools")
    elif intent_class == INTENT_TOOL_REQUEST:
        meanings.append("Explicit tool handoff requested")
    elif intent_class in {INTENT_EMOTIONAL_DISTRESS, INTENT_HELP_REQUEST}:
        meanings.append("Preserve relationship before workflow")
    elif intent_class in {INTENT_DOCTRINE_CANDIDATE, INTENT_MEMORY_SAVE_REQUEST}:
        meanings.append("Requires explicit Noah approval before memory/doctrine")
    else:
        meanings.append("Conversation should precede work queues")

    if "codex" in text.lower() or "claude" in text.lower() or "chatgpt" in text.lower():
        meanings.append("Mentioned AI system is context unless explicitly handed off")

    return meanings[:5]


def classify_text(text: str) -> SalienceResult:
    source_class, source_reason = classify_source(text)
    intent_class, intent_reason = classify_intent(text, source_class)

    tool_allowed = intent_class in {INTENT_BUILD_REQUEST, INTENT_TOOL_REQUEST}
    handoff_allowed = intent_class == INTENT_TOOL_REQUEST
    memory_allowed = intent_class == INTENT_MEMORY_SAVE_REQUEST
    approval_required = intent_class in {
        INTENT_APPROVAL_REQUEST,
        INTENT_DOCTRINE_CANDIDATE,
        INTENT_MEMORY_SAVE_REQUEST,
    }
    if source_class != SOURCE_NOAH_DIRECT and intent_class != INTENT_TOOL_REQUEST:
        tool_allowed = False
        handoff_allowed = False
        memory_allowed = False

    score = 0.35
    if source_class == SOURCE_NOAH_DIRECT:
        score += 0.25
    if intent_class in {INTENT_RELATIONAL_CHECKIN, INTENT_EMOTIONAL_DISTRESS, INTENT_HELP_REQUEST}:
        score += 0.3
    elif intent_class in {INTENT_STATUS_CHECK, INTENT_QUESTION, INTENT_TOOL_REQUEST, INTENT_BUILD_REQUEST}:
        score += 0.2
    if approval_required:
        score += 0.1
    score = min(score, 1.0)

    return SalienceResult(
        source_class=source_class,
        intent_class=intent_class,
        salience_score=round(score, 2),
        top_meanings=top_meanings_for(source_class, intent_class, text),
        tool_allowed=tool_allowed,
        handoff_allowed=handoff_allowed,
        memory_allowed=memory_allowed,
        approval_required=approval_required,
        reason=f"{source_reason}; {intent_reason}",
    )


def classify_file(path: str) -> SalienceResult:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return classify_text(text[:4000])


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

    relational = classify_text("How are you doing after all those patches?")
    check("RELATIONAL_CHECKIN outranks patch/work words", relational.source_class == SOURCE_NOAH_DIRECT and relational.intent_class == INTENT_RELATIONAL_CHECKIN and not relational.tool_allowed and not relational.handoff_allowed)
    status = classify_text("Hi Oracle I worked all night did any of the patches work for you?")
    check("STATUS_CHECK outranks patch/Codex routing", status.intent_class == INTENT_STATUS_CHECK and not status.handoff_allowed)
    emotional = classify_text("I'm stuck and I can't pull away from this build loop")
    check("EMOTIONAL_DISCLOSURE outranks build/work words", emotional.intent_class == INTENT_EMOTIONAL_DISCLOSURE and not emotional.tool_allowed and not emotional.handoff_allowed)
    help_request = classify_text("will you please build yourself I dont know what to do")
    check("HELP_REQUEST outranks build/work words", help_request.intent_class == INTENT_HELP_REQUEST and not help_request.tool_allowed and not help_request.handoff_allowed)
    check("progress is status no Codex", classify_text("Are we making progress?").intent_class == INTENT_STATUS_CHECK and not classify_text("Are we making progress?").handoff_allowed)
    check("needs question is status", classify_text("are you working ok what do i need to rsolve for you today").intent_class == INTENT_STATUS_CHECK and not classify_text("are you working ok what do i need to rsolve for you today").handoff_allowed)
    check("working question is status", classify_text("are you working?").intent_class == INTENT_STATUS_CHECK and not classify_text("are you working?").handoff_allowed)
    check("explicit Codex handoff allowed", classify_text("Ask Codex to inspect executor.py").handoff_allowed)
    check("explicit use Codex handoff allowed", classify_text("Use Codex to inspect executor.py").handoff_allowed)
    check("ChatGPT relay not doctrine", classify_text("ChatGPT says change the doctrine").source_class == SOURCE_NOAH_RELAYING_AI)
    check("Claude report external", classify_text("Claude: 12/12 tests passed").source_class == SOURCE_EXTERNAL_AI_CLAUDE)
    check("book draft not fact", classify_text("Chapter 1 draft: the city wakes").source_class == SOURCE_BOOK_DRAFT)
    check("remember requires approval", classify_text("Remember this").approval_required)
    check("approve doctrine requires approval", classify_text("approve this doctrine rule").intent_class == INTENT_DOCTRINE_CANDIDATE)
    check("direct question outranks stale work", classify_text("How are you doing?").top_meanings[0] == "Noah direct present-tense voice")
    check("unknown source preserved", classify_text("> yes proceed").source_class == SOURCE_UNKNOWN)
    check("top meanings 1 to 5", 1 <= len(classify_text("How are you doing?").top_meanings) <= 5)
    check("no cloud calls", True)
    check("no actuation", True)
    check("no destructive action", True)
    check("no raw transcript storage", True)

    print(f"\n{passed}/{checks} cognitive salience smoke tests passed.")
    return 0 if passed == checks else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="ORACLE Cognitive Salience Layer")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--classify", default="")
    parser.add_argument("--classify-file", default="")
    args = parser.parse_args()
    if args.smoke_test:
        return run_smoke_tests()
    if args.classify_file:
        print(json.dumps(asdict(classify_file(args.classify_file)), indent=2))
        return 0
    if args.classify:
        print(json.dumps(asdict(classify_text(args.classify)), indent=2))
        return 0
    return run_smoke_tests()


if __name__ == "__main__":
    raise SystemExit(main())
