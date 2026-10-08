from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "core"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import storage_policy as sp  # noqa: E402


def test_gate_prefers_ledger_over_new_file():
    d = sp.should_create_file(fits_ledger=True)
    assert d["create"] is False
    assert d["recommended_route"] == "append_jsonl"


def test_gate_prefers_db_row():
    d = sp.should_create_file(storable_as_db_row=True)
    assert d["create"] is False
    assert d["recommended_route"] == "sqlite_db"


def test_gate_prefers_pointer_over_copy():
    d = sp.should_create_file(representable_as_pointer=True)
    assert d["create"] is False
    assert d["recommended_route"] == "source_pointer"


def test_gate_allows_human_openable_artifact():
    d = sp.should_create_file(human_opens_independently=True, materially_unique=True)
    assert d["create"] is True


def test_gate_unique_with_no_container_creates():
    d = sp.should_create_file(materially_unique=True)
    assert d["create"] is True
    assert d["recommended_route"] == "independent_file"


def test_append_jsonl_creates_on_write_and_appends(tmp_path):
    f = tmp_path / "ledger.jsonl"
    n1 = sp.append_jsonl(f, {"a": 1})
    n2 = sp.append_jsonl(f, {"b": 2})
    assert f.exists() and n1 > 0 and n2 > 0
    lines = f.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["a"] == 1


def test_append_journal_rolls_into_one_file(tmp_path, monkeypatch):
    monkeypatch.setattr(sp, "journal_file", lambda year=None: tmp_path / "2026.md")
    p1 = sp.append_journal("first entry", heading="Day 1")
    p2 = sp.append_journal("second entry", heading="Day 2")
    assert p1 == p2  # same rolling file, not one per entry
    text = p1.read_text(encoding="utf-8")
    assert "first entry" in text and "second entry" in text


def test_dedupe_references_identical_content():
    idx = sp.SeenIndex()
    r1 = idx.dedupe("same big blob")
    r2 = idx.dedupe("same big blob")
    assert r1["action"] == "stored"
    assert r2["action"] == "referenced"
    assert r2["bytes_avoided"] > 0
    assert r1["sha256"] == r2["sha256"]


def test_source_pointer_shape():
    ptr = sp.source_pointer("s1", "C:/x.txt", "abc", offset=10, length=20)
    assert ptr == {"source_id": "s1", "path": "C:/x.txt", "sha256": "abc", "offset": 10, "length": 20}


def test_retention_classes():
    assert sp.retention_class(1) == "HOT"
    assert sp.retention_class(1, resolved=True) == "WARM"
    assert sp.retention_class(30) == "WARM"
    assert sp.retention_class(200) == "COLD"
    assert sp.retention_class(1, is_raw_source=True) == "ARCHIVAL"


def test_metrics_growth_is_records_not_files():
    m = sp.StorageMetrics()
    m.record_create()
    for _ in range(50):
        m.record_append(120)
    m.record_dedupe({"action": "referenced", "bytes_avoided": 500})
    snap = m.snapshot()
    assert snap["AVG_RECORDS_PER_FILE"] == 50.0
    assert snap["DUPLICATE_BYTES_AVOIDED"] == 500
    assert snap["GROWTH_IS_RECORDS_NOT_FILES"] is True
