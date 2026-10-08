"""Quote-capable corpus packets for ORACLE.

This layer is different from Document Atlas and AI Lockbox:

* Document Atlas proves a source exists.
* AI Lockbox creates compact .AI shorthand summaries.
* Quote Corpus stores bounded exact excerpts with source hashes so ORACLE can
  cite Noah's words without pretending metadata is understanding.

Boundary: read-only source access, no source mutation, no external send, no
canon promotion. Credential-risk files and secret-looking content are skipped.
"""
from __future__ import annotations

import bisect
import hashlib
import html
import json
import os
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from root import ROOT as RUNTIME_ROOT
except Exception:  # pragma: no cover
    RUNTIME_ROOT = Path(__file__).resolve().parents[1]


QUOTE_DIR = RUNTIME_ROOT / "Memory" / "quote_corpus"
PACKET_DIR = QUOTE_DIR / "packets"
MANIFEST_FILE = QUOTE_DIR / "manifest.jsonl"
RECEIPT_FILE = QUOTE_DIR / "receipts.jsonl"
LATEST_STATUS_FILE = QUOTE_DIR / "latest_status.json"

SCHEMA_VERSION = "oracle.quote_corpus.v1"
DEFAULT_INGEST_LIMIT = 5
MAX_INGEST_LIMIT = 100
MAX_SCAN_FILES = 50_000
MAX_FILE_BYTES = 8_000_000
MAX_TEXT_CHARS = 240_000
DEFAULT_MAX_QUOTES_PER_FILE = 80
DEFAULT_QUOTE_CHARS = 900
MIN_QUOTE_CHARS = 80

TEXT_EXTS = {
    ".ai", ".md", ".markdown", ".txt", ".json", ".jsonl", ".csv", ".tsv",
    ".yaml", ".yml", ".log", ".xml", ".html", ".htm", ".py", ".js", ".ts",
    ".css", ".ini", ".cfg", ".toml", ".ps1", ".bat",
}
DOCX_EXTS = {".docx"}
SUPPORTED_EXTS = TEXT_EXTS | DOCX_EXTS

DEFAULT_ROOTS: list[Path] | None = None

STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "have", "you",
    "your", "are", "was", "were", "will", "what", "when", "where", "how",
    "why", "not", "but", "all", "can", "into", "about", "then", "than",
    "they", "them", "there", "their", "been", "being", "does", "did",
    "has", "had", "his", "her", "our", "out", "use", "using", "right",
    "now", "quote", "quotes", "source", "sources",
}

SECRET_CONTENT_RE = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"\bsk-[A-Za-z0-9_-]{12,}|"
    r"\bAKIA[0-9A-Z]{16}\b|"
    r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}|"
    r"\b(api[_-]?key|password|passwd|secret|token)\s*[:=]\s*[^\s]{8,})",
    re.IGNORECASE,
)


class QuoteCorpusError(ValueError):
    """Raised when quote corpus work would violate a boundary."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ensure_dirs() -> None:
    PACKET_DIR.mkdir(parents=True, exist_ok=True)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _clean_inline(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _normalize_text(value: str) -> str:
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, ensure_ascii=True) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def _roots() -> list[Path]:
    if DEFAULT_ROOTS is not None:
        candidates = DEFAULT_ROOTS
    else:
        try:
            from file_recall import allowed_roots

            candidates = allowed_roots()
        except Exception:
            candidates = [RUNTIME_ROOT, Path.home()]
    out: list[Path] = []
    seen: set[str] = set()
    for root in candidates:
        try:
            resolved = Path(root).resolve()
            key = str(resolved).lower()
            if key not in seen and resolved.exists():
                seen.add(key)
                out.append(resolved)
        except Exception:
            continue
    return out


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False


def _secret_risk(path: Path) -> str | None:
    try:
        from file_recall import secret_risk_reason

        return secret_risk_reason(path)
    except Exception:
        lowered = str(path).lower()
        if any(term in lowered for term in ("password", "secret", "token", ".env", "credential", "id_rsa")):
            return "sensitive filename pattern"
    return None


def _inside_allowed_root(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except Exception:
        return False
    for root in _roots():
        try:
            resolved.relative_to(root.resolve())
            return True
        except Exception:
            continue
    return False


def validate_source_path(path_text: str | Path) -> Path:
    value = str(path_text or "").strip().strip('"')
    if not value:
        raise QuoteCorpusError("path is required")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = RUNTIME_ROOT / path
    try:
        path = path.resolve()
    except OSError:
        pass
    if not _inside_allowed_root(path):
        raise QuoteCorpusError("path is outside ORACLE's read-only granted roots")
    if not path.exists():
        raise QuoteCorpusError("path does not exist")
    if not path.is_file():
        raise QuoteCorpusError("path is not a file")
    if _secret_risk(path):
        raise QuoteCorpusError("path is blocked by the secret/credential boundary")
    if path.suffix.lower() not in SUPPORTED_EXTS:
        raise QuoteCorpusError(f"unsupported file type for quote corpus: {path.suffix.lower() or 'none'}")
    return path


def _read_text_file(path: Path, *, max_chars: int = MAX_TEXT_CHARS) -> tuple[str, bool]:
    raw = path.read_bytes()
    truncated = len(raw) > MAX_FILE_BYTES
    raw = raw[:MAX_FILE_BYTES]
    text = raw.decode("utf-8", errors="replace")
    if len(text) > max_chars:
        truncated = True
        text = text[:max_chars]
    return _normalize_text(text), truncated


def _read_docx_text(path: Path, *, max_chars: int = MAX_TEXT_CHARS) -> tuple[str, bool]:
    try:
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml").decode("utf-8", errors="replace")
    except Exception as exc:
        raise QuoteCorpusError(f"docx text extraction failed: {type(exc).__name__}") from exc
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"</w:tab>", "\t", xml)
    text = html.unescape(re.sub(r"<[^>]+>", "", xml))
    text = _normalize_text(text)
    truncated = len(text) > max_chars
    if truncated:
        text = text[:max_chars]
    return text, truncated


def extract_text(path: Path, *, max_chars: int = MAX_TEXT_CHARS) -> tuple[str, bool]:
    ext = path.suffix.lower()
    if ext in TEXT_EXTS:
        return _read_text_file(path, max_chars=max_chars)
    if ext in DOCX_EXTS:
        return _read_docx_text(path, max_chars=max_chars)
    raise QuoteCorpusError(f"unsupported file type for quote corpus: {ext or 'none'}")


def _line_starts(text: str) -> list[int]:
    starts = [0]
    for match in re.finditer(r"\n", text):
        starts.append(match.end())
    return starts


def _line_number(starts: list[int], offset: int) -> int:
    return max(1, bisect.bisect_right(starts, offset))


def _paragraph_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    pos = 0
    for match in re.finditer(r"\n\s*\n+", text):
        start, end = pos, match.start()
        if _clean_inline(text[start:end]):
            ranges.append((start, end))
        pos = match.end()
    if _clean_inline(text[pos:]):
        ranges.append((pos, len(text)))
    if not ranges and text.strip():
        ranges.append((0, len(text)))
    return ranges


def _chunk_ranges(text: str, *, max_quote_chars: int = DEFAULT_QUOTE_CHARS) -> list[tuple[int, int]]:
    max_quote_chars = max(MIN_QUOTE_CHARS, int(max_quote_chars or DEFAULT_QUOTE_CHARS))
    ranges: list[tuple[int, int]] = []
    current_start: int | None = None
    current_end: int | None = None
    for start, end in _paragraph_ranges(text):
        if end - start > max_quote_chars:
            if current_start is not None and current_end is not None:
                ranges.append((current_start, current_end))
                current_start = current_end = None
            cursor = start
            while cursor < end:
                stop = min(end, cursor + max_quote_chars)
                if stop < end:
                    split_at = max(text.rfind(". ", cursor, stop), text.rfind("\n", cursor, stop))
                    if split_at > cursor + MIN_QUOTE_CHARS:
                        stop = split_at + 1
                ranges.append((cursor, stop))
                cursor = stop
            continue
        if current_start is None:
            current_start, current_end = start, end
            continue
        if end - current_start <= max_quote_chars:
            current_end = end
            continue
        ranges.append((current_start, current_end or end))
        current_start, current_end = start, end
    if current_start is not None and current_end is not None:
        ranges.append((current_start, current_end))
    return ranges


def _source_metadata(path: Path, text: str, truncated: bool) -> dict[str, Any]:
    st = path.stat()
    return {
        "source_path": str(path),
        "name": path.name,
        "extension": path.suffix.lower(),
        "size": st.st_size,
        "modified": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_sha256": _sha256_file(path),
        "text_sha256": _sha256_text(text),
        "text_chars_indexed": len(text),
        "truncated": truncated,
    }


def _privacy_status(path: Path) -> str:
    lowered = str(path).lower()
    if any(term in lowered for term in ("public", "website", "publish", "github")):
        return "public_candidate"
    return "private_candidate"


def build_source_packet(
    path_text: str | Path,
    *,
    max_quotes: int = DEFAULT_MAX_QUOTES_PER_FILE,
    max_quote_chars: int = DEFAULT_QUOTE_CHARS,
) -> dict[str, Any]:
    """Read one source and return quote packet data without writing it."""
    path = validate_source_path(path_text)
    text, truncated = extract_text(path)
    if not text.strip():
        raise QuoteCorpusError("source contains no extractable text")
    if SECRET_CONTENT_RE.search(text):
        return {
            "ok": False,
            "operation_type": "quote_corpus_packet",
            "status": "gated_sensitive_content",
            "source_path": str(path),
            "quote_count": 0,
            "boundary": "secret-looking content detected; no quote packet written",
        }
    meta = _source_metadata(path, text, truncated)
    source_id = meta["text_sha256"][:16]
    starts = _line_starts(text)
    quotes: list[dict[str, Any]] = []
    for index, (start, end) in enumerate(_chunk_ranges(text, max_quote_chars=max_quote_chars), 1):
        quote_text = text[start:end].strip()
        if len(_clean_inline(quote_text)) < MIN_QUOTE_CHARS:
            continue
        quote_id = _sha256_text(f"{meta['text_sha256']}:{start}:{end}:{quote_text}")[:20]
        quotes.append({
            "quote_id": quote_id,
            "quote_index": index,
            "quote_text": quote_text,
            "char_start": start,
            "char_end": end,
            "line_start": _line_number(starts, start),
            "line_end": _line_number(starts, max(start, end - 1)),
            "quote_sha256": _sha256_text(quote_text),
        })
        if len(quotes) >= max(1, int(max_quotes or DEFAULT_MAX_QUOTES_PER_FILE)):
            break
    return {
        "ok": True,
        "operation_type": "quote_corpus_packet",
        "schema_version": SCHEMA_VERSION,
        "source_id": source_id,
        "created_at": _now(),
        **meta,
        "privacy_status": _privacy_status(path),
        "canon_status": "candidate",
        "promotion_status": "not_promoted",
        "authorial_authority": "UNKNOWN",
        "token_origin": "source_file_extraction",
        "quote_count": len(quotes),
        "quotes": quotes,
        "boundary": {
            "source_read_only": True,
            "source_mutation": False,
            "external_send": False,
            "canon_promotion": False,
            "credential_risk_skipped": True,
            "quote_storage": "bounded_exact_excerpts",
        },
    }


def _packet_text(packet: dict[str, Any]) -> str:
    source = {
        key: packet.get(key)
        for key in (
            "source_path", "name", "extension", "size", "modified", "source_sha256",
            "text_sha256", "privacy_status", "canon_status", "promotion_status",
            "authorial_authority", "token_origin", "truncated",
        )
    }
    lines = [
        f".AI:QUOTE_SOURCE_PACKET/{packet.get('source_id')}",
        "@SOURCE " + json.dumps(source, ensure_ascii=True, sort_keys=True),
        "@BOUNDARY " + json.dumps(packet.get("boundary") or {}, ensure_ascii=True, sort_keys=True),
    ]
    for quote in packet.get("quotes") or []:
        lines.append("@QUOTE " + json.dumps(quote, ensure_ascii=True, sort_keys=True))
    lines.append("")
    return "\n".join(lines)


def _packet_path(source_id: str) -> Path:
    return PACKET_DIR / f"{source_id}.ai"


def ingest_file(
    path_text: str | Path,
    *,
    max_quotes: int = DEFAULT_MAX_QUOTES_PER_FILE,
    max_quote_chars: int = DEFAULT_QUOTE_CHARS,
) -> dict[str, Any]:
    """Create one .AI quote packet and append searchable quote rows."""
    _ensure_dirs()
    packet = build_source_packet(path_text, max_quotes=max_quotes, max_quote_chars=max_quote_chars)
    if not packet.get("ok"):
        receipt = {
            "receipt_kind": "quote_corpus_ingest_receipt",
            "schema_version": SCHEMA_VERSION,
            "timestamp": _now(),
            "status": packet.get("status") or "not_ok",
            "source_path": packet.get("source_path"),
            "quote_count": 0,
            "boundary": packet.get("boundary"),
        }
        receipt["receipt_hash_sha256"] = _sha256_text(json.dumps(receipt, sort_keys=True, ensure_ascii=True))
        _append_jsonl(RECEIPT_FILE, receipt)
        return {**packet, "receipt_path": str(RECEIPT_FILE)}

    source_id = str(packet["source_id"])
    packet_path = _packet_path(source_id)
    packet_text = _packet_text(packet)
    packet_path.write_text(packet_text, encoding="utf-8")
    existing_quote_ids = {str(row.get("quote_id")) for row in _jsonl(MANIFEST_FILE)}
    written = 0
    for quote in packet.get("quotes") or []:
        if quote["quote_id"] in existing_quote_ids:
            continue
        row = {
            "schema_version": SCHEMA_VERSION,
            "source_id": source_id,
            "quote_id": quote["quote_id"],
            "quote_index": quote["quote_index"],
            "quote_text": quote["quote_text"],
            "quote_sha256": quote["quote_sha256"],
            "source_path": packet["source_path"],
            "name": packet["name"],
            "extension": packet["extension"],
            "source_sha256": packet["source_sha256"],
            "text_sha256": packet["text_sha256"],
            "packet_path": str(packet_path),
            "line_start": quote["line_start"],
            "line_end": quote["line_end"],
            "char_start": quote["char_start"],
            "char_end": quote["char_end"],
            "privacy_status": packet["privacy_status"],
            "canon_status": packet["canon_status"],
            "promotion_status": packet["promotion_status"],
            "created_at": packet["created_at"],
        }
        _append_jsonl(MANIFEST_FILE, row)
        written += 1
    receipt = {
        "receipt_kind": "quote_corpus_ingest_receipt",
        "schema_version": SCHEMA_VERSION,
        "timestamp": _now(),
        "status": "ok",
        "source_id": source_id,
        "source_path": packet["source_path"],
        "packet_path": str(packet_path),
        "quote_count": packet["quote_count"],
        "quotes_written": written,
        "source_sha256": packet["source_sha256"],
        "text_sha256": packet["text_sha256"],
        "packet_sha256": _sha256_text(packet_text),
        "boundary": packet["boundary"],
    }
    receipt["receipt_hash_sha256"] = _sha256_text(json.dumps(receipt, sort_keys=True, ensure_ascii=True))
    _append_jsonl(RECEIPT_FILE, receipt)
    status = status_payload()
    status["latest_receipt"] = receipt
    _write_json(LATEST_STATUS_FILE, status)
    return {
        "ok": True,
        "operation_type": "quote_corpus_ingest_file",
        "source_id": source_id,
        "source_path": packet["source_path"],
        "packet_path": str(packet_path),
        "quote_count": packet["quote_count"],
        "quotes_written": written,
        "manifest_path": str(MANIFEST_FILE),
        "receipt_path": str(RECEIPT_FILE),
        "boundary": packet["boundary"],
    }


def _iter_supported_files(query: str = ""):
    terms = [term.lower() for term in re.findall(r"[A-Za-z0-9_\-]{2,}", query or "")]
    seen = 0
    quote_root = QUOTE_DIR
    for root in _roots():
        for dirpath, dirnames, filenames in os.walk(root, topdown=True):
            dirnames[:] = [
                d for d in dirnames
                if not _is_under(Path(dirpath) / d, quote_root)
                and d.lower() not in {".git", "node_modules", "__pycache__", ".venv", "venv", "sandbox.trash"}
            ]
            for filename in filenames:
                seen += 1
                if seen > MAX_SCAN_FILES:
                    return
                path = Path(dirpath) / filename
                if _is_under(path, quote_root):
                    continue
                if path.suffix.lower() not in SUPPORTED_EXTS:
                    continue
                if _secret_risk(path):
                    continue
                lowered = str(path).lower()
                if terms and not all(term in lowered for term in terms):
                    continue
                yield path


def build_quote_index(
    query: str = "",
    *,
    limit: int = DEFAULT_INGEST_LIMIT,
    max_quotes_per_file: int = DEFAULT_MAX_QUOTES_PER_FILE,
) -> dict[str, Any]:
    """Ingest a bounded path-query batch into quote packets."""
    bounded_limit = max(1, min(int(limit or DEFAULT_INGEST_LIMIT), MAX_INGEST_LIMIT))
    created: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    existing_sources = {str(row.get("source_path")) for row in _jsonl(MANIFEST_FILE)}
    for path in _iter_supported_files(query):
        if str(path) in existing_sources:
            continue
        try:
            created.append(ingest_file(path, max_quotes=max_quotes_per_file))
            existing_sources.add(str(path))
        except Exception as exc:
            errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
        if len(created) >= bounded_limit:
            break
    receipt = {
        "receipt_kind": "quote_corpus_batch_receipt",
        "schema_version": SCHEMA_VERSION,
        "timestamp": _now(),
        "query": _clean_inline(query),
        "created_count": len(created),
        "error_count": len(errors),
        "packet_paths": [row.get("packet_path") for row in created],
        "manifest_path": str(MANIFEST_FILE),
        "boundary": {
            "bounded_batch": True,
            "source_read_only": True,
            "source_mutation": False,
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
        "operation_type": "quote_corpus_batch_ingest",
        "query": _clean_inline(query),
        "created_count": len(created),
        "error_count": len(errors),
        "created": created,
        "errors": errors[:10],
        "manifest_path": str(MANIFEST_FILE),
        "receipt_path": str(RECEIPT_FILE),
        "boundary": receipt["boundary"],
    }


def search_quotes(query: str, *, limit: int = 8) -> dict[str, Any]:
    q = _clean_inline(query)
    if not q:
        raise QuoteCorpusError("query is required")
    terms = [term.lower() for term in re.findall(r"[A-Za-z0-9_\-]{2,}", q) if term.lower() not in STOPWORDS]
    if not terms:
        terms = [term.lower() for term in re.findall(r"[A-Za-z0-9_\-]{2,}", q)]
    bounded_limit = max(1, min(int(limit or 8), 50))
    hits: list[dict[str, Any]] = []
    for row in reversed(_jsonl(MANIFEST_FILE)):
        haystack = " ".join([
            str(row.get("source_path") or ""),
            str(row.get("name") or ""),
            str(row.get("quote_text") or ""),
        ]).lower()
        if terms and not all(term in haystack for term in terms):
            continue
        hits.append(dict(row))
        if len(hits) >= bounded_limit:
            break
    return {
        "ok": True,
        "operation_type": "quote_corpus_search",
        "query": q,
        "result_count": len(hits),
        "results": hits,
        "manifest_path": str(MANIFEST_FILE),
        "boundary": "searched local quote-corpus exact excerpts only",
    }


def status_payload() -> dict[str, Any]:
    _ensure_dirs()
    rows = _jsonl(MANIFEST_FILE)
    receipts = _jsonl(RECEIPT_FILE)
    source_ids = {str(row.get("source_id")) for row in rows if row.get("source_id")}
    return {
        "ok": True,
        "operation_type": "quote_corpus_status",
        "schema_version": SCHEMA_VERSION,
        "source_count": len(source_ids),
        "quote_count": len(rows),
        "receipt_count": len(receipts),
        "manifest_path": str(MANIFEST_FILE),
        "packet_dir": str(PACKET_DIR),
        "roots": [str(root) for root in _roots()],
        "latest_receipt": receipts[-1] if receipts else None,
        "boundary": "local read-only exact quote corpus; source files unchanged; no external send",
    }


def context_block(user_text: str, *, max_chars: int = 1600) -> str:
    words = [
        word for word in re.findall(r"[A-Za-z0-9_\-]{3,}", str(user_text or ""))
        if word.lower() not in STOPWORDS
    ]
    if not words:
        return ""
    queries: list[str] = []
    for size in (5, 3, 2, 1):
        if len(words) >= size:
            query = " ".join(words[:size])
            if query not in queries:
                queries.append(query)
    hits: list[dict[str, Any]] = []
    for query in queries:
        try:
            hits = search_quotes(query, limit=3).get("results") or []
        except Exception:
            hits = []
        if hits:
            break
    if not hits:
        return ""
    lines = ["[QUOTE_CORPUS - exact excerpts; cite source_path and line range when used]"]
    for hit in hits:
        lines.append(f"- {hit.get('name')} ({hit.get('source_path')}:{hit.get('line_start')})")
        quote = str(hit.get("quote_text") or "").replace("\n", " ")
        lines.append(f"  quote: {quote[:360]}")
    return "\n".join(lines)[:max_chars]


def parse_quote_request(text: str) -> dict[str, str] | None:
    raw = str(text or "").strip()
    lower = raw.lower()
    if not raw:
        return None
    if lower in {"/quote-corpus", "/quote-corpus-status", "/quote-status"}:
        return {"mode": "status", "value": ""}
    for prefix in ("/quote-corpus-ingest ", "/quote-ingest "):
        if lower.startswith(prefix):
            return {"mode": "ingest", "value": raw[len(prefix):].strip()}
    if lower in {"/quote-corpus-ingest", "/quote-ingest"}:
        return {"mode": "ingest", "value": ""}
    for prefix in ("/quote-corpus-search ", "/quote-search "):
        if lower.startswith(prefix):
            return {"mode": "search", "value": raw[len(prefix):].strip()}
    for prefix in ("/quote-source ", "/quote-packet "):
        if lower.startswith(prefix):
            return {"mode": "file", "value": raw[len(prefix):].strip()}
    return None


def format_result(result: dict[str, Any]) -> str:
    op = result.get("operation_type")
    if op == "quote_corpus_status":
        latest = result.get("latest_receipt") or {}
        return "\n".join([
            "QUOTE CORPUS STATUS",
            "boundary: local read-only exact excerpts; no source mutation; no external send",
            f"source_count: {result.get('source_count', 0)}",
            f"quote_count: {result.get('quote_count', 0)}",
            f"receipt_count: {result.get('receipt_count', 0)}",
            f"manifest_path: {result.get('manifest_path')}",
            f"packet_dir: {result.get('packet_dir')}",
            f"latest_created_count: {latest.get('created_count', 0) if latest else 0}",
        ])
    if op in {"quote_corpus_batch_ingest", "quote_corpus_ingest_file"}:
        lines = [
            "QUOTE CORPUS INGEST",
            "boundary: read-only exact quote packets; source files unchanged",
            f"created_count: {result.get('created_count', 1 if result.get('packet_path') else 0)}",
            f"quote_count: {result.get('quote_count', '')}",
            f"manifest_path: {result.get('manifest_path')}",
            f"receipt_path: {result.get('receipt_path')}",
        ]
        for row in (result.get("created") or [])[:8]:
            lines.append(f"- {Path(str(row.get('source_path') or '')).name} -> {row.get('packet_path')} ({row.get('quote_count', 0)} quotes)")
        if result.get("packet_path"):
            lines.append(f"- {Path(str(result.get('source_path') or '')).name} -> {result.get('packet_path')} ({result.get('quote_count', 0)} quotes)")
        for err in (result.get("errors") or [])[:5]:
            lines.append(f"! {err.get('path')}: {err.get('error')}")
        return "\n".join(line for line in lines if line is not None)
    if op == "quote_corpus_search":
        lines = [
            "QUOTE CORPUS SEARCH",
            f"query: {result.get('query')}",
            f"result_count: {result.get('result_count', 0)}",
        ]
        for idx, row in enumerate(result.get("results") or [], 1):
            lines.append(f"{idx}. {row.get('name')}:{row.get('line_start')}-{row.get('line_end')}")
            lines.append(f"   source_path: {row.get('source_path')}")
            quote = _clean_inline(str(row.get("quote_text") or ""))
            if quote:
                lines.append(f"   quote: {quote[:260]}")
        if not result.get("results"):
            lines.append("no_results: ingest quote packets or try a different query")
        return "\n".join(lines)
    return json.dumps(result, indent=2, ensure_ascii=True)
