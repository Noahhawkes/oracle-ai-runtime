from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import media_thread_memory as bridge
import memory


def _event(event_id: str = "event-1") -> dict:
    return {
        "event_id": event_id,
        "thread_id": bridge.THREAD_ID,
        "ts_utc": "2026-07-29T12:00:00Z",
        "event_type": "media_metadata",
        "source_path": r"C:\Pictures\clip.mov",
        "canon_status": "candidate",
        "content": {
            "filename": "clip.mov",
            "duration_s": 65,
            "created_utc": "2026-07-29T11:00:00Z",
            "container_metadata": {
                "com.apple.quicktime.make": "Apple",
                "com.apple.quicktime.model": "iPhone",
            },
            "streams": [
                {"type": "video", "codec": "hevc", "width": 1920, "height": 1080},
                {"type": "audio", "codec": "aac"},
            ],
        },
    }


def test_fact_from_media_event_preserves_provenance() -> None:
    fact, provenance = bridge.fact_from_event(_event())
    assert "clip.mov" in fact
    assert "1m 5s" in fact
    assert "iPhone" in fact
    assert provenance["source_id"] == "event-1"
    assert provenance["canonical_status"] == "candidate"
    assert provenance["approval_status"] == "pending"


def test_sync_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "memory.db"
    monkeypatch.setattr(memory, "DB_PATH", db)
    monkeypatch.setattr(bridge, "DB_PATH", db)
    memory._FTS_AVAILABLE = None
    memory.init_db()

    thread = tmp_path / "thread.jsonl"
    thread.write_text(json.dumps(_event()) + "\n", encoding="utf-8")

    first = bridge.sync_thread(thread)
    second = bridge.sync_thread(thread)

    assert first["indexed"] == 1
    assert second["indexed"] == 0
    assert second["already_indexed"] == 1
    with memory.get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM durable_facts").fetchone()[0] == 1

