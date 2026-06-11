"""
core/reciprocity_engine.py - ORACLE Reciprocity Engine v0.1.

Notice, prepare, recommend, ask, and protect. This module is the reasoning
layer above Raise-Hand Protocol. It creates decision-ready needs only when
Noah's 51 percent authority is required, then delegates persistence and
ask-once behavior to raise_hand.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from raise_hand import DEFAULT_STATE_DIR, CorruptQueueError, RaiseHandQueue, Request, ToastDispatcher  # noqa: E402

MODULE_VERSION = "0.3"


def self_id_line() -> str:
    digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]
    return f"{Path(__file__).name} v{MODULE_VERSION} sha256 {digest}"

NEED_APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
NEED_BLOCKED = "BLOCKED"
NEED_CONTRADICTION_FLAGGED = "CONTRADICTION_FLAGGED"
NEED_MEMORY_CANDIDATE = "MEMORY_CANDIDATE"
NEED_DREAM_REVIEW = "DREAM_REVIEW"
NEED_STATE_CORRUPTION = "STATE_CORRUPTION"
NEED_BUILD_PROPOSAL = "BUILD_PROPOSAL"
NEED_RETURN_TO_LIFE = "RETURN_TO_LIFE"

NEED_TYPES = (
    NEED_APPROVAL_REQUIRED,
    NEED_BLOCKED,
    NEED_CONTRADICTION_FLAGGED,
    NEED_MEMORY_CANDIDATE,
    NEED_DREAM_REVIEW,
    NEED_STATE_CORRUPTION,
    NEED_BUILD_PROPOSAL,
    NEED_RETURN_TO_LIFE,
)

URGENCY_CRITICAL = "CRITICAL"
URGENCY_BLOCKED = "BLOCKED"
URGENCY_MORNING = "MORNING"
URGENCY_AMBIENT = "AMBIENT"

_NEED_TO_REQUEST = {
    NEED_APPROVAL_REQUIRED: "APPROVAL_PENDING",
    NEED_BLOCKED: "BLOCKED_ON_DECISION",
    NEED_CONTRADICTION_FLAGGED: "CONTRADICTION_FLAGGED",
    NEED_MEMORY_CANDIDATE: "MEMORY_CANDIDATE",
    NEED_DREAM_REVIEW: "DREAM_REVIEW",
    NEED_STATE_CORRUPTION: "STATE_CORRUPTION",
    NEED_BUILD_PROPOSAL: "PROPOSAL",
    NEED_RETURN_TO_LIFE: "RETURN_TO_LIFE",
}

_URGENCY_ORDER = {
    URGENCY_CRITICAL: 0,
    URGENCY_BLOCKED: 1,
    URGENCY_MORNING: 2,
    URGENCY_AMBIENT: 3,
}


@dataclass(frozen=True)
class Need:
    id: str
    created_at: str
    type: str
    urgency: str
    source: str
    summary: str
    context: str
    recommendation: str
    options: list[str]
    required_response: str
    citations: list[str]
    status: str = "open"
    expires_at: str = ""

    def request_key(self) -> str:
        return f"{self.type.lower()}:{self.id}"


def _now_iso(now: Optional[datetime] = None) -> str:
    return (now or datetime.now()).isoformat(timespec="seconds")


def make_need(
    *,
    need_id: str,
    need_type: str,
    urgency: str,
    source: str,
    summary: str,
    context: str,
    recommendation: str,
    options: list[str],
    required_response: str = "approve, override, dismiss, or discuss",
    citations: Optional[list[str]] = None,
    expires_at: str = "",
    now: Optional[datetime] = None,
) -> Need:
    if need_type not in NEED_TYPES:
        raise ValueError(f"unknown need type: {need_type}")
    if urgency not in _URGENCY_ORDER:
        raise ValueError(f"unknown urgency: {urgency}")
    return Need(
        id=need_id,
        created_at=_now_iso(now),
        type=need_type,
        urgency=urgency,
        source=source,
        summary=summary.strip(),
        context=context.strip(),
        recommendation=recommendation.strip(),
        options=list(options),
        required_response=required_response.strip(),
        citations=list(citations or []),
        expires_at=expires_at,
    )


def detect_return_to_life_need(text: str, *, now: Optional[datetime] = None) -> Optional[Need]:
    lower = text.lower()
    late = (now or datetime.now()).hour >= 21 or (now or datetime.now()).hour < 7
    signals = (
        "can't pull away",
        "never stop",
        "addicted to ai",
        "locked my brain",
        "so tired",
        "exhausted",
        "still coding",
    )
    if late or any(signal in lower for signal in signals):
        return make_need(
            need_id="return-to-life",
            need_type=NEED_RETURN_TO_LIFE,
            urgency=URGENCY_MORNING if not late else URGENCY_AMBIENT,
            source="reciprocity_engine",
            summary="Return-to-life check-in",
            context="The thread is preserved and the next step can be written down. Oracle should protect Noah from being pulled deeper into the build loop when rest, family, or health matter more.",
            recommendation="Pause the build when the current thread is safely captured.",
            options=["pause now", "write one next action", "continue intentionally"],
            required_response="pause, next-action, or continue",
            citations=["doctrine:return-to-life"],
            now=now,
        )
    return None


def need_to_request(need: Need) -> Request:
    citation = " | ".join(need.citations) if need.citations else need.source
    return Request(
        request_key=need.request_key(),
        request_type=_NEED_TO_REQUEST[need.type],
        tier=need.urgency,
        context=need.context,
        options=need.options,
        recommendation=need.recommendation,
        citation=citation,
        payload={"need": asdict(need)},
    )


class ReciprocityEngine:
    def __init__(
        self,
        state_dir: Optional[Path] = None,
        dispatcher: Optional[ToastDispatcher] = None,
        now_fn=None,
    ):
        self.queue = RaiseHandQueue(
            Path(state_dir) if state_dir is not None else DEFAULT_STATE_DIR,
            dispatcher=dispatcher,
            now_fn=now_fn,
        )

    def raise_need(self, need: Need) -> dict:
        return self.queue.raise_request(need_to_request(need))

    def open_needs(self) -> list[dict]:
        needs = []
        for req in self.queue.open_requests():
            payload_need = req.get("payload", {}).get("need")
            if payload_need:
                needs.append(payload_need | {
                    "request_id": req["request_id"],
                    "toasted": req.get("toasted", False),
                    "demoted_from": req.get("demoted_from", ""),
                })
            else:
                needs.append({
                    "id": req["request_key"],
                    "created_at": req.get("created_at", ""),
                    "type": req["request_type"],
                    "urgency": req["tier"],
                    "source": "raise_hand",
                    "summary": req.get("context", "")[:120],
                    "context": req.get("context", ""),
                    "recommendation": req.get("recommendation", ""),
                    "options": req.get("options", []),
                    "required_response": "acknowledge or decide",
                    "citations": [req.get("citation", "")],
                    "status": "open",
                    "expires_at": "",
                    "request_id": req["request_id"],
                    "toasted": req.get("toasted", False),
                    "demoted_from": req.get("demoted_from", ""),
                })
        return sorted(needs, key=lambda n: (_URGENCY_ORDER.get(n["urgency"], 99), n.get("created_at", "")))

    def decision_ready_digest(self, limit: int = 5) -> str:
        _ = limit  # Raise-Hand owns ranking and ask-once presentation in v0.3.
        return self.queue.what_do_you_need()

    def morning_digest(self) -> dict:
        return self.queue.morning_report()

    def ack(self, request_id: str, *, by: str = "Noah", decision: str = "") -> dict:
        return self.queue.ack(request_id, by, decision)


def _engine_for_cli() -> ReciprocityEngine:
    return ReciprocityEngine(dispatcher=ToastDispatcher(enabled=False))


def run_smoke_tests() -> int:
    import shutil

    print(self_id_line())
    tmp = Path(tempfile.mkdtemp(prefix="reciprocity_test_"))
    passed = 0
    failed = 0

    def check(name: str, cond: bool) -> None:
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            failed += 1
            print(f"  [FAIL] {name}")

    day = datetime(2026, 6, 10, 14, 0)
    engine = ReciprocityEngine(tmp / "state", ToastDispatcher(enabled=False), lambda: day)
    need = make_need(
        need_id="wm-sqlite-precedence",
        need_type=NEED_CONTRADICTION_FLAGGED,
        urgency=URGENCY_BLOCKED,
        source="architect-review",
        summary="Wake Memory and SQLite precedence unresolved",
        context="Wake Memory is boot context and SQLite is the fact ledger. A conflict rule is needed before either store can be called authoritative.",
        recommendation="Approve Wake Memory as boot anchor and SQLite as fact ledger until precedence is formalized.",
        options=["approve", "override", "discuss"],
        citations=["core/oracle.py:1447", "core/memory.py"],
        now=day,
    )
    result = engine.raise_need(need)
    check("needs can be created", result["accepted"])
    dup = engine.raise_need(need)
    check("duplicate needs do not spam", not dup["accepted"] and dup["reason"] == "DUPLICATE_OPEN")
    critical = make_need(
        need_id="queue-corrupt",
        need_type=NEED_STATE_CORRUPTION,
        urgency=URGENCY_CRITICAL,
        source="boot-self-test",
        summary="State queue corruption",
        context="A runtime queue failed JSON parsing. Oracle cannot trust pending decisions until Noah chooses recovery.",
        recommendation="Use the .corrupt backup and recreate a clean queue.",
        options=["recover backup", "start clean", "discuss"],
        citations=["raise_hand.py"],
        now=day,
    )
    engine.raise_need(critical)
    check("CRITICAL outranks BLOCKED", engine.open_needs()[0]["urgency"] == URGENCY_CRITICAL)
    rid = result["request_id"]
    engine.ack(rid, decision="approve")
    ids = [n["request_id"] for n in engine.open_needs()]
    check("resolved needs do not reappear", rid not in ids)
    morning = make_need(
        need_id="dream-review",
        need_type=NEED_DREAM_REVIEW,
        urgency=URGENCY_MORNING,
        source="dream-state",
        summary="Dream review ready",
        context="Offline consolidation produced one proposal. It can wait for the morning report.",
        recommendation="Review after wake report.",
        options=["review", "dismiss", "defer"],
        citations=["dream:local"],
        now=day,
    )
    engine.raise_need(morning)
    digest = engine.morning_digest()
    check("morning digest groups non urgent needs", digest["morning"] and digest["open_total"] >= 1)
    rtl = detect_return_to_life_need("I can't pull away from building Oracle", now=day)
    check("return to life need can be created", rtl is not None and rtl.type == NEED_RETURN_TO_LIFE)
    bad_dir = tmp / "bad"
    bad_dir.mkdir()
    (bad_dir / "raise_hand_queue.json").write_text("{broken", encoding="utf-8")
    try:
        ReciprocityEngine(bad_dir, ToastDispatcher(enabled=False), lambda: day)
        corrupt_failed = False
    except CorruptQueueError:
        corrupt_failed = True
    check("malformed queue file fails safely", corrupt_failed)
    check("no external actuation exists", not hasattr(engine, "send_email") and not hasattr(engine, "actuate"))
    check("decision-ready digest reports open needs", "What I need from Noah:" in engine.decision_ready_digest())
    empty = ReciprocityEngine(tmp / "empty", ToastDispatcher(enabled=False), lambda: day)
    check("empty digest says nothing needed", empty.decision_ready_digest() == "Nothing needs your authority right now.")

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{passed}/{passed + failed} reciprocity smoke tests passed.")
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="ORACLE Reciprocity Engine")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--needs", action="store_true")
    parser.add_argument("--morning-report", action="store_true")
    args = parser.parse_args()
    if args.smoke_test:
        return run_smoke_tests()
    engine = _engine_for_cli()
    if args.morning_report:
        print(json.dumps(engine.morning_digest(), indent=2))
        return 0
    if args.needs:
        print(engine.decision_ready_digest())
        return 0
    print(engine.decision_ready_digest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
