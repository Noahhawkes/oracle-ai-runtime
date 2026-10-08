"""Tests for the Federation pattern buffer capability (TP_004 doctrine).

The Federation capability surfaces the replicator / pattern-buffer doctrine as a
real, non-destructive broker capability: it reads the approved-truth store and
the candidate staging area without ever promoting or manufacturing a record.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "core")):
    if p not in sys.path:
        sys.path.insert(0, p)

import capability_broker as cb


def test_federation_capability_is_registered():
    keys = {c.key for c in cb.COMPONENTS}
    assert "federation" in keys
    cap = cb._BY_KEY["federation"]
    assert cap.component == "Federation pattern buffer"
    assert cap.permitted == "read_only_no_promotion"
    assert cap.smoke is _smoke_ref()


def _smoke_ref():
    return cb._smoke_federation


def test_federation_smoke_is_read_only_and_carries_doctrine():
    outcome = cb._smoke_federation()
    # Read-only probe must not fail or block on a healthy local runtime.
    assert outcome.status in {"success", "degraded"}
    assert outcome.evidence["doctrine"] == cb.FEDERATION_DOCTRINE
    assert outcome.evidence["buffer_mode"] == "read_only_no_promotion"
    assert isinstance(outcome.evidence["approved_records"], int)
    assert "manufacture truth" in cb.FEDERATION_DOCTRINE


def test_federation_appears_in_discovery():
    statuses = cb.discover_capabilities(run_smokes=False)
    names = {s.component for s in statuses}
    assert "Federation pattern buffer" in names


def test_federation_smoke_receipt_round_trips():
    receipt = cb.invoke_capability("federation", "smoke")
    assert receipt.component == "Federation pattern buffer"
    assert receipt.status in {"success", "degraded"}
    assert receipt.evidence.get("doctrine") == cb.FEDERATION_DOCTRINE
