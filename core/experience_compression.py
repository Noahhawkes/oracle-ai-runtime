"""
core/experience_compression.py — ORACLE Experience Compression Layer

Every significant action — success or failure — becomes a structured experience:

    Observation : what happened
    Cause       : why it happened
    Outcome     : what resulted (success / failure / partial)
    Lesson      : what to do differently or repeat
    Confidence  : how certain ORACLE is about the lesson (0.0–1.0)

Experiences are more valuable than events.
Lessons are more valuable than logs.

Usage:
    from experience_compression import record, recall_lessons, lesson_block

    # After a tool call
    record(
        observation="Claude routing failed",
        cause="CLI unavailable — shutil.which('claude') returned None",
        outcome=OUTCOME_FAILURE,
        lesson="Verify tool availability before delegation",
        confidence=0.9,
        domain="routing",
        tags=["claude", "routing", "cli"],
    )

    # Before a new attempt
    lessons = recall_lessons("routing to claude", top_k=3)
    for l in lessons:
        print(l.lesson, l.confidence)

    # Inject into system prompt
    block = lesson_block(query="send task to claude")
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Paths ──────────────────────────────────────────────────────────────────────
import sys
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "core"))

MEMORY_DIR      = ROOT / "Memory"
EXPERIENCE_FILE = MEMORY_DIR / "experiences.json"
MEMORY_DIR.mkdir(exist_ok=True)

# ── Outcome constants ──────────────────────────────────────────────────────────
OUTCOME_SUCCESS  = "success"
OUTCOME_FAILURE  = "failure"
OUTCOME_PARTIAL  = "partial"
OUTCOME_BLOCKED  = "blocked"
OUTCOME_UNKNOWN  = "unknown"

ALL_OUTCOMES = [OUTCOME_SUCCESS, OUTCOME_FAILURE, OUTCOME_PARTIAL, OUTCOME_BLOCKED, OUTCOME_UNKNOWN]

# ── Domain constants ───────────────────────────────────────────────────────────
DOMAIN_ROUTING    = "routing"
DOMAIN_ACTUATION  = "actuation"
DOMAIN_MEMORY     = "memory"
DOMAIN_TOOLS      = "tools"
DOMAIN_GOVERNANCE = "governance"
DOMAIN_BUILD      = "build"
DOMAIN_CHANNEL    = "channel"
DOMAIN_VOICE      = "voice"
DOMAIN_GENERAL    = "general"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Data model ─────────────────────────────────────────────────────────────────

@dataclass
class Experience:
    id:          str   = field(default_factory=lambda: uuid.uuid4().hex[:10])
    observation: str   = ""      # what happened
    cause:       str   = ""      # why it happened
    outcome:     str   = OUTCOME_UNKNOWN
    lesson:      str   = ""      # what to do differently or repeat
    confidence:  float = 0.5     # 0.0 = guess, 1.0 = certain

    domain:      str   = DOMAIN_GENERAL
    tags:        list  = field(default_factory=list)
    recurrence:  int   = 1       # how many times this experience has repeated

    created_at:  str   = field(default_factory=_now)
    updated_at:  str   = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "observation": self.observation,
            "cause":       self.cause,
            "outcome":     self.outcome,
            "lesson":      self.lesson,
            "confidence":  round(self.confidence, 3),
            "domain":      self.domain,
            "tags":        self.tags,
            "recurrence":  self.recurrence,
            "created_at":  self.created_at,
            "updated_at":  self.updated_at,
        }

    @staticmethod
    def from_dict(d: dict) -> "Experience":
        e = Experience()
        for k, v in d.items():
            if hasattr(e, k):
                setattr(e, k, v)
        return e

    def summary(self) -> str:
        icon = {"success": "✓", "failure": "✗", "partial": "~",
                "blocked": "⊘", "unknown": "?"}.get(self.outcome, "?")
        return (
            f"[{self.domain.upper():10}] {icon} "
            f"conf={self.confidence:.1f}  {self.lesson[:80]}"
        )

    def as_prompt_block(self) -> str:
        """Single experience formatted for system prompt injection."""
        lines = [
            f"  Observation : {self.observation[:100]}",
            f"  Cause       : {self.cause[:100]}",
            f"  Outcome     : {self.outcome}",
            f"  Lesson      : {self.lesson[:120]}",
            f"  Confidence  : {self.confidence:.0%}",
        ]
        if self.recurrence > 1:
            lines.append(f"  Recurrence  : {self.recurrence}x — this lesson is validated")
        return "\n".join(lines)


# ── Persistence ────────────────────────────────────────────────────────────────

def _load() -> list[Experience]:
    try:
        raw = json.loads(EXPERIENCE_FILE.read_text(encoding="utf-8"))
        return [Experience.from_dict(d) for d in raw if isinstance(d, dict)]
    except Exception:
        return []


def _save(experiences: list[Experience]) -> None:
    EXPERIENCE_FILE.write_text(
        json.dumps([e.to_dict() for e in experiences], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ── Similarity ─────────────────────────────────────────────────────────────────

def _similar(a: str, b: str, threshold: float = 0.55) -> bool:
    wa = set(a.lower().split())
    wb = set(b.lower().split())
    if not wa or not wb:
        return False
    return len(wa & wb) / min(len(wa), len(wb)) >= threshold


# ── Public API ─────────────────────────────────────────────────────────────────

def record(
    observation: str,
    cause:       str,
    outcome:     str,
    lesson:      str,
    confidence:  float = 0.5,
    domain:      str   = DOMAIN_GENERAL,
    tags:        Optional[list] = None,
) -> Experience:
    """
    Record a new experience. If a similar lesson already exists in the same
    domain, increment recurrence and boost confidence instead of duplicating.
    """
    experiences = _load()

    # Check for existing similar lesson in same domain
    for ex in experiences:
        if ex.domain == domain and _similar(ex.lesson, lesson):
            ex.recurrence += 1
            # Boost confidence toward certainty with each recurrence
            ex.confidence  = min(1.0, ex.confidence + (1 - ex.confidence) * 0.2)
            ex.updated_at  = _now()
            # Update observation/cause to most recent
            ex.observation = observation[:300]
            ex.cause       = cause[:300]
            _save(experiences)
            return ex

    exp = Experience(
        observation = observation[:300],
        cause       = cause[:300],
        outcome     = outcome,
        lesson      = lesson[:300],
        confidence  = max(0.0, min(1.0, confidence)),
        domain      = domain,
        tags        = tags or [],
    )
    experiences.append(exp)
    _save(experiences)
    return exp


def recall_lessons(
    query:   str,
    domain:  Optional[str] = None,
    top_k:   int = 5,
    min_conf: float = 0.0,
) -> list[Experience]:
    """
    Return the most relevant experiences for a given query.
    Ranks by: query relevance + confidence + recurrence.
    """
    experiences = _load()
    if domain:
        experiences = [e for e in experiences if e.domain == domain]
    if min_conf > 0:
        experiences = [e for e in experiences if e.confidence >= min_conf]

    if not experiences:
        return []

    query_lower = query.lower()

    def _rank(e: Experience) -> float:
        combined = f"{e.observation} {e.lesson} {e.cause}".lower()
        q_words  = set(query_lower.split())
        e_words  = set(combined.split())
        overlap  = len(q_words & e_words) / max(len(q_words), 1)
        recur_boost = min(0.2, (e.recurrence - 1) * 0.05)
        return overlap * 0.5 + e.confidence * 0.3 + recur_boost

    return sorted(experiences, key=_rank, reverse=True)[:top_k]


def lesson_block(query: str = "", max_chars: int = 700) -> str:
    """
    Build a compact lesson block for system prompt injection.
    Only includes high-confidence, relevant experiences.
    Failure lessons come first — they prevent repeated mistakes.
    """
    # Failures first, then successes
    failures = recall_lessons(query, top_k=3, min_conf=0.5)
    failures = [e for e in failures if e.outcome in (OUTCOME_FAILURE, OUTCOME_BLOCKED)]
    successes = recall_lessons(query, top_k=2, min_conf=0.6)
    successes = [e for e in successes if e.outcome == OUTCOME_SUCCESS]

    all_exp = failures + [e for e in successes if e not in failures]
    if not all_exp:
        return ""

    lines = ["[ORACLE LESSONS — from experience]"]
    total = 0
    for e in all_exp:
        block = e.as_prompt_block()
        total += len(block)
        if total > max_chars:
            break
        lines.append("")
        lines.append(block)
    lines.append("")
    return "\n".join(lines)


def record_tool_result(
    tool_name:   str,
    input_summary: str,
    success:     bool,
    result:      str,
    extra_cause: str = "",
) -> Experience:
    """
    Convenience wrapper — called automatically after every tool execution.
    Generates observation/cause/lesson from tool name + result.
    """
    outcome = OUTCOME_SUCCESS if success else OUTCOME_FAILURE

    if success:
        observation = f"{tool_name} succeeded: {input_summary[:80]}"
        cause       = "Tool executed normally"
        lesson      = f"{tool_name} works when called with: {input_summary[:60]}"
        confidence  = 0.7
    else:
        observation = f"{tool_name} failed: {input_summary[:80]}"
        cause       = extra_cause or f"{result[:120]}"
        lesson      = _generate_failure_lesson(tool_name, result)
        confidence  = 0.6

    domain = _tool_to_domain(tool_name)

    return record(
        observation = observation,
        cause       = cause,
        outcome     = outcome,
        lesson      = lesson,
        confidence  = confidence,
        domain      = domain,
        tags        = [tool_name],
    )


def _tool_to_domain(tool_name: str) -> str:
    mapping = {
        "send_to_claude_code": DOMAIN_ROUTING,
        "type_into_window":    DOMAIN_ACTUATION,
        "inject_via_keyboard": DOMAIN_ACTUATION,
        "find_window":         DOMAIN_ACTUATION,
        "find_control":        DOMAIN_ACTUATION,
        "run_shell":           DOMAIN_TOOLS,
        "terminal_run":        DOMAIN_TOOLS,
        "write_file":          DOMAIN_TOOLS,
        "read_file":           DOMAIN_TOOLS,
        "remember_fact":       DOMAIN_MEMORY,
        "recall_facts":        DOMAIN_MEMORY,
        "speak":               DOMAIN_VOICE,
    }
    for key, domain in mapping.items():
        if key in tool_name.lower():
            return domain
    return DOMAIN_GENERAL


def _generate_failure_lesson(tool_name: str, result: str) -> str:
    result_lower = result.lower()

    if "not found" in result_lower and "window" in result_lower:
        return f"Verify target window is open before calling {tool_name}"
    if "not found" in result_lower and "control" in result_lower:
        return f"Edit control absent in this app — use keyboard clipboard fallback"
    if "cli not found" in result_lower or "which" in result_lower:
        return "Verify CLI is on PATH before attempting CLI-based routing"
    if "timeout" in result_lower:
        return f"{tool_name} timed out — check if target is responsive before calling"
    if "permission" in result_lower or "access denied" in result_lower:
        return f"{tool_name} requires elevated permissions or Noah approval"
    if "import" in result_lower or "module" in result_lower:
        return f"Dependency missing for {tool_name} — check requirements"

    return f"When {tool_name} fails with '{result[:60]}', investigate before retrying"


def list_experiences(
    domain:  Optional[str] = None,
    outcome: Optional[str] = None,
    limit:   int = 20,
) -> list[Experience]:
    all_e = _load()
    if domain:
        all_e = [e for e in all_e if e.domain == domain]
    if outcome:
        all_e = [e for e in all_e if e.outcome == outcome]
    return sorted(all_e, key=lambda e: e.confidence * e.recurrence, reverse=True)[:limit]


def purge_old(older_than_days: int = 90) -> int:
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    experiences = _load()
    before = len(experiences)
    kept = []
    for e in experiences:
        # Always keep high-confidence, frequently-recurring lessons
        if e.confidence >= 0.8 or e.recurrence >= 3:
            kept.append(e)
            continue
        try:
            ts = datetime.fromisoformat(e.updated_at)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                kept.append(e)
        except Exception:
            kept.append(e)
    _save(kept)
    return before - len(kept)


# ── Pre-seed with ORACLE's known lessons from this session ────────────────────

def seed_known_lessons():
    """
    Seed the experience store with operational lessons already learned.
    Safe to call multiple times — recurrence deduplication prevents noise.
    """
    known = [
        dict(
            observation="Claude Desktop actuation failed at find_control",
            cause="Claude Desktop is an Electron/webview app — no Edit UIA control exposed",
            outcome=OUTCOME_FAILURE,
            lesson="For Electron apps, skip find_control and use keyboard clipboard fallback directly",
            confidence=0.95,
            domain=DOMAIN_ACTUATION,
            tags=["claude", "electron", "uia", "actuation"],
        ),
        dict(
            observation="qwen responded 'routing to claude code' without calling any tool",
            cause="Local 7B model hallucinates action phrases when it cannot call tools",
            outcome=OUTCOME_FAILURE,
            lesson="Block 'routing to claude code' as a phrase; use _QWEN_ROUTING_HALLUCINATION re-route",
            confidence=0.90,
            domain=DOMAIN_ROUTING,
            tags=["qwen", "hallucination", "routing"],
        ),
        dict(
            observation="Short user inputs like 'approve' were classified as CHAT mode",
            cause="Word-count fallback defaulted <=5 words to CHAT",
            outcome=OUTCOME_FAILURE,
            lesson="Default unmatched input to WORK, not CHAT. CHAT requires explicit conversational trigger.",
            confidence=0.90,
            domain=DOMAIN_ROUTING,
            tags=["mode_classifier", "chat", "work"],
        ),
        dict(
            observation="Spaces were stripped from text injected into Claude Desktop",
            cause="pyautogui.hotkey ctrl+v sent to foreground window, not Claude's handle",
            outcome=OUTCOME_FAILURE,
            lesson="Use pywinauto raw.type_keys('^v') to target window handle directly, not foreground",
            confidence=0.95,
            domain=DOMAIN_ACTUATION,
            tags=["pywinauto", "clipboard", "spaces"],
        ),
        dict(
            observation="Channel echo loop: ORACLE displayed Claude response then qwen re-processed it",
            cause="Missing 'continue' after channel response display in REPL loop",
            outcome=OUTCOME_FAILURE,
            lesson="Always add 'continue' after consuming channel response to prevent qwen re-processing",
            confidence=0.95,
            domain=DOMAIN_CHANNEL,
            tags=["channel", "echo_loop", "continue"],
        ),
        dict(
            observation="'tell Claude X' / 'with claude' / broad phrases routed everything to Claude Desktop",
            cause="_CLAUDE_DIRECT_PATTERNS was too broad — matched normal conversation",
            outcome=OUTCOME_FAILURE,
            lesson="Keep _CLAUDE_DIRECT_PATTERNS tight: only 'tell claude to', 'ask claude to', 'send to claude code'",
            confidence=0.90,
            domain=DOMAIN_ROUTING,
            tags=["routing", "claude_bridge", "over_routing"],
        ),
        dict(
            observation="ORACLE successfully sent task to Claude Code via keyboard fallback",
            cause="pyperclip + pywinauto type_keys('^v') targeted window handle directly",
            outcome=OUTCOME_SUCCESS,
            lesson="Keyboard clipboard fallback works for Electron apps when pyperclip is installed",
            confidence=0.85,
            domain=DOMAIN_ACTUATION,
            tags=["actuation", "success", "clipboard"],
        ),
        dict(
            observation="list_active() prevents dead action candidates from resurfacing",
            cause="Used list_candidates() which returns all statuses including rejected/revoked",
            outcome=OUTCOME_SUCCESS,
            lesson="Always use list_active() for approval/actuation feeds — never list_candidates()",
            confidence=0.90,
            domain=DOMAIN_GOVERNANCE,
            tags=["action_candidates", "list_active"],
        ),
    ]

    for lesson_data in known:
        record(**lesson_data)


# ── Smoke tests ────────────────────────────────────────────────────────────────

def _smoke_test() -> int:
    import tempfile
    orig = EXPERIENCE_FILE
    tmp = Path(tempfile.mktemp(suffix=".json"))

    import experience_compression as ec
    ec.EXPERIENCE_FILE = tmp

    failures = 0

    def check(label, passed, detail=""):
        nonlocal failures
        tag = "PASS" if passed else "FAIL"
        print(f"  [{tag}] {label}")
        if not passed and detail:
            print(f"         {detail}")
        if not passed:
            failures += 1

    print("=" * 55)
    print("Experience Compression — Smoke Tests")
    print("=" * 55)

    # 1. Record a failure
    e = ec.record(
        observation="Claude routing failed",
        cause="CLI unavailable",
        outcome=ec.OUTCOME_FAILURE,
        lesson="Verify tool availability before delegation",
        confidence=0.9,
        domain=ec.DOMAIN_ROUTING,
    )
    check("record() returns Experience", isinstance(e, ec.Experience))
    check("outcome stored", e.outcome == ec.OUTCOME_FAILURE)
    check("confidence stored", e.confidence == 0.9)
    check("domain stored", e.domain == ec.DOMAIN_ROUTING)

    # 2. Record a success
    e2 = ec.record(
        observation="Keyboard fallback injected text into Claude Desktop",
        cause="pyperclip + pywinauto type_keys worked",
        outcome=ec.OUTCOME_SUCCESS,
        lesson="Keyboard clipboard fallback works for Electron apps",
        confidence=0.85,
        domain=ec.DOMAIN_ACTUATION,
    )
    check("success experience stored", e2.outcome == ec.OUTCOME_SUCCESS)

    # 3. Recurrence deduplication
    e_dup = ec.record(
        observation="Claude routing failed again",
        cause="CLI still unavailable",
        outcome=ec.OUTCOME_FAILURE,
        lesson="Verify tool availability before delegation",  # same lesson
        confidence=0.7,
        domain=ec.DOMAIN_ROUTING,
    )
    check("duplicate lesson increments recurrence", e_dup.recurrence == 2, f"got {e_dup.recurrence}")
    check("confidence boosted on recurrence", e_dup.confidence > 0.9)
    check("id unchanged on dedup", e_dup.id == e.id)

    # 4. recall_lessons finds relevant
    hits = ec.recall_lessons("routing to claude", top_k=3)
    check("recall_lessons returns results", len(hits) > 0)
    check("recall_lessons finds routing lesson", any("tool availability" in h.lesson for h in hits))

    # 5. Domain filter
    actuation_hits = ec.recall_lessons("", domain=ec.DOMAIN_ACTUATION, top_k=5)
    check("domain filter works", all(h.domain == ec.DOMAIN_ACTUATION for h in actuation_hits))

    # 6. lesson_block builds correct structure
    block = ec.lesson_block("routing")
    check("lesson_block non-empty", bool(block))
    check("lesson_block has LESSONS header", "[ORACLE LESSONS" in block)
    check("lesson_block contains Lesson field", "Lesson" in block)

    # 7. record_tool_result convenience
    e3 = ec.record_tool_result("find_control", "window=Claude control=Edit", False, "control not found")
    check("record_tool_result stores failure", e3.outcome == ec.OUTCOME_FAILURE)
    check("record_tool_result generates lesson", "control" in e3.lesson.lower() or "fallback" in e3.lesson.lower())

    # 8. list_experiences
    all_e = ec.list_experiences()
    check("list_experiences returns list", isinstance(all_e, list))
    check("list_experiences includes stored experiences", len(all_e) >= 3)

    # 9. Experience.summary()
    s = e.summary()
    check("summary non-empty", bool(s))
    check("summary contains domain", "ROUTING" in s)

    # 10. as_prompt_block
    pb = e.as_prompt_block()
    check("as_prompt_block has Observation", "Observation" in pb)
    check("as_prompt_block has Lesson", "Lesson" in pb)
    check("as_prompt_block has Confidence", "Confidence" in pb)

    # Cleanup
    ec.EXPERIENCE_FILE = orig
    try:
        tmp.unlink()
    except Exception:
        pass

    total = 20
    passed = total - failures
    print(f"{'='*55}")
    print(f"Result: {passed}/{total} passed")
    print(f"STATUS: {'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    print(f"{'='*55}\n")
    return failures


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="ORACLE Experience Compression")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--seed", action="store_true", help="Seed known lessons from this session")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--domain", default=None)
    parser.add_argument("--recall", metavar="QUERY")
    args = parser.parse_args()

    if args.smoke_test:
        sys.exit(_smoke_test())
    elif args.seed:
        seed_known_lessons()
        print(f"Seeded known lessons into {EXPERIENCE_FILE}")
        for e in list_experiences(limit=30):
            print(f"  {e.summary()}")
    elif args.list:
        for e in list_experiences(domain=args.domain):
            print(f"  {e.summary()}")
    elif args.recall:
        hits = recall_lessons(args.recall, top_k=5)
        print(f"\nLessons for: {args.recall!r}\n")
        for h in hits:
            print(f"  {h.as_prompt_block()}")
            print()
