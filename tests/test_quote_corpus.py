from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import file_recall as fr  # noqa: E402
import quote_corpus as qc  # noqa: E402


def _wire_tmp_quote_corpus(monkeypatch, tmp_path):
    quote_root = tmp_path / "Memory" / "quote_corpus"
    monkeypatch.setattr(qc, "QUOTE_DIR", quote_root)
    monkeypatch.setattr(qc, "PACKET_DIR", quote_root / "packets")
    monkeypatch.setattr(qc, "MANIFEST_FILE", quote_root / "manifest.jsonl")
    monkeypatch.setattr(qc, "RECEIPT_FILE", quote_root / "receipts.jsonl")
    monkeypatch.setattr(qc, "LATEST_STATUS_FILE", quote_root / "latest_status.json")
    monkeypatch.setattr(qc, "DEFAULT_ROOTS", [tmp_path])
    monkeypatch.setattr(fr, "DEFAULT_ROOTS", [tmp_path])
    monkeypatch.setattr(fr, "MEMORY_DIR", tmp_path / "Memory")
    monkeypatch.setattr(fr, "RECEIPT_FILE", tmp_path / "Memory" / "file_recall_receipts.jsonl")


def _minimal_docx(path: Path, text: str) -> None:
    document_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
        "<w:body><w:p><w:r><w:t>"
        + text
        + "</w:t></w:r></w:p></w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types></Types>")
        zf.writestr("word/document.xml", document_xml)


def test_ingest_file_creates_exact_quote_packet_without_touching_source(tmp_path, monkeypatch):
    _wire_tmp_quote_corpus(monkeypatch, tmp_path)
    source = tmp_path / "rendered_reality.ai"
    original = (
        "Rendered Reality is a continuity system for preserving source-backed identity. "
        "It should keep the exact words close enough to cite without pretending a summary "
        "is the same thing as evidence.\n\n"
        "ORACLE should remember provenance before prose, and preserve uncertainty before myth."
    )
    source.write_text(original, encoding="utf-8")

    result = qc.ingest_file(source, max_quote_chars=260)
    packet_text = Path(result["packet_path"]).read_text(encoding="utf-8")
    manifest_rows = [
        json.loads(line)
        for line in (tmp_path / "Memory" / "quote_corpus" / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    assert result["ok"] is True
    assert result["operation_type"] == "quote_corpus_ingest_file"
    assert result["quote_count"] >= 1
    assert source.read_text(encoding="utf-8") == original
    assert ".AI:QUOTE_SOURCE_PACKET/" in packet_text
    assert "@QUOTE" in packet_text
    assert "Rendered Reality is a continuity system" in packet_text
    assert manifest_rows[0]["source_path"] == str(source.resolve())
    assert manifest_rows[0]["line_start"] == 1
    assert manifest_rows[0]["quote_sha256"]
    assert manifest_rows[0]["source_sha256"]


def test_search_quotes_returns_source_path_and_line_range(tmp_path, monkeypatch):
    _wire_tmp_quote_corpus(monkeypatch, tmp_path)
    source = tmp_path / "oracle_source.md"
    source.write_text(
        "ORACLE quote corpus stores exact excerpts with line ranges and packet hashes. "
        "That lets frontend recall cite the source instead of bluffing through metadata.",
        encoding="utf-8",
    )
    qc.ingest_file(source)

    result = qc.search_quotes("exact excerpts line ranges", limit=3)

    assert result["operation_type"] == "quote_corpus_search"
    assert result["result_count"] == 1
    assert result["results"][0]["source_path"] == str(source.resolve())
    assert result["results"][0]["line_start"] >= 1
    assert "exact excerpts" in result["results"][0]["quote_text"]


def test_secret_like_content_is_receipted_but_not_stored(tmp_path, monkeypatch):
    _wire_tmp_quote_corpus(monkeypatch, tmp_path)
    source = tmp_path / "safe_name.md"
    source.write_text(
        "This document contains password: do-not-store-this-secret-value and should be gated.",
        encoding="utf-8",
    )

    result = qc.ingest_file(source)
    receipts = (tmp_path / "Memory" / "quote_corpus" / "receipts.jsonl").read_text(encoding="utf-8")

    assert result["ok"] is False
    assert result["status"] == "gated_sensitive_content"
    assert result["receipt_path"]
    assert not (tmp_path / "Memory" / "quote_corpus" / "manifest.jsonl").exists()
    assert not list((tmp_path / "Memory" / "quote_corpus" / "packets").glob("*.ai"))
    assert "do-not-store-this-secret-value" not in receipts


def test_docx_text_can_be_quoted(tmp_path, monkeypatch):
    _wire_tmp_quote_corpus(monkeypatch, tmp_path)
    source = tmp_path / "thread_merge.docx"
    _minimal_docx(
        source,
        "Thread Merge contains Rendered Reality continuity language and enough exact words "
        "to become a quote packet with a stable source hash.",
    )

    result = qc.ingest_file(source)
    search = qc.search_quotes("Rendered Reality continuity", limit=3)

    assert result["ok"] is True
    assert result["quote_count"] == 1
    assert search["result_count"] == 1
    assert search["results"][0]["name"] == "thread_merge.docx"


def test_parse_and_format_quote_commands():
    assert qc.parse_quote_request("/quote-corpus-status") == {"mode": "status", "value": ""}
    assert qc.parse_quote_request("/quote-corpus-ingest Rendered Reality") == {
        "mode": "ingest",
        "value": "Rendered Reality",
    }
    assert qc.parse_quote_request("/quote-corpus-search Noah") == {"mode": "search", "value": "Noah"}
    assert qc.parse_quote_request("/quote-source docs/example.ai") == {"mode": "file", "value": "docs/example.ai"}

    rendered = qc.format_result({
        "operation_type": "quote_corpus_status",
        "source_count": 2,
        "quote_count": 12,
        "receipt_count": 3,
        "manifest_path": "manifest.jsonl",
        "packet_dir": "packets",
        "latest_receipt": {"created_count": 1},
    })

    assert "QUOTE CORPUS STATUS" in rendered
    assert "quote_count: 12" in rendered
