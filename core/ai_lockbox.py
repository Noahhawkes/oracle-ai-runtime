"""Local .AI lockbox ingest and shorthand recall.

The lockbox is a read-only recall layer. It inventories reachable files, turns
supported text/docx previews into compact .AI capsules, and exposes a manifest
that front-end chat can search. It never uploads, deletes, moves, renames,
commits, pushes, promotes canon, or reads raw credential-risk content.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from root import ROOT as RUNTIME_ROOT
except Exception:  # pragma: no cover
    RUNTIME_ROOT = Path(__file__).resolve().parents[1]

LOCKBOX_DIR = RUNTIME_ROOT / "Memory" / "ai_lockbox"
CAPSULE_DIR = LOCKBOX_DIR / "capsules"
MANIFEST_FILE = LOCKBOX_DIR / "manifest.jsonl"
RECEIPT_FILE = LOCKBOX_DIR / "receipts.jsonl"
LATEST_STATUS_FILE = LOCKBOX_DIR / "latest_status.json"

SCHEMA_VERSION = "oracle.ai_lockbox.v1"
MAX_INGEST_LIMIT = 500
DEFAULT_INGEST_LIMIT = 25
MAX_SCAN_FILES = 50_000
MAX_CONTEXT_CHARS = 1600

# Tests may override this. In normal runtime, roots come from file_recall.
DEFAULT_ROOTS: list[Path] | None = None

STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "have", "you",
    "your", "are", "was", "were", "will", "what", "when", "where", "how",
    "why", "not", "but", "all", "can", "into", "about", "then", "than",
    "they", "them", "there", "their", "been", "being", "does", "did",
    "has", "had", "his", "her", "hers", "our", "out", "use", "using",
}


class AiLockboxError(ValueError):
    """Raised when a lockbox request is invalid."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _ensure_dirs() -> None:
    CAPSULE_DIR.mkdir(parents=True, exist_ok=True)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            item = json.loads(line)
            if isinstance(item, dict):
                rows.append(item)
        except Exception:
            continue
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, ensure_ascii=True) + "\n")


def _roots() -> list[Path]:
    if DEFAULT_ROOTS is not None:
        roots = DEFAULT_ROOTS
    else:
        try:
            from file_recall import allowed_roots

            roots = allowed_roots()
        except Exception:
            roots = [RUNTIME_ROOT, Path.home()]
    out: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        try:
            resolved = Path(root).resolve()
            key = str(resolved).lower()
            if key in seen or not resolved.exists():
                continue
            seen.add(key)
            out.append(resolved)
        except Exception:
            continue
    return out


def _skip_dir(name: str) -> bool:
    try:
        from file_recall import NOISE_DIR_NAMES

        return name.lower() in NOISE_DIR_NAMES
    except Exception:
        return name.lower() in {".git", "node_modules", "__pycache__", ".venv", "venv"}


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False


def _supported(path: Path) -> bool:
    try:
        from file_recall import DOCX_EXTS, TEXT_EXTS

        return path.suffix.lower() in (TEXT_EXTS | DOCX_EXTS)
    except Exception:
        return path.suffix.lower() in {".ai", ".md", ".txt", ".json", ".jsonl", ".py", ".docx"}


def _credential_risk(path: Path) -> str | None:
    try:
        from file_recall import secret_risk_reason

        return secret_risk_reason(path)
    except Exception:
        text = str(path).lower()
        if any(token in text for token in ("password", "secret", "token", ".env", "credential", "id_rsa")):
            return "sensitive filename pattern"
    return None


def _read_supported(path: Path) -> dict[str, Any] | None:
    try:
        from file_recall import DOCX_EXTS, TEXT_EXTS, _read_docx_text, _read_text_file
    except Exception:
        return None
    if _credential_risk(path):
        return None
    ext = path.suffix.lower()
    if ext in DOCX_EXTS:
        text = _read_docx_text(path)
    elif ext in TEXT_EXTS:
        text = _read_text_file(path)
    else:
        return None
    try:
        st = path.stat()
    except OSError:
        return None
    return {
        "ok": True,
        "path": str(path),
        "name": path.name,
        "size": st.st_size,
        "modified": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
        "text_preview": text,
    }


def _iter_supported_files(query: str = ""):
    terms = [term.lower() for term in re.findall(r"[A-Za-z0-9_\-]{2,}", query or "")]
    seen = 0
    lockbox_root = LOCKBOX_DIR
    for root in _roots():
        for dirpath, dirnames, filenames in os.walk(root, topdown=True):
            dirnames[:] = [
                d for d in dirnames
                if not _skip_dir(d) and not _is_under(Path(dirpath) / d, lockbox_root)
            ]
            for filename in filenames:
                seen += 1
                if seen > MAX_SCAN_FILES:
                    return
                path = Path(dirpath) / filename
                if _is_under(path, lockbox_root):
                    continue
                path_l = str(path).lower()
                if terms and not all(term in path_l for term in terms):
                    continue
                if _credential_risk(path) or not _supported(path):
                    continue
                yield path


def _top_terms(text: str, limit: int = 18) -> list[str]:
    words = [
        word.lower()
        for word in re.findall(r"[A-Za-z][A-Za-z0-9_\-]{2,}", text or "")
        if word.lower() not in STOPWORDS
    ]
    counts = Counter(words)
    return [word for word, _count in counts.most_common(limit)]


def _signal_lines(text: str, limit: int = 6) -> list[str]:
    pieces = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    out: list[str] = []
    seen: set[str] = set()
    for piece in pieces:
        cleaned = _clean_text(piece)
        if len(cleaned) < 24:
            continue
        key = cleaned[:120].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned[:220])
        if len(out) >= limit:
            break
    return out


def ai_shorthand(
    *,
    source_path: str,
    text: str,
    size: int = 0,
    modified: str = "",
    source_sha256: str | None = None,
) -> str:
    """Translate a readable source preview into compact .AI shorthand."""

    path = str(source_path)
    source_hash = source_sha256 or _sha256_text(text)
    record_id = source_hash[:16]
    terms = _top_terms(text)
    signals = _signal_lines(text)
    payload = {
        "path": path,
        "name": Path(path).name,
        "sha256": source_hash,
        "size": size,
        "modified": modified,
    }
    return "\n".join([
        f".AI:LOCKBOX_SOURCE/{record_id}",
        "",
        "@SOURCE " + json.dumps(payload, ensure_ascii=True, sort_keys=True),
        "@RECALL " + json.dumps({
            "mode": "read_only_ai_shorthand",
            "canon_status": "candidate",
            "promotion_status": "not_promoted",
            "topic_terms": terms,
        }, ensure_ascii=True, sort_keys=True),
        "@SIGNALS " + json.dumps(signals, ensure_ascii=True),
        "@BOUNDARY " + json.dumps([
            "source-derived shorthand, not canon",
            "raw credential-risk values not ingested",
            "no write/delete/move/rename/upload/send/execute",
            "Noah.Physical holds final correction authority",
        ], ensure_ascii=True),
        "",
    ])


def _capsule_path(record_id: str) -> Path:
    return CAPSULE_DIR / f"{record_id}.ai"


def capsule_for_file(path: str | Path) -> dict[str, Any]:
    _ensure_dirs()
    target = Path(path).expanduser()
    if not target.is_absolute():
        target = RUNTIME_ROOT / target
    try:
        target = target.resolve()
    except OSError:
        pass
    read = _read_supported(target)
    if not read or not read.get("ok"):
        raise AiLockboxError(f"unsupported or unreadable file for .AI shorthand: {target}")
    text = str(read.get("text_preview") or "")
    source_sha = _sha256_text(text)
    record_id = source_sha[:16]
    capsule_text = ai_shorthand(
        source_path=str(target),
        text=text,
        size=int(read.get("size") or 0),
        modified=str(read.get("modified") or ""),
        source_sha256=source_sha,
    )
    capsule_path = _capsule_path(record_id)
    capsule_path.write_text(capsule_text, encoding="utf-8")
    row = {
        "record_id": record_id,
        "schema_version": SCHEMA_VERSION,
        "source_path": str(target),
        "name": target.name,
        "extension": target.suffix.lower(),
        "source_sha256": source_sha,
        "capsule_path": str(capsule_path),
        "capsule_sha256": _sha256_text(capsule_text),
        "size": int(read.get("size") or 0),
        "modified": read.get("modified"),
        "terms": _top_terms(text),
        "canon_status": "candidate",
        "promotion_status": "not_promoted",
        "created_at": _now(),
        "boundary": "read-only .AI shorthand capsule; source-derived; no canon promotion",
    }
    _append_jsonl(MANIFEST_FILE, row)
    return row


def build_lockbox(query: str = "", *, limit: int = DEFAULT_INGEST_LIMIT) -> dict[str, Any]:
    _ensure_dirs()
    bounded_limit = max(1, min(int(limit or DEFAULT_INGEST_LIMIT), MAX_INGEST_LIMIT))
    created: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    seen_paths: set[str] = {str(row.get("source_path")) for row in _jsonl(MANIFEST_FILE)}

    for path in _iter_supported_files(query):
        key = str(path)
        if key in seen_paths:
            continue
        try:
            created.append(capsule_for_file(path))
            seen_paths.add(key)
        except Exception as exc:
            errors.append({"path": key, "error": f"{type(exc).__name__}: {exc}"})
        if len(created) >= bounded_limit:
            break

    sensitive_count = 0
    try:
        from file_recall import sensitive_inventory

        sensitive_count = int(sensitive_inventory(query, limit=25, write_receipt=False).get("result_count") or 0)
    except Exception:
        sensitive_count = 0

    receipt = {
        "receipt_kind": "ai_lockbox_ingest_receipt",
        "schema_version": SCHEMA_VERSION,
        "timestamp": _now(),
        "query": _clean_text(query),
        "created_count": len(created),
        "error_count": len(errors),
        "sensitive_metadata_matches": sensitive_count,
        "capsule_paths": [row["capsule_path"] for row in created],
        "manifest_path": str(MANIFEST_FILE),
        "boundary": {
            "read_only": True,
            "ai_shorthand": True,
            "raw_secret_ingest": False,
            "write_source_files": False,
            "external_send": False,
            "canon_promotion": False,
        },
    }
    receipt["receipt_hash_sha256"] = _sha256_text(json.dumps(receipt, sort_keys=True, ensure_ascii=True))
    _append_jsonl(RECEIPT_FILE, receipt)
    status = status_payload()
    status["latest_receipt"] = receipt
    _write_json(LATEST_STATUS_FILE, status)
    return {
        "ok": True,
        "operation_type": "ai_lockbox_ingest",
        "created_count": len(created),
        "errors": errors[:10],
        "created": created,
        "sensitive_metadata_matches": sensitive_count,
        "manifest_path": str(MANIFEST_FILE),
        "receipt_path": str(RECEIPT_FILE),
        "boundary": receipt["boundary"],
    }


def status_payload() -> dict[str, Any]:
    _ensure_dirs()
    manifest = _jsonl(MANIFEST_FILE)
    receipts = _jsonl(RECEIPT_FILE)
    return {
        "ok": True,
        "operation_type": "ai_lockbox_status",
        "schema_version": SCHEMA_VERSION,
        "capsule_count": len(manifest),
        "receipt_count": len(receipts),
        "manifest_path": str(MANIFEST_FILE),
        "capsule_dir": str(CAPSULE_DIR),
        "roots": [str(root) for root in _roots()],
        "latest_receipt": receipts[-1] if receipts else None,
        "boundary": "local read-only .AI shorthand recall; source files unchanged; no external send",
    }


def search_lockbox(query: str, *, limit: int = 8) -> dict[str, Any]:
    q = _clean_text(query)
    if not q:
        raise AiLockboxError("query is required")
    terms = [term.lower() for term in re.findall(r"[A-Za-z0-9_\-]{2,}", q)]
    bounded_limit = max(1, min(int(limit or 8), 25))
    hits: list[dict[str, Any]] = []
    for row in reversed(_jsonl(MANIFEST_FILE)):
        haystack = " ".join([
            str(row.get("source_path") or ""),
            str(row.get("name") or ""),
            " ".join(row.get("terms") or []),
        ]).lower()
        capsule_text = ""
        try:
            capsule_text = Path(str(row.get("capsule_path"))).read_text(encoding="utf-8", errors="replace")
            haystack += "\n" + capsule_text.lower()
        except Exception:
            pass
        if terms and not all(term in haystack for term in terms):
            continue
        hit = dict(row)
        hit["ai_preview"] = capsule_text[:900]
        hits.append(hit)
        if len(hits) >= bounded_limit:
            break
    return {
        "ok": True,
        "operation_type": "ai_lockbox_search",
        "query": q,
        "result_count": len(hits),
        "results": hits,
        "manifest_path": str(MANIFEST_FILE),
        "boundary": "searched local .AI shorthand capsules only",
    }


def context_block(user_text: str, *, max_chars: int = MAX_CONTEXT_CHARS) -> str:
    words = [
        word for word in re.findall(r"[A-Za-z0-9_\-]{3,}", str(user_text or ""))
        if word.lower() not in STOPWORDS
    ]
    if not words:
        return ""
    queries: list[str] = []
    for size in (5, 3, 2, 1):
        if len(words) >= size:
            q = " ".join(words[:size])
            if q not in queries:
                queries.append(q)
    hits: list[dict[str, Any]] = []
    for query in queries:
        try:
            result = search_lockbox(query, limit=3)
            hits = result.get("results") or []
        except Exception:
            hits = []
        if hits:
            break
    if not hits:
        return ""
    lines = ["[AI_LOCKBOX - local .AI shorthand recall capsules; cite source_path when used]"]
    for hit in hits:
        lines.append(f"- {hit.get('name')} ({hit.get('source_path')})")
        preview = str(hit.get("ai_preview") or "").replace("\n", " ")
        if preview:
            lines.append(f"  {preview[:260]}")
    return "\n".join(lines)[:max_chars]


def parse_lockbox_request(text: str) -> dict[str, str] | None:
    raw = str(text or "").strip()
    lower = raw.lower()
    if not raw:
        return None
    if lower in {"/ai-lockbox", "/ai-lockbox-status", "/lockbox", "/recall-status"}:
        return {"mode": "status", "value": ""}
    for prefix in ("/ai-lockbox-ingest ", "/lockbox-ingest ", "/ai-ingest "):
        if lower.startswith(prefix):
            return {"mode": "ingest", "value": raw[len(prefix):].strip()}
    if lower in {"/ai-lockbox-ingest", "/lockbox-ingest", "/ai-ingest"}:
        return {"mode": "ingest", "value": ""}
    for prefix in ("/ai-lockbox-search ", "/lockbox-search ", "/ai-recall "):
        if lower.startswith(prefix):
            return {"mode": "search", "value": raw[len(prefix):].strip()}
    for prefix in ("/ai-shorthand ", "/ai-capsule "):
        if lower.startswith(prefix):
            return {"mode": "capsule", "value": raw[len(prefix):].strip()}
    return None


def format_result(result: dict[str, Any]) -> str:
    op = result.get("operation_type")
    if op == "ai_lockbox_status":
        latest = result.get("latest_receipt") or {}
        return "\n".join([
            "AI LOCKBOX STATUS",
            "boundary: local read-only .AI shorthand recall; no source mutation; no external send",
            f"capsule_count: {result.get('capsule_count', 0)}",
            f"receipt_count: {result.get('receipt_count', 0)}",
            f"manifest_path: {result.get('manifest_path')}",
            f"capsule_dir: {result.get('capsule_dir')}",
            f"latest_created_count: {latest.get('created_count', 0) if latest else 0}",
        ])
    if op == "ai_lockbox_ingest":
        lines = [
            "AI LOCKBOX INGEST",
            "boundary: read-only ingest into .AI shorthand capsules; source files unchanged",
            f"created_count: {result.get('created_count', 0)}",
            f"sensitive_metadata_matches: {result.get('sensitive_metadata_matches', 0)}",
            f"manifest_path: {result.get('manifest_path')}",
            f"receipt_path: {result.get('receipt_path')}",
        ]
        for row in (result.get("created") or [])[:8]:
            lines.append(f"- {row.get('name')} -> {row.get('capsule_path')}")
        return "\n".join(lines)
    if op == "ai_lockbox_search":
        lines = [
            "AI LOCKBOX SEARCH",
            f"query: {result.get('query')}",
            f"result_count: {result.get('result_count', 0)}",
        ]
        for idx, row in enumerate(result.get("results") or [], 1):
            lines.append(f"{idx}. {row.get('name')}")
            lines.append(f"   source_path: {row.get('source_path')}")
            lines.append(f"   capsule_path: {row.get('capsule_path')}")
            preview = str(row.get("ai_preview") or "").splitlines()
            if preview:
                lines.append(f"   {preview[0][:220]}")
        if not result.get("results"):
            lines.append("no_results: build the lockbox or try a different query")
        return "\n".join(lines)
    return json.dumps(result, indent=2, ensure_ascii=True)
