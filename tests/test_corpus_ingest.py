"""Tests for LCL corpus ingestion: metadata, UNKNOWN honesty, gating, dry-run."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import light_compression as lc  # noqa: E402
import corpus_ingest as ci  # noqa: E402


def test_metadata_has_hash_and_size(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello world", encoding="utf-8")
    meta = ci.file_metadata(f)
    assert meta["bytes"] == 11
    assert meta["ext"] == ".txt"
    assert meta["sha256"] and len(meta["sha256"]) == 64


def test_cloud_stub_is_unknown(tmp_path):
    f = tmp_path / "doc.gdoc"
    f.write_text('{"url": "https://docs.google.com/..."}', encoding="utf-8")
    text, status = ci.extract_text(f)
    assert text is None and status == "cloud_stub_unreadable"


def test_empty_file_unknown(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("", encoding="utf-8")
    _, status = ci.extract_text(f)
    assert status == "empty_file"


def test_binary_yields_unknown_not_guess(tmp_path):
    f = tmp_path / "img.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
    cand = ci.compress_file(f)
    assert cand["kernel"] == "UNKNOWN"
    assert cand["disposition"] == "unknown"


def test_sensitive_file_is_gated(tmp_path):
    f = tmp_path / "secrets.txt"
    f.write_text("api_key = sk-abc123def456 and the bearer token is secret", encoding="utf-8")
    cand = ci.compress_file(f)
    assert cand["disposition"] == "gated_sensitive"
    assert cand["sensitivity"] > 0.5


def test_doctrine_file_becomes_candidate(tmp_path):
    f = tmp_path / "law.md"
    f.write_text(
        "Light Compression Law: ORACLE must preserve the authentic kernel and "
        "discard noise. This is a governance rule and a hard constraint on memory.",
        encoding="utf-8",
    )
    cand = ci.compress_file(f)
    assert cand["status"] == "ok"
    assert cand["memory_type"] == lc.CONSTRAINT
    assert cand["kernel"].startswith("Rule:")
    assert cand["disposition"] == "candidate"


def test_dry_run_writes_receipt_commits_nothing(tmp_path, monkeypatch):
    # Isolate durable memory + receipts.
    monkeypatch.setattr(lc, "LIGHT_FILE", tmp_path / "light_memory.json")
    monkeypatch.setattr(ci, "RECEIPT_DIR", tmp_path / "receipts")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "rule.md").write_text(
        "Governance law: ORACLE must never act without a receipt. Hard constraint.",
        encoding="utf-8")
    (corpus / "note.txt").write_text("ok thanks", encoding="utf-8")  # noise

    man = ingest = ci.ingest_corpus(corpus, commit=False)
    assert man["mode"] == "dry_run"
    assert man["counts"]["seen"] == 2
    assert man["counts"]["committed"] == 0
    assert Path(man["receipt_path"]).exists()
    # Nothing durable was written.
    assert not (tmp_path / "light_memory.json").exists()


def test_commit_promotes_candidate(tmp_path, monkeypatch):
    monkeypatch.setattr(lc, "LIGHT_FILE", tmp_path / "light_memory.json")
    monkeypatch.setattr(ci, "RECEIPT_DIR", tmp_path / "receipts")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "project.md").write_text(
        "ORACLE.AI build: the voice loop, actuation channel, and commit pipeline "
        "are the current project priority and next step to ship.",
        encoding="utf-8")
    man = ci.ingest_corpus(corpus, commit=True)
    assert man["counts"]["committed"] >= 1
    assert (tmp_path / "light_memory.json").exists()
