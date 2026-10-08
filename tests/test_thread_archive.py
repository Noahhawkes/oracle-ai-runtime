import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

import memory  # noqa: E402
import companion_bootstrap as cb  # noqa: E402
import thread_archive as ta  # noqa: E402


def _patch_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(ta, "DB_PATH", tmp_path / "oracle_memory.db")
    monkeypatch.setattr(ta, "THREAD_EXPORTS_DIR", tmp_path / "thread_exports")
    monkeypatch.setattr(ta, "THREAD_RECALL_DIR", tmp_path / "thread_recall")
    monkeypatch.setattr(ta, "RECALL_IMPORTS_DIR", tmp_path / "thread_recall" / "imports")
    monkeypatch.setattr(ta, "RECALL_MANIFESTS_DIR", tmp_path / "thread_recall" / "manifests")
    monkeypatch.setattr(ta, "RECALL_RECEIPTS_DIR", tmp_path / "thread_recall" / "receipts")
    monkeypatch.setattr(ta, "ONGOING_DIR", tmp_path / "thread_recall" / "ongoing")
    monkeypatch.setattr(ta, "ONGOING_THREAD_PATH", tmp_path / "thread_recall" / "ongoing" / "ongoing_cross_system_thread.txt")
    monkeypatch.setattr(ta, "ONGOING_RECEIPT_JSONL", tmp_path / "thread_recall" / "receipts" / "ongoing_cross_system_thread_receipts.jsonl")
    monkeypatch.setattr(memory, "DB_PATH", tmp_path / "oracle_memory.db")
    memory.init_db()


def _seed_session() -> int:
    sid = memory.new_session()
    memory.save_message(sid, "user", "hello from Noah")
    memory.save_message(sid, "assistant", "hello from ORACLE")
    return sid


def test_export_session_to_txt_and_recall_fact(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    sid = _seed_session()

    result = ta.export_session_to_txt(sid)

    out = Path(result["path"])
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "ORACLE THREAD TXT EXPORT" in text
    assert "hello from Noah" in text
    assert result["recall"]["stored_txt_path"]

    with memory.get_conn() as con:
        rows = con.execute("select category, key, value from facts where category='thread_recall'").fetchall()
    assert rows
    assert "stored_txt_path" in rows[0]["value"]


def test_export_all_sessions(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    first = _seed_session()
    second = _seed_session()

    result = ta.export_all_sessions_to_txt()

    assert result["session_count"] == 2
    assert {e["session_id"] for e in result["exports"]} == {first, second}
    assert len(list((tmp_path / "thread_exports").glob("*.txt"))) == 2


def test_register_json_thread_file_converts_to_txt(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    src = tmp_path / "chatgpt_thread.json"
    src.write_text(json.dumps({
        "title": "ChatGPT thread",
        "source_system": "ChatGPT",
        "messages": [
            {"role": "user", "content": "question", "timestamp": "2026-06-30T00:00:00Z"},
            {"role": "assistant", "content": "answer", "timestamp": "2026-06-30T00:00:01Z"},
        ],
    }), encoding="utf-8")

    result = ta.register_thread_file(src, source_system="ChatGPT", title="ChatGPT thread")

    stored = Path(result["stored_txt_path"])
    assert stored.exists()
    assert stored.suffix == ".txt"
    assert "question" in stored.read_text(encoding="utf-8")
    assert Path(result["manifest_path"]).exists()


def test_import_thread_directory(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "a.txt").write_text("A thread", encoding="utf-8")
    (inbox / "b.md").write_text("B thread", encoding="utf-8")
    (inbox / "skip.exe").write_text("no", encoding="utf-8")

    result = ta.import_thread_directory(inbox, source_system="manual_drop")

    assert result["file_count"] == 2
    assert len(list((tmp_path / "thread_recall" / "imports").glob("*.txt"))) == 2


def test_append_ongoing_capture_is_explicit_and_receipted(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)

    receipt = ta.append_ongoing_capture(
        "Copied text from Gemini.",
        source_system="Gemini",
        source_ref="manual paste",
    )

    ongoing = tmp_path / "thread_recall" / "ongoing" / "ongoing_cross_system_thread.txt"
    assert ongoing.exists()
    assert "Copied text from Gemini." in ongoing.read_text(encoding="utf-8")
    assert receipt["capture_mode"] == "explicit_append_only"
    assert receipt["hidden_recording"] is False
    assert receipt["cloud_upload"] is False
    receipts = tmp_path / "thread_recall" / "receipts" / "ongoing_cross_system_thread_receipts.jsonl"
    assert receipts.exists()


def test_latest_session_id_uses_latest_message(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    old = _seed_session()
    new = _seed_session()

    assert ta.latest_session_id() == new
    assert old != new


def test_session_id_helpers_skip_malformed_rows(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    valid = _seed_session()
    with memory.get_conn() as con:
        con.execute(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            ("", "user", "bad legacy row", "2026-06-30T00:00:00"),
        )

    assert ta.latest_session_id() == valid
    assert ta.list_session_ids() == [valid]


def test_thread_recall_records_enter_companion_grounding(monkeypatch, tmp_path):
    db = tmp_path / "oracle_memory.db"
    with sqlite3.connect(db) as con:
        con.execute(
            "CREATE TABLE facts (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, key TEXT, value TEXT, updated_at TEXT)"
        )
        con.execute(
            "INSERT INTO facts (category, key, value, updated_at) VALUES (?, ?, ?, ?)",
            (
                "thread_recall",
                "ChatGPT:abc123",
                "THREAD_RECALL_RECORD\n"
                "title: ChatGPT thread\n"
                "source_system: ChatGPT\n"
                "stored_txt_path: C:\\Oracle\\ORACLE.AI-runtime\\Memory\\thread_recall\\imports\\chatgpt.txt\n"
                "sha256: abc123\n"
                "status: imported_thread_candidate\n"
                "canon_status: not_canon\n"
                "excerpt: This is a bounded recall excerpt.",
                "2026-06-30T00:00:00",
            ),
        )
    monkeypatch.setattr(cb, "MEMORY_DB_PATH", db)

    lines = cb._thread_recall_source_lines()

    joined = "\n".join(lines)
    assert "record_count: 1" in joined
    assert "source_system: ChatGPT" in joined
    assert "canon_status: not_canon" in joined
    assert "bounded recall excerpt" in joined
