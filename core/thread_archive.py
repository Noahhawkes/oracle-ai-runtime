"""Governed thread archive and recall registry.

This module gives ORACLE a local-only way to:

- export SQLite chat sessions to TXT files,
- register TXT/MD/JSON thread artifacts as recall records,
- append explicitly supplied cross-system text into one ongoing thread log.

It deliberately does not watch keystrokes, scrape browser tabs, read hidden
windows, upload to cloud, commit to git, or promote anything to canon. Raw
threads become imported-thread recall candidates with receipts and file hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from root import ROOT
except Exception:  # pragma: no cover
    ROOT = Path(__file__).resolve().parents[1]

DB_PATH = ROOT / "Memory" / "oracle_memory.db"
THREAD_EXPORTS_DIR = ROOT / "thread_exports" / "sqlite_sessions"
THREAD_RECALL_DIR = ROOT / "Memory" / "thread_recall"
RECALL_IMPORTS_DIR = THREAD_RECALL_DIR / "imports"
RECALL_MANIFESTS_DIR = THREAD_RECALL_DIR / "manifests"
RECALL_RECEIPTS_DIR = THREAD_RECALL_DIR / "receipts"
ONGOING_DIR = THREAD_RECALL_DIR / "ongoing"
ONGOING_THREAD_PATH = ONGOING_DIR / "ongoing_cross_system_thread.txt"
ONGOING_RECEIPT_JSONL = RECALL_RECEIPTS_DIR / "ongoing_cross_system_thread_receipts.jsonl"

ALLOWED_IMPORT_EXTENSIONS = {".txt", ".md", ".json"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe_slug(value: str, *, fallback: str = "thread") -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip()).strip("._-")
    return slug[:120] or fallback


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    db = Path(db_path or DB_PATH)
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    return con


def _load_messages(session_id: int, *, db_path: Path | None = None) -> list[dict[str, Any]]:
    with _connect(db_path) as con:
        rows = con.execute(
            "select id, session_id, role, content, timestamp from messages where session_id=? order by id asc",
            (session_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def latest_session_id(*, db_path: Path | None = None) -> int | None:
    with _connect(db_path) as con:
        rows = con.execute("select session_id from messages order by id desc limit 50").fetchall()
    for row in rows:
        try:
            return int(row["session_id"])
        except (TypeError, ValueError):
            continue
    return None


def list_session_ids(*, db_path: Path | None = None) -> list[int]:
    with _connect(db_path) as con:
        rows = con.execute(
            "select session_id from messages group by session_id order by max(id) asc"
        ).fetchall()
    session_ids: list[int] = []
    for row in rows:
        try:
            session_ids.append(int(row["session_id"]))
        except (TypeError, ValueError):
            continue
    return session_ids


def _format_thread_txt(
    *,
    title: str,
    source_system: str,
    source_ref: str,
    messages: Iterable[dict[str, Any]],
    exported_at: str,
) -> str:
    msg_list = list(messages)
    serial = json.dumps(msg_list, ensure_ascii=False, sort_keys=True).encode("utf-8")
    digest = _sha256_bytes(serial)
    lines = [
        "ORACLE THREAD TXT EXPORT",
        f"title: {title}",
        f"source_system: {source_system}",
        f"source_ref: {source_ref}",
        f"exported_at: {exported_at}",
        f"message_count: {len(msg_list)}",
        f"messages_json_sha256: {digest}",
        "status: imported_thread_candidate",
        "canon_status: not_canon",
        "boundary: local-only TXT export; recall candidate pointer, not automatic canon memory",
        "",
        "THREAD",
        "",
    ]
    for idx, message in enumerate(msg_list, start=1):
        role = str(message.get("role") or "unknown").upper()
        ts = str(message.get("timestamp") or "")
        content = str(message.get("content") or "").rstrip()
        lines.extend([
            f"[{idx:06d}] {ts} {role}",
            content,
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def export_session_to_txt(
    session_id: int | None = None,
    *,
    db_path: Path | None = None,
    output_dir: Path | None = None,
    register_recall: bool = True,
) -> dict[str, Any]:
    """Export one SQLite session to TXT and optionally register recall metadata."""
    sid = session_id if session_id is not None else latest_session_id(db_path=db_path)
    if sid is None:
        raise ValueError("No SQLite messages found to export.")
    messages = _load_messages(int(sid), db_path=db_path)
    if not messages:
        raise ValueError(f"Session {sid} has no messages.")

    out_dir = Path(output_dir or THREAD_EXPORTS_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    exported_at = _now()
    filename = f"oracle_session_{sid}_{_stamp()}.txt"
    text = _format_thread_txt(
        title=f"ORACLE session {sid}",
        source_system="ORACLE",
        source_ref=f"sqlite_session:{sid}",
        messages=messages,
        exported_at=exported_at,
    )
    path = out_dir / filename
    path.write_text(text, encoding="utf-8")
    result = {
        "ok": True,
        "operation": "export_session_to_txt",
        "session_id": int(sid),
        "message_count": len(messages),
        "path": str(path.resolve()),
        "sha256": _sha256_bytes(text.encode("utf-8")),
        "cloud_upload": False,
        "git_commit": False,
        "git_push": False,
        "canon_promotion": False,
    }
    if register_recall:
        result["recall"] = register_thread_file(
            path,
            source_system="ORACLE",
            source_ref=f"sqlite_session:{sid}",
            title=f"ORACLE session {sid}",
        )
    return result


def export_all_sessions_to_txt(
    *,
    db_path: Path | None = None,
    output_dir: Path | None = None,
    register_recall: bool = True,
    max_sessions: int | None = None,
) -> dict[str, Any]:
    sids = list_session_ids(db_path=db_path)
    if max_sessions is not None:
        sids = sids[-int(max_sessions):]
    exports = [
        export_session_to_txt(
            sid,
            db_path=db_path,
            output_dir=output_dir,
            register_recall=register_recall,
        )
        for sid in sids
    ]
    return {
        "ok": True,
        "operation": "export_all_sessions_to_txt",
        "session_count": len(exports),
        "exports": exports,
        "cloud_upload": False,
        "git_commit": False,
        "git_push": False,
    }


def _json_thread_to_txt(path: Path) -> str | None:
    data = _read_json(path)
    if not data:
        return None
    messages = data.get("messages") or data.get("history")
    if not isinstance(messages, list):
        return None
    title = str(data.get("title") or f"Imported JSON thread {path.name}")
    source_system = str(data.get("source_system") or "imported_json")
    source_ref = str(data.get("source_ref") or path.name)
    return _format_thread_txt(
        title=title,
        source_system=source_system,
        source_ref=source_ref,
        messages=[m for m in messages if isinstance(m, dict)],
        exported_at=_now(),
    )


def _read_thread_as_txt(path: Path) -> str:
    ext = path.suffix.lower()
    if ext not in ALLOWED_IMPORT_EXTENSIONS:
        raise ValueError(f"Unsupported thread import extension: {ext}")
    if ext == ".json":
        converted = _json_thread_to_txt(path)
        if converted:
            return converted
    return path.read_text(encoding="utf-8", errors="replace")


def register_thread_file(
    path: str | Path,
    *,
    source_system: str = "manual_import",
    source_ref: str = "",
    title: str | None = None,
    source_authority: str = "Noah.Physical",
) -> dict[str, Any]:
    """Copy a thread artifact into recall storage and register a SQLite fact.

    This writes a pointer and excerpt into the facts table. It does not promote
    raw transcript text to canon.
    """
    src = Path(path)
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(str(src))
    text = _read_thread_as_txt(src)
    raw = text.encode("utf-8")
    digest = _sha256_bytes(raw)
    title = title or src.stem
    safe_name = f"{_safe_slug(source_system)}_{_safe_slug(title)}_{digest[:12]}.txt"
    RECALL_IMPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stored = RECALL_IMPORTS_DIR / safe_name
    stored.write_text(text, encoding="utf-8")

    manifest = {
        "manifest_kind": "thread_recall_record",
        "recorded_at": _now(),
        "title": title,
        "source_system": source_system,
        "source_ref": source_ref or str(src),
        "source_authority": source_authority,
        "original_path": str(src.resolve()),
        "stored_txt_path": str(stored.resolve()),
        "sha256": digest,
        "size_bytes": len(raw),
        "status": "imported_thread_candidate",
        "canon_status": "not_canon",
        "recall_permission": "recall_for_context_with_label",
        "cloud_upload": False,
        "git_commit": False,
        "git_push": False,
        "raw_text_promoted_to_canon": False,
    }
    RECALL_MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = RECALL_MANIFESTS_DIR / f"{_safe_slug(title)}_{digest[:12]}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")

    excerpt = " ".join(text.split())[:1200]
    fact_value = (
        "THREAD_RECALL_RECORD\n"
        f"title: {title}\n"
        f"source_system: {source_system}\n"
        f"source_ref: {source_ref or str(src)}\n"
        f"stored_txt_path: {stored.resolve()}\n"
        f"manifest_path: {manifest_path.resolve()}\n"
        f"sha256: {digest}\n"
        "status: imported_thread_candidate\n"
        "canon_status: not_canon\n"
        f"excerpt: {excerpt}"
    )
    try:
        import memory

        memory.init_db()
        memory.upsert_fact("thread_recall", f"{_safe_slug(source_system)}:{digest[:12]}", fact_value)
    except Exception as exc:
        manifest["memory_fact_error"] = f"{type(exc).__name__}: {exc}"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "ok": True,
        "operation": "register_thread_file",
        "title": title,
        "source_system": source_system,
        "stored_txt_path": str(stored.resolve()),
        "manifest_path": str(manifest_path.resolve()),
        "sha256": digest,
        "cloud_upload": False,
        "git_commit": False,
        "git_push": False,
        "canon_promotion": False,
    }


def import_thread_directory(
    directory: str | Path,
    *,
    source_system: str = "manual_import",
    pattern: str = "*",
) -> dict[str, Any]:
    root = Path(directory)
    if not root.exists() or not root.is_dir():
        raise NotADirectoryError(str(root))
    candidates = [
        path for path in sorted(root.glob(pattern))
        if path.is_file() and path.suffix.lower() in ALLOWED_IMPORT_EXTENSIONS
    ]
    imports = [
        register_thread_file(path, source_system=source_system, source_ref=str(path), title=path.stem)
        for path in candidates
    ]
    return {
        "ok": True,
        "operation": "import_thread_directory",
        "directory": str(root.resolve()),
        "file_count": len(imports),
        "imports": imports,
    }


def append_ongoing_capture(
    text: str,
    *,
    source_system: str,
    source_ref: str = "",
    source_authority: str = "Noah.Physical",
) -> dict[str, Any]:
    """Append explicitly supplied text to the ongoing cross-system thread.

    This function only records text handed to it. It is not a watcher and not a
    keylogger.
    """
    clean = str(text or "").strip()
    if not clean:
        raise ValueError("Cannot append empty thread capture text.")
    ONGOING_DIR.mkdir(parents=True, exist_ok=True)
    RECALL_RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    if not ONGOING_THREAD_PATH.exists():
        ONGOING_THREAD_PATH.write_text(
            "ONGOING CROSS-SYSTEM THREAD\n"
            "capture_mode: explicit_append_only\n"
            "boundary: no hidden keystroke logging, no stealth browser scraping, no cloud upload\n"
            "canon_status: not_canon\n\n",
            encoding="utf-8",
        )
    block = (
        f"\n--- CAPTURE {_now()} ---\n"
        f"source_system: {source_system}\n"
        f"source_ref: {source_ref}\n"
        f"source_authority: {source_authority}\n\n"
        f"{clean}\n"
    )
    with ONGOING_THREAD_PATH.open("a", encoding="utf-8") as fh:
        fh.write(block)
    raw = ONGOING_THREAD_PATH.read_bytes()
    digest = _sha256_bytes(raw)
    receipt = {
        "operation": "append_ongoing_cross_system_thread",
        "recorded_at": _now(),
        "source_system": source_system,
        "source_ref": source_ref,
        "source_authority": source_authority,
        "stored_txt_path": str(ONGOING_THREAD_PATH.resolve()),
        "sha256_after_append": digest,
        "capture_mode": "explicit_append_only",
        "cloud_upload": False,
        "git_commit": False,
        "git_push": False,
        "hidden_recording": False,
    }
    with ONGOING_RECEIPT_JSONL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(receipt, ensure_ascii=True, sort_keys=True) + "\n")
    try:
        import memory

        memory.init_db()
        memory.upsert_fact(
            "thread_recall",
            "ongoing_cross_system_thread_latest",
            (
                "ONGOING_CROSS_SYSTEM_THREAD\n"
                f"stored_txt_path: {ONGOING_THREAD_PATH.resolve()}\n"
                f"sha256_after_append: {digest}\n"
                "capture_mode: explicit_append_only\n"
                "boundary: no hidden keystroke logging, no stealth browser scraping, no cloud upload\n"
                f"latest_source_system: {source_system}\n"
                f"latest_source_ref: {source_ref}\n"
            ),
        )
    except Exception as exc:
        receipt["memory_fact_error"] = f"{type(exc).__name__}: {exc}"
    return receipt


def status() -> dict[str, Any]:
    manifests = list(RECALL_MANIFESTS_DIR.glob("*.json")) if RECALL_MANIFESTS_DIR.exists() else []
    exports = list(THREAD_EXPORTS_DIR.glob("*.txt")) if THREAD_EXPORTS_DIR.exists() else []
    ongoing_exists = ONGOING_THREAD_PATH.exists()
    return {
        "thread_exports_dir": str(THREAD_EXPORTS_DIR.resolve()),
        "thread_recall_dir": str(THREAD_RECALL_DIR.resolve()),
        "exported_sqlite_txt_count": len(exports),
        "recall_manifest_count": len(manifests),
        "ongoing_thread_path": str(ONGOING_THREAD_PATH.resolve()),
        "ongoing_thread_exists": ongoing_exists,
        "ongoing_thread_bytes": ONGOING_THREAD_PATH.stat().st_size if ongoing_exists else 0,
        "capture_mode": "explicit_append_only",
        "cloud_upload": False,
        "hidden_recording": False,
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description="ORACLE governed thread archive")
    parser.add_argument("--export-session", type=int, help="Export one SQLite session id to TXT")
    parser.add_argument("--export-latest", action="store_true", help="Export latest SQLite session to TXT")
    parser.add_argument("--export-all", action="store_true", help="Export all SQLite sessions to TXT")
    parser.add_argument("--import-file", help="Register one TXT/MD/JSON thread file in recall")
    parser.add_argument("--import-dir", help="Register all TXT/MD/JSON files in a directory")
    parser.add_argument("--source-system", default="manual_import")
    parser.add_argument("--source-ref", default="")
    parser.add_argument("--append", help="Append explicit text to ongoing cross-system thread")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if args.export_all:
        print(json.dumps(export_all_sessions_to_txt(), indent=2))
    elif args.export_latest:
        print(json.dumps(export_session_to_txt(), indent=2))
    elif args.export_session is not None:
        print(json.dumps(export_session_to_txt(args.export_session), indent=2))
    elif args.import_file:
        print(json.dumps(register_thread_file(args.import_file, source_system=args.source_system, source_ref=args.source_ref), indent=2))
    elif args.import_dir:
        print(json.dumps(import_thread_directory(args.import_dir, source_system=args.source_system), indent=2))
    elif args.append:
        print(json.dumps(append_ongoing_capture(args.append, source_system=args.source_system, source_ref=args.source_ref), indent=2))
    else:
        print(json.dumps(status(), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
