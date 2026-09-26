from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import master_task_ledger as ledger


def test_normalize_removes_nested_stale_prefixes() -> None:
    assert ledger.normalize_title(
        "Stale pending item: Stale pending item: No smoke test in bridge.py"
    ) == "No smoke test in bridge.py"


def test_add_collapses_duplicate_records() -> None:
    tasks = {}
    ledger._add(
        tasks,
        title="No smoke test in bridge.py",
        category="code_quality",
        status="candidate",
        source_ref="one",
    )
    ledger._add(
        tasks,
        title="No smoke test in bridge.py",
        category="code_quality",
        status="candidate",
        source_ref="two",
    )
    assert len(tasks) == 1
    task = next(iter(tasks.values()))
    assert task["duplicate_records"] == 1
    assert task["source_refs"] == ["one", "two"]

