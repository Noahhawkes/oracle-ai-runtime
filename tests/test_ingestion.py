import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from wirt import ingest_engine as ie


def test_lossless_text_retention_preserves_raw_layout_gaps_symbols_and_tabs(tmp_path, monkeypatch):
    corpus_root = tmp_path / "corpus"
    corpus_root.mkdir()
    monkeypatch.setattr(ie, "CORPUS_ROOT", corpus_root)

    source = corpus_root / "source.txt"
    raw_text = "alpha\tbeta\n\n  gamma  \nline with symbols: []{}<>|!@#$%^&*()\nend"
    source.write_text(raw_text, encoding="utf-8")

    receipt = ie.ingest_candidate_trace(
        source,
        "vault/copied.txt",
        corpus_root=corpus_root,
        authorship_tag="user_submitted_text",
    )

    copied = corpus_root / "vault" / "copied.txt"
    assert receipt["status"] == "VERIFIED"
    assert receipt["receipt_type"] == "candidate_trace_verified"
    assert receipt["authorship_tag"] == "user_submitted_text"
    assert receipt["receipt_sha256"] == ie.sha256_file(source)
    assert copied.read_text(encoding="utf-8") == raw_text
    assert receipt["lossless_retention"] is True


def test_traversal_protection_blocks_target_escape_visibly(tmp_path, monkeypatch):
    corpus_root = tmp_path / "corpus"
    corpus_root.mkdir()
    monkeypatch.setattr(ie, "CORPUS_ROOT", corpus_root)

    source = corpus_root / "source.txt"
    source.write_text("payload", encoding="utf-8")

    receipt = ie.ingest_candidate_trace(
        source,
        "../escape.txt",
        corpus_root=corpus_root,
        authorship_tag="system_witness_trace",
    )

    assert receipt["status"] == "BLOCKED"
    assert receipt["blocked_reason"] == "path_isolation_violation"
    assert receipt["intercepted"] is True
    assert receipt["authorship_tag"] == "system_witness_trace"
    assert not (tmp_path / "escape.txt").exists()


def test_traversal_protection_blocks_source_context_leak_visibly(tmp_path, monkeypatch):
    corpus_root = tmp_path / "corpus"
    corpus_root.mkdir()
    monkeypatch.setattr(ie, "CORPUS_ROOT", corpus_root)

    external_root = tmp_path / "external"
    external_root.mkdir()
    source = external_root / "leak.txt"
    source.write_text("payload", encoding="utf-8")

    receipt = ie.ingest_candidate_trace(
        source,
        "vault/leak.txt",
        corpus_root=corpus_root,
        authorship_tag="user_submitted_text",
    )

    assert receipt["status"] == "BLOCKED"
    assert receipt["blocked_reason"] == "path_isolation_violation"
    assert receipt["intercepted"] is True
    assert receipt["source_path"] == str(source)
    assert not (corpus_root / "vault" / "leak.txt").exists()
