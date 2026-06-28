"""Tests for the Federation Replicator / Pattern Buffer engine (core/federation.py).

Doctrine under test: "Replicate from approved truth; do not manufacture truth."
The replicator must copy candidate text verbatim into canon, gate on approval,
refuse secrets, and never double-write. All tests run against temp stores so real
canon is never touched.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "core")):
    if p not in sys.path:
        sys.path.insert(0, p)

import federation
import approval_center as ac
import memory


def _seed_candidate(mem_dir: Path, cid: str, text: str, *, key="content"):
    idx_path = mem_dir / "remember_me" / "index.json"
    idx_path.parent.mkdir(parents=True, exist_ok=True)
    idx = {}
    if idx_path.exists():
        idx = json.loads(idx_path.read_text(encoding="utf-8"))
    idx[cid] = {key: text, "summary": text[:40], "status": "pending", "created_at": "2026-06-27T00:00:00+00:00"}
    idx_path.write_text(json.dumps(idx, indent=2), encoding="utf-8")
    return idx_path


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    mem_dir = tmp_path / "Memory"
    mem_dir.mkdir()
    monkeypatch.setattr(memory, "DB_PATH", mem_dir / "test_canon.db")
    monkeypatch.setattr(federation, "MEMORY", mem_dir)
    monkeypatch.setattr(federation, "RECEIPT_FILE", mem_dir / "federation_promotions.jsonl")
    monkeypatch.setattr(ac, "MEM", mem_dir)
    memory.init_db()
    return mem_dir


def _canon_rows():
    with memory.get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM durable_facts").fetchall()]


def test_promote_replicates_verbatim_into_canon(isolated):
    text = "Apollo greets Noah at the door every morning. This is a presence anchor, not a pet."
    _seed_candidate(isolated, "cand-1", text)

    receipt = federation.promote("cand-1", source="memory", approved_by="Noah.Physical")

    assert receipt["status"] == "replicated"
    rows = _canon_rows()
    assert len(rows) == 1
    row = rows[0]
    assert row["fact_text"] == text                 # verbatim — no smoothing
    assert row["source_type"] == "human_stated"
    assert row["approval_status"] == "approved"
    assert row["source_id"] == "federation:memory:cand-1"
    hist = json.loads(row["transformation_history"])
    assert hist[0]["raw_preserved"] is True
    assert hist[0]["doctrine"] == federation.DOCTRINE


def test_promote_grants_highest_authority(isolated):
    _seed_candidate(isolated, "cand-2", "Noah authorized truth.")
    federation.promote("cand-2", source="memory")
    # human_stated + approved is authority rank 100 — Noah's approved word is top.
    assert memory._authority_rank("human_stated", "approved", "canon") == 100


def test_promotion_is_idempotent(isolated):
    _seed_candidate(isolated, "cand-3", "Replicate once, not twice.")
    first = federation.promote("cand-3", source="memory")
    second = federation.promote("cand-3", source="memory")
    assert first["status"] == "replicated"
    assert second["status"] == "noop_already_canon"
    assert len(_canon_rows()) == 1                   # never double-written


def test_secret_candidate_is_refused(isolated):
    _seed_candidate(isolated, "cand-4", "my api_key=sk-abcdefghijklmnopqrstuvwxyz123456")
    receipt = federation.promote("cand-4", source="memory")
    assert receipt["status"] == "blocked"
    assert "secret" in receipt["blocker"].lower()
    assert len(_canon_rows()) == 0                   # nothing manufactured into canon


def test_missing_candidate_blocks(isolated):
    receipt = federation.promote("does-not-exist", source="memory")
    assert receipt["status"] == "blocked"
    assert len(_canon_rows()) == 0


def test_non_promotable_source_blocks(isolated):
    receipt = federation.promote("x", source="video")
    assert receipt["status"] == "blocked"
    assert "not promotable" in receipt["blocker"]


def test_status_reports_doctrine_and_counts(isolated):
    _seed_candidate(isolated, "cand-5", "A staged truth.")
    st = federation.status()
    assert st["doctrine"] == federation.DOCTRINE
    assert isinstance(st["approved_records"], int)
    assert st["candidate_records_staged"] >= 1
