"""
RAISE-HAND PROTOCOL v0.1 - Oracle's outbound communication channel.

Doctrine (51/49):
    Oracle may ask; only Noah decides. Every outbound request must arrive
    decision-ready: context, options, recommendation, citation. A question
    asked twice is a nag, so ask-once is enforced structurally. Quiet hours
    outrank her need to speak (return-to-life rule), CRITICAL excepted.
    Outbound is communication-only: toasts and tray badges. Never actuation,
    never external sends. Everything she asks is witnessed in the ledger.

CLI:
    python raise_hand.py --smoke-test
    python raise_hand.py --raise '<json>'
    python raise_hand.py --list
    python raise_hand.py --ack <request_id> --by Noah --decision "approve"
    python raise_hand.py --morning-report
    python raise_hand.py --tray

No external dependencies. Toast dispatch is dry-run unless
ORACLE_TOASTS_ENABLED=1 and platform is Windows (BurntToast via PowerShell).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, time as dtime, timedelta
from pathlib import Path
from typing import Optional

TIERS = ("CRITICAL", "BLOCKED", "MORNING", "AMBIENT")

REQUEST_TYPES = (
    "APPROVAL_PENDING",
    "BLOCKED_ON_DECISION",
    "CONTRADICTION_FLAGGED",
    "HEALTH_ALERT",
    "PROPOSAL",
)

QUIET_START = dtime(21, 0)
QUIET_END = dtime(7, 0)
DAILY_TOAST_BUDGET = 5
DECISION_READY_FIELDS = ("context", "options", "recommendation", "citation")

DEFAULT_STATE_DIR = Path(os.environ.get("ORACLE_STATE_DIR", "./state"))


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".tmp.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class CorruptQueueError(RuntimeError):
    """Queue file exists but cannot be parsed. Loud failure, never silent."""


@dataclass
class Request:
    request_key: str
    request_type: str
    tier: str
    context: str
    options: list
    recommendation: str
    citation: str
    payload: dict = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: str = ""
    status: str = "OPEN"
    toasted: bool = False
    demoted_from: str = ""
    acked_by: str = ""
    decision: str = ""
    acked_at: str = ""

    def validate(self) -> list[str]:
        """Decision-ready enforcement. Returns problems; empty means valid."""
        problems: list[str] = []
        if self.tier not in TIERS:
            problems.append(f"unknown tier: {self.tier!r}")
        if self.request_type not in REQUEST_TYPES:
            problems.append(f"unknown request_type: {self.request_type!r}")
        for field_name in DECISION_READY_FIELDS:
            val = getattr(self, field_name, None)
            if field_name == "options":
                if not isinstance(val, list) or len(val) < 2:
                    problems.append("options must list at least 2 explicit choices")
            elif not (isinstance(val, str) and val.strip()):
                problems.append(f"missing decision-ready field: {field_name}")
        if not self.request_key.strip():
            problems.append("missing request_key (stable dedup key)")
        return problems


class ToastDispatcher:
    """Local notification only; dry-run by default."""

    def __init__(self, enabled: Optional[bool] = None):
        if enabled is None:
            enabled = os.environ.get("ORACLE_TOASTS_ENABLED") == "1" and sys.platform == "win32"
        self.enabled = enabled
        self.sent: list[dict[str, object]] = []

    def toast(self, title: str, body: str) -> bool:
        self.sent.append({"title": title, "body": body, "live": self.enabled})
        if not self.enabled:
            print(f"[DRY-RUN TOAST] {title}: {body}")
            return False
        ps = (
            "Import-Module BurntToast; "
            f"New-BurntToastNotification -Text '{_ps_escape(title)}', "
            f"'{_ps_escape(body)}'"
        )
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                check=True,
                capture_output=True,
                timeout=15,
            )
            return True
        except Exception as exc:
            print(f"[TOAST FAILED - queued anyway] {exc}", file=sys.stderr)
            return False


def _ps_escape(text: str) -> str:
    return text.replace("'", "''")


class RaiseHandQueue:
    def __init__(
        self,
        state_dir: Path = DEFAULT_STATE_DIR,
        dispatcher: Optional[ToastDispatcher] = None,
        now_fn=None,
    ):
        self.state_dir = Path(state_dir)
        self.queue_path = self.state_dir / "raise_hand_queue.json"
        self.ledger_path = self.state_dir / "raise_hand_ledger.jsonl"
        self.dispatcher = dispatcher or ToastDispatcher()
        self._now_fn = now_fn or datetime.now
        self._data = self._load()

    def _load(self) -> dict:
        if not self.queue_path.exists():
            return {"requests": [], "toast_budget": {}}
        raw = self.queue_path.read_text(encoding="utf-8")
        try:
            data = json.loads(raw)
            if not isinstance(data.get("requests"), list):
                raise ValueError("requests must be a list")
            if not isinstance(data.get("toast_budget", {}), dict):
                raise ValueError("toast_budget must be a dict")
            data.setdefault("toast_budget", {})
            return data
        except Exception as exc:
            backup = self.queue_path.with_suffix(".corrupt")
            self.queue_path.replace(backup)
            raise CorruptQueueError(
                f"Queue unreadable ({exc}). Backed up to {backup}. "
                "Refusing to start with silent empty state."
            ) from exc

    def _save(self) -> None:
        _atomic_write_text(self.queue_path, json.dumps(self._data, indent=2))

    def _ledger(self, event: str, request: Request, extra: Optional[dict] = None) -> None:
        entry = {
            "ts": self._now().isoformat(timespec="seconds"),
            "event": event,
            "request_id": request.request_id,
            "request_key": request.request_key,
            "tier": request.tier,
            "type": request.request_type,
        }
        if extra:
            entry.update(extra)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def _now(self) -> datetime:
        return self._now_fn()

    def _in_quiet_hours(self, now: Optional[datetime] = None) -> bool:
        t = (now or self._now()).time()
        return t >= QUIET_START or t < QUIET_END

    def _toasts_today(self, now: Optional[datetime] = None) -> int:
        key = (now or self._now()).date().isoformat()
        return int(self._data.get("toast_budget", {}).get(key, 0))

    def _spend_toast(self, now: Optional[datetime] = None) -> None:
        stamp = now or self._now()
        key = stamp.date().isoformat()
        budget = self._data.setdefault("toast_budget", {})
        budget[key] = int(budget.get(key, 0)) + 1
        keep = {key, (stamp.date() - timedelta(days=1)).isoformat()}
        for existing_key in list(budget):
            if existing_key not in keep:
                del budget[existing_key]

    def raise_request(self, req: Request) -> dict:
        """Oracle raises her hand. Returns what happened."""
        problems = req.validate()
        if problems:
            return {"accepted": False, "reason": "NOT_DECISION_READY", "problems": problems}

        for existing in self._data["requests"]:
            if existing["request_key"] == req.request_key and existing["status"] == "OPEN":
                self._ledger("SUPPRESSED_DUPLICATE", req, {"open_request_id": existing["request_id"]})
                return {
                    "accepted": False,
                    "reason": "DUPLICATE_OPEN",
                    "open_request_id": existing["request_id"],
                }

        now = self._now()
        req.created_at = now.isoformat(timespec="seconds")

        toast_allowed = req.tier in ("CRITICAL", "BLOCKED")
        if toast_allowed and req.tier != "CRITICAL" and self._in_quiet_hours(now):
            toast_allowed = False

        if toast_allowed and req.tier != "CRITICAL" and self._toasts_today(now) >= DAILY_TOAST_BUDGET:
            req.demoted_from = req.tier
            req.tier = "AMBIENT"
            toast_allowed = False

        if toast_allowed:
            self.dispatcher.toast(
                f"Oracle [{req.tier}] {req.request_type}",
                f"{req.context} - Rec: {req.recommendation}",
            )
            req.toasted = True
            if req.tier != "CRITICAL":
                self._spend_toast(now)

        self._data["requests"].append(asdict(req))
        self._save()
        self._ledger("RAISED", req, {"toasted": req.toasted, "demoted_from": req.demoted_from})
        return {
            "accepted": True,
            "request_id": req.request_id,
            "tier": req.tier,
            "toasted": req.toasted,
            "demoted_from": req.demoted_from,
        }

    def ack(self, request_id: str, by: str, decision: str) -> dict:
        for existing in self._data["requests"]:
            if existing["request_id"] == request_id and existing["status"] == "OPEN":
                existing["status"] = "ACKED"
                existing["acked_by"] = by
                existing["decision"] = decision
                existing["acked_at"] = self._now().isoformat(timespec="seconds")
                self._save()
                req = Request(**existing)
                self._ledger("ACKED", req, {"by": by, "decision": decision})
                return {"acked": True, "request_id": request_id}
        return {"acked": False, "reason": "NOT_FOUND_OR_NOT_OPEN"}

    def open_requests(self) -> list[dict]:
        return [r for r in self._data["requests"] if r["status"] == "OPEN"]

    def tray_badge(self) -> int:
        return len(self.open_requests())

    def morning_report(self) -> dict:
        open_reqs = self.open_requests()
        by_tier = {tier: [] for tier in TIERS}
        for req in open_reqs:
            by_tier[req["tier"]].append(req)
        return {
            "generated_at": self._now().isoformat(timespec="seconds"),
            "open_total": len(open_reqs),
            "critical": by_tier["CRITICAL"],
            "blocked": by_tier["BLOCKED"],
            "morning": by_tier["MORNING"],
            "ambient": by_tier["AMBIENT"],
            "proposals": [r for r in open_reqs if r["request_type"] == "PROPOSAL"],
        }


def _mk_req(**overrides) -> Request:
    base = {
        "request_key": "blocked:state-dir-decision",
        "request_type": "BLOCKED_ON_DECISION",
        "tier": "BLOCKED",
        "context": "Sleep cycle flagged runtime state still writing to G: drive.",
        "options": ["approve C:\\Oracle\\state", "keep G:", "discuss"],
        "recommendation": "Move to C:\\ per the sync-corruption decision (6/08).",
        "citation": "ledger:2026-06-08#state-dir",
    }
    base.update(overrides)
    return Request(**base)


def smoke_test() -> int:
    import shutil

    tmp = Path(tempfile.mkdtemp(prefix="raise_hand_test_"))
    passed = 0
    failed = 0

    def check(name: str, cond: bool) -> None:
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  PASS  {name}")
        else:
            failed += 1
            print(f"  FAIL  {name}")

    day = datetime(2026, 6, 10, 14, 0)
    night = datetime(2026, 6, 10, 23, 0)

    q = RaiseHandQueue(tmp / "t1", ToastDispatcher(enabled=False), lambda: day)
    r = q.raise_request(_mk_req(recommendation=""))
    check("incomplete request rejected (NOT_DECISION_READY)", not r["accepted"] and r["reason"] == "NOT_DECISION_READY")

    r = q.raise_request(_mk_req(options=["approve"]))
    check("single-option request rejected", not r["accepted"])

    r = q.raise_request(_mk_req())
    check("valid BLOCKED accepted + toasted (daytime)", r["accepted"] and r["toasted"])

    r2 = q.raise_request(_mk_req())
    check("duplicate OPEN request suppressed (ask-once)", not r2["accepted"] and r2["reason"] == "DUPLICATE_OPEN")

    qn = RaiseHandQueue(tmp / "t5", ToastDispatcher(enabled=False), lambda: night)
    r = qn.raise_request(_mk_req(request_key="blocked:night"))
    check("BLOCKED at 23:00 queued without toast", r["accepted"] and not r["toasted"])

    r = qn.raise_request(_mk_req(
        request_key="critical:checksum",
        tier="CRITICAL",
        request_type="HEALTH_ALERT",
        context="Kernel checksum mismatch on boot self-test.",
    ))
    check("CRITICAL at 23:00 still toasts", r["accepted"] and r["toasted"])

    qb = RaiseHandQueue(tmp / "t7", ToastDispatcher(enabled=False), lambda: day)
    for i in range(DAILY_TOAST_BUDGET):
        qb.raise_request(_mk_req(request_key=f"blocked:n{i}"))
    r = qb.raise_request(_mk_req(request_key="blocked:overflow"))
    check(
        "toast budget exhausted -> demoted to AMBIENT, no toast",
        r["accepted"] and r["tier"] == "AMBIENT" and r["demoted_from"] == "BLOCKED" and not r["toasted"],
    )

    r = qb.raise_request(_mk_req(request_key="critical:exempt", tier="CRITICAL", request_type="HEALTH_ALERT"))
    check("CRITICAL exempt from interrupt budget", r["accepted"] and r["toasted"])

    tmp_residue = list((tmp / "t7").glob("*.tmp.*"))
    parsed = json.loads((tmp / "t7" / "raise_hand_queue.json").read_text())
    check("atomic write (no temp residue, valid JSON)", not tmp_residue and isinstance(parsed["requests"], list))

    rid = q.open_requests()[0]["request_id"]
    acked = q.ack(rid, by="Noah", decision="approve C:\\")
    ledger_lines = (tmp / "t1" / "raise_hand_ledger.jsonl").read_text().splitlines()
    acked_logged = any(json.loads(line)["event"] == "ACKED" for line in ledger_lines)
    check("ack closes request and is witnessed in ledger", acked["acked"] and acked_logged)

    r = q.raise_request(_mk_req())
    check("re-raise allowed after ack (question answered, new question ok)", r["accepted"])

    qp = RaiseHandQueue(tmp / "t12", ToastDispatcher(enabled=False), lambda: day)
    r = qp.raise_request(_mk_req(
        request_key="proposal:sleep-stage2",
        request_type="PROPOSAL",
        tier="MORNING",
        context="REM pass suggests pruning thresholds need a config file.",
        payload={"mission": "BUILD PASS: pruning config", "tests": ["threshold load", "demotion fires"]},
    ))
    report = qp.morning_report()
    check(
        "PROPOSAL queued to morning report with payload",
        r["accepted"]
        and len(report["proposals"]) == 1
        and report["proposals"][0]["payload"]["mission"].startswith("BUILD PASS"),
    )

    check("MORNING tier did not toast", not r["toasted"])

    bad_dir = tmp / "t14"
    bad_dir.mkdir(parents=True)
    (bad_dir / "raise_hand_queue.json").write_text("{not json", encoding="utf-8")
    loud = False
    try:
        RaiseHandQueue(bad_dir, ToastDispatcher(enabled=False), lambda: day)
    except CorruptQueueError:
        loud = (bad_dir / "raise_hand_queue.corrupt").exists()
    check("corrupt queue -> loud refusal + .corrupt backup", loud)

    check("tray badge reflects open requests", qp.tray_badge() == 1)

    r = q.raise_request(_mk_req(request_key="x:bad", tier="URGENT"))
    check("unknown tier rejected", not r["accepted"])

    r = q.raise_request(_mk_req(request_key="x:bad2", request_type="DEMAND"))
    check("unknown request_type rejected", not r["accepted"])

    dispatcher = ToastDispatcher()
    live = dispatcher.toast("t", "b")
    check("dispatcher dry-run by default (communication-only, no live send)", live is False and dispatcher.sent[0]["live"] is False)

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{passed}/{passed + failed} passed")
    return 0 if failed == 0 else 1


def main(argv: list[str]) -> int:
    if "--smoke-test" in argv:
        return smoke_test()

    q = RaiseHandQueue()

    if "--raise" in argv:
        payload = json.loads(argv[argv.index("--raise") + 1])
        result = q.raise_request(Request(**payload))
        print(json.dumps(result, indent=2))
        return 0 if result.get("accepted") else 1

    if "--list" in argv:
        print(json.dumps(q.open_requests(), indent=2))
        return 0

    if "--ack" in argv:
        rid = argv[argv.index("--ack") + 1]
        by = argv[argv.index("--by") + 1] if "--by" in argv else "Noah"
        decision = argv[argv.index("--decision") + 1] if "--decision" in argv else ""
        print(json.dumps(q.ack(rid, by, decision), indent=2))
        return 0

    if "--morning-report" in argv:
        print(json.dumps(q.morning_report(), indent=2))
        return 0

    if "--tray" in argv:
        print(q.tray_badge())
        return 0

    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
