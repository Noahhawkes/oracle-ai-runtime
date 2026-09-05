"""core/context_bus.py — ORACLE Context Bus / Thread-Pass Composer.

Kills the manual clipboard relay. Instead of Noah hand-assembling context from
five tools and copy/pasting between AIs, ORACLE composes ONE canonical,
provenance-tagged context pass from its own live verified state.

Governance (matches HANDS_OFF doctrine):
  - This composes content only. It does NOT auto-send or auto-type into any
    other AI. The human still performs the paste — the keys stay with Noah.
    Reflection channel != authority channel; a composed pass is not consent.
  - Every section is tagged with its basis: RUNTIME_VERIFIED (pulled live from a
    subsystem this turn), CANDIDATE (staged, unapproved), or DOCTRINE (standing
    project law). Nothing simulated is presented as verified.
  - Every subsystem read is defensive: one failing module degrades that line to
    UNKNOWN, it never breaks the pass.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "core"
for _p in (str(ROOT), str(CORE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Standing project doctrine (canon candidates). Basis: DOCTRINE.
DOCTRINE = [
    "Reflection channel is not authority channel.",
    "Semantic context is not system-level execution.",
    "A blueprint is not a receipt.",
    "Code in chat is candidate until written, tested, and hashed.",
    "MindCoin measures verified continuity work, not hype, crypto, or simulated progress.",
    "AI may have hands; the human keeps the keys.",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(fn: Callable[[], Any], default: Any = None) -> tuple[Any, str]:
    """Run a live read defensively. Returns (value, basis) where basis is
    RUNTIME_VERIFIED on success or UNKNOWN on failure."""
    try:
        return fn(), "RUNTIME_VERIFIED"
    except Exception as exc:
        return ({"error": f"{type(exc).__name__}: {exc}"} if default is None else default), "UNKNOWN"


def _capabilities() -> dict[str, int]:
    from capability_broker import discover_capabilities
    sts = discover_capabilities(run_smokes=False)
    return {
        "total": len(sts),
        "verified": sum(1 for s in sts if s.current_status == "verified"),
        "degraded": sum(1 for s in sts if s.current_status == "degraded"),
        "blocked": sum(1 for s in sts if s.current_status == "blocked"),
    }


def _federation() -> dict[str, Any]:
    from federation import status as fed_status
    st = fed_status()
    return {
        "approved_canon": st.get("approved_records"),
        "candidates_staged": st.get("candidate_records_staged"),
        "promotable_now": st.get("promotable_now"),
    }


def _witness() -> dict[str, Any]:
    import witness_artifacts as wa
    return {"witness_receipts": wa.count_drops()}


def _mindcoin() -> dict[str, Any]:
    d = json.loads((ROOT / "Memory" / "mindcoin_ledger.json").read_text(encoding="utf-8"))
    return {
        "approved_points": d.get("approved_points"),
        "pending_points": d.get("pending_points"),
        "verified_total": d.get("total_points"),
    }


def _runtime() -> dict[str, Any]:
    from operational_state import build_operational_state
    s = build_operational_state()
    v = s.get("verified", {})
    return {
        "branch": v.get("branch"),
        "commit": v.get("commit"),
        "runtime_status": (v.get("runtime") or {}).get("runtime_status"),
    }


def _cognition() -> dict[str, Any]:
    from boot_receipt import inspect_cognition
    c = inspect_cognition()
    return {
        "mode": c.get("mode"),
        "model": c.get("verified_model_name") or c.get("model"),
        "network_boundary": c.get("network_boundary"),
    }


def _hands() -> dict[str, Any]:
    import computer_control as cc
    return {"hands_off": cc._hands_off(), "posture": "HANDS_OFF" if cc._hands_off() else "HANDS_MODE"}


def compose(*, channel: str = "all") -> dict[str, Any]:
    """Compose the canonical context pass from live verified state."""
    sections: dict[str, dict[str, Any]] = {}
    for name, fn in (
        ("runtime", _runtime),
        ("cognition", _cognition),
        ("capabilities", _capabilities),
        ("federation", _federation),
        ("witness", _witness),
        ("mindcoin", _mindcoin),
        ("hands", _hands),
    ):
        value, basis = _safe(fn)
        sections[name] = {"value": value, "basis": basis}
    return {
        "kind": "oracle_context_pass",
        "observed_at": _now(),
        "channel": channel,
        "sections": sections,
        "doctrine": DOCTRINE,
        "governance_note": (
            "Composed by ORACLE from live state. Human performs the paste "
            "(HANDS_OFF). Sections tagged RUNTIME_VERIFIED / CANDIDATE / DOCTRINE."
        ),
    }


def render(data: dict[str, Any] | None = None, *, compress: bool = True) -> str:
    """Render a paste-ready text pass. compress=True is the dense AI form."""
    if data is None:
        data = compose()
    s = data["sections"]

    def g(sec: str, key: str, dflt: str = "UNKNOWN") -> Any:
        v = s.get(sec, {}).get("value")
        if isinstance(v, dict):
            return v.get(key, dflt)
        return dflt

    def basis(sec: str) -> str:
        return s.get(sec, {}).get("basis", "UNKNOWN")

    L = []
    L.append("=== ORACLE CONTEXT PASS === " + data["observed_at"])
    L.append("composed by ORACLE from live state | human pastes (HANDS_OFF) | basis-tagged")
    L.append(f"[RUNTIME {basis('runtime')}] branch={g('runtime','branch')} commit={g('runtime','commit')} status={g('runtime','runtime_status')}")
    L.append(f"[COGNITION {basis('cognition')}] mode={g('cognition','mode')} model={g('cognition','model')} net={g('cognition','network_boundary')}")
    L.append(f"[CAPABILITIES {basis('capabilities')}] verified={g('capabilities','verified')} degraded={g('capabilities','degraded')} blocked={g('capabilities','blocked')}/{g('capabilities','total')}")
    L.append(f"[FEDERATION {basis('federation')}] canon={g('federation','approved_canon')} staged_candidates={g('federation','candidates_staged')} promotable_now={g('federation','promotable_now')}")
    L.append(f"[MINDCOIN {basis('mindcoin')}] verified_total={g('mindcoin','verified_total')} approved={g('mindcoin','approved_points')} pending_candidate={g('mindcoin','pending_points')}")
    L.append(f"[WITNESS {basis('witness')}] receipts={g('witness','witness_receipts')} (candidate-only, raw preserved)")
    L.append(f"[HANDS {basis('hands')}] posture={g('hands','posture')}")
    L.append("[DOCTRINE] " + " | ".join(data["doctrine"]))
    L.append("[ASK BACK] receipt discipline: candidate vs verified, no simulated-execution claims, authority stays with Noah.Physical.")
    if not compress:
        L.append("")
        L.append("(full json available via /api/context-pass)")
    return "\n".join(L)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="ORACLE Context Bus / thread-pass composer")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--channel", default="all")
    args = ap.parse_args()
    if args.json:
        print(json.dumps(compose(channel=args.channel), indent=2, default=str))
    else:
        print(render(compose(channel=args.channel)))
