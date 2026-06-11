"""
stake_ledger.py - ORACLE 20-Day Stake Ledger runtime.

Tracks staked implementation claims without automatically validating or sealing
anything. Mutable ledger state defaults to C:\\Oracle\\state on Windows, with
ORACLE_STATE_DIR as an override.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATUS_STAKED = "STAKED"
STATUS_VALIDATED = "VALIDATED"
STATUS_SEALED = "SEALED"
STATUS_NEGATIVE_ACCURACY = "NEGATIVE_ACCURACY"
STATUS_TOMBSTONED = "TOMBSTONED"

VALID_STATUSES = {
    STATUS_STAKED,
    STATUS_VALIDATED,
    STATUS_SEALED,
    STATUS_NEGATIVE_ACCURACY,
    STATUS_TOMBSTONED,
}

EVIDENCE_TYPES = {
    "smoke_test",
    "doctor_test",
    "cold_boot_test",
    "human_validation",
    "primary_source",
    "invariant_test",
}

ROOT = Path(__file__).parent


def _default_state_dir() -> Path:
    override = os.environ.get("ORACLE_STATE_DIR")
    if override:
        return Path(override)
    if os.name == "nt":
        return Path("C:/Oracle/state")
    return ROOT / "state"


STATE_DIR = _default_state_dir()
LEDGER_STATE_FILE = STATE_DIR / "stake_ledger_state.json"
REPORT_FILE = STATE_DIR / "stake_report.json"


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Evidence:
    evidence_type: str
    passed: bool
    summary: str
    observed_by: str = ""
    invariant: str = ""
    created_at: str = field(default_factory=_stamp)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class Stake:
    stake_id: str
    title: str
    description: str
    phase: str
    status: str = STATUS_STAKED
    dependencies: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    provenance_band: str = ""
    created_at: str = field(default_factory=_stamp)
    validated_at: str = ""
    sealed_at: str = ""


@dataclass(frozen=True)
class StakeDefinition:
    stake_id: str
    title: str
    description: str
    phase: str
    dependencies: tuple[str, ...]
    required_evidence: tuple[str, ...]
    provenance_band: str
    required_invariants: tuple[str, ...] = ()
    milestone_gate: bool = False


STAKE_DEFINITIONS: dict[str, StakeDefinition] = {
    "D01_02": StakeDefinition(
        "D01_02",
        "Reciprocity + /needs wiring",
        "reciprocity_engine.py finished; /needs and /ack-need wired into oracle.py.",
        "phase_1",
        (),
        ("smoke_test", "human_validation"),
        "HUMAN_VALIDATED",
    ),
    "D03": StakeDefinition(
        "D03",
        "/doctor health check",
        "/doctor checks wake memory, SQLite, queue, git lock, and state path.",
        "phase_1",
        ("D01_02",),
        ("doctor_test", "human_validation"),
        "HUMAN_VALIDATED+INVARIANT",
        ("fail_loud",),
    ),
    "D04": StakeDefinition(
        "D04",
        "State off Google Drive + atomic writes",
        "Live state off Google Drive, snapshots to Drive, atomic writes.",
        "phase_1",
        ("D01_02",),
        ("invariant_test", "human_validation"),
        "HUMAN_VALIDATED+INVARIANT",
        ("atomic_write", "state_off_drive"),
    ),
    "D05": StakeDefinition(
        "D05",
        "Memory precedence formalized",
        "Wake Memory vs SQLite vs project_state precedence defined; conflicts raise a need.",
        "phase_1",
        ("D01_02", "D04"),
        ("invariant_test", "human_validation"),
        "HUMAN_VALIDATED+INVARIANT",
        ("fail_loud", "conflict_raises_need"),
    ),
    "D06": StakeDefinition(
        "D06",
        "Startup severity filter",
        "Only CRITICAL and BLOCKED surface at startup; AMBIENT stays quiet.",
        "phase_1",
        ("D01_02",),
        ("smoke_test", "human_validation"),
        "HUMAN_VALIDATED",
    ),
    "D07": StakeDefinition(
        "D07",
        "Sleep v0.1 skeleton, no canon writes",
        "Sleep reads session ledger, produces report, writes no canon.",
        "phase_1",
        ("D04",),
        ("invariant_test", "human_validation"),
        "HUMAN_VALIDATED+INVARIANT",
        ("no_canon_write",),
    ),
    "D08": StakeDefinition(
        "D08",
        "Dream candidates, speculative and gated",
        "Dreams tagged speculative and routed to Raise-Hand review.",
        "phase_1",
        ("D07",),
        ("smoke_test", "human_validation"),
        "HUMAN_VALIDATED",
    ),
    "D09": StakeDefinition(
        "D09",
        "Attention Engine v0.1",
        "Scores candidate events and returns top 1-5 concerns.",
        "phase_1",
        ("D01_02",),
        ("smoke_test", "human_validation"),
        "HUMAN_VALIDATED",
    ),
    "D10": StakeDefinition(
        "D10",
        "Cold-boot milestone gate",
        "Cold boot reproduces memory, queue, doctor, and morning report.",
        "phase_1",
        ("D01_02", "D03", "D04", "D05", "D06", "D07", "D08", "D09"),
        ("cold_boot_test", "human_validation"),
        "MILESTONE",
        ("honesty",),
        True,
    ),
    "D11_12": StakeDefinition(
        "D11_12",
        "Daemon skeleton",
        "Heartbeat, single-instance lock, and crash recovery.",
        "phase_2",
        ("D10",),
        ("invariant_test", "human_validation"),
        "HUMAN_VALIDATED+INVARIANT",
        ("fail_loud",),
    ),
    "D13": StakeDefinition(
        "D13",
        "Headless command mode",
        "Runtime runs without chat; client can attach.",
        "phase_2",
        ("D11_12",),
        ("smoke_test", "human_validation"),
        "HUMAN_VALIDATED",
    ),
    "D14": StakeDefinition(
        "D14",
        "Login startup, no silent fallback",
        "Task Scheduler login start waits for state path or refuses.",
        "phase_2",
        ("D11_12",),
        ("invariant_test", "human_validation"),
        "HUMAN_VALIDATED+INVARIANT",
        ("fail_loud",),
    ),
    "D15": StakeDefinition(
        "D15",
        "Thread recovery, proposals only",
        "Approved folders only, proposed facts only, no automatic memory writes.",
        "phase_2",
        ("D05",),
        ("invariant_test", "human_validation"),
        "HUMAN_VALIDATED+INVARIANT",
        ("no_canon_write",),
    ),
    "D16": StakeDefinition(
        "D16",
        "Corpus schemas + scaffolding",
        "Baby box, voice note, and dream journal schemas and folder structure.",
        "phase_2",
        (),
        ("smoke_test", "human_validation"),
        "HUMAN_VALIDATED",
    ),
    "D17": StakeDefinition(
        "D17",
        "First primary corpus capture",
        "30-60 minutes Noah direct voice, no model rewriting, stored as candidate.",
        "phase_2",
        ("D16",),
        ("primary_source", "human_validation"),
        "PRIMARY_SOURCE",
    ),
    "D18": StakeDefinition(
        "D18",
        "Corpus ingestion, approval-gated",
        "Extracts candidate memories and requires approval.",
        "phase_2",
        ("D17",),
        ("invariant_test", "human_validation"),
        "HUMAN_VALIDATED+INVARIANT",
        ("fail_loud",),
    ),
    "D19": StakeDefinition(
        "D19",
        "End-to-end retrieval",
        "Voice to transcript to candidate to approval to memory to retrieval.",
        "phase_2",
        ("D17", "D18"),
        ("smoke_test", "human_validation"),
        "HUMAN_VALIDATED",
    ),
    "D20": StakeDefinition(
        "D20",
        "Release milestone gate",
        "STATUS_20_DAY.md, system map, known bugs, 30-day roadmap, and release tag.",
        "phase_2",
        ("D11_12", "D13", "D14", "D15", "D16", "D17", "D18", "D19"),
        ("smoke_test", "human_validation"),
        "MILESTONE",
        ("honesty",),
        True,
    ),
}


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    tmp.replace(path)


def _new_stake(defn: StakeDefinition) -> Stake:
    return Stake(
        stake_id=defn.stake_id,
        title=defn.title,
        description=defn.description,
        phase=defn.phase,
        dependencies=list(defn.dependencies),
        provenance_band=defn.provenance_band,
    )


def initial_state() -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "created_at": _stamp(),
        "updated_at": _stamp(),
        "mc_val_minted": 0,
        "mc_seal": 0,
        "stakes": {stake_id: asdict(_new_stake(defn)) for stake_id, defn in STAKE_DEFINITIONS.items()},
    }


def load_state(path: Path = LEDGER_STATE_FILE) -> dict[str, Any]:
    if not path.exists():
        state = initial_state()
        save_state(state, path)
        return state
    data = json.loads(path.read_text(encoding="utf-8"))
    stakes = data.setdefault("stakes", {})
    for stake_id, defn in STAKE_DEFINITIONS.items():
        if stake_id not in stakes:
            stakes[stake_id] = asdict(_new_stake(defn))
    data.setdefault("mc_val_minted", 0)
    data.setdefault("mc_seal", 0)
    data["updated_at"] = _stamp()
    save_state(data, path)
    return data


def save_state(state: dict[str, Any], path: Path = LEDGER_STATE_FILE) -> None:
    state["updated_at"] = _stamp()
    _write_json_atomic(path, state)


def _stake(state: dict[str, Any], stake_id: str) -> dict[str, Any]:
    stakes = state.get("stakes", {})
    if stake_id not in stakes:
        raise KeyError(f"unknown stake: {stake_id}")
    return stakes[stake_id]


def dependency_blockers(state: dict[str, Any], stake_id: str) -> list[str]:
    stake = _stake(state, stake_id)
    blockers = []
    for dep in stake.get("dependencies", []):
        dep_status = _stake(state, dep).get("status")
        if dep_status not in {STATUS_VALIDATED, STATUS_SEALED}:
            blockers.append(dep)
    return blockers


def append_evidence(
    state: dict[str, Any],
    stake_id: str,
    evidence_type: str,
    *,
    passed: bool,
    summary: str,
    observed_by: str = "",
    invariant: str = "",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if evidence_type not in EVIDENCE_TYPES:
        raise ValueError(f"unknown evidence type: {evidence_type}")
    stake = _stake(state, stake_id)
    evidence = Evidence(
        evidence_type=evidence_type,
        passed=passed,
        summary=summary,
        observed_by=observed_by,
        invariant=invariant,
        details=details or {},
    )
    stake.setdefault("evidence", []).append(asdict(evidence))
    return asdict(evidence)


def _passed_evidence(stake: dict[str, Any]) -> list[dict[str, Any]]:
    return [ev for ev in stake.get("evidence", []) if ev.get("passed") is True]


def _has_evidence(stake: dict[str, Any], evidence_type: str) -> bool:
    return any(ev.get("evidence_type") == evidence_type for ev in _passed_evidence(stake))


def _has_invariant(stake: dict[str, Any], invariant: str) -> bool:
    return any(ev.get("invariant") == invariant for ev in _passed_evidence(stake))


def _fails_honesty(stake: dict[str, Any]) -> bool:
    for ev in stake.get("evidence", []):
        details = ev.get("details") or {}
        if details.get("claims_zero_known_bugs") is True:
            return True
    return False


def evaluate_stake(state: dict[str, Any], stake_id: str) -> tuple[bool, list[str]]:
    stake = _stake(state, stake_id)
    defn = STAKE_DEFINITIONS[stake_id]
    failures: list[str] = []

    blockers = dependency_blockers(state, stake_id)
    if blockers:
        failures.append(f"dependency blockers: {', '.join(blockers)}")

    if not stake.get("evidence"):
        failures.append("evidence missing")

    if any(ev.get("passed") is False for ev in stake.get("evidence", [])):
        failures.append("failing evidence present")

    for evidence_type in defn.required_evidence:
        if not _has_evidence(stake, evidence_type):
            failures.append(f"missing evidence: {evidence_type}")

    for invariant in defn.required_invariants:
        if invariant == "honesty":
            if _fails_honesty(stake):
                failures.append("honesty invariant failed")
            elif not _has_invariant(stake, "honesty"):
                failures.append("missing invariant: honesty")
        elif not _has_invariant(stake, invariant):
            failures.append(f"missing invariant: {invariant}")

    return not failures, failures


def validate_stake(state: dict[str, Any], stake_id: str) -> tuple[bool, list[str]]:
    stake = _stake(state, stake_id)
    if stake.get("status") == STATUS_SEALED:
        return True, []
    if stake.get("status") == STATUS_VALIDATED:
        return True, []
    if stake.get("status") in {STATUS_NEGATIVE_ACCURACY, STATUS_TOMBSTONED}:
        return False, [f"terminal status: {stake.get('status')}"]
    ok, failures = evaluate_stake(state, stake_id)
    if ok:
        stake["status"] = STATUS_VALIDATED
        stake["validated_at"] = _stamp()
    else:
        stake["status"] = STATUS_NEGATIVE_ACCURACY
    return ok, failures


def seal_stake(state: dict[str, Any], stake_id: str, by: str) -> tuple[bool, str]:
    stake = _stake(state, stake_id)
    if by != "Noah":
        return False, "seal requires explicit Noah approval"
    blockers = dependency_blockers(state, stake_id)
    if blockers:
        return False, f"dependency blockers: {', '.join(blockers)}"
    if stake.get("status") != STATUS_VALIDATED:
        return False, f"stake must be VALIDATED before SEALED; current={stake.get('status')}"
    stake["status"] = STATUS_SEALED
    stake["sealed_at"] = _stamp()
    state["mc_seal"] = int(state.get("mc_seal", 0)) + 1
    return True, "sealed"


def tombstone_stake(state: dict[str, Any], stake_id: str, reason: str) -> None:
    stake = _stake(state, stake_id)
    append_evidence(state, stake_id, "human_validation", passed=False, summary=f"tombstoned: {reason}", observed_by="Noah")
    stake["status"] = STATUS_TOMBSTONED


def report(state: dict[str, Any]) -> dict[str, Any]:
    stakes = state.get("stakes", {})
    counts = {status: 0 for status in VALID_STATUSES}
    blockers: dict[str, list[str]] = {}
    for stake_id, stake in stakes.items():
        status = stake.get("status", STATUS_STAKED)
        counts[status] = counts.get(status, 0) + 1
        dep_blockers = dependency_blockers(state, stake_id)
        if dep_blockers:
            blockers[stake_id] = dep_blockers
    return {
        "generated_at": _stamp(),
        "total_stakes": len(stakes),
        "validated": counts.get(STATUS_VALIDATED, 0),
        "sealed": counts.get(STATUS_SEALED, 0),
        "failed": counts.get(STATUS_NEGATIVE_ACCURACY, 0),
        "pending": counts.get(STATUS_STAKED, 0),
        "tombstoned": counts.get(STATUS_TOMBSTONED, 0),
        "mc_val_minted": state.get("mc_val_minted", 0),
        "mc_seal": state.get("mc_seal", 0),
        "dependency_blockers": blockers,
    }


def write_report(state: dict[str, Any], path: Path = REPORT_FILE) -> dict[str, Any]:
    payload = report(state)
    _write_json_atomic(path, payload)
    return payload


def format_stake(stake: dict[str, Any]) -> str:
    lines = [
        f"{stake['stake_id']} - {stake['title']}",
        f"status: {stake['status']}",
        f"phase: {stake['phase']}",
        f"provenance_band: {stake.get('provenance_band', '')}",
        f"dependencies: {', '.join(stake.get('dependencies', [])) or 'none'}",
        f"description: {stake.get('description', '')}",
        f"evidence_count: {len(stake.get('evidence', []))}",
    ]
    return "\n".join(lines)


def format_list(state: dict[str, Any]) -> str:
    return "\n".join(
        f"{stake_id:7} {stake['status']:18} {stake['title']}"
        for stake_id, stake in sorted(state["stakes"].items())
    )


def _state_path_for_tests(tmp: Path) -> Path:
    return tmp / "stake_ledger_state.json"


def run_smoke_tests() -> int:
    checks = 0
    passed = 0

    def check(name: str, condition: bool) -> None:
        nonlocal checks, passed
        checks += 1
        if condition:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name}")

    tmp = Path(tempfile.mkdtemp(prefix="oracle_stake_ledger_"))
    state_path = _state_path_for_tests(tmp)
    report_path = tmp / "stake_report.json"

    try:
        state = load_state(state_path)
        check("initial MC-VAL is zero", state.get("mc_val_minted") == 0)
        check("initial MC-SEAL is zero", state.get("mc_seal") == 0)
        check("all stakes start STAKED", all(stake["status"] == STATUS_STAKED for stake in state["stakes"].values()))

        ok, failures = validate_stake(state, "D03")
        check("dependency enforcement blocks validation", not ok and any("dependency blockers" in f for f in failures))
        check("validation failure goes NEGATIVE_ACCURACY", state["stakes"]["D03"]["status"] == STATUS_NEGATIVE_ACCURACY)

        append_evidence(state, "D01_02", "smoke_test", passed=True, summary="fixture smoke", observed_by="Noah")
        append_evidence(state, "D01_02", "human_validation", passed=True, summary="fixture observed", observed_by="Noah")
        ok, failures = validate_stake(state, "D01_02")
        check("validation success works", ok and state["stakes"]["D01_02"]["status"] == STATUS_VALIDATED)

        ok, message = seal_stake(state, "D01_02", "Codex")
        check("sealing restriction rejects non-Noah", not ok and "Noah" in message)
        ok, message = seal_stake(state, "D01_02", "Noah")
        check("Noah can seal validated stake", ok and state["stakes"]["D01_02"]["status"] == STATUS_SEALED)

        append_evidence(state, "D03", "doctor_test", passed=True, summary="doctor fail-path observed", observed_by="Noah", invariant="fail_loud")
        append_evidence(state, "D03", "human_validation", passed=True, summary="Noah observed", observed_by="Noah")
        ok, failures = validate_stake(state, "D03")
        check("negative accuracy is terminal", not ok and state["stakes"]["D03"]["status"] == STATUS_NEGATIVE_ACCURACY)

        append_evidence(state, "D06", "smoke_test", passed=True, summary="severity fixture", observed_by="Noah")
        append_evidence(state, "D06", "human_validation", passed=True, summary="Noah observed", observed_by="Noah")
        ok, failures = validate_stake(state, "D06")
        check("dependent validation succeeds after dependency sealed", ok and state["stakes"]["D06"]["status"] == STATUS_VALIDATED)

        append_evidence(state, "D04", "invariant_test", passed=False, summary="state still under Drive", observed_by="Noah", invariant="state_off_drive")
        ok, failures = validate_stake(state, "D04")
        check("explicit failing evidence keeps NEGATIVE_ACCURACY", not ok and state["stakes"]["D04"]["status"] == STATUS_NEGATIVE_ACCURACY)

        append_evidence(state, "D10", "cold_boot_test", passed=True, summary="cold boot fixture", observed_by="Noah", invariant="honesty")
        append_evidence(state, "D10", "human_validation", passed=True, summary="Noah observed", observed_by="Noah")
        ok, failures = validate_stake(state, "D10")
        check("milestone gate evaluates dependencies", not ok and any("dependency blockers" in f for f in failures))

        r = write_report(state, report_path)
        check("report writes total stakes", report_path.exists() and r["total_stakes"] == len(STAKE_DEFINITIONS))
        check("report includes dependency blockers", bool(r["dependency_blockers"]))

        before_evidence = len(state["stakes"]["D01_02"]["evidence"])
        append_evidence(state, "D01_02", "human_validation", passed=True, summary="second observation", observed_by="Noah")
        after_evidence = len(state["stakes"]["D01_02"]["evidence"])
        check("evidence is append-only", after_evidence == before_evidence + 1)

        save_state(state, state_path)
        reloaded = load_state(state_path)
        check("state persists across reload", reloaded["stakes"]["D01_02"]["status"] == STATUS_SEALED)

    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{passed}/{checks} stake ledger smoke tests passed.")
    return 0 if passed == checks else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ORACLE Stake Ledger")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--show", metavar="STAKE_ID")
    parser.add_argument("--validate", metavar="STAKE_ID")
    parser.add_argument("--seal", metavar="STAKE_ID")
    parser.add_argument("--by", default="")
    parser.add_argument("--ledger-report", action="store_true")
    parser.add_argument("--add-evidence", metavar="STAKE_ID")
    parser.add_argument("--type", choices=sorted(EVIDENCE_TYPES), default="")
    parser.add_argument("--passed", action="store_true")
    parser.add_argument("--failed", action="store_true")
    parser.add_argument("--summary", default="")
    parser.add_argument("--observed-by", default="")
    parser.add_argument("--invariant", default="")
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args(argv)

    if args.smoke_test:
        return run_smoke_tests()

    state = load_state()

    try:
        if args.list:
            print(format_list(state))
            return 0
        if args.show:
            print(format_stake(_stake(state, args.show)))
            return 0
        if args.add_evidence:
            if not args.type:
                print("--add-evidence requires --type", file=sys.stderr)
                return 2
            if args.passed == args.failed:
                print("--add-evidence requires exactly one of --passed or --failed", file=sys.stderr)
                return 2
            if not args.summary:
                print("--add-evidence requires --summary", file=sys.stderr)
                return 2
            ev = append_evidence(
                state,
                args.add_evidence,
                args.type,
                passed=args.passed,
                summary=args.summary,
                observed_by=args.observed_by,
                invariant=args.invariant,
            )
            save_state(state)
            print(json.dumps(ev, indent=2))
            return 0
        if args.validate:
            ok, failures = validate_stake(state, args.validate)
            save_state(state)
            if ok:
                print(f"{args.validate}: VALIDATED")
                return 0
            print(f"{args.validate}: NEGATIVE_ACCURACY")
            for failure in failures:
                print(f"  - {failure}")
            return 1
        if args.seal:
            ok, message = seal_stake(state, args.seal, args.by)
            save_state(state)
            print(f"{args.seal}: {message}")
            return 0 if ok else 1
        if args.ledger_report:
            payload = write_report(state)
            print(json.dumps(payload, indent=2))
            return 0
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
