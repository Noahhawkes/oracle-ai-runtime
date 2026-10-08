import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

import memory  # noqa: E402
import thread_capture as tc  # noqa: E402


def _patch_paths(monkeypatch, tmp_path):
    ingest = tmp_path / "thread_ingest"
    monkeypatch.setattr(tc, "THREAD_INGEST_DIR", ingest)
    monkeypatch.setattr(tc, "THREAD_EXPORTS_DIR", tmp_path / "thread_exports")
    monkeypatch.setattr(tc, "RAW_TRANSCRIPTS_DIR", ingest / "raw_transcripts")
    monkeypatch.setattr(tc, "PARSED_TRANSCRIPTS_DIR", ingest / "parsed_transcripts")
    monkeypatch.setattr(tc, "SOURCE_MANIFESTS_DIR", ingest / "source_manifests")
    monkeypatch.setattr(tc, "CUSTODY_RECEIPTS_DIR", ingest / "custody_receipts")
    monkeypatch.setattr(tc, "SOURCE_MANIFEST_JSONL", ingest / "source_manifests" / "source_manifest.jsonl")
    monkeypatch.setattr(tc, "SEARCH_INDEX_JSONL", ingest / "search_index.jsonl")
    monkeypatch.setattr(tc, "MEMORY_DB_PATH", tmp_path / "oracle_memory.db")
    monkeypatch.setattr(memory, "DB_PATH", tmp_path / "oracle_memory.db")
    memory.init_db()


def test_ingest_paste_preserves_raw_parsed_receipt_and_provenance(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    sample = """ChatGPT: Here is an implementation idea.
User: This was copied from another system, author unknown.
Noah.Physical: I approve transport, not canon.
Claude Code: ```python
print("hello")
```
"""

    result = tc.ingest_paste(
        sample,
        source_system="ChatGPT",
        source_thread_id="sample-thread",
    )

    metadata = result["metadata"]
    raw_path = Path(result["raw_file_path"])
    parsed_path = Path(result["parsed_transcript_path"])
    receipt_path = Path(result["custody_receipt_path"])

    assert raw_path.exists()
    assert parsed_path.exists()
    assert receipt_path.exists()
    assert raw_path.read_text(encoding="utf-8") == sample
    assert metadata["raw_sha256"] == hashlib.sha256(sample.encode("utf-8")).hexdigest()
    assert metadata["canon_status"] == "candidate"
    assert metadata["promotion_status"] == "not_promoted"
    assert metadata["message_count"] == 4
    assert metadata["contains_ai_generated_text"] is True
    assert metadata["contains_user_submitted_text"] is True
    assert "Noah.Physical" in metadata["known_authors"]
    assert "User" in metadata["unknown_authors"]

    parsed = json.loads(parsed_path.read_text(encoding="utf-8"))
    messages = parsed["messages"]
    assert [m["message_index"] for m in messages] == [1, 2, 3, 4]
    assert messages[0]["speaker"] == "ChatGPT"
    assert messages[0]["token_origin"] == "ai_generated_text"
    assert messages[0]["authorial_authority"] == "unknown"
    assert messages[1]["speaker"] == "User"
    assert messages[1]["token_origin"] == "user_channel_unknown_author"
    assert messages[1]["authorial_authority"] == "unknown"
    assert messages[2]["speaker"] == "Noah.Physical"
    assert messages[2]["token_origin"] == "human_submitted_text"
    assert messages[2]["authorial_authority"] == "Noah.Physical"
    assert messages[3]["claim_type"] == "code_or_artifact"
    assert all(m["canon_status"] == "candidate" for m in messages)
    assert all(m["promotion_status"] == "not_promoted" for m in messages)

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["raw_sha256"] == metadata["raw_sha256"]
    assert len(receipt["receipt_hash_sha256"]) == 64
    assert receipt["account_scrape_performed"] is False
    assert receipt["source_file_mutated"] is False

    manifest_lines = tc.SOURCE_MANIFEST_JSONL.read_text(encoding="utf-8").splitlines()
    assert len(manifest_lines) == 1
    manifest = json.loads(manifest_lines[0])
    assert manifest["source_system"] == "ChatGPT"
    assert manifest["source_thread_id"] == "sample-thread"
    assert manifest["canon_status"] == "candidate"

    index_lines = tc.SEARCH_INDEX_JSONL.read_text(encoding="utf-8").splitlines()
    assert len(index_lines) == 4
    assert any("copied from another system" in json.loads(line)["message_text"] for line in index_lines)

    with memory.get_conn() as con:
        rows = con.execute("select key, value from facts where category='thread_capture'").fetchall()
    assert rows
    assert "promotion_status: not_promoted" in rows[0]["value"]


def test_ingest_json_messages(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    src = tmp_path / "claude_export.json"
    src.write_text(
        json.dumps(
            {
                "messages": [
                    {"role": "user", "content": "Please inspect this.", "timestamp": "2026-06-30T00:00:00Z"},
                    {"role": "assistant", "content": "Inspection result.", "timestamp": "2026-06-30T00:00:01Z"},
                ]
            }
        ),
        encoding="utf-8",
    )

    result = tc.ingest_file(
        src,
        source_system="Claude",
        source_thread_id="json-thread",
        capture_method="export_file",
    )

    parsed = json.loads(Path(result["parsed_transcript_path"]).read_text(encoding="utf-8"))
    assert parsed["metadata"]["message_count"] == 2
    assert parsed["messages"][0]["speaker"] == "User"
    assert parsed["messages"][0]["authorial_authority"] == "unknown"
    assert parsed["messages"][1]["speaker"] == "Assistant"
    assert parsed["messages"][1]["token_origin"] == "ai_generated_text"


def test_ingest_ai_extension_is_parsed_as_text(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    src = tmp_path / "recursion_pass.ai"
    src.write_text(
        ".AI:RECURSION_PASS/TEST\n\nNoah.Physical: Raw artifacts outrank summaries.\n",
        encoding="utf-8",
    )

    result = tc.ingest_file(
        src,
        source_system="Codex",
        source_thread_id="ai-pass",
        capture_method="current_session_user_submission",
    )

    parsed = json.loads(Path(result["parsed_transcript_path"]).read_text(encoding="utf-8"))
    assert parsed["metadata"]["message_count"] == 2
    assert "speaker_label_text" in parsed["metadata"]["parse_status"]
    assert parsed["messages"][0]["speaker"] == "unknown"
    assert parsed["messages"][1]["speaker"] == "Noah.Physical"
    assert parsed["messages"][1]["authorial_authority"] == "Noah.Physical"
    assert "Raw artifacts outrank summaries" in parsed["messages"][1]["message_text"]
    assert result["search_index_rows_written"] == 2


def test_binary_evidence_is_stored_raw_without_claiming_text(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    image = tmp_path / "screen.png"
    image.write_bytes(b"\x89PNG\r\nfake")

    result = tc.ingest_file(
        image,
        source_system="screenshot",
        source_thread_id="screen-1",
        capture_method="screenshot_file",
    )

    parsed = json.loads(Path(result["parsed_transcript_path"]).read_text(encoding="utf-8"))
    assert parsed["metadata"]["message_count"] == 0
    assert "ocr_not_enabled" in parsed["metadata"]["parse_status"]
    assert Path(result["raw_file_path"]).read_bytes() == b"\x89PNG\r\nfake"
    assert result["search_index_rows_written"] == 0


def test_ingest_directory_transports_each_file(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    exports = tmp_path / "exports"
    exports.mkdir()
    (exports / "a.txt").write_text("ChatGPT: first", encoding="utf-8")
    (exports / "b.txt").write_text("Claude: second", encoding="utf-8")

    result = tc.ingest_directory(
        exports,
        source_system="Drive export",
        capture_method="directory_import",
    )

    assert result["file_count"] == 2
    assert result["ingested_count"] == 2
    assert len(list((tmp_path / "thread_ingest" / "raw_transcripts").rglob("*.txt"))) == 2
    assert len(list((tmp_path / "thread_ingest" / "custody_receipts").rglob("*.json"))) == 2
    assert len(tc.SEARCH_INDEX_JSONL.read_text(encoding="utf-8").splitlines()) == 2
