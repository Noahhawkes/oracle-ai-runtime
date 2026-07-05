"""ORACLE Thread Capture Architecture.

Black-box transcript custody for AI-era conversations.

This module transports explicit user-supplied thread artifacts into ORACLE as:

- raw transcript/file custody copies,
- parsed transcript JSON,
- source manifest JSONL records,
- custody receipts with SHA-256 hashes,
- searchable JSONL message index rows.

It does not scrape accounts, watch browsers, mutate source files, upload,
delete, sync, commit, push, or promote anything to canon. Captured material is
evidence first: canon_status is always "candidate" here and promotion_status is
always "not_promoted".
"""

from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import mimetypes
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from root import ROOT
except Exception:  # pragma: no cover
    ROOT = Path(__file__).resolve().parents[1]

THREAD_INGEST_DIR = ROOT / "Memory" / "thread_ingest"
THREAD_EXPORTS_DIR = ROOT / "thread_exports"
RAW_TRANSCRIPTS_DIR = THREAD_INGEST_DIR / "raw_transcripts"
PARSED_TRANSCRIPTS_DIR = THREAD_INGEST_DIR / "parsed_transcripts"
SOURCE_MANIFESTS_DIR = THREAD_INGEST_DIR / "source_manifests"
CUSTODY_RECEIPTS_DIR = THREAD_INGEST_DIR / "custody_receipts"
SOURCE_MANIFEST_JSONL = SOURCE_MANIFESTS_DIR / "source_manifest.jsonl"
SEARCH_INDEX_JSONL = THREAD_INGEST_DIR / "search_index.jsonl"
MEMORY_DB_PATH = ROOT / "Memory" / "oracle_memory.db"

SUPPORTED_SOURCE_SYSTEMS = {
    "ChatGPT",
    "Claude",
    "Claude Code",
    "Codex",
    "Gemini",
    "Grok",
    "GitHub Copilot",
    "ORACLE",
    "Google Drive",
    "Drive export",
    "screenshot",
    "PDF",
    "HTML",
    "manual_paste",
}

TEXT_EXTENSIONS = {".txt", ".md", ".json", ".jsonl", ".html", ".htm", ".csv", ".log", ".ai"}
BINARY_EVIDENCE_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
}

AI_SPEAKERS = {
    "assistant",
    "ai",
    "chatgpt",
    "claude",
    "claude code",
    "codex",
    "gemini",
    "grok",
    "github copilot",
    "oracle",
}

KNOWN_HUMAN_SPEAKERS = {"noah", "noah.physical", "noah a. hawkes", "noah hawkes"}

SPEAKER_LABEL_RE = re.compile(
    r"^\s*(?P<speaker>Noah(?:\.Physical| A\. Hawkes| Hawkes)?|User|Human|Assistant|AI|"
    r"ChatGPT|Claude(?: Code)?|Codex|Gemini|Grok|GitHub Copilot|ORACLE|System|Tool|Developer)"
    r"\s*[:：]\s*(?P<content>.*)$",
    re.IGNORECASE,
)

THREAD_ARCHIVE_ROW_RE = re.compile(
    r"^\[(?P<index>\d{6})\]\s+(?P<stamp>.*?)\s+(?P<speaker>[A-Z_]+)\s*$"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe_slug(value: str, *, fallback: str = "thread") -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip()).strip("._-")
    return slug[:100] or fallback


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _ensure_dirs() -> None:
    for path in (
        THREAD_INGEST_DIR,
        THREAD_EXPORTS_DIR,
        RAW_TRANSCRIPTS_DIR,
        PARSED_TRANSCRIPTS_DIR,
        SOURCE_MANIFESTS_DIR,
        CUSTODY_RECEIPTS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def _json_dump(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")


def _receipt_hash(payload: dict[str, Any]) -> str:
    stable = {k: v for k, v in payload.items() if k != "receipt_hash_sha256"}
    raw = json.dumps(stable, ensure_ascii=True, sort_keys=True, default=str).encode("utf-8")
    return _sha256_bytes(raw)


def _decode_text(raw: bytes) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "cp1252"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8-replace"


def _plain_text_from_html(text: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "\n", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|li|h[1-6]|tr)>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _plain_text_from_pdf(raw: bytes) -> tuple[str, str]:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as exc:
        return "", f"pypdf_unavailable:{type(exc).__name__}"
    try:
        reader = PdfReader(io.BytesIO(raw))
        pages = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                pages.append("")
        text = "\n".join(page for page in pages if page.strip()).strip()
        return text, f"pdf_text_extracted_pages={len(reader.pages)}"
    except Exception as exc:
        return "", f"pdf_text_extract_error:{type(exc).__name__}: {exc}"


def _load_json_text(text: str) -> Any | None:
    try:
        return json.loads(text)
    except Exception:
        return None


def _message_text_from_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(_message_text_from_content(item) for item in content if item is not None).strip()
    if isinstance(content, dict):
        if isinstance(content.get("parts"), list):
            return "\n".join(str(part) for part in content["parts"] if part is not None).strip()
        for key in ("text", "content", "value"):
            if key in content:
                return _message_text_from_content(content.get(key))
        if isinstance(content.get("messages"), list):
            return _message_text_from_content(content.get("messages"))
        return json.dumps(content, ensure_ascii=False, sort_keys=True)
    return str(content)


def _role_from_json_message(message: dict[str, Any]) -> str:
    author = message.get("author")
    if isinstance(author, dict):
        role = author.get("role") or author.get("name")
        if role:
            return str(role)
    for key in ("role", "speaker", "name", "author"):
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return "unknown"


def _timestamp_from_json_message(message: dict[str, Any]) -> str | None:
    for key in ("timestamp", "created_at", "create_time", "time", "date"):
        value = message.get(key)
        if value is None:
            continue
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(float(value), timezone.utc).isoformat().replace("+00:00", "Z")
            except Exception:
                return str(value)
        text = str(value).strip()
        if text:
            return text
    return None


def _json_messages(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        candidates = data
    elif isinstance(data, dict) and isinstance(data.get("messages"), list):
        candidates = data["messages"]
    elif isinstance(data, dict) and isinstance(data.get("history"), list):
        candidates = data["history"]
    elif isinstance(data, dict) and isinstance(data.get("mapping"), dict):
        nodes = []
        for node in data["mapping"].values():
            if isinstance(node, dict) and isinstance(node.get("message"), dict):
                message = dict(node["message"])
                if node.get("id") and "id" not in message:
                    message["id"] = node.get("id")
                nodes.append(message)
        return sorted(nodes, key=lambda m: str(m.get("create_time") or m.get("timestamp") or ""))
    else:
        return []
    return [item for item in candidates if isinstance(item, dict)]


def _normalize_speaker(speaker: str) -> str:
    value = re.sub(r"\s+", " ", str(speaker or "unknown").strip())
    if not value:
        return "unknown"
    lowered = value.lower()
    known = {
        "user": "User",
        "human": "Human",
        "assistant": "Assistant",
        "system": "System",
        "tool": "Tool",
        "developer": "Developer",
        "chatgpt": "ChatGPT",
        "claude": "Claude",
        "claude code": "Claude Code",
        "codex": "Codex",
        "gemini": "Gemini",
        "grok": "Grok",
        "github copilot": "GitHub Copilot",
        "oracle": "ORACLE",
        "noah": "Noah.Physical",
        "noah.physical": "Noah.Physical",
        "noah a. hawkes": "Noah A. Hawkes",
        "noah hawkes": "Noah A. Hawkes",
    }
    return known.get(lowered, value)


def _token_origin_and_authority(speaker: str) -> tuple[str, str]:
    lower = speaker.strip().lower()
    if lower in KNOWN_HUMAN_SPEAKERS:
        return "human_submitted_text", "Noah.Physical"
    if lower in AI_SPEAKERS:
        return "ai_generated_text", "unknown"
    if lower in {"system", "developer"}:
        return "system_or_developer_instruction", "unknown"
    if lower == "tool":
        return "tool_runtime_output", "unknown"
    if lower in {"user", "human"}:
        return "user_channel_unknown_author", "unknown"
    return "unknown", "unknown"


def _claim_type(text: str, speaker: str) -> str:
    lower = (text or "").lower()
    if not text.strip():
        return "empty"
    if "```" in text:
        return "code_or_artifact"
    if "?" in text and len(text) < 800:
        return "question"
    if re.search(r"\b(todo|fix|build|implement|wire|patch|test|next step|action)\b", lower):
        return "task_or_instruction"
    if re.search(r"\b(doctrine|law|rule|canon|authority|provenance|authorship)\b", lower):
        return "doctrine_or_governance_claim"
    if re.search(r"\b(i think|maybe|inference|infer|seems|probably)\b", lower):
        return "inference_or_hypothesis"
    if speaker.strip().lower() in AI_SPEAKERS:
        return "ai_response"
    return "conversation"


def _message_record(
    *,
    message_index: int,
    speaker: str,
    message_text: str,
    timestamp_if_known: str | None = None,
) -> dict[str, Any]:
    normalized = _normalize_speaker(speaker)
    token_origin, authorial_authority = _token_origin_and_authority(normalized)
    return {
        "message_index": int(message_index),
        "speaker": normalized,
        "message_text": message_text,
        "timestamp_if_known": timestamp_if_known,
        "token_origin": token_origin,
        "authorial_authority": authorial_authority,
        "claim_type": _claim_type(message_text, normalized),
        "canon_status": "candidate",
        "promotion_status": "not_promoted",
    }


def _parse_labeled_text(text: str) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    current_speaker: str | None = None
    current_timestamp: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_speaker, current_timestamp, current_lines
        if current_speaker is None and not current_lines:
            return
        body = "\n".join(current_lines).strip()
        if body or current_speaker:
            messages.append(
                _message_record(
                    message_index=len(messages) + 1,
                    speaker=current_speaker or "unknown",
                    message_text=body,
                    timestamp_if_known=current_timestamp,
                )
            )
        current_speaker = None
        current_timestamp = None
        current_lines = []

    for line in text.splitlines():
        archive_match = THREAD_ARCHIVE_ROW_RE.match(line)
        if archive_match:
            flush()
            current_speaker = archive_match.group("speaker").title().replace("_", " ")
            stamp = archive_match.group("stamp").strip()
            current_timestamp = stamp or None
            continue
        label_match = SPEAKER_LABEL_RE.match(line)
        if label_match:
            flush()
            current_speaker = label_match.group("speaker")
            current_timestamp = None
            first = label_match.group("content")
            current_lines = [first] if first else []
            continue
        if current_speaker is None and not messages and not line.strip():
            continue
        current_lines.append(line)

    flush()
    if messages:
        return messages
    stripped = text.strip()
    if not stripped:
        return []
    return [
        _message_record(
            message_index=1,
            speaker="unknown",
            message_text=stripped,
            timestamp_if_known=None,
        )
    ]


def _parse_json_transcript(text: str) -> list[dict[str, Any]]:
    data = _load_json_text(text)
    messages = _json_messages(data)
    out: list[dict[str, Any]] = []
    for message in messages:
        content = message.get("content")
        if content is None and "message" in message:
            content = message.get("message")
        if content is None and "text" in message:
            content = message.get("text")
        body = _message_text_from_content(content).strip()
        if not body:
            continue
        out.append(
            _message_record(
                message_index=len(out) + 1,
                speaker=_role_from_json_message(message),
                message_text=body,
                timestamp_if_known=_timestamp_from_json_message(message),
            )
        )
    return out


def _parse_transcript_text(text: str, *, extension: str) -> tuple[list[dict[str, Any]], str]:
    ext = extension.lower()
    parse_text = text
    if ext in {".html", ".htm"}:
        parse_text = _plain_text_from_html(text)
    if ext == ".json":
        parsed = _parse_json_transcript(parse_text)
        if parsed:
            return parsed, "json_messages"
    parsed = _parse_labeled_text(parse_text)
    return parsed, "speaker_label_text" if parsed else "no_messages_detected"


def _source_thread_id(source_thread_id: str | None, raw_sha256: str) -> str:
    clean = str(source_thread_id or "").strip()
    return clean or f"thread_{raw_sha256[:16]}"


def _participants(messages: list[dict[str, Any]]) -> list[str]:
    return sorted({m["speaker"] for m in messages if m.get("speaker")})


def _participant_summaries(messages: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    known: set[str] = set()
    unknown: set[str] = set()
    for message in messages:
        speaker = str(message.get("speaker") or "unknown")
        if message.get("authorial_authority") == "Noah.Physical":
            known.add(speaker)
        else:
            unknown.add(speaker)
    return sorted(known), sorted(unknown)


def _metadata(
    *,
    source_system: str,
    source_thread_id: str,
    captured_by: str,
    capture_method: str,
    captured_at: str,
    raw_file_path: Path,
    raw_sha256: str,
    messages: list[dict[str, Any]],
    original_source_path: str = "",
    parse_status: str = "",
) -> dict[str, Any]:
    participants = _participants(messages)
    known_authors, unknown_authors = _participant_summaries(messages)
    return {
        "schema_version": "thread_capture.v1",
        "source_system": source_system,
        "source_thread_id": source_thread_id,
        "captured_by": captured_by,
        "capture_method": capture_method,
        "captured_at": captured_at,
        "original_source_path": original_source_path,
        "raw_file_path": str(raw_file_path.resolve()),
        "raw_sha256": raw_sha256,
        "message_count": len(messages),
        "participants": participants,
        "known_authors": known_authors,
        "unknown_authors": unknown_authors,
        "contains_ai_generated_text": any(m.get("token_origin") == "ai_generated_text" for m in messages),
        "contains_user_submitted_text": any(str(m.get("token_origin", "")).startswith("user_channel") or m.get("token_origin") == "human_submitted_text" for m in messages),
        "parse_status": parse_status,
        "canon_status": "candidate",
        "promotion_status": "not_promoted",
        "raw_text_promoted_to_canon": False,
        "transport_equals_origin": False,
        "cloud_upload": False,
        "git_commit": False,
        "git_push": False,
    }


def _copy_raw_bytes(
    *,
    raw: bytes,
    source_system: str,
    source_thread_id: str,
    raw_sha256: str,
    extension: str,
) -> Path:
    source_dir = RAW_TRANSCRIPTS_DIR / _safe_slug(source_system)
    source_dir.mkdir(parents=True, exist_ok=True)
    ext = extension if extension.startswith(".") else f".{extension}" if extension else ".bin"
    path = source_dir / f"{_safe_slug(source_thread_id)}_{raw_sha256[:12]}{ext}"
    path.write_bytes(raw)
    return path


def _write_parsed(
    *,
    source_system: str,
    source_thread_id: str,
    raw_sha256: str,
    metadata: dict[str, Any],
    messages: list[dict[str, Any]],
) -> Path:
    source_dir = PARSED_TRANSCRIPTS_DIR / _safe_slug(source_system)
    source_dir.mkdir(parents=True, exist_ok=True)
    path = source_dir / f"{_safe_slug(source_thread_id)}_{raw_sha256[:12]}.json"
    payload = {
        "metadata": metadata,
        "messages": messages,
    }
    _json_dump(path, payload)
    return path


def _write_manifest(metadata: dict[str, Any], parsed_path: Path, receipt_path: Path) -> dict[str, Any]:
    manifest = dict(metadata)
    manifest.update(
        {
            "manifest_kind": "thread_capture_source_manifest",
            "parsed_transcript_path": str(parsed_path.resolve()),
            "custody_receipt_path": str(receipt_path.resolve()),
            "search_index_path": str(SEARCH_INDEX_JSONL.resolve()),
        }
    )
    _append_jsonl(SOURCE_MANIFEST_JSONL, manifest)
    return manifest


def _write_search_index(metadata: dict[str, Any], parsed_path: Path, messages: list[dict[str, Any]]) -> int:
    count = 0
    for message in messages:
        row = {
            "source_system": metadata["source_system"],
            "source_thread_id": metadata["source_thread_id"],
            "captured_at": metadata["captured_at"],
            "raw_sha256": metadata["raw_sha256"],
            "parsed_transcript_path": str(parsed_path.resolve()),
            "raw_file_path": metadata["raw_file_path"],
            "message_index": message["message_index"],
            "speaker": message["speaker"],
            "message_text": message["message_text"],
            "timestamp_if_known": message.get("timestamp_if_known"),
            "token_origin": message["token_origin"],
            "authorial_authority": message["authorial_authority"],
            "claim_type": message["claim_type"],
            "canon_status": "candidate",
            "promotion_status": "not_promoted",
        }
        _append_jsonl(SEARCH_INDEX_JSONL, row)
        count += 1
    return count


def _write_receipt(
    *,
    source_system: str,
    source_thread_id: str,
    captured_by: str,
    capture_method: str,
    raw_file_path: Path,
    raw_sha256: str,
    parsed_path: Path,
    metadata: dict[str, Any],
    search_index_rows_written: int,
) -> Path:
    receipt = {
        "receipt_kind": "thread_capture_custody_receipt",
        "schema_version": "thread_capture.v1",
        "operation": "ingest_thread_capture",
        "recorded_at": _now(),
        "source_system": source_system,
        "source_thread_id": source_thread_id,
        "captured_by": captured_by,
        "capture_method": capture_method,
        "raw_file_path": str(raw_file_path.resolve()),
        "raw_sha256": raw_sha256,
        "parsed_transcript_path": str(parsed_path.resolve()),
        "source_manifest_jsonl": str(SOURCE_MANIFEST_JSONL.resolve()),
        "search_index_jsonl": str(SEARCH_INDEX_JSONL.resolve()),
        "search_index_rows_written": search_index_rows_written,
        "message_count": metadata["message_count"],
        "participants": metadata["participants"],
        "known_authors": metadata["known_authors"],
        "unknown_authors": metadata["unknown_authors"],
        "contains_ai_generated_text": metadata["contains_ai_generated_text"],
        "contains_user_submitted_text": metadata["contains_user_submitted_text"],
        "canon_status": "candidate",
        "promotion_status": "not_promoted",
        "cloud_upload": False,
        "git_commit": False,
        "git_push": False,
        "source_file_mutated": False,
        "account_scrape_performed": False,
    }
    receipt["receipt_hash_sha256"] = _receipt_hash(receipt)
    source_dir = CUSTODY_RECEIPTS_DIR / _safe_slug(source_system)
    source_dir.mkdir(parents=True, exist_ok=True)
    path = source_dir / f"{_safe_slug(source_thread_id)}_{raw_sha256[:12]}_receipt.json"
    _json_dump(path, receipt)
    return path


def _upsert_memory_pointer(metadata: dict[str, Any], parsed_path: Path, receipt_path: Path) -> None:
    try:
        import memory

        memory.init_db()
        excerpt = ""
        try:
            parsed = json.loads(parsed_path.read_text(encoding="utf-8"))
            messages = parsed.get("messages") or []
            if messages:
                excerpt = " ".join(str(messages[0].get("message_text") or "").split())[:800]
        except Exception:
            excerpt = ""
        value = (
            "THREAD_CAPTURE_RECORD\n"
            f"source_system: {metadata['source_system']}\n"
            f"source_thread_id: {metadata['source_thread_id']}\n"
            f"capture_method: {metadata['capture_method']}\n"
            f"captured_at: {metadata['captured_at']}\n"
            f"raw_file_path: {metadata['raw_file_path']}\n"
            f"raw_sha256: {metadata['raw_sha256']}\n"
            f"parsed_transcript_path: {parsed_path.resolve()}\n"
            f"custody_receipt_path: {receipt_path.resolve()}\n"
            f"message_count: {metadata['message_count']}\n"
            "canon_status: candidate\n"
            "promotion_status: not_promoted\n"
            f"excerpt: {excerpt}"
        )
        key = f"{_safe_slug(metadata['source_system'])}:{metadata['raw_sha256'][:12]}"
        memory.upsert_fact("thread_capture", key, value)
    except Exception:
        return


def ingest_bytes(
    raw: bytes,
    *,
    source_system: str,
    source_thread_id: str | None = None,
    capture_method: str,
    captured_by: str = "Noah.Physical",
    original_source_path: str = "",
    filename_hint: str = "",
) -> dict[str, Any]:
    """Ingest an explicit raw transcript/file payload into custody."""
    _ensure_dirs()
    captured_at = _now()
    raw_sha256 = _sha256_bytes(raw)
    thread_id = _source_thread_id(source_thread_id, raw_sha256)
    ext = Path(filename_hint).suffix.lower() if filename_hint else ".txt"
    if not ext:
        ext = ".txt"
    raw_file_path = _copy_raw_bytes(
        raw=raw,
        source_system=source_system,
        source_thread_id=thread_id,
        raw_sha256=raw_sha256,
        extension=ext,
    )

    messages: list[dict[str, Any]] = []
    parse_status = "binary_stored_raw_only"
    if ext.lower() in TEXT_EXTENSIONS:
        text, encoding = _decode_text(raw)
        messages, parse_kind = _parse_transcript_text(text, extension=ext)
        parse_status = f"{parse_kind}; encoding={encoding}"
    elif ext.lower() == ".pdf":
        pdf_text, pdf_status = _plain_text_from_pdf(raw)
        if pdf_text:
            messages, parse_kind = _parse_transcript_text(pdf_text, extension=".txt")
            parse_status = f"{parse_kind}; {pdf_status}"
        else:
            messages = []
            parse_status = f"pdf_stored_raw_only; {pdf_status}"
    elif ext.lower() in BINARY_EVIDENCE_EXTENSIONS:
        messages = []
        parse_status = "visual_or_binary_evidence_stored_raw_only; ocr_not_enabled"
    else:
        mime, _ = mimetypes.guess_type(filename_hint)
        if mime and mime.startswith("text/"):
            text, encoding = _decode_text(raw)
            messages, parse_kind = _parse_transcript_text(text, extension=".txt")
            parse_status = f"{parse_kind}; encoding={encoding}; mime={mime}"

    metadata = _metadata(
        source_system=source_system,
        source_thread_id=thread_id,
        captured_by=captured_by,
        capture_method=capture_method,
        captured_at=captured_at,
        raw_file_path=raw_file_path,
        raw_sha256=raw_sha256,
        messages=messages,
        original_source_path=original_source_path,
        parse_status=parse_status,
    )
    parsed_path = _write_parsed(
        source_system=source_system,
        source_thread_id=thread_id,
        raw_sha256=raw_sha256,
        metadata=metadata,
        messages=messages,
    )
    search_rows = _write_search_index(metadata, parsed_path, messages)
    receipt_path = _write_receipt(
        source_system=source_system,
        source_thread_id=thread_id,
        captured_by=captured_by,
        capture_method=capture_method,
        raw_file_path=raw_file_path,
        raw_sha256=raw_sha256,
        parsed_path=parsed_path,
        metadata=metadata,
        search_index_rows_written=search_rows,
    )
    manifest = _write_manifest(metadata, parsed_path, receipt_path)
    _upsert_memory_pointer(metadata, parsed_path, receipt_path)
    return {
        "ok": True,
        "operation": "ingest_thread_capture",
        "metadata": metadata,
        "raw_file_path": str(raw_file_path.resolve()),
        "parsed_transcript_path": str(parsed_path.resolve()),
        "custody_receipt_path": str(receipt_path.resolve()),
        "source_manifest_jsonl": str(SOURCE_MANIFEST_JSONL.resolve()),
        "search_index_jsonl": str(SEARCH_INDEX_JSONL.resolve()),
        "source_manifest_record": manifest,
        "search_index_rows_written": search_rows,
        "canon_status": "candidate",
        "promotion_status": "not_promoted",
        "cloud_upload": False,
        "git_commit": False,
        "git_push": False,
    }


def ingest_file(
    path: str | Path,
    *,
    source_system: str,
    source_thread_id: str | None = None,
    capture_method: str = "export_file",
    captured_by: str = "Noah.Physical",
) -> dict[str, Any]:
    src = Path(path)
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(str(src))
    raw = src.read_bytes()
    return ingest_bytes(
        raw,
        source_system=source_system,
        source_thread_id=source_thread_id,
        capture_method=capture_method,
        captured_by=captured_by,
        original_source_path=str(src.resolve()),
        filename_hint=src.name,
    )


def ingest_directory(
    directory: str | Path,
    *,
    source_system: str,
    capture_method: str = "directory_import",
    captured_by: str = "Noah.Physical",
    pattern: str = "*",
    recursive: bool = False,
    max_files: int | None = None,
) -> dict[str, Any]:
    root = Path(directory)
    if not root.exists() or not root.is_dir():
        raise NotADirectoryError(str(root))
    iterator = root.rglob(pattern) if recursive else root.glob(pattern)
    files = [path for path in sorted(iterator) if path.is_file()]
    if max_files is not None:
        files = files[: int(max_files)]
    ingests = [
        ingest_file(
            path,
            source_system=source_system,
            source_thread_id=path.stem,
            capture_method=capture_method,
            captured_by=captured_by,
        )
        for path in files
    ]
    return {
        "ok": True,
        "operation": "ingest_thread_capture_directory",
        "directory": str(root.resolve()),
        "file_count": len(files),
        "ingested_count": len(ingests),
        "first_receipt_path": ingests[0]["custody_receipt_path"] if ingests else None,
        "last_receipt_path": ingests[-1]["custody_receipt_path"] if ingests else None,
        "source_system": source_system,
        "capture_method": capture_method,
        "recursive": recursive,
        "canon_status": "candidate",
        "promotion_status": "not_promoted",
        "cloud_upload": False,
        "git_commit": False,
        "git_push": False,
    }


def ingest_paste(
    text: str,
    *,
    source_system: str,
    source_thread_id: str | None = None,
    captured_by: str = "Noah.Physical",
) -> dict[str, Any]:
    clean = str(text or "")
    if not clean.strip():
        raise ValueError("Cannot ingest empty pasted transcript.")
    return ingest_bytes(
        clean.encode("utf-8"),
        source_system=source_system,
        source_thread_id=source_thread_id,
        capture_method="manual_paste",
        captured_by=captured_by,
        original_source_path="manual_paste",
        filename_hint="manual_paste.txt",
    )


def status() -> dict[str, Any]:
    raw_count = len([p for p in RAW_TRANSCRIPTS_DIR.rglob("*") if p.is_file()]) if RAW_TRANSCRIPTS_DIR.exists() else 0
    parsed_count = len(list(PARSED_TRANSCRIPTS_DIR.rglob("*.json"))) if PARSED_TRANSCRIPTS_DIR.exists() else 0
    receipt_count = len(list(CUSTODY_RECEIPTS_DIR.rglob("*.json"))) if CUSTODY_RECEIPTS_DIR.exists() else 0
    manifest_rows = 0
    if SOURCE_MANIFEST_JSONL.exists():
        manifest_rows = len([line for line in SOURCE_MANIFEST_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()])
    index_rows = 0
    if SEARCH_INDEX_JSONL.exists():
        index_rows = len([line for line in SEARCH_INDEX_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()])
    return {
        "thread_ingest_dir": str(THREAD_INGEST_DIR.resolve()),
        "thread_exports_dir": str(THREAD_EXPORTS_DIR.resolve()),
        "raw_transcripts_dir": str(RAW_TRANSCRIPTS_DIR.resolve()),
        "parsed_transcripts_dir": str(PARSED_TRANSCRIPTS_DIR.resolve()),
        "source_manifests_dir": str(SOURCE_MANIFESTS_DIR.resolve()),
        "custody_receipts_dir": str(CUSTODY_RECEIPTS_DIR.resolve()),
        "source_manifest_jsonl": str(SOURCE_MANIFEST_JSONL.resolve()),
        "search_index_jsonl": str(SEARCH_INDEX_JSONL.resolve()),
        "raw_artifact_count": raw_count,
        "parsed_transcript_count": parsed_count,
        "custody_receipt_count": receipt_count,
        "source_manifest_rows": manifest_rows,
        "search_index_rows": index_rows,
        "canon_status_for_new_captures": "candidate",
        "promotion_status_for_new_captures": "not_promoted",
        "account_scraping": False,
        "cloud_upload": False,
    }


def search_index(query: str, *, limit: int = 10) -> list[dict[str, Any]]:
    terms = [term.lower() for term in re.findall(r"[A-Za-z0-9_.'-]+", query or "") if len(term) > 1]
    if not terms or not SEARCH_INDEX_JSONL.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in SEARCH_INDEX_JSONL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        haystack = " ".join(str(row.get(k) or "") for k in ("source_system", "speaker", "message_text", "claim_type")).lower()
        if all(term in haystack for term in terms):
            rows.append(row)
            if len(rows) >= limit:
                break
    return rows


def _compact_result(result: dict[str, Any]) -> dict[str, Any]:
    metadata = result.get("metadata") or {}
    return {
        "ok": result.get("ok"),
        "operation": result.get("operation"),
        "source_system": metadata.get("source_system"),
        "source_thread_id": metadata.get("source_thread_id"),
        "capture_method": metadata.get("capture_method"),
        "raw_file_path": result.get("raw_file_path"),
        "raw_sha256": metadata.get("raw_sha256"),
        "parsed_transcript_path": result.get("parsed_transcript_path"),
        "custody_receipt_path": result.get("custody_receipt_path"),
        "source_manifest_jsonl": result.get("source_manifest_jsonl"),
        "search_index_jsonl": result.get("search_index_jsonl"),
        "message_count": metadata.get("message_count"),
        "participants": metadata.get("participants"),
        "known_authors": metadata.get("known_authors"),
        "unknown_authors": metadata.get("unknown_authors"),
        "contains_ai_generated_text": metadata.get("contains_ai_generated_text"),
        "contains_user_submitted_text": metadata.get("contains_user_submitted_text"),
        "search_index_rows_written": result.get("search_index_rows_written"),
        "canon_status": "candidate",
        "promotion_status": "not_promoted",
        "cloud_upload": False,
        "git_commit": False,
        "git_push": False,
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description="ORACLE Thread Capture Architecture")
    parser.add_argument("--ingest-file", help="Path to exported transcript/evidence file")
    parser.add_argument("--ingest-dir", help="Directory of exported transcript/evidence files")
    parser.add_argument("--ingest-paste", help="Transcript text supplied on the command line")
    parser.add_argument("--ingest-stdin", action="store_true", help="Read pasted transcript text from stdin")
    parser.add_argument("--source-system", default="manual_paste")
    parser.add_argument("--source-thread-id", default="")
    parser.add_argument("--capture-method", default="")
    parser.add_argument("--captured-by", default="Noah.Physical")
    parser.add_argument("--pattern", default="*")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--max-files", type=int)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--search", help="Search captured transcript message index")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    if args.status:
        print(json.dumps(status(), indent=2))
        return 0
    if args.search:
        print(json.dumps(search_index(args.search, limit=args.limit), indent=2))
        return 0
    if args.ingest_file:
        result = ingest_file(
            args.ingest_file,
            source_system=args.source_system,
            source_thread_id=args.source_thread_id or None,
            capture_method=args.capture_method or "export_file",
            captured_by=args.captured_by,
        )
        print(json.dumps(_compact_result(result), indent=2))
        return 0
    if args.ingest_dir:
        result = ingest_directory(
            args.ingest_dir,
            source_system=args.source_system,
            capture_method=args.capture_method or "directory_import",
            captured_by=args.captured_by,
            pattern=args.pattern,
            recursive=args.recursive,
            max_files=args.max_files,
        )
        print(json.dumps(result, indent=2))
        return 0
    if args.ingest_paste is not None:
        result = ingest_paste(
            args.ingest_paste,
            source_system=args.source_system,
            source_thread_id=args.source_thread_id or None,
            captured_by=args.captured_by,
        )
        print(json.dumps(_compact_result(result), indent=2))
        return 0
    if args.ingest_stdin:
        text = sys.stdin.read()
        result = ingest_paste(
            text,
            source_system=args.source_system,
            source_thread_id=args.source_thread_id or None,
            captured_by=args.captured_by,
        )
        print(json.dumps(_compact_result(result), indent=2))
        return 0
    print(json.dumps(status(), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
