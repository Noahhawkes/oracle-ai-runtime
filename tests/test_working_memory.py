"""Tests for L1 working memory: concurrency, expiration, bounds, source labels, versioning."""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))

from working_memory import WorkingMemory, VALID_STATUS  # noqa: E402


def test_source_labels_and_status_validation():
    wm = WorkingMemory()
    wm.set_state("active_task", "build recall fabric", source="noah", status="verified")
    sv = wm.get_state("active_task")
    assert sv.value == "build recall fabric"
    assert sv.status == "verified" and sv.status in VALID_STATUS
    assert sv.source == "noah" and sv.updated_at
    with pytest.raises(ValueError):
        wm.set_state("x", "y", source="s", status="totally-sure")  # invalid status
    with pytest.raises(ValueError):
        wm.set_state("x", "y", source="")                          # missing source
    with pytest.raises(ValueError):
        wm.add_fact("z", source="")                                # missing source


def test_version_increments_only_on_authoritative_change():
    wm = WorkingMemory()
    v0 = wm.version
    v1 = wm.set_state("mode", "companion", source="server", status="verified")
    assert v1 == v0 + 1
    v2 = wm.set_state("mode", "companion", source="server", status="verified")  # identical
    assert v2 == v1, "identical re-set must not bump version"
    v3 = wm.set_state("mode", "builder", source="server", status="verified")    # real change
    assert v3 == v2 + 1
    # status change alone is authoritative
    v4 = wm.set_state("mode", "builder", source="server", status="reported")
    assert v4 == v3 + 1
    # adding rolling facts does NOT bump authoritative version
    wm.add_fact("a fact", source="t")
    assert wm.version == v4


def test_bounded_collections():
    wm = WorkingMemory(max_items=10)
    for i in range(100):
        wm.add_fact(f"fact-{i}", source="t")
    snap = wm.snapshot()
    assert len(snap["recent_facts"]) == 10
    assert snap["recent_facts"][-1]["content"] == "fact-99"  # newest retained


def test_expiration_purges_rolling_items():
    wm = WorkingMemory()
    wm.add_fact("ephemeral", source="t", ttl=0.2)
    wm.add_fact("durable", source="t", ttl=0)  # ttl<=0 => no expiry
    assert len(wm.snapshot()["recent_facts"]) == 2
    time.sleep(0.35)
    facts = [f["content"] for f in wm.snapshot()["recent_facts"]]
    assert "ephemeral" not in facts
    assert "durable" in facts


def test_snapshot_is_immutable():
    wm = WorkingMemory()
    wm.set_state("project", "ORACLE.AI", source="server", status="verified")
    wm.add_fact("f1", source="t")
    snap = wm.snapshot()
    snap["state"]["project"]["value"] = "TAMPERED"
    snap["recent_facts"].append({"content": "injected"})
    snap2 = wm.snapshot()
    assert snap2["state"]["project"]["value"] == "ORACLE.AI"
    assert all(f["content"] != "injected" for f in snap2["recent_facts"])


def test_concurrent_writes_do_not_corrupt():
    wm = WorkingMemory(max_items=1000)
    errors = []

    def worker(n: int):
        try:
            for i in range(200):
                wm.add_fact(f"{n}-{i}", source=f"thread-{n}")
                wm.set_state(f"k{n}", i, source=f"thread-{n}", status="reported")
                wm.snapshot()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, f"concurrency errors: {errors[:3]}"
    snap = wm.snapshot()
    assert len(snap["recent_facts"]) == 1000          # bounded, not corrupted
    assert len([k for k in snap["state"] if k.startswith("k")]) == 8
