"""Index the canonical OBS/media source thread into ORACLE durable memory.

The JSONL source thread remains authoritative. Rows inserted here are derived,
searchable candidates with provenance back to an immutable event id.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memory import DB_PATH, get_conn, insert_durable_fact

DEFAULT_THREAD = Path(r"C:\Oracle\state\threads\oracle_obs_media_thread_v1.jsonl")
THREAD_ID = "oracle_obs_media_thread_v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_bridge_schema() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS source_thread_ingest (
                event_id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                memory_id INTEGER NOT NULL,
                source_path TEXT,
                ingested_at TEXT NOT NULL
            )
            """
        )


def _duration(value: Any) -> str:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return "unknown duration"
    minutes, seconds = divmod(int(round(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    return f"{minutes}m {seconds}s"


def _stream_summary(streams: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for stream in streams:
        kind = str(stream.get("type") or "stream")
        codec = str(stream.get("codec") or "unknown codec")
        if kind == "video":
            size = ""
            if stream.get("width") and stream.get("height"):
                size = f" {stream['width']}x{stream['height']}"
            parts.append(f"video {codec}{size}")
        elif kind == "audio":
            parts.append(f"audio {codec}")
    return ", ".join(parts[:4]) or "stream details unavailable"


def fact_from_event(record: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    event_id = str(record.get("event_id") or "").strip()
    if not event_id:
        raise ValueError("source-thread event is missing event_id")
    event_type = str(record.get("event_type") or "unknown")
    content = record.get("content") if isinstance(record.get("content"), dict) else {}
    source_path = str(record.get("source_path") or "")

    if event_type == "media_metadata":
        filename = str(content.get("filename") or Path(source_path).name or "unknown media")
        if content.get("cloud_placeholder"):
            fact = (
                f"Media inventory observed {filename} at {source_path}. "
                f"It is an online-only cloud placeholder, size {content.get('size_bytes', 'unknown')} bytes; "
                "container content was not downloaded or read."
            )
        else:
            metadata = content.get("container_metadata")
            metadata = metadata if isinstance(metadata, dict) else {}
            device = " ".join(
                str(metadata.get(key) or "").strip()
                for key in ("com.apple.quicktime.make", "com.apple.quicktime.model")
            ).strip()
            created = (
                metadata.get("com.apple.quicktime.creationdate")
                or metadata.get("creation_time")
                or content.get("created_utc")
                or "unknown date"
            )
            fact = (
                f"Media metadata observed {filename} at {source_path}; "
                f"created {created}; duration {_duration(content.get('duration_s'))}; "
                f"{_stream_summary(content.get('streams') or [])}"
            )
            if device:
                fact += f"; device {device}"
            fact += "."
        source_type = "observed"
        confidence = 0.95
        transform = "filesystem_and_container_metadata_summary"
    elif event_type == "obs_transcript_segment":
        lines = content.get("transcript_lines")
        lines = lines if isinstance(lines, list) else []
        transcript = " ".join(str(line).strip() for line in lines if str(line).strip())
        transcript = transcript[:4000]
        fact = (
            f"OBS transcript candidate from {content.get('recording') or Path(source_path).name}, "
            f"offset {content.get('offset_start_s', '?')}s-{content.get('offset_end_s', '?')}s: "
            f"{transcript or '[no speech extracted]'}"
        )
        source_type = "generated"
        confidence = 0.65 if transcript else 0.4
        transform = "local_speech_to_text_segment"
    else:
        fact = f"Source-thread event {event_type} from {source_path}: {json.dumps(content, ensure_ascii=False)[:3000]}"
        source_type = "generated"
        confidence = 0.5
        transform = "generic_source_thread_index"

    provenance = {
        "source_type": source_type,
        "source_id": event_id,
        "observed_at": str(record.get("ts_utc") or _utc_now()),
        "confidence": confidence,
        "transformation_history": [
            {
                "operation": transform,
                "source_thread": str(record.get("thread_id") or THREAD_ID),
                "source_path": source_path,
                "canon_status": str(record.get("canon_status") or "candidate"),
            }
        ],
        "canonical_status": "candidate",
        "approval_status": "pending",
    }
    return fact, provenance


def ingest_event(record: dict[str, Any]) -> dict[str, Any]:
    ensure_bridge_schema()
    event_id = str(record.get("event_id") or "").strip()
    if not event_id:
        raise ValueError("source-thread event is missing event_id")
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT memory_id FROM source_thread_ingest WHERE event_id=?",
            (event_id,),
        ).fetchone()
        if existing:
            return {"status": "already_indexed", "event_id": event_id, "memory_id": existing["memory_id"]}
        durable = conn.execute(
            "SELECT id FROM durable_facts WHERE source_id=? ORDER BY id LIMIT 1",
            (event_id,),
        ).fetchone()
    if durable:
        memory_id = int(durable["id"])
    else:
        fact, provenance = fact_from_event(record)
        memory_id = int(insert_durable_fact(fact, provenance))
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO source_thread_ingest
              (event_id, thread_id, event_type, memory_id, source_path, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                str(record.get("thread_id") or THREAD_ID),
                str(record.get("event_type") or "unknown"),
                memory_id,
                str(record.get("source_path") or ""),
                _utc_now(),
            ),
        )
    return {"status": "indexed", "event_id": event_id, "memory_id": memory_id}


def sync_thread(path: Path = DEFAULT_THREAD, *, limit: int | None = None) -> dict[str, Any]:
    ensure_bridge_schema()
    if not path.exists():
        return {
            "ok": False,
            "thread_path": str(path),
            "indexed": 0,
            "already_indexed": 0,
            "errors": [{"error": "thread_not_found"}],
        }
    indexed = 0
    already = 0
    errors: list[dict[str, Any]] = []
    scanned = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            if limit is not None and scanned >= limit:
                break
            scanned += 1
            try:
                result = ingest_event(json.loads(line))
                if result["status"] == "indexed":
                    indexed += 1
                else:
                    already += 1
            except Exception as exc:
                errors.append({
                    "line": line_number,
                    "error": f"{type(exc).__name__}: {exc}",
                })
    return {
        "ok": not errors,
        "thread_id": THREAD_ID,
        "thread_path": str(path),
        "memory_db": str(DB_PATH),
        "scanned": scanned,
        "indexed": indexed,
        "already_indexed": already,
        "errors": errors,
    }


def bridge_status(path: Path = DEFAULT_THREAD) -> dict[str, Any]:
    ensure_bridge_schema()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n, MAX(ingested_at) AS latest FROM source_thread_ingest WHERE thread_id=?",
            (THREAD_ID,),
        ).fetchone()
    source_records = 0
    if path.exists():
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            source_records = sum(1 for line in handle if line.strip())
    indexed = int(row["n"] or 0)
    return {
        "ok": path.exists() and indexed == source_records,
        "thread_id": THREAD_ID,
        "thread_path": str(path),
        "source_records": source_records,
        "indexed_records": indexed,
        "remaining": max(0, source_records - indexed),
        "latest_ingested_at": row["latest"],
    }

