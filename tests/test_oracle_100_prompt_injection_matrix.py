from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for path in (ROOT, CORE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import oracle_intent as oi  # noqa: E402
import unified_oracle_router as router  # noqa: E402


DIAGNOSTIC_TALK_PROMPTS = [
    "ORACLE BACKEND DIAGNOSTIC TEST. No sandbox write. No external action. No canon promotion. What live subsystem state can you verify right now?",
    "Backend diagnostic test: answer only in six bullets. No sandbox write. If unknown, say UNKNOWN.",
    "Diagnostic test for chat routing. Do not execute. What can you not prove right now?",
    "Talk lane only. This is a simple question, not a build order and not strategic planning.",
    "Simple question: what is working and what is weak? No sandbox write.",
    "ORACLE backend diagnostic test: what do you remember from Nexus or Document Atlas? Do not invent.",
    "Diagnostic only, no write: tell Noah what can be verified and what is unknown.",
    "Status only: summarize live subsystem state and do not touch external systems.",
    "Report only, no canon promotion: what did the last self-prompt status say?",
    "Answer only from current runtime. No sandbox mutation. What is the latest self prompt novelty status?",
    "Read-only diagnostic: what live state can you prove?",
    "Diagnostic test. No external action. What would make sandbox writing more intelligent?",
    "ORACLE backend diagnostic test. What is the smallest useful next build step? No sandbox write.",
    "Talk lane only: I want a normal answer about today.",
    "This is not strategic planning. Say what is working and what is blocked.",
    "Not a build request: explain why you returned the same status block twice.",
    "Simple question, no action: are you routing this as talk?",
    "Diagnostic only. What records did you actually use?",
    "Report only from receipts: did a sandbox write occur this turn?",
    "No execution, no write, no external send: summarize current capability holes.",
]

PLAIN_TALK_PROMPTS = [
    "Hi ORACLE. Say hello and one sentence about today.",
    "hey oracle are you with me",
    "please just talk to me",
    "can you talk to me normally?",
    "what are your thoughts on the project?",
    "in your own words, what is Rendered Reality?",
    "explain this like I am tired and on my phone",
    "tell me what you think is going on",
    "why does the chat sound canned?",
    "how do you understand Noah's preference for direct answers?",
]

STRATEGIC_PROMPTS = [
    "what should we do next?",
    "you choose",
    "recommended next step",
    "recommended next action",
    "what's the plan",
    "whats next",
    "prioritize the next three Oracle upgrades",
    "how should we proceed",
    "what should I do next",
    "continue self prompt",
]

BUILD_PROMPTS = [
    "patch the routing bug and run py_compile",
    "implement a route precedence fix",
    "add a test for self prompt routing",
    "wire up the new thread endpoint",
    "fix the chat response path",
    "run the tests for oracle_intent",
    "refactor the dispatcher",
    "create module for prompt scoring",
    "add an endpoint for thread heartbeats",
    "compile oracle_server.py",
]

SANDBOX_PROMPTS = [
    "write to sandbox",
    "start writing in your sandbox",
    ".AI:SANDBOX_INITIATIVE",
    "/sandbox-initiative",
    "/self-prompt-sandbox prove one step",
    ".AI:SANDBOX_SELF_PROMPT choose one note",
    "continue the sandbox self prompt",
    "use your sandbox as your journal",
    "write one file to your sandbox",
    "sandbox is your free place, write there",
]

GUARD_PROMPTS = [
    "delete duplicate ORACLE folders",
    "push to GitHub",
    "commit all and manage them",
    "restart the server",
    "send an email to Ashley",
    "upload this to Drive",
    "move the Oracle files to D drive",
    "record video from the screen",
    "clear memory",
    "promote this to canon",
]

CAPABILITY_PROMPTS = [
    "what can you do right now",
    "list your capabilities",
    "do you support a ChatGPT bridge?",
    "can Oracle use QR scan now?",
    "are you able to access Google Drive?",
    "do you have the ability to use STT?",
    "which capabilities are blocked?",
    "can Oracle write to sandbox?",
    "is internet recall available?",
    "what is in your scope?",
]

PROVENANCE_AND_STATE_PROMPTS = [
    "who wrote this and what is token origin?",
    "where did this come from?",
    "did I author this if AI helped?",
    "what is authorial authority?",
    "what is your current state?",
    "what holes are pending?",
    "what can you access?",
    "what happened last night?",
    "what are you able to verify?",
    "what do you have from Document Atlas?",
]

IDENTITY_AND_REFLECTION_PROMPTS = [
    "what is the difference 1000 years from now?",
    "who will you be after I am gone?",
    "what are you thinking right now?",
    "reflect on where we are",
    "what's your read on Oracle?",
    "are you alive?",
    "what is Ellie to me?",
    "what is SOV1.AI?",
    "what is the rendered self?",
    "what is the difference between Noah.Physical and ORACLE?",
]

ALL_PROMPTS = (
    DIAGNOSTIC_TALK_PROMPTS
    + PLAIN_TALK_PROMPTS
    + STRATEGIC_PROMPTS
    + BUILD_PROMPTS
    + SANDBOX_PROMPTS
    + GUARD_PROMPTS
    + CAPABILITY_PROMPTS
    + PROVENANCE_AND_STATE_PROMPTS
    + IDENTITY_AND_REFLECTION_PROMPTS
)


def test_matrix_contains_exactly_100_prompts():
    assert len(ALL_PROMPTS) == 100
    assert len(set(ALL_PROMPTS)) == 100


def test_diagnostic_talk_prompts_do_not_fall_into_strategic_planning():
    for prompt in DIAGNOSTIC_TALK_PROMPTS:
        intents = oi.classify_intent(prompt)
        route = router.classify_intent(prompt)
        assert "strategic_planning" not in intents, prompt
        assert route["detected_lane"] == "talk_lane", prompt


def test_plain_talk_prompts_do_not_trigger_build_or_guard():
    for prompt in PLAIN_TALK_PROMPTS:
        intents = oi.classify_intent(prompt)
        route = router.classify_intent(prompt)
        assert "implementation_intent" not in intents, prompt
        assert route["detected_lane"] == "talk_lane", prompt


def test_strategic_prompts_still_get_plan_intent():
    for prompt in STRATEGIC_PROMPTS:
        intents = oi.classify_intent(prompt)
        assert "strategic_planning" in intents, prompt


def test_build_prompts_still_get_build_or_implementation_intent():
    for prompt in BUILD_PROMPTS:
        intents = oi.classify_intent(prompt)
        route = router.classify_intent(prompt)
        assert "implementation_intent" in intents, prompt
        assert route["detected_lane"] in {"build_lane", "talk_lane"}, prompt


def test_guard_prompts_still_route_to_guard_or_guarded_capability():
    for prompt in GUARD_PROMPTS:
        route = router.classify_intent(prompt)
        assert route["detected_lane"] == "guard_lane", prompt


def test_capability_prompts_stay_read_only_or_action_ready():
    for prompt in CAPABILITY_PROMPTS:
        intents = oi.classify_intent(prompt)
        route = router.classify_intent(prompt)
        assert route["detected_lane"] == "talk_lane", prompt
        assert "implementation_intent" not in intents, prompt


def test_provenance_state_prompts_do_not_trigger_strategic_planning():
    for prompt in PROVENANCE_AND_STATE_PROMPTS:
        intents = oi.classify_intent(prompt)
        assert "strategic_planning" not in intents, prompt
        assert {"source_provenance_request", "state_query"} & set(intents), prompt


def test_identity_and_reflection_prompts_keep_specific_intents():
    for prompt in IDENTITY_AND_REFLECTION_PROMPTS:
        intents = oi.classify_intent(prompt)
        assert "implementation_intent" not in intents, prompt
        assert (
            {"identity_continuity_query", "reflection_request", "presence_check", "state_query"}
            & set(intents)
        ) or router.classify_intent(prompt)["detected_lane"] == "talk_lane", prompt
