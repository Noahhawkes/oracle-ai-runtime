import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(ROOT))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import thread_burden as tb  # noqa: E402


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def test_thread_burden_report_counts_duplicates_words_and_buckets(monkeypatch, tmp_path):
    manifest = tmp_path / "source_manifest.jsonl"
    search_index = tmp_path / "search_index.jsonl"
    monkeypatch.setattr(tb, "SOURCE_MANIFEST_JSONL", manifest)
    monkeypatch.setattr(tb, "SEARCH_INDEX_JSONL", search_index)

    _append_jsonl(
        manifest,
        {
            "source_system": "ChatGPT",
            "source_thread_id": "thread-one",
            "captured_at": "2026-07-02T10:00:00Z",
            "message_count": 2,
            "raw_sha256": "a" * 64,
            "custody_receipt_path": "receipts/thread-one.json",
            "canon_status": "candidate",
            "promotion_status": "not_promoted",
        },
    )
    _append_jsonl(
        manifest,
        {
            "source_system": "Codex",
            "source_thread_id": "thread-one-duplicate",
            "captured_at": "2026-07-02T11:00:00Z",
            "message_count": 2,
            "raw_sha256": "a" * 64,
            "custody_receipt_path": "receipts/thread-one-duplicate.json",
            "canon_status": "candidate",
            "promotion_status": "not_promoted",
        },
    )
    _append_jsonl(
        manifest,
        {
            "source_system": "Gemini",
            "source_thread_id": "thread-two",
            "captured_at": "2026-07-02T12:00:00Z",
            "message_count": 1,
            "raw_sha256": "b" * 64,
            "custody_receipt_path": "receipts/thread-two.json",
            "canon_status": "candidate",
            "promotion_status": "not_promoted",
        },
    )

    _append_jsonl(
        search_index,
        {
            "source_system": "ChatGPT",
            "source_thread_id": "thread-one",
            "message_index": 1,
            "speaker": "Noah.Physical",
            "message_text": "Ellie and UserPath are too much to carry but I need provenance.",
            "token_origin": "human_submitted_text",
            "authorial_authority": "Noah.Physical",
            "claim_type": "conversation",
            "canon_status": "candidate",
            "promotion_status": "not_promoted",
            "parsed_transcript_path": "parsed/thread-one.json",
        },
    )
    _append_jsonl(
        search_index,
        {
            "source_system": "ChatGPT",
            "source_thread_id": "thread-one",
            "message_index": 2,
            "speaker": "ChatGPT",
            "message_text": "Rendered Reality should preserve receipts and avoid narrative smoothing.",
            "token_origin": "ai_generated_text",
            "authorial_authority": "unknown",
            "claim_type": "ai_response",
            "canon_status": "candidate",
            "promotion_status": "not_promoted",
            "parsed_transcript_path": "parsed/thread-one.json",
        },
    )
    _append_jsonl(
        search_index,
        {
            "source_system": "Gemini",
            "source_thread_id": "thread-two",
            "message_index": 1,
            "speaker": "Assistant",
            "message_text": "Preferences can stop cold introductions and support routing repair.",
            "token_origin": "ai_generated_text",
            "authorial_authority": "unknown",
            "claim_type": "ai_response",
            "canon_status": "candidate",
            "promotion_status": "not_promoted",
            "parsed_transcript_path": "parsed/thread-two.json",
        },
    )

    report = tb.build_thread_burden_report(recent_limit=2, duplicate_limit=3, sample_per_bucket=1)

    assert report["source_manifest_rows"] == 3
    assert report["search_index_rows"] == 3
    assert report["unique_raw_hashes"] == 2
    assert report["duplicate_group_count"] == 1
    assert report["counts_by_capture_source_system"] == {"ChatGPT": 1, "Codex": 1, "Gemini": 1}
    assert report["word_metrics"]["noah_authored_words"] > 0
    assert report["word_metrics"]["ai_generated_words"] > 0
    assert report["boundary"]["canon_status"] == "candidate"
    assert report["boundary"]["promotion_status"] == "not_promoted"
    assert report["boundary"]["cloud_upload"] is False
    assert report["boundary"]["git_push"] is False

    buckets = {bucket["bucket_id"]: bucket for bucket in report["carry_buckets"]}
    assert buckets["ellie"]["matching_messages"] == 1
    assert buckets["userpath"]["matching_messages"] == 1
    assert buckets["rendered_reality"]["matching_messages"] == 1
    assert buckets["preferences"]["matching_messages"] == 1

    text = tb.format_thread_burden_report(report)
    assert "THREAD BURDEN REPORT" in text
    assert "candidate" in text
    assert "not_promoted" in text
    assert "Ellie / Drakin / Dragonkin" in text
    assert "DUPLICATE RAW HASHES" in text


def test_thread_burden_report_tolerates_missing_files(monkeypatch, tmp_path):
    monkeypatch.setattr(tb, "SOURCE_MANIFEST_JSONL", tmp_path / "missing_manifest.jsonl")
    monkeypatch.setattr(tb, "SEARCH_INDEX_JSONL", tmp_path / "missing_search.jsonl")

    report = tb.build_thread_burden_report()

    assert report["ok"] is True
    assert report["source_manifest_rows"] == 0
    assert report["search_index_rows"] == 0
    assert report["word_metrics"]["total_indexed_words"] == 0
    assert report["boundary"]["promotion_status"] == "not_promoted"


def test_thread_burden_slash_command_routes_to_report(monkeypatch):
    import asyncio
    import memory
    import oracle_server as srv

    monkeypatch.setattr(memory, "save_message", lambda *_, **__: None)
    monkeypatch.setattr(
        tb,
        "build_thread_burden_report",
        lambda **_: {
            "ok": True,
            "generated_at": "2026-07-02T00:00:00Z",
            "source_manifest_rows": 1,
            "search_index_rows": 1,
            "unique_raw_hashes": 1,
            "duplicate_group_count": 0,
            "counts_by_capture_source_system": {"ChatGPT": 1},
            "word_metrics": {
                "total_indexed_words": 2,
                "noah_authored_words": 2,
                "ai_generated_words": 0,
                "noah_to_ai_word_ratio": None,
            },
            "carry_buckets": [],
            "recent_captures": [],
            "duplicate_groups": [],
            "boundary": {
                "canon_status": "candidate",
                "promotion_status": "not_promoted",
                "source_rule": "Captured threads are searchable evidence candidates, not canon.",
            },
        },
    )

    async def collect():
        payloads = []
        async for chunk in srv._stream_reply("/thread-burden"):
            if chunk.startswith("data: "):
                payloads.append(json.loads(chunk[len("data: "):].strip()))
        return payloads

    payloads = asyncio.run(collect())
    text = "".join(item.get("text", "") for item in payloads if item.get("type") == "token")
    done = [item for item in payloads if item.get("type") == "done"][-1]

    assert "THREAD BURDEN REPORT" in text
    assert "Prompt-back candidate:" not in text
    assert done["initiative_prompt_back"]["reason"] == "thread_burden_decision_point"
    assert done["initiative_prompt_back"]["action_taken"] == "none"
    assert done["initiative_prompt_back"]["question"] == "Do you want me to classify the landed thread material, index/search it, or hold it raw for now?"
    assert done["effective_route"] == "thread_burden_report"
