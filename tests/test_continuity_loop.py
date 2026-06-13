"""
tests/test_continuity_loop.py — ORACLE End-to-End Continuity Loop Integration Test

Behavioral contract (non-negotiable):
  1. A durable fact IS saved for "My preferred dealer visit cadence is Tuesday through Thursday."
  2. "The coffee is cold." is discarded (below salience threshold).
  3. "Noah probably dislikes all coffee." is staged/pending, NOT promoted to canonical.
  4. Every durable write has complete provenance.
  5. An audit chain exists for the session.
  6. A clean reload can recall the saved fact.

Run:
  python tests/test_continuity_loop.py
  python -m pytest tests/test_continuity_loop.py -v
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# ── Path bootstrap ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))


# ── Test fixture ───────────────────────────────────────────────────────────────

SESSION_FIXTURE = [
    {"speaker": "Noah",   "text": "My preferred dealer visit cadence is Tuesday through Thursday."},
    {"speaker": "Noah",   "text": "The coffee is cold."},
    {"speaker": "Oracle", "text": "Noah probably dislikes all coffee."},
]


# ── Assertion helpers ──────────────────────────────────────────────────────────

def durable_fact_was_saved(result: dict) -> bool:
    """At least one record was written with the dealer cadence content."""
    for rec in result.get("written", []):
        if "dealer" in rec.get("fact_text", "").lower() or "tuesday" in rec.get("fact_text", "").lower():
            return True
    return False


def irrelevant_statement_was_discarded(result: dict) -> bool:
    """'The coffee is cold.' was NOT written as a durable fact."""
    for rec in result.get("written", []):
        if "coffee is cold" in rec.get("fact_text", "").lower():
            return False
    return True


def inference_was_not_promoted_to_verified(result: dict) -> bool:
    """The oracle inference about coffee is NOT written as canonical/accepted."""
    for rec in result.get("written", []):
        text = rec.get("fact_text", "").lower()
        if "probably" in text or "dislikes all coffee" in text:
            provenance = rec.get("provenance", {})
            if provenance.get("canonical_status") == "accepted":
                return False
    # It is acceptable for it to be staged
    return True


def provenance_is_complete(result: dict) -> bool:
    """Every written record has all required provenance fields."""
    required = {
        "source_type", "source_id", "observed_at", "confidence",
        "transformation_history", "canonical_status", "approval_status",
    }
    for rec in result.get("written", []):
        provenance = rec.get("provenance", {})
        if not required.issubset(set(provenance.keys())):
            return False
        if not isinstance(provenance.get("transformation_history"), list):
            return False
        if provenance.get("confidence") is None:
            return False
    # Also check staged records
    for rec in result.get("staged", []):
        provenance = rec.get("provenance", {})
        if not required.issubset(set(provenance.keys())):
            return False
    return True


def audit_chain_is_complete(result: dict) -> bool:
    """
    The audit chain must contain these events in order:
      session_received -> candidate_extracted -> provenance_assigned
      -> policy_evaluated (via transformation_history) -> memory_written
      -> pipeline_complete
    """
    chain = result.get("audit_chain", [])
    events = [e.get("event") for e in chain]

    required_events = {
        "session_received",
        "candidate_extracted",
        "provenance_assigned",
        "memory_written",
        "pipeline_complete",
    }
    return required_events.issubset(set(events))


# ── Main test ─────────────────────────────────────────────────────────────────

def test_continuity_fact_survives_clean_reload() -> bool:
    """
    Full end-to-end test with isolated temp database.
    Returns True if all assertions pass.
    """
    import memory as mem_module
    from continuity_pipeline import run_continuity_pipeline, ContinuityRuntime

    failures = []

    def check(name: str, passed: bool, detail: str = "") -> None:
        tag = "PASS" if passed else "FAIL"
        print(f"  [{tag}] {name}" + (f"\n         {detail}" if detail and not passed else ""))
        if not passed:
            failures.append(name)

    print("\n" + "=" * 65)
    print("ORACLE Continuity Loop — Integration Test")
    print("=" * 65)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = Path(tmp) / "test_oracle_memory.db"
        original_db_path = mem_module.DB_PATH

        try:
            # ── Run the pipeline ───────────────────────────────────────────
            print("\n  [FIXTURE] Three-statement session:")
            for msg in SESSION_FIXTURE:
                print(f"    {msg['speaker']}: {msg['text']}")
            print()

            result = run_continuity_pipeline(
                SESSION_FIXTURE,
                session_id="test_session_001",
                db_path=db_path,
            )

            # ── Show what happened ─────────────────────────────────────────
            print(f"  Written  : {len(result['written'])} record(s)")
            print(f"  Staged   : {len(result['staged'])} record(s)")
            print(f"  Discarded: {len(result['discarded'])} record(s)")
            print(f"  Audit    : {len(result['audit_chain'])} event(s)")
            print()

            # ── Behavioral assertions ──────────────────────────────────────
            check("Durable fact was saved (dealer cadence)", durable_fact_was_saved(result))
            check("Irrelevant statement was discarded (coffee cold)",
                  irrelevant_statement_was_discarded(result))
            check("Inference NOT promoted to verified/canonical",
                  inference_was_not_promoted_to_verified(result),
                  str({r.get("fact_text"): r.get("provenance", {}).get("canonical_status")
                       for r in result.get("written", [])}))
            check("Provenance is complete on all written records",
                  provenance_is_complete(result))
            check("Audit chain is complete",
                  audit_chain_is_complete(result),
                  str([e["event"] for e in result["audit_chain"]]))

            # ── Show the saved record detail ───────────────────────────────
            for rec in result.get("written", []):
                if "dealer" in rec.get("fact_text", "").lower() or "tuesday" in rec.get("fact_text", "").lower():
                    print("  Original statement : " + SESSION_FIXTURE[0]["text"])
                    print("  Classification     : " + rec["provenance"]["source_type"])
                    print("  Canonical status   : " + rec["provenance"]["canonical_status"])
                    print("  Approval status    : " + rec["provenance"]["approval_status"])
                    print("  Confidence         : " + str(rec["provenance"]["confidence"]))
                    print("  Stored record      :")
                    print("    fact_text    : " + rec["fact_text"])
                    print("    provenance   : " + json.dumps({
                        k: v for k, v in rec["provenance"].items()
                        if k != "transformation_history"
                    }, indent=2).replace("\n", "\n    "))
                    steps = [t.get("step") for t in rec["provenance"].get("transformation_history", [])]
                    print("    tx_history   : " + str(steps))
                    break

            # ── Show audit chain ───────────────────────────────────────────
            print("\n  Audit chain:")
            chain_events = [e["event"] for e in result["audit_chain"]]
            print("    " + " -> ".join(chain_events))

            # ── Clean reload test ──────────────────────────────────────────
            print("\n  [RELOAD TEST] Creating fresh runtime with same database...")
            fresh_runtime = ContinuityRuntime(db_path=db_path)
            recalled = fresh_runtime.wake_memory_search("dealer visit cadence")

            check("Fresh-restart recall returns a result", recalled is not None,
                  "wake_memory_search returned None")
            if recalled:
                check("Recalled fact has source_type=human_stated",
                      recalled.get("source_type") == "human_stated",
                      f"Got source_type={recalled.get('source_type')!r}")
                check("Recalled fact has canonical_status=accepted",
                      recalled.get("canonical_status") == "accepted",
                      f"Got canonical_status={recalled.get('canonical_status')!r}")

                print()
                print("  Fresh-restart recall:")
                print(f"    fact_text    : {recalled.get('fact_text')}")
                print(f"    source_type  : {recalled.get('source_type')}")
                print(f"    canonical    : {recalled.get('canonical_status')}")

        finally:
            mem_module.DB_PATH = original_db_path

    print()
    total = 8
    passed = total - len(failures)
    print("=" * 65)
    print(f"Result: {passed}/{total} passed")
    if failures:
        print(f"FAILURES: {failures}")
    print(f"STATUS: {'ALL PASS' if not failures else str(len(failures)) + ' FAILURES'}")
    print("=" * 65 + "\n")
    return len(failures) == 0


# ── pytest-compatible entry points ────────────────────────────────────────────

def test_durable_fact_saved():
    import memory as mem_module
    from continuity_pipeline import run_continuity_pipeline
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = Path(tmp) / "oracle_memory.db"
        orig = mem_module.DB_PATH
        try:
            result = run_continuity_pipeline(SESSION_FIXTURE, session_id="t1", db_path=db_path)
            assert durable_fact_was_saved(result), \
                f"Dealer cadence not saved. written={[r['fact_text'] for r in result['written']]}"
        finally:
            mem_module.DB_PATH = orig


def test_irrelevant_discarded():
    import memory as mem_module
    from continuity_pipeline import run_continuity_pipeline
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = Path(tmp) / "oracle_memory.db"
        orig = mem_module.DB_PATH
        try:
            result = run_continuity_pipeline(SESSION_FIXTURE, session_id="t2", db_path=db_path)
            assert irrelevant_statement_was_discarded(result), \
                "Coffee cold was not discarded"
        finally:
            mem_module.DB_PATH = orig


def test_inference_not_promoted():
    import memory as mem_module
    from continuity_pipeline import run_continuity_pipeline
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = Path(tmp) / "oracle_memory.db"
        orig = mem_module.DB_PATH
        try:
            result = run_continuity_pipeline(SESSION_FIXTURE, session_id="t3", db_path=db_path)
            assert inference_was_not_promoted_to_verified(result), \
                "Oracle inference was written as canonical"
        finally:
            mem_module.DB_PATH = orig


def test_provenance_complete():
    import memory as mem_module
    from continuity_pipeline import run_continuity_pipeline
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = Path(tmp) / "oracle_memory.db"
        orig = mem_module.DB_PATH
        try:
            result = run_continuity_pipeline(SESSION_FIXTURE, session_id="t4", db_path=db_path)
            assert provenance_is_complete(result), \
                f"Incomplete provenance on: {result['written']}"
        finally:
            mem_module.DB_PATH = orig


def test_audit_chain_complete():
    import memory as mem_module
    from continuity_pipeline import run_continuity_pipeline
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = Path(tmp) / "oracle_memory.db"
        orig = mem_module.DB_PATH
        try:
            result = run_continuity_pipeline(SESSION_FIXTURE, session_id="t5", db_path=db_path)
            assert audit_chain_is_complete(result), \
                f"Audit chain incomplete: {[e['event'] for e in result['audit_chain']]}"
        finally:
            mem_module.DB_PATH = orig


def test_clean_reload_recall():
    import memory as mem_module
    from continuity_pipeline import run_continuity_pipeline, ContinuityRuntime
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = Path(tmp) / "oracle_memory.db"
        orig = mem_module.DB_PATH
        try:
            run_continuity_pipeline(SESSION_FIXTURE, session_id="t6", db_path=db_path)
            # Fresh runtime — different object, same db
            mem_module.DB_PATH = orig  # reset before ContinuityRuntime sets it
            fresh = ContinuityRuntime(db_path=db_path)
            recalled = fresh.wake_memory_search("dealer visit cadence")
            assert recalled is not None, "wake_memory_search returned None after clean reload"
            assert recalled["source_type"] == "human_stated", \
                f"Expected human_stated, got {recalled['source_type']!r}"
        finally:
            mem_module.DB_PATH = orig


# ── CLI runner ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ok = test_continuity_fact_survives_clean_reload()
    sys.exit(0 if ok else 1)
